"""
图片描述 API 路由

提供图片自动描述功能，用于聊天界面上传图片时自动生成描述文本
"""

import logging
import base64
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from open_webui.utils.auth import get_verified_user
from open_webui.config import ENABLE_IMAGE_CAPTION, IMAGE_CAPTION_MODEL, IMAGE_CAPTION_BILLING_RATIO

log = logging.getLogger(__name__)

router = APIRouter()


class ImageCaptionRequest(BaseModel):
    """图片描述请求"""
    image_url: str  # base64 编码的图片数据或 URL


class ImageCaptionResponse(BaseModel):
    """图片描述响应"""
    caption: str
    model: str


@router.post("/generate", response_model=ImageCaptionResponse)
async def generate_image_caption(
    request: Request,
    form_data: ImageCaptionRequest,
    user=Depends(get_verified_user)
):
    """
    生成图片描述

    Args:
        request: FastAPI 请求对象
        form_data: 包含图片数据的请求体
        user: 当前用户

    Returns:
        ImageCaptionResponse: 包含描述文本和使用的模型

    Raises:
        HTTPException(400): 功能未启用或配置错误
        HTTPException(500): 生成描述失败
    """
    try:
        # 检查功能是否启用
        if not ENABLE_IMAGE_CAPTION.value:
            raise HTTPException(
                status_code=400,
                detail="Image caption feature is not enabled"
            )

        # 检查是否配置了模型
        caption_model = IMAGE_CAPTION_MODEL.value
        if not caption_model:
            raise HTTPException(
                status_code=400,
                detail="Image caption model is not configured"
            )

        # 调用 vision 模型生成描述
        from open_webui.main import generate_chat_completions

        # 构建消息
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": form_data.image_url}
                    },
                    {
                        "type": "text",
                        "text": "Please describe this image in detail."
                    }
                ]
            }
        ]

        # 调用模型
        payload = {
            "model": caption_model,
            "messages": messages,
            "stream": False
        }

        response = await generate_chat_completions(request, form_data=payload, user=user)

        # 应用计费倍率（如果不是 1.0）
        billing_ratio = IMAGE_CAPTION_BILLING_RATIO.value
        if billing_ratio != 1.0:
            try:
                from open_webui.billing.core import deduct_balance_with_usage
                from open_webui.billing.usage import UsageInfo
                from open_webui.models.billing import BillingLog

                # 获取最近的计费记录
                if hasattr(response, 'usage') and response.usage:
                    usage = response.usage
                    # 计算额外费用（倍率 - 1.0）
                    extra_ratio = billing_ratio - 1.0

                    # 构建 UsageInfo
                    usage_info = UsageInfo(
                        prompt_tokens=int(usage.prompt_tokens * extra_ratio),
                        completion_tokens=int(usage.completion_tokens * extra_ratio)
                    )

                    # 额外扣费
                    deduct_balance_with_usage(
                        user_id=user.id,
                        model_id=caption_model,
                        usage=usage_info,
                        note=f"Image caption billing ratio adjustment ({billing_ratio}x)"
                    )

                    log.info(f"Applied caption billing ratio {billing_ratio}x for user {user.id}")
            except Exception as e:
                log.error(f"Failed to apply caption billing ratio: {e}")
                # 不影响主流程，继续返回结果

        # 提取描述文本
        if hasattr(response, 'choices') and len(response.choices) > 0:
            caption = response.choices[0].message.content
        else:
            caption = response.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not caption:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate caption"
            )

        log.info(f"Generated caption for user {user.id} using model {caption_model}")

        return ImageCaptionResponse(
            caption=caption,
            model=caption_model
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error generating image caption: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate image caption: {str(e)}"
        )


@router.get("/config")
async def get_image_caption_config(user=Depends(get_verified_user)):
    """
    获取图片描述配置

    Returns:
        dict: 包含启用状态、模型配置和计费倍率
    """
    return {
        "enabled": ENABLE_IMAGE_CAPTION.value,
        "model": IMAGE_CAPTION_MODEL.value,
        "billing_ratio": IMAGE_CAPTION_BILLING_RATIO.value
    }


class ImageCaptionConfigUpdate(BaseModel):
    """图片描述配置更新"""
    enabled: bool
    model: str
    billing_ratio: float = 1.0


@router.post("/config")
async def update_image_caption_config(
    form_data: ImageCaptionConfigUpdate,
    user=Depends(get_verified_user)
):
    """
    更新图片描述配置（仅管理员）

    Args:
        form_data: 配置更新数据
        user: 当前用户

    Returns:
        dict: 更新后的配置

    Raises:
        HTTPException(403): 非管理员用户
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admin users can update image caption config"
        )

    ENABLE_IMAGE_CAPTION.value = form_data.enabled
    IMAGE_CAPTION_MODEL.value = form_data.model
    IMAGE_CAPTION_BILLING_RATIO.value = form_data.billing_ratio

    return {
        "enabled": ENABLE_IMAGE_CAPTION.value,
        "model": IMAGE_CAPTION_MODEL.value,
        "billing_ratio": IMAGE_CAPTION_BILLING_RATIO.value
    }
