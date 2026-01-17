"""
短信验证码管理器
复用 EmailVerificationManager 的逻辑结构
"""
import json
import logging
import secrets
import time
from typing import Optional

log = logging.getLogger(__name__)


def generate_sms_code(length: int = 6) -> str:
    """生成数字验证码"""
    alphabet = "0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class SMSVerificationManager:
    """存储和验证短信验证码，使用 Redis 或内存存储"""

    def __init__(self, redis=None, prefix: str = "sms:code"):
        self.redis = redis
        self.prefix = prefix
        self.memory_store: dict[str, dict] = {}

    def _now(self) -> int:
        return int(time.time())

    def _key(self, phone: str) -> str:
        return f"{self.prefix}:{phone}"

    async def _delete(self, phone: str):
        key = self._key(phone)
        if self.redis:
            await self.redis.delete(key)
        else:
            self.memory_store.pop(key, None)

    async def _load_record(self, phone: str) -> Optional[dict]:
        """
        从 Redis 或本地内存检索验证记录
        检查过期时间，如已过期则自动删除
        """
        key = self._key(phone)
        record = None
        if self.redis:
            raw = await self.redis.get(key)
            log.debug(f"[SMSAuth] Loading from Redis - Key: {key}, Raw Value: {raw}")
            if raw:
                try:
                    record = json.loads(raw)
                except Exception:
                    log.debug("Failed to decode SMS verification record for %s", phone)
        else:
            record = self.memory_store.get(key)
            log.debug(f"[SMSAuth] Loading from Memory - Key: {key}, Value: {record}")

        if not record:
            return None

        # 检查过期
        expires_at = record.get("expires_at")
        if expires_at and expires_at <= self._now():
            log.debug(
                f"[SMSAuth] Record expired for {phone}. ExpiresAt: {expires_at}, Now: {self._now()}"
            )
            await self._delete(phone)
            return None

        return record

    async def _save_record(self, phone: str, record: dict, ttl: int):
        """保存验证记录到 Redis（带TTL）或本地内存"""
        key = self._key(phone)
        ttl = max(ttl, 1)
        if self.redis:
            log.debug(
                f"[SMSAuth] Saving to Redis - Key: {key}, Value: {record}, TTL: {ttl}"
            )
            await self.redis.set(key, json.dumps(record), ex=ttl)
        else:
            log.debug(f"[SMSAuth] Saving to Memory - Key: {key}, Value: {record}")
            self.memory_store[key] = record

    async def can_send(self, phone: str, send_interval: int) -> tuple[bool, int]:
        """
        检查是否可以向该手机号发送新的验证码
        强制执行 send_interval 定义的冷却期
        
        Returns:
            (bool, int): (True if allowed, 0) 或 (False, remaining_seconds_to_wait)
        """
        record = await self._load_record(phone)
        if not record:
            return True, 0

        sent_at = record.get("sent_at")
        if sent_at:
            delta = self._now() - sent_at
            remaining = send_interval - delta
            if remaining > 0:
                log.debug(f"[SMSAuth] Rate limited for {phone}. Remaining: {remaining}s")
                return False, remaining

        return True, 0

    async def store_code(
        self,
        phone: str,
        code: str,
        ttl: int,
        max_attempts: int,
        ip: Optional[str] = None,
    ):
        """
        生成并存储新的验证记录
        记录包含：code, 过期时间, 剩余尝试次数, 发送时间戳, 以及可选的IP
        """
        now = self._now()
        record = {
            "code": code,
            "expires_at": now + ttl,
            "attempts_left": max_attempts,
            "sent_at": now,
            **({"ip": ip} if ip else {}),
        }
        await self._save_record(phone, record, ttl)
        log.info(f"Stored SMS verification code for {phone}")

    async def validate_code(self, phone: str, code: str) -> bool:
        """
        验证提供的验证码
        
        步骤：
        1. 检索记录（Redis/Memory），如果未找到（或已过期）则失败
        2. 显式检查过期
        3. 比较验证码
           - 如果不匹配：减少 attempts_left，如果为0则删除记录，失败
           - 如果匹配：删除记录（消耗验证码），成功
        """
        log.debug(f"[SMSAuth] Validating code for {phone}. Input Code: {code}")
        record = await self._load_record(phone)
        if not record:
            log.warning(f"SMS verification failed for {phone}: No record found.")
            return False

        ttl_left = max(record.get("expires_at", 0) - self._now(), 0)

        if record.get("code") != code:
            log.warning(
                f"SMS verification failed for {phone}: Code mismatch. Expected: {record.get('code')}, Got: {code}"
            )
            attempts_left = record.get("attempts_left", 1) - 1
            if attempts_left <= 0:
                log.warning(
                    f"[SMSAuth] Max attempts reached for {phone}. Deleting record."
                )
                await self._delete(phone)
            else:
                record["attempts_left"] = attempts_left
                await self._save_record(phone, record, ttl_left)
            return False

        log.info(f"SMS verification successful for {phone}.")
        await self._delete(phone)
        return True
