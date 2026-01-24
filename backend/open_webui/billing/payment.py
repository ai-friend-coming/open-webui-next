"""
支付服务核心

提供统一的订单创建、支付回调处理接口
"""

import time
import uuid
import logging
from typing import Optional
from dataclasses import dataclass

from open_webui.models.billing import PaymentOrders, RechargeLog
from open_webui.internal.db import get_db
from open_webui.billing.providers import PaymentMethod, get_provider

log = logging.getLogger(__name__)


@dataclass
class CreateOrderResult:
    """订单创建结果"""

    success: bool
    order_id: Optional[str] = None
    out_trade_no: Optional[str] = None
    pay_url: Optional[str] = None
    amount_yuan: float = 0
    expired_at: int = 0
    error: Optional[str] = None


@dataclass
class PaymentSuccessResult:
    """支付成功处理结果"""

    success: bool
    user_id: str
    amount: int  # 充值金额（毫）
    bonus_amount: int = 0  # 首充奖励（毫）
    is_first_recharge: bool = False
    error: Optional[str] = None


def create_order(
    user_id: str,
    amount_yuan: float,
    payment_method: PaymentMethod,
    subject: str = "Cakumi账户充值",
) -> CreateOrderResult:
    """
    统一订单创建入口

    Args:
        user_id: 用户ID
        amount_yuan: 金额（元）
        payment_method: 支付方式
        subject: 订单标题

    Returns:
        CreateOrderResult: 创建结果
    """
    # 1. 金额验证
    if amount_yuan < 0.01:
        return CreateOrderResult(success=False, error="充值金额最低0.01元")
    if amount_yuan > 10000:
        return CreateOrderResult(success=False, error="充值金额最高10000元")

    # 2. 生成订单号
    out_trade_no = f"CK{int(time.time())}{uuid.uuid4().hex[:8].upper()}"

    # 3. 获取支付渠道提供者
    try:
        provider = get_provider(payment_method)
    except ValueError as e:
        return CreateOrderResult(success=False, error=str(e))

    if not provider.is_configured():
        return CreateOrderResult(success=False, error="支付功能暂未开放，请联系管理员")

    # 4. 调用支付渠道创建订单
    success, msg, pay_url = provider.create_payment(
        out_trade_no=out_trade_no,
        amount_yuan=amount_yuan,
        subject=subject,
    )

    if not success:
        log.error(f"创建支付订单失败: {msg}")
        return CreateOrderResult(success=False, error=f"创建订单失败: {msg}")

    # 5. 保存订单到数据库
    now = int(time.time())
    expired_at = now + 900  # 15分钟过期

    order = PaymentOrders.create(
        user_id=user_id,
        out_trade_no=out_trade_no,
        amount=int(amount_yuan * 10000),  # 元 → 毫
        qr_code=pay_url,
        expired_at=expired_at,
        payment_method=provider.method_name,
        payment_type=provider.payment_type,
    )

    log.info(
        f"创建支付订单成功: {out_trade_no}, 用户={user_id}, "
        f"金额={amount_yuan}元, 方式={payment_method.value}"
    )

    # 6. 埋点
    _track_order_created(
        user_id=user_id,
        order_id=order.id,
        out_trade_no=out_trade_no,
        amount_yuan=amount_yuan,
        payment_type=payment_method.value,
    )

    return CreateOrderResult(
        success=True,
        order_id=order.id,
        out_trade_no=out_trade_no,
        pay_url=pay_url,
        amount_yuan=amount_yuan,
        expired_at=expired_at,
    )


def process_payment_success(
    order,
    trade_no: str,
    payment_method: str,
) -> PaymentSuccessResult:
    """
    支付成功后的统一处理逻辑

    包含：更新订单状态、增加余额、首充优惠、邀请返现、埋点

    Args:
        order: PaymentOrder 对象
        trade_no: 支付平台交易号
        payment_method: 支付方式（alipay/wechat）

    Returns:
        PaymentSuccessResult: 处理结果
    """
    from open_webui.models.users import User as UserModel
    from open_webui.billing.first_recharge import (
        process_first_recharge_bonus,
        record_first_recharge_billing_log,
    )

    now = int(time.time())

    # 1. 更新订单状态
    PaymentOrders.update_status(
        out_trade_no=order.out_trade_no,
        status="paid",
        trade_no=trade_no,
        paid_at=now,
    )

    try:
        with get_db() as db:
            user = (
                db.query(UserModel)
                .filter_by(id=order.user_id)
                .with_for_update()
                .first()
            )
            if not user:
                return PaymentSuccessResult(
                    success=False,
                    user_id=order.user_id,
                    amount=order.amount,
                    error="用户不存在",
                )

            # 2. 计算首充奖励
            bonus_amount, is_first_recharge = process_first_recharge_bonus(
                user_id=order.user_id,
                recharge_amount=order.amount,
                db=db,
            )

            # 3. 更新用户余额（充值金额 + 奖励金额）
            total_amount = order.amount + bonus_amount
            user.balance = (user.balance or 0) + total_amount
            db.commit()

            # 4. 记录充值日志
            recharge_log = _create_recharge_log(
                user_id=order.user_id,
                amount=order.amount,
                out_trade_no=order.out_trade_no,
                payment_method=payment_method,
                db=db,
            )

            # 5. 处理邀请返现
            try:
                from open_webui.billing.invite import process_invite_rebate

                process_invite_rebate(
                    invitee_id=order.user_id,
                    recharge_amount=order.amount,
                    recharge_log_id=recharge_log.id,
                )
            except Exception as e:
                log.error(f"邀请返现处理失败: {e}")
                # 不影响充值流程，继续执行

            # 6. 如果是首充，记录计费日志
            if is_first_recharge and bonus_amount > 0:
                try:
                    record_first_recharge_billing_log(
                        user_id=order.user_id,
                        bonus_amount=bonus_amount,
                        balance_after=user.balance,
                        db=db,
                    )
                    log.info(
                        f"首充优惠发放成功: 用户={order.user_id}, "
                        f"充值={order.amount / 10000:.2f}元, "
                        f"奖励={bonus_amount / 10000:.2f}元"
                    )
                except Exception as e:
                    log.error(f"首充优惠记录失败: {e}")

            # 7. 埋点
            _track_payment_success(
                user_id=order.user_id,
                order_id=order.id,
                out_trade_no=order.out_trade_no,
                trade_no=trade_no,
                amount=order.amount,
                is_first_recharge=is_first_recharge,
                bonus_amount=bonus_amount,
            )

            log.info(
                f"支付成功: 用户={order.user_id}, 金额={order.amount / 10000:.2f}元, "
                f"订单={order.out_trade_no}, 支付方式={payment_method}"
                + (f", 首充奖励={bonus_amount / 10000:.2f}元" if is_first_recharge else "")
            )

            return PaymentSuccessResult(
                success=True,
                user_id=order.user_id,
                amount=order.amount,
                bonus_amount=bonus_amount,
                is_first_recharge=is_first_recharge,
            )

    except Exception as e:
        log.error(f"支付成功处理失败: {e}")
        import traceback
        log.error(f"详细堆栈: {traceback.format_exc()}")
        return PaymentSuccessResult(
            success=False,
            user_id=order.user_id,
            amount=order.amount,
            error=str(e),
        )


def _create_recharge_log(
    user_id: str,
    amount: int,
    out_trade_no: str,
    payment_method: str,
    db,
) -> RechargeLog:
    """创建充值日志"""
    method_names = {"alipay": "支付宝", "wechat": "微信"}
    method_name = method_names.get(payment_method, payment_method)

    recharge_log = RechargeLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        amount=amount,
        operator_id="system",
        remark=f"{method_name}充值，订单号: {out_trade_no}",
        created_at=int(time.time()),
    )
    db.add(recharge_log)
    db.commit()
    return recharge_log


def _track_order_created(
    user_id: str,
    order_id: str,
    out_trade_no: str,
    amount_yuan: float,
    payment_type: str,
) -> None:
    """埋点：订单创建"""
    try:
        from open_webui.utils.posthog import track_payment_order_created, flush

        track_payment_order_created(
            user_id=user_id,
            order_id=order_id,
            out_trade_no=out_trade_no,
            amount_yuan=amount_yuan,
            payment_type=payment_type,
        )
        flush()
    except Exception as e:
        log.warning(f"埋点失败: {e}")


def _track_payment_success(
    user_id: str,
    order_id: str,
    out_trade_no: str,
    trade_no: str,
    amount: int,
    is_first_recharge: bool,
    bonus_amount: int,
) -> None:
    """埋点：支付成功"""
    try:
        from open_webui.utils.posthog import track_payment_success, flush

        track_payment_success(
            user_id=user_id,
            order_id=order_id,
            out_trade_no=out_trade_no,
            trade_no=trade_no,
            amount_yuan=amount / 10000,
            is_first_recharge=is_first_recharge,
            bonus_amount_yuan=bonus_amount / 10000 if bonus_amount else 0,
        )
        flush()
    except Exception as e:
        log.warning(f"埋点失败: {e}")
