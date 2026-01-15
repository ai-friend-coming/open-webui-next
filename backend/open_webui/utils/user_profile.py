"""
用户画像分析模块

基于用户聊天数据异步分析生成用户画像，用于个性化体验优化。
"""

import json
import logging
from typing import Any, Optional

from fastapi import Request

from open_webui.env import USER_PROFILE_MESSAGE_THRESHOLD
from open_webui.models.user_profile import UserProfiles

log = logging.getLogger(__name__)

####################################
# Prompt Templates
####################################

COLD_START_PROMPT = """# Role
你是一位拥有敏锐洞察力的用户体验分析师。你的任务是阅读一段"用户"所发送的消息，从中提炼出用户的个人画像。

# Objective
请分析提供的对话日志，尽可能填充以下 JSON 结构中的字段。

**重要原则：**
1. **实事求是**：只提取对话中明确提到或能强烈推断出的信息。如果不确定，请将该字段留空 (null) 或忽略。
2. **捕捉偏好**：特别关注用户对 AI 回复的反馈（例如用户说"太长了"、"别废话"），这代表了交互偏好。
3. **隐私保护**：不要提取任何个人身份敏感信息（PII），如手机号、具体家庭住址、身份证号，仅关注用户特征和偏好。

# Output Format (严格遵守)
- **必须**输出合法的 JSON 格式，确保可以被 `json.loads()` 正确解析
- **禁止**在 JSON 前后添加任何解释性文字
- **禁止**在字符串值中使用未转义的引号或换行符
- 直接以 `{` 开头，以 `}` 结尾

# Target JSON Schema
{
  "basic_info": {
    "nickname": "String or null",
    "language": "String or null (e.g., 'zh-CN', 'en-US')",
    "location": "String or null (仅城市级别，不要具体地址)",
    "occupation": "String or null",
    "expertise_level": "Novice/Intermediate/Expert or null"
  },
  "preferences": {
    "tone_style": "String or null",
    "response_length": "Brief/Detailed/Auto or null",
    "format_preference": ["String"] or null,
    "sensitivity": ["String"] or null
  },
  "current_context": {
    "primary_goal": "String or null",
    "pain_points": "String or null",
    "emotional_state": "String or null"
  },
  "memorized_entities": [
    {"name": "String", "type": "String", "description": "String"}
  ] or []
}

# Chat Log
{{CHAT_LOGS}}

# Output
"""

INCREMENTAL_PROMPT = """# Role
你是一位拥有敏锐洞察力的用户体验分析师。你的任务是阅读一段"用户"所发送的消息，从中提炼出用户的个人画像。

# Input Data
1. **Existing Profile (旧画像)**: JSON 格式，包含我们目前对用户的了解。
2. **New Chat Log (新对话)**: 用户最近产生的一段对话。

# Instructions
请对比"新对话"与"旧画像"，执行以下更新逻辑：

1. **新增 (Add)**: 如果新对话中包含了旧画像中不存在的信息，请填入。
2. **更新/修正 (Update)**: 如果新对话中的信息与旧画像冲突，**以新对话为准**进行更新。
3. **强化 (Reinforce)**: 如果用户再次表现出相同的偏好，请确认该偏好设置无误。
4. **状态刷新 (Refresh State)**: 更新 `current_context` 中的目标和情绪，使其反映用户当下的状态。

**重要原则：**
- 保留旧画像中仍然有效的信息，不要无故删除。
- **隐私保护**：不要提取任何个人身份敏感信息（PII），如手机号、具体家庭住址、身份证号。

# Output Format (严格遵守)
- **必须**输出合法的 JSON 格式，确保可以被 `json.loads()` 正确解析
- **禁止**在 JSON 前后添加任何解释性文字
- **禁止**在字符串值中使用未转义的引号或换行符
- 直接以 `{` 开头，以 `}` 结尾

# Existing Profile
{{EXISTING_PROFILE_JSON}}

# New Chat Log
{{NEW_CHAT_LOGS}}

# Output
"""


####################################
# Helper Functions
####################################


def format_messages(messages: list) -> str:
    """格式化消息列表为对话日志字符串"""
    formatted = []
    for i, msg in enumerate(messages, 1):
        formatted.append(f"[用户消息 {i}]: {msg}")
    return "\n".join(formatted)


def parse_profile_response(response: Any) -> Optional[dict]:
    """解析 LLM 响应，提取 JSON 格式的用户画像"""
    import re

    try:
        if isinstance(response, dict):
            # 非流式响应
            content = (
                response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
        else:
            # 可能是字符串
            content = str(response)

        # 尝试解析 JSON
        # 移除可能的 markdown 代码块标记
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试用正则提取 JSON 对象
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        log.error(f"Failed to parse profile response as JSON")
        log.debug(f"Response content: {response}")
        return None
    except Exception as e:
        log.error(f"Error parsing profile response: {e}")
        return None


####################################
# Core Functions
####################################


async def update_profile(
    user_id: str, request: Request, model_id: str, user: Any, form_data: dict
) -> None:
    """
    检查用户设置并更新用户画像。

    异步函数，检查用户是否启用数据分析，提取消息并存储，
    当消息数量达到阈值后调用 LLM 分析生成/更新画像。

    Args:
        user_id: 用户 ID
        request: FastAPI Request 对象
        model_id: 用于分析的模型 ID
        user: 用户对象
        form_data: 聊天请求数据，包含 messages
    """
    try:
        # 检查用户是否启用了数据分析功能
        user_settings = user.settings
        if user_settings is None:
            return

        # UserSettings 是 Pydantic 模型，ui 是其属性
        ui_settings = user_settings.ui or {}
        enable_data_analysis = ui_settings.get("enableDataAnalysis", False)

        if not enable_data_analysis:
            return

        # 获取用户最后一条消息
        messages = form_data.get("messages", [])
        if not messages:
            return

        # 找到最后一条 user 角色的消息
        user_messages = [m for m in messages if m.get("role") == "user"]
        if not user_messages:
            return

        last_user_message = user_messages[-1].get("content", "")
        if not last_user_message or not last_user_message.strip():
            return

        # 添加消息到待分析队列
        UserProfiles.append_message(user_id, last_user_message)
        log.debug(f"Added message to user profile queue for user {user_id}")

        # 获取更新后的 profile 数据
        profile_data = UserProfiles.get_by_user_id(user_id)
        if profile_data is None:
            log.debug(f"No profile data found for user {user_id}")
            return

        stored_messages = profile_data.data.get("messages", [])
        message_count = len(stored_messages)

        # 检查阈值
        if message_count < USER_PROFILE_MESSAGE_THRESHOLD:
            log.debug(
                f"User {user_id} has {message_count} messages, "
                f"threshold is {USER_PROFILE_MESSAGE_THRESHOLD}, skipping analysis"
            )
            return

        log.info(
            f"User {user_id} reached threshold ({message_count} messages), "
            f"starting profile analysis"
        )

        # 获取现有画像
        existing_profile = profile_data.profile

        # 调用 LLM 分析
        # 第一次进行 profile 提取
        if existing_profile is None:
            log.info(f"Cold start profile extraction for user {user_id}")
            prompt = COLD_START_PROMPT.replace(
                "{{CHAT_LOGS}}", format_messages(stored_messages)
            )
            new_profile = await call_llm_for_profile(prompt, request, model_id, user)

        # 进行 profile 更新
        else:
            log.info(f"Incremental profile update for user {user_id}")
            prompt = INCREMENTAL_PROMPT.replace(
                "{{EXISTING_PROFILE_JSON}}",
                json.dumps(existing_profile, ensure_ascii=False),
            )
            prompt = prompt.replace(
                "{{NEW_CHAT_LOGS}}", format_messages(stored_messages)
            )
            new_profile = await call_llm_for_profile(prompt, request, model_id, user)

        if new_profile:
            # 更新画像
            UserProfiles.update_profile(user_id, new_profile)
            log.info(f"Successfully updated profile for user {user_id}")

            # 清空消息队列
            UserProfiles.clear_messages(user_id)
            log.debug(f"Cleared message queue for user {user_id}")
        else:
            log.warning(f"Failed to generate profile for user {user_id}")

    except Exception as e:
        log.error(f"Error updating profile for user {user_id}: {e}")

async def call_llm_for_profile(
    prompt: str, request: Request, model_id: str, user: Any
) -> Optional[dict]:
    """
    调用 LLM 生成用户画像。

    使用用户当前请求的模型，走正常计费流程。

    Args:
        prompt: 提示词
        request: FastAPI Request 对象
        model_id: 模型 ID
        user: 用户对象

    Returns:
        解析后的用户画像字典，失败返回 None
    """
    try:
        from open_webui.billing.proxy import chat_with_billing
        from open_webui.utils.chat import generate_chat_completion

        # 构造请求
        form_data = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }

        log.debug(f"Calling LLM for profile analysis with model {model_id}")

        # 调用带计费的 chat_completion
        response = await chat_with_billing(
            generate_chat_completion,
            request,
            form_data,
            user,
            bypass_filter=True,
            chatting_completion=False,
        )

        # 解析 JSON 响应
        return parse_profile_response(response)

    except Exception as e:
        log.error(f"Error calling LLM for profile: {e}")
        return None
