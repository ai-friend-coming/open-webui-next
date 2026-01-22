"""
邀请系统数据模型

包含邀请返现日志、邀请统计的 ORM 模型和数据访问层
"""

import time
import uuid
from typing import Optional, List

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, String, Integer, BigInteger, func, desc

from open_webui.internal.db import Base, get_db


####################
# Invite DB Schema
####################


class InviteRebateLog(Base):
    """邀请返现日志表"""

    __tablename__ = "invite_rebate_log"

    id = Column(String, primary_key=True)
    inviter_id = Column(String, nullable=False, index=True)  # 邀请人ID
    invitee_id = Column(String, nullable=False, index=True)  # 被邀请人ID
    recharge_amount = Column(Integer, nullable=False)  # 被邀请人充值金额（毫，1元=10000毫）
    rebate_amount = Column(Integer, nullable=False)  # 返现金额（毫，1元=10000毫）
    rebate_rate = Column(Integer, nullable=False)  # 返现比例（百分比，如5表示5%）
    inviter_balance_before = Column(Integer, nullable=False)  # 邀请人返现前余额（毫）
    inviter_balance_after = Column(Integer, nullable=False)  # 邀请人返现后余额（毫）
    recharge_log_id = Column(String, nullable=True)  # 关联的充值日志ID
    created_at = Column(BigInteger, nullable=False, index=True)


class InviteStats(Base):
    """邀请统计表"""

    __tablename__ = "invite_stats"

    user_id = Column(String, primary_key=True)  # 邀请人ID
    total_invitees = Column(Integer, default=0, nullable=False)  # 总邀请人数
    total_rebate_amount = Column(Integer, default=0, nullable=False)  # 累计返现金额（毫，1元=10000毫）
    last_rebate_at = Column(BigInteger, nullable=True)  # 最后返现时间
    updated_at = Column(BigInteger, nullable=False, index=True)


####################
# Pydantic Models
####################


class InviteRebateLogModel(BaseModel):
    """邀请返现日志 Pydantic 模型"""

    id: str
    inviter_id: str
    invitee_id: str
    recharge_amount: int  # 毫
    rebate_amount: int  # 毫
    rebate_rate: int  # 百分比
    inviter_balance_before: int  # 毫
    inviter_balance_after: int  # 毫
    recharge_log_id: Optional[str] = None
    created_at: int

    model_config = ConfigDict(from_attributes=True)


class InviteStatsModel(BaseModel):
    """邀请统计 Pydantic 模型"""

    user_id: str
    total_invitees: int
    total_rebate_amount: int  # 毫
    last_rebate_at: Optional[int] = None
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


####################
# Data Access Layer
####################


class InviteRebateLogs:
    """邀请返现日志数据访问层"""

    @staticmethod
    def insert_rebate_log(
        inviter_id: str,
        invitee_id: str,
        recharge_amount: int,
        rebate_amount: int,
        rebate_rate: int,
        inviter_balance_before: int,
        inviter_balance_after: int,
        recharge_log_id: Optional[str] = None,
    ) -> InviteRebateLogModel:
        """创建返现记录"""
        with get_db() as db:
            log = InviteRebateLog(
                id=str(uuid.uuid4()),
                inviter_id=inviter_id,
                invitee_id=invitee_id,
                recharge_amount=recharge_amount,
                rebate_amount=rebate_amount,
                rebate_rate=rebate_rate,
                inviter_balance_before=inviter_balance_before,
                inviter_balance_after=inviter_balance_after,
                recharge_log_id=recharge_log_id,
                created_at=time.time_ns(),
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            return InviteRebateLogModel.model_validate(log)

    @staticmethod
    def get_rebate_logs_by_inviter(
        inviter_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> List[InviteRebateLogModel]:
        """获取邀请人的返现记录列表"""
        with get_db() as db:
            logs = (
                db.query(InviteRebateLog)
                .filter(InviteRebateLog.inviter_id == inviter_id)
                .order_by(desc(InviteRebateLog.created_at))
                .offset(skip)
                .limit(limit)
                .all()
            )
            return [InviteRebateLogModel.model_validate(log) for log in logs]

    @staticmethod
    def count_rebate_logs_by_inviter(inviter_id: str) -> int:
        """统计邀请人的返现记录数量"""
        with get_db() as db:
            return (
                db.query(func.count(InviteRebateLog.id))
                .filter(InviteRebateLog.inviter_id == inviter_id)
                .scalar()
            )


class InviteStatsTable:
    """邀请统计数据访问层"""

    @staticmethod
    def get_stats(user_id: str) -> Optional[InviteStatsModel]:
        """获取用户邀请统计"""
        with get_db() as db:
            stats = db.query(InviteStats).filter(InviteStats.user_id == user_id).first()
            return InviteStatsModel.model_validate(stats) if stats else None

    @staticmethod
    def upsert_stats(
        user_id: str,
        total_invitees: Optional[int] = None,
        total_rebate_amount: Optional[int] = None,
        last_rebate_at: Optional[int] = None,
    ) -> InviteStatsModel:
        """创建或更新邀请统计"""
        with get_db() as db:
            stats = db.query(InviteStats).filter(InviteStats.user_id == user_id).first()

            if stats:
                # 更新现有统计
                if total_invitees is not None:
                    stats.total_invitees = total_invitees
                if total_rebate_amount is not None:
                    stats.total_rebate_amount = total_rebate_amount
                if last_rebate_at is not None:
                    stats.last_rebate_at = last_rebate_at
                stats.updated_at = time.time_ns()
            else:
                # 创建新统计
                stats = InviteStats(
                    user_id=user_id,
                    total_invitees=total_invitees or 0,
                    total_rebate_amount=total_rebate_amount or 0,
                    last_rebate_at=last_rebate_at,
                    updated_at=time.time_ns(),
                )
                db.add(stats)

            db.commit()
            db.refresh(stats)
            return InviteStatsModel.model_validate(stats)

    @staticmethod
    def increment_stats(
        user_id: str,
        rebate_amount: int,
        is_new_invitee: bool = False,
    ) -> InviteStatsModel:
        """增量更新邀请统计"""
        with get_db() as db:
            stats = db.query(InviteStats).filter(InviteStats.user_id == user_id).first()

            if stats:
                # 更新现有统计
                if is_new_invitee:
                    stats.total_invitees += 1
                stats.total_rebate_amount += rebate_amount
                stats.last_rebate_at = time.time_ns()
                stats.updated_at = time.time_ns()
            else:
                # 创建新统计
                stats = InviteStats(
                    user_id=user_id,
                    total_invitees=1 if is_new_invitee else 0,
                    total_rebate_amount=rebate_amount,
                    last_rebate_at=time.time_ns(),
                    updated_at=time.time_ns(),
                )
                db.add(stats)

            db.commit()
            db.refresh(stats)
            return InviteStatsModel.model_validate(stats)

    @staticmethod
    def increment_invitee_count(user_id: str) -> InviteStatsModel:
        """仅增加邀请人数（用户注册时调用）"""
        with get_db() as db:
            stats = db.query(InviteStats).filter(InviteStats.user_id == user_id).first()

            if stats:
                # 更新现有统计
                stats.total_invitees += 1
                stats.updated_at = time.time_ns()
            else:
                # 创建新统计
                stats = InviteStats(
                    user_id=user_id,
                    total_invitees=1,
                    total_rebate_amount=0,
                    last_rebate_at=None,
                    updated_at=time.time_ns(),
                )
                db.add(stats)

            db.commit()
            db.refresh(stats)
            return InviteStatsModel.model_validate(stats)
