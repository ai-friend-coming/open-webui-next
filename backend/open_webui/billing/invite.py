"""
邀请返现核心逻辑

实现邀请关系管理、返现计算、返现发放等功能
"""

import time
import uuid
import logging
from typing import Optional

from open_webui.config import PersistentConfig
from open_webui.models.users import Users, User
from open_webui.models.billing import BillingLog
from open_webui.models.invite import InviteRebateLogs, InviteStatsTable
from open_webui.internal.db import get_db

log = logging.getLogger(__name__)


# ============================================================================
# 配置项
# ============================================================================

# 邀请返现比例（百分比，默认5%）
INVITE_REBATE_RATE = PersistentConfig(
    "INVITE_REBATE_RATE",
    "invite.rebate_rate",
    5,
)


# ============================================================================
# 核心函数
# ============================================================================


def process_invite_rebate(
    invitee_id: str,
    recharge_amount: int,
    recharge_log_id: Optional[str] = None,
) -> bool:
    """
    处理邀请返现

    在被邀请人充值成功后调用，给邀请人发放返现

    Args:
        invitee_id: 被邀请人ID
        recharge_amount: 充值金额（毫，1元=10000毫）
        recharge_log_id: 充值日志ID（可选）

    Returns:
        bool: 是否成功发放返现
    """
    try:
        with get_db() as db:
            # 1. 查询被邀请人的邀请关系
            invitee = db.query(User).filter(User.id == invitee_id).first()
            if not invitee or not invitee.invited_by:
                log.debug(f"User {invitee_id} has no inviter, skipping rebate")
                return False

            inviter_id = invitee.invited_by

            # 2. 使用行锁获取邀请人记录（确保并发安全）
            inviter = (
                db.query(User)
                .filter(User.id == inviter_id)
                .with_for_update()
                .first()
            )

            if not inviter:
                log.warning(f"Inviter {inviter_id} not found, skipping rebate")
                return False

            # 3. 计算返现金额
            rebate_rate = INVITE_REBATE_RATE.value
            rebate_amount = int(recharge_amount * rebate_rate / 100)

            if rebate_amount <= 0:
                log.debug(f"Rebate amount is 0, skipping (rate={rebate_rate}%)")
                return False

            # 4. 记录返现前余额
            balance_before = inviter.balance

            # 5. 增加邀请人余额
            inviter.balance += rebate_amount
            balance_after = inviter.balance

            # 6. 如果邀请人账户被冻结且余额 >= 0.01元，则解冻
            if inviter.billing_status == "frozen" and balance_after >= 100:
                inviter.billing_status = "active"
                log.info(f"Unfroze inviter {inviter_id} account (balance={balance_after} mils)")

            # 7. 提交用户余额更新
            db.commit()
            db.refresh(inviter)

            # 8. 记录邀请返现日志
            rebate_log = InviteRebateLogs.insert_rebate_log(
                inviter_id=inviter_id,
                invitee_id=invitee_id,
                recharge_amount=recharge_amount,
                rebate_amount=rebate_amount,
                rebate_rate=rebate_rate,
                inviter_balance_before=balance_before,
                inviter_balance_after=balance_after,
                recharge_log_id=recharge_log_id,
            )

            # 9. 记录到 BillingLog（用于账单审计）
            billing_log = BillingLog(
                id=str(uuid.uuid4()),
                user_id=inviter_id,
                model_id="invite_rebate",
                prompt_tokens=0,
                completion_tokens=0,
                total_cost=-rebate_amount,  # 负数表示收入
                balance_after=balance_after,
                log_type="rebate",
                created_at=time.time_ns(),
            )
            db.add(billing_log)
            db.commit()

            # 10. 检查是否是首次返现（判断是否新邀请人）
            is_new_invitee = (
                db.query(User)
                .filter(User.invited_by == inviter_id, User.id == invitee_id)
                .count()
                == 1
            )

            # 11. 更新邀请统计
            InviteStatsTable.increment_stats(
                user_id=inviter_id,
                rebate_amount=rebate_amount,
                is_new_invitee=is_new_invitee,
            )

            log.info(
                f"Rebate processed: inviter={inviter_id}, invitee={invitee_id}, "
                f"recharge={recharge_amount} mils, rebate={rebate_amount} mils ({rebate_rate}%), "
                f"balance: {balance_before} -> {balance_after} mils"
            )

            return True

    except Exception as e:
        log.exception(f"Failed to process invite rebate for invitee {invitee_id}: {e}")
        return False


def get_invite_info(user_id: str) -> dict:
    """
    获取用户邀请信息

    Args:
        user_id: 用户ID

    Returns:
        dict: 邀请信息 {
            "invite_code": "ABC123",
            "total_invitees": 10,
            "total_rebate_amount": 50000,  # 毫
            "rebate_rate": 5,  # 百分比
        }
    """
    try:
        # 获取用户邀请码
        user = Users.get_user_by_id(user_id)
        if not user:
            return None

        invite_code = user.invite_code

        # 获取邀请统计
        stats = InviteStatsTable.get_stats(user_id)

        return {
            "invite_code": invite_code,
            "total_invitees": stats.total_invitees if stats else 0,
            "total_rebate_amount": stats.total_rebate_amount if stats else 0,
            "rebate_rate": INVITE_REBATE_RATE.value,
        }

    except Exception as e:
        log.exception(f"Failed to get invite info for user {user_id}: {e}")
        return None
