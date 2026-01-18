"""
计费管理 API 路由

提供余额查询、充值、消费记录、统计报表、模型定价等管理接口
"""

import time
import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from open_webui.models.users import Users, User
from open_webui.models.billing import ModelPricings, BillingLogs, RechargeLogs, BillingLog
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
    model_id: str
    cost: float
    balance_after: Optional[float]
    type: str
    prompt_tokens: int
    completion_tokens: int
    created_at: int
    precharge_id: Optional[str] = None  # 预扣费事务ID，用于关联 precharge 和 settle


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
                model_id=log.model_id,
                cost=float(log.total_cost),
                balance_after=float(log.balance_after) if log.balance_after else None,
                type=log.log_type,
                prompt_tokens=log.prompt_tokens,
                completion_tokens=log.completion_tokens,
                created_at=log.created_at,
                precharge_id=log.precharge_id,  # 添加预扣费事务ID
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

        # 查询用户的首充记录
        first_recharge_log = FirstRechargeBonusLogs.get_by_user_id(user.id)

        result = []
        for o in orders:
            is_first_recharge = False
            bonus_amount = 0

            # 检查是否为首充订单
            if first_recharge_log and o.status == "paid" and o.paid_at:
                # 通过充值金额和支付时间判断（允许10秒误差）
                if (
                    abs(o.amount - first_recharge_log.recharge_amount) < 100  # 金额误差小于0.01元
                    and abs(o.paid_at - (first_recharge_log.created_at // 1000000000)) < 10
                ):
                    is_first_recharge = True
                    bonus_amount = first_recharge_log.bonus_amount / 10000  # 毫 → 元

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
    import uuid as uuid_module

    from open_webui.utils.alipay import create_page_payment, is_alipay_configured
    from open_webui.models.billing import PaymentOrders

    # 检查支付宝配置
    if not is_alipay_configured():
        raise HTTPException(status_code=503, detail="支付功能暂未开放，请联系管理员")

    # 验证金额
    if req.amount < 0.01:
        raise HTTPException(status_code=400, detail="充值金额最低0.01元")
    if req.amount > 10000:
        raise HTTPException(status_code=400, detail="充值金额最高10000元")

    # 生成订单号: CK + 时间戳 + 随机字符
    out_trade_no = f"CK{int(time.time())}{uuid_module.uuid4().hex[:8].upper()}"

    # 调用支付宝创建PC网页支付订单
    success, msg, pay_url = create_page_payment(
        out_trade_no=out_trade_no,
        amount_yuan=req.amount,
        subject="Cakumi账户充值",
    )

    if not success:
        log.error(f"创建支付订单失败: {msg}")
        raise HTTPException(status_code=500, detail=f"创建订单失败: {msg}")

    # 保存订单到数据库
    now = int(time.time())
    expired_at = now + 900  # 15分钟后过期

    order = PaymentOrders.create(
        user_id=user.id,
        out_trade_no=out_trade_no,
        amount=int(req.amount * 10000),  # 元 → 毫
        qr_code=pay_url,  # 存储跳转URL
        expired_at=expired_at,
        payment_method="alipay",
        payment_type="page",
    )

    log.info(f"创建PC支付订单成功: {out_trade_no}, 用户={user.id}, 金额={req.amount}元")

    # 埋点：创建订单
    from open_webui.utils.posthog import track_payment_order_created, flush
    track_payment_order_created(
        user_id=user.id,
        order_id=order.id,
        out_trade_no=out_trade_no,
        amount_yuan=req.amount,
        payment_type="page",
    )
    flush()  # 立即发送到 PostHog

    return CreateOrderResponse(
        order_id=order.id,
        out_trade_no=out_trade_no,
        pay_url=pay_url,
        amount=req.amount,
        expired_at=expired_at,
    )


@router.post("/payment/create/h5", response_model=CreateH5OrderResponse)
async def create_h5_payment_order(req: CreateOrderRequest, user=Depends(get_verified_user)):
    """
    创建H5支付订单（移动端跳转支付宝收银台）

    需要登录
    """
    import uuid as uuid_module

    from open_webui.utils.alipay import create_wap_payment, is_alipay_configured
    from open_webui.models.billing import PaymentOrders

    # 检查支付宝配置
    if not is_alipay_configured():
        raise HTTPException(status_code=503, detail="支付功能暂未开放，请联系管理员")

    # 验证金额
    if req.amount < 0.01:
        raise HTTPException(status_code=400, detail="充值金额最低0.01元")
    if req.amount > 10000:
        raise HTTPException(status_code=400, detail="充值金额最高10000元")

    # 生成订单号: CK + 时间戳 + 随机字符
    out_trade_no = f"CK{int(time.time())}{uuid_module.uuid4().hex[:8].upper()}"

    # 调用支付宝创建H5支付订单
    success, msg, pay_url = create_wap_payment(
        out_trade_no=out_trade_no,
        amount_yuan=req.amount,
        subject="Cakumi账户充值",
    )

    if not success:
        log.error(f"创建H5支付订单失败: {msg}")
        raise HTTPException(status_code=500, detail=f"创建订单失败: {msg}")

    # 保存订单到数据库
    now = int(time.time())
    expired_at = now + 900  # 15分钟后过期

    order = PaymentOrders.create(
        user_id=user.id,
        out_trade_no=out_trade_no,
        amount=int(req.amount * 10000),  # 元 → 毫
        qr_code=pay_url,  # H5支付存储跳转URL
        expired_at=expired_at,
        payment_method="alipay",
        payment_type="h5",
    )

    log.info(f"创建H5支付订单成功: {out_trade_no}, 用户={user.id}, 金额={req.amount}元")

    # 埋点：创建订单
    from open_webui.utils.posthog import track_payment_order_created, flush
    track_payment_order_created(
        user_id=user.id,
        order_id=order.id,
        out_trade_no=out_trade_no,
        amount_yuan=req.amount,
        payment_type="h5",
    )
    flush()  # 立即发送到 PostHog

    return CreateH5OrderResponse(
        order_id=order.id,
        out_trade_no=out_trade_no,
        pay_url=pay_url,
        amount=req.amount,
        expired_at=expired_at,
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
        first_recharge_log = FirstRechargeBonusLogs.get_by_user_id(user.id)
        if first_recharge_log:
            # 通过充值金额和支付时间判断（允许10秒误差）
            if (
                abs(order.amount - first_recharge_log.recharge_amount) < 100
                and abs(order.paid_at - (first_recharge_log.created_at // 1000000000)) < 10
            ):
                is_first_recharge = True
                bonus_amount = first_recharge_log.bonus_amount / 10000  # 毫 → 元
                bonus_rate = first_recharge_log.bonus_rate

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
    from open_webui.utils.alipay import verify_notify_sign
    from open_webui.models.billing import PaymentOrders, RechargeLog
    import uuid as uuid_module

    # 获取回调参数
    form_data = await request.form()
    params = dict(form_data)

    log.info(f"收到支付宝回调: {params.get('out_trade_no')}")

    # 验签
    if not verify_notify_sign(params):
        log.error("支付宝回调验签失败")
        return "fail"

    out_trade_no = params.get("out_trade_no")
    trade_no = params.get("trade_no")
    trade_status = params.get("trade_status")

    # 只处理支付成功状态
    if trade_status not in ["TRADE_SUCCESS", "TRADE_FINISHED"]:
        log.info(f"支付宝回调，非成功状态: {trade_status}")
        return "success"

    # 查询订单
    order = PaymentOrders.get_by_out_trade_no(out_trade_no)
    if not order:
        log.error(f"支付宝回调，订单不存在: {out_trade_no}")
        return "success"

    # 幂等检查：已处理的订单直接返回成功
    if order.status == "paid":
        log.info(f"支付宝回调，订单已处理: {out_trade_no}")
        return "success"

    # 更新订单状态
    now = int(time.time())
    PaymentOrders.update_status(
        out_trade_no=out_trade_no,
        status="paid",
        trade_no=trade_no,
        paid_at=now,
    )

    # 增加用户余额
    try:
        from open_webui.models.users import User as UserModel
        from open_webui.models.billing import FirstRechargeBonusLogs, BillingLog
        from open_webui.config import (
            FIRST_RECHARGE_BONUS_ENABLED,
            FIRST_RECHARGE_BONUS_RATE,
            FIRST_RECHARGE_BONUS_MAX_AMOUNT,
        )

        with get_db() as db:
            user = db.query(UserModel).filter_by(id=order.user_id).first()
            if user:
                # 检查是否需要发放首充优惠
                bonus_amount = 0
                is_first_recharge = False
                matched_tier = None

                # 预设档位（毫）
                PRESET_TIERS = [100000, 500000, 1000000, 2000000, 5000000, 10000000]  # 10, 50, 100, 200, 500, 1000元

                # 精确匹配档位
                if order.amount in PRESET_TIERS:
                    matched_tier = order.amount
                    # 检查该档位是否已参与
                    if (
                        FIRST_RECHARGE_BONUS_ENABLED.value
                        and not FirstRechargeBonusLogs.has_participated_tier(order.user_id, matched_tier)
                    ):
                        is_first_recharge = True
                        # 计算奖励金额
                        rate = float(FIRST_RECHARGE_BONUS_RATE.value) / 100
                        max_amount = int(FIRST_RECHARGE_BONUS_MAX_AMOUNT.value)
                        bonus_amount = int(order.amount * rate)
                        bonus_amount = min(bonus_amount, max_amount)

                # 更新用户余额（充值金额 + 奖励金额）
                total_amount = order.amount + bonus_amount
                user.balance = (user.balance or 0) + total_amount
                db.commit()

                # 记录充值日志
                recharge_log = RechargeLog(
                    id=str(uuid_module.uuid4()),
                    user_id=order.user_id,
                    amount=order.amount,
                    operator_id="system",  # 系统自动充值
                    remark=f"支付宝充值，订单号: {out_trade_no}",
                    created_at=now,
                )
                db.add(recharge_log)
                db.commit()

                # 如果是首充，记录首充优惠日志和计费日志
                if is_first_recharge and bonus_amount > 0 and matched_tier is not None:
                    try:
                        # 记录首充优惠参与记录（包含档位信息）
                        FirstRechargeBonusLogs.create(
                            user_id=order.user_id,
                            tier_amount=matched_tier,  # 记录档位金额
                            recharge_amount=order.amount,
                            bonus_amount=bonus_amount,
                            bonus_rate=int(FIRST_RECHARGE_BONUS_RATE.value),
                        )

                        # 记录计费日志（奖励类型）
                        billing_log = BillingLog(
                            id=str(uuid_module.uuid4()),
                            user_id=order.user_id,
                            model_id="first_recharge_bonus",
                            prompt_tokens=0,
                            completion_tokens=0,
                            total_cost=bonus_amount,
                            balance_after=user.balance,
                            log_type="refund",  # 使用 refund 类型表示奖励
                            created_at=int(time.time_ns()),
                        )
                        db.add(billing_log)
                        db.commit()

                        log.info(
                            f"首充优惠发放成功: 用户={order.user_id}, "
                            f"充值={order.amount / 10000:.2f}元, "
                            f"奖励={bonus_amount / 10000:.2f}元"
                        )
                    except Exception as e:
                        log.error(f"首充优惠记录失败: {e}")
                        # 不影响充值流程，继续执行

                log.info(
                    f"支付成功: 用户={order.user_id}, 金额={order.amount / 10000:.2f}元, "
                    f"订单={out_trade_no}"
                    + (f", 首充奖励={bonus_amount / 10000:.2f}元" if is_first_recharge else "")
                )

                # 埋点：支付成功
                from open_webui.utils.posthog import track_payment_success, flush
                track_payment_success(
                    user_id=order.user_id,
                    order_id=order.id,
                    out_trade_no=out_trade_no,
                    trade_no=trade_no,
                    amount_yuan=order.amount / 10000,
                    is_first_recharge=is_first_recharge,
                    bonus_amount_yuan=bonus_amount / 10000 if bonus_amount else 0,
                )
                flush()  # 立即发送到 PostHog
    except Exception as e:
        log.error(f"支付回调处理失败: {e}")
        # 即使余额更新失败，也返回 success，避免支付宝重复回调
        # 后续可通过定时任务修复

    return "success"


@router.get("/payment/config")
async def get_payment_config():
    """
    获取支付配置状态

    公开接口，用于前端判断是否显示充值功能
    """
    from open_webui.utils.alipay import is_alipay_configured

    return {
        "alipay_enabled": is_alipay_configured(),
    }
