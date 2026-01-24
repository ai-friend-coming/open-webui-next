"""
支付渠道提供者工厂
"""

from enum import Enum
from typing import Union

from open_webui.billing.providers.base import PaymentProvider
from open_webui.billing.providers.alipay import AlipayPageProvider, AlipayH5Provider
from open_webui.billing.providers.hupijiao import HupijiaoWechatProvider


class PaymentMethod(str, Enum):
    """支付方式枚举"""

    ALIPAY_PAGE = "alipay_page"  # 支付宝PC网页
    ALIPAY_H5 = "alipay_h5"  # 支付宝H5
    WECHAT_H5 = "wechat_h5"  # 微信H5(虎皮椒)


def get_provider(method: Union[PaymentMethod, str]) -> PaymentProvider:
    """
    获取支付渠道提供者

    Args:
        method: 支付方式

    Returns:
        PaymentProvider: 支付渠道实例

    Raises:
        ValueError: 不支持的支付方式
    """
    # 支持字符串和枚举两种传入方式
    if isinstance(method, str):
        try:
            method = PaymentMethod(method)
        except ValueError:
            raise ValueError(f"不支持的支付方式: {method}")

    providers = {
        PaymentMethod.ALIPAY_PAGE: AlipayPageProvider,
        PaymentMethod.ALIPAY_H5: AlipayH5Provider,
        PaymentMethod.WECHAT_H5: HupijiaoWechatProvider,
    }

    provider_class = providers.get(method)
    if not provider_class:
        raise ValueError(f"不支持的支付方式: {method}")

    return provider_class()


__all__ = [
    "PaymentMethod",
    "PaymentProvider",
    "get_provider",
    "AlipayPageProvider",
    "AlipayH5Provider",
    "HupijiaoWechatProvider",
]
