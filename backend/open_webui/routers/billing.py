"""
计费管理 API 路由

提供余额查询、充值、消费记录、统计报表、模型定价等管理接口
"""
# test build 4

import time
import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from open_webui.models.users import Users, User
from open_webui.models.billing import ModelPricings, BillingLogs, RechargeLogs, BillingLog
from open_webui.billing.core import RECHARGE_TIERS
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.billing import recharge_user
from open_webui.internal.db import get_db, SQLALCHEMY_DATABASE_URL

log = logging.getLogger(__name__)

router = APIRouter()


####################
# Request/Response Models
####################


class BalanceResponse(BaseModel):
    """余额响应"""

    balance: float = Field(..., description="当前余额（元）")
    total_consumed: float = Field(..., description="累计消费（元）")
    billing_status: str = Field(..., description="账户状态: active/frozen")


class RechargeRequest(BaseModel):
    """充值请求"""

    user_id: str = Field(..., description="用户ID")
    amount: int = Field(..., ne=0, description="充值/扣费金额（毫），1元 = 10000毫，正数充值，负数扣费")
    remark: str = Field(default="", description="备注")


class RechargeResponse(BaseModel):
    """充值响应"""

    balance: float = Field(..., description="充值后余额（毫），1元 = 10000毫")
    status: str = Field(..., description="账户状态")


class BillingLogResponse(BaseModel):
    """计费日志响应"""

    id: str
    user_id: Optional[str] = None
    model_id: str
    cost: float
    balance_after: Optional[float]
    type: str
    prompt_tokens: int
    completion_tokens: int
    created_at: int
    precharge_id: Optional[str] = None  # 预扣费事务ID，用于关联 precharge 和 settle
    status: Optional[str] = None
    estimated_tokens: Optional[int] = None
    refund_amount: Optional[float] = None


class PricingRequest(BaseModel):
    """定价请求"""

    model_id: str = Field(..., description="模型标识")
    input_price: Decimal = Field(..., ge=0, description="输入价格（元/百万token）")
    output_price: Decimal = Field(..., ge=0, description="输出价格（元/百万token）")


class PricingResponse(BaseModel):
    """定价响应"""

    model_id: str
    input_price: float
    output_price: float
    source: str = Field(..., description="来源: database/default")


class DailyStats(BaseModel):
    """每日统计"""

    date: str
    cost: float
    by_model: dict[str, float] = {}  # 按模型分组的消费


class ModelStats(BaseModel):
    """模型统计"""

    model: str
    cost: float
    count: int


class StatsResponse(BaseModel):
    """统计报表响应"""

    daily: list[DailyStats]
    by_model: list[ModelStats]
    models: list[str] = []  # 所有模型列表（用于前端生成堆叠图系列）


####################
# API Endpoints
####################


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(user=Depends(get_verified_user)):
    """
    查询当前用户余额

    需要登录
    """
    user_data = Users.get_user_by_id(user.id)
    if not user_data:
        raise HTTPException(status_code=404, detail="用户不存在")

    return BalanceResponse(
        balance=float(user_data.balance or 0),
        total_consumed=float(user_data.total_consumed or 0),
        billing_status=user_data.billing_status or "active",
    )


@router.post("/recharge", response_model=RechargeResponse)
async def recharge(req: RechargeRequest, admin=Depends(get_admin_user)):
    """
    管理员充值

    需要管理员权限
    """
    try:
        balance = recharge_user(
            user_id=req.user_id,
            amount=req.amount,
            operator_id=admin.id,
            remark=req.remark,
        )

        # 获取用户状态
        user_data = Users.get_user_by_id(req.user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="用户不存在")

        return RechargeResponse(
            balance=float(balance), status=user_data.billing_status or "active"
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"充值失败: {e}")
        raise HTTPException(status_code=500, detail=f"充值失败: {str(e)}")


@router.get("/logs", response_model=list[BillingLogResponse])
async def get_logs(
    user=Depends(get_verified_user), limit: int = 50, offset: int = 0
):
    """
    查询当前用户消费记录

    需要登录
    """
    try:
        logs = BillingLogs.get_by_user_id(user.id, limit=limit, offset=offset)

        return [
            BillingLogResponse(
                id=log.id,
                user_id=log.user_id,
                model_id=log.model_id,
                cost=float(log.total_cost),
                balance_after=float(log.balance_after)
                if log.balance_after is not None
                else None,
                type=log.log_type,
                prompt_tokens=log.prompt_tokens,
                completion_tokens=log.completion_tokens,
                created_at=log.created_at,
                precharge_id=log.precharge_id,  # 添加预扣费事务ID
                status=log.status,
                estimated_tokens=log.estimated_tokens,
                refund_amount=float(log.refund_amount)
                if log.refund_amount is not None
                else None,
            )
            for log in logs
        ]
    except Exception as e:
        log.error(f"查询日志失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询日志失败: {str(e)}")


@router.get("/logs/{user_id}", response_model=list[BillingLogResponse])
async def get_logs_by_user_id(
    user_id: str,
    admin=Depends(get_admin_user),
):
    """
    查询指定用户消费记录 (仅管理员)
    """
    try:
        logs = BillingLogs.get_all_by_user_id(user_id)

        return [
            BillingLogResponse(
                id=log.id,
                user_id=log.user_id,
                model_id=log.model_id,
                cost=float(log.total_cost),
                balance_after=float(log.balance_after)
                if log.balance_after is not None
                else None,
                type=log.log_type,
                prompt_tokens=log.prompt_tokens,
                completion_tokens=log.completion_tokens,
                created_at=log.created_at,
                precharge_id=log.precharge_id,
                status=log.status,
                estimated_tokens=log.estimated_tokens,
                refund_amount=float(log.refund_amount)
                if log.refund_amount is not None
                else None,
            )
            for log in logs
        ]
    except Exception as e:
        log.error(f"查询日志失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询日志失败: {str(e)}")


def _get_date_trunc_expr(trunc_unit: str, timestamp_col):
    """
    根据数据库类型返回日期截断表达式

    PostgreSQL: date_trunc('day', to_timestamp(ts))
    SQLite: strftime('%Y-%m-%d', datetime(ts, 'unixepoch'))
    """
    from sqlalchemy import func

    is_sqlite = "sqlite" in SQLALCHEMY_DATABASE_URL

    # 将纳秒时间戳转换为秒
    ts_seconds = timestamp_col / 1000000000

    if is_sqlite:
        # SQLite: 使用 strftime，返回字符串
        format_map = {
            "hour": "%Y-%m-%d %H:00:00",
            "day": "%Y-%m-%d",
            "month": "%Y-%m-01",
        }
        fmt = format_map.get(trunc_unit, "%Y-%m-%d")
        return func.strftime(fmt, func.datetime(ts_seconds, "unixepoch"))
    else:
        # PostgreSQL: 使用 date_trunc，返回 datetime
        return func.date_trunc(trunc_unit, func.to_timestamp(ts_seconds))


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    user=Depends(get_verified_user),
    days: int = 7,
    granularity: str = "day"
):
    """
    查询统计报表

    Args:
        days: 查询天数
        granularity: 时间粒度 (hour/day/month)

    需要登录
    """
    try:
        from sqlalchemy import func
        from datetime import datetime, timedelta
        from dateutil.relativedelta import relativedelta

        with get_db() as db:
            now = datetime.now()
            cutoff = int((time.time() - days * 86400) * 1000000000)

            # 根据粒度选择分组方式和生成完整时间序列（包含当前时段）
            if granularity == "hour":
                trunc_unit = "hour"
                date_format = "%H:00"
                # 生成过去24小时的完整序列（包含当前小时）
                all_periods = []
                for i in range(23, -1, -1):
                    dt = now - timedelta(hours=i)
                    all_periods.append(dt.replace(minute=0, second=0, microsecond=0))
            elif granularity == "month":
                trunc_unit = "month"
                date_format = "%Y-%m"
                # 生成过去12个月的完整序列（包含当前月）
                all_periods = []
                for i in range(11, -1, -1):
                    dt = now - relativedelta(months=i)
                    all_periods.append(dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
            else:
                # 默认按天分组
                trunc_unit = "day"
                date_format = "%m-%d"
                # 生成过去N天的完整序列（包含今天）
                all_periods = []
                for i in range(days - 1, -1, -1):
                    dt = now - timedelta(days=i)
                    all_periods.append(dt.replace(hour=0, minute=0, second=0, microsecond=0))

            # 按时间+模型分组统计（用于堆叠图）
            daily_by_model_query = (
                db.query(
                    _get_date_trunc_expr(trunc_unit, BillingLog.created_at).label("date"),
                    BillingLog.model_id,
                    func.sum(BillingLog.total_cost).label("total"),
                )
                .filter(
                    BillingLog.user_id == user.id,
                    BillingLog.created_at >= cutoff,
                    BillingLog.log_type.in_(["deduct", "settle","RAG"]),
                )
                .group_by("date", BillingLog.model_id)
                .order_by("date")
                .all()
            )

            # 构建数据结构: {date_key: {model_id: cost, ...}, ...}
            data_dict: dict[str, dict[str, float]] = {}
            all_models: set[str] = set()
            for d in daily_by_model_query:
                if d[0] and d[1]:
                    # 兼容 SQLite (返回字符串) 和 PostgreSQL (返回 datetime)
                    if isinstance(d[0], str):
                        # SQLite 返回字符串，需要解析后重新格式化
                        if ":" in d[0]:
                            parsed = datetime.strptime(d[0], "%Y-%m-%d %H:00:00")
                        elif d[0].endswith("-01") and len(d[0]) == 10:
                            parsed = datetime.strptime(d[0], "%Y-%m-%d")
                        else:
                            parsed = datetime.strptime(d[0], "%Y-%m-%d")
                        date_key = parsed.strftime(date_format)
                    else:
                        # PostgreSQL 返回 datetime
                        date_key = d[0].strftime(date_format)
                    model_id = d[1]
                    cost = d[2] / 10000 if d[2] else 0
                    all_models.add(model_id)
                    if date_key not in data_dict:
                        data_dict[date_key] = {}
                    data_dict[date_key][model_id] = cost

            log.debug(f"统计查询: granularity={granularity}, days={days}, 记录数={len(daily_by_model_query)}, 模型数={len(all_models)}")

            # 填充完整时间序列
            daily_stats = []
            for period in all_periods:
                key = period.strftime(date_format)
                by_model = data_dict.get(key, {})
                total_cost = sum(by_model.values())
                daily_stats.append(DailyStats(date=key, cost=total_cost, by_model=by_model))

            log.debug(f"生成时间序列: 数量={len(daily_stats)}, 模型列表={list(all_models)}")

            # 按模型统计
            by_model_query = (
                db.query(
                    BillingLog.model_id,
                    func.sum(BillingLog.total_cost).label("total"),
                    func.count().label("count"),
                )
                .filter(
                    BillingLog.user_id == user.id,
                    BillingLog.created_at >= cutoff,
                    BillingLog.log_type.in_(["deduct", "settle","RAG"]),
                )
                .group_by(BillingLog.model_id)
                .order_by(func.sum(BillingLog.total_cost).desc())
                .all()
            )

            return StatsResponse(
                daily=daily_stats,
                by_model=[
                    ModelStats(model=m[0], cost=m[1] / 10000 if m[1] else 0, count=m[2])
                    for m in by_model_query
                ],
                models=sorted(list(all_models)),  # 按字母排序的模型列表
            )
    except Exception as e:
        log.error(f"查询统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询统计失败: {str(e)}")


@router.post("/pricing", response_model=PricingResponse)
async def set_pricing(req: PricingRequest, admin=Depends(get_admin_user)):
    """
    设置模型定价

    需要管理员权限
    """
    try:
        pricing = ModelPricings.upsert(
            model_id=req.model_id,
            input_price=req.input_price,
            output_price=req.output_price,
        )

        return PricingResponse(
            model_id=pricing.model_id,
            input_price=float(pricing.input_price),
            output_price=float(pricing.output_price),
            source="database",
        )
    except Exception as e:
        log.error(f"设置定价失败: {e}")
        raise HTTPException(status_code=500, detail=f"设置定价失败: {str(e)}")


@router.get("/pricing/{model_id}", response_model=PricingResponse)
async def get_pricing(model_id: str):
    """
    查询模型定价

    公开接口，无需登录
    """
    try:
        pricing = ModelPricings.get_by_model_id(model_id)

        if pricing:
            return PricingResponse(
                model_id=pricing.model_id,
                input_price=float(pricing.input_price),
                output_price=float(pricing.output_price),
                source="database",
            )
        else:
            # 返回默认价格
            from open_webui.utils.billing import DEFAULT_PRICING

            default = DEFAULT_PRICING.get(model_id, DEFAULT_PRICING["default"])
            return PricingResponse(
                model_id=model_id,
                input_price=float(default["input"]),
                output_price=float(default["output"]),
                source="default",
            )
    except Exception as e:
        log.error(f"查询定价失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询定价失败: {str(e)}")


@router.get("/pricing", response_model=list[PricingResponse])
async def list_pricing():
    """
    列出所有模型定价

    公开接口，无需登录
    """
    try:
        pricings = ModelPricings.get_all()

        return [
            PricingResponse(
                model_id=p.model_id,
                input_price=float(p.input_price),
                output_price=float(p.output_price),
                source="database",
            )
            for p in pricings
        ]
    except Exception as e:
        log.error(f"列出定价失败: {e}")
        raise HTTPException(status_code=500, detail=f"列出定价失败: {str(e)}")


@router.get("/recharge/logs/{user_id}")
async def get_recharge_logs(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    admin=Depends(get_admin_user)
):
    """
    查询用户充值记录 (仅管理员)

    需要管理员权限
    """
    try:
        logs = RechargeLogs.get_by_user_id_with_operator_name(
            user_id, limit=limit, offset=offset
        )
        return logs
    except Exception as e:
        log.error(f"查询充值记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询充值记录失败: {str(e)}")


####################
# Payment API (用户自助充值)
####################


class CreateOrderRequest(BaseModel):
    """创建充值订单请求"""

    amount: float = Field(..., gt=0, le=10000, description="充值金额（元），1-10000")


class CreateOrderResponse(BaseModel):
    """创建充值订单响应（PC网页支付）"""

    order_id: str
    out_trade_no: str
    pay_url: str  # 支付宝收银台跳转URL
    amount: float
    expired_at: int


class CreateH5OrderResponse(BaseModel):
    """创建H5支付订单响应（移动端跳转）"""

    order_id: str
    out_trade_no: str
    pay_url: str
    amount: float
    expired_at: int


class OrderStatusResponse(BaseModel):
    """订单状态响应"""

    order_id: str
    status: str
    amount: float
    paid_at: Optional[int] = None
    is_first_recharge: bool = False  # 是否为首充订单
    bonus_amount: float = 0  # 首充奖励金额（元）
    bonus_rate: int = 0  # 首充返现比例（百分比）


class PaymentOrderResponse(BaseModel):
    """支付订单响应（用于列表展示）"""

    id: str
    out_trade_no: str  # 商户订单号
    trade_no: Optional[str] = None  # 支付宝交易号
    amount: float  # 金额（元）
    status: str  # pending/paid/closed/refunded
    payment_method: str
    paid_at: Optional[int] = None
    created_at: int
    is_first_recharge: bool = False  # 是否为首充订单
    bonus_amount: float = 0  # 首充奖励金额（元）


@router.get("/payment/orders", response_model=list[PaymentOrderResponse])
async def get_user_payment_orders(
    limit: int = 50,
    offset: int = 0,
    user=Depends(get_verified_user),
):
    """
    获取当前用户的支付订单列表

    需要登录
    """
    from open_webui.models.billing import PaymentOrders, FirstRechargeBonusLogs

    try:
        orders = PaymentOrders.get_by_user_id(user.id, limit=limit, offset=offset)

        # 查询用户的所有首充记录（列表）
        first_recharge_logs = FirstRechargeBonusLogs.get_by_user_id(user.id)

        result = []
        for o in orders:
            is_first_recharge = False
            bonus_amount = 0

            # 检查是否为首充订单（遍历所有首充记录）
            if first_recharge_logs and o.status == "paid" and o.paid_at:
                for log in first_recharge_logs:
                    # 通过充值金额和支付时间判断（允许10秒误差）
                    if (
                        abs(o.amount - log.recharge_amount) < 100  # 金额误差小于0.01元
                        and abs(o.paid_at - (log.created_at // 1000000000)) < 10
                    ):
                        is_first_recharge = True
                        bonus_amount = log.bonus_amount / 10000  # 毫 → 元
                        break

            result.append(
                PaymentOrderResponse(
                    id=o.id,
                    out_trade_no=o.out_trade_no,
                    trade_no=o.trade_no,
                    amount=o.amount / 10000,  # 毫 → 元
                    status=o.status,
                    payment_method=o.payment_method,
                    paid_at=o.paid_at,
                    created_at=o.created_at,
                    is_first_recharge=is_first_recharge,
                    bonus_amount=bonus_amount,
                )
            )

        return result
    except Exception as e:
        log.error(f"获取支付订单失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取支付订单失败: {str(e)}")


@router.post("/payment/create", response_model=CreateOrderResponse)
async def create_payment_order(req: CreateOrderRequest, user=Depends(get_verified_user)):
    """
    创建充值订单（PC端电脑网站支付，跳转支付宝收银台）

    需要登录
    """
    from open_webui.billing.payment import create_order
    from open_webui.billing.providers import PaymentMethod

    result = create_order(
        user_id=user.id,
        amount_yuan=req.amount,
        payment_method=PaymentMethod.ALIPAY_PAGE,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return CreateOrderResponse(
        order_id=result.order_id,
        out_trade_no=result.out_trade_no,
        pay_url=result.pay_url,
        amount=result.amount_yuan,
        expired_at=result.expired_at,
    )


@router.post("/payment/create/h5", response_model=CreateH5OrderResponse)
async def create_h5_payment_order(req: CreateOrderRequest, user=Depends(get_verified_user)):
    """
    创建H5支付订单（移动端跳转支付宝收银台）

    需要登录
    """
    from open_webui.billing.payment import create_order
    from open_webui.billing.providers import PaymentMethod

    result = create_order(
        user_id=user.id,
        amount_yuan=req.amount,
        payment_method=PaymentMethod.ALIPAY_H5,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return CreateH5OrderResponse(
        order_id=result.order_id,
        out_trade_no=result.out_trade_no,
        pay_url=result.pay_url,
        amount=result.amount_yuan,
        expired_at=result.expired_at,
    )


@router.get("/payment/status/{order_id}", response_model=OrderStatusResponse)
async def get_payment_status(order_id: str, user=Depends(get_verified_user)):
    """
    查询订单状态（前端轮询）

    需要登录
    """
    from open_webui.models.billing import PaymentOrders, FirstRechargeBonusLogs

    order = PaymentOrders.get_by_id(order_id)

    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    # 确保只能查询自己的订单
    if order.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权查询该订单")

    # 检查是否为首充订单
    is_first_recharge = False
    bonus_amount = 0
    bonus_rate = 0

    if order.status == "paid" and order.paid_at:
        first_recharge_logs = FirstRechargeBonusLogs.get_by_user_id(user.id)
        if first_recharge_logs:
            for log in first_recharge_logs:
                # 通过充值金额和支付时间判断（允许10秒误差）
                if (
                    abs(order.amount - log.recharge_amount) < 100
                    and abs(order.paid_at - (log.created_at // 1000000000)) < 10
                ):
                    is_first_recharge = True
                    bonus_amount = log.bonus_amount / 10000  # 毫 → 元
                    bonus_rate = log.bonus_rate
                    break

    return OrderStatusResponse(
        order_id=order.id,
        status=order.status,
        amount=order.amount / 10000,  # 毫 → 元
        paid_at=order.paid_at,
        is_first_recharge=is_first_recharge,
        bonus_amount=bonus_amount,
        bonus_rate=bonus_rate,
    )


@router.get("/payment/return")
async def payment_return(request: Request):
    """
    支付宝同步返回页面（支付完成后跳转）

    注意：此接口无需登录验证，会重定向到前端页面
    """
    from open_webui.env import ALIPAY_FRONTEND_URL
    from open_webui.models.billing import PaymentOrders

    # 获取回调参数
    params = dict(request.query_params)
    out_trade_no = params.get("out_trade_no", "")

    log.info(f"支付宝同步返回: {out_trade_no}")

    # 查询订单
    order = PaymentOrders.get_by_out_trade_no(out_trade_no)

    # 构建前端页面路径
    if order:
        page_path = f"/payment/return?order_id={order.id}&status={order.status}"
    else:
        page_path = "/payment/return?error=order_not_found"

    # 如果配置了前端地址，使用完整 URL；否则使用相对路径
    if ALIPAY_FRONTEND_URL:
        redirect_url = f"{ALIPAY_FRONTEND_URL}{page_path}"
    else:
        redirect_url = page_path

    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/payment/notify")
async def alipay_notify(request: Request):
    """
    支付宝异步通知回调

    注意：此接口无需登录验证
    """
    from open_webui.billing.providers import get_provider, PaymentMethod
    from open_webui.billing.payment import process_payment_success
    from open_webui.models.billing import PaymentOrders
    from open_webui.env import ALIPAY_APP_ID

    # 获取回调参数
    form_data = await request.form()
    params = dict(form_data)

    log.info(f"收到支付宝回调: {params.get('out_trade_no')}")

    # 获取提供者并验签
    provider = get_provider(PaymentMethod.ALIPAY_PAGE)
    if not provider.verify_notify(params):
        log.error("支付宝回调验签失败")
        return "fail"

    # 解析参数
    parsed = provider.parse_notify_params(params)

    # 安全验证1：验证 app_id 是否是本商户
    if parsed.get("app_id") != ALIPAY_APP_ID:
        log.error(
            f"支付宝回调，app_id 不匹配: 期望={ALIPAY_APP_ID}, "
            f"收到={parsed.get('app_id')}, 订单={parsed['out_trade_no']}"
        )
        return "fail"

    if parsed["status"] != "success":
        log.info(f"支付宝回调，非成功状态: {params.get('trade_status')}")
        return "success"

    # 查询订单
    order = PaymentOrders.get_by_out_trade_no(parsed["out_trade_no"])
    if not order:
        log.error(f"支付宝回调，订单不存在: {parsed['out_trade_no']}")
        return "success"

    # 安全验证2：验证回调金额与订单金额是否匹配
    # 订单金额是毫（1元=10000毫），回调金额是元
    order_amount_yuan = order.amount / 10000
    callback_amount_yuan = parsed.get("total_amount_yuan", 0)
    # 允许 0.01 元的误差（精度问题）
    if abs(order_amount_yuan - callback_amount_yuan) > 0.01:
        log.error(
            f"支付宝回调，金额不匹配: 订单金额={order_amount_yuan}元, "
            f"回调金额={callback_amount_yuan}元, 订单={parsed['out_trade_no']}"
        )
        return "fail"

    # 幂等检查：已处理的订单直接返回成功
    if order.status == "paid":
        log.info(f"支付宝回调，订单已处理: {parsed['out_trade_no']}")
        return "success"

    # 处理支付成功（余额、首充、返现、埋点）
    try:
        process_payment_success(order, parsed["trade_no"], "alipay")
    except Exception as e:
        log.error(f"支付回调处理失败: {e}")
        # 即使余额更新失败，也返回 success，避免支付宝重复回调

    return "success"


@router.get("/payment/config")
async def get_payment_config():
    """
    获取支付配置状态

    公开接口，用于前端判断是否显示充值功能
    """
    from open_webui.utils.alipay import is_alipay_configured
    from open_webui.utils.hupijiao import is_hupijiao_configured

    return {
        "alipay_enabled": is_alipay_configured(),
        "wechat_enabled": is_hupijiao_configured(),
    }


####################
# 微信支付 (虎皮椒)
####################


@router.post("/payment/create/wechat", response_model=CreateOrderResponse)
async def create_wechat_payment_order(req: CreateOrderRequest, user=Depends(get_verified_user)):
    """
    创建微信支付订单（通过虎皮椒，H5跳转支付）

    需要登录
    """
    from open_webui.billing.payment import create_order
    from open_webui.billing.providers import PaymentMethod

    result = create_order(
        user_id=user.id,
        amount_yuan=req.amount,
        payment_method=PaymentMethod.WECHAT_H5,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return CreateOrderResponse(
        order_id=result.order_id,
        out_trade_no=result.out_trade_no,
        pay_url=result.pay_url,
        amount=result.amount_yuan,
        expired_at=result.expired_at,
    )


@router.post("/payment/hupijiao/notify")
async def hupijiao_notify(request: Request):
    """
    虎皮椒异步通知回调（微信支付）

    注意：此接口无需登录验证
    """
    from open_webui.billing.providers import get_provider, PaymentMethod
    from open_webui.billing.payment import process_payment_success
    from open_webui.models.billing import PaymentOrders
    from open_webui.env import HUPIJIAO_APP_ID

    # 获取回调参数
    form_data = await request.form()
    params = dict(form_data)

    log.info(f"收到虎皮椒回调: {params.get('trade_order_id')}, params={params}")

    # 获取提供者并验签
    provider = get_provider(PaymentMethod.WECHAT_H5)
    if not provider.verify_notify(params):
        log.error("虎皮椒回调验签失败")
        return "fail"

    # 解析参数
    parsed = provider.parse_notify_params(params)

    # 安全验证1：验证 appid 是否是本商户
    if parsed.get("appid") != HUPIJIAO_APP_ID:
        log.error(
            f"虎皮椒回调，appid 不匹配: 期望={HUPIJIAO_APP_ID}, "
            f"收到={parsed.get('appid')}, 订单={parsed['out_trade_no']}"
        )
        return "fail"

    if parsed["status"] != "success":
        log.info(f"虎皮椒回调，非成功状态: {params.get('status')}")
        return "success"

    # 查询订单
    order = PaymentOrders.get_by_out_trade_no(parsed["out_trade_no"])
    if not order:
        log.error(f"虎皮椒回调，订单不存在: {parsed['out_trade_no']}")
        return "success"

    # 安全验证2：验证回调金额与订单金额是否匹配
    # 订单金额是毫（1元=10000毫），回调金额是元
    order_amount_yuan = order.amount / 10000
    callback_amount_yuan = parsed.get("total_fee_yuan", 0)
    # 允许 0.01 元的误差（精度问题）
    if abs(order_amount_yuan - callback_amount_yuan) > 0.01:
        log.error(
            f"虎皮椒回调，金额不匹配: 订单金额={order_amount_yuan}元, "
            f"回调金额={callback_amount_yuan}元, 订单={parsed['out_trade_no']}"
        )
        return "fail"

    # 幂等检查：已处理的订单直接返回成功
    if order.status == "paid":
        log.info(f"虎皮椒回调，订单已处理: {parsed['out_trade_no']}")
        return "success"

    # 处理支付成功（余额、首充、返现、埋点）
    try:
        process_payment_success(order, parsed["trade_no"], "wechat")
    except Exception as e:
        log.error(f"虎皮椒回调处理失败: {e}")
        # 即使余额更新失败，也返回 success，避免虎皮椒重复回调

    return "success"


@router.get("/payment/hupijiao/return")
async def hupijiao_return(request: Request):
    """
    虎皮椒同步返回页面（支付完成后跳转）

    注意：此接口无需登录验证，会重定向到前端页面
    """
    from open_webui.env import ALIPAY_FRONTEND_URL
    from open_webui.models.billing import PaymentOrders

    # 获取回调参数
    params = dict(request.query_params)
    trade_order_id = params.get("trade_order_id", "")

    log.info(f"虎皮椒同步返回: {trade_order_id}")

    # 查询订单
    order = PaymentOrders.get_by_out_trade_no(trade_order_id)

    # 构建前端页面路径
    if order:
        page_path = f"/payment/return?order_id={order.id}&status={order.status}"
    else:
        page_path = "/payment/return?error=order_not_found"

    # 如果配置了前端地址，使用完整 URL；否则使用相对路径
    if ALIPAY_FRONTEND_URL:
        redirect_url = f"{ALIPAY_FRONTEND_URL}{page_path}"
    else:
        redirect_url = page_path

    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/payment/hupijiao/callback")
async def hupijiao_callback(request: Request):
    """
    虎皮椒失败回调页面（支付失败时跳转）

    注意：此接口无需登录验证，会重定向到前端页面
    """
    from open_webui.env import ALIPAY_FRONTEND_URL

    # 获取回调参数
    params = dict(request.query_params)
    trade_order_id = params.get("trade_order_id", "")

    log.info(f"虎皮椒失败回调: {trade_order_id}")

    # 构建前端页面路径
    page_path = f"/payment/return?error=payment_failed&order_no={trade_order_id}"

    # 如果配置了前端地址，使用完整 URL；否则使用相对路径
    if ALIPAY_FRONTEND_URL:
        redirect_url = f"{ALIPAY_FRONTEND_URL}{page_path}"
    else:
        redirect_url = page_path

    return RedirectResponse(url=redirect_url, status_code=302)
