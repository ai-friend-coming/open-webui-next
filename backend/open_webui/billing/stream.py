"""
流式响应计费包装器

自动解析 SSE 中的 usage 并更新到 BillingContext
在流结束时（包括用户中断）自动执行结算

关键设计：
- 使用 finally 块确保即使用户中断也能结算
- 使用统一的 usage 解析模块 (usage.py)
- 支持 OpenAI/Claude/Gemini 格式的流式响应
- 支持缓存 token 和推理 token
"""

import asyncio
import logging
from typing import AsyncIterator, Union

from open_webui.billing.context import BillingContext
from open_webui.billing.usage import (
    UsageInfo,
    parse_usage_from_sse_chunk,
    extract_delta_content,
)

log = logging.getLogger(__name__)


class BillingStreamWrapper:
    """
    流式响应计费包装器

    包装原始的 AsyncIterator，在迭代过程中解析 usage，
    并在流结束时（包括用户中断）自动执行结算。

    特性：
    - 支持 OpenAI/Claude/Gemini 的 usage 格式
    - 支持 prompt_tokens_details（缓存 token）
    - 支持 completion_tokens_details（推理 token）
    - 累计流内容用于后备 token 估算
    """

    def __init__(
        self,
        stream: AsyncIterator[bytes],
        billing_context: BillingContext,
    ):
        self.stream = stream
        self.billing = billing_context
        self._settled = False
        self._accumulated_content = []  # 累计流内容用于后备估算
        self._usage = UsageInfo()  # 累计的 usage 信息

    async def __aiter__(self):
        try:
            async for chunk in self.stream:
                # 解析 usage（使用统一的解析模块）
                self._parse_usage(chunk)
                # 累计内容用于后备估算
                self._accumulate_content(chunk)
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
            # 传递累计的 usage 信息到 BillingContext
            if self._usage.has_data():
                self.billing.update_usage_info(self._usage)

            # 传递累计内容用于后备估算
            if self._accumulated_content and not self.billing.has_usage_data:
                self.billing.accumulated_content = "".join(self._accumulated_content)

            await self.billing.settle()
        except Exception as e:
            log.error(f"[Billing] 结算失败: {e}")
            # 转换计费相关的 HTTPException 为 CustmizedError
            from fastapi import HTTPException
            if isinstance(e, HTTPException) and e.status_code in (402, 403, 404):
                from open_webui.billing.core import convert_billing_exception_to_customized_error
                raise convert_billing_exception_to_customized_error(e)
            # 其他异常不重新抛出，避免影响已发送的流

    def _parse_usage(self, chunk: Union[bytes, str]) -> None:
        """
        从 SSE chunk 中解析 usage

        使用统一的 usage 解析模块，支持：
        - OpenAI 完整格式（含 prompt_tokens_details, completion_tokens_details）
        - Claude 格式（含 cache_read_input_tokens）
        - Gemini 格式（含 thoughts_token_count）

        注意：只累积 UsageInfo，不直接调用 billing.update_usage()
        在 _ensure_settle() 中统一通过 update_usage_info() 更新
        """
        try:
            usage_info = parse_usage_from_sse_chunk(chunk)
            if usage_info and usage_info.has_data():
                # 合并到累计的 usage（取最大值）
                self._usage.merge_max(usage_info)

                log.debug(
                    f"[Billing] 解析到 usage: "
                    f"prompt={usage_info.prompt_tokens}, "
                    f"completion={usage_info.completion_tokens}, "
                    f"cached={usage_info.cached_tokens}, "
                    f"reasoning={usage_info.reasoning_tokens}"
                )

        except Exception as e:
            # 解析失败忽略，不影响流式传输
            log.debug(f"[Billing] 解析 usage 失败（忽略）: {e}")

    def _accumulate_content(self, chunk: Union[bytes, str]) -> None:
        """
        累计流式内容用于后备 token 估算

        当 API 不返回 usage 时，使用累计的内容进行 tiktoken 估算
        同时提取 reasoning_content 用于估算推理 token
        """
        try:
            content = extract_delta_content(chunk)
            if content:
                self._accumulated_content.append(content)
        except Exception:
            # 累计失败忽略，不影响流式传输
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
