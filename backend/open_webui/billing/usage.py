"""
统一的 Usage 解析模块

收拢所有 LLM API 返回的 usage 解析逻辑，支持：
- OpenAI 格式（含 prompt_tokens_details, completion_tokens_details）
- Claude 格式（含 cache_read_input_tokens, cache_creation_input_tokens）
- Gemini 格式（含 thoughts_token_count）

设计原则：
- 单一职责：只负责解析 usage，不涉及计费计算
- 兼容多格式：统一输出标准化的 UsageInfo
- 可扩展：新增 provider 只需添加解析逻辑
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Union, Dict, Any

log = logging.getLogger(__name__)


@dataclass
class UsageInfo:
    """
    标准化的 Usage 信息

    设计说明：
    - prompt_tokens: 输入 token（不含缓存）
    - completion_tokens: 输出 token（不含推理）
    - cached_tokens: 缓存命中的输入 token（计费通常为原价 10%）
    - reasoning_tokens: 推理/思考 token（如 o1, Claude thinking）
    - audio_input_tokens: 音频输入 token
    - audio_output_tokens: 音频输出 token
    - image_tokens: 图片 token（估算值）

    费用计算建议：
    - 输入费用 = (prompt_tokens + cached_tokens * cache_ratio) * input_price
    - 输出费用 = (completion_tokens + reasoning_tokens) * output_price
    """

    # 基础 token
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # 缓存 token（Claude Prompt Caching / OpenAI）
    cached_tokens: int = 0  # 缓存命中
    cache_creation_tokens: int = 0  # 缓存创建（首次写入）

    # 推理 token（o1, Claude thinking）
    reasoning_tokens: int = 0

    # 音频 token
    audio_input_tokens: int = 0
    audio_output_tokens: int = 0

    # 图片 token（估算）
    image_tokens: int = 0

    # 原始数据（用于调试）
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_prompt_tokens(self) -> int:
        """总输入 token（含缓存）"""
        return self.prompt_tokens + self.cached_tokens + self.cache_creation_tokens

    @property
    def total_completion_tokens(self) -> int:
        """总输出 token（含推理）"""
        return self.completion_tokens + self.reasoning_tokens

    @property
    def total_tokens(self) -> int:
        """总 token"""
        return self.total_prompt_tokens + self.total_completion_tokens

    def merge_max(self, other: "UsageInfo") -> None:
        """
        合并 usage（取最大值）

        用于流式响应中累积 usage
        """
        self.prompt_tokens = max(self.prompt_tokens, other.prompt_tokens)
        self.completion_tokens = max(self.completion_tokens, other.completion_tokens)
        self.cached_tokens = max(self.cached_tokens, other.cached_tokens)
        self.cache_creation_tokens = max(self.cache_creation_tokens, other.cache_creation_tokens)
        self.reasoning_tokens = max(self.reasoning_tokens, other.reasoning_tokens)
        self.audio_input_tokens = max(self.audio_input_tokens, other.audio_input_tokens)
        self.audio_output_tokens = max(self.audio_output_tokens, other.audio_output_tokens)
        self.image_tokens = max(self.image_tokens, other.image_tokens)
        if other.raw:
            self.raw = other.raw

    def has_data(self) -> bool:
        """是否有有效的 usage 数据"""
        return (
            self.prompt_tokens > 0
            or self.completion_tokens > 0
            or self.cached_tokens > 0
            or self.reasoning_tokens > 0
        )


def parse_usage(usage: Optional[Dict[str, Any]]) -> UsageInfo:
    """
    解析 API 返回的 usage 对象

    支持格式：
    1. OpenAI 标准格式:
       {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}

    2. OpenAI 详细格式 (GPT-4o+):
       {"prompt_tokens": 10, "completion_tokens": 20,
        "prompt_tokens_details": {"cached_tokens": 5, "audio_tokens": 0},
        "completion_tokens_details": {"reasoning_tokens": 8, "audio_tokens": 0}}

    3. Claude 格式:
       {"input_tokens": 10, "output_tokens": 20,
        "cache_read_input_tokens": 5, "cache_creation_input_tokens": 0}

    4. Gemini 格式:
       {"prompt_tokens": 10, "candidates_token_count": 20,
        "thoughts_token_count": 5}

    Args:
        usage: API 返回的 usage 字典

    Returns:
        UsageInfo: 标准化的 usage 信息
    """
    if not usage:
        return UsageInfo()

    info = UsageInfo(raw=usage)

    # === 基础 token ===
    # OpenAI 格式
    info.prompt_tokens = usage.get("prompt_tokens", 0) or 0
    info.completion_tokens = usage.get("completion_tokens", 0) or 0

    # Claude 格式 (input_tokens / output_tokens)
    # 只在 OpenAI 格式没有值，或 Claude 格式有更大的值时才使用
    # （避免某些 API 同时返回两种格式但 Claude 格式为 0 的情况覆盖正确值）
    if "input_tokens" in usage:
        input_tokens = usage.get("input_tokens", 0) or 0
        if input_tokens > 0 or info.prompt_tokens == 0:
            info.prompt_tokens = max(info.prompt_tokens, input_tokens)
    if "output_tokens" in usage:
        output_tokens = usage.get("output_tokens", 0) or 0
        if output_tokens > 0 or info.completion_tokens == 0:
            info.completion_tokens = max(info.completion_tokens, output_tokens)

    # Gemini 格式 (candidates_token_count)
    if "candidates_token_count" in usage:
        info.completion_tokens = usage.get("candidates_token_count", 0) or 0

    # === 缓存 token ===
    # OpenAI 详细格式
    prompt_details = usage.get("prompt_tokens_details") or {}
    if prompt_details:
        info.cached_tokens = prompt_details.get("cached_tokens", 0) or 0
        info.audio_input_tokens = prompt_details.get("audio_tokens", 0) or 0

    # Claude 格式
    if "cache_read_input_tokens" in usage:
        info.cached_tokens = usage.get("cache_read_input_tokens", 0) or 0
    if "cache_creation_input_tokens" in usage:
        info.cache_creation_tokens = usage.get("cache_creation_input_tokens", 0) or 0

    # === 推理 token ===
    # OpenAI 详细格式
    completion_details = usage.get("completion_tokens_details") or {}
    if completion_details:
        info.reasoning_tokens = completion_details.get("reasoning_tokens", 0) or 0
        info.audio_output_tokens = completion_details.get("audio_tokens", 0) or 0

    # Gemini 格式 (thoughts_token_count)
    if "thoughts_token_count" in usage:
        info.reasoning_tokens = usage.get("thoughts_token_count", 0) or 0

    return info


def parse_usage_from_sse_chunk(chunk: Union[bytes, str]) -> Optional[UsageInfo]:
    """
    从 SSE chunk 中解析 usage

    Args:
        chunk: SSE 数据块（bytes 或 str）

    Returns:
        UsageInfo 或 None（如果没有 usage）
    """
    try:
        # 转换为字符串
        if isinstance(chunk, bytes):
            chunk_str = chunk.decode("utf-8")
        else:
            chunk_str = chunk

        # 跳过非数据行
        if "data: " not in chunk_str:
            return None

        # 提取 data 部分
        for line in chunk_str.split("\n"):
            if not line.startswith("data: "):
                continue

            data_str = line[6:].strip()
            if not data_str or data_str == "[DONE]":
                continue

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            # 提取 usage
            usage = data.get("usage")
            if usage:
                return parse_usage(usage)

        return None

    except Exception as e:
        log.debug(f"解析 SSE usage 失败: {e}")
        return None


def extract_delta_content(chunk: Union[bytes, str]) -> str:
    """
    从 SSE chunk 中提取 delta content

    用于累积流式内容进行后备 token 估算

    Args:
        chunk: SSE 数据块

    Returns:
        str: 提取的 content（可能为空）
    """
    try:
        if isinstance(chunk, bytes):
            chunk_str = chunk.decode("utf-8")
        else:
            chunk_str = chunk

        if "data: " not in chunk_str:
            return ""

        content_parts = []
        for line in chunk_str.split("\n"):
            if not line.startswith("data: "):
                continue

            data_str = line[6:].strip()
            if not data_str or data_str == "[DONE]":
                continue

            try:
                data = json.loads(data_str)
                # OpenAI 格式
                choices = data.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        content_parts.append(content)
                    # 也提取 reasoning_content 用于估算
                    reasoning = delta.get("reasoning_content") or delta.get("reasoning") or delta.get("thinking")
                    if reasoning:
                        content_parts.append(reasoning)
            except json.JSONDecodeError:
                continue

        return "".join(content_parts)

    except Exception:
        return ""
