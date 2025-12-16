"""
流式响应计费包装器

自动解析 SSE 中的 usage 并更新到 BillingContext
在流结束时（包括用户中断）自动执行结算

关键设计：
- 使用 finally 块确保即使用户中断也能结算
- 从 SSE 事件中提取 usage 信息
- 支持 OpenAI/Claude 格式的流式响应
"""

import json
import asyncio
import logging
from typing import AsyncIterator, Union

from open_webui.billing.context import BillingContext

log = logging.getLogger(__name__)


class BillingStreamWrapper:
    """
    流式响应计费包装器

    包装原始的 AsyncIterator，在迭代过程中解析 usage，
    并在流结束时（包括用户中断）自动执行结算。
    """

    def __init__(
        self,
        stream: AsyncIterator[bytes],
        billing_context: BillingContext,
    ):
        self.stream = stream
        self.billing = billing_context
        self._settled = False

    async def __aiter__(self):
        try:
            async for chunk in self.stream:
                # 解析 usage
                self._parse_usage(chunk)
                yield chunk

        except asyncio.CancelledError:
            # 用户中断
            log.info(f"[Billing] 流被取消: user={self.billing.user_id}")
            raise

        except Exception as e:
            log.error(f"[Billing] 流式传输异常: {e}")
            raise

        finally:
            # 确保结算（无论正常结束还是异常/中断）
            await self._ensure_settle()

    async def _ensure_settle(self):
        """确保结算只执行一次"""
        if self._settled:
            return
        self._settled = True

        try:
            await self.billing.settle()
        except Exception as e:
            log.error(f"[Billing] 结算失败: {e}")

    def _parse_usage(self, chunk: Union[bytes, str]) -> None:
        """
        从 SSE chunk 中解析 usage

        支持的格式：
        - OpenAI: data: {"usage": {"prompt_tokens": 10, "completion_tokens": 20}}
        - Claude: data: {"type": "message_delta", "usage": {...}}
        """
        try:
            # 转换为字符串
            if isinstance(chunk, bytes):
                chunk_str = chunk.decode("utf-8")
            else:
                chunk_str = chunk

            # 跳过非数据行
            if "data: " not in chunk_str:
                return

            # 提取 data 部分
            for line in chunk_str.split("\n"):
                if not line.startswith("data: "):
                    continue

                data_str = line[6:].strip()  # 去掉 "data: " 前缀
                if not data_str or data_str == "[DONE]":
                    continue

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                # 提取 usage
                usage = data.get("usage")
                if usage:
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)

                    if prompt_tokens > 0 or completion_tokens > 0:
                        self.billing.update_usage(prompt_tokens, completion_tokens)

        except Exception:
            # 解析失败忽略，不影响流式传输
            pass


def wrap_stream_with_billing(
    stream: AsyncIterator[bytes],
    billing_context: BillingContext,
) -> BillingStreamWrapper:
    """
    便捷函数：包装流式响应以添加计费

    Args:
        stream: 原始的流式响应迭代器
        billing_context: 计费上下文

    Returns:
        BillingStreamWrapper: 包装后的迭代器
    """
    return BillingStreamWrapper(stream, billing_context)
