"""
签到系统数据模型

支持每日签到、正态分布奖励金额
"""

import time
import uuid
from typing import Optional
from datetime import datetime, date

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, String, Integer, BigInteger, Date, UniqueConstraint, func

from open_webui.internal.db import Base, get_db


####################
# SignInLog DB Schema
####################


class SignInLog(Base):
    """签到记录表"""

    __tablename__ = "sign_in_log"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # 奖励金额（毫，1元=10000毫）
    sign_in_date = Column(Date, nullable=False)  # 签到日期（用于唯一性约束）
    created_at = Column(BigInteger, nullable=False, index=True)

    __table_args__ = (
        # 确保每个用户每天只能签到一次
        UniqueConstraint('user_id', 'sign_in_date', name='uq_user_sign_in_date'),
    )


####################
# Pydantic Models
####################


class SignInLogModel(BaseModel):
    """签到记录 Pydantic 模型"""

    id: str
    user_id: str
    amount: int  # 毫
    sign_in_date: date
    created_at: int

    model_config = ConfigDict(from_attributes=True)


####################
# Data Access Layer
####################


class SignInLogTable:
    """签到记录数据访问层"""

    def has_signed_today(self, user_id: str) -> bool:
        """检查用户今天是否已签到"""
        try:
            today = date.today()
            with get_db() as db:
                exists = (
                    db.query(SignInLog)
                    .filter_by(user_id=user_id, sign_in_date=today)
                    .first()
                )
                return exists is not None
        except Exception:
            return False

    def create(self, user_id: str, amount: int) -> SignInLogModel:
        """创建签到记录"""
        with get_db() as db:
            today = date.today()
            now = int(time.time_ns())

            log = SignInLog(
                id=str(uuid.uuid4()),
                user_id=user_id,
                amount=amount,
                sign_in_date=today,
                created_at=now,
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            return SignInLogModel.model_validate(log)

    def get_by_user_id(
        self, user_id: str, limit: int = 30, offset: int = 0
    ) -> list[SignInLogModel]:
        """获取用户签到记录"""
        with get_db() as db:
            logs = (
                db.query(SignInLog)
                .filter_by(user_id=user_id)
                .order_by(SignInLog.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [SignInLogModel.model_validate(log) for log in logs]

    def get_user_stats(self, user_id: str) -> dict:
        """获取用户签到统计"""
        with get_db() as db:
            # 总签到天数
            total_days = db.query(SignInLog).filter_by(user_id=user_id).count()

            # 累计奖励金额
            total_amount = (
                db.query(func.sum(SignInLog.amount))
                .filter_by(user_id=user_id)
                .scalar() or 0
            )

            # 本月签到天数
            now = datetime.now()
            first_day_of_month = date(now.year, now.month, 1)
            month_days = (
                db.query(SignInLog)
                .filter(
                    SignInLog.user_id == user_id,
                    SignInLog.sign_in_date >= first_day_of_month
                )
                .count()
            )

            return {
                "total_days": total_days,
                "total_amount": total_amount,  # 毫
                "month_days": month_days,
            }

    def get_continuous_days(self, user_id: str) -> int:
        """获取连续签到天数"""
        with get_db() as db:
            # 获取最近30天的签到记录
            logs = (
                db.query(SignInLog.sign_in_date)
                .filter_by(user_id=user_id)
                .order_by(SignInLog.sign_in_date.desc())
                .limit(30)
                .all()
            )

            if not logs:
                return 0

            # 计算连续天数
            continuous_days = 1
            today = date.today()
            expected_date = today

            for log in logs:
                log_date = log[0] if isinstance(log, tuple) else log.sign_in_date
                if log_date == expected_date:
                    if log_date != today:
                        continuous_days += 1
                    from datetime import timedelta
                    expected_date = expected_date - timedelta(days=1)
                else:
                    break

            return continuous_days


# 单例实例
SignInLogs = SignInLogTable()
