"""
性能日志记录器 - 用于追踪 /api/chat/completions 接口的性能指标

记录关键时间节点：
1. 接口调用开始
2. ensure_initial_summary 开始
3. 摘要生成（开始/结束）
4. 上下文装入（开始/结束）
5. 调用 LLM 之前
6. LLM 返回第一个 token
7. LLM 完成

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
        self.t1_ensure_summary = None  # ensure_initial_summary 开始
        self.t2_summary_start = None  # 摘要生成开始
        self.t2_summary_end = None  # 摘要生成结束
        self.t3_context_load_start = None  # 上下文装入开始
        self.t3_context_load_end = None  # 上下文装入结束
        self.t4_before_llm = None  # 调用 LLM 之前
        self.t5_first_token = None  # LLM 返回第一个 token
        self.t6_llm_complete = None  # LLM 完成

        # 新增：细粒度时间戳
        self.t_payload_start = None  # process_chat_payload 开始
        self.t_payload_end = None  # process_chat_payload 结束
        self.t_summary_update_start = None  # 后台 summary 更新开始
        self.t_summary_update_end = None  # 后台 summary 更新结束

        # 详细信息
        self.summary_info: Dict[str, Any] = {}
        self.context_info: Dict[str, Any] = {}
        self.llm_info: Dict[str, Any] = {}
        self.payload_info: Dict[str, Any] = {}  # payload 处理详情
        self.summary_update_info: Dict[str, Any] = {}  # summary 更新详情

        # 新增：LLM 调用和 Summary 材料存储
        self.llm_payload: Optional[Dict[str, Any]] = None  # LLM 调用的完整 payload
        self.summary_materials: Optional[Dict[str, Any]] = None  # Summary 更新使用的材料

    def mark_api_start(self) -> None:
        """1. 标记接口调用开始"""
        self.t0 = time.time()
        print(f"[PERF] 1. /api/chat/completions 接口调用开始: {self.t0:.6f}")

    def mark_ensure_summary_start(
        self,
        has_existing_summary: bool,
        init_summary_messages: Optional[List[Dict]] = None,
        cold_start_messages: Optional[List[Dict]] = None,
    ) -> None:
        """
        2. 标记 ensure_initial_summary 开始

        Args:
            has_existing_summary: 是否已有摘要
            init_summary_messages: 用于生成初始摘要的消息列表
            cold_start_messages: 冷启动消息列表
        """
        self.t1_ensure_summary = time.time()
        self.summary_info = {
            "has_existing_summary": has_existing_summary,
            "init_summary_messages_count": (
                len(init_summary_messages) if init_summary_messages else 0
            ),
            "cold_start_messages_count": (
                len(cold_start_messages) if cold_start_messages else 0
            ),
        }

        delta_ms = (self.t1_ensure_summary - self.t0) * 1000 if self.t0 else 0
        print(
            f"[PERF] 2. ensure_initial_summary 开始: {self.t1_ensure_summary:.6f} "
            f"(距接口调用 +{delta_ms:.2f}ms, 已有摘要={has_existing_summary})"
        )

    def mark_summary_generation(
        self, start: bool = True, messages: Optional[List[Dict]] = None, stage: str = ""
    ) -> None:
        """
        3. 标记摘要生成（开始/结束）

        Args:
            start: True=开始，False=结束
            messages: 参与摘要的消息列表
            stage: 阶段标识（如 "适中消息量" 或 "基础摘要"）
        """
        if start:
            self.t2_summary_start = time.time()
            if messages:
                self.summary_info["summary_messages_count"] = len(messages)
                self.summary_info["stage"] = stage
            delta_ms = (self.t2_summary_start - self.t0) * 1000 if self.t0 else 0
            print(
                f"[PERF] 3. 开始生成摘要（{stage}, 消息数={len(messages) if messages else 0}）: "
                f"{self.t2_summary_start:.6f} (距接口调用 +{delta_ms:.2f}ms)"
            )
        else:
            self.t2_summary_end = time.time()
            if self.t2_summary_start:
                duration_ms = (self.t2_summary_end - self.t2_summary_start) * 1000
                print(
                    f"[PERF] 3. 摘要生成完成: {self.t2_summary_end:.6f} (耗时 {duration_ms:.2f}ms)"
                )

    def mark_context_load(
        self,
        start: bool = True,
        system_prompt: Optional[str] = None,
        cold_start_messages: Optional[List[Dict]] = None,
        ordered_messages: Optional[List[Dict]] = None,
    ) -> None:
        """
        4. 标记上下文装入（开始/结束）

        Args:
            start: True=开始，False=结束
            system_prompt: 系统提示词
            cold_start_messages: 冷启动消息列表
            ordered_messages: 排序后的消息列表
        """
        if start:
            self.t3_context_load_start = time.time()
            print(
                f"[PERF] 4a. 开始装入上下文: {self.t3_context_load_start:.6f}"
            )
        else:
            self.t3_context_load_end = time.time()
            self.context_info = {
                "has_system_prompt": bool(system_prompt),
                "system_prompt_length": len(system_prompt) if system_prompt else 0,
                "cold_start_count": (
                    len(cold_start_messages) if cold_start_messages else 0
                ),
                "ordered_messages_count": (
                    len(ordered_messages) if ordered_messages else 0
                ),
            }

            if self.t3_context_load_start:
                duration_ms = (
                    self.t3_context_load_end - self.t3_context_load_start
                ) * 1000
                print(
                    f"[PERF] 4b. 装入上下文完成: {self.t3_context_load_end:.6f} "
                    f"(耗时 {duration_ms:.2f}ms, 总消息数={self.context_info['ordered_messages_count']})"
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

    def mark_before_llm(self) -> None:
        """5. 标记调用 LLM 之前"""
        self.t4_before_llm = time.time()
        delta_ms = (self.t4_before_llm - self.t0) * 1000 if self.t0 else 0
        print(
            f"[PERF] 5. 调用 LLM 之前: {self.t4_before_llm:.6f} "
            f"(距接口调用 +{delta_ms:.2f}ms)"
        )

    def mark_first_token(self) -> None:
        """6. 标记 LLM 返回第一个 token"""
        self.t5_first_token = time.time()
        ttft_ms = (
            (self.t5_first_token - self.t4_before_llm) * 1000
            if self.t4_before_llm
            else 0
        )
        total_ms = (self.t5_first_token - self.t0) * 1000 if self.t0 else 0
        print(
            f"[PERF] 6. LLM 返回第一个 token: {self.t5_first_token:.6f} "
            f"(TTFT={ttft_ms:.2f}ms, 距接口调用 +{total_ms:.2f}ms)"
        )

    def mark_llm_complete(self, usage: Optional[Dict] = None) -> None:
        """
        7. 标记 LLM 完成

        Args:
            usage: LLM 使用情况统计（tokens 等）
        """
        self.t6_llm_complete = time.time()
        if usage:
            self.llm_info["usage"] = usage

        generation_ms = (
            (self.t6_llm_complete - self.t5_first_token) * 1000
            if self.t5_first_token
            else 0
        )
        total_ms = (self.t6_llm_complete - self.t0) * 1000 if self.t0 else 0
        print(
            f"[PERF] 7. LLM 完成: {self.t6_llm_complete:.6f} "
            f"(生成耗时 {generation_ms:.2f}ms, 总耗时 {total_ms:.2f}ms)"
        )

    def mark_summary_update(
        self,
        start: bool = True,
        tokens: Optional[int] = None,
        threshold: Optional[int] = None,
        messages_count: Optional[int] = None,
    ) -> None:
        """
        8. 标记后台 Summary 更新（基于阈值触发）

        Args:
            start: True=开始，False=结束
            tokens: 当前 token 数量
            threshold: token 阈值
            messages_count: 参与摘要的消息数量
        """
        if start:
            self.t_summary_update_start = time.time()
            self.summary_update_info = {
                "tokens": tokens,
                "threshold": threshold,
                "messages_count": messages_count,
            }
            print(
                f"[PERF] 8. 开始后台 Summary 更新: {self.t_summary_update_start:.6f} "
                f"(tokens={tokens}, threshold={threshold}, 消息数={messages_count})"
            )
        else:
            self.t_summary_update_end = time.time()
            if self.t_summary_update_start:
                duration_ms = (
                    self.t_summary_update_end - self.t_summary_update_start
                ) * 1000
                print(
                    f"[PERF] 8. 后台 Summary 更新完成: {self.t_summary_update_end:.6f} "
                    f"(耗时 {duration_ms:.2f}ms)"
                )
            else:
                print(
                    f"[PERF] 8. 后台 Summary 更新完成: {self.t_summary_update_end:.6f}"
                )

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

    def record_summary_materials(
        self,
        messages: List[Dict],
        old_summary: Optional[str] = None,
        model: Optional[str] = None,
        user_id: Optional[str] = None,
        new_summary: Optional[str] = None,
    ) -> None:
        """
        记录 Summary 更新时 summarize() 函数的完整参数

        Args:
            messages: 参与摘要的消息列表（对应 summarize 的 messages 参数）
            old_summary: 旧的摘要内容（对应 summarize 的 old_summary 参数）
            model: 模型 ID（对应 summarize 的 model 参数）
            user_id: 用户 ID（对应 summarize 的 user 参数）
            new_summary: 新生成的摘要内容（summarize 的返回值）
        """
        self.summary_materials = {
            # summarize() 函数的输入参数
            "function_args": {
                "messages": self._sanitize_messages(messages),
                "old_summary": old_summary,
                "model": model,
                "user_id": user_id,
            },
            # summarize() 函数的输出
            "function_output": {
                "new_summary": new_summary,
            },
            # 统计元数据
            "metadata": {
                "messages_count": len(messages),
                "old_summary_length": len(old_summary) if old_summary else 0,
                "new_summary_length": len(new_summary) if new_summary else 0,
                "total_messages_content_length": sum(
                    len(str(msg.get("content", "")))
                    for msg in messages
                ),
            }
        }
        print(
            f"[PERF] 记录 Summary 材料: model={model}, 消息数={len(messages)}, "
            f"旧摘要长度={len(old_summary) if old_summary else 0}, "
            f"新摘要长度={len(new_summary) if new_summary else 0}"
        )

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
            },
            "timestamps": {
                "api_start": self.t0,
                "ensure_summary_start": self.t1_ensure_summary,
                "summary_generation_start": self.t2_summary_start,
                "summary_generation_end": self.t2_summary_end,
                "payload_processing_start": self.t_payload_start,
                "context_load_start": self.t3_context_load_start,
                "context_load_end": self.t3_context_load_end,
                "payload_processing_end": self.t_payload_end,
                "before_llm": self.t4_before_llm,
                "first_token": self.t5_first_token,
                "llm_complete": self.t6_llm_complete,
                "summary_update_start": self.t_summary_update_start,
                "summary_update_end": self.t_summary_update_end,
            },
            "durations_ms": {},
            "summary_info": self.summary_info,
            "context_info": self.context_info,
            "llm_info": self.llm_info,
            "payload_info": self.payload_info,  # 包含所有 checkpoint 信息
            "summary_update_info": self.summary_update_info,  # summary 更新详情
            "llm_payload": self.llm_payload,  # LLM 调用的完整 payload
            "summary_materials": self.summary_materials,  # Summary 更新使用的材料
        }

        # 计算各个阶段的耗时
        if self.t0:
            durations = result["durations_ms"]

            if self.t1_ensure_summary:
                durations["to_ensure_summary"] = (
                    self.t1_ensure_summary - self.t0
                ) * 1000

            if self.t2_summary_start and self.t2_summary_end:
                durations["summary_generation"] = (
                    self.t2_summary_end - self.t2_summary_start
                ) * 1000

            if self.t3_context_load_start and self.t3_context_load_end:
                durations["context_load"] = (
                    self.t3_context_load_end - self.t3_context_load_start
                ) * 1000

            if self.t_payload_start and self.t_payload_end:
                durations["payload_processing"] = (
                    self.t_payload_end - self.t_payload_start
                ) * 1000

            if self.t4_before_llm:
                durations["total_preprocessing"] = (self.t4_before_llm - self.t0) * 1000

                # 细分预处理阶段
                if self.t1_ensure_summary:
                    durations["preprocessing_before_ensure_summary"] = (
                        self.t1_ensure_summary - self.t0
                    ) * 1000
                if self.t_payload_start:
                    durations["preprocessing_before_payload"] = (
                        self.t_payload_start - self.t0
                    ) * 1000
                if self.t_payload_end:
                    durations["preprocessing_after_payload"] = (
                        self.t4_before_llm - self.t_payload_end
                    ) * 1000

            if self.t5_first_token:
                durations["ttft"] = (
                    (self.t5_first_token - self.t4_before_llm) * 1000
                    if self.t4_before_llm
                    else None
                )
                durations["total_to_first_token"] = (self.t5_first_token - self.t0) * 1000

            if self.t6_llm_complete:
                durations["llm_generation"] = (
                    (self.t6_llm_complete - self.t5_first_token) * 1000
                    if self.t5_first_token
                    else None
                )
                durations["total"] = (self.t6_llm_complete - self.t0) * 1000

            # 计算后台 summary 更新耗时
            if self.t_summary_update_start and self.t_summary_update_end:
                durations["summary_update"] = (
                    self.t_summary_update_end - self.t_summary_update_start
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

            # 生成文件名
            user_name = self.user_name or self.user_id or "unknown"
            chat_title = self.chat_title or "untitled"
            message_id = str(self.message_id) or "unknown"

            # 清理文件名中的非法字符
            safe_user = "".join(
                c for c in user_name if c.isalnum() or c in (" ", "-", "_")
            ).strip()[:50]  # 限制长度
            safe_title = "".join(
                c for c in chat_title if c.isalnum() or c in (" ", "-", "_")
            ).strip()[:50]
            safe_msg = "".join(
                c for c in message_id if c.isalnum() or c in ("-", "_")
            )[:50]

            # 添加时间戳避免冲突
            timestamp = int(time.time())
            filename = f"{safe_user}_{safe_title}_{safe_msg}_{timestamp}.json"
            filepath = log_path / filename

            # 保存 JSON
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

            print(f"[PERF] Performance log saved to: {filepath}")
            return filepath

        except Exception as e:
            print(f"[PERF] Failed to save performance log: {e}")
            return None
