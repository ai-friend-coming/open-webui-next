"""
签到系统 API 路由

提供每日签到、奖励发放、签到记录查询等功能
"""

import logging
import random
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from open_webui.models.sign_in import SignInLogs, SignInLogModel
from open_webui.models.users import Users, User as UserModel
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.config import get_config, save_config
from open_webui.internal.db import get_db

log = logging.getLogger(__name__)

router = APIRouter()


####################
# 配置管理
####################


class SignInConfig(BaseModel):
    """签到配置"""

    enabled: bool = Field(..., description="是否启用签到")
    mean: float = Field(..., ge=0, description="奖励金额均值（元）")
    std: float = Field(..., ge=0, description="奖励金额标准差（元）")
    min_amount: float = Field(..., ge=0, description="最小奖励金额（元）")
    max_amount: float = Field(..., ge=0, description="最大奖励金额（元）")


def get_sign_in_config() -> SignInConfig:
    """获取签到配置"""
    config = get_config()
    sign_in_config = config.get("ui", {}).get("sign_in", {})

    return SignInConfig(
        enabled=sign_in_config.get("enabled", False),
        mean=sign_in_config.get("mean", 1.0),
        std=sign_in_config.get("std", 0.5),
        min_amount=sign_in_config.get("min_amount", 0.1),
        max_amount=sign_in_config.get("max_amount", 5.0),
    )


def generate_reward_amount(config: SignInConfig) -> int:
    """
    生成符合正态分布的奖励金额（毫）

    使用 Box-Muller 变换生成正态分布随机数
    """
    # 生成正态分布随机数
    amount = random.gauss(config.mean, config.std)

    # 限制在最小值和最大值之间
    amount = max(config.min_amount, min(amount, config.max_amount))

    # 转换为毫（1元 = 10000毫）
    amount_milli = int(amount * 10000)

    return amount_milli


####################
# Request/Response Models
####################


class SignInResponse(BaseModel):
    """签到响应"""

    success: bool
    amount: float = Field(..., description="奖励金额（元）")
    message: str
    continuous_days: int = Field(..., description="连续签到天数")


class SignInStatusResponse(BaseModel):
    """签到状态响应"""

    has_signed_today: bool
    continuous_days: int
    total_days: int
    total_amount: float = Field(..., description="累计奖励金额（元）")
    month_days: int


class SignInLogResponse(BaseModel):
    """签到记录响应"""

    id: str
    amount: float = Field(..., description="奖励金额（元）")
    sign_in_date: date
    created_at: int


####################
# API Endpoints
####################


@router.post("/", response_model=SignInResponse)
async def sign_in(user=Depends(get_verified_user)):
    """
    每日签到

    需要登录
    """
    try:
        # 检查签到功能是否启用
        config = get_sign_in_config()
        if not config.enabled:
            raise HTTPException(status_code=403, detail="签到功能暂未开放")

        # 检查今天是否已签到
        if SignInLogs.has_signed_today(user.id):
            raise HTTPException(status_code=400, detail="今天已经签到过了哦~")

        # 生成奖励金额
        amount_milli = generate_reward_amount(config)

        # 创建签到记录
        SignInLogs.create(user_id=user.id, amount=amount_milli)

        # 更新用户余额
        with get_db() as db:
            user_model = db.query(UserModel).filter_by(id=user.id).first()
            if user_model:
                user_model.balance = (user_model.balance or 0) + amount_milli
                db.commit()

        # 获取连续签到天数
        continuous_days = SignInLogs.get_continuous_days(user.id)

        log.info(f"用户 {user.id} 签到成功，奖励 {amount_milli / 10000:.2f} 元")

        return SignInResponse(
            success=True,
            amount=amount_milli / 10000,
            message=f"签到成功！获得 ¥{amount_milli / 10000:.2f} 奖励",
            continuous_days=continuous_days,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"签到失败: {e}")
        raise HTTPException(status_code=500, detail=f"签到失败: {str(e)}")


@router.get("/status", response_model=SignInStatusResponse)
async def get_sign_in_status(user=Depends(get_verified_user)):
    """
    获取签到状态

    需要登录
    """
    try:
        has_signed_today = SignInLogs.has_signed_today(user.id)
        continuous_days = SignInLogs.get_continuous_days(user.id)
        stats = SignInLogs.get_user_stats(user.id)

        return SignInStatusResponse(
            has_signed_today=has_signed_today,
            continuous_days=continuous_days,
            total_days=stats["total_days"],
            total_amount=stats["total_amount"] / 10000,  # 毫 → 元
            month_days=stats["month_days"],
        )
    except Exception as e:
        log.error(f"获取签到状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.get("/logs", response_model=list[SignInLogResponse])
async def get_sign_in_logs(
    user=Depends(get_verified_user), limit: int = 30, offset: int = 0
):
    """
    获取签到记录

    需要登录
    """
    try:
        logs = SignInLogs.get_by_user_id(user.id, limit=limit, offset=offset)

        return [
            SignInLogResponse(
                id=log.id,
                amount=log.amount / 10000,  # 毫 → 元
                sign_in_date=log.sign_in_date,
                created_at=log.created_at,
            )
            for log in logs
        ]
    except Exception as e:
        log.error(f"获取签到记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取记录失败: {str(e)}")


@router.get("/config", response_model=SignInConfig)
async def get_config_endpoint(admin=Depends(get_admin_user)):
    """
    获取签到配置

    需要管理员权限
    """
    return get_sign_in_config()


@router.post("/config", response_model=SignInConfig)
async def update_config_endpoint(
    config: SignInConfig, admin=Depends(get_admin_user)
):
    """
    更新签到配置

    需要管理员权限
    """
    try:
        # 验证配置
        if config.min_amount > config.max_amount:
            raise HTTPException(status_code=400, detail="最小金额不能大于最大金额")

        if config.std < 0:
            raise HTTPException(status_code=400, detail="标准差必须大于等于0")

        # 获取当前配置
        current_config = get_config()

        # 深拷贝避免修改原对象
        import copy
        new_config = copy.deepcopy(current_config)

        # 确保路径存在
        if "ui" not in new_config:
            new_config["ui"] = {}
        if "sign_in" not in new_config["ui"]:
            new_config["ui"]["sign_in"] = {}

        # 更新配置
        new_config["ui"]["sign_in"]["enabled"] = config.enabled
        new_config["ui"]["sign_in"]["mean"] = config.mean
        new_config["ui"]["sign_in"]["std"] = config.std
        new_config["ui"]["sign_in"]["min_amount"] = config.min_amount
        new_config["ui"]["sign_in"]["max_amount"] = config.max_amount

        # 保存配置
        if not save_config(new_config):
            raise HTTPException(status_code=500, detail="保存配置失败")

        log.info(
            f"管理员 {admin.id} 更新签到配置: enabled={config.enabled}, "
            f"mean={config.mean}, std={config.std}"
        )

        return config
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"更新签到配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


@router.get("/config/public", response_model=dict)
async def get_public_config():
    """
    获取签到公开配置（仅返回是否启用）

    无需登录
    """
    config = get_sign_in_config()
    return {
        "enabled": config.enabled,
    }
