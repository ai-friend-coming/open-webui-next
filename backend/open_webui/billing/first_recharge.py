"""
首充优惠服务

实现档位独立的首充返现逻辑，支持支付宝/虎皮椒共用
"""

import time
import uuid
import logging
from typing import Tuple, Optional, List

from open_webui.config import (
    Config,
    FIRST_RECHARGE_BONUS_ENABLED,
    FIRST_RECHARGE_BONUS_RATE,
    FIRST_RECHARGE_BONUS_MAX_AMOUNT,
)
from open_webui.models.billing import FirstRechargeBonusLogs, BillingLog
from open_webui.internal.db import get_db
from open_webui.billing.core import RECHARGE_TIERS

log = logging.getLogger(__name__)


def get_recharge_tiers_from_db(db) -> List[int]:
    """
    从数据库获取充值档位配置

    避免多 worker 进程内存不一致问题
    """
    config_entry = db.query(Config).order_by(Config.id.desc()).first()
    if (
        config_entry
        and "billing" in config_entry.data
        and "recharge_tiers" in config_entry.data["billing"]
    ):
        return config_entry.data["billing"]["recharge_tiers"]

    # 默认档位
    return RECHARGE_TIERS.value


def process_first_recharge_bonus(
    user_id: str,
    recharge_amount: int,
    db=None,
) -> Tuple[int, bool]:
    """
    处理首充优惠

    Args:
        user_id: 用户ID
        recharge_amount: 充值金额（毫）
        db: 数据库会话（可选，如果不传则自动获取）

    Returns:
        Tuple[int, bool]: (奖励金额（毫）, 是否为首充)
    """
    if not FIRST_RECHARGE_BONUS_ENABLED.value:
        return 0, False

    should_close_db = db is None
    if should_close_db:
        db_context = get_db()
        db = db_context.__enter__()
    else:
        db_context = None

    try:
        # 1. 获取档位配置
        recharge_tiers = get_recharge_tiers_from_db(db)

        # 2. 精确匹配档位
        if recharge_amount not in recharge_tiers:
            log.debug(
                f"首充优惠: 金额 {recharge_amount} 不在档位列表中，跳过"
            )
            return 0, False

        matched_tier = recharge_amount

        # 3. 检查该档位是否已参与
        if FirstRechargeBonusLogs.has_participated_tier(user_id, matched_tier):
            log.debug(
                f"首充优惠: 用户 {user_id} 档位 {matched_tier} 已参与过，跳过"
            )
            return 0, False

        # 4. 计算奖励金额
        rate = float(FIRST_RECHARGE_BONUS_RATE.value) / 100
        max_amount = int(FIRST_RECHARGE_BONUS_MAX_AMOUNT.value)
        bonus_amount = int(recharge_amount * rate)
        bonus_amount = min(bonus_amount, max_amount)

        if bonus_amount <= 0:
            return 0, False

        # 5. 记录首充参与
        FirstRechargeBonusLogs.create(
            user_id=user_id,
            tier_amount=matched_tier,
            recharge_amount=recharge_amount,
            bonus_amount=bonus_amount,
            bonus_rate=int(FIRST_RECHARGE_BONUS_RATE.value),
        )

        log.info(
            f"首充优惠匹配成功: user={user_id}, tier={matched_tier / 10000:.2f}元, "
            f"bonus={bonus_amount / 10000:.2f}元"
        )

        return bonus_amount, True

    except Exception as e:
        log.error(f"首充优惠处理异常: {e}")
        return 0, False

    finally:
        if should_close_db and db_context:
            db_context.__exit__(None, None, None)


def record_first_recharge_billing_log(
    user_id: str,
    bonus_amount: int,
    balance_after: int,
    db,
) -> None:
    """
    记录首充奖励的计费日志

    Args:
        user_id: 用户ID
        bonus_amount: 奖励金额（毫）
        balance_after: 余额（毫）
        db: 数据库会话
    """
    billing_log = BillingLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        model_id="first_recharge_bonus",
        prompt_tokens=0,
        completion_tokens=0,
        total_cost=bonus_amount,
        balance_after=balance_after,
        log_type="refund",
        created_at=int(time.time_ns()),
    )
    db.add(billing_log)
    db.commit()


def get_available_tiers(user_id: str) -> List[dict]:
    """
    获取用户可参与首充的档位列表

    Args:
        user_id: 用户ID

    Returns:
        list[dict]: 可用档位列表，每项包含:
            - tier_amount: 档位金额（毫）
            - bonus_amount: 预计奖励（毫）
            - participated: 是否已参与
    """
    participated_tiers = FirstRechargeBonusLogs.get_participated_tiers(user_id)

    with get_db() as db:
        recharge_tiers = get_recharge_tiers_from_db(db)

    rate = float(FIRST_RECHARGE_BONUS_RATE.value) / 100
    max_amount = int(FIRST_RECHARGE_BONUS_MAX_AMOUNT.value)

    result = []
    for tier in recharge_tiers:
        bonus = min(int(tier * rate), max_amount)
        result.append(
            {
                "tier_amount": tier,
                "bonus_amount": bonus,
                "participated": tier in participated_tiers,
            }
        )

    return result


def is_first_recharge_enabled() -> bool:
    """检查首充优惠是否启用"""
    return bool(FIRST_RECHARGE_BONUS_ENABLED.value)


def get_first_recharge_config() -> dict:
    """获取首充优惠配置"""
    return {
        "enabled": bool(FIRST_RECHARGE_BONUS_ENABLED.value),
        "rate": int(FIRST_RECHARGE_BONUS_RATE.value),
        "max_amount": int(FIRST_RECHARGE_BONUS_MAX_AMOUNT.value) / 10000,  # 转换为元
    }
