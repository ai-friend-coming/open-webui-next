from typing import Dict, List, Optional, Tuple, Sequence, Any
import json
import re
import os
from dataclasses import dataclass
from logging import getLogger

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from open_webui.models.chats import Chats
from open_webui.config import OPENAI_API_KEYS, OPENAI_API_BASE_URLS

# Import for calling main chat API
from fastapi import Request

log = getLogger(__name__)

# --- Constants & Prompts from persona_extractor ---

SUMMARY_PROMPT = """你是一名“对话历史整理员”，请在保持事实准确的前提下，概括当前为止的聊天记录。
## 要求
1. 最终摘要不得超过 1000 字。
2. 聚焦人物状态、事件节点、情绪/意图等关键信息，将片段整合为连贯文字。
3. 输出需包含 who / how / why / what 四个字段，每项不超过 50 字。
4. 禁止臆测或脏话，所有内容都必须能在聊天中找到对应描述。
5. 目标：帮助后续对话快速回忆上下文与人物设定。

已存在的摘要（如无则写“无”）：
{existing_summary}

聊天片段：
---CHATS---
{chat_transcript}
---END---

请严格输出下列 JSON：
{{
  "summary": "不超过1000字的连贯摘要",
  "table": {{
    "who": "不超过50字",
    "how": "不超过50字",
    "why": "不超过50字",
    "what": "不超过50字"
  }}
}}
"""

MERGE_ONLY_PROMPT = """你是一名“对话历史整理员”。
请将以下两段对话摘要（A 和 B）合并为一段连贯的、更新后的对话历史摘要。
摘要 A 是较早的时间段，摘要 B 是较新的时间段。

【摘要 A (旧)】
{summary_a}

【摘要 B (新)】
{summary_b}

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

@dataclass
class HistorySummary:
    summary: str
    table: dict[str, str]

@dataclass(slots=True)
class ChatMessage:
    role: str
    content: str
    timestamp: Optional[Any] = None
    
    def formatted(self) -> str:
        return f"{self.role}: {self.content}"

class HistorySummarizer:
    def __init__(
        self,
        *,
        client: Optional[Any] = None,
        model: str = "gpt-4.1-mini",
        max_output_tokens: int = 800,
        temperature: float = 0.1,
        max_messages: int = 120,
    ) -> None:
        if client is None:
            if OpenAI is None:
                log.warning("OpenAI client not available. Install openai>=1.0.0.")
            else:
                try:
                    # 尝试从配置获取 API Key 和 Base URL
                    from open_webui.config import OPENAI_API_CONFIGS
                    
                    api_keys = OPENAI_API_KEYS.value if hasattr(OPENAI_API_KEYS, "value") else []
                    base_urls = OPENAI_API_BASE_URLS.value if hasattr(OPENAI_API_BASE_URLS, "value") else []
                    configs = OPENAI_API_CONFIGS.value if hasattr(OPENAI_API_CONFIGS, "value") else {}
                    
                    api_key = None
                    base_url = None
                    
                    # 1. 尝试从 OPENAI_API_CONFIGS 中查找模型对应的配置
                    if configs:
                        for key, config in configs.items():
                            # 检查模型是否在该配置的模型列表中
                            if model in config.get("model_ids", []):
                                try:
                                    idx = int(key)
                                    if idx < len(api_keys):
                                        api_key = api_keys[idx]
                                    if idx < len(base_urls):
                                        base_url = base_urls[idx]
                                    log.info(f"Using config for model {model}: base_url={base_url}")
                                    break
                                except ValueError:
                                    pass
                    
                    # 2. 如果没找到特定配置，回退到默认（第一个）配置
                    if not api_key:
                        api_key = api_keys[0] if api_keys else os.environ.get("OPENAI_API_KEY")
                        
                    if not base_url:
                        base_url = base_urls[0] if base_urls else os.environ.get("OPENAI_API_BASE_URL")
                    
                    if api_key:
                        kwargs = {"api_key": api_key}
                        if base_url:
                            kwargs["base_url"] = base_url
                        client = OpenAI(**kwargs)
                    else:
                        log.warning("No OpenAI API key found.")

                except Exception as e:
                    log.warning(f"Failed to init OpenAI client: {e}")
        
        self._client = client
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._max_messages = max_messages

    def summarize(
        self,
        messages: Sequence[Dict],
        *,
        existing_summary: Optional[str] = None,
        max_tokens: Optional[int] = None,
        user: Optional[Any] = None,
    ) -> Optional[HistorySummary]:
        if not messages and not existing_summary:
            return None
        
        # 转换 dict 消息为 ChatMessage 格式用于 prompt 生成
        # 确保消息按时间戳排序，防止乱序导致切片错误
        sorted_messages = sorted(messages, key=lambda m: m.get('timestamp', 0) if isinstance(m.get('timestamp'), (int, float)) else 0)
        
        # 如果有 existing_summary，我们可以适当减少这里的消息量，或者依然取最近的
        # 但为了逻辑简单，我们还是取最近的 max_messages
        trail = sorted_messages[-self._max_messages :]
        transcript = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in trail)
        
        prompt = SUMMARY_PROMPT.format(
            existing_summary=existing_summary.strip() if existing_summary else "无",
            chat_transcript=transcript,
        )
        
        if not self._client:
            log.error("No OpenAI client available for summarization.")
            return None

        log.info(f"Starting summary generation for {len(messages)} messages...")
        
        # Try primary client first
        try:
            # 增加 max_tokens 限制，避免摘要过长被截断，同时留给 JSON 结构足够的空间
            # 根据经验，1000 字摘要 + JSON 结构大约需要 1500 tokens
            safe_max_tokens = max(max_tokens or self._max_output_tokens, 2000)
            
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=safe_max_tokens,
                temperature=self._temperature,
            )
            
            # Debug: Print full response to investigate empty content issues
            log.info(f"Full Summary API Response: {response}")

            # === 计费逻辑接入 ===
            if user and hasattr(response, "usage") and response.usage:
                try:
                    from open_webui.utils.billing import deduct_balance
                    
                    # 确定用户ID
                    user_id = getattr(user, "id", str(user))
                    
                    usage = response.usage
                    prompt_tokens = usage.prompt_tokens
                    completion_tokens = usage.completion_tokens
                    
                    cost, balance = deduct_balance(
                        user_id=user_id,
                        model_id=self._model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        log_type="deduct_summary"  # 标记为摘要扣费
                    )
                    
                    log.info(
                        f"摘要生成计费成功: user={user_id} model={self._model} "
                        f"tokens={prompt_tokens}+{completion_tokens} "
                        f"cost={cost / 10000:.4f}元 balance={balance / 10000:.4f}元"
                    )
                except Exception as e:
                    # 计费失败不应中断摘要生成，只记录日志
                    log.error(f"摘要生成计费失败: {e}")
            # ===================

            payload = response.choices[0].message.content or ""
            finish_reason = response.choices[0].finish_reason
            
            if finish_reason == "length":
                log.warning("Summary generation was truncated due to length limit!")
                
            log.info(f"Summary generation completed. Payload length: {len(payload)}")
            log.info(f"Summary Content:\n{payload}")
            
            return self._parse_response(payload)

        except Exception as e:
            log.warning(f"Summarization failed: {e}")
            return None

    def _parse_response(self, payload: str) -> HistorySummary:
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
            
        return HistorySummary(summary=summary, table=table)

    def merge_summaries(
        self,
        summary_a: str,
        summary_b: str,
        *,
        max_tokens: Optional[int] = None,
        user: Optional[Any] = None,
    ) -> Optional[HistorySummary]:
        if not summary_a and not summary_b:
            return None
            
        prompt = MERGE_ONLY_PROMPT.format(
            summary_a=summary_a or "无",
            summary_b=summary_b or "无",
        )
        
        if not self._client:
            return None

        log.info(f"Starting summary merge (A len={len(summary_a)}, B len={len(summary_b)})...")
        
        # Try primary client
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens or self._max_output_tokens,
                temperature=self._temperature,
            )
            
            # === 计费逻辑接入 ===
            if user and hasattr(response, "usage") and response.usage:
                try:
                    from open_webui.utils.billing import deduct_balance
                    
                    user_id = getattr(user, "id", str(user))
                    usage = response.usage
                    
                    cost, balance = deduct_balance(
                        user_id=user_id,
                        model_id=self._model,
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens,
                        log_type="deduct_summary_merge"
                    )
                    
                    log.info(
                        f"摘要合并计费成功: user={user_id} model={self._model} "
                        f"tokens={usage.prompt_tokens}+{usage.completion_tokens} "
                        f"cost={cost / 10000:.4f}元 balance={balance / 10000:.4f}元"
                    )
                except Exception as e:
                    log.error(f"摘要合并计费失败: {e}")
            # ===================

            payload = response.choices[0].message.content or ""
            log.info("Summary merge completed successfully.")
            return self._parse_response(payload)

        except Exception as e:
            log.warning(f"Merge failed: {e}")
            return None


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


def _parse_response(payload: str) -> HistorySummary:
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

    return HistorySummary(summary=summary, table=table)


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


def get_recent_messages_by_user_id(user_id: str, chat_id: str, num: int) -> List[Dict]:
    """
    获取指定用户的最近 N 条消息（优先当前会话，然后按时间顺序）

    参数：
        user_id: 用户 ID
        chat_id: 当前会话 ID（用于优先提取）
        num: 需要获取的消息数量（<= 0 时返回全部）

    返回：
        有序的消息列表（优先当前会话，不足时由全局最近补齐）
    """
    current_chat_messages: List[Dict] = []
    other_messages: List[Dict] = []

    # 遍历用户的所有聊天
    chats = Chats.get_chat_list_by_user_id(user_id, include_archived=True)
    for chat in chats:
        messages_map = chat.chat.get("history", {}).get("messages", {}) or {}
        # 简单判断是否为当前会话
        is_current_chat = (str(chat.id) == str(chat_id))

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
            
            if is_current_chat:
                current_chat_messages.append(entry)
            else:
                other_messages.append(entry)

    # 分别排序
    current_chat_messages.sort(key=lambda m: m.get("timestamp", 0))
    other_messages.sort(key=lambda m: m.get("timestamp", 0))

    if num <= 0:
        combined = current_chat_messages + other_messages
        combined.sort(key=lambda m: m.get("timestamp", 0))
        return combined

    # 策略：优先保留当前会话消息
    if len(current_chat_messages) >= num:
        return current_chat_messages[-num:]
    
    # 补充不足的部分
    needed = num - len(current_chat_messages)
    supplement = other_messages[-needed:] if other_messages else []
    
    # 合并并最终按时间排序
    final_list = supplement + current_chat_messages
    final_list.sort(key=lambda m: m.get("timestamp", 0))
    
    return final_list


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


async def summarize(
    messages: List[Dict],
    old_summary: Optional[str] = None,
    model_id: Optional[str] = None,
    user: Optional[Any] = None,
    request: Optional[Request] = None,
    is_user_model: bool = False,
    model_config: Optional[Dict] = None,
) -> str:
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
    """
    # 如果提供了 request，则使用新逻辑（调用主对话 API）
    if request is not None:
        return await _summarize_with_main_api(
            messages=messages,
            old_summary=old_summary,
            model_id=model_id,
            user=user,
            request=request,
            is_user_model=is_user_model,
            model_config=model_config,
        )
    else:
        # 向后兼容：使用旧逻辑（独立 OpenAI client）
        log.warning("使用旧的 summarize 逻辑（不推荐），建议传入 request 参数")
        summarizer = HistorySummarizer(model=model_id) if model_id else HistorySummarizer()
        result = summarizer.summarize(messages, existing_summary=old_summary, user=user)
        return result.summary if result else ""


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


async def _summarize_with_main_api(
    messages: List[Dict],
    old_summary: Optional[str],
    model_id: Optional[str],
    user: Any,
    request: Request,
    is_user_model: bool,
    model_config: Optional[Dict] = None,
) -> str:
    """
    使用主对话 API 生成摘要（内部函数）

    核心优势：
    1. 自动复用用户的 API 配置（base_url, api_key）
    2. 自动判断是否扣费（is_user_model=True 时不扣费）
    3. 使用当前会话的模型（而不是固定的 gpt-4.1-mini）
    4. 通过 request.state 直接传递已验证的模型配置,避免重复查找和验证
    """
    from open_webui.routers.openai import generate_chat_completion as generate_openai_chat_completion
    from starlette.responses import JSONResponse, Response

    # 0. 空消息检查
    if not messages and not old_summary:
        log.warning("摘要生成跳过：无消息且无旧摘要")
        return ""

    # 保存原始 request.state 值，用于后续恢复
    original_direct = getattr(request.state, "direct", None)
    original_model = getattr(request.state, "model", None)

    try:
        # 【关键】判断是否需要设置 direct 模式
        # - 只有当 model_config 中包含 base_url（真正的私有模型）时才设置 direct 模式
        # - 对于平台模型（只有 urlIdx），让 openai.py 走正常路径，通过 urlIdx 获取配置
        #   这样可以利用 openai.py 中的 Gemini/Azure 特殊处理逻辑
        if model_config and model_config.get("base_url"):
            # 私有模型路径：直接使用 model_config 中的 base_url 和 api_key
            request.state.direct = True
            request.state.model = model_config
            log.debug(f"摘要生成使用私有模型: {model_config.get('id', 'unknown')}, base_url={model_config.get('base_url')}")
        else:
            # 平台模型路径：不设置 direct，让 openai.py 自己查找模型配置
            # 这样可以：1. 通过 urlIdx 获取正确的 API 配置  2. 应用 Gemini/Azure 特殊处理
            log.debug(f"摘要生成使用平台模型: {model_id}")

        # 1. 构建摘要 prompt
        # 排序并截断消息（最近 120 条）
        sorted_messages = sorted(messages, key=lambda m: m.get('timestamp', 0) if isinstance(m.get('timestamp'), (int, float)) else 0)
        trail = sorted_messages[-120:]
        # 使用 _extract_text_content 处理多模态消息
        transcript = "\n".join(f"{m.get('role', 'user')}: {_extract_text_content(m.get('content', ''))}" for m in trail)

        prompt = SUMMARY_PROMPT.format(
            existing_summary=old_summary.strip() if old_summary else "无",
            chat_transcript=transcript,
        )

        # 2. 构造请求参数（OpenAI 格式）
        form_data = {
            "model": model_id or "gpt-4o-mini",  # 默认使用 gpt-4o-mini
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,  # 摘要不使用流式
            "max_tokens": 2000,  # 安全值，防止截断
            "temperature": 0.1,  # 低温度保证稳定性
            "is_user_model": is_user_model,  # ← 关键：用户模型标记（控制是否扣费）
        }

        log.info(f"开始生成摘要: model={model_id}, is_user_model={is_user_model}, messages_count={len(messages)}")

        # 3. 调用主对话 API
        response = await generate_openai_chat_completion(
            request=request,
            form_data=form_data,
            user=user,
            bypass_filter=True,  # 跳过权限检查（摘要是系统内部调用）
        )

        # 4. 解析响应（处理多种返回类型）
        if isinstance(response, dict):
            # 正常响应：直接是 dict
            payload = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            # 记录 usage 信息（调试用）
            usage = response.get("usage", {})
            log.info(
                f"摘要生成完成: model={model_id}, is_user_model={is_user_model}, "
                f"tokens={usage.get('prompt_tokens', 0)}+{usage.get('completion_tokens', 0)}, "
                f"payload_length={len(payload)}"
            )

            # 5. 解析 JSON 并提取摘要
            result = _parse_response(payload)
            return result.summary if result else ""

        elif isinstance(response, JSONResponse):
            # 错误响应：JSONResponse
            # 尝试从 body 中提取错误信息
            try:
                error_body = response.body.decode("utf-8") if hasattr(response, "body") else str(response)
                log.error(f"摘要 API 返回错误 (JSONResponse): status={response.status_code}, body={error_body[:500]}")
            except Exception:
                log.error(f"摘要 API 返回错误 (JSONResponse): status={response.status_code}")
            return ""

        elif isinstance(response, Response):
            # 其他 Response 类型
            log.error(f"摘要 API 返回意外响应类型: {type(response).__name__}, status={getattr(response, 'status_code', 'unknown')}")
            return ""

        else:
            log.error(f"摘要 API 返回格式错误: {type(response)}")
            return ""

    except Exception as e:
        log.error(f"摘要生成失败 (model={model_id}): {e}")
        # 不再使用后备模型，直接失败
        # 原因：用户希望摘要使用与主对话完全一致的模型，不应该回退到其他模型
        return ""

    finally:
        # 【重要】恢复 request.state，避免污染后续请求
        if original_direct is None:
            if hasattr(request.state, "direct"):
                delattr(request.state, "direct")
        else:
            request.state.direct = original_direct

        if original_model is None:
            if hasattr(request.state, "model"):
                delattr(request.state, "model")
        else:
            request.state.model = original_model

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
