"""
兑换码路由

提供兑换码的管理和兑换功能。
"""

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status

from open_webui.models.redeem_codes import (
    RedeemCodeForm,
    RedeemCodeModel,
    RedeemLogModel,
    RedeemCodes,
)
from open_webui.models.users import Users
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.constants import ERROR_MESSAGES

router = APIRouter()


####################
# Request/Response Models
####################


class RedeemCodeResponse(BaseModel):
    """兑换码响应（包含计算的状态和剩余次数）"""

    id: str
    code: str
    amount: float  # 元
    max_uses: int
    current_uses: int
    remaining_uses: int  # 剩余次数
    start_time: int
    end_time: int
    enabled: bool
    created_by: str
    creator_name: str  # 创建者名称
    remark: Optional[str]
    created_at: int
    updated_at: int
    status: str  # 'pending'|'active'|'expired'|'exhausted'|'disabled'


class RedeemCodeListResponse(BaseModel):
    """兑换码列表响应"""

    codes: list[RedeemCodeResponse]
    total: int


class RedeemCodeStatsResponse(BaseModel):
    """兑换码统计响应"""

    total_amount: float  # 总兑换金额（元）
    total_users: int  # 兑换用户数
    total_uses: int  # 兑换次数


class RedeemRequest(BaseModel):
    """兑换请求"""

    code: str = Field(..., min_length=6, max_length=32, description="兑换码")


class RedeemResponse(BaseModel):
    """兑换响应"""

    amount: float  # 兑换金额（元）
    balance: float  # 兑换后余额（元）
    message: str  # 成功消息


class RedeemLogResponse(BaseModel):
    """兑换日志响应"""

    id: str
    code: str
    user_id: str
    user_name: str
    amount: float  # 元
    balance_before: float  # 元
    balance_after: float  # 元
    created_at: int


####################
# Helper Functions
####################


def to_response(code: RedeemCodeModel) -> RedeemCodeResponse:
    """将数据库模型转换为响应模型"""
    # 获取创建者信息
    creator = Users.get_user_by_id(code.created_by)
    creator_name = creator.name if creator else "未知"

    # 计算状态
    status = RedeemCodes.calculate_status(code)

    # 计算剩余次数
    remaining_uses = max(0, code.max_uses - code.current_uses)

    return RedeemCodeResponse(
        id=code.id,
        code=code.code,
        amount=code.amount / 10000,  # 毫转元
        max_uses=code.max_uses,
        current_uses=code.current_uses,
        remaining_uses=remaining_uses,
        start_time=code.start_time,
        end_time=code.end_time,
        enabled=code.enabled,
        created_by=code.created_by,
        creator_name=creator_name,
        remark=code.remark,
        created_at=code.created_at,
        updated_at=code.updated_at,
        status=status,
    )


def to_log_response(log: RedeemLogModel) -> RedeemLogResponse:
    """将兑换日志转换为响应模型"""
    user = Users.get_user_by_id(log.user_id)
    user_name = user.name if user else "未知"

    return RedeemLogResponse(
        id=log.id,
        code=log.code,
        user_id=log.user_id,
        user_name=user_name,
        amount=log.amount / 10000,  # 毫转元
        balance_before=log.balance_before / 10000,  # 毫转元
        balance_after=log.balance_after / 10000,  # 毫转元
        created_at=log.created_at,
    )


####################
# 管理员 API
####################


@router.post("/redeem-codes/create", response_model=RedeemCodeResponse)
async def create_redeem_code(form: RedeemCodeForm, admin=Depends(get_admin_user)):
    """
    创建兑换码

    需要管理员权限
    """
    # 验证兑换码唯一性
    existing = RedeemCodes.get_redeem_code_by_code(form.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="兑换码已存在，请使用其他兑换码",
        )

    # 验证时间范围
    if form.start_time >= form.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="生效时间必须早于失效时间",
        )

    # 创建兑换码
    code = RedeemCodes.create_redeem_code(admin.id, form)
    if not code:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT(),
        )

    return to_response(code)


@router.get("/redeem-codes", response_model=RedeemCodeListResponse)
async def list_redeem_codes(
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    admin=Depends(get_admin_user),
):
    """
    查询兑换码列表

    需要管理员权限
    支持状态筛选和分页
    """
    codes, total = RedeemCodes.list_redeem_codes(
        status=status_filter, skip=skip, limit=limit
    )
    return RedeemCodeListResponse(
        codes=[to_response(c) for c in codes],
        total=total,
    )


@router.get("/redeem-codes/{code_id}", response_model=RedeemCodeResponse)
async def get_redeem_code(code_id: str, admin=Depends(get_admin_user)):
    """
    查询兑换码详情

    需要管理员权限
    """
    code = RedeemCodes.get_redeem_code_by_id(code_id)
    if not code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="兑换码不存在",
        )

    return to_response(code)


@router.put("/redeem-codes/{code_id}", response_model=RedeemCodeResponse)
async def update_redeem_code(
    code_id: str,
    form: RedeemCodeForm,
    admin=Depends(get_admin_user),
):
    """
    更新兑换码

    需要管理员权限
    不允许修改已使用次数 > 0 的兑换码的金额
    """
    # 检查兑换码是否存在
    existing = RedeemCodes.get_redeem_code_by_id(code_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="兑换码不存在",
        )

    # 验证时间范围
    if form.start_time >= form.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="生效时间必须早于失效时间",
        )

    # 如果更改了兑换码，检查新兑换码是否已存在
    if form.code != existing.code:
        duplicate = RedeemCodes.get_redeem_code_by_code(form.code)
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="兑换码已存在，请使用其他兑换码",
            )

    try:
        code = RedeemCodes.update_redeem_code(code_id, form)
        if not code:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ERROR_MESSAGES.DEFAULT(),
            )

        return to_response(code)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/redeem-codes/{code_id}")
async def delete_redeem_code(code_id: str, admin=Depends(get_admin_user)):
    """
    删除兑换码（软删除）

    需要管理员权限
    """
    result = RedeemCodes.delete_redeem_code(code_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="兑换码不存在",
        )

    return {"success": True}


@router.post("/redeem-codes/{code_id}/toggle", response_model=RedeemCodeResponse)
async def toggle_redeem_code(code_id: str, admin=Depends(get_admin_user)):
    """
    启用/禁用兑换码

    需要管理员权限
    """
    code = RedeemCodes.toggle_enabled(code_id)
    if not code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="兑换码不存在",
        )

    return to_response(code)


@router.get(
    "/redeem-codes/{code_id}/logs",
    response_model=list[RedeemLogResponse],
)
async def get_redeem_code_logs(
    code_id: str,
    skip: int = 0,
    limit: int = 50,
    admin=Depends(get_admin_user),
):
    """
    查询兑换码的兑换日志

    需要管理员权限
    """
    logs = RedeemCodes.get_redeem_logs(code_id, skip, limit)
    return [to_log_response(log) for log in logs]


@router.get(
    "/redeem-codes/{code_id}/stats",
    response_model=RedeemCodeStatsResponse,
)
async def get_redeem_code_stats(code_id: str, admin=Depends(get_admin_user)):
    """
    查询兑换码统计信息

    需要管理员权限
    """
    logs = RedeemCodes.get_redeem_logs(code_id, skip=0, limit=10000)

    # 计算统计信息
    total_amount = sum(log.amount for log in logs) / 10000  # 毫转元
    total_users = len(set(log.user_id for log in logs))
    total_uses = len(logs)

    return RedeemCodeStatsResponse(
        total_amount=total_amount,
        total_users=total_users,
        total_uses=total_uses,
    )


####################
# 用户 API
####################


@router.post("/redeem-codes/redeem", response_model=RedeemResponse)
async def redeem_code(req: RedeemRequest, user=Depends(get_verified_user)):
    """
    用户兑换码兑换

    业务逻辑：
    1. 验证兑换码存在
    2. 验证兑换码未过期
    3. 验证兑换码未用尽
    4. 验证兑换码已启用
    5. 验证用户未使用过该兑换码
    6. 在事务中增加余额、使用次数、记录日志
    """
    try:
        result = RedeemCodes.redeem(req.code, user.id)

        return RedeemResponse(
            amount=result["amount"] / 10000,  # 毫转元
            balance=result["balance_after"] / 10000,  # 毫转元
            message=result["message"],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/redeem-logs/my", response_model=list[RedeemLogResponse])
async def get_my_redeem_logs(
    skip: int = 0,
    limit: int = 50,
    user=Depends(get_verified_user),
):
    """
    查询当前用户的兑换记录

    需要登录
    """
    logs = RedeemCodes.get_user_redeem_logs(user.id, skip, limit)
    return [to_log_response(log) for log in logs]
