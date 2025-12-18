"""
计费模块兼容层

此文件保持向后兼容，所有功能重定向到 open_webui.billing 模块。
新代码应直接从 open_webui.billing 导入。

示例：
    # 旧方式（仍可用）
    from open_webui.utils.billing import calculate_cost

    # 新方式（推荐）
    from open_webui.billing import calculate_cost
"""

# 从 billing 模块重新导出所有公共接口
from open_webui.billing.ratio import DEFAULT_PRICING
from open_webui.billing.core import (
    estimate_prompt_tokens,
    calculate_cost,
    deduct_balance,
    recharge_user,
    get_user_balance,
    precharge_balance,
    settle_precharge,
    check_user_balance_threshold,
    charge_direct,
)

# 保留 safe_deduct_balance_for_middleware 函数（用于 middleware.py）
import logging
from typing import Tuple, Optional
from fastapi import HTTPException

log = logging.getLogger(__name__)


async def safe_deduct_balance_for_middleware(
    user_id: str,
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    event_emitter: Optional[callable] = None,
    log_prefix: str = "计费"
) -> Tuple[Optional[int], Optional[int]]:
    """
    安全扣费包装器（用于middleware.py）

    统一处理计费逻辑、异常处理、日志记录和事件通知

    Args:
        user_id: 用户ID
        model_id: 模型ID
        prompt_tokens: 输入tokens
        completion_tokens: 输出tokens
        event_emitter: 事件发送器（可选）
        log_prefix: 日志前缀（"计费" or "流式计费"）

    Returns:
        Tuple[Optional[int], Optional[int]]: (cost, balance_after) 或 (None, None)
    """
    # 如果tokens都为0，跳过计费
    if prompt_tokens == 0 and completion_tokens == 0:
        return None, None

    try:
        cost, balance_after = deduct_balance(
            user_id=user_id,
            model_id=model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens
        )

        # 统一日志格式（单位：毫 → 元）
        log.info(
            f"{log_prefix}成功: 用户={user_id}, 模型={model_id}, "
            f"tokens={prompt_tokens}+{completion_tokens}, "
            f"费用={cost / 10000:.6f}元, 余额={balance_after / 10000:.4f}元"
        )

        return cost, balance_after

    except ImportError:
        log.warning("billing模块不存在，跳过计费")
        return None, None

    except HTTPException as e:
        # 业务异常（如余额不足）
        log.error(f"{log_prefix}失败（业务异常）: {e.detail}")

        if event_emitter:
            try:
                await event_emitter({
                    "type": "billing:error",
                    "data": {"message": str(e.detail)}
                })
            except Exception:
                pass

        return None, None

    except Exception as e:
        # 系统异常
        log.error(f"{log_prefix}失败（系统异常）: {e}", exc_info=True)

        if event_emitter:
            try:
                await event_emitter({
                    "type": "billing:error",
                    "data": {"message": f"计费系统异常: {str(e)}"}
                })
            except Exception:
                pass

        return None, None


__all__ = [
    "DEFAULT_PRICING",
    "estimate_prompt_tokens",
    "calculate_cost",
    "deduct_balance",
    "recharge_user",
    "get_user_balance",
    "precharge_balance",
    "settle_precharge",
    "check_user_balance_threshold",
    "charge_direct",
    "safe_deduct_balance_for_middleware",
]
