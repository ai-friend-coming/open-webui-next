from typing import Dict, List, Optional, Tuple, Sequence, Any, Union
import json
import re
import os
from contextlib import contextmanager
import time
from logging import getLogger

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from open_webui.models.chats import Chats
from open_webui.tasks import create_task
from open_webui.utils.chat_error_boundary import chat_error_boundary, CustmizedError
from open_webui.routers.openai import generate_chat_completion as generate_openai_chat_completion
from open_webui.utils.perf_logger import ChatPerfLogger

from open_webui.env import (
    CHAT_DEBUG_FLAG,
    SUMMARY_TOKEN_THRESHOLD_DEFAULT,
    INITIAL_SUMMARY_TOKEN_WINDOW_DEFAULT,
    COLD_START_TOKEN_WINDOW_DEFAULT,
    ROLLING_SUMMARY_TOKEN_THRESHOLD_DEFAULT,
)

from open_webui.utils.misc import merge_consecutive_messages

# Import for calling main chat API
from fastapi import Request

log = getLogger(__name__)

# --- Constants & Prompts from persona_extractor ---

SUMMARY_PROMPT = """你是一名“对话历史整理员”，请在保持事实准确的前提下，将最近用户 和 Assistant 的聊天记录 <chat_transcript> 概括为一段描述。
## 要求
1. 最终摘要需要尽可能详细，1000 字左右，在此基础上尽可能详细地描述用户与 Assistant 之间的互动，以及对话中发生过和用户说的的所有事情。
2. 聚焦人物状态、事件节点、情绪/意图等关键信息，将片段整合为连贯文字。
3. 输出需包含 who / how / why / what 四个字段，每项不超过 50 字。
4. 禁止臆测或脏话，所有内容都必须能在聊天中找到对应描述。
5. 要求 Assistant 在后续的和用户对话中，参考你总结出的信息，能快速回忆历史。
6. 要求绝对不能遗漏 <chat_transcript> 中重要的信息！一定要显式地在概括中描述清楚！

聊天片段：
<chat_transcript>
{chat_transcript}
</chat_transcript>

请严格输出下列 JSON：
{{
  "summary": "1000字左右的连贯摘要，尽可能详细！",
  "table": {{
    "who": "不超过50字",
    "how": "不超过50字",
    "why": "不超过50字",
    "what": "不超过50字"
  }}
}}
"""

UPDATE_SUMMARY_PROMPT = """你是一名“对话历史整理员”，请在保持事实准确的前提下，根据已有的摘要 <existing_summary> 和到当前为止的聊天记录 <chat_transcript> 结合并概括为一段描述。
## 要求
1. 最终摘要需要尽可能详细，1000 字左右，在此基础上尽可能详细地描述用户与 Assistant 之间的互动，以及对话中发生过和用户说的的所有事情。
2. 聚焦人物状态、事件节点、情绪/意图等关键信息，将片段整合为连贯文字。
3. 输出需包含 who / how / why / what 四个字段，每项不超过 50 字。
4. 禁止臆测或脏话，所有内容都必须能在聊天中找到对应描述。
5. 要求 Assistant 在后续的和用户对话中，参考你总结出的信息，能快速回忆历史。
6. 要求不能遗漏 <existing_summary> 中的信息，要将 <existing_summary> 中的信息与 <chat_transcript> 按照时间顺序总结概括！

请注意！以下是已经存在的摘要，这段摘要是发生在 <chat_transcript> 聊天历史之前的用户与 Assistant 发生的事情。
已存在的摘要：
<existing_summary>
{existing_summary}
</existing_summary>

聊天片段：
<chat_transcript>
{chat_transcript}
</chat_transcript>

请严格输出下列 JSON：
{{
  "summary": "1000字左右的连贯摘要，尽可能详细！",
  "table": {{
    "who": "不超过50字",
    "how": "不超过50字",
    "why": "不超过50字",
    "what": "不超过50字"
  }}
}}
"""

MERGE_ONLY_PROMPT = """你是一名“对话历史整理员”。
请将以下两段对话摘要合并为一段连贯的、更新后的对话历史摘要。
摘要 <summary_old> 是较早的时间段，摘要 <summary_new> 是较新的时间段。

【摘要 A (旧)】
<summary_old>
{summary_b}
</summary_old>

【摘要 B (新)】
<summary_new>
{summary_b}
</summary_new>

## 要求
1. 保持时间线的连贯性，将新发生的事自然接续在旧事之后。
2. 最终摘要不得超过 1000 字。
3. 依然提取 who / how / why / what 四个关键要素（基于合并后的全貌）。
4. 禁止臆测，只基于提供的摘要内容。

请严格输出下列 JSON：
{{
  "summary": "合并后的连贯摘要",
  "table": {{
    "who": "不超过50字",
    "how": "不超过50字",
    "why": "不超过50字",
    "what": "不超过50字"
  }}
}}
"""

def _safe_json_loads(raw: str) -> Dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 简单的正则提取尝试
        match = re.search(r'(\{.*\})', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return {}

def _parse_response(payload: str):
    """解析摘要 API 响应（独立函数，供 _summarize_with_main_api 使用）"""
    data = _safe_json_loads(payload)

    # 如果解析出的 data 是空或者不是 dict，尝试直接用 payload
    if not isinstance(data, dict) or (not data and not payload.strip().startswith("{")):
        summary = payload.strip()
        table = {}
    else:
        summary = str(data.get("summary", "")).strip()
        table_payload = data.get("table", {}) or {}
        table = {
            "who": str(table_payload.get("who", "")).strip(),
            "how": str(table_payload.get("how", "")).strip(),
            "why": str(table_payload.get("why", "")).strip(),
            "what": str(table_payload.get("what", "")).strip(),
        }

    if not summary:
        summary = payload.strip()

    if len(summary) > 1000:
        summary = summary[:1000].rstrip() + "..."

    return summary, table

def _extract_text_content(content) -> str:
    """从消息 content 中提取文本（处理字符串和列表格式）"""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        # 多模态消息，提取 text 部分
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
            elif isinstance(item, str):
                texts.append(item)
        return " ".join(texts)
    return str(content) if content else ""

def compute_token_count(messages: List[Dict]) -> int:
    """
    计算消息的 token 数量（使用 tiktoken）

    复用 billing/core.py 中的 estimate_prompt_tokens 函数，
    使用 cl100k_base encoding 进行准确的 token 计算。
    """
    try:
        from open_webui.billing.core import estimate_prompt_tokens
        return estimate_prompt_tokens(messages, model_id="default")
    except ImportError:
        # 如果 billing 模块不可用，降级为字符估算
        log.warning("billing 模块不可用，降级为字符估算")
        total_chars = 0
        for msg in messages:
            content = msg.get('content')
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        total_chars += len(item.get('text', ''))
        return max(total_chars // 4, 0)

# --- Core Logic Modules ---

def build_ordered_messages(
    messages_map: Optional[Dict], anchor_id: Optional[str] = None
) -> List[Dict]:
    """
    将消息 map 还原为有序列表

    策略：
    1. 优先：基于 parentId 链条追溯（从 anchor_id 向上回溯到根消息）
    2. 退化：按时间戳排序（无 anchor_id 或追溯失败时）

    参数：
        messages_map: 消息 map，格式 {"msg-id": {"role": "user", "content": "...", "parentId": "...", "timestamp": 123456}}
        anchor_id: 锚点消息 ID（链尾），从此消息向上追溯

    返回：
        有序的消息列表，每个消息包含 id 字段
    """
    if not messages_map:
        return []

    # 补齐消息的 id 字段
    def with_id(message_id: str, message: Dict) -> Dict:
        return {**message, **({"id": message_id} if "id" not in message else {})}

    # 模式 1：基于 parentId 链条追溯
    if anchor_id and anchor_id in messages_map:
        ordered: List[Dict] = []
        current_id: Optional[str] = anchor_id

        while current_id:
            current_msg = messages_map.get(current_id)
            if not current_msg:
                break
            ordered.insert(0, with_id(current_id, current_msg))
            current_id = current_msg.get("parentId")

        return ordered

    # 模式 2：基于时间戳排序
    sortable: List[Tuple[int, str, Dict]] = []
    for mid, message in messages_map.items():
        ts = (
            message.get("createdAt")
            or message.get("created_at")
            or message.get("timestamp")
            or 0
        )
        sortable.append((int(ts), mid, message))

    sortable.sort(key=lambda x: x[0])
    return [with_id(mid, msg) for _, mid, msg in sortable]

def get_recent_messages_by_user_id(
    user_id: str,
    num: int,
    exclude_loaded_by_user: bool,
    exclude_by_chat_id: Optional[str] = None,
) -> List[Dict]:
    """
    获取指定用户的最近 N 条消息（按时间顺序）

    参数：
        user_id: 用户 ID
        num: 需要获取的消息数量（<= 0 时返回全部）
        exclude_loaded_by_user: 是否过滤用户导入的聊天（chat.meta.loaded_by_user）
        exclude_by_chat_id:
            - str: 过滤 chat.meta.loaded_by_chat_id 等于该值的聊天

    返回：
        有序的消息列表（按时间顺序）
    """
    messages: List[Dict] = []

    # 遍历用户的所有聊天
    chats = Chats.get_chat_list_by_user_id(user_id, include_archived=True)
    for chat in chats:
        if exclude_loaded_by_user and (chat.meta or {}).get("loaded_by_user", None):
            continue
        loaded_by_chat_id = (chat.meta or {}).get("loaded_by_chat_id", None)
        if exclude_by_chat_id and loaded_by_chat_id == exclude_by_chat_id:
            continue
        messages_map = chat.chat.get("history", {}).get("messages", {}) or {}
        for mid, msg in messages_map.items():
            # 跳过空内容
            if msg.get("content", "") == "":
                continue
            ts = (
                msg.get("createdAt")
                or msg.get("created_at")
                or msg.get("timestamp")
                or 0
            )
            entry = {**msg, "id": mid}
            entry.setdefault("chat_id", chat.id)
            entry.setdefault("timestamp", int(ts))
            messages.append(entry)

    messages.sort(key=lambda m: m.get("timestamp", 0))

    if num <= 0:
        return messages

    return messages[-num:]

def get_recent_messages_by_user_id_and_chat_id(
    user_id: str, chat_id: str, num: int
) -> List[Dict]:
    """
    获取指定用户在指定聊天中的最近 N 条消息（按时间顺序）

    参数：
        user_id: 用户 ID
        chat_id: 聊天 ID
        num: 需要获取的消息数量（<= 0 时返回全部）

    返回：
        有序的消息列表（按时间顺序）
    """
    if not chat_id:
        return []

    chat = Chats.get_chat_by_id_and_user_id(chat_id, user_id)
    if not chat:
        return []

    messages: List[Dict] = []
    messages_map = chat.chat.get("history", {}).get("messages", {}) or {}
    for mid, msg in messages_map.items():
        # 跳过空内容
        if msg.get("content", "") == "":
            continue
        ts = (
            msg.get("createdAt")
            or msg.get("created_at")
            or msg.get("timestamp")
            or 0
        )
        entry = {**msg, "id": mid}
        entry.setdefault("chat_id", chat.id)
        entry.setdefault("timestamp", int(ts))
        messages.append(entry)

    messages.sort(key=lambda m: m.get("timestamp", 0))

    if num <= 0:
        return messages

    return messages[-num:]

def slice_messages_with_summary(
    messages_map: Dict,
    boundary_message_id: Optional[str],
    anchor_id: Optional[str],
    pre_boundary: int = 20,
) -> List[Dict]:
    """
    基于摘要边界裁剪消息列表（返回摘要前 N 条 + 摘要后全部消息）

    策略：保留摘要边界前 N 条消息（提供上下文）+ 摘要后全部消息（最新对话）
    目的：降低 token 消耗，同时保留足够的上下文信息

    参数：
        messages_map: 消息 map
        boundary_message_id: 摘要边界消息 ID（None 时返回全量消息）
        anchor_id: 锚点消息 ID（链尾）
        pre_boundary: 摘要边界前保留的消息数量（默认 20）

    返回：
        裁剪后的有序消息列表

    示例：
        100 条消息，摘要边界在第 50 条，pre_boundary=20
        → 返回消息 29-99（共 71 条）
    """
    ordered = build_ordered_messages(messages_map, anchor_id)

    if boundary_message_id:
        try:
            # 查找摘要边界消息的索引
            boundary_idx = next(
                idx for idx, msg in enumerate(ordered) if msg.get("id") == boundary_message_id
            )
            # 计算裁剪起点
            start_idx = max(boundary_idx - pre_boundary, 0)
            ordered = ordered[start_idx:]
        except StopIteration:
            # 边界消息不存在，返回全量
            pass

    return ordered

def _get_global_api_config(request: Request) -> Optional[Dict[str, Any]]:
    """
    获取 Global Summary API 配置

    返回：
        如果配置完整，返回 {
            "key": str,
            "base_url": str,
            "model_id": str,
            "input_price": int,
            "output_price": int
        }
        否则返回 None
    """
    global_api_key = getattr(request.app.state.config, "GLOBAL_API_KEY", None)
    global_api_base_url = getattr(request.app.state.config, "GLOBAL_API_BASE_URL", None)
    global_api_model_id = getattr(request.app.state.config, "GLOBAL_API_MODEL_ID", None)
    global_api_input_price = getattr(request.app.state.config, "GLOBAL_API_INPUT_PRICE", None)
    global_api_output_price = getattr(request.app.state.config, "GLOBAL_API_OUTPUT_PRICE", None)

    # 提取 PersistentConfig 的实际值
    if global_api_key:
        global_api_key = getattr(global_api_key, "value", global_api_key)
    if global_api_base_url:
        global_api_base_url = getattr(global_api_base_url, "value", global_api_base_url)
    if global_api_model_id:
        global_api_model_id = getattr(global_api_model_id, "value", global_api_model_id)
    if global_api_input_price:
        global_api_input_price = getattr(global_api_input_price, "value", global_api_input_price)
    if global_api_output_price:
        global_api_output_price = getattr(global_api_output_price, "value", global_api_output_price)

    # 判断配置是否有效（三个必需字段都非空）
    if (
        global_api_key and isinstance(global_api_key, str) and global_api_key.strip() and
        global_api_base_url and isinstance(global_api_base_url, str) and global_api_base_url.strip() and
        global_api_model_id and isinstance(global_api_model_id, str) and global_api_model_id.strip()
    ):
        return {
            "key": global_api_key,
            "base_url": global_api_base_url,
            "model_id": global_api_model_id,
            "input_price": int(global_api_input_price) if global_api_input_price else 0,
            "output_price": int(global_api_output_price) if global_api_output_price else 0,
        }
    return None

# 临时修改 request.state
# 作用：为摘要调用注入 direct/model 或 global summayr api 配置，同时不污染后续请求处理。
@contextmanager
def _temporary_request_state(
    request: Request,
    is_user_model: bool,
    model_config: Optional[Dict],
    model_id: Optional[str],
):
    """
    临时修改 request.state，为摘要调用注入模型配置

    优先级：
    1. 如果 is_user_model = True → 使用用户私有模型（不扣费）
    2. 否则，检查 Global API：
       - 如果 Global API 配置完整 → 使用 Global API（扣费）
       - 如果 Global API 为空 → 使用用户指定的模型（扣费）
    """
    local_request = request
    original_direct = getattr(local_request.state, "direct", None)
    original_model = getattr(local_request.state, "model", None)

    # 优先级 1: 如果是用户私有模型，直接使用
    if is_user_model:
        effective_model_config = model_config
        effective_is_user_model = True
        log.info(f"摘要生成使用用户私有模型（不扣费）: model={model_id}")
    else:
        # 优先级 2: 检查 Global API 配置
        global_api_config = _get_global_api_config(request)

        if global_api_config:
            # 使用 Global Summary API
            effective_model_config = {
                "id": global_api_config["model_id"],
                "base_url": global_api_config["base_url"],
                "api_key": global_api_config["key"],
            }
            effective_is_user_model = False  # 改为 False，因为需要扣费
            log.info(
                f"摘要生成使用 Global Summary API（扣费）: "
                f"model={global_api_config['model_id']}, base_url={global_api_config['base_url']}"
            )
        else:
            # 优先级 3: 回退使用用户指定的平台模型
            effective_model_config = model_config
            effective_is_user_model = False
            log.info(f"摘要生成使用平台模型（扣费）: model={model_id}")

    # 设置 request.state
    if effective_is_user_model:
        local_request.state.direct = True
        local_request.state.model = effective_model_config
        log.debug(
            f"设置 request.state: direct=True, model_id={effective_model_config.get('id', 'unknown')}, "
            f"base_url={effective_model_config.get('base_url')}"
        )
    else:
        log.debug(f"设置 request.state: 使用平台模型 {model_id}")

    try:
        yield local_request
    finally:
        if original_direct is None:
            if hasattr(local_request.state, "direct"):
                delattr(local_request.state, "direct")
        else:
            local_request.state.direct = original_direct

        if original_model is None:
            if hasattr(local_request.state, "model"):
                delattr(local_request.state, "model")
        else:
            local_request.state.model = original_model

def build_summary_prompt(
    messages: List[Dict], old_summary: Optional[str]
) -> str:
    # 使用 _extract_text_content 处理多模态消息
    sorted_messages = sorted(
        messages,
        key=lambda m: m.get("timestamp", 0)
        if isinstance(m.get("timestamp"), (int, float))
        else 0,
    )
    transcript = "\n".join(
        f"{m.get('role', 'user')}: {_extract_text_content(m.get('content', ''))}"
        for m in sorted_messages
    )
    if not old_summary:
        return SUMMARY_PROMPT.format(
            chat_transcript=transcript,
        )
    else:
        return UPDATE_SUMMARY_PROMPT.format(
            existing_summary=old_summary.strip(),
            chat_transcript=transcript,
        )

# === 3. Token 选择器：按 token 数量从最近消息中选取 ===
def select_recent_messages_by_tokens(
    messages,
    token_target,
    max_messages=None,
    starting_tokens=0,
):
    selected = []
    total_tokens = starting_tokens
    for msg in reversed(messages):
        if max_messages is not None and len(selected) >= max_messages:
            break
        selected.append(msg)
        total_tokens += compute_token_count([msg])
        if total_tokens >= token_target:
            break
    return list(reversed(selected)), total_tokens


# === 4. 滚动摘要辅助函数 ===
def split_messages_by_tokens(
    messages: List[Dict],
    max_tokens: int
) -> Tuple[List[Dict], List[Dict]]:
    """
    从消息列表头部取出不超过 max_tokens 的消息

    参数：
        messages: 消息列表（按时间从旧到新排序）
        max_tokens: token 上限

    返回：
        (chunk, remaining): chunk 是取出的消息，remaining 是剩余的消息
    """
    chunk = []
    chunk_tokens = 0

    for i, msg in enumerate(messages):
        msg_tokens = compute_token_count([msg])
        if chunk_tokens + msg_tokens <= max_tokens:
            chunk.append(msg)
            chunk_tokens += msg_tokens
        else:
            # 返回已取出的 chunk 和剩余的消息
            return chunk, messages[i:]

    # 所有消息都在 chunk 内
    return chunk, []


async def summarize(
    messages: List[Dict],
    model_id: str,
    user: Any,
    request: Request,
    is_user_model: bool,
    model_config: Optional[Dict],
    old_summary: Optional[str] = None,
    return_details: bool = False,
) -> Union[str, Tuple[str, Dict[str, Any]]]:
    """
    生成对话摘要（新版：复用主对话 API）

    参数：
        messages: 需要摘要的消息列表
        old_summary: 旧摘要
        model_id: 指定使用的模型 ID（如果为 None，则使用默认值 gpt-4.1-mini）
        user: 用户对象（用于计费）
        request: FastAPI Request 对象（用于调用主对话 API）
        is_user_model: 是否为用户自己的模型（True 时不扣费）
        model_config: 已验证的模型配置对象（用于直接复用主对话的模型连接）

    返回：
        摘要字符串

    使用主对话 API 生成摘要（内部函数）

    核心优势：
    1. 自动复用用户的 API 配置（base_url, api_key）
    2. 自动判断是否扣费（is_user_model=True 时不扣费）
    3. 使用当前会话的模型（而不是固定的 gpt-4.1-mini）
    4. 通过 request.state 直接传递已验证的模型配置,避免重复查找和验证

    计费策略：
    - 使用后付费模式
    - 成功时根据实际 usage 扣费，带 log_type="deduct_summary" 标签
    - 失败时不扣费（API 返回错误或异常）
    """
    user_id = getattr(user, "id", str(user))

    # 0. 空消息检查
    if not messages:
        log.warning("摘要生成跳过：无消息")
        return ""

    # 1. 构建摘要 prompt
    prompt = build_summary_prompt(messages, old_summary)

    # 2. 构造请求参数（OpenAI 格式）
    form_data = {
        "model": model_id or "gpt-4o-mini",  # 默认使用 gpt-4o-mini
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,  # 摘要不使用流式
        "max_tokens": 3000,  # 安全值，防止截断
        "temperature": 0.1,  # 低温度保证稳定性
    }

    log.info(f"开始生成摘要: model={model_id}, is_user_model={is_user_model}, messages_count={len(messages)}")

    # 3. 直接调用 API（不使用 chat_with_billing，采用后付费模式）
    with _temporary_request_state(request, is_user_model, model_config, model_id) as local_request:
        response = await generate_openai_chat_completion(
            request = local_request,
            form_data = form_data,
            user = user,
            bypass_filter = True,  # 跳过权限检查（摘要是系统内部调用）
            chatting_completion = True
        )

    # 4. 解析响应（处理多种返回类型）
    if isinstance(response, dict):
        # 正常响应：直接是 dict
        payload = response.get("choices", [{}])[0].get("message", {}).get("content", "")

        # 提取 usage 信息
        usage = response.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        log.info(
            f"摘要生成完成: model={model_id}, is_user_model={is_user_model}, "
            f"tokens={prompt_tokens}+{completion_tokens}, "
            f"payload_length={len(payload)}"
        )

        # 5. 后付费扣费
        # 判断是否需要扣费：
        # - 如果原始 is_user_model = True，说明用户使用私有模型，不扣费
        # - 如果原始 is_user_model = False，需要扣费（无论是 Global API 还是平台模型）
        if not is_user_model and (prompt_tokens > 0 or completion_tokens > 0):
            from open_webui.billing.core import deduct_balance

            # 检查是否使用 Global API
            global_api_config = _get_global_api_config(request)

            # 如果使用 Global API，使用自定义价格；否则使用默认价格
            if global_api_config:
                custom_input_price = global_api_config["input_price"]
                custom_output_price = global_api_config["output_price"]

                # Global API 始终扣费（即使价格为 0 也记录）
                try:
                    cost, balance = deduct_balance(
                        user_id=user_id,
                        model_id=global_api_config["model_id"],
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        custom_input_price=custom_input_price,
                        custom_output_price=custom_output_price,
                        log_type="deduct_summary"
                    )
                    log.info(
                        f"摘要生成计费成功（Global API）: user={user_id} model={global_api_config['model_id']} "
                        f"tokens={prompt_tokens}+{completion_tokens} "
                        f"cost={cost / 10000:.4f}元 balance={balance / 10000:.4f}元"
                    )
                except Exception as e:
                    from fastapi import HTTPException
                    if isinstance(e, HTTPException) and e.status_code in (402, 403, 404):
                        from open_webui.billing.core import convert_billing_exception_to_customized_error
                        raise convert_billing_exception_to_customized_error(e)
                    raise
            else:
                # 使用平台模型，按默认价格扣费
                try:
                    cost, balance = deduct_balance(
                        user_id=user_id,
                        model_id=model_id,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        log_type="deduct_summary"
                    )
                    log.info(
                        f"摘要生成计费成功: user={user_id} model={model_id} "
                        f"tokens={prompt_tokens}+{completion_tokens} "
                        f"cost={cost / 10000:.4f}元 balance={balance / 10000:.4f}元"
                    )
                except Exception as e:
                    from fastapi import HTTPException
                    if isinstance(e, HTTPException) and e.status_code in (402, 403, 404):
                        from open_webui.billing.core import convert_billing_exception_to_customized_error
                        raise convert_billing_exception_to_customized_error(e)
                    raise

        # 6. 解析 JSON 并提取摘要
        summary, table = _parse_response(payload)
        if return_details:
            llm_details = {
                "prompt": prompt,
                "response": payload,
                "usage": usage,
                "model": form_data.get("model"),
            }
            return summary, llm_details
        return summary
    else:
        # 错误响应：JSONResponse / Response / str（不扣费）
        error_body = response.body.decode("utf-8") if hasattr(response, "body") else str(response)

        raise CustmizedError(
            user_toast_message = "梳理记忆失败，请联系管理员。",
            cause = RuntimeError(error_body)
        )


async def summarize_multi_chunk(
    messages: List[Dict],
    model_id: str,
    user: Any,
    request: Request,
    is_user_model: bool,
    model_config: Optional[Dict],
    token_threshold: int = ROLLING_SUMMARY_TOKEN_THRESHOLD_DEFAULT,
    old_summary: Optional[str] = None,
    return_details: bool = False,
    perf_logger: Optional["ChatPerfLogger"] = None,
) -> Union[str, Tuple[str, Dict[str, Any]]]:
    """
    并行分段摘要生成器 - 处理超大消息列表的分段摘要

    当消息总 token 数超过单次 LLM 调用上限时，将消息分段并行处理：
    1. 将消息按 token_threshold 分成多段
    2. 并发对每一段调用 summarize
    3. 将所有摘要直接拼接作为最终结果

    参数：
        messages: 完整的消息列表（按时间从旧到新排序）
        model_id: 模型 ID
        user: 用户对象
        request: FastAPI Request 对象
        is_user_model: 是否为用户私有模型
        model_config: 模型配置
        token_threshold: 单次 LLM 调用的 token 上限
        old_summary: 已有的旧摘要（可选，会作为第一段的前缀）
        return_details: 是否返回详细信息
        perf_logger: 性能日志记录器

    返回：
        摘要字符串，或 (摘要字符串, 详细信息字典)
    """
    import asyncio

    # 0. 空消息检查
    if not messages:
        log.warning("并行摘要跳过：无消息")
        if return_details:
            return "", {"usage": {"prompt_tokens": 0, "completion_tokens": 0}, "chunks": 0}
        return ""

    # 1. 预检查：如果消息 token 总数不超过阈值，直接调用 summarize
    total_tokens = compute_token_count(messages)
    if total_tokens <= token_threshold:
        log.info(f"消息 token ({total_tokens}) <= 阈值 ({token_threshold})，直接调用 summarize")
        return await summarize(
            messages=messages,
            model_id=model_id,
            user=user,
            request=request,
            is_user_model=is_user_model,
            model_config=model_config,
            old_summary=old_summary,
            return_details=return_details,
        )

    # 2. 将消息分成多段（从后往前，确保最新消息不被截断）
    chunks = []
    remaining_messages = list(reversed(messages.copy()))  # 反转：从新到旧
    while remaining_messages:
        chunk, remaining_messages = split_messages_by_tokens(remaining_messages, token_threshold)
        # 边界情况：单条消息超过阈值，强制取出
        if not chunk and remaining_messages:
            log.warning(f"并行摘要：单条消息超过阈值，强制取出")
            chunk = [remaining_messages.pop(0)]
        if chunk:
            # 反转 chunk 内的消息顺序，恢复从旧到新
            chunks.append(list(reversed(chunk)))

    # 反转 chunks 列表，使 chunks[0] 包含最新消息
    chunks = list(reversed(chunks))

    log.info(
        f"开始并行摘要: total_tokens={total_tokens}, threshold={token_threshold}, "
        f"messages_count={len(messages)}, chunks={len(chunks)}, is_user_model={is_user_model}"
    )

    # 限制摘要范围
    from open_webui.env import MAX_SUMMARY_CHUNKS

    if len(chunks) > MAX_SUMMARY_CHUNKS:
        discarded_chunks = len(chunks) - MAX_SUMMARY_CHUNKS
        discarded_messages = sum(len(chunks[i]) for i in range(MAX_SUMMARY_CHUNKS, len(chunks)))
        log.info(
            f"消息分段数 ({len(chunks)}) 超过限制 ({MAX_SUMMARY_CHUNKS})，"
            f"丢弃最早的 {discarded_chunks} 个分段（共 {discarded_messages} 条消息），"
            f"只摘要最新的 {MAX_SUMMARY_CHUNKS} 个分段"
        )
        chunks = chunks[:MAX_SUMMARY_CHUNKS]  # 保留前 N 个（最新的）

    # 3. 并发对每一段调用 summarize
    async def summarize_chunk(chunk_idx: int, chunk: List[Dict]) -> Tuple[int, str, Dict]:
        """对单个分段进行摘要"""
        try:
            # 只有第一段需要 old_summary
            chunk_old_summary = old_summary if chunk_idx == 0 else None
            summary_text, details = await summarize(
                messages=chunk,
                model_id=model_id,
                user=user,
                request=request,
                is_user_model=is_user_model,
                model_config=model_config,
                old_summary=chunk_old_summary,
                return_details=True,
            )
            log.info(
                f"并行摘要第 {chunk_idx + 1}/{len(chunks)} 段完成: "
                f"messages={len(chunk)}, "
                f"prompt_tokens={details.get('usage', {}).get('prompt_tokens', 0)}, "
                f"completion_tokens={details.get('usage', {}).get('completion_tokens', 0)}"
            )
            return chunk_idx, summary_text, details
        except Exception as e:
            log.error(f"并行摘要第 {chunk_idx + 1} 段失败: {e}")
            raise

    # 并发执行所有分段的摘要
    tasks = [summarize_chunk(i, chunk) for i, chunk in enumerate(chunks)]
    results = await asyncio.gather(*tasks)

    # 4. 按顺序整理结果（按时间顺序：从旧到新）
    # 由于 chunks[0] 是最新的，chunk_idx 越小越新，所以需要反转排序
    results_sorted = sorted(results, key=lambda x: x[0], reverse=True)
    all_summaries = []
    all_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    all_prompts = []
    all_responses = []

    for chunk_idx, summary_text, details in results_sorted:
        all_summaries.append(summary_text)
        usage = details.get("usage", {})
        all_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        all_usage["completion_tokens"] += usage.get("completion_tokens", 0)
        all_prompts.append(details.get("prompt", ""))
        all_responses.append(details.get("response", ""))

        # 记录到 perf_logger
        if perf_logger:
            perf_logger.record_rolling_summary_iteration(
                iteration=chunk_idx + 1,
                old_summary=old_summary if chunk_idx == 0 else None,
                messages=chunks[chunk_idx],
                response=summary_text,
                usage=usage,
                remaining_messages_count=sum(len(chunks[j]) for j in range(chunk_idx + 1, len(chunks))),
            )

    # 5. 拼接所有摘要
    final_summary = "\n\n".join(all_summaries)

    log.info(
        f"并行摘要完成: chunks={len(chunks)}, "
        f"total_prompt_tokens={all_usage['prompt_tokens']}, "
        f"total_completion_tokens={all_usage['completion_tokens']}, "
        f"final_summary_length={len(final_summary)}"
    )

    # 6. 返回最终摘要
    if return_details:
        return final_summary, {
            "usage": all_usage,
            "chunks": len(chunks),
            "prompts": all_prompts,
            "responses": all_responses,
            "model": model_id,
        }
    return final_summary


async def ensure_initial_summary(
    request: Request,
    metadata,
    user,
    chat_id,
    model_id,
    is_user_model: bool,
    model_config,
    perf_logger=None
):
    """
    初始摘要生成器 - 为新聊天会话生成首次上下文摘要和冷启动消息

    根据 loaded_by_user 和 memory_enabled 的组合，分为四种情况：
    1. loaded_by_user=True,  memory_enabled=True:  导入聊天 + 开启记忆
    2. loaded_by_user=True,  memory_enabled=False: 导入聊天 + 关闭记忆
    3. loaded_by_user=False, memory_enabled=True:  新建聊天 + 开启记忆
    4. loaded_by_user=False, memory_enabled=False: 新建聊天 + 关闭记忆
    """
    if not chat_id:
        return

    # === 1. 基础信息提取 ===
    chat_item = Chats.get_chat_by_id_and_user_id(chat_id, user.id)
    old_summary = Chats.get_summary_by_user_id_and_chat_id(user.id, chat_id)
    memory_enabled = chat_item.chat.get('memory_enabled', True)
    loaded_by_user = (chat_item.meta or {}).get("loaded_by_user", None)
    token_target = INITIAL_SUMMARY_TOKEN_WINDOW_DEFAULT

    # === 2. 已有摘要则跳过 ===
    if old_summary:
        return

    # === 4. 定义四种内部处理函数 ===

    def _handle_loaded_with_memory():
        """
        情况1: 导入的聊天且开启记忆
        - 从当前聊天取出所有消息
        - 如果不足 token_target，从全局补充
        - 如果超出 token_target，全部装入
        - 从冷启动消息中取出 设置 last_summary_id 为最后一条消息
        - 
        """
        # 取出当前聊天的所有消息
        chat_messages = get_recent_messages_by_user_id_and_chat_id(
            user.id, chat_id, 0
        )
        chat_tokens = compute_token_count(chat_messages)

        # 如果当前聊天消息不足 token_target，从全局补充
        if chat_tokens < token_target:
            recent_conversation = get_recent_messages_by_user_id(
                user.id, 0,
                exclude_loaded_by_user=False,
                exclude_by_chat_id=chat_id,
            )
            global_messages, _ = select_recent_messages_by_tokens(
                recent_conversation, token_target,
                max_messages=100,
                starting_tokens=chat_tokens,
            )
            messages_for_summary = global_messages + chat_messages
        else:
            # 超出 token_target 则全部装入
            messages_for_summary = chat_messages

        # 构建冷启动消息
        cold_start_messages = _build_cold_start_messages(messages_for_summary)

        # last_summary_id 指向最后一条消息
        last_summary_id = cold_start_messages[-1].get("id") if cold_start_messages else None

        return messages_for_summary, last_summary_id, cold_start_messages, True  # need_summary=True

    def _handle_loaded_without_memory():
        """
        情况2: 导入聊天 + 关闭记忆
        - 从当前聊天获取消息作为冷启动
        - 生成摘要
        """
        conversation_in_this_chat = get_recent_messages_by_user_id_and_chat_id(
            user.id, chat_id, 0
        )
        messages_for_summary = conversation_in_this_chat

        # 使用 cold_start_messages 来用 last_summary_id 在该 chat 内取到一个窗口
        cold_start_messages = _build_cold_start_messages(messages_for_summary)
        last_summary_id = cold_start_messages[0].get("id") if cold_start_messages else None

        return messages_for_summary, last_summary_id, [], True  # need_summary=True

    def _handle_new_with_memory():
        """
        情况3: 新建聊天 + 开启记忆
        - 从全局获取消息
        - 生成摘要
        - 设置 last_summary_id 为该 chat 最新一条消息
        - 构建冷启动消息
        """
        recent_conversation = get_recent_messages_by_user_id(
            user_id=user.id, num=0,
            exclude_loaded_by_user=False,
        )
        messages_for_summary, _ = select_recent_messages_by_tokens(
            recent_conversation, token_target, max_messages=100
        )

        # last_summary_id 指向该 chat 最新一条消息
        last_summary_id = metadata.get("message_id")

        # 构建冷启动消息
        cold_start_messages = _build_cold_start_messages(messages_for_summary)

        return messages_for_summary, last_summary_id, cold_start_messages, True  # need_summary=True

    def _handle_new_without_memory():
        """
        情况4: 新建聊天 + 关闭记忆
        - 不需要任何历史消息
        - 不生成摘要
        - last_summary_id 指向该 chat 的第一条消息
        - 无冷启动消息
        """
        # 获取该 chat 的第一条消息作为 last_summary_id
        messages_map = Chats.get_messages_map_by_chat_id(chat_id) or {}
        current_message_id = metadata.get("message_id")
        ordered_messages = build_ordered_messages(messages_map, current_message_id)
        first_message_id = ordered_messages[0].get("id") if ordered_messages else None

        return [], first_message_id, [], False  # need_summary=False

    def _build_cold_start_messages(messages_for_summary):
        """构建冷启动消息：从消息列表中选取最多 COLD_START_TOKEN_WINDOW_DEFAULT token, 不超过 80 条"""
        if not messages_for_summary:
            return []

        cold_start, _ = select_recent_messages_by_tokens(
            messages_for_summary,
            token_target=COLD_START_TOKEN_WINDOW_DEFAULT,
            max_messages=80
        )
        return [
            {
                "id": m.get("id"),
                "role": m.get("role"),
                "content": m.get("content"),
                "timestamp": m.get("timestamp"),
            }
            for m in cold_start
            if m.get("id") and m.get("content")
        ]

    # === 5. 根据条件选择处理函数 ===
    if loaded_by_user:
        if memory_enabled:
            # 情况1: 导入聊天 + 开启记忆
            log.info(f"[ensure_initial_summary] 情况1: 导入聊天 + 开启记忆, chat_id={chat_id}")
            messages_for_summary, last_summary_id, cold_start_messages, need_summary = _handle_loaded_with_memory()
        else:
            # 情况2: 导入聊天 + 关闭记忆
            log.info(f"[ensure_initial_summary] 情况2: 导入聊天 + 关闭记忆, chat_id={chat_id}")
            messages_for_summary, last_summary_id, cold_start_messages, need_summary = _handle_loaded_without_memory()
    else:
        if memory_enabled:
            # 情况3: 新建聊天 + 开启记忆
            log.info(f"[ensure_initial_summary] 情况3: 新建聊天 + 开启记忆, chat_id={chat_id}")
            messages_for_summary, last_summary_id, cold_start_messages, need_summary = _handle_new_with_memory()
        else:
            # 情况4: 新建聊天 + 关闭记忆
            log.info(f"[ensure_initial_summary] 情况4: 新建聊天 + 关闭记忆, chat_id={chat_id}")
            messages_for_summary, last_summary_id, cold_start_messages, need_summary = _handle_new_without_memory()

    # === 6. 性能监控：标记摘要生成开始 ===
    if perf_logger and messages_for_summary:
        prompt = build_summary_prompt(messages_for_summary, None)
        perf_logger.ensure_initial_summary_start(messages_for_summary, prompt)

    # === 7. 根据 need_summary 决定是否生成摘要 ===
    if need_summary and messages_for_summary:
        # 需要生成摘要：创建后台任务
        async def summarize_and_save():
            async with chat_error_boundary(metadata, user):
                summary_text, summary_llm_details = await summarize_multi_chunk(
                    messages=messages_for_summary,
                    model_id=model_id,
                    user=user,
                    request=request,
                    is_user_model=is_user_model,
                    model_config=model_config,
                    old_summary=None,
                    return_details=True,
                    perf_logger=perf_logger,
                )
                Chats.set_summary_by_user_id_and_chat_id(
                    user_id=user.id,
                    chat_id=chat_id,
                    summary=summary_text,
                    last_summary_id=last_summary_id,
                    last_timestamp=int(time.time()),
                    status="done",
                    summarize_task_id="",
                    cold_start_messages=cold_start_messages,
                    increase_summary_time=True,
                )

                if perf_logger:
                    perf_logger.ensure_initial_summary_end(
                        response={
                            "summary_text": summary_text,
                            "llm_response": summary_llm_details.get("response"),
                        },
                        prompt=summary_llm_details.get("prompt"),
                        usage=summary_llm_details.get("usage"),
                    )
                    await perf_logger.save_to_file()

        summarize_task_id, _ = await create_task(
            request.app.state.redis,
            summarize_and_save(),
            id=chat_id,
        )

        # 持久化待完成的 summarize 到数据库
        Chats.set_summary_by_user_id_and_chat_id(
            user_id=user.id,
            chat_id=chat_id,
            summary="",
            last_summary_id=last_summary_id,
            last_timestamp=int(time.time()),
            status="generating",
            summarize_task_id=summarize_task_id,
            cold_start_messages=cold_start_messages,
        )
    else:
        # 不需要生成摘要：直接写入空摘要记录
        Chats.set_summary_by_user_id_and_chat_id(
            user_id=user.id,
            chat_id=chat_id,
            summary="",
            last_summary_id=last_summary_id,
            last_timestamp=int(time.time()),
            status="done",
            summarize_task_id='',
            cold_start_messages=cold_start_messages
        )

def messages_loaded(
    request: Request,
    metadata,
    user,
    memory_enabled: bool,
    perf_logger: Optional[ChatPerfLogger] = None,
):
    chat_id = metadata.get("chat_id", None)
    chat_item = Chats.get_chat_by_id_and_user_id(chat_id, user.id)
    summary_record = Chats.get_summary_by_user_id_and_chat_id(user.id, chat_id)

    current_message_id = metadata.get("message_id")
    # 1 注入 system prompt
    summary_system_message = {
        "role": "system",
        "content": (
            "Conversation History Summary:\n"
            f"{summary_record.get('content', '') if summary_record else ''}"
        ),
    }

    # 2 获取冷启动消息（用于注入关键历史消息）
    cold_start_messages = chat_item.meta.get("cold_start_messages", []) or []

    # 获取 last_summary_id 往后的所有消息
    messages_map = Chats.get_messages_map_by_chat_id(chat_id) or {}
    current_message_id = metadata.get("message_id")
    last_summary_id = summary_record.get("last_summary_id") if summary_record else None
    if last_summary_id is None and summary_record: # 兼容旧版本, last_summary_id 之前 被命名为 last_message_id
        last_summary_id = summary_record.get("last_message_id")
    ordered_messages_in_chat = build_ordered_messages(messages_map, current_message_id)
    recent_conversation_in_this_chat = []
    if summary_record and last_summary_id:
        try:
            boundary_idx = next(
                idx
                for idx, msg in enumerate(ordered_messages_in_chat)
                if msg.get("id") == last_summary_id
            )
            recent_conversation_in_this_chat = ordered_messages_in_chat[boundary_idx:]
        except StopIteration:
            recent_conversation_in_this_chat = []

    if not recent_conversation_in_this_chat:
        # Fallback: use as many recent messages as possible within 30k tokens.
        token_budget = 30000
        token_count = 0
        window = []
        for msg in reversed(ordered_messages_in_chat):
            next_tokens = compute_token_count([msg])
            if token_count + next_tokens > token_budget and window:
                break
            token_count += next_tokens
            window.append(msg)
        recent_conversation_in_this_chat = list(reversed(window))

    if perf_logger:
        perf_logger.mark_payload_checkpoint("db_get_messages_map")
        perf_logger.record_messages_loaded(
            summary_system_message,
            cold_start_messages,
            recent_conversation_in_this_chat,
        )

    # 移除旧的 system 消息
    recent_conversation_in_this_chat = [
        m for m in recent_conversation_in_this_chat if m.get("role") != "system"
    ]

    # 正确的消息顺序：System Message + Cold Start Messages + 当前窗口消息
    ordered_messages = [summary_system_message, *cold_start_messages, *recent_conversation_in_this_chat]
    # 合并连续的同角色消息，避免 LLM API 报错
    ordered_messages = merge_consecutive_messages(ordered_messages)
    return ordered_messages

async def update_summary(request, metadata, user, model, is_user_model):
    perf_logger: Optional[ChatPerfLogger] = metadata.get("perf_logger")
    chat_id = metadata.get("chat_id")
    chat_item = Chats.get_chat_by_id_and_user_id(chat_id, user.id)
    messages_map = Chats.get_messages_map_by_chat_id(chat_id) or {}
    threshold = getattr(request.app.state.config, "SUMMARY_TOKEN_THRESHOLD", SUMMARY_TOKEN_THRESHOLD_DEFAULT)
    existing_summary = Chats.get_summary_by_user_id_and_chat_id(user.id, chat_id)
    summary_content = existing_summary.get("content")
    last_summary_id = existing_summary.get("last_summary_id", None) if existing_summary else None
    if last_summary_id is None: # 兼容旧版本, last_summary_id 之前 被命名为 last_message_id
        last_summary_id = existing_summary.get("last_message_id")

    # 截取 last_summary_id（上次 summary 时的 message） 和 current_message_id 之间的所有 message
    current_message_id = metadata.get("message_id")
    cold_start_messages = chat_item.meta.get("cold_start_messages", []) or []
    new_messages = slice_messages_with_summary(
        messages_map = messages_map,
        boundary_message_id = last_summary_id,
        anchor_id = current_message_id,
        pre_boundary = 0,
    )
    # 只统计 user 和 assistant 消息
    messages_in_window = [msg for msg in cold_start_messages + new_messages if msg.get("role") in ("user", "assistant")]
    tokens_in_window = compute_token_count(messages_in_window)

    if CHAT_DEBUG_FLAG:
        print(
            f"[summary:update] chat_id={chat_id} 已有摘要，"
            f"新增消息数={len(new_messages)} 新增token={tokens_in_window} 阈值={threshold} tokens_in_window={tokens_in_window}"
        )

    # 若超过阈值，才生成/更新摘要
    if tokens_in_window >= threshold:
        # 读取已有的 summary
        old_summary = summary_content

        # 过滤
        to_be_summarized_summary_messages = [
            msg for msg in messages_in_window if msg.get("role") in ("user", "assistant")
        ]

        # 标记 summary 更新开始
        if perf_logger:
            perf_logger.update_summary_start(
                old_summary=old_summary,
                to_be_summarized_messages=to_be_summarized_summary_messages,
                tokens=tokens_in_window,
                threshold=threshold,
            )
        
        # 获取当前模型ID和用户模型标记，确保使用正确的模型进行摘要更新
        model_id = model.get("id") if model else None

        # 调用摘要生成（复用主对话 API，自动判断是否扣费）
        # 传递 model_config 以直接复用主对话的已验证模型配置，避免重复查找
        summary_text, summary_llm_details = await summarize(
            messages=to_be_summarized_summary_messages,
            model_id=model_id,
            user=user,
            request=request,
            is_user_model=is_user_model,
            model_config=model,
            old_summary=old_summary,
            return_details=True,
        )

        # 在 to_be_summarized_summary_messages 找到最远 5000 个token 或 16条 message， 作为 last_summary_id 点位，以保证 summary 后的连贯性
        recent_messages_in_summary_window ,_ = select_recent_messages_by_tokens(
            to_be_summarized_summary_messages,
            token_target=5000,
            max_messages=16,
            starting_tokens=0
        )
        last_summary_id = recent_messages_in_summary_window[0].get("id")
        Chats.set_summary_by_user_id_and_chat_id(
            user_id = user.id,
            chat_id = chat_id,
            summary = summary_text,
            last_summary_id = last_summary_id,
            last_timestamp = int(time.time()),
            status = 'done',
            summarize_task_id = '',
            cold_start_messages = [],
            increase_summary_time = True,
        )

        # 记录 summary 更新使用的材料（summarize 函数的完整参数）
        # 标记 summary 更新结束
        if perf_logger:
            perf_logger.update_summary_end(
                response={
                    "summary_text": summary_text,
                    "llm_response": summary_llm_details.get("response"),
                },
                prompt=summary_llm_details.get("prompt"),
                usage=summary_llm_details.get("usage"),
            )
    else: # tokens 未超过阈值，不执行摘要更新
        pass

def messages_loaded_new(
    metadata,
    user,
    user_token_num: int,
    assistant_token_num: int,
    perf_logger: Optional[ChatPerfLogger] = None,
):
    chat_id = metadata.get("chat_id", None)
    chat_item = Chats.get_chat_by_id_and_user_id(chat_id, user.id)
    summary_record = Chats.get_summary_by_user_id_and_chat_id(user.id, chat_id)

    # 1 注入 system prompt
    summary_system_message = {
        "role": "system",
        "content": (
            "Conversation History Summary:\n"
            f"{summary_record.get('content', '') if summary_record else ''}"
        ),
    }

    # 2 冷启动消息
    cold_start_messages = chat_item.meta.get("cold_start_messages", []) or []

    messages_map = Chats.get_messages_map_by_chat_id(chat_id) or {}
    current_message_id = metadata.get("message_id")
    all_messages = build_ordered_messages(messages_map, current_message_id)

    if perf_logger:
        perf_logger.mark_payload_checkpoint("db_get_messages_map")

    # 3 按分支顺序从新到旧遍历消息，按角色分别扣减 token 配额
    all_messages = list(reversed(all_messages))
    selected_messages = []

    def append_if_budget_allows(message):
        nonlocal user_token_num, assistant_token_num
        role = message.get("role")
        if role == "user" and user_token_num > 0:
            selected_messages.append(message)
            user_token_num -= compute_token_count([message])
        if role == "assistant" and assistant_token_num > 0:
            selected_messages.append(message)
            assistant_token_num -= compute_token_count([message])

    for message in all_messages:
        append_if_budget_allows(message)
        if user_token_num <= 0 and assistant_token_num <= 0:
            break

    # 4 若配额未用完，则从 cold_start_messages 中继续补充
    if user_token_num > 0 or assistant_token_num > 0:
        for message in reversed(cold_start_messages):
            append_if_budget_allows(message)
            if user_token_num <= 0 and assistant_token_num <= 0:
                break

    # 保证消息顺序为旧到新
    selected_messages = list(reversed(selected_messages))

    ordered_messages = [summary_system_message, *selected_messages]
    ordered_messages = merge_consecutive_messages(ordered_messages)
    return ordered_messages
