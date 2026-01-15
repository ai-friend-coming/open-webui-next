import time
from typing import Optional

from open_webui.internal.db import Base, JSONField, get_db
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, String

####################
# DataforPersonalizedExperience DB Schema
####################


class DataforPersonalizedExperience(Base):
    __tablename__ = "data_for_personalized_experience"

    id = Column(String, primary_key=True)  # 与 user.id 相同
    data = Column(JSONField, default={"messages": []})  # 待分析的消息
    profile = Column(JSONField, nullable=True)  # 用户画像
    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)


####################
# Pydantic Models
####################


class UserProfileModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    data: dict
    profile: Optional[dict] = None
    updated_at: int
    created_at: int


####################
# UserProfileTable
####################


class UserProfileTable:
    def get_by_user_id(self, user_id: str) -> Optional[UserProfileModel]:
        """获取用户画像数据"""
        try:
            with get_db() as db:
                profile = (
                    db.query(DataforPersonalizedExperience)
                    .filter_by(id=user_id)
                    .first()
                )
                if profile:
                    return UserProfileModel.model_validate(profile)
                return None
        except Exception as e:
            print(f"Error getting user profile: {e}")
            return None

    def create_or_get(self, user_id: str) -> Optional[UserProfileModel]:
        """获取或创建用户画像数据"""
        try:
            with get_db() as db:
                profile = (
                    db.query(DataforPersonalizedExperience)
                    .filter_by(id=user_id)
                    .first()
                )
                if profile:
                    return UserProfileModel.model_validate(profile)

                # 创建新记录
                now = int(time.time())
                new_profile = DataforPersonalizedExperience(
                    id=user_id,
                    data={"messages": []},
                    profile=None,
                    updated_at=now,
                    created_at=now,
                )
                db.add(new_profile)
                db.commit()
                db.refresh(new_profile)
                return UserProfileModel.model_validate(new_profile)
        except Exception as e:
            print(f"Error creating user profile: {e}")
            return None

    def append_message(self, user_id: str, message: str) -> Optional[UserProfileModel]:
        """追加消息到待分析队列"""
        try:
            with get_db() as db:
                profile = (
                    db.query(DataforPersonalizedExperience)
                    .filter_by(id=user_id)
                    .first()
                )

                now = int(time.time())

                if profile is None:
                    # 创建新记录
                    new_profile = DataforPersonalizedExperience(
                        id=user_id,
                        data={"messages": [message]},
                        profile=None,
                        updated_at=now,
                        created_at=now,
                    )
                    db.add(new_profile)
                    db.commit()
                    db.refresh(new_profile)
                    return UserProfileModel.model_validate(new_profile)
                else:
                    # 追加消息
                    data = profile.data or {"messages": []}
                    messages = data.get("messages", [])
                    messages.append(message)
                    data["messages"] = messages

                    db.query(DataforPersonalizedExperience).filter_by(
                        id=user_id
                    ).update({"data": data, "updated_at": now})
                    db.commit()

                    profile = (
                        db.query(DataforPersonalizedExperience)
                        .filter_by(id=user_id)
                        .first()
                    )
                    return UserProfileModel.model_validate(profile)
        except Exception as e:
            print(f"Error appending message: {e}")
            return None

    def update_profile(
        self, user_id: str, profile: dict
    ) -> Optional[UserProfileModel]:
        """更新用户画像"""
        try:
            with get_db() as db:
                now = int(time.time())
                db.query(DataforPersonalizedExperience).filter_by(id=user_id).update(
                    {"profile": profile, "updated_at": now}
                )
                db.commit()

                result = (
                    db.query(DataforPersonalizedExperience)
                    .filter_by(id=user_id)
                    .first()
                )
                if result:
                    return UserProfileModel.model_validate(result)
                return None
        except Exception as e:
            print(f"Error updating profile: {e}")
            return None

    def clear_messages(self, user_id: str) -> Optional[UserProfileModel]:
        """清空消息队列"""
        try:
            with get_db() as db:
                now = int(time.time())
                db.query(DataforPersonalizedExperience).filter_by(id=user_id).update(
                    {"data": {"messages": []}, "updated_at": now}
                )
                db.commit()

                result = (
                    db.query(DataforPersonalizedExperience)
                    .filter_by(id=user_id)
                    .first()
                )
                if result:
                    return UserProfileModel.model_validate(result)
                return None
        except Exception as e:
            print(f"Error clearing messages: {e}")
            return None


UserProfiles = UserProfileTable()
