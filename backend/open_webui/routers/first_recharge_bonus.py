"""
首充优惠活动管理 API 路由

提供首充优惠活动的配置、统计、参与者列表等管理接口
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from open_webui.models.billing import FirstRechargeBonusLogs
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.config import (
    get_config,
    save_config,
    FIRST_RECHARGE_BONUS_ENABLED,
    FIRST_RECHARGE_BONUS_RATE,
    FIRST_RECHARGE_BONUS_MAX_AMOUNT,
)

log = logging.getLogger(__name__)

router = APIRouter()


####################
# Request/Response Models
####################


class FirstRechargeBonusConfig(BaseModel):
    """首充优惠配置"""

    enabled: bool = Field(..., description="是否启用")
    rate: float = Field(..., ge=0, le=100, description="返现比例（百分比）")
    max_amount: float = Field(..., ge=0, description="最高返现金额（元）")


class FirstRechargeBonusStats(BaseModel):
    """首充优惠统计"""

    participant_count: int = Field(..., description="参与人数")
    total_recharge: float = Field(..., description="总充值金额（元）")
    total_bonus: float = Field(..., description="总奖励金额（元）")


class ParticipantItem(BaseModel):
    """参与者信息"""

    id: str
    user_id: str
    user_name: str
    user_email: Optional[str] = None
    recharge_amount: float = Field(..., description="首充金额（元）")
    bonus_amount: float = Field(..., description="奖励金额（元）")
    bonus_rate: int = Field(..., description="返现比例（整数百分比）")
    created_at: int = Field(..., description="参与时间（纳秒时间戳）")


class ParticipantListResponse(BaseModel):
    """参与者列表响应"""

    participants: list[ParticipantItem]
    total: int


class EligibilityResponse(BaseModel):
    """资格检查响应"""

    eligible: bool = Field(..., description="是否有资格参与")
    reason: Optional[str] = Field(None, description="不符合资格的原因")


class TierEligibility(BaseModel):
    """档位资格"""

    tier_amount: float = Field(..., description="档位金额（元）")
    eligible: bool = Field(..., description="是否有资格参与")


class TiersEligibilityResponse(BaseModel):
    """所有档位资格检查响应"""

    enabled: bool = Field(..., description="活动是否启用")
    tiers: list[TierEligibility] = Field(..., description="各档位资格列表")


####################
# API Endpoints
####################


@router.get("/config/public", response_model=FirstRechargeBonusConfig)
async def get_first_recharge_bonus_config_public():
    """
    获取首充优惠配置（公开接口，无需登录）

    前端用于显示首充优惠活动信息
    """
    try:
        return FirstRechargeBonusConfig(
            enabled=bool(FIRST_RECHARGE_BONUS_ENABLED.value),
            rate=float(FIRST_RECHARGE_BONUS_RATE.value),
            max_amount=float(FIRST_RECHARGE_BONUS_MAX_AMOUNT.value) / 10000,  # 毫 → 元
        )
    except Exception as e:
        log.error(f"获取首充优惠配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.get("/config", response_model=FirstRechargeBonusConfig)
async def get_first_recharge_bonus_config(admin=Depends(get_admin_user)):
    """
    获取首充优惠配置

    需要管理员权限
    """
    try:
        return FirstRechargeBonusConfig(
            enabled=bool(FIRST_RECHARGE_BONUS_ENABLED.value),
            rate=float(FIRST_RECHARGE_BONUS_RATE.value),
            max_amount=float(FIRST_RECHARGE_BONUS_MAX_AMOUNT.value) / 10000,  # 毫 → 元
        )
    except Exception as e:
        log.error(f"获取首充优惠配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.post("/config", response_model=FirstRechargeBonusConfig)
async def update_first_recharge_bonus_config(
    config: FirstRechargeBonusConfig, admin=Depends(get_admin_user)
):
    """
    更新首充优惠配置

    需要管理员权限
    """
    try:
        # 获取当前配置
        current_config = get_config()

        # 更新配置（深拷贝避免修改原对象）
        import copy

        new_config = copy.deepcopy(current_config)

        # 确保 ui.first_recharge_bonus 路径存在
        if "ui" not in new_config:
            new_config["ui"] = {}
        if "first_recharge_bonus" not in new_config["ui"]:
            new_config["ui"]["first_recharge_bonus"] = {}

        # 更新配置值
        new_config["ui"]["first_recharge_bonus"]["enabled"] = config.enabled
        new_config["ui"]["first_recharge_bonus"]["rate"] = config.rate
        new_config["ui"]["first_recharge_bonus"]["max_amount"] = int(
            config.max_amount * 10000
        )  # 元 → 毫

        # 保存配置
        if not save_config(new_config):
            raise HTTPException(status_code=500, detail="保存配置失败")

        log.info(
            f"管理员 {admin.id} 更新首充优惠配置: enabled={config.enabled}, "
            f"rate={config.rate}%, max_amount={config.max_amount}元"
        )

        return config
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"更新首充优惠配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


@router.get("/stats", response_model=FirstRechargeBonusStats)
async def get_first_recharge_bonus_stats(admin=Depends(get_admin_user)):
    """
    获取首充优惠统计

    需要管理员权限
    """
    try:
        stats = FirstRechargeBonusLogs.get_stats()

        return FirstRechargeBonusStats(
            participant_count=stats["participant_count"],
            total_recharge=stats["total_recharge"] / 10000,  # 毫 → 元
            total_bonus=stats["total_bonus"] / 10000,  # 毫 → 元
        )
    except Exception as e:
        log.error(f"获取首充优惠统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


@router.get("/participants", response_model=ParticipantListResponse)
async def get_first_recharge_bonus_participants(
    limit: int = 50, offset: int = 0, admin=Depends(get_admin_user)
):
    """
    获取首充优惠参与者列表

    需要管理员权限
    """
    try:
        participants, total = FirstRechargeBonusLogs.get_participant_list(
            limit=limit, offset=offset
        )

        # 转换金额单位（毫 → 元）
        participants_formatted = [
            ParticipantItem(
                id=p["id"],
                user_id=p["user_id"],
                user_name=p["user_name"],
                user_email=p.get("user_email"),
                recharge_amount=p["recharge_amount"] / 10000,
                bonus_amount=p["bonus_amount"] / 10000,
                bonus_rate=p["bonus_rate"],
                created_at=p["created_at"],
            )
            for p in participants
        ]

        return ParticipantListResponse(participants=participants_formatted, total=total)
    except Exception as e:
        log.error(f"获取参与者列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取参与者列表失败: {str(e)}")


@router.get("/eligibility", response_model=EligibilityResponse)
async def check_first_recharge_bonus_eligibility(user=Depends(get_verified_user)):
    """
    检查当前用户是否有资格参与首充优惠（任意档位）

    需要登录
    """
    try:
        # 检查活动是否启用
        if not FIRST_RECHARGE_BONUS_ENABLED.value:
            return EligibilityResponse(eligible=False, reason="活动未启用")

        # 检查用户是否已参与过任何档位
        has_participated = FirstRechargeBonusLogs.has_participated(user.id)
        if has_participated:
            return EligibilityResponse(eligible=False, reason="您已参与过首充优惠")

        return EligibilityResponse(eligible=True)
    except Exception as e:
        log.error(f"检查资格失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查资格失败: {str(e)}")


@router.get("/eligibility/tiers", response_model=TiersEligibilityResponse)
async def check_tiers_eligibility(user=Depends(get_verified_user)):
    """
    检查当前用户在所有预设档位的首充资格

    需要登录
    """
    try:
        # 从数据库读取充值档位配置
        from open_webui.config import Config
        from open_webui.internal.db import get_db

        with get_db() as db:
            config_entry = db.query(Config).order_by(Config.id.desc()).first()

            if config_entry and "billing" in config_entry.data and "recharge_tiers" in config_entry.data["billing"]:
                tiers_mils = config_entry.data["billing"]["recharge_tiers"]
            else:
                # 如果数据库没有配置，使用默认值
                tiers_mils = [100000, 500000, 1000000, 2000000, 5000000, 10000000]

        # 转换为元
        PRESET_TIERS = [tier / 10000 for tier in tiers_mils]

        # 检查活动是否启用
        if not FIRST_RECHARGE_BONUS_ENABLED.value:
            return TiersEligibilityResponse(
                enabled=False,
                tiers=[TierEligibility(tier_amount=tier, eligible=False) for tier in PRESET_TIERS]
            )

        # 获取用户已参与的档位（毫）
        participated_tiers_milli = FirstRechargeBonusLogs.get_participated_tiers(user.id)
        participated_tiers_yuan = [tier / 10000 for tier in participated_tiers_milli]

        # 检查每个档位的资格
        tier_eligibilities = []
        for tier in PRESET_TIERS:
            eligible = tier not in participated_tiers_yuan
            tier_eligibilities.append(TierEligibility(tier_amount=tier, eligible=eligible))

        return TiersEligibilityResponse(enabled=True, tiers=tier_eligibilities)
    except Exception as e:
        log.error(f"检查档位资格失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查档位资格失败: {str(e)}")
