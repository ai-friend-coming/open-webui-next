"""
计费模块

提供统一的计费接口：
- BillingContext: 计费上下文管理
- BillingStreamWrapper: 流式响应计费包装
- chat_with_billing: 聊天计费代理
- charge_direct: 直接扣费（传入金额和log_type，无需token计算）
"""

from open_webui.billing.context import BillingContext
from open_webui.billing.stream import BillingStreamWrapper
from open_webui.billing.proxy import chat_with_billing
from open_webui.billing.core import (
    calculate_cost,
    deduct_balance,
    precharge_balance,
    settle_precharge,
    recharge_user,
    get_user_balance,
    estimate_prompt_tokens,
    check_user_balance_threshold,
    charge_direct,
)

__all__ = [
    "BillingContext",
    "BillingStreamWrapper",
    "chat_with_billing",
    "calculate_cost",
    "deduct_balance",
    "precharge_balance",
    "settle_precharge",
    "recharge_user",
    "get_user_balance",
    "estimate_prompt_tokens",
    "check_user_balance_threshold",
    "charge_direct",
]
