
# 新版 summary

from typing import Dict, List, Optional, Tuple, Sequence, Any, Union, Callable
import datetime
import re
import os
import time
from logging import getLogger
import hashlib
from jinja2 import Environment

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from open_webui.models.chats import Chats
from open_webui.tasks import create_task
from open_webui.utils.chat_error_boundary import chat_error_boundary, CustmizedError
from open_webui.routers.openai import generate_chat_completion as generate_openai_chat_completion
from open_webui.utils.perf_logger import ChatPerfLogger
from open_webui.utils.global_api import (
    get_global_api_config as _get_global_api_config,
    temporary_request_state as _temporary_request_state,
)

from open_webui.env import (
    BOOTSTRAP_SUMMARY_CHUNK_STRATEGY,
    SUMMARY_MESSAGE_THRESHOLD,
    SUMMARY_TOKEN_THRESHOLD,
    SUMMARY_SUBCHUNK_MIN_MESSAGES,
    SUMMARY_RETRIEVAL_LIMIT,
    SUMMARY_RETRIEVAL_USER_MESSAGE_COUNT,
    CURRENT_CONTEXT_TOKEN_BUDGET,
    CURRENT_CONTEXT_MINIAL_MESSAGE,
)

from open_webui.utils.misc import merge_consecutive_messages

# Import for calling main chat API
from fastapi import Request

log = getLogger(__name__)

# --- Constants & Prompts from persona_extractor ---

SUMMARY_PROMPT = """# Role
你是一个专业的对话记录员和记忆归档师。你的任务是将一段“用户”与“AI助手”之间的原始对话压缩成一段简练、信息密度极高的摘要。

# Input Data
<chat_transcript>
{chat_transcript}
</chat_transcript>

# Instructions
请对上述对话进行总结，生成一段不超过 {summary_chars} 字的摘要。
1. **保留关键事实**：用户提到的喜好、计划、发生的事件、提及的人名或地点。
2. **捕捉情绪变化**：记录用户当时的心情（如：焦虑、兴奋、疲惫）。
3. **第三人称叙述**：使用“用户”和“AI”作为主语（或者用用户的名字）。
4. **独立性**：这段摘要未来会被独立检索，所以请确保它在没有上下文的情况下也能被读懂（例如，不要说“他说了那个”，要说“用户提到了《三体》这本书”）。
5. 最终摘要需要尽可能详细，{summary_chars} 字左右，在此基础上尽可能详细地描述用户与 Assistant 之间的互动，以及对话中发生过和用户说的的所有事情。
6. 聚焦人物状态、事件节点、情绪/意图等关键信息，将片段整合为连贯文字。
7. 禁止臆测或脏话，所有内容都必须能在聊天中找到对应描述。
8. 要求 Assistant 在后续的和用户对话中，参考你总结出的信息，能快速回忆历史。
9. 要求绝对不能遗漏 <chat_transcript> 中重要的信息！一定要显式地在概括中描述清楚！

# Output Format
直接输出摘要内容，不要包含任何前言或后语。
"""

BOOTSTRAP_SUMMARY_TARGET_CHARS = 1200
ROLLING_SUMMARY_TARGET_CHARS = 500

SYSTEM_PROMPT_ENV = Environment(trim_blocks=True, lstrip_blocks=True)
SUMMARY_SYSTEM_PROMPT_TEMPLATE = SYSTEM_PROMPT_ENV.from_string(
    """# Memory System (Recall)
以下是你脑海中闪过的**历史记忆片段**。这些事情发生在过去，仅作为背景参考，帮助你更好地理解 User：
<relevant_memories>
{% for memory in searched_summaries %}
## 记忆片段 {{ loop.index }}
[时间: {{ memory.start_time or memory.start_timestamp or "未知" }} ~ {{ memory.end_time or memory.end_timestamp or "未知" }}]
[来源: {{ "这条回忆来自于本对话框" if memory.is_same_chat else "这条回忆来自于其他对话框" }}]
记忆内容: {{ memory.content }}
{% endfor %}
</relevant_memories>

# Short-term Context (Continuity)
{% if latest_summary.is_same_chat is defined and not latest_summary.is_same_chat %}
以下是**刚刚发生**在其他聊天窗口的一段对话总结，承接当前的聊天语境：
{% else %}
以下是**刚刚发生**的一段对话总结，承接当前的聊天语境：
{% endif %}
<recent_summary>
[时间: {{ latest_summary.start_time or latest_summary.start_timestamp or "未知" }} ~ {{ latest_summary.end_time or latest_summary.end_timestamp or "未知" }}]
{{ latest_summary.content }}
</recent_summary>

# Response Guidelines
1. **不要复读记忆**：不要生硬地把记忆里的内容背诵出来（比如不要说“根据记忆库显示你喜欢吃苹果”），要自然地融合在对话中（比如“既然你喜欢吃苹果，那这个甜点你肯定喜欢”）。
2. **时间感知**：`<relevant_memories>` 里的都是过去式。
"""
)

def _normalize_summary(payload: str) -> str:
    summary = payload.strip()
    return summary

def _format_timestamp(timestamp: int) -> str:
    if not timestamp:
        return "未知"
    return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

def _format_timestamp_range(start_timestamp: int, end_timestamp: int) -> str:
    start_time_str = _format_timestamp(start_timestamp)
    end_time_str = _format_timestamp(end_timestamp)
    if start_time_str == "未知" and end_time_str == "未知":
        return "未知"
    return f"{start_time_str} ~ {end_time_str}"

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

def _strip_pending_pair(
    messages: List[Dict[str, Any]],
    *,
    metadata: Dict[str, Any],
    messages_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """移除当前轮的 user+空 assistant 占位对话，避免误判为历史消息。"""
    current_assistant_id = metadata.get("message_id")
    if not current_assistant_id:
        return messages
    current_assistant = messages_map.get(current_assistant_id) or {}
    if current_assistant.get("role") != "assistant":
        return messages
    assistant_text = _extract_text_content(current_assistant.get("content", "")).strip()
    if assistant_text:
        return messages
    parent_id = current_assistant.get("parentId")
    drop_ids = {current_assistant_id}
    if parent_id:
        drop_ids.add(parent_id)
    return [msg for msg in messages if msg.get("id") not in drop_ids]

def _transform_message_content(
    content: Any,
    transform: Callable[[str], str],
) -> Any:
    if isinstance(content, str):
        return transform(content)
    if isinstance(content, list):
        updated = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                new_item = dict(item)
                new_item["text"] = transform(item.get("text", ""))
                updated.append(new_item)
            elif isinstance(item, str):
                updated.append(transform(item))
            else:
                updated.append(item)
        return updated
    return content

def strip_details_blocks(text: str) -> str:
    if not text:
        return text
    return re.sub(r"<details\b[^>]*>.*?</details>", "", text, flags=re.IGNORECASE | re.DOTALL)

def apply_content_transform_to_messages(
    messages: List[Dict[str, Any]],
    transform: Optional[Callable[[str], str]] = None,
) -> List[Dict[str, Any]]:
    if not messages or transform is None:
        return messages
    updated = []
    for msg in messages:
        new_msg = dict(msg)
        new_msg["content"] = _transform_message_content(
            msg.get("content"),
            transform,
        )
        updated.append(new_msg)
    return updated

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

def _serialize_vector(vector: Any) -> Any:
    if vector is None:
        return None
    if hasattr(vector, "tolist"):
        try:
            return vector.tolist()
        except Exception:
            return vector
    if isinstance(vector, tuple):
        return list(vector)
    return vector

# --- Chroma Summary Store ---

class SummaryChromaStore:
    def __init__(self, request: Request, user_id: Any, chat_id: Optional[str]):
        self._user_id = user_id
        self._chat_id = chat_id
        self._client = getattr(request.app.state, "VECTOR_DB_CLIENT", None)
        if self._client is None:
            try:
                from open_webui.retrieval.vector.factory import (
                    VECTOR_DB_CLIENT as default_client,
                )
                self._client = default_client
            except Exception:
                self._client = None
        self._collection_name = self._build_collection_name(user_id, chat_id)

    @staticmethod
    def _build_collection_name(user_id: Any, chat_id: Optional[str]) -> Optional[str]:
        if not user_id or not chat_id:
            return None

        base = f"{user_id}-{chat_id}"
        safe = re.sub(r"[^0-9A-Za-z_-]+", "-", base).strip("-_")
        prefix = "chat-summary-"
        name = f"{prefix}{safe}" if safe else ""

        if not name or len(name) > 63 or not re.match(r"^[0-9A-Za-z].*[0-9A-Za-z]$", name):
            digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
            name = f"{prefix}{digest}"

        return name

    @property
    def collection_name(self) -> Optional[str]:
        return self._collection_name

    def is_ready(self) -> bool:
        return bool(self._client and self._collection_name)

    def search(self, query_embedding: List[Union[float, int]], limit: int) -> List[Dict[str, Any]]:
        if not self.is_ready():
            return []

        result = self._client.search(
            collection_name=self._collection_name,
            vectors=[query_embedding],
            limit=limit,
        )
        if not result:
            return []

        ids = result.ids[0] if result.ids else []
        documents = result.documents[0] if result.documents else []
        metadatas = result.metadatas[0] if result.metadatas else []
        distances = result.distances[0] if getattr(result, "distances", None) else []

        min_len = min(len(ids), len(documents), len(metadatas)) if (ids or documents or metadatas) else 0
        items = []
        for idx in range(min_len):
            items.append(
                {
                    "id": ids[idx],
                    "document": documents[idx],
                    "metadata": metadatas[idx],
                    "distance": distances[idx] if idx < len(distances) else None,
                }
            )
        return items

    def get_all(self) -> List[Dict[str, Any]]:
        if not self.is_ready():
            return []

        result = self._client.get(collection_name=self._collection_name)
        if not result:
            return []

        ids = result.ids[0] if result.ids else []
        documents = result.documents[0] if result.documents else []
        metadatas = result.metadatas[0] if result.metadatas else []

        min_len = min(len(ids), len(documents), len(metadatas)) if (ids or documents or metadatas) else 0
        items = []
        for idx in range(min_len):
            items.append(
                {
                    "id": ids[idx],
                    "document": documents[idx],
                    "metadata": metadatas[idx],
                }
            )
        return items

    def upsert(self, item_id: str, text: str, vector: List[Union[float, int]], metadata: Dict[str, Any]) -> None:
        if not self.is_ready():
            return

        self._client.upsert(
            collection_name=self._collection_name,
            items=[
                {
                    "id": item_id,
                    "text": text,
                    "vector": vector,
                    "metadata": metadata,
                }
            ],
        )

    def upsert_many(self, items: List[Dict[str, Any]]) -> None:
        if not self.is_ready() or not items:
            return

        self._client.upsert(
            collection_name=self._collection_name,
            items=items,
        )

    def search_in_chat(
        self, query_embedding: List[Union[float, int]], limit: int
    ) -> List[Dict[str, Any]]:
        return self.search(query_embedding, limit)

    def search_in_user_chats(
        self, request: Request, query_embedding: List[Union[float, int]], limit: int
    ) -> List[Dict[str, Any]]:
        if not self._user_id:
            return []

        retrieval_results: List[Dict[str, Any]] = []
        chat_list = Chats.get_chat_title_id_list_by_user_id(
            self._user_id,
            include_archived=True,
            include_folders=True,
            include_pinned=True,
        )
        for chat in chat_list:
            other_chat_id = getattr(chat, "id", None)
            if not other_chat_id and isinstance(chat, dict):
                other_chat_id = chat.get("id")
            if not other_chat_id:
                continue

            other_store = self
            if other_chat_id != self._chat_id:
                other_store = SummaryChromaStore(request, self._user_id, other_chat_id)
            if not other_store.is_ready():
                continue

            results = other_store.search(query_embedding, limit)
            if results:
                retrieval_results.extend(results)

        if retrieval_results:
            retrieval_results.sort(
                key=lambda item: item.get("distance")
                if isinstance(item.get("distance"), (int, float))
                else float("-inf"),
                reverse=True,
            )
            retrieval_results = retrieval_results[:limit]

        return retrieval_results

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

def build_summary_prompt(messages: List[Dict], summary_chars: int = 200) -> str:
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
    return SUMMARY_PROMPT.format(
        chat_transcript=transcript,
        summary_chars=summary_chars,
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

def split_messages_by_token_and_count(
    messages: List[Dict],
    max_tokens: int,
    max_messages: int,
    min_messages: int,
) -> List[List[Dict]]:
    """
    按 token 与消息条数双阈值进行切分，并保证最小条数。

    规则：
    1) 达到 max_messages 时强制切分；
    2) token 即将超过 max_tokens 时，若当前已达到 min_messages 才切分；
    3) 若未达到 min_messages，则允许超出 max_tokens 继续累积。

    结果：
        返回按原顺序切分后的多个 chunk。
    """
    chunks: List[List[Dict]] = []
    current: List[Dict] = []
    current_tokens = 0

    # min_messages 至少为 1，且不允许 max_messages < min_messages
    min_messages = max(min_messages, 1)
    if max_messages < min_messages:
        max_messages = min_messages

    for msg in messages:
        msg_tokens = compute_token_count([msg])
        if current:
            would_exceed_tokens = current_tokens + msg_tokens > max_tokens

            # 优先规则：数量达到上限直接切分
            if len(current) >= max_messages:
                chunks.append(current)
                current = []
                current_tokens = 0
            # 仅当满足最小条数时，才允许因 token 超限切分
            elif would_exceed_tokens and len(current) >= min_messages:
                chunks.append(current)
                current = []
                current_tokens = 0

        current.append(msg)
        current_tokens += msg_tokens

    # 处理最后一个 chunk
    if current:
        chunks.append(current)

    return chunks

def build_summary_chunks(
    messages: List[Dict],
    rolling_token_threshold: int,
    subchunk_token_threshold: int,
    subchunk_message_threshold: int,
    subchunk_min_messages: int,
    max_chunks: int,
) -> Tuple[List[List[Dict]], int, int, List[str]]:
    """
    构建用于摘要的分段列表（先粗分，再细化最新分段）

    策略：
    1. 从最新消息向旧消息切分粗粒度 chunk，尽可能让最新 chunk 占满 token；
    2. 超过 max_chunks 时，仅保留最新的 max_chunks（基于粗分块）；
    3. 将最后一个 chunk 细分为更小的 sub-chunk（限制 token/消息条数，并保证最小条数）。

    返回：
        (chunks, discarded_chunks, discarded_messages, chunk_types)
    """
    if not messages:
        return [], 0, 0, []

    # 1) 粗粒度切分（从最新到最旧）
    newest_first_chunks: List[List[Dict]] = []
    remaining_messages = list(reversed(messages))
    while remaining_messages:
        chunk, remaining_messages = split_messages_by_tokens(
            remaining_messages, rolling_token_threshold
        )
        if not chunk and remaining_messages:
            log.warning("update_summary: 单条消息超过阈值，强制取出")
            chunk = [remaining_messages.pop(0)]
        if chunk:
            newest_first_chunks.append(list(reversed(chunk)))

    # 还原为从旧到新顺序
    chunks = list(reversed(newest_first_chunks))

    # 2) 控制粗分 chunk 数量上限
    discarded_chunks = 0
    discarded_messages = 0
    if max_chunks and len(chunks) > max_chunks:
        discarded_chunks = len(chunks) - max_chunks
        discarded_messages = sum(len(chunk) for chunk in chunks[:discarded_chunks])
        chunks = chunks[-max_chunks:]

    # 3) 细化最新 chunk
    chunk_types = ["chunk"] * len(chunks)
    if chunks:
        refined_latest = split_messages_by_token_and_count(
            chunks[-1],
            subchunk_token_threshold,
            subchunk_message_threshold,
            subchunk_min_messages,
        )
        if refined_latest:
            chunks = chunks[:-1] + refined_latest
            chunk_types = ["chunk"] * (len(chunks) - len(refined_latest)) + [
                "subchunk"
            ] * len(refined_latest)

    return chunks, discarded_chunks, discarded_messages, chunk_types

def _get_message_timestamp_or_zero(message: Dict) -> int:
    return int(
        message.get("createdAt")
        or message.get("created_at")
        or message.get("timestamp")
        or 0
    )

def _get_message_timestamp(message: Dict) -> int:
    return int(
        message.get("createdAt")
        or message.get("created_at")
        or message.get("timestamp")
        or int(time.time())
    )

def store_summary_chunks(
    chunk_summaries: List[Dict[str, Any]],
    *,
    embedding_function,
    store: "SummaryChromaStore",
    chat_id: str,
    user_id: Any,
    user: Any,
    state: Dict[str, Any],
) -> bool:
    """
    批量生成 embedding 并写入向量库，失败时设置 state.error_status。

    处理流程：
    1) 过滤空摘要并准备文本列表；
    2) 批量生成 embedding，处理单条/多条返回形态；
    3) 构建向量入库 items + 结构化记录；
    4) 批量 upsert，并合并到 state 统计数据。
    """
    if not chunk_summaries:
        return True

    # 1) 过滤空摘要，确保不会写入无效内容
    valid_summaries: List[Dict[str, Any]] = []
    for summary_info in chunk_summaries:
        summary_text = summary_info.get("summary", "")
        if not summary_text:
            state["error_status"] = state["error_status"] or "empty_summary"
            break
        valid_summaries.append(summary_info)

    if not valid_summaries:
        return False

    # 2) 批量生成 embedding（支持 list 输入）
    summary_texts = [item.get("summary", "") for item in valid_summaries]
    try:
        embeddings = embedding_function(summary_texts, user=user)
    except Exception as e:
        state["error_status"] = "embedding_error"
        state["error_message"] = str(e)
        return False

    # 兼容单条输入返回一维向量的情况
    if (
        len(summary_texts) == 1
        and isinstance(embeddings, list)
        and embeddings
        and isinstance(embeddings[0], (int, float))
    ):
        embeddings = [embeddings]

    # 返回数量不匹配视为错误，避免错位写入
    if not isinstance(embeddings, list) or len(embeddings) != len(summary_texts):
        state["error_status"] = "embedding_error"
        state["error_message"] = "embedding_batch_mismatch"
        return False

    # 3) 构建入库 items 与统计信息
    items = []
    chunk_records = []
    summary_iterations = []
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0}
    processed_message_count = 0
    last_processed_msg = None
    last_processed_timestamp = None
    chunk_index = state["current_chunk_count"]

    for summary_info, embedding_vector in zip(valid_summaries, embeddings):
        chunk_messages = summary_info.get("messages", []) or []
        first_msg = chunk_messages[0] if chunk_messages else {}
        last_msg = chunk_messages[-1] if chunk_messages else {}

        start_timestamp = _get_message_timestamp(first_msg)
        end_timestamp = _get_message_timestamp(last_msg)

        # 元数据用于检索与追溯
        item_id = f"{chat_id}_{chunk_index}"
        vector_metadata = {
            "chat_id": chat_id,
            "user_id": user_id,
            "chunk_index": chunk_index,
            "start_message_id": first_msg.get("id", ""),
            "end_message_id": last_msg.get("id", ""),
            "start_timestamp": int(start_timestamp),
            "end_timestamp": int(end_timestamp),
            "message_count": len(chunk_messages),
            "created_at": int(time.time()),
        }

        # 向量库批量入库项
        items.append(
            {
                "id": item_id,
                "text": summary_info.get("summary", ""),
                "vector": embedding_vector,
                "metadata": vector_metadata,
            }
        )

        # 结构化记录（给 perf_logger/调试使用）
        chunk_records.append(
            {
                "item_id": item_id,
                "message_count": len(chunk_messages),
                "start_message_id": first_msg.get("id", ""),
                "end_message_id": last_msg.get("id", ""),
                "start_timestamp": int(start_timestamp),
                "end_timestamp": int(end_timestamp),
            }
        )

        # 累加 usage / summary_iterations
        usage = summary_info.get("usage", {}) if summary_info else {}
        usage_total["prompt_tokens"] += usage.get("prompt_tokens", 0)
        usage_total["completion_tokens"] += usage.get("completion_tokens", 0)
        summary_iterations.append(
            {
                "chunk_index": chunk_index,
                "chunk_type": summary_info.get("chunk_type", "chunk"),
                "message_count": len(chunk_messages),
                "start_message_id": first_msg.get("id", ""),
                "end_message_id": last_msg.get("id", ""),
                "start_timestamp": int(start_timestamp),
                "end_timestamp": int(end_timestamp),
                "summary": summary_info.get("summary", ""),
                "prompt": summary_info.get("prompt", ""),
                "response": summary_info.get("response", ""),
                "usage": usage,
            }
        )

        processed_message_count += len(chunk_messages)
        last_processed_msg = last_msg
        last_processed_timestamp = end_timestamp
        chunk_index += 1

    # 4) 批量写入向量库
    try:
        store.upsert_many(items)
    except Exception as e:
        state["error_status"] = "chroma_error"
        state["error_message"] = str(e)
        return False

    # 5) 合并统计数据到 state
    state["processed_message_count"] += processed_message_count
    state["last_processed_msg"] = last_processed_msg
    state["last_processed_timestamp"] = last_processed_timestamp
    state["current_chunk_count"] = chunk_index
    state["usage_total"]["prompt_tokens"] += usage_total["prompt_tokens"]
    state["usage_total"]["completion_tokens"] += usage_total["completion_tokens"]
    state["summary_iterations"].extend(summary_iterations)
    state["chunk_records"].extend(chunk_records)
    return True


async def summarize(
    messages: List[Dict],
    model_id: str,
    user: Any,
    request: Request,
    is_user_model: bool,
    model_config: Optional[Dict],
    return_details: bool = False,
    summary_chars: int = 200,
) -> Union[str, Tuple[str, Dict[str, Any]]]:
    """
    生成对话摘要（新版：复用主对话 API）

    参数：
        messages: 需要摘要的消息列表
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
    prompt = build_summary_prompt(messages, summary_chars=summary_chars)

    # 2. 构造请求参数（OpenAI 格式）
    form_data = {
        "model": model_id or "gpt-4o-mini",  # 默认使用 gpt-4o-mini
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,  # 摘要不使用流式
        "max_tokens": 3000,  # 安全值，防止截断
        "temperature": 0.1,  # 低温度保证稳定性
    }

    effective_model_id = form_data["model"]
    if not is_user_model:
        global_api_config = _get_global_api_config(request)
        if global_api_config:
            effective_model_id = global_api_config["model_id"]
            form_data["model"] = effective_model_id

    model_id = effective_model_id
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

        # 6. Normalize summary content
        summary = _normalize_summary(payload)
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
        status_code = getattr(response, "status_code", None)
        content_type = getattr(response, "media_type", None)
        if content_type is None and hasattr(response, "headers"):
            content_type = response.headers.get("content-type")

        log.error(
            "Summary LLM error response: type=%s status=%s content_type=%s body=%s",
            type(response).__name__,
            status_code,
            content_type,
            error_body,
        )

        raise CustmizedError(
            user_toast_message = "梳理记忆失败，请联系管理员。",
            cause = RuntimeError(error_body)
        )


async def summarize_multi_chunk(
    chunks: List[List[Dict]],
    model_id: str,
    user: Any,
    request: Request,
    is_user_model: bool,
    model_config: Optional[Dict],
    summary_chars: int = 200,
) -> List[Dict[str, Any]]:
    """
    并行分段摘要生成器 - 基于已分段消息生成摘要

    处理流程：
    1. 并发对每一段调用 summarize
    2. 返回分段摘要列表（含原始 messages/usage/prompt/response）

    参数：
        chunks: 已分段的消息列表（按时间从旧到新排序）
        model_id: 模型 ID
        user: 用户对象
        request: FastAPI Request 对象
        is_user_model: 是否为用户私有模型
        model_config: 模型配置

    返回：
        分段摘要列表
    """
    import asyncio

    # 0. 空消息检查
    if not chunks:
        log.warning("并行摘要跳过：无分段消息")
        return []

    total_tokens = sum(compute_token_count(chunk) for chunk in chunks)
    log.info(
        f"开始并行摘要: total_tokens={total_tokens}, "
        f"messages_count={sum(len(chunk) for chunk in chunks)}, chunks={len(chunks)}, "
        f"is_user_model={is_user_model}"
    )

    # 3. 并发对每一段调用 summarize
    async def summarize_chunk(chunk_idx: int, chunk: List[Dict]) -> Tuple[int, str, Dict]:
        """对单个分段进行摘要"""
        try:
            summary_text, details = await summarize(
                messages=chunk,
                model_id=model_id,
                user=user,
                request=request,
                is_user_model=is_user_model,
                model_config=model_config,
                return_details=True,
                summary_chars=summary_chars,
            )
            log.info(
                f"并行摘要第 {chunk_idx + 1}/{len(chunks)} 段完成: "
                f"messages={len(chunk)}, "
                f"prompt_tokens={details.get('usage', {}).get('prompt_tokens', 0)}, "
                f"completion_tokens={details.get('usage', {}).get('completion_tokens', 0)}"
            )
            return chunk_idx, summary_text, details
        except Exception as e:
            if isinstance(e, CustmizedError):
                log.error(
                    "并行摘要第 %s 段失败: %s; debug_log=%s",
                    chunk_idx + 1,
                    e.user_toast_message,
                    e.debug_log,
                )
            else:
                log.error(
                    "并行摘要第 %s 段失败: %s",
                    chunk_idx + 1,
                    e,
                    exc_info=True,
                )
            raise

    # 并发执行所有分段的摘要
    tasks = [summarize_chunk(i, chunk) for i, chunk in enumerate(chunks)]
    results = await asyncio.gather(*tasks)

    # 4. 按顺序整理结果（按时间顺序：从旧到新）
    results_sorted = sorted(results, key=lambda x: x[0])
    chunk_summaries: List[Dict[str, Any]] = []

    for chunk_idx, summary_text, details in results_sorted:
        usage = details.get("usage", {})
        chunk_summaries.append(
            {
                "summary": summary_text,
                "messages": chunks[chunk_idx],
                "prompt": details.get("prompt", ""),
                "response": details.get("response", ""),
                "usage": usage,
                "model": details.get("model", model_id),
            }
        )

    return chunk_summaries

def messages_loaded(
    request: Request,
    metadata,
    user,
    memory_enabled: bool,
    perf_logger: Optional[ChatPerfLogger] = None,
):
    """
    同步上下文加载函数（滚动摘要版本）

    策略：
    1. 提取最近 N 条用户消息
    2. 加载最近至少 CURRENT_CONTEXT_MINIAL_MESSAGE 条消息，满足最小条数后继续追加，
       直到加入第一条使总 token 超过 CURRENT_CONTEXT_TOKEN_BUDGET 的消息
    3. 根据窗口最旧消息的时间获取该 chat 的 latest_summary
    4. 检索最相关的摘要（limit+1 后去重 latest_summary）
    5. 构建 system prompt（memory + latest_summary）
    6. 组装最终消息列表

    返回：
        [system_message, ...recent_messages]
    """
    chat_id = metadata.get("chat_id", None)
    user_id = user.id

    # 1. 获取当前聊天的消息
    messages_map = Chats.get_messages_map_by_chat_id(chat_id) or {}
    current_message_id = metadata.get("message_id")
    ordered_messages_in_chat = build_ordered_messages(messages_map, current_message_id)
    ordered_messages_in_chat = apply_content_transform_to_messages(
        messages = ordered_messages_in_chat,
        transform = strip_details_blocks,
    )

    # 2. 提取最近 N 条用户消息（用于检索）
    recent_user_messages = []
    for msg in reversed(ordered_messages_in_chat):
        if msg.get("role") == "user":
            content = _extract_text_content(msg.get("content", ""))
            if content:
                recent_user_messages.append(content)
                if len(recent_user_messages) >= SUMMARY_RETRIEVAL_USER_MESSAGE_COUNT:
                    break
    recent_user_messages = list(reversed(recent_user_messages))
    retrieval_query = "\n".join(recent_user_messages).strip()

    store = SummaryChromaStore(request, user_id, chat_id)

    # 3. 加载最近至少 CURRENT_CONTEXT_MINIAL_MESSAGE 条消息，满足最小条数后继续追加，
    #    直到加入第一条使总 token 超过 CURRENT_CONTEXT_TOKEN_BUDGET 的消息
    token_budget = CURRENT_CONTEXT_TOKEN_BUDGET
    min_message_count = max(CURRENT_CONTEXT_MINIAL_MESSAGE, 0)
    token_count = 0
    window = []
    for msg in reversed(ordered_messages_in_chat):
        if len(window) >= min_message_count and token_count > token_budget:
            break
        next_tokens = compute_token_count([msg])
        token_count += next_tokens
        window.append(msg)
        if len(window) >= min_message_count and token_count > token_budget:
            break
    recent_conversation_in_this_chat = list(reversed(window))

    # 移除旧的 system 消息
    recent_conversation_in_this_chat = [
        m for m in recent_conversation_in_this_chat if m.get("role") != "system"
    ]

    # 4. 根据窗口最旧消息时间寻找该 chat 的 latest_summary
    latest_summary_item_id = None
    latest_summary = {
        "timestamp": "未知",
        "start_timestamp": 0,
        "end_timestamp": 0,
        "start_time": "未知",
        "end_time": "未知",
        "content": "（暂无最近摘要）",
        "is_same_chat": True,
    }
    latest_summary_error = None
    latest_summary_found = False
    latest_summary_source = "none"
    oldest_message_timestamp = (
        _get_message_timestamp_or_zero(recent_conversation_in_this_chat[0])
        if recent_conversation_in_this_chat
        else 0
    )
    if oldest_message_timestamp and store.is_ready():
        try:
            summary_items = store.get_all()
            if summary_items:
                in_range = []
                before = []
                for item in summary_items:
                    metadata_item = item.get("metadata", {}) or {}
                    start_ts = int(metadata_item.get("start_timestamp") or 0)
                    end_ts = int(metadata_item.get("end_timestamp") or 0)
                    if start_ts and end_ts and start_ts <= oldest_message_timestamp <= end_ts:
                        in_range.append((start_ts, item))
                    elif end_ts and end_ts <= oldest_message_timestamp:
                        before.append((end_ts, item))

                chosen_item = None
                if in_range:
                    chosen_item = max(in_range, key=lambda x: x[0])[1]
                elif before:
                    chosen_item = max(before, key=lambda x: x[0])[1]

                if chosen_item:
                    metadata_item = chosen_item.get("metadata", {}) or {}
                    start_ts = int(metadata_item.get("start_timestamp") or 0)
                    end_ts = int(metadata_item.get("end_timestamp") or 0)
                    latest_summary = {
                        "timestamp": _format_timestamp_range(start_ts, end_ts),
                        "start_timestamp": start_ts,
                        "end_timestamp": end_ts,
                        "start_time": _format_timestamp(start_ts),
                        "end_time": _format_timestamp(end_ts),
                        "content": chosen_item.get("document", ""),
                        "is_same_chat": True,
                    }
                    latest_summary_item_id = chosen_item.get("id")
                    latest_summary_found = True
                    latest_summary_source = "current_chat"
        except Exception as e:
            latest_summary_error = str(e)
            log.warning(f"latest_summary 获取失败: {e}")

    # 4.5 当前 chat 无 summary 时，回退到全局最近的 summary（memory_enabled=True）
    if not latest_summary_found and memory_enabled:
        try:
            chat_list = Chats.get_chat_title_id_list_by_user_id(
                user_id,
                include_archived=True,
                include_folders=True,
                include_pinned=True,
            )
            latest_item = None
            latest_ts = 0
            for chat in chat_list:
                other_chat_id = getattr(chat, "id", None)
                if not other_chat_id and isinstance(chat, dict):
                    other_chat_id = chat.get("id")
                if not other_chat_id:
                    continue

                other_store = store if other_chat_id == chat_id else SummaryChromaStore(
                    request, user_id, other_chat_id
                )
                if not other_store.is_ready():
                    continue

                for item in other_store.get_all():
                    metadata_item = item.get("metadata", {}) or {}
                    end_ts = int(metadata_item.get("end_timestamp") or 0)
                    start_ts = int(metadata_item.get("start_timestamp") or 0)
                    ts = end_ts or start_ts
                    if ts > latest_ts:
                        latest_ts = ts
                        latest_item = item

            if latest_item:
                metadata_item = latest_item.get("metadata", {}) or {}
                start_ts = int(metadata_item.get("start_timestamp") or 0)
                end_ts = int(metadata_item.get("end_timestamp") or 0)
                latest_summary = {
                    "timestamp": _format_timestamp_range(start_ts, end_ts),
                    "start_timestamp": start_ts,
                    "end_timestamp": end_ts,
                    "start_time": _format_timestamp(start_ts),
                    "end_time": _format_timestamp(end_ts),
                    "content": latest_item.get("document", ""),
                    "is_same_chat": False,
                }
                latest_summary_item_id = latest_item.get("id")
                latest_summary_found = True
                latest_summary_source = "user_chats"
        except Exception as e:
            latest_summary_error = latest_summary_error or str(e)
            log.warning(f"latest_summary 全局获取失败: {e}")

    # 5. 检索最相关的摘要（如果有最近用户消息且 embedding 功能可用）
    retrieved_summaries = []
    query_embedding = None
    retrieval_results = []
    retrieval_error = None
    if retrieval_query and hasattr(request.app.state, "EMBEDDING_FUNCTION") and store.is_ready():
        try:
            # 生成查询 embedding
            embedding_function = request.app.state.EMBEDDING_FUNCTION
            query_embedding = embedding_function(retrieval_query, user=user)

            retrieval_limit = SUMMARY_RETRIEVAL_LIMIT + 1
            if memory_enabled:
                retrieval_results = store.search_in_user_chats(
                    request,
                    query_embedding,
                    retrieval_limit,
                )
            else:
                retrieval_results = store.search_in_chat(
                    query_embedding,
                    retrieval_limit,
                )

            # 提取摘要内容，并去除 latest_summary
            if retrieval_results:
                filtered_results = []
                for item in retrieval_results:
                    if latest_summary_item_id and item.get("id") == latest_summary_item_id:
                        continue
                    filtered_results.append(item)
                    summary_text = item.get("document", "")
                    metadata_item = item.get("metadata", {})
                    start_timestamp = metadata_item.get("start_timestamp", 0)
                    end_timestamp = metadata_item.get("end_timestamp", 0)

                    retrieved_summaries.append(
                        {
                            "start_timestamp": int(start_timestamp or 0),
                            "end_timestamp": int(end_timestamp or 0),
                            "start_time": _format_timestamp(int(start_timestamp or 0)),
                            "end_time": _format_timestamp(int(end_timestamp or 0)),
                            "is_same_chat": bool(
                                metadata_item.get("chat_id")
                                and chat_id
                                and metadata_item.get("chat_id") == chat_id
                            ),
                            "content": summary_text,
                        }
                    )
                    if len(retrieved_summaries) >= SUMMARY_RETRIEVAL_LIMIT:
                        break

                retrieval_results = filtered_results[:SUMMARY_RETRIEVAL_LIMIT]
                log.info(f"检索到 {len(retrieved_summaries)} 个相关摘要")
        except Exception as e:
            retrieval_error = str(e)
            log.warning(f"摘要检索失败: {e}")

    # 5. 构建 system prompt
    system_content = SUMMARY_SYSTEM_PROMPT_TEMPLATE.render(
        searched_summaries=retrieved_summaries,
        latest_summary=latest_summary,
    )

    summary_system_message = {
        "role": "system",
        "content": system_content
    }

    # 6. 组装最终消息列表
    ordered_messages = [summary_system_message, *recent_conversation_in_this_chat]

    # 合并连续的同角色消息，避免 LLM API 报错
    ordered_messages = merge_consecutive_messages(ordered_messages)

    if perf_logger:
        perf_logger.record_messages_loaded(
            summary_system_message=summary_system_message,
            recent_conversation_in_this_chat=recent_conversation_in_this_chat,
            extra={
                "chat_id": chat_id,
                "user_id": user_id,
                "current_message_id": current_message_id,
                "messages_map_size": len(messages_map),
                "ordered_messages_in_chat": ordered_messages_in_chat,
                "retrieved_summaries": retrieved_summaries,
                "latest_summary": latest_summary,
                "latest_summary_error": latest_summary_error,
                "oldest_message_timestamp": oldest_message_timestamp,
                "latest_summary_source": latest_summary_source,
                "retrieval": {
                    "collection_name": store.collection_name,
                    "limit": SUMMARY_RETRIEVAL_LIMIT + 1,
                    "results": retrieval_results,
                    "error": retrieval_error,
                },
                "retrieved_summaries_count": len(retrieved_summaries),
                "recent_messages_count": len(recent_conversation_in_this_chat),
                "token_budget": token_budget,
                "min_message_count": min_message_count,
                "token_count": token_count,
                "ordered_messages": ordered_messages,
            },
        )

    return ordered_messages

def build_bootstrap_chunks(
    messages: List[Dict],
    token_limits: Sequence[int],
) -> List[List[Dict]]:
    """
    按 token_limits 从旧到新切分 bootstrap 摘要 chunk。

    规则：
    1) 依次按 token_limits 切分；
    2) 单条消息超过阈值时，强制取出；
    3) 超出策略的剩余消息合并到最后一个 chunk。
    """
    if not messages:
        return []

    remaining = list(messages)
    chunks: List[List[Dict]] = []
    for max_tokens in token_limits:
        if not remaining:
            break
        chunk, remaining = split_messages_by_tokens(remaining, max_tokens)
        if not chunk and remaining:
            log.warning("update_summary: bootstrap 单条消息超过阈值，强制取出")
            chunk = [remaining.pop(0)]
        if chunk:
            chunks.append(chunk)

    if remaining:
        if chunks:
            log.warning(
                "update_summary: bootstrap 分段策略不足，剩余消息合并到最后一个 chunk"
            )
            chunks[-1].extend(remaining)
        else:
            chunks = [remaining]

    return chunks

def _init_state(prev_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    prev_state = prev_state if isinstance(prev_state, dict) else {}
    usage_total = prev_state.get("usage_total")
    if not isinstance(usage_total, dict):
        usage_total = {}
    return {
        "error_status": prev_state.get("error_status"),
        "error_message": prev_state.get("error_message"),
        "processed_message_count": int(prev_state.get("processed_message_count", 0) or 0),
        "last_processed_msg": None,
        "last_processed_timestamp": int(
            prev_state.get("last_summarized_timestamp", 0) or 0
        ),
        "current_chunk_count": int(prev_state.get("current_chunk_count", 0) or 0),
        "usage_total": {
            "prompt_tokens": int(usage_total.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage_total.get("completion_tokens", 0) or 0),
        },
        "summary_iterations": [],
        "chunk_records": [],
    }

def _build_summary_state(
    prev_state: Optional[Dict[str, Any]],
    state: Dict[str, Any],
    status: str,
    task_id: Optional[str],
) -> Dict[str, Any]:
    prev_state = prev_state if isinstance(prev_state, dict) else {}
    # last_processed_ts: 本轮摘要覆盖的最后一条消息时间戳
    last_processed_ts = state.get("last_processed_timestamp")
    # last_ts: 写回的摘要边界时间戳，用于下次滚动摘要的起点
    last_ts = int(
        last_processed_ts
        or prev_state.get("last_summarized_timestamp", 0)
        or 0
    )
    # last_msg_id: 写回的摘要边界消息 ID，用于下次滚动摘要的起点
    last_msg_id = prev_state.get("last_summarized_message_id", "") or ""
    # last_msg: 本轮处理的最后一条消息对象（用于更新边界 ID）
    last_msg = state.get("last_processed_msg")
    if isinstance(last_msg, dict) and last_msg.get("id"):
        last_msg_id = last_msg.get("id")

    # usage_total: 累计的 token 使用情况（跨多段摘要）
    usage_total = state.get("usage_total")
    if not isinstance(usage_total, dict):
        usage_total = prev_state.get("usage_total")
    if not isinstance(usage_total, dict):
        usage_total = {"prompt_tokens": 0, "completion_tokens": 0}

    return {
        # status: generating/done，用于并发互斥与状态展示
        "status": status,
        # task_id: 后台摘要任务 ID，便于追踪
        "task_id": task_id,
        # last_summarized_timestamp: 下一次滚动摘要的时间边界
        "last_summarized_timestamp": last_ts,
        # last_summarized_message_id: 下一次滚动摘要的消息边界
        "last_summarized_message_id": last_msg_id,
        # current_chunk_count: 已写入向量库的摘要分段总数
        "current_chunk_count": int(
            state.get("current_chunk_count")
            or prev_state.get("current_chunk_count", 0)
            or 0
        ),
        # processed_message_count: 累计已摘要的消息条数
        "processed_message_count": int(
            state.get("processed_message_count")
            or prev_state.get("processed_message_count", 0)
            or 0
        ),
        # usage_total: 摘要调用累计消耗的 prompt/completion token
        "usage_total": {
            "prompt_tokens": int(usage_total.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage_total.get("completion_tokens", 0) or 0),
        },
        # error_status/error_message: 上次错误信息，便于排查
        "error_status": state.get("error_status"),
        "error_message": state.get("error_message"),
        # updated_at: summary_state 最近更新时间
        "updated_at": int(time.time()),
    }

async def update_summary(
    request: Request,
    metadata,
    user,
    model,
    is_user_model,
):
    """
    异步摘要生成函数（精简逻辑）

    规则：
    1) chat.meta 无 summary_state -> bootstrap summarize 并初始化 summary_state。
    2) chat.meta 有 summary_state -> 滚动摘要 last_summarized_timestamp 之后的消息。
    3) 滚动触发条件：
       - 消息数 >= SUMMARY_MESSAGE_THRESHOLD 或 token 数 >= SUMMARY_TOKEN_THRESHOLD；
       - 且消息数 >= SUMMARY_SUBCHUNK_MIN_MESSAGES。
    4) bootstrap：无历史消息直接结束；有消息按 [90000, 10000, 10000] 分段摘要。
    """
    perf_logger: Optional[ChatPerfLogger] = metadata.get("perf_logger")
    chat_id = metadata.get("chat_id")
    user_id = user.id

    # 1) 获取聊天和消息
    chat_item = Chats.get_chat_by_id_and_user_id(chat_id, user_id)
    if not chat_item:
        log.warning(f"update_summary: 聊天不存在 chat_id={chat_id}")
        return

    messages_map = Chats.get_messages_map_by_chat_id(chat_id) or {}
    ordered_messages = build_ordered_messages(messages_map, None)
    ordered_messages = apply_content_transform_to_messages(
        messages = ordered_messages,
        transform = strip_details_blocks,
    )

    # 2) 读取 summary_state
    meta = chat_item.meta if isinstance(chat_item.meta, dict) else {}
    summary_state = meta.get("summary_state") if isinstance(meta, dict) else None
    summary_state = summary_state if isinstance(summary_state, dict) else None

    # 摘要依赖向量库与 embedding；缺失则跳过避免无效任务
    store = SummaryChromaStore(request, user_id, chat_id)
    embedding_function = getattr(request.app.state, "EMBEDDING_FUNCTION", None)
    if not store.is_ready() or not embedding_function:
        log.warning("update_summary: 向量库或 embedding 未就绪，跳过摘要")
        return

    # 若已有生成中的任务，避免并发重复摘要
    if summary_state and summary_state.get("status") == "generating":
        log.info("update_summary: 摘要任务进行中，跳过本轮")
        return

    # 摘要仅处理 user/assistant 消息，避免 system/tool 噪声进入摘要
    ordered_messages = [
        msg for msg in ordered_messages if msg.get("role") in ("user", "assistant")
    ]

    model_id = model.get("id") if model else None
    model_config = model

    # 生成最终写回 chat.meta.summary_state 的结构
    # 统一的后台摘要执行逻辑：生成摘要 -> 写向量库 -> 更新 summary_state
    async def _summarize_and_store(
        *,
        chunks: List[List[Dict[str, Any]]],
        chunk_types: List[str],
        prev_state: Optional[Dict[str, Any]],
        mode: str,
        summary_chars: int,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        state = _init_state(prev_state)
        state["error_status"] = None
        state["error_message"] = None
        chunk_summaries: List[Dict[str, Any]] = []
        error = None

        async with chat_error_boundary(metadata, user):
            try:
                # 1) 并行生成各分段摘要
                chunk_summaries = await summarize_multi_chunk(
                    chunks=chunks,
                    model_id=model_id,
                    user=user,
                    request=request,
                    is_user_model=is_user_model,
                    model_config=model_config,
                    summary_chars=summary_chars,
                )
                # 2) 记录分段类型（bootstrap/rolling/subchunk）
                for idx, summary_info in enumerate(chunk_summaries):
                    if idx < len(chunk_types):
                        summary_info["chunk_type"] = chunk_types[idx]

                if perf_logger:
                    perf_logger.record_summary_runs(mode, chunk_summaries)

                # 3) 生成 embedding 并写入向量库，同时更新统计状态
                stored = store_summary_chunks(
                    chunk_summaries,
                    embedding_function=embedding_function,
                    store=store,
                    chat_id=chat_id,
                    user_id=user_id,
                    user=user,
                    state=state,
                )
                if not stored and not state.get("error_status"):
                    state["error_status"] = "store_error"
            except Exception as e:
                error = e
                state["error_status"] = state.get("error_status") or "summary_error"
                state["error_message"] = str(e)
            finally:
                # 4) 无论成功/失败，都写回 summary_state 以记录边界与统计
                summary_state_payload = _build_summary_state(
                    prev_state, state, "done", task_id=""
                )
                Chats.update_chat_meta(chat_id, user_id, {"summary_state": summary_state_payload})

                if perf_logger:
                    await perf_logger.save_to_file()

            if error:
                raise error

    # === Bootstrap 摘要：第一次进入该 chat 时生成初始摘要 ===
    if not summary_state:
        bootstrap_messages = _strip_pending_pair(
            ordered_messages,
            metadata=metadata,
            messages_map=messages_map,
        )
        # 没有历史消息则只落状态，不生成摘要
        if not bootstrap_messages:
            empty_state = _init_state({})
            summary_state_payload = _build_summary_state(
                {}, empty_state, "done", task_id=""
            )
            Chats.update_chat_meta(chat_id, user_id, {"summary_state": summary_state_payload})
            return
        # 新窗口首轮对话（仅 user+assistant 两条）不做摘要，但写入状态防止重复 bootstrap
        if len(bootstrap_messages) <= 2:
            empty_state = _init_state({})
            summary_state_payload = _build_summary_state(
                {}, empty_state, "done", task_id=""
            )
            Chats.update_chat_meta(chat_id, user_id, {"summary_state": summary_state_payload})
            return

        # 按 BOOTSTRAP_SUMMARY_CHUNK_STRATEGY 切分历史消息
        bootstrap_chunks = build_bootstrap_chunks(
            bootstrap_messages, BOOTSTRAP_SUMMARY_CHUNK_STRATEGY
        )
        if not bootstrap_chunks:
            return

        # 标记为 bootstrap chunk，供入库与审计区分
        bootstrap_chunk_types = ["bootstrap"] * len(bootstrap_chunks)
        extra = None
        if perf_logger:
            total_tokens = sum(compute_token_count(chunk) for chunk in bootstrap_chunks)
            extra = {
                "messages": len(bootstrap_messages),
                "tokens": total_tokens,
                "chunks": len(bootstrap_chunks),
            }

        # 启动后台任务执行 bootstrap 摘要
        summarize_task_id, _ = await create_task(
            request.app.state.redis,
            _summarize_and_store(
                chunks=bootstrap_chunks,
                chunk_types=bootstrap_chunk_types,
                prev_state=summary_state,
                mode="bootstrap",
                summary_chars=BOOTSTRAP_SUMMARY_TARGET_CHARS,
                extra=extra,
            ),
            id=chat_id,
        )

        # 标记为生成中，防止并发重复启动
        pending_state = _init_state(summary_state)
        pending_state["error_status"] = None
        pending_state["error_message"] = None
        summary_state_payload = _build_summary_state(
            summary_state, pending_state, "generating", task_id=summarize_task_id
        )
        Chats.update_chat_meta(chat_id, user_id, {"summary_state": summary_state_payload})
        return

    # === Rolling 摘要：基于上次摘要边界只处理新增消息 ===
    last_summary_msg_id = summary_state.get("last_summarized_message_id")
    if last_summary_msg_id:
        new_messages = []
        found = False
        for msg in ordered_messages:
            if found:
                new_messages.append(msg)
            elif msg.get("id") == last_summary_msg_id:
                found = True
        if not found:
            # 若找不到上次 message_id，则回退到 timestamp 边界
            last_ts = int(summary_state.get("last_summarized_timestamp", 0) or 0)
            new_messages = [
                msg
                for msg in ordered_messages
                if _get_message_timestamp(msg) > last_ts
            ]
    else:
        # 只有 timestamp 边界时，按时间过滤新增消息
        last_ts = int(summary_state.get("last_summarized_timestamp", 0) or 0)
        new_messages = [
            msg
            for msg in ordered_messages
            if _get_message_timestamp(msg) > last_ts
        ]

    # 无新增消息，不做摘要
    if not new_messages:
        return

    message_count = len(new_messages)
    # 即使 token 达标也要满足最小消息数，防止过短摘要抖动
    if message_count < SUMMARY_SUBCHUNK_MIN_MESSAGES:
        return
    token_count = compute_token_count(new_messages)
    # 触发条件：消息数或 token 数超过阈值
    if message_count < SUMMARY_MESSAGE_THRESHOLD and token_count < SUMMARY_TOKEN_THRESHOLD:
        return

    # 滚动摘要不再二次切分，直接把窗口作为一个 chunk
    chunks = [new_messages]
    chunk_types = ["rolling"]
    discarded_chunks = 0
    discarded_messages = 0
    if not chunks:
        return

    extra = {
        "messages": message_count,
        "tokens": token_count,
        "chunks": len(chunks),
        "discarded_chunks": discarded_chunks,
        "discarded_messages": discarded_messages,
    }

    # 启动后台任务执行滚动摘要
    summarize_task_id, _ = await create_task(
        request.app.state.redis,
        _summarize_and_store(
            chunks=chunks,
            chunk_types=chunk_types,
            prev_state=summary_state,
            mode="rolling",
            summary_chars=ROLLING_SUMMARY_TARGET_CHARS,
            extra=extra,
        ),
        id=chat_id,
    )

    # 写入生成中状态，避免并发重复更新
    pending_state = _init_state(summary_state)
    pending_state["error_status"] = None
    pending_state["error_message"] = None
    summary_state_payload = _build_summary_state(
        summary_state, pending_state, "generating", task_id=summarize_task_id
    )
    Chats.update_chat_meta(chat_id, user_id, {"summary_state": summary_state_payload})

# bootstrap summarize
# - BOOTSTRAP_SUMMARY_CHUNK_STRATEGY（90000,10000,10000）：首次 bootstrap 摘要时按 token 上限切分历史消息的策略。

# load message
# - SUMMARY_RETRIEVAL_LIMIT（3）：检索注入的摘要数量上限（用于 searched_summaries）。
# - SUMMARY_RETRIEVAL_USER_MESSAGE_COUNT（4）：检索摘要时使用的最近用户消息条数（拼成检索查询）。
# - CURRENT_CONTEXT_MINIAL_MESSAGE（4）：当前上下文最少保留的消息条数。
# - CURRENT_CONTEXT_TOKEN_BUDGET（3000）：当前上下文窗口的 token 预算上限。

# rolling summarize
# - SUMMARY_MESSAGE_THRESHOLD（12）：滚动摘要触发的消息条数阈值。
# - SUMMARY_TOKEN_THRESHOLD（5000）：滚动摘要触发的 token 数阈值。
# - SUMMARY_SUBCHUNK_MIN_MESSAGES（2）：即使 token 超限，滚动摘要也必须满足的最小消息数。
