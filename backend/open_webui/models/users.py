import time
import logging
from typing import Optional

from open_webui.internal.db import Base, JSONField, get_db


from open_webui.env import DATABASE_USER_ACTIVE_STATUS_UPDATE_INTERVAL
from open_webui.models.chats import Chats
from open_webui.models.groups import Groups
from open_webui.utils.misc import throttle
from open_webui.utils.invite import generate_unique_invite_code


from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, String, Text, Date, Integer, func
from sqlalchemy import or_

import datetime

log = logging.getLogger(__name__)

####################
# User DB Schema
####################


class User(Base):
    __tablename__ = "user"

    id = Column(String, primary_key=True)
    name = Column(String)

    email = Column(String, nullable=True)
    phone = Column(String(20), nullable=True)
    username = Column(String(50), nullable=True)

    role = Column(String)
    profile_image_url = Column(Text)

    bio = Column(Text, nullable=True)
    gender = Column(Text, nullable=True)
    date_of_birth = Column(Date, nullable=True)

    info = Column(JSONField, nullable=True)
    settings = Column(JSONField, nullable=True)

    api_key = Column(String, nullable=True, unique=True)
    oauth_sub = Column(Text, unique=True)

    last_active_at = Column(BigInteger)

    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)

    # 计费相关字段（以毫为单位存储，1元=10000毫）
    balance = Column(Integer, default=0, nullable=False)  # 账户余额（毫，1元=10000毫）
    total_consumed = Column(Integer, default=0, nullable=False)  # 累计消费（毫，1元=10000毫）
    billing_status = Column(String(20), default="active", nullable=False)  # active/frozen

    # 邀请相关字段
    invite_code = Column(String(8), unique=True, nullable=True, index=True)  # 用户专属邀请码
    invited_by = Column(String, nullable=True, index=True)  # 邀请人的 user_id


class UserSettings(BaseModel):
    ui: Optional[dict] = {}
    model_config = ConfigDict(extra="allow")
    pass


class UserModel(BaseModel):
    id: str
    name: str

    email: Optional[str] = None
    phone: Optional[str] = None
    username: Optional[str] = None

    role: str = "pending"
    profile_image_url: str

    bio: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None

    info: Optional[dict] = None
    settings: Optional[UserSettings] = None

    api_key: Optional[str] = None
    oauth_sub: Optional[str] = None

    last_active_at: int  # timestamp in epoch
    updated_at: int  # timestamp in epoch
    created_at: int  # timestamp in epoch

    # 计费相关字段（以毫为单位，1元=10000毫）
    balance: Optional[int] = 0  # 毫
    total_consumed: Optional[int] = 0  # 毫
    billing_status: Optional[str] = "active"
    total_recharged: Optional[int] = 0  # 累计充值金额（毫）

    # 邀请相关字段
    invite_code: Optional[str] = None  # 用户专属邀请码
    invited_by: Optional[str] = None  # 邀请人的 user_id

    model_config = ConfigDict(from_attributes=True)


####################
# Forms
####################


class UpdateProfileForm(BaseModel):
    profile_image_url: str
    name: str
    bio: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None


class UserListResponse(BaseModel):
    users: list[UserModel]
    total: int


class UserInfoResponse(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str


class UserIdNameResponse(BaseModel):
    id: str
    name: str


class UserInfoListResponse(BaseModel):
    users: list[UserInfoResponse]
    total: int


class UserIdNameListResponse(BaseModel):
    users: list[UserIdNameResponse]
    total: int


class UserResponse(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    profile_image_url: str


class UserNameResponse(BaseModel):
    id: str
    name: str
    role: str
    profile_image_url: str


class UserRoleUpdateForm(BaseModel):
    id: str
    role: str


class UserUpdateForm(BaseModel):
    role: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    profile_image_url: str
    password: Optional[str] = None


class UsersTable:
    def insert_new_user(
        self,
        id: str,
        name: str,
        email: Optional[str] = None,
        profile_image_url: str = "/user.png",
        role: str = "pending",
        oauth_sub: Optional[str] = None,
        phone: Optional[str] = None,
        invited_by_code: Optional[str] = None,
    ) -> Optional[UserModel]:
        with get_db() as db:
            # 验证邀请码并获取邀请人ID
            invited_by = None
            if invited_by_code:
                inviter = db.query(User).filter(User.invite_code == invited_by_code).first()
                if inviter:
                    invited_by = inviter.id
                    log.info(f"User {id} invited by {invited_by} (code: {invited_by_code})")
                else:
                    log.warning(f"Invalid invite code: {invited_by_code}")

            # 生成唯一邀请码
            def check_invite_code_exists(code: str) -> bool:
                return db.query(User).filter(User.invite_code == code).first() is not None

            invite_code = generate_unique_invite_code(check_invite_code_exists)

            user = UserModel(
                **{
                    "id": id,
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "role": role,
                    "profile_image_url": profile_image_url,
                    # AI-Friend, 默认启用记忆功能
                    "settings": {"ui": {"memory": True}},
                    "last_active_at": int(time.time()),
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                    "oauth_sub": oauth_sub,
                    "invite_code": invite_code,
                    "invited_by": invited_by,
                }
            )
            result = User(**user.model_dump(exclude={"total_recharged"}))
            db.add(result)
            db.commit()
            db.refresh(result)
            if result:
                # 如果有邀请人，增加邀请人的邀请统计
                if invited_by:
                    try:
                        from open_webui.models.invite import InviteStatsTable
                        InviteStatsTable.increment_invitee_count(invited_by)
                        log.info(f"Incremented invite count for inviter {invited_by}")
                    except Exception as e:
                        log.error(f"Failed to increment invite count for inviter {invited_by}: {e}")
                return user
            else:
                return None

    def get_user_by_id(self, id: str) -> Optional[UserModel]:
        try:
            with get_db() as db:
                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_user_by_api_key(self, api_key: str) -> Optional[UserModel]:
        try:
            with get_db() as db:
                user = db.query(User).filter_by(api_key=api_key).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_user_by_email(self, email: str) -> Optional[UserModel]:
        try:
            with get_db() as db:
                user = db.query(User).filter_by(email=email).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_user_by_phone(self, phone: str) -> Optional[UserModel]:
        try:
            with get_db() as db:
                user = db.query(User).filter_by(phone=phone).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_user_by_oauth_sub(self, sub: str) -> Optional[UserModel]:
        try:
            with get_db() as db:
                user = db.query(User).filter_by(oauth_sub=sub).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_users(
        self,
        filter: Optional[dict] = None,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        from open_webui.models.billing import PaymentOrder

        with get_db() as db:
            # 创建子查询计算每个用户的充值总额
            recharge_subquery = (
                db.query(
                    PaymentOrder.user_id,
                    func.sum(PaymentOrder.amount).label('total_recharged')
                )
                .filter(PaymentOrder.status == 'paid')
                .group_by(PaymentOrder.user_id)
                .subquery()
            )

            # 左连接子查询
            query = db.query(User).outerjoin(
                recharge_subquery, User.id == recharge_subquery.c.user_id
            )
            query = query.add_columns(
                func.coalesce(recharge_subquery.c.total_recharged, 0).label('total_recharged')
            )

            if filter:
                query_key = filter.get("query")
                if query_key:
                    query = query.filter(
                        or_(
                            User.name.ilike(f"%{query_key}%"),
                            User.email.ilike(f"%{query_key}%"),
                            User.phone.ilike(f"%{query_key}%"),
                        )
                    )

                order_by = filter.get("order_by")
                direction = filter.get("direction")

                if order_by == "name":
                    if direction == "asc":
                        query = query.order_by(User.name.asc())
                    else:
                        query = query.order_by(User.name.desc())
                elif order_by == "email":
                    if direction == "asc":
                        query = query.order_by(User.email.asc())
                    else:
                        query = query.order_by(User.email.desc())

                elif order_by == "created_at":
                    if direction == "asc":
                        query = query.order_by(User.created_at.asc())
                    else:
                        query = query.order_by(User.created_at.desc())

                elif order_by == "last_active_at":
                    if direction == "asc":
                        query = query.order_by(User.last_active_at.asc())
                    else:
                        query = query.order_by(User.last_active_at.desc())

                elif order_by == "updated_at":
                    if direction == "asc":
                        query = query.order_by(User.updated_at.asc())
                    else:
                        query = query.order_by(User.updated_at.desc())
                elif order_by == "role":
                    if direction == "asc":
                        query = query.order_by(User.role.asc())
                    else:
                        query = query.order_by(User.role.desc())
                elif order_by == "balance":
                    if direction == "asc":
                        query = query.order_by(User.balance.asc())
                    else:
                        query = query.order_by(User.balance.desc())
                elif order_by == "total_recharged":
                    if direction == "asc":
                        query = query.order_by(func.coalesce(recharge_subquery.c.total_recharged, 0).asc())
                    else:
                        query = query.order_by(func.coalesce(recharge_subquery.c.total_recharged, 0).desc())

            else:
                query = query.order_by(User.created_at.desc())

            if skip:
                query = query.offset(skip)
            if limit:
                query = query.limit(limit)

            results = query.all()
            users = []
            for row in results:
                user_obj = row[0]  # User 对象
                total_recharged = row[1] if len(row) > 1 else 0  # total_recharged 值
                user_model = UserModel.model_validate(user_obj)
                user_model.total_recharged = total_recharged
                users.append(user_model)

            return {
                "users": users,
                "total": db.query(User).count(),
            }

    def get_users_by_user_ids(self, user_ids: list[str]) -> list[UserModel]:
        with get_db() as db:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
            return [UserModel.model_validate(user) for user in users]

    def get_num_users(self) -> Optional[int]:
        with get_db() as db:
            return db.query(User).count()

    def has_users(self) -> bool:
        with get_db() as db:
            return db.query(db.query(User).exists()).scalar()

    def get_first_user(self) -> UserModel:
        try:
            with get_db() as db:
                user = db.query(User).order_by(User.created_at).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_user_webhook_url_by_id(self, id: str) -> Optional[str]:
        try:
            with get_db() as db:
                user = db.query(User).filter_by(id=id).first()

                if user.settings is None:
                    return None
                else:
                    return (
                        user.settings.get("ui", {})
                        .get("notifications", {})
                        .get("webhook_url", None)
                    )
        except Exception:
            return None

    def update_user_role_by_id(self, id: str, role: str) -> Optional[UserModel]:
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update({"role": role})
                db.commit()
                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def update_user_profile_image_url_by_id(
        self, id: str, profile_image_url: str
    ) -> Optional[UserModel]:
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update(
                    {"profile_image_url": profile_image_url}
                )
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    @throttle(DATABASE_USER_ACTIVE_STATUS_UPDATE_INTERVAL)
    def update_user_last_active_by_id(self, id: str) -> Optional[UserModel]:
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update(
                    {"last_active_at": int(time.time())}
                )
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def update_user_oauth_sub_by_id(
        self, id: str, oauth_sub: str
    ) -> Optional[UserModel]:
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update({"oauth_sub": oauth_sub})
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def update_user_by_id(self, id: str, updated: dict) -> Optional[UserModel]:
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update(updated)
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
                # return UserModel(**user.dict())
        except Exception as e:
            print(e)
            return None

    def update_user_settings_by_id(self, id: str, updated: dict) -> Optional[UserModel]:
        try:
            with get_db() as db:
                user_settings = db.query(User).filter_by(id=id).first().settings

                if user_settings is None:
                    user_settings = {}

                user_settings.update(updated)

                db.query(User).filter_by(id=id).update({"settings": user_settings})
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def delete_user_by_id(self, id: str) -> bool:
        try:
            # Remove User from Groups
            Groups.remove_user_from_all_groups(id)

            # Delete User Chats
            result = Chats.delete_chats_by_user_id(id)
            if result:
                with get_db() as db:
                    # Delete User
                    db.query(User).filter_by(id=id).delete()
                    db.commit()

                return True
            else:
                return False
        except Exception:
            return False

    def update_user_api_key_by_id(self, id: str, api_key: str) -> bool:
        try:
            with get_db() as db:
                result = db.query(User).filter_by(id=id).update({"api_key": api_key})
                db.commit()
                return True if result == 1 else False
        except Exception:
            return False

    def get_user_api_key_by_id(self, id: str) -> Optional[str]:
        try:
            with get_db() as db:
                user = db.query(User).filter_by(id=id).first()
                return user.api_key
        except Exception:
            return None

    def get_valid_user_ids(self, user_ids: list[str]) -> list[str]:
        with get_db() as db:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
            return [user.id for user in users]

    def get_super_admin_user(self) -> Optional[UserModel]:
        with get_db() as db:
            user = db.query(User).filter_by(role="admin").first()
            if user:
                return UserModel.model_validate(user)
            else:
                return None

    def get_user_by_invite_code(self, invite_code: str) -> Optional[UserModel]:
        """根据邀请码查找用户"""
        try:
            with get_db() as db:
                user = db.query(User).filter(User.invite_code == invite_code).first()
                return UserModel.model_validate(user) if user else None
        except Exception:
            return None

    def get_invitees_by_inviter_id(
        self, inviter_id: str, skip: int = 0, limit: int = 50
    ) -> dict:
        """获取邀请人的被邀请用户列表"""
        with get_db() as db:
            query = db.query(User).filter(User.invited_by == inviter_id)
            query = query.order_by(User.created_at.desc())

            total = query.count()
            users = query.offset(skip).limit(limit).all()

            return {
                "users": [UserModel.model_validate(user) for user in users],
                "total": total,
            }


Users = UsersTable()
