import json
import logging
import smtplib
import ssl
import time
import secrets
from typing import Optional
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

log = logging.getLogger(__name__)


def send_email(
    *,
    subject: str,
    body: str,
    to_email: str,
    smtp_server: str,
    smtp_port: int,
    smtp_username: str = "",
    smtp_password: str = "",
    from_email: str,
    from_alias: str = "",
    use_ssl: bool = True,
):
    """
    发送邮件（基于腾讯云邮件服务实现）
    - use_ssl=True: 使用 SMTP_SSL（端口 465/587）
    - use_ssl=False: 使用 SMTP（端口 25）
    """
    try:
        # 构建邮件
        message = MIMEMultipart('alternative')
        message['Subject'] = Header(subject, 'UTF-8')
        message['From'] = formataddr([from_alias, from_email])
        message['To'] = to_email

        # 添加邮件内容（HTML 格式）
        mime_text = MIMEText(body, _subtype='html', _charset='UTF-8')
        message.attach(mime_text)

        # 发送邮件
        if use_ssl:
            context = ssl.create_default_context()
            context.set_ciphers('DEFAULT')
            client = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context)
        else:
            client = smtplib.SMTP(smtp_server, smtp_port)

        client.login(smtp_username, smtp_password)
        client.sendmail(from_email, [to_email], message.as_string())
        client.quit()

        log.info(f'Email sent successfully to {to_email}')
    except smtplib.SMTPConnectError as e:
        log.error(f'SMTP connection error: {e.smtp_code} {e.smtp_error}')
        raise
    except smtplib.SMTPAuthenticationError as e:
        log.error(f'SMTP authentication error: {e.smtp_code} {e.smtp_error}')
        raise
    except smtplib.SMTPSenderRefused as e:
        log.error(f'SMTP sender refused: {e.smtp_code} {e.smtp_error}')
        raise
    except smtplib.SMTPRecipientsRefused as e:
        log.error(f'SMTP recipients refused: {e.recipients}')
        raise
    except smtplib.SMTPDataError as e:
        log.error(f'SMTP data error: {e.smtp_code} {e.smtp_error}')
        raise
    except smtplib.SMTPException as e:
        log.error(f'SMTP exception: {str(e)}')
        raise
    except Exception as e:
        log.error(f'Failed to send email: {str(e)}')
        raise

def generate_verification_code(length: int = 6) -> str:
    alphabet = "0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class EmailVerificationManager:
    """Stores and validates email verification codes using Redis if available."""

    def __init__(self, redis=None, prefix: str = "signup:code"):
        self.redis = redis
        self.prefix = prefix
        self.memory_store: dict[str, dict] = {}

    def _now(self) -> int:
        return int(time.time())

    def _key(self, email: str) -> str:
        return f"{self.prefix}:{email.lower()}"

    async def _delete(self, email: str):
        key = self._key(email)
        if self.redis:
            await self.redis.delete(key)
        else:
            self.memory_store.pop(key, None)

    async def _load_record(self, email: str) -> Optional[dict]:
        """
        Retrieves the verification record from Redis or local memory.
        Checks for expiration based on 'expires_at' and automatically deletes if expired.
        """
        key = self._key(email)
        record = None
        if self.redis:
            raw = await self.redis.get(key)
            log.debug(f"[EmailAuth] Loading from Redis - Key: {key}, Raw Value: {raw}")
            if raw:
                try:
                    record = json.loads(raw)
                except Exception:
                    log.debug("Failed to decode email verification record for %s", email)
        else:
            record = self.memory_store.get(key)
            log.debug(f"[EmailAuth] Loading from Memory - Key: {key}, Value: {record}")

        if not record:
            return None

        # Check for expiration
        expires_at = record.get("expires_at")
        if expires_at and expires_at <= self._now():
            log.debug(f"[EmailAuth] Record expired for {email}. ExpiresAt: {expires_at}, Now: {self._now()}")
            await self._delete(email)
            return None

        return record

    async def _save_record(self, email: str, record: dict, ttl: int):
        """
        Saves the verification record to Redis (with TTL) or local memory.
        """
        key = self._key(email)
        ttl = max(ttl, 1)
        if self.redis:
            log.debug(f"[EmailAuth] Saving to Redis - Key: {key}, Value: {record}, TTL: {ttl}")
            await self.redis.set(key, json.dumps(record), ex=ttl)
        else:
            log.debug(f"[EmailAuth] Saving to Memory - Key: {key}, Value: {record}")
            self.memory_store[key] = record

    async def can_send(self, email: str, send_interval: int) -> tuple[bool, int]:
        """
        Checks if a new verification code can be sent to the given email.
        Enforces a cooldown period defined by `send_interval`.
        
        Returns:
            (bool, int): (True if allowed, 0) or (False, remaining_seconds_to_wait)
        """
        record = await self._load_record(email)
        if not record:
            return True, 0

        sent_at = record.get("sent_at")
        if sent_at:
            delta = self._now() - sent_at
            remaining = send_interval - delta
            if remaining > 0:
                log.debug(f"[EmailAuth] Rate limited for {email}. Remaining: {remaining}s")
                return False, remaining

        return True, 0

    async def store_code(
        self,
        email: str,
        code: str,
        ttl: int,
        max_attempts: int,
        ip: Optional[str] = None,
    ):
        """
        Generates and stores a new verification record.
        Record includes: code, expiration time, remaining attempts, sent timestamp, and optionally IP.
        """
        now = self._now()
        record = {
            "code": code,
            "expires_at": now + ttl,
            "attempts_left": max_attempts,
            "sent_at": now,
            **({"ip": ip} if ip else {}),
        }
        await self._save_record(email, record, ttl)
        # ⚠️ SECURITY WARNING: Logging the code is for debugging purposes only.
        log.info(f"Stored verification code for {email}. Code: {code}")

    async def validate_code(self, email: str, code: str) -> bool:
        """
        Validates the provided code against the stored record.
        
        Steps:
        1. Retrieve record (Redis/Memory). If not found (or expired), fail.
        2. Check expiration explicitly.
        3. Compare codes.
           - If mismatch: Decrement 'attempts_left'. If 0, delete record. Fail.
           - If match: Delete record (consumes the code). Success.
        """
        # # 调试模式：@test.com 邮箱接受固定验证码 951753
        # if email.lower().endswith("@test.com") and code == "951753":
        #     log.info(f"Debug mode: accepted test verification code for {email}")
        #     # 清理可能存在的验证码记录
        #     self._delete(email)
        #     return True

        log.debug(f"[EmailAuth] Validating code for {email}. Input Code: {code}")
        record = await self._load_record(email)
        if not record:
            log.warning(f"Verification failed for {email}: No record found.")
            return False

        ttl_left = max(record.get("expires_at", 0) - self._now(), 0)

        if record.get("code") != code:
            log.warning(f"Verification failed for {email}: Code mismatch. Expected: {record.get('code')}, Got: {code}")
            attempts_left = record.get("attempts_left", 1) - 1
            if attempts_left <= 0:
                log.warning(f"[EmailAuth] Max attempts reached for {email}. Deleting record.")
                await self._delete(email)
            else:
                record["attempts_left"] = attempts_left
                await self._save_record(email, record, ttl_left)
            return False

        log.info(f"Verification successful for {email}.")
        await self._delete(email)
        return True
