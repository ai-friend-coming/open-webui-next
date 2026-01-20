"""
PostHog 埋点工具模块

用于后端事件追踪，主要用于支付相关埋点。
"""

import logging
from typing import Optional
from datetime import datetime, timezone

import posthog

log = logging.getLogger(__name__)

# PostHog 配置（与前端保持一致）
POSTHOG_API_KEY = "phc_Abmjxrycc5WX5tnegaHmQx5COrSTFmM72VmyDVv4xCa"
POSTHOG_HOST = "https://us.i.posthog.com"

# 初始化标志
_initialized = False


def init_posthog():
    """初始化 PostHog SDK"""
    global _initialized
    if _initialized:
        return

    # PostHog 7.x 使用 api_key 而非 project_api_key
    posthog.api_key = POSTHOG_API_KEY
    posthog.host = POSTHOG_HOST
    # 禁用自动捕获个人信息
    posthog.disabled = False
    _initialized = True
    log.info("PostHog SDK 初始化完成")


def _ensure_initialized():
    """确保 PostHog 已初始化"""
    if not _initialized:
        init_posthog()


# =====================================================
# ==================== 支付订单埋点 ====================
# =====================================================


def track_payment_order_created(
    user_id: str,
    order_id: str,
    out_trade_no: str,
    amount_yuan: float,
    payment_type: str,  # 'page' | 'h5'
):
    """
    埋点：payment_order_created

    【埋点时机】用户创建充值订单时（调用支付宝 API 成功后）
    【业务环节】充值流程的起点，用户发起支付意图
    【埋点数据】
      - order_id: string - 内部订单 ID
      - out_trade_no: string - 商户订单号
      - amount: number - 充值金额（元）
      - payment_type: string - 支付类型 (page=PC网页, h5=移动端)
      - created_at: string - 创建时间 (ISO 8601)
    """
    _ensure_initialized()

    try:
        posthog.capture(
            distinct_id=user_id,
            event="payment_order_created",
            properties={
                "order_id": order_id,
                "out_trade_no": out_trade_no,
                "amount": amount_yuan,
                "payment_type": payment_type,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        log.debug(f"埋点 payment_order_created: user={user_id}, order={out_trade_no}, amount={amount_yuan}")
    except Exception as e:
        log.error(f"埋点失败 payment_order_created: {e}")


def track_payment_success(
    user_id: str,
    order_id: str,
    out_trade_no: str,
    trade_no: str,
    amount_yuan: float,
    is_first_recharge: bool = False,
    bonus_amount_yuan: float = 0,
):
    """
    埋点：payment_success

    【埋点时机】支付宝异步通知回调，确认支付成功时
    【业务环节】充值流程的成功终点，用户完成付款且金额已到账
    【埋点数据】
      - order_id: string - 内部订单 ID
      - out_trade_no: string - 商户订单号
      - trade_no: string - 支付宝交易号
      - amount: number - 充值金额（元）
      - is_first_recharge: boolean - 是否首充
      - bonus_amount: number - 首充奖励金额（元）
      - paid_at: string - 支付成功时间 (ISO 8601)
    """
    _ensure_initialized()

    try:
        posthog.capture(
            distinct_id=user_id,
            event="payment_success",
            properties={
                "order_id": order_id,
                "out_trade_no": out_trade_no,
                "trade_no": trade_no,
                "amount": amount_yuan,
                "is_first_recharge": is_first_recharge,
                "bonus_amount": bonus_amount_yuan,
                "paid_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        log.debug(
            f"埋点 payment_success: user={user_id}, order={out_trade_no}, "
            f"amount={amount_yuan}, first={is_first_recharge}"
        )
    except Exception as e:
        log.error(f"埋点失败 payment_success: {e}")


def flush():
    """刷新事件队列，确保所有事件发送完成"""
    _ensure_initialized()
    try:
        posthog.flush()
    except Exception as e:
        log.error(f"PostHog flush 失败: {e}")
