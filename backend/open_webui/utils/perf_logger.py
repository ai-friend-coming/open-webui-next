"""
性能日志记录器 - 用于追踪 /api/chat/completions 接口的性能指标

记录关键时间节点：
1. 接口调用开始
2. ensure_initial_summary 开始/结束
3. messages_loaded 组装完成
4. 调用 LLM 之前
5. LLM 返回第一个 token
6. LLM 回复完成
7. update_summary 开始/结束

最终保存为 JSON 文件，便于性能分析。
"""

import time
import json
from pathlib import Path
from typing import Optional, Dict, List, Any


class ChatPerfLogger:
    """聊天性能日志记录器"""

    def __init__(
        self,
        user_id: str,
        chat_id: str,
        message_id: str,
        user_name: Optional[str] = None,
        chat_title: Optional[str] = None,
    ):
        """
        初始化性能日志记录器

        Args:
            user_id: 用户 ID
            chat_id: 聊天 ID
            message_id: 消息 ID
            user_name: 用户名（可选，用于文件命名）
            chat_title: 聊天标题（可选，用于文件命名）
        """
        self.user_id = user_id
        self.chat_id = chat_id
        self.message_id = message_id
        self.user_name = user_name
        self.chat_title = chat_title

        # 时间戳
        self.t0 = None  # 接口调用开始
        self.t_before_llm = None  # 调用 LLM 之前
        self.t_first_token = None  # LLM 返回第一个 token
        self.t_llm_response = None  # LLM 回复完成
        self.t_payload_start = None  # process_chat_payload 开始
        self.t_payload_end = None  # process_chat_payload 结束
        self.t_ensure_initial_summary_start = None
        self.t_ensure_initial_summary_end = None
        self.t_update_summary_start = None
        self.t_update_summary_end = None

        # 详细信息
        self.llm_info: Dict[str, Any] = {}
        self.payload_info: Dict[str, Any] = {}  # payload 处理详情
        self.ensure_initial_summary_info: Dict[str, Any] = {}
        self.messages_loaded_info: Dict[str, Any] = {}
        self.update_summary_info: Dict[str, Any] = {}

        # 新增：LLM 调用和 Summary 材料存储
        self.llm_payload: Optional[Dict[str, Any]] = None  # LLM 调用的完整 payload
        self.llm_response_content: Optional[Any] = None  # LLM 回复内容（最终响应）

        self.model_id: Optional[str] = None
        self._filepath: Optional[Path] = None

    def start(self, model_id: Optional[str] = None) -> None:
        """1. 标记接口调用开始，并记录核心元信息"""
        self.t0 = time.time()
        self.model_id = model_id
        print(
            f"[PERF] 1. /api/chat/completions 接口调用开始: {self.t0:.6f} "
            f"(user_id={self.user_id}, chat_id={self.chat_id}, model_id={self.model_id})"
        )

    def mark_payload_processing(self, start: bool = True) -> None:
        """
        标记 process_chat_payload 的开始/结束

        Args:
            start: True=开始，False=结束
        """
        if start:
            self.t_payload_start = time.time()
            delta_ms = (self.t_payload_start - self.t0) * 1000 if self.t0 else 0
            print(
                f"[PERF] 4. process_chat_payload 开始: {self.t_payload_start:.6f} "
                f"(距接口调用 +{delta_ms:.2f}ms)"
            )
        else:
            self.t_payload_end = time.time()
            if self.t_payload_start:
                duration_ms = (self.t_payload_end - self.t_payload_start) * 1000
                print(
                    f"[PERF] 4. process_chat_payload 完成: {self.t_payload_end:.6f} "
                    f"(耗时 {duration_ms:.2f}ms)"
                )

    def mark_payload_checkpoint(self, name: str) -> None:
        """
        标记 payload 处理过程中的检查点

        Args:
            name: 检查点名称（如 "billing_check", "memory_load" 等）
        """
        t_now = time.time()
        if not hasattr(self, "_payload_checkpoints"):
            self._payload_checkpoints = []

        # 计算距离上一个检查点的耗时
        if self._payload_checkpoints:
            last_checkpoint = self._payload_checkpoints[-1]
            duration_ms = (t_now - last_checkpoint["time"]) * 1000
            print(f"[PERF]   ├─ {last_checkpoint['name']} → {name}: {duration_ms:.2f}ms")
        else:
            # 第一个检查点，计算距离 payload_start 的耗时
            if self.t_payload_start:
                duration_ms = (t_now - self.t_payload_start) * 1000
                print(f"[PERF]   ├─ payload_start → {name}: {duration_ms:.2f}ms")

        self._payload_checkpoints.append({"name": name, "time": t_now})
        self.payload_info[f"checkpoint_{name}"] = t_now

    def before_call_llm(self, payload: Dict[str, Any]) -> None:
        """5. 标记调用 LLM 之前，并记录 payload"""
        self.t_before_llm = time.time()
        self.record_llm_payload(payload)
        delta_ms = (self.t_before_llm - self.t0) * 1000 if self.t0 else 0
        print(
            f"[PERF] 5. 调用 LLM 之前: {self.t_before_llm:.6f} "
            f"(距接口调用 +{delta_ms:.2f}ms)"
        )

    def mark_first_token(self) -> None:
        """6. 标记 LLM 返回第一个 token"""
        self.t_first_token = time.time()
        ttft_ms = (
            (self.t_first_token - self.t_before_llm) * 1000
            if self.t_before_llm
            else 0
        )
        total_ms = (self.t_first_token - self.t0) * 1000 if self.t0 else 0
        print(
            f"[PERF] 6. LLM 返回第一个 token: {self.t_first_token:.6f} "
            f"(TTFT={ttft_ms:.2f}ms, 距接口调用 +{total_ms:.2f}ms)"
        )

    def llm_response(self, response: Any, usage: Optional[Dict] = None) -> None:
        """
        记录 LLM 最终回复内容与时间

        Args:
            response: LLM 回复内容（文本或序列化内容块）
            usage: LLM 使用情况统计（tokens 等）
        """
        self.t_llm_response = time.time()
        if usage:
            self.llm_info["usage"] = usage
        self.llm_response_content = response
        # 尝试从完整响应中提取 usage（如果存在）
        if isinstance(response, dict):
            response_usage = response.get("usage")
            if isinstance(response_usage, dict) and response_usage:
                self.llm_info["usage"] = response_usage
        elif isinstance(response, str):
            try:
                response_data = json.loads(response)
                if isinstance(response_data, dict):
                    response_usage = response_data.get("usage")
                    if isinstance(response_usage, dict) and response_usage:
                        self.llm_info["usage"] = response_usage
            except Exception:
                pass
        if isinstance(response, (str, list, dict)):
            self.llm_info["response_length"] = len(response)
        print("[PERF] 记录 LLM 回复内容")

    def ensure_initial_summary_start(
        self, messages: List[Dict], prompt: str
    ) -> None:
        """2. ensure_initial_summary 开始"""
        self.t_ensure_initial_summary_start = time.time()
        self.ensure_initial_summary_info = {
            "messages": self._sanitize_messages(messages),
            "prompt": prompt,
            "messages_count": len(messages),
            "prompt_length": len(prompt) if prompt else 0,
        }
        print(
            f"[PERF] ensure_initial_summary 开始: {self.t_ensure_initial_summary_start:.6f} "
            f"(messages={len(messages)})"
        )

    def ensure_initial_summary_end(
        self, response: Optional[Any], prompt:str, usage: Optional[Dict[str, Any]]
    ) -> None:
        """3. ensure_initial_summary 结束"""
        self.t_ensure_initial_summary_end = time.time()
        self.ensure_initial_summary_info["usage"] = usage
        self.ensure_initial_summary_info["prompt"] = prompt
        self.ensure_initial_summary_info["response"] = response
        print(
            f"[PERF] ensure_initial_summary 结束: {self.t_ensure_initial_summary_end:.6f}"
        )

    def record_messages_loaded(
        self,
        summary_system_message: Dict[str, Any],
        cold_start_messages: List[Dict[str, Any]],
        recent_conversation_in_this_chat: List[Dict[str, Any]],
    ) -> None:
        """4. messages_loaded 内部组装完成"""
        t_now = time.time()
        self.messages_loaded_info = {
            "time": t_now,
            "summary_system_message": summary_system_message,
            "cold_start_messages": self._sanitize_messages(cold_start_messages),
            "recent_conversation_in_this_chat": self._sanitize_messages(
                recent_conversation_in_this_chat
            ),
        }
        print(f"[PERF] messages_loaded 组装完成: {t_now:.6f}")

    def update_summary_start(
        self,
        old_summary: Optional[str],
        to_be_summarized_messages: List[Dict[str, Any]],
        tokens: Optional[int] = None,
        threshold: Optional[int] = None,
    ) -> None:
        """7. update_summary 开始"""
        self.t_update_summary_start = time.time()
        self.update_summary_info = {
            "old_summary": old_summary,
            "to_be_summarized_messages": self._sanitize_messages(
                to_be_summarized_messages
            ),
            "tokens": tokens,
            "threshold": threshold,
        }
        print(
            f"[PERF] update_summary 开始: {self.t_update_summary_start:.6f} "
            f"(messages={len(to_be_summarized_messages)})"
        )

    def update_summary_end(
        self, response: Optional[Any], prompt:str, usage: Optional[Dict[str, Any]], 
    ) -> None:
        """8. update_summary 结束"""
        self.t_update_summary_end = time.time()
        self.update_summary_info["response"] = response
        self.update_summary_info["prompt"] = prompt
        self.update_summary_info["usage"] = usage
        print(f"[PERF] update_summary 结束: {self.t_update_summary_end:.6f}")

    def record_llm_payload(self, payload: Dict[str, Any]) -> None:
        """
        记录 LLM 调用的完整 payload

        Args:
            payload: LLM 请求的 payload 数据
        """
        self.llm_payload = {
            "model": payload.get("model"),
            "messages": self._sanitize_messages(payload.get("messages", [])),
            "temperature": payload.get("temperature"),
            "max_tokens": payload.get("max_tokens"),
            "stream": payload.get("stream"),
            "metadata": {
                "messages_count": len(payload.get("messages", [])),
                "total_content_length": sum(
                    len(str(msg.get("content", "")))
                    for msg in payload.get("messages", [])
                ),
            }
        }
        print(f"[PERF] 记录 LLM Payload: model={payload.get('model')}, 消息数={len(payload.get('messages', []))}")

    def _sanitize_messages(self, messages: List[Dict]) -> List[Dict]:
        """
        清理消息数据，只保留关键字段，减小日志体积

        Args:
            messages: 原始消息列表

        Returns:
            清理后的消息列表
        """
        sanitized = []
        for msg in messages:
            sanitized_msg = {
                "role": msg.get("role"),
                "content": msg.get("content"),
            }
            # 可选字段
            if "id" in msg:
                sanitized_msg["id"] = msg["id"]
            if "name" in msg:
                sanitized_msg["name"] = msg["name"]

            sanitized.append(sanitized_msg)

        return sanitized

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式

        Returns:
            包含所有性能数据的字典
        """
        result = {
            "metadata": {
                "user_id": self.user_id,
                "chat_id": self.chat_id,
                "message_id": self.message_id,
                "user_name": self.user_name,
                "chat_title": self.chat_title,
                "model_id": self.model_id,
            },
            "timestamps": {
                "api_start": self.t0,
                "payload_processing_start": self.t_payload_start,
                "payload_processing_end": self.t_payload_end,
                "ensure_initial_summary_start": self.t_ensure_initial_summary_start,
                "ensure_initial_summary_end": self.t_ensure_initial_summary_end,
                "messages_loaded": self.messages_loaded_info.get("time"),
                "before_llm": self.t_before_llm,
                "first_token": self.t_first_token,
                "llm_response": self.t_llm_response,
                "update_summary_start": self.t_update_summary_start,
                "update_summary_end": self.t_update_summary_end,
            },
            "durations_ms": {},
            "llm_info": self.llm_info,
            "payload_info": self.payload_info,  # 包含所有 checkpoint 信息
            "ensure_initial_summary_info": self.ensure_initial_summary_info,
            "messages_loaded_info": self.messages_loaded_info,
            "update_summary_info": self.update_summary_info,
            "llm_payload": self.llm_payload,  # LLM 调用的完整 payload
            "llm_response": self.llm_response_content,  # LLM 回复内容
        }

        # 计算各个阶段的耗时
        if self.t0:
            durations = result["durations_ms"]

            if self.t_payload_start and self.t_payload_end:
                durations["payload_processing"] = (
                    self.t_payload_end - self.t_payload_start
                ) * 1000

            if self.t_before_llm:
                durations["total_preprocessing"] = (self.t_before_llm - self.t0) * 1000

            if self.t_first_token:
                durations["ttft"] = (
                    (self.t_first_token - self.t_before_llm) * 1000
                    if self.t_before_llm
                    else None
                )
                durations["total_to_first_token"] = (
                    self.t_first_token - self.t0
                ) * 1000

            if self.t_llm_response:
                durations["total"] = (self.t_llm_response - self.t0) * 1000

            if self.t_update_summary_start and self.t_update_summary_end:
                durations["update_summary"] = (
                    self.t_update_summary_end - self.t_update_summary_start
                ) * 1000

            # 计算 payload checkpoints 之间的耗时
            if hasattr(self, "_payload_checkpoints") and self._payload_checkpoints:
                checkpoints = self._payload_checkpoints

                # 第一个 checkpoint 距离 payload_start 的耗时
                if self.t_payload_start:
                    durations[f"checkpoint_to_{checkpoints[0]['name']}"] = (
                        checkpoints[0]["time"] - self.t_payload_start
                    ) * 1000

                # 后续 checkpoint 之间的耗时
                for i in range(1, len(checkpoints)):
                    duration_key = f"checkpoint_{checkpoints[i-1]['name']}_to_{checkpoints[i]['name']}"
                    durations[duration_key] = (
                        checkpoints[i]["time"] - checkpoints[i-1]["time"]
                    ) * 1000

        return result

    async def save_to_file(self, log_dir: str = "logs") -> Optional[Path]:
        """
        保存为 JSON 文件

        Args:
            log_dir: 日志目录路径

        Returns:
            保存的文件路径，失败则返回 None
        """
        try:
            # 确保 log 目录存在
            log_path = Path(log_dir)
            log_path.mkdir(exist_ok=True)

            if self._filepath is None:
                self._filepath = self._build_filepath(log_path)

            # 保存 JSON
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

            print(f"[PERF] Performance log saved to: {self._filepath}")
            return self._filepath

        except Exception as e:
            print(f"[PERF] Failed to save performance log: {e}")
            return None

    def _build_filepath(self, log_path: Path) -> Path:
        user_name = self.user_name or self.user_id or "unknown"
        chat_title = self.chat_title or "untitled"
        message_id = str(self.message_id) or "unknown"

        safe_user = "".join(
            c for c in user_name if c.isalnum() or c in (" ", "-", "_")
        ).strip()[:50]
        safe_title = "".join(
            c for c in chat_title if c.isalnum() or c in (" ", "-", "_")
        ).strip()[:50]
        safe_msg = "".join(c for c in message_id if c.isalnum() or c in ("-", "_"))[
            :50
        ]
        filename = f"{safe_user}_{safe_title}_{safe_msg}.json"
        return log_path / filename
