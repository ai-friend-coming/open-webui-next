"""
计费代理

提供 chat_with_billing 函数，包装 generate_chat_completion，
自动处理预扣费和结算逻辑。

设计目标：
- chat.py 和 openai.py 无需知道计费逻辑
- 所有计费代码集中在此模块
- 支持流式和非流式响应
- 用户中断时正确结算
"""

import logging
from typing import Any

from fastapi import Request
from starlette.responses import StreamingResponse

from open_webui.billing.context import BillingContext
from open_webui.billing.stream import BillingStreamWrapper

log = logging.getLogger(__name__)


async def chat_with_billing(
    generate_fn,
    request: Request,
    form_data: dict,
    user: Any,
    bypass_filter: bool = False,
    chatting_completion: bool = False,
):
    """
    带计费的聊天完成

    包装任意聊天生成函数，自动处理预扣费和结算。

    流程：
    1. 预扣费
    2. 调用原始生成函数
    3. 流式响应：用 BillingStreamWrapper 包装，在流结束时结算
    4. 非流式响应：从返回值中提取 usage 并结算
    5. 错误时全额退款

    Args:
        generate_fn: 原始的聊天生成函数（如 generate_chat_completion）
        request: FastAPI Request 对象
        form_data: OpenAI 格式的聊天请求数据
        user: 用户对象
        bypass_filter: 是否绕过权限检查
        chatting_completion: 是否为连续聊天模式

    Returns:
        - 流式: StreamingResponse (SSE 格式)
        - 非流式: dict (OpenAI 兼容格式)

    Raises:
        HTTPException: 余额不足或账户冻结
    """
    # 1. 创建计费上下文
    billing = BillingContext(
        user_id=user.id,
        model_id=form_data.get("model", "unknown"),
        messages=form_data.get("messages", []),
        max_completion_tokens=form_data.get("max_tokens", 4096),
        stream=form_data.get("stream", False),
    )

    # 用户模型不启用扣费
    if form_data.get("is_user_model") and form_data.get("model_item", {}).get("credential_id"):
        billing.enabled = False

    try:
        # 2. 预扣费
        await billing.precharge()

        # 3. 调用原始生成函数
        response = await generate_fn(
            request=request,
            form_data=form_data,
            user=user,
            bypass_filter=bypass_filter,
            chatting_completion=chatting_completion,
        )

        # 4. 根据响应类型处理计费
        if isinstance(response, StreamingResponse):
            # 流式响应：用 BillingStreamWrapper 包装
            wrapped_stream = BillingStreamWrapper(
                stream=response.body_iterator,
                billing_context=billing,
            )
            return StreamingResponse(
                wrapped_stream,
                media_type=response.media_type,
                headers=dict(response.headers),
                background=response.background,
            )
        else:
            # 非流式响应：从返回值中提取 usage 并结算
            if isinstance(response, dict):
                usage = response.get("usage", {})
                billing.update_usage(
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                )
            await billing.settle()
            return response

    except Exception as e:
        # 错误时全额退款
        log.error(f"[Billing] 请求失败，执行退款: {e}")
        await billing.refund()
        raise
