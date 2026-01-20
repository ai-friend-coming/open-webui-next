import logging
from typing import Optional
import base64
import io


from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse, FileResponse
from pydantic import BaseModel


from open_webui.models.auths import Auths
from open_webui.models.oauth_sessions import OAuthSessions

from open_webui.models.groups import Groups
from open_webui.models.chats import Chats
from open_webui.models.users import (
    UserModel,
    UserListResponse,
    UserInfoListResponse,
    UserIdNameListResponse,
    UserRoleUpdateForm,
    Users,
    UserSettings,
    UserUpdateForm,
)


from open_webui.socket.main import (
    get_active_status_by_user_id,
    get_active_user_ids,
    get_user_active_status,
)
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import SRC_LOG_LEVELS, STATIC_DIR


from open_webui.utils.auth import get_admin_user, get_password_hash, get_verified_user
from open_webui.utils.access_control import get_permissions, has_permission


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


############################
# GetActiveUsers
############################


@router.get("/active")
async def get_active_users(
    user=Depends(get_verified_user),
):
    """
    Get a list of active users.
    """
    return {
        "user_ids": get_active_user_ids(),
    }


############################
# GetUsers
############################


PAGE_ITEM_COUNT = 500


@router.get("/", response_model=UserListResponse)
async def get_users(
    query: Optional[str] = None,
    order_by: Optional[str] = None,
    direction: Optional[str] = None,
    page: Optional[int] = 1,
    user=Depends(get_admin_user),
):
    limit = PAGE_ITEM_COUNT

    page = max(1, page)
    skip = (page - 1) * limit

    filter = {}
    if query:
        filter["query"] = query
    if order_by:
        filter["order_by"] = order_by
    if direction:
        filter["direction"] = direction

    return Users.get_users(filter=filter, skip=skip, limit=limit)


@router.get("/all", response_model=UserInfoListResponse)
async def get_all_users(
    user=Depends(get_admin_user),
):
    return Users.get_users()


@router.get("/search", response_model=UserIdNameListResponse)
async def search_users(
    query: Optional[str] = None,
    user=Depends(get_verified_user),
):
    limit = PAGE_ITEM_COUNT

    page = 1  # Always return the first page for search
    skip = (page - 1) * limit

    filter = {}
    if query:
        filter["query"] = query

    return Users.get_users(filter=filter, skip=skip, limit=limit)


############################
# User Groups
############################


@router.get("/groups")
async def get_user_groups(user=Depends(get_verified_user)):
    return Groups.get_groups_by_member_id(user.id)


############################
# User Permissions
############################


@router.get("/permissions")
async def get_user_permissisions(request: Request, user=Depends(get_verified_user)):
    user_permissions = get_permissions(
        user.id, request.app.state.config.USER_PERMISSIONS
    )

    return user_permissions


############################
# User Default Permissions
############################
class WorkspacePermissions(BaseModel):
    models: bool = False
    knowledge: bool = False
    prompts: bool = False
    tools: bool = False


class SharingPermissions(BaseModel):
    public_models: bool = True
    public_knowledge: bool = True
    public_prompts: bool = True
    public_tools: bool = True
    public_notes: bool = True


class ChatPermissions(BaseModel):
    controls: bool = True
    valves: bool = True
    system_prompt: bool = True
    params: bool = True
    file_upload: bool = True
    delete: bool = True
    delete_message: bool = True
    continue_response: bool = True
    regenerate_response: bool = True
    rate_response: bool = True
    edit: bool = True
    share: bool = True
    export: bool = True
    stt: bool = True
    tts: bool = True
    call: bool = True
    multiple_models: bool = True
    temporary: bool = True
    temporary_enforced: bool = False


class FeaturesPermissions(BaseModel):
    direct_tool_servers: bool = False
    web_search: bool = True
    image_generation: bool = True
    code_interpreter: bool = True
    notes: bool = True


class UserPermissions(BaseModel):
    workspace: WorkspacePermissions
    sharing: SharingPermissions
    chat: ChatPermissions
    features: FeaturesPermissions


@router.get("/default/permissions", response_model=UserPermissions)
async def get_default_user_permissions(request: Request, user=Depends(get_admin_user)):
    return {
        "workspace": WorkspacePermissions(
            **request.app.state.config.USER_PERMISSIONS.get("workspace", {})
        ),
        "sharing": SharingPermissions(
            **request.app.state.config.USER_PERMISSIONS.get("sharing", {})
        ),
        "chat": ChatPermissions(
            **request.app.state.config.USER_PERMISSIONS.get("chat", {})
        ),
        "features": FeaturesPermissions(
            **request.app.state.config.USER_PERMISSIONS.get("features", {})
        ),
    }


@router.post("/default/permissions")
async def update_default_user_permissions(
    request: Request, form_data: UserPermissions, user=Depends(get_admin_user)
):
    request.app.state.config.USER_PERMISSIONS = form_data.model_dump()
    return request.app.state.config.USER_PERMISSIONS


############################
# GetUserSettingsBySessionUser
############################


@router.get("/user/settings", response_model=Optional[UserSettings])
async def get_user_settings_by_session_user(user=Depends(get_verified_user)):
    user = Users.get_user_by_id(user.id)
    if user:
        return user.settings
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# UpdateUserSettingsBySessionUser
############################


@router.post("/user/settings/update", response_model=UserSettings)
async def update_user_settings_by_session_user(
    request: Request, form_data: UserSettings, user=Depends(get_verified_user)
):
    updated_user_settings = form_data.model_dump()
    if (
        user.role != "admin"
        and "toolServers" in updated_user_settings.get("ui").keys()
        and not has_permission(
            user.id,
            "features.direct_tool_servers",
            request.app.state.config.USER_PERMISSIONS,
        )
    ):
        # If the user is not an admin and does not have permission to use tool servers, remove the key
        updated_user_settings["ui"].pop("toolServers", None)

    user = Users.update_user_settings_by_id(user.id, updated_user_settings)
    if user:
        return user.settings
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# GetUserInfoBySessionUser
############################


@router.get("/user/info", response_model=Optional[dict])
async def get_user_info_by_session_user(user=Depends(get_verified_user)):
    user = Users.get_user_by_id(user.id)
    if user:
        return user.info
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# UpdateUserInfoBySessionUser
############################


@router.post("/user/info/update", response_model=Optional[dict])
async def update_user_info_by_session_user(
    form_data: dict, user=Depends(get_verified_user)
):
    user = Users.get_user_by_id(user.id)
    if user:
        if user.info is None:
            user.info = {}

        user = Users.update_user_by_id(user.id, {"info": {**user.info, **form_data}})
        if user:
            return user.info
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.USER_NOT_FOUND,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# GetUserById
############################


class UserResponse(BaseModel):
    name: str
    profile_image_url: str
    active: Optional[bool] = None


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(user_id: str, user=Depends(get_verified_user)):
    # Check if user_id is a shared chat
    # If it is, get the user_id from the chat
    if user_id.startswith("shared-"):
        chat_id = user_id.replace("shared-", "")
        chat = Chats.get_chat_by_id(chat_id)
        if chat:
            user_id = chat.user_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.USER_NOT_FOUND,
            )

    user = Users.get_user_by_id(user_id)

    if user:
        return UserResponse(
            **{
                "name": user.name,
                "profile_image_url": user.profile_image_url,
                "active": get_active_status_by_user_id(user_id),
            }
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


@router.get("/{user_id}/oauth/sessions", response_model=Optional[dict])
async def get_user_oauth_sessions_by_id(user_id: str, user=Depends(get_admin_user)):
    sessions = OAuthSessions.get_sessions_by_user_id(user_id)
    if sessions and len(sessions) > 0:
        return sessions
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# GetUserProfileImageById
############################


@router.get("/{user_id}/profile/image")
async def get_user_profile_image_by_id(user_id: str, user=Depends(get_verified_user)):
    user = Users.get_user_by_id(user_id)
    if user:
        if user.profile_image_url:
            # check if it's url or base64
            if user.profile_image_url.startswith("http"):
                return Response(
                    status_code=status.HTTP_302_FOUND,
                    headers={"Location": user.profile_image_url},
                )
            elif user.profile_image_url.startswith("data:image"):
                try:
                    header, base64_data = user.profile_image_url.split(",", 1)
                    image_data = base64.b64decode(base64_data)
                    image_buffer = io.BytesIO(image_data)

                    return StreamingResponse(
                        image_buffer,
                        media_type="image/png",
                        headers={"Content-Disposition": "inline; filename=image.png"},
                    )
                except Exception as e:
                    pass
        return FileResponse(f"{STATIC_DIR}/user.png")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# GetUserActiveStatusById
############################


@router.get("/{user_id}/active", response_model=dict)
async def get_user_active_status_by_id(user_id: str, user=Depends(get_verified_user)):
    return {
        "active": get_user_active_status(user_id),
    }


############################
# UpdateUserById
############################


@router.post("/{user_id}/update", response_model=Optional[UserModel])
async def update_user_by_id(
    user_id: str,
    form_data: UserUpdateForm,
    session_user=Depends(get_admin_user),
):
    # Prevent modification of the primary admin user by other admins
    try:
        first_user = Users.get_first_user()
        if first_user:
            if user_id == first_user.id:
                if session_user.id != user_id:
                    # If the user trying to update is the primary admin, and they are not the primary admin themselves
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=ERROR_MESSAGES.ACTION_PROHIBITED,
                    )

                if form_data.role != "admin":
                    # If the primary admin is trying to change their own role, prevent it
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=ERROR_MESSAGES.ACTION_PROHIBITED,
                    )

    except Exception as e:
        log.error(f"Error checking primary admin status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify primary admin status.",
        )

    user = Users.get_user_by_id(user_id)

    if user:
        # 验证邮箱是否被其他用户使用
        email = form_data.email.lower().strip() if form_data.email else None
        if email and email != user.email:
            email_user = Users.get_user_by_email(email)
            if email_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.EMAIL_TAKEN,
                )

        # 验证手机号是否被其他用户使用
        phone = form_data.phone.strip() if form_data.phone else None
        if phone and phone != user.phone:
            phone_user = Users.get_user_by_phone(phone)
            if phone_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone number already registered.",
                )

        if form_data.password:
            hashed = get_password_hash(form_data.password)
            log.debug(f"hashed: {hashed}")
            Auths.update_user_password_by_id(user_id, hashed)

        # 更新 Auth 表中的 email 和 phone
        if email:
            Auths.update_email_by_id(user_id, email)
        if phone:
            Auths.update_phone_by_id(user_id, phone)

        updated_user = Users.update_user_by_id(
            user_id,
            {
                "role": form_data.role,
                "name": form_data.name,
                "email": email,
                "phone": phone,
                "profile_image_url": form_data.profile_image_url,
            },
        )

        if updated_user:
            return updated_user

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=ERROR_MESSAGES.USER_NOT_FOUND,
    )


############################
# DeleteUserById
############################


@router.delete("/{user_id}", response_model=bool)
async def delete_user_by_id(user_id: str, user=Depends(get_admin_user)):
    # Prevent deletion of the primary admin user
    try:
        first_user = Users.get_first_user()
        if first_user and user_id == first_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ERROR_MESSAGES.ACTION_PROHIBITED,
            )
    except Exception as e:
        log.error(f"Error checking primary admin status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify primary admin status.",
        )

    if user.id != user_id:
        result = Auths.delete_auth_by_id(user_id)

        if result:
            return True

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DELETE_USER_ERROR,
        )

    # Prevent self-deletion
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=ERROR_MESSAGES.ACTION_PROHIBITED,
    )


############################
# GetUserGroupsById
############################


@router.get("/{user_id}/groups")
async def get_user_groups_by_id(user_id: str, user=Depends(get_admin_user)):
    return Groups.get_groups_by_member_id(user_id)


############################
# Invite System APIs
############################


@router.get("/invite/info")
async def get_invite_info(user=Depends(get_verified_user)):
    """
    获取当前用户的邀请信息

    返回：
    - invite_code: 邀请码
    - total_invitees: 总邀请人数
    - total_rebate_amount: 累计返现金额（毫）
    - rebate_rate: 返现比例（百分比）
    """
    from open_webui.billing.invite import get_invite_info as get_info

    info = get_info(user.id)
    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite info not found",
        )

    return info


@router.get("/invite/rebate-logs")
async def get_rebate_logs(
    skip: int = 0,
    limit: int = 50,
    user=Depends(get_verified_user)
):
    """
    获取当前用户的返现记录列表

    参数：
    - skip: 跳过条数
    - limit: 每页数量

    返回：
    - logs: 返现记录列表
    - total: 总记录数
    """
    from open_webui.models.invite import InviteRebateLogs

    logs = InviteRebateLogs.get_rebate_logs_by_inviter(user.id, skip, limit)
    total = InviteRebateLogs.count_rebate_logs_by_inviter(user.id)

    return {
        "logs": logs,
        "total": total,
    }


@router.get("/invite/invitees")
async def get_invitees(
    skip: int = 0,
    limit: int = 50,
    user=Depends(get_verified_user)
):
    """
    获取当前用户邀请的用户列表

    参数：
    - skip: 跳过条数
    - limit: 每页数量

    返回：
    - users: 用户列表
    - total: 总人数
    """
    result = Users.get_invitees_by_inviter_id(user.id, skip, limit)
    return result
