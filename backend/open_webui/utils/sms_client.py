"""
梦网SMS客户端 Python 实现
基于验证通过的 test_sms.sh 修改
"""
import hashlib
import json
import logging
import time
import urllib.parse
from enum import Enum
from typing import Optional, Tuple

import requests

log = logging.getLogger(__name__)


class SMSScene(Enum):
    """短信验证码场景"""
    SIGNUP = "signup"       # 注册
    RESET = "reset"         # 密码重置
    LOGIN = "login"         # 登录验证


# 使用模版ID 64573（已验证通过）
# 模板格式: 您的验证码是{d1-10}，在{d1-3}分钟内有效。如非本人操作请忽略本短信。
SMS_TEMPLATE = "您的验证码是{code}，在5分钟内有效。如非本人操作请忽略本短信。"


class SMSClient:
    """梦网SMS客户端 - 基于验证通过的 test_sms.sh"""

    # 需要触发故障转移的错误码（网络/服务端问题，非业务逻辑错误）
    FAILOVER_RESULT_CODES = {
        "-3",   # 连接失败
        "-4",   # 超时
        "-6",   # 系统忙
        "-7",   # 服务不可用
        "-12",  # 网关故障
        "-14",  # 服务器内部错误
    }

    def __init__(
        self,
        user_id: str,
        password: str,
        main_addr: str,
        bak_addrs: Optional[list[str]] = None,
    ):
        self.user_id = user_id
        self.password = password
        self.main_addr = main_addr
        self.bak_addrs = bak_addrs or []

    def _send_to_addr(
        self,
        addr: str,
        payload: dict,
        mobile: str,
    ) -> Tuple[bool, str, Optional[str], bool]:
        """
        向指定地址发送短信

        Args:
            addr: SMS API 地址
            payload: 请求数据
            mobile: 手机号（用于日志）

        Returns:
            (success, msgid_or_error, error_message, should_failover)
            should_failover: 是否应该尝试备用地址
        """
        api_url = f"http://{addr}/sms/v2/std/single_send"
        json_data = json.dumps(payload)

        log.info(f"[SMS] Sending to {addr}, mobile: {mobile}")
        log.debug(f"[SMS Debug] URL: {api_url}")
        log.debug(f"[SMS Debug] Request JSON: {json_data}")

        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "*/*",
                "User-Agent": "MontnetsSDK/Go",
            }

            response = requests.post(api_url, data=json_data, headers=headers, timeout=30)

            log.info(f"[SMS] Response from {addr}: status={response.status_code}")
            log.debug(f"[SMS Debug] Response body: {response.text}")

            # HTTP 5xx 错误触发故障转移
            if response.status_code >= 500:
                error_msg = f"HTTP {response.status_code} from {addr}"
                log.warning(f"[SMS] {error_msg}, will try failover")
                return False, "", error_msg, True

            # 其他 HTTP 错误不触发故障转移（如 4xx 通常是请求问题）
            if response.status_code != 200:
                error_msg = f"HTTP status code: {response.status_code}, body: {response.text}"
                return False, "", error_msg, False

            resp_data = response.json()

        except requests.Timeout as e:
            error_msg = f"Timeout connecting to {addr}: {e}"
            log.warning(f"[SMS] {error_msg}, will try failover")
            return False, "", error_msg, True
        except requests.ConnectionError as e:
            error_msg = f"Connection error to {addr}: {e}"
            log.warning(f"[SMS] {error_msg}, will try failover")
            return False, "", error_msg, True
        except requests.RequestException as e:
            error_msg = f"Request error to {addr}: {e}"
            log.warning(f"[SMS] {error_msg}, will try failover")
            return False, "", error_msg, True
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse response from {addr}: {e}"
            log.error(f"[SMS] {error_msg}")
            return False, "", error_msg, False

        result = resp_data.get("result")
        if result is None:
            return False, "", "No result field in response", False

        result_str = str(result)

        if result_str == "0":
            msgid = resp_data.get("msgid", "")
            log.info(f"[SMS] Sent successfully via {addr}, mobile: {mobile}, msgid: {msgid}")
            return True, msgid, None, False

        # 检查是否需要故障转移
        desc = resp_data.get("desc", "Unknown error")
        error_msg = f"SMS send failed, result: {result}, desc: {desc}"

        if result_str in self.FAILOVER_RESULT_CODES:
            log.warning(f"[SMS] {error_msg} from {addr}, will try failover")
            return False, "", error_msg, True

        # 业务逻辑错误（如余额不足、黑名单等）不触发故障转移
        log.error(f"[SMS] {error_msg}")
        return False, "", error_msg, False

    def send_sms(self, mobile: str, code: str, scene: SMSScene = SMSScene.SIGNUP) -> Tuple[bool, str, Optional[str]]:
        """
        发送单条短信（使用模版ID 64573），支持故障转移

        Args:
            mobile: 手机号
            code: 验证码
            scene: 验证码场景 (signup/reset/login)

        Returns:
            (success, msgid_or_error, error_message)
        """
        # 1. userid 必须大写
        userid_upper = self.user_id.upper()

        # 2. 生成时间戳 (格式: MMDDHHmmss)
        timestamp = time.strftime("%m%d%H%M%S", time.localtime())

        # 3. 计算MD5加密密码
        md5_input = f"{userid_upper}00000000{self.password}{timestamp}"
        md5_pwd = hashlib.md5(md5_input.encode("utf-8")).hexdigest()

        # 4. 构建短信内容
        content_raw = SMS_TEMPLATE.format(code=code)

        # 5. GBK 编码后 URL encode
        gbk_content = content_raw.encode("gbk")
        content_encoded = urllib.parse.quote(gbk_content, safe="")

        # 6. 生成 custid
        custid = f"sms{time.strftime('%Y%m%d%H%M%S', time.localtime())}{mobile[-4:]}"

        # 7. 构建请求数据
        payload = {
            "userid": userid_upper,
            "pwd": md5_pwd,
            "mobile": mobile,
            "content": content_encoded,
            "timestamp": timestamp,
            "exno": "",
            "custid": custid,
            "exdata": "",
            "svrtype": "",
        }

        log.debug(f"[SMS Debug] UserID: {userid_upper}")
        log.debug(f"[SMS Debug] Mobile: {mobile}")
        log.debug(f"[SMS Debug] Content Raw: {content_raw}")
        log.debug(f"[SMS Debug] Timestamp: {timestamp}")

        # 8. 构建地址列表：主地址 + 备用地址
        all_addrs = [self.main_addr] + self.bak_addrs
        last_error = ""

        for i, addr in enumerate(all_addrs):
            addr_type = "main" if i == 0 else f"backup-{i}"
            log.info(f"[SMS] Trying {addr_type} address: {addr}")

            success, msgid, error, should_failover = self._send_to_addr(addr, payload, mobile)

            if success:
                if i > 0:
                    log.info(f"[SMS] Successfully sent via {addr_type} address after failover")
                return True, msgid, None

            last_error = error

            if not should_failover:
                log.info(f"[SMS] Not triggering failover for error: {error}")
                break

            if i < len(all_addrs) - 1:
                log.info(f"[SMS] Failover: switching from {addr} to {all_addrs[i + 1]}")

        log.error(f"[SMS] All addresses failed for mobile {mobile}, last error: {last_error}")
        return False, "", last_error


# 全局SMS客户端实例（惰性初始化）
_sms_client: Optional[SMSClient] = None


def get_sms_client() -> Optional[SMSClient]:
    """获取全局SMS客户端实例"""
    global _sms_client
    return _sms_client


def init_sms_client(
    user_id: str,
    password: str,
    main_addr: str,
    bak_addrs: Optional[list[str]] = None,
) -> Optional[SMSClient]:
    """初始化全局SMS客户端"""
    global _sms_client
    bak_addrs = bak_addrs or []
    log.info(f"[SMS Init] user_id={user_id}, main_addr={main_addr}, bak_addrs={bak_addrs}, password={'*' * len(password) if password else 'EMPTY'}")
    if not user_id or not password or not main_addr:
        log.error(f"[SMS Init] Missing required config: user_id={bool(user_id)}, password={bool(password)}, main_addr={bool(main_addr)}")
        return None
    _sms_client = SMSClient(user_id, password, main_addr, bak_addrs)
    log.info(f"[SMS Init] SMS client initialized with main_addr: {main_addr}, backup addresses: {len(bak_addrs)}")
    return _sms_client


def send_sms_code(mobile: str, code: str, scene: SMSScene = SMSScene.SIGNUP) -> Tuple[bool, str, Optional[str]]:
    """
    发送短信验证码的便捷函数

    Args:
        mobile: 手机号
        code: 验证码
        scene: 验证码场景 (signup/reset/login)

    Returns:
        (success, msgid_or_error, error_message)
    """
    client = get_sms_client()
    if client is None:
        return False, "", "SMS client not initialized"
    return client.send_sms(mobile, code, scene)
