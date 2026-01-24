"""
支付宝支付渠道适配器
"""

from typing import Tuple, Optional

from open_webui.billing.providers.base import PaymentProvider
from open_webui.utils.alipay import (
    is_alipay_configured,
    create_page_payment,
    create_wap_payment,
    verify_notify_sign,
)


class AlipayPageProvider(PaymentProvider):
    """支付宝PC网页支付"""

    @property
    def method_name(self) -> str:
        return "alipay"

    @property
    def payment_type(self) -> str:
        return "page"

    def is_configured(self) -> bool:
        return is_alipay_configured()

    def create_payment(
        self,
        out_trade_no: str,
        amount_yuan: float,
        subject: str,
    ) -> Tuple[bool, str, Optional[str]]:
        return create_page_payment(out_trade_no, amount_yuan, subject)

    def verify_notify(self, params: dict) -> bool:
        return verify_notify_sign(params)

    def parse_notify_params(self, params: dict) -> dict:
        trade_status = params.get("trade_status", "")
        status_map = {
            "TRADE_SUCCESS": "success",
            "TRADE_FINISHED": "success",
            "WAIT_BUYER_PAY": "pending",
            "TRADE_CLOSED": "fail",
        }

        # 解析金额，支付宝返回的 total_amount 是字符串格式的元
        total_amount_str = params.get("total_amount", "0")
        try:
            total_amount_yuan = float(total_amount_str)
        except (ValueError, TypeError):
            total_amount_yuan = 0

        return {
            "out_trade_no": params.get("out_trade_no"),
            "trade_no": params.get("trade_no"),
            "status": status_map.get(trade_status, "pending"),
            "app_id": params.get("app_id", ""),
            "total_amount_yuan": total_amount_yuan,  # 回调金额（元）
        }


class AlipayH5Provider(PaymentProvider):
    """支付宝H5支付（移动端）"""

    @property
    def method_name(self) -> str:
        return "alipay"

    @property
    def payment_type(self) -> str:
        return "h5"

    def is_configured(self) -> bool:
        return is_alipay_configured()

    def create_payment(
        self,
        out_trade_no: str,
        amount_yuan: float,
        subject: str,
    ) -> Tuple[bool, str, Optional[str]]:
        return create_wap_payment(out_trade_no, amount_yuan, subject)

    def verify_notify(self, params: dict) -> bool:
        return verify_notify_sign(params)

    def parse_notify_params(self, params: dict) -> dict:
        # 与 AlipayPageProvider 相同
        trade_status = params.get("trade_status", "")
        status_map = {
            "TRADE_SUCCESS": "success",
            "TRADE_FINISHED": "success",
            "WAIT_BUYER_PAY": "pending",
            "TRADE_CLOSED": "fail",
        }

        # 解析金额，支付宝返回的 total_amount 是字符串格式的元
        total_amount_str = params.get("total_amount", "0")
        try:
            total_amount_yuan = float(total_amount_str)
        except (ValueError, TypeError):
            total_amount_yuan = 0

        return {
            "out_trade_no": params.get("out_trade_no"),
            "trade_no": params.get("trade_no"),
            "status": status_map.get(trade_status, "pending"),
            "app_id": params.get("app_id", ""),
            "total_amount_yuan": total_amount_yuan,  # 回调金额（元）
        }
