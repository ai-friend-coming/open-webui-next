"""
虎皮椒支付渠道适配器（微信支付）
"""

from typing import Tuple, Optional

from open_webui.billing.providers.base import PaymentProvider
from open_webui.utils.hupijiao import (
    is_hupijiao_configured,
    create_wechat_payment,
    verify_notify_sign,
)


class HupijiaoWechatProvider(PaymentProvider):
    """虎皮椒微信H5支付"""

    @property
    def method_name(self) -> str:
        return "wechat"

    @property
    def payment_type(self) -> str:
        return "h5"

    def is_configured(self) -> bool:
        return is_hupijiao_configured()

    def create_payment(
        self,
        out_trade_no: str,
        amount_yuan: float,
        subject: str,
    ) -> Tuple[bool, str, Optional[str]]:
        return create_wechat_payment(out_trade_no, amount_yuan, subject)

    def verify_notify(self, params: dict) -> bool:
        return verify_notify_sign(params)

    def parse_notify_params(self, params: dict) -> dict:
        """
        解析虎皮椒回调参数

        虎皮椒状态码：
        - OD: 已支付
        - WP: 等待支付
        """
        status = params.get("status", "")
        status_map = {
            "OD": "success",
            "WP": "pending",
        }

        # 解析金额，虎皮椒返回的 total_fee 是字符串格式的元
        total_fee_str = params.get("total_fee", "0")
        try:
            total_fee_yuan = float(total_fee_str)
        except (ValueError, TypeError):
            total_fee_yuan = 0

        return {
            "out_trade_no": params.get("trade_order_id"),
            "trade_no": params.get("transaction_id", ""),
            "status": status_map.get(status, "pending"),
            "appid": params.get("appid", ""),
            "total_fee_yuan": total_fee_yuan,  # 回调金额（元）
        }
