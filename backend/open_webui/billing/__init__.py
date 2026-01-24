"""
计费模块

提供统一的计费接口：
- BillingContext: 计费上下文管理（支持信任额度模式）
- BillingStreamWrapper: 流式响应计费包装
- chat_with_billing: 聊天计费代理
- UsageInfo: 标准化的 usage 数据结构

支付服务：
- create_order: 统一订单创建
- process_payment_success: 统一支付成功处理
- PaymentMethod: 支付方式枚举

首充优惠：
- process_first_recharge_bonus: 处理首充优惠

计费机制：
1. 预扣费模式：precharge → settle（普通用户）
2. 信任额度模式：直接后付费（高余额用户）
3. 支持缓存 token（10% 价格）和推理 token
"""

from open_webui.billing.context import BillingContext
from open_webui.billing.stream import BillingStreamWrapper, wrap_stream_with_billing
from open_webui.billing.proxy import chat_with_billing
from open_webui.billing.usage import (
    UsageInfo,
    parse_usage,
    parse_usage_from_sse_chunk,
    extract_delta_content,
)
from open_webui.billing.core import (
    # 费用计算
    calculate_cost,
    calculate_cost_with_usage,
    get_model_pricing,
    CACHE_TOKEN_RATIO,
    # Token 估算
    estimate_prompt_tokens,
    estimate_completion_tokens,
    estimate_image_tokens,
    estimate_video_tokens,
    estimate_file_tokens,
    # 余额操作
    deduct_balance,
    deduct_balance_with_usage,
    precharge_balance,
    settle_precharge,
    settle_precharge_with_usage,
    recharge_user,
    get_user_balance,
    check_user_balance_threshold,
    # 信任额度
    check_trust_quota,
    TRUST_QUOTA_THRESHOLD,
)

# 支付服务
from open_webui.billing.payment import (
    create_order,
    process_payment_success,
    CreateOrderResult,
    PaymentSuccessResult,
)
from open_webui.billing.providers import PaymentMethod, get_provider

# 首充优惠
from open_webui.billing.first_recharge import (
    process_first_recharge_bonus,
    get_available_tiers,
    is_first_recharge_enabled,
    get_first_recharge_config,
)

__all__ = [
    # 上下文和包装器
    "BillingContext",
    "BillingStreamWrapper",
    "wrap_stream_with_billing",
    "chat_with_billing",
    # Usage 数据结构
    "UsageInfo",
    "parse_usage",
    "parse_usage_from_sse_chunk",
    "extract_delta_content",
    # 费用计算
    "calculate_cost",
    "calculate_cost_with_usage",
    "get_model_pricing",
    "CACHE_TOKEN_RATIO",
    # Token 估算
    "estimate_prompt_tokens",
    "estimate_completion_tokens",
    "estimate_image_tokens",
    "estimate_video_tokens",
    "estimate_file_tokens",
    # 余额操作
    "deduct_balance",
    "deduct_balance_with_usage",
    "precharge_balance",
    "settle_precharge",
    "settle_precharge_with_usage",
    "recharge_user",
    "get_user_balance",
    "check_user_balance_threshold",
    # 信任额度
    "check_trust_quota",
    "TRUST_QUOTA_THRESHOLD",
    # 支付服务
    "create_order",
    "process_payment_success",
    "CreateOrderResult",
    "PaymentSuccessResult",
    "PaymentMethod",
    "get_provider",
    # 首充优惠
    "process_first_recharge_bonus",
    "get_available_tiers",
    "is_first_recharge_enabled",
    "get_first_recharge_config",
]
