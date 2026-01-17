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

    def send_sms(self, mobile: str, code: str, scene: SMSScene = SMSScene.SIGNUP) -> Tuple[bool, str, Optional[str]]:
        """
        发送单条短信（使用模版ID 64573）

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
        # 格式: userid(大写) + "00000000" + password + timestamp
        md5_input = f"{userid_upper}00000000{self.password}{timestamp}"
        md5_pwd = hashlib.md5(md5_input.encode("utf-8")).hexdigest()

        # 4. 构建短信内容（使用已验证的模板64573）
        content_raw = SMS_TEMPLATE.format(code=code)

        # 5. content 需要 GBK 编码后 URL encode（与 test_sms.sh 完全一致）
        gbk_content = content_raw.encode("gbk")
        content_encoded = urllib.parse.quote(gbk_content, safe="")

        # 6. 生成 custid (客户流水号)
        custid = f"test{time.strftime('%Y%m%d%H%M%S', time.localtime())}"

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

        # 8. 发送HTTP请求
        api_url = f"http://{self.main_addr}/sms/v2/std/single_send"

        log.info(f"[SMS Debug] URL: {api_url}")
        log.info(f"[SMS Debug] UserID: {userid_upper}")
        log.info(f"[SMS Debug] Mobile: {mobile}")
        log.info(f"[SMS Debug] Content Raw: {content_raw}")
        log.info(f"[SMS Debug] Content Encoded: {content_encoded}")
        log.info(f"[SMS Debug] Timestamp: {timestamp}")
        log.info(f"[SMS Debug] MD5 Input: {md5_input}")
        log.info(f"[SMS Debug] MD5 Output: {md5_pwd}")

        json_data = json.dumps(payload)
        log.info(f"[SMS Debug] Request JSON: {json_data}")

        try:
            # Headers 与 test_sms.sh 完全一致
            headers = {
                "Content-Type": "application/json",
                "Accept": "*/*",
                "User-Agent": "MontnetsSDK/Go",
            }

            response = requests.post(api_url, data=json_data, headers=headers, timeout=30)

            log.info(f"[SMS Debug] Status: {response.status_code}, Response: {response.text}")

            if response.status_code != 200:
                return False, "", f"HTTP status code: {response.status_code}, body: {response.text}"

            # 9. 解析响应
            resp_data = response.json()

        except requests.RequestException as e:
            log.error(f"[SMS Debug] HTTP Error: {e}")
            return False, "", str(e)
        except json.JSONDecodeError as e:
            log.error(f"[SMS Debug] JSON Parse Error: {e}")
            return False, "", f"Failed to parse response: {e}"

        # 10. 检查结果
        result = resp_data.get("result")
        if result is None:
            return False, "", "No result field in response"

        # result 可能是 int 或 str
        if str(result) == "0":
            # 发送成功
            msgid = resp_data.get("msgid", "")
            log.info(f"SMS sent successfully to {mobile}, msgid: {msgid}")
            return True, msgid, None

        # 发送失败
        desc = resp_data.get("desc", "Unknown error")
        log.error(f"SMS send failed, result: {result}, desc: {desc}")
        return False, "", f"SMS send failed, result: {result}, desc: {desc}"


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
    log.info(f"[SMS Init] user_id={user_id}, main_addr={main_addr}, password={'*' * len(password) if password else 'EMPTY'}")
    if not user_id or not password or not main_addr:
        log.error(f"[SMS Init] Missing required config: user_id={bool(user_id)}, password={bool(password)}, main_addr={bool(main_addr)}")
        return None
    _sms_client = SMSClient(user_id, password, main_addr, bak_addrs)
    log.info(f"[SMS Init] SMS client initialized successfully with main_addr: {main_addr}")
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
