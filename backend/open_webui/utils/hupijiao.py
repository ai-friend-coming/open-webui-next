"""
虎皮椒聚合支付服务

支持：
- 微信支付（H5跳转）
"""

import hashlib
import time
import logging
import requests
from typing import Optional, Tuple
from urllib.parse import urlencode, unquote_plus

from open_webui.env import (
    HUPIJIAO_APP_ID,
    HUPIJIAO_APP_SECRET,
    HUPIJIAO_CALLBACK_DOMAIN,
)

log = logging.getLogger(__name__)

# 虎皮椒API端点
HUPIJIAO_API_URL = "https://api.xunhupay.com/payment/do.html"

# 回调路径常量
NOTIFY_PATH = "/api/v1/billing/payment/hupijiao/notify"
RETURN_PATH = "/api/v1/billing/payment/hupijiao/return"
CALLBACK_PATH = "/api/v1/billing/payment/hupijiao/callback"


def get_notify_url() -> str:
    """获取异步通知URL"""
    if HUPIJIAO_CALLBACK_DOMAIN:
        return f"{HUPIJIAO_CALLBACK_DOMAIN}{NOTIFY_PATH}"
    return ""


def get_return_url() -> str:
    """获取同步返回URL"""
    if HUPIJIAO_CALLBACK_DOMAIN:
        return f"{HUPIJIAO_CALLBACK_DOMAIN}{RETURN_PATH}"
    return ""


def get_callback_url() -> str:
    """获取失败回调URL"""
    if HUPIJIAO_CALLBACK_DOMAIN:
        return f"{HUPIJIAO_CALLBACK_DOMAIN}{CALLBACK_PATH}"
    return ""


# 启动时打印配置状态
print(f"[Hupijiao] HUPIJIAO_APP_ID = {HUPIJIAO_APP_ID[:8] + '***' if HUPIJIAO_APP_ID else '(未配置)'}")
print(f"[Hupijiao] HUPIJIAO_CALLBACK_DOMAIN = {HUPIJIAO_CALLBACK_DOMAIN or '(未配置)'}")
print(f"[Hupijiao] notify_url = {get_notify_url() or '(未配置)'}")
print(f"[Hupijiao] return_url = {get_return_url() or '(未配置)'}")


def is_hupijiao_configured() -> bool:
    """检查虎皮椒是否已配置"""
    return bool(HUPIJIAO_APP_ID and HUPIJIAO_APP_SECRET and HUPIJIAO_CALLBACK_DOMAIN)


def generate_sign(params: dict, app_secret: str) -> str:
    """
    生成虎皮椒签名

    算法：
    1. 参数按 key 字母排序
    2. URL 编码后再解码（unquote_plus）
    3. 拼接 AppSecret
    4. MD5 加密（小写）
    """
    sorted_params = sorted(params.items())
    query_string = unquote_plus(urlencode(sorted_params))
    sign_string = f"{query_string}{app_secret}"
    return hashlib.md5(sign_string.encode("utf-8")).hexdigest()


def create_wechat_payment(
    out_trade_no: str,
    amount_yuan: float,
    subject: str = "账户充值",
) -> Tuple[bool, str, Optional[str]]:
    """
    创建微信支付订单（虎皮椒）

    Args:
        out_trade_no: 商户订单号
        amount_yuan: 金额（元）
        subject: 订单标题

    Returns:
        Tuple[success, message, pay_url]
    """
    if not is_hupijiao_configured():
        return False, "虎皮椒支付未配置", None

    # 在 return_url 和 callback_url 中附加订单号，因为虎皮椒同步返回不会传递订单号
    return_url_with_order = f"{get_return_url()}?trade_order_id={out_trade_no}"
    callback_url_with_order = f"{get_callback_url()}?trade_order_id={out_trade_no}"

    params = {
        "version": "1.1",
        "lang": "zh-cn",
        "plugins": "cakumi",
        "appid": HUPIJIAO_APP_ID,
        "trade_order_id": out_trade_no,
        "payment": "wechat",
        "is_app": "Y",
        "total_fee": f"{amount_yuan:.2f}",
        "title": subject,
        "description": "",
        "time": str(int(time.time())),
        "notify_url": get_notify_url(),
        "return_url": return_url_with_order,
        "callback_url": callback_url_with_order,
        "nonce_str": str(int(time.time() * 1000)),
    }
    params["hash"] = generate_sign(params, HUPIJIAO_APP_SECRET)

    try:
        headers = {"Referer": "https://cakumi.com/"}
        response = requests.post(HUPIJIAO_API_URL, data=params, headers=headers, timeout=10)
        result = response.json()

        log.info(f"虎皮椒API响应: {result}")

        # 虎皮椒成功响应: {"errcode": 0, "url": "..."}
        # 或直接返回 {"url": "..."} 不带 errcode
        if result.get("errcode", 0) == 0 and result.get("url"):
            pay_url = result.get("url")
            log.info(f"创建微信支付订单成功: {out_trade_no}")
            return True, "success", pay_url
        else:
            error_msg = result.get("errmsg") or result.get("msg") or "未知错误"
            log.error(f"创建微信支付订单失败: {out_trade_no}, {error_msg}, response={result}")
            return False, error_msg, None

    except requests.RequestException as e:
        log.error(f"创建微信支付订单网络异常: {out_trade_no}, {e}")
        return False, f"网络请求失败: {str(e)}", None
    except Exception as e:
        import traceback
        log.error(f"创建微信支付订单异常: {out_trade_no}, {e}")
        log.error(f"详细堆栈: {traceback.format_exc()}")
        return False, str(e), None


def verify_notify_sign(params: dict) -> bool:
    """
    验证虎皮椒回调签名

    Args:
        params: 回调参数（包含 hash 字段）

    Returns:
        签名是否有效
    """
    if not is_hupijiao_configured():
        return False

    # 复制参数避免修改原始数据
    params_copy = dict(params)
    received_hash = params_copy.pop("hash", "")

    if not received_hash:
        log.error("虎皮椒回调缺少签名")
        return False

    expected_hash = generate_sign(params_copy, HUPIJIAO_APP_SECRET)

    if received_hash == expected_hash:
        log.info(f"虎皮椒回调验签成功: {params.get('trade_order_id')}")
        return True
    else:
        log.error(
            f"虎皮椒回调验签失败: {params.get('trade_order_id')}, "
            f"received={received_hash}, expected={expected_hash}"
        )
        return False
