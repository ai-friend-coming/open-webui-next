"""
支付宝支付服务

支持：
- 当面付（扫码支付）- PC端
- 手机网站支付（H5）- 移动端
"""

import logging
from typing import Optional, Tuple
from urllib.parse import parse_qs, unquote

from open_webui.env import (
    ALIPAY_APP_ID,
    ALIPAY_PRIVATE_KEY,
    ALIPAY_PUBLIC_KEY,
    ALIPAY_CALLBACK_DOMAIN,
    ALIPAY_SANDBOX,
)

# 回调路径常量
NOTIFY_PATH = "/api/v1/billing/payment/notify"
RETURN_PATH = "/api/v1/billing/payment/return"


def get_notify_url() -> str:
    """获取异步通知URL"""
    if ALIPAY_CALLBACK_DOMAIN:
        return f"{ALIPAY_CALLBACK_DOMAIN}{NOTIFY_PATH}"
    return ""


def get_return_url() -> str:
    """获取同步返回URL"""
    if ALIPAY_CALLBACK_DOMAIN:
        return f"{ALIPAY_CALLBACK_DOMAIN}{RETURN_PATH}"
    return ""

log = logging.getLogger(__name__)

# 启动时打印配置状态（使用 print 确保可见）
print(f"[Alipay] ALIPAY_CALLBACK_DOMAIN = {ALIPAY_CALLBACK_DOMAIN or '(未配置)'}")
print(f"[Alipay] notify_url = {get_notify_url() or '(未配置)'}")
print(f"[Alipay] return_url = {get_return_url() or '(未配置)'}")
print(f"[Alipay] ALIPAY_SANDBOX = {ALIPAY_SANDBOX}")


def is_alipay_configured() -> bool:
    """检查支付宝是否已配置"""
    return bool(ALIPAY_APP_ID and ALIPAY_PRIVATE_KEY and ALIPAY_PUBLIC_KEY)


def get_alipay_client():
    """
    获取支付宝客户端

    Returns:
        DefaultAlipayClient 实例
    """
    if not is_alipay_configured():
        raise ValueError("支付宝配置不完整，请检查环境变量")

    try:
        from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
        from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
    except ImportError:
        raise ImportError("请安装 alipay-sdk-python: pip install alipay-sdk-python")

    config = AlipayClientConfig()
    config.app_id = ALIPAY_APP_ID
    config.app_private_key = ALIPAY_PRIVATE_KEY
    config.alipay_public_key = ALIPAY_PUBLIC_KEY

    if ALIPAY_SANDBOX:
        config.server_url = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"
    else:
        config.server_url = "https://openapi.alipay.com/gateway.do"

    return DefaultAlipayClient(alipay_client_config=config)


def create_qr_payment(
    out_trade_no: str, amount_yuan: float, subject: str = "账户充值"
) -> Tuple[bool, str, Optional[str]]:
    """
    创建扫码支付订单

    Args:
        out_trade_no: 商户订单号
        amount_yuan: 金额（元）
        subject: 订单标题

    Returns:
        Tuple[success, message, qr_code]
    """
    try:
        from alipay.aop.api.domain.AlipayTradePrecreateModel import (
            AlipayTradePrecreateModel,
        )
        from alipay.aop.api.request.AlipayTradePrecreateRequest import (
            AlipayTradePrecreateRequest,
        )

        client = get_alipay_client()

        model = AlipayTradePrecreateModel()
        model.out_trade_no = out_trade_no
        model.total_amount = f"{amount_yuan:.2f}"
        model.subject = subject
        model.timeout_express = "15m"  # 15分钟过期

        request = AlipayTradePrecreateRequest(biz_model=model)
        notify_url = get_notify_url()
        if notify_url:
            request.notify_url = notify_url

        response = client.execute(request)

        # 解析响应（可能是字符串或对象）
        if isinstance(response, str):
            import json
            response = json.loads(response)

        # 支持 dict 和对象两种格式
        if isinstance(response, dict):
            code = response.get("code")
            if code == "10000":
                qr_code = response.get("qr_code")
                log.info(f"创建支付宝订单成功: {out_trade_no}")
                return True, "success", qr_code
            else:
                error_msg = response.get("sub_msg") or response.get("msg") or "未知错误"
                log.error(f"创建支付宝订单失败: {out_trade_no}, {response}")
                return False, error_msg, None
        else:
            # 对象格式
            if hasattr(response, "code") and response.code == "10000":
                qr_code = response.qr_code
                log.info(f"创建支付宝订单成功: {out_trade_no}")
                return True, "success", qr_code
            else:
                error_msg = getattr(response, "sub_msg", None) or getattr(response, "msg", "未知错误")
                log.error(f"创建支付宝订单失败: {out_trade_no}, {error_msg}")
                return False, error_msg, None

    except Exception as e:
        import traceback
        log.error(f"创建支付宝订单异常: {e}")
        log.error(f"详细堆栈: {traceback.format_exc()}")
        return False, str(e), None


def create_wap_payment(
    out_trade_no: str,
    amount_yuan: float,
    subject: str = "账户充值",
    return_url: str = None,
) -> Tuple[bool, str, Optional[str]]:
    """
    创建手机网站支付订单 (H5)

    移动端用户跳转到支付宝收银台完成支付

    Args:
        out_trade_no: 商户订单号
        amount_yuan: 金额（元）
        subject: 订单标题
        return_url: 同步返回地址（可选，默认使用环境变量配置）

    Returns:
        Tuple[success, message, pay_url]
        pay_url: 支付宝收银台跳转URL
    """
    try:
        from alipay.aop.api.domain.AlipayTradeWapPayModel import AlipayTradeWapPayModel
        from alipay.aop.api.request.AlipayTradeWapPayRequest import (
            AlipayTradeWapPayRequest,
        )

        client = get_alipay_client()

        model = AlipayTradeWapPayModel()
        model.out_trade_no = out_trade_no
        model.total_amount = f"{amount_yuan:.2f}"
        model.subject = subject
        model.product_code = "QUICK_WAP_WAY"
        model.timeout_express = "15m"  # 15分钟过期

        request = AlipayTradeWapPayRequest(biz_model=model)
        notify_url = get_notify_url()
        if notify_url:
            request.notify_url = notify_url
        final_return_url = return_url or get_return_url()
        if final_return_url:
            request.return_url = final_return_url

        print(f"[Alipay] 创建H5支付订单: {out_trade_no}")
        print(f"[Alipay] notify_url = {notify_url or '(空)'}")
        print(f"[Alipay] return_url = {final_return_url or '(空)'}")

        # page_execute 返回跳转 URL
        pay_url = client.page_execute(request, http_method="GET")

        # 检查生成的URL中是否包含 return_url
        if "return_url" in pay_url:
            print(f"[Alipay] 创建成功，pay_url 包含 return_url 参数")
        else:
            print(f"[Alipay] 警告: pay_url 不包含 return_url! 支付完成后将无法显示返回商家按钮")
        print(f"[Alipay] pay_url 前200字符: {pay_url[:200]}...")
        return True, "success", pay_url

    except Exception as e:
        import traceback
        log.error(f"创建H5支付订单异常: {e}")
        log.error(f"详细堆栈: {traceback.format_exc()}")
        return False, str(e), None


def create_page_payment(
    out_trade_no: str,
    amount_yuan: float,
    subject: str = "账户充值",
    return_url: str = None,
) -> Tuple[bool, str, Optional[str]]:
    """
    创建电脑网站支付订单 (PC)

    桌面端用户跳转到支付宝收银台完成支付

    Args:
        out_trade_no: 商户订单号
        amount_yuan: 金额（元）
        subject: 订单标题
        return_url: 同步返回地址（可选，默认使用环境变量配置）

    Returns:
        Tuple[success, message, pay_url]
        pay_url: 支付宝收银台跳转URL
    """
    try:
        from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel
        from alipay.aop.api.request.AlipayTradePagePayRequest import (
            AlipayTradePagePayRequest,
        )

        client = get_alipay_client()

        model = AlipayTradePagePayModel()
        model.out_trade_no = out_trade_no
        model.total_amount = f"{amount_yuan:.2f}"
        model.subject = subject
        model.product_code = "FAST_INSTANT_TRADE_PAY"
        model.timeout_express = "15m"  # 15分钟过期

        request = AlipayTradePagePayRequest(biz_model=model)
        notify_url = get_notify_url()
        if notify_url:
            request.notify_url = notify_url
        final_return_url = return_url or get_return_url()
        if final_return_url:
            request.return_url = final_return_url

        print(f"[Alipay] 创建PC支付订单: {out_trade_no}")
        print(f"[Alipay] notify_url = {notify_url or '(空)'}")
        print(f"[Alipay] return_url = {final_return_url or '(空)'}")

        # page_execute 返回跳转 URL
        pay_url = client.page_execute(request, http_method="GET")

        # 检查生成的URL中是否包含 return_url
        if "return_url" in pay_url:
            print(f"[Alipay] 创建成功，pay_url 包含 return_url 参数")
        else:
            print(f"[Alipay] 警告: pay_url 不包含 return_url! 支付完成后将无法显示返回商家按钮")
        print(f"[Alipay] pay_url 前200字符: {pay_url[:200]}...")
        return True, "success", pay_url

    except Exception as e:
        import traceback
        log.error(f"创建PC支付订单异常: {e}")
        log.error(f"详细堆栈: {traceback.format_exc()}")
        return False, str(e), None


def query_payment(out_trade_no: str) -> Tuple[str, Optional[str]]:
    """
    查询订单状态

    Args:
        out_trade_no: 商户订单号

    Returns:
        Tuple[status, trade_no]
        status: WAIT_BUYER_PAY / TRADE_CLOSED / TRADE_SUCCESS / TRADE_FINISHED / NOT_FOUND / ERROR
    """
    try:
        from alipay.aop.api.domain.AlipayTradeQueryModel import AlipayTradeQueryModel
        from alipay.aop.api.request.AlipayTradeQueryRequest import (
            AlipayTradeQueryRequest,
        )

        client = get_alipay_client()

        model = AlipayTradeQueryModel()
        model.out_trade_no = out_trade_no

        request = AlipayTradeQueryRequest(biz_model=model)
        response = client.execute(request)

        # 解析响应（可能是字符串或对象）
        if isinstance(response, str):
            import json
            response = json.loads(response)

        if isinstance(response, dict):
            if response.get("code") == "10000":
                return response.get("trade_status"), response.get("trade_no")
            else:
                return "NOT_FOUND", None
        else:
            if hasattr(response, "code") and response.code == "10000":
                return response.trade_status, response.trade_no
            else:
                return "NOT_FOUND", None

    except Exception as e:
        log.error(f"查询支付宝订单失败: {e}")
        return "ERROR", None


def close_payment(out_trade_no: str) -> bool:
    """
    关闭订单

    Args:
        out_trade_no: 商户订单号

    Returns:
        是否成功
    """
    try:
        from alipay.aop.api.domain.AlipayTradeCloseModel import AlipayTradeCloseModel
        from alipay.aop.api.request.AlipayTradeCloseRequest import (
            AlipayTradeCloseRequest,
        )

        client = get_alipay_client()

        model = AlipayTradeCloseModel()
        model.out_trade_no = out_trade_no

        request = AlipayTradeCloseRequest(biz_model=model)
        response = client.execute(request)

        # 解析响应（可能是字符串或对象）
        if isinstance(response, str):
            import json
            response = json.loads(response)

        code = response.get("code") if isinstance(response, dict) else getattr(response, "code", None)
        if code == "10000":
            log.info(f"关闭支付宝订单成功: {out_trade_no}")
            return True
        else:
            log.error(f"关闭支付宝订单失败: {out_trade_no}")
            return False

    except Exception as e:
        log.error(f"关闭支付宝订单异常: {e}")
        return False


def verify_notify_sign(params: dict) -> bool:
    """
    验证支付宝异步通知签名

    Args:
        params: 支付宝回调参数

    Returns:
        签名是否有效
    """
    if not is_alipay_configured():
        return False

    try:
        from alipay.aop.api.util.SignatureUtils import verify_with_rsa

        # 获取签名
        sign = params.get("sign", "")
        sign_type = params.get("sign_type", "RSA2")

        if not sign:
            log.error("回调参数缺少签名")
            return False

        # 构建待验签字符串（按字母排序，排除 sign 和 sign_type）
        sorted_params = sorted(
            [(k, v) for k, v in params.items() if k not in ("sign", "sign_type") and v]
        )
        unsigned_string = "&".join([f"{k}={v}" for k, v in sorted_params])

        # 验签
        if sign_type == "RSA2":
            result = verify_with_rsa(
                ALIPAY_PUBLIC_KEY, unsigned_string.encode("utf-8"), sign
            )
        else:
            # RSA (SHA1)
            from alipay.aop.api.util.SignatureUtils import verify_with_rsa as verify_rsa1

            result = verify_rsa1(
                ALIPAY_PUBLIC_KEY, unsigned_string.encode("utf-8"), sign
            )

        if result:
            log.info(f"支付宝回调验签成功: {params.get('out_trade_no')}")
        else:
            log.error(f"支付宝回调验签失败: {params.get('out_trade_no')}")

        return result

    except Exception as e:
        log.error(f"支付宝回调验签异常: {e}")
        return False
