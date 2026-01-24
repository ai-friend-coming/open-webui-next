"""
支付渠道抽象基类

定义支付渠道的统一接口
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional


class PaymentProvider(ABC):
    """支付渠道抽象基类"""

    @property
    @abstractmethod
    def method_name(self) -> str:
        """支付方式名称（如 alipay, wechat）"""
        pass

    @property
    @abstractmethod
    def payment_type(self) -> str:
        """支付类型（如 page, h5, qrcode）"""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """检查是否已配置"""
        pass

    @abstractmethod
    def create_payment(
        self,
        out_trade_no: str,
        amount_yuan: float,
        subject: str,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        创建支付

        Args:
            out_trade_no: 商户订单号
            amount_yuan: 金额（元）
            subject: 订单标题

        Returns:
            Tuple[success, message, pay_url]
        """
        pass

    @abstractmethod
    def verify_notify(self, params: dict) -> bool:
        """
        验证回调签名

        Args:
            params: 回调参数

        Returns:
            签名是否有效
        """
        pass

    def parse_notify_params(self, params: dict) -> dict:
        """
        解析回调参数（标准化）

        Args:
            params: 原始回调参数

        Returns:
            标准化参数: {
                "out_trade_no": str,
                "trade_no": str,
                "status": str,  # "success" | "fail" | "pending"
            }
        """
        raise NotImplementedError
