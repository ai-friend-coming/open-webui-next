"""
计费上下文管理器

管理预扣费 → 结算/退款的完整生命周期

使用方式：
    billing = BillingContext(user_id, model_id, messages, max_tokens)
    await billing.precharge()  # 预扣费

    # ... 执行 LLM 请求 ...

    billing.update_usage(prompt_tokens, completion_tokens)
    await billing.settle()  # 结算

    # 或者发生错误时：
    await billing.refund()  # 全额退款
"""

import logging
from typing import Optional
from dataclasses import dataclass, field

from open_webui.billing.core import (
    estimate_prompt_tokens,
    precharge_balance,
    settle_precharge,
    deduct_balance,
)

log = logging.getLogger(__name__)


@dataclass
class BillingContext:
    """计费上下文"""

    user_id: str
    model_id: str
    messages: list
    max_completion_tokens: int = 4096
    stream: bool = True

    # 内部状态
    precharge_id: Optional[str] = field(default=None, init=False)
    precharged_cost: int = field(default=0, init=False)
    estimated_prompt: int = field(default=0, init=False)
    actual_usage: dict = field(default_factory=lambda: {"prompt": 0, "completion": 0}, init=False)
    has_usage_data: bool = field(default=False, init=False)
    settled: bool = field(default=False, init=False)
    enabled: bool = field(default=True, init=False)

    async def precharge(self) -> bool:
        """
        执行预扣费

        Returns:
            bool: 预扣费是否成功
        """
        if not self.enabled:
            return True

        try:
            # 1. 预估 prompt tokens
            self.estimated_prompt = estimate_prompt_tokens(self.messages, self.model_id)

            # 2. 预扣费
            self.precharge_id, self.precharged_cost, balance = precharge_balance(
                user_id=self.user_id,
                model_id=self.model_id,
                estimated_prompt_tokens=self.estimated_prompt,
                max_completion_tokens=self.max_completion_tokens,
            )

            log.info(
                f"[Billing] 预扣费成功: user={self.user_id} model={self.model_id} "
                f"estimated={self.estimated_prompt}+{self.max_completion_tokens} "
                f"cost={self.precharged_cost / 10000:.4f}元"
            )
            return True

        except Exception as e:
            # 余额不足等异常向上抛出
            log.warning(f"[Billing] 预扣费失败: {e}")
            raise

    async def settle(self) -> None:
        """执行结算逻辑"""
        if not self.enabled:
            return

        if self.settled:
            return
        self.settled = True

        try:
            if self.precharge_id:
                # 预扣费模式：结算
                if not self.has_usage_data:
                    # 未收到 usage，使用预估值
                    self.actual_usage["prompt"] = self.estimated_prompt

                actual_cost, refund, balance = settle_precharge(
                    precharge_id=self.precharge_id,
                    actual_prompt_tokens=self.actual_usage["prompt"],
                    actual_completion_tokens=self.actual_usage["completion"],
                )

                log.info(
                    f"[Billing] 结算完成: precharge_id={self.precharge_id} "
                    f"actual={self.actual_usage['prompt']}+{self.actual_usage['completion']} "
                    f"cost={actual_cost / 10000:.4f}元 refund={refund / 10000:.4f}元"
                )

            elif self.actual_usage["prompt"] > 0 or self.actual_usage["completion"] > 0:
                # 无预扣费但有 usage，直接扣费（降级模式）
                cost, balance = deduct_balance(
                    user_id=self.user_id,
                    model_id=self.model_id,
                    prompt_tokens=self.actual_usage["prompt"],
                    completion_tokens=self.actual_usage["completion"],
                )

                log.info(
                    f"[Billing] 后付费扣费: user={self.user_id} "
                    f"tokens={self.actual_usage['prompt']}+{self.actual_usage['completion']} "
                    f"cost={cost / 10000:.4f}元"
                )

        except Exception as e:
            log.error(f"[Billing] 结算异常: {e}", exc_info=True)

    async def refund(self) -> None:
        """全额退款（请求失败时调用）"""
        if not self.enabled:
            return

        if self.precharge_id and not self.settled:
            self.settled = True
            try:
                settle_precharge(self.precharge_id, 0, 0)
                log.info(f"[Billing] 已退款: precharge_id={self.precharge_id}")
            except Exception as e:
                log.error(f"[Billing] 退款失败: {e}")

    def update_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """
        更新实际 usage（流式过程中调用）

        Args:
            prompt_tokens: 实际 prompt tokens
            completion_tokens: 实际 completion tokens
        """
        self.has_usage_data = True
        self.actual_usage["prompt"] = max(self.actual_usage["prompt"], prompt_tokens)
        self.actual_usage["completion"] = max(self.actual_usage["completion"], completion_tokens)

    def disable(self) -> None:
        """禁用计费（用于不需要计费的请求）"""
        self.enabled = False
