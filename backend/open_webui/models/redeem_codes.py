"""
兑换码模型

支持管理员创建兑换码，用户通过兑换码获得余额充值。
"""

import time
import uuid
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    Boolean,
    Text,
    UniqueConstraint,
    Index,
)

from open_webui.internal.db import Base, get_db


####################
# DB 模型
####################


class RedeemCode(Base):
    """兑换码主表"""

    __tablename__ = "redeem_code"

    id = Column(String, primary_key=True)
    code = Column(String(32), unique=True, nullable=False, index=True)  # 兑换码
    amount = Column(Integer, nullable=False)  # 兑换金额（毫，1元=10000毫）
    max_uses = Column(Integer, nullable=False)  # 最大使用次数
    current_uses = Column(Integer, default=0, nullable=False)  # 当前已使用次数
    start_time = Column(BigInteger, nullable=False)  # 生效时间（秒级时间戳）
    end_time = Column(BigInteger, nullable=False)  # 失效时间（秒级时间戳）
    enabled = Column(Boolean, default=True, nullable=False)  # 是否启用
    created_by = Column(String, nullable=False)  # 创建者用户ID
    remark = Column(Text, nullable=True)  # 备注说明
    created_at = Column(BigInteger, nullable=False)  # 创建时间
    updated_at = Column(BigInteger, nullable=False)  # 更新时间


class RedeemLog(Base):
    """兑换日志表"""

    __tablename__ = "redeem_log"

    id = Column(String, primary_key=True)
    code_id = Column(String, nullable=False, index=True)  # 兑换码ID（外键）
    code = Column(String(32), nullable=False)  # 兑换码（冗余存储，便于查询）
    user_id = Column(String, nullable=False, index=True)  # 兑换用户ID
    amount = Column(Integer, nullable=False)  # 兑换金额（毫）
    balance_before = Column(Integer, nullable=False)  # 兑换前余额（毫）
    balance_after = Column(Integer, nullable=False)  # 兑换后余额（毫）
    created_at = Column(BigInteger, nullable=False, index=True)  # 兑换时间（纳秒级）

    __table_args__ = (
        # 唯一约束：同一用户不能重复使用同一兑换码
        UniqueConstraint("code_id", "user_id", name="uq_code_user"),
    )


####################
# Pydantic 模型
####################


class RedeemCodeModel(BaseModel):
    """兑换码模型"""

    id: str
    code: str
    amount: int  # 毫
    max_uses: int
    current_uses: int
    start_time: int  # 秒级时间戳
    end_time: int  # 秒级时间戳
    enabled: bool
    created_by: str
    remark: Optional[str] = None
    created_at: int
    updated_at: int

    class Config:
        from_attributes = True


class RedeemCodeForm(BaseModel):
    """兑换码创建/更新表单"""

    code: str = Field(..., min_length=6, max_length=32, description="兑换码")
    amount: float = Field(..., gt=0, description="兑换金额（元）")
    max_uses: int = Field(..., gt=0, description="最大使用次数")
    start_time: int = Field(..., description="生效时间（秒级时间戳）")
    end_time: int = Field(..., description="失效时间（秒级时间戳）")
    remark: Optional[str] = Field(None, description="备注说明")


class RedeemLogModel(BaseModel):
    """兑换日志模型"""

    id: str
    code_id: str
    code: str
    user_id: str
    amount: int  # 毫
    balance_before: int  # 毫
    balance_after: int  # 毫
    created_at: int  # 纳秒

    class Config:
        from_attributes = True


####################
# 数据访问层
####################


class RedeemCodesTable:
    """兑换码数据访问层"""

    def create_redeem_code(
        self, user_id: str, form_data: RedeemCodeForm
    ) -> Optional[RedeemCodeModel]:
        """创建兑换码"""
        try:
            with get_db() as db:
                # 元转毫
                amount_in_milli = int(form_data.amount * 10000)

                now = int(time.time())
                redeem_code = RedeemCode(
                    id=str(uuid.uuid4()),
                    code=form_data.code,
                    amount=amount_in_milli,
                    max_uses=form_data.max_uses,
                    current_uses=0,
                    start_time=form_data.start_time,
                    end_time=form_data.end_time,
                    enabled=True,
                    created_by=user_id,
                    remark=form_data.remark,
                    created_at=now,
                    updated_at=now,
                )
                db.add(redeem_code)
                db.commit()
                db.refresh(redeem_code)
                return RedeemCodeModel.model_validate(redeem_code)
        except Exception as e:
            print(f"Error creating redeem code: {e}")
            return None

    def get_redeem_code_by_id(self, code_id: str) -> Optional[RedeemCodeModel]:
        """根据ID查询兑换码"""
        try:
            with get_db() as db:
                code = db.query(RedeemCode).filter_by(id=code_id).first()
                return RedeemCodeModel.model_validate(code) if code else None
        except Exception:
            return None

    def get_redeem_code_by_code(self, code: str) -> Optional[RedeemCodeModel]:
        """根据兑换码查询"""
        try:
            with get_db() as db:
                redeem_code = db.query(RedeemCode).filter_by(code=code).first()
                return (
                    RedeemCodeModel.model_validate(redeem_code)
                    if redeem_code
                    else None
                )
        except Exception:
            return None

    def list_redeem_codes(
        self, status: Optional[str] = None, skip: int = 0, limit: int = 50
    ) -> tuple[list[RedeemCodeModel], int]:
        """
        查询兑换码列表

        Args:
            status: 状态筛选 (all/active/pending/expired/exhausted/disabled)
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            (codes, total)
        """
        try:
            with get_db() as db:
                query = db.query(RedeemCode)

                # 状态筛选
                now = int(time.time())
                if status == "active":
                    query = query.filter(
                        RedeemCode.enabled == True,  # noqa: E712
                        RedeemCode.start_time <= now,
                        RedeemCode.end_time >= now,
                        RedeemCode.current_uses < RedeemCode.max_uses,
                    )
                elif status == "pending":
                    query = query.filter(
                        RedeemCode.enabled == True,  # noqa: E712
                        RedeemCode.start_time > now,
                    )
                elif status == "expired":
                    query = query.filter(
                        RedeemCode.enabled == True,  # noqa: E712
                        RedeemCode.end_time < now,
                    )
                elif status == "exhausted":
                    query = query.filter(
                        RedeemCode.current_uses >= RedeemCode.max_uses
                    )
                elif status == "disabled":
                    query = query.filter(RedeemCode.enabled == False)  # noqa: E712

                total = query.count()
                codes = (
                    query.order_by(RedeemCode.created_at.desc())
                    .offset(skip)
                    .limit(limit)
                    .all()
                )

                return (
                    [RedeemCodeModel.model_validate(c) for c in codes],
                    total,
                )
        except Exception as e:
            print(f"Error listing redeem codes: {e}")
            return [], 0

    def update_redeem_code(
        self, code_id: str, form_data: RedeemCodeForm
    ) -> Optional[RedeemCodeModel]:
        """更新兑换码"""
        try:
            with get_db() as db:
                code = db.query(RedeemCode).filter_by(id=code_id).first()
                if not code:
                    return None

                # 如果已使用次数 > 0，不允许修改金额
                amount_in_milli = int(form_data.amount * 10000)
                if code.current_uses > 0 and amount_in_milli != code.amount:
                    raise ValueError("Cannot modify amount after code has been used")

                code.code = form_data.code
                code.amount = amount_in_milli
                code.max_uses = form_data.max_uses
                code.start_time = form_data.start_time
                code.end_time = form_data.end_time
                code.remark = form_data.remark
                code.updated_at = int(time.time())

                db.commit()
                db.refresh(code)
                return RedeemCodeModel.model_validate(code)
        except Exception as e:
            print(f"Error updating redeem code: {e}")
            return None

    def delete_redeem_code(self, code_id: str) -> bool:
        """删除兑换码（软删除：设置 enabled=False）"""
        try:
            with get_db() as db:
                code = db.query(RedeemCode).filter_by(id=code_id).first()
                if not code:
                    return False

                code.enabled = False
                code.updated_at = int(time.time())
                db.commit()
                return True
        except Exception as e:
            print(f"Error deleting redeem code: {e}")
            return False

    def toggle_enabled(self, code_id: str) -> Optional[RedeemCodeModel]:
        """启用/禁用兑换码"""
        try:
            with get_db() as db:
                code = db.query(RedeemCode).filter_by(id=code_id).first()
                if not code:
                    return None

                code.enabled = not code.enabled
                code.updated_at = int(time.time())
                db.commit()
                db.refresh(code)
                return RedeemCodeModel.model_validate(code)
        except Exception as e:
            print(f"Error toggling redeem code: {e}")
            return None

    def calculate_status(self, code: RedeemCodeModel) -> str:
        """
        计算兑换码状态

        Returns:
            'pending' | 'active' | 'expired' | 'exhausted' | 'disabled'
        """
        if not code.enabled:
            return "disabled"

        now = int(time.time())

        if code.current_uses >= code.max_uses:
            return "exhausted"

        if now < code.start_time:
            return "pending"

        if now > code.end_time:
            return "expired"

        return "active"

    def redeem(self, code: str, user_id: str) -> dict:
        """
        兑换码兑换

        Args:
            code: 兑换码
            user_id: 用户ID

        Returns:
            dict: {"amount": int (毫), "balance_after": int (毫), "message": str}

        Raises:
            ValueError: 验证失败
        """
        from open_webui.models.users import User
        from open_webui.models.billing import RechargeLog
        from sqlalchemy import and_

        with get_db() as db:
            # 1. 行锁获取兑换码
            redeem_code = (
                db.query(RedeemCode).filter_by(code=code).with_for_update().first()
            )

            if not redeem_code:
                raise ValueError("兑换码不存在")

            # 2. 验证兑换码状态
            now = int(time.time())

            if not redeem_code.enabled:
                raise ValueError("兑换码已被禁用")

            if now < redeem_code.start_time:
                raise ValueError("兑换码尚未生效")

            if now > redeem_code.end_time:
                raise ValueError("兑换码已过期")

            if redeem_code.current_uses >= redeem_code.max_uses:
                raise ValueError("兑换码已用尽")

            # 3. 验证用户是否已使用
            existing_log = (
                db.query(RedeemLog)
                .filter(
                    and_(
                        RedeemLog.code_id == redeem_code.id,
                        RedeemLog.user_id == user_id,
                    )
                )
                .first()
            )

            if existing_log:
                raise ValueError("您已使用过该兑换码，每个兑换码每个用户只能使用一次")

            # 4. 行锁获取用户
            user = db.query(User).filter_by(id=user_id).with_for_update().first()
            if not user:
                raise ValueError("用户不存在")

            balance_before = user.balance or 0

            # 5. 增加余额
            user.balance = balance_before + redeem_code.amount

            # 6. 解冻账户（如果余额 >= 100毫）
            if user.balance >= 100:
                user.billing_status = "active"

            # 7. 增加兑换码使用次数
            redeem_code.current_uses += 1
            redeem_code.updated_at = now

            # 8. 记录兑换日志
            redeem_log = RedeemLog(
                id=str(uuid.uuid4()),
                code_id=redeem_code.id,
                code=redeem_code.code,
                user_id=user_id,
                amount=redeem_code.amount,
                balance_before=balance_before,
                balance_after=user.balance,
                created_at=int(time.time() * 1000000000),  # 纳秒
            )
            db.add(redeem_log)

            # 9. 记录充值日志
            recharge_log = RechargeLog(
                id=str(uuid.uuid4()),
                user_id=user_id,
                amount=redeem_code.amount,
                operator_id="system",
                remark=f"兑换码充值: {code}",
                created_at=int(time.time() * 1000000000),  # 纳秒
            )
            db.add(recharge_log)

            # 10. 提交事务
            db.commit()

            print(
                f"兑换码兑换成功: user={user_id} code={code} "
                f"amount={redeem_code.amount / 10000:.2f}元 "
                f"balance={balance_before / 10000:.2f} -> {user.balance / 10000:.2f}元"
            )

            return {
                "amount": redeem_code.amount,
                "balance_after": user.balance,
                "message": f"兑换成功！获得 {redeem_code.amount / 10000:.2f} 元",
            }

    def get_redeem_logs(
        self, code_id: str, skip: int = 0, limit: int = 50
    ) -> list[RedeemLogModel]:
        """查询兑换码的兑换日志"""
        try:
            with get_db() as db:
                logs = (
                    db.query(RedeemLog)
                    .filter_by(code_id=code_id)
                    .order_by(RedeemLog.created_at.desc())
                    .offset(skip)
                    .limit(limit)
                    .all()
                )
                return [RedeemLogModel.model_validate(log) for log in logs]
        except Exception as e:
            print(f"Error getting redeem logs: {e}")
            return []

    def get_user_redeem_logs(
        self, user_id: str, skip: int = 0, limit: int = 50
    ) -> list[RedeemLogModel]:
        """查询用户的兑换记录"""
        try:
            with get_db() as db:
                logs = (
                    db.query(RedeemLog)
                    .filter_by(user_id=user_id)
                    .order_by(RedeemLog.created_at.desc())
                    .offset(skip)
                    .limit(limit)
                    .all()
                )
                return [RedeemLogModel.model_validate(log) for log in logs]
        except Exception as e:
            print(f"Error getting user redeem logs: {e}")
            return []


# 模块级单例
RedeemCodes = RedeemCodesTable()
