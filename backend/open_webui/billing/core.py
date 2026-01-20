"""
计费核心逻辑

提供费用计算、余额扣除、预扣费、结算等核心功能

金额单位说明：
- 存储单位：毫（整数），1元 = 10000毫
- 定价单位：毫/百万tokens
"""

import time
import uuid
import logging
from typing import Tuple, Optional

from fastapi import HTTPException

from open_webui.models.users import User
from open_webui.models.billing import BillingLog, ModelPricings, RechargeLog
from open_webui.internal.db import get_db
from open_webui.billing.ratio import DEFAULT_PRICING
from open_webui.config import PersistentConfig

log = logging.getLogger(__name__)


# ============================================================================
# 配置项
# ============================================================================

# 充值档位（毫），默认 [10, 50, 100, 200, 500, 1000] 元
RECHARGE_TIERS = PersistentConfig(
    "RECHARGE_TIERS",
    "billing.recharge_tiers",
    [100000, 500000, 1000000, 2000000, 5000000, 10000000],
)


# ============================================================================
# Token 估算函数
# ============================================================================


def estimate_image_tokens(image_item: dict, model_id: str) -> int:
    """
    估算图片的 token 数量 （未验证过）

    基于 new-api 的实现，支持多种计算策略：
    - Tile-based (GPT-4o): 基础 85 + 每 512x512 块 170 tokens
    - Patch-based (GPT-4.1-mini): 32x32 像素块，上限 1536
    - Fixed (GLM-4 等): 固定 token 数

    由于无法获取图片实际尺寸，使用保守的默认估算值

    Args:
        image_item: 图片内容项 {"type": "image_url", "image_url": {"url": "..."}}
        model_id: 模型 ID

    Returns:
        int: 估算的 token 数量
    """
    model_lower = model_id.lower()

    # GPT-4o 系列: Tile-based，中等尺寸约 765 tokens
    if "gpt-4o" in model_lower or "gpt-4-vision" in model_lower:
        # 假设中等尺寸图片：85 基础 + 4 块 * 170 = 765
        return 765

    # GPT-4.1-mini: Patch-based
    if "gpt-4.1" in model_lower or "gpt-4-1" in model_lower:
        return 1105  # 保守估算

    # Claude 系列: 按像素计费，中等尺寸约 1000-2000 tokens
    if "claude" in model_lower:
        return 1500

    # GLM-4 系列: 固定 token
    if "glm" in model_lower:
        return 1047

    # Gemini 系列
    if "gemini" in model_lower:
        return 1000

    # 其他模型: 保守默认值
    return 1000


def estimate_video_tokens(model_id: str) -> int:
    """
    估算视频的 token 数量（未验证过）

    基于 new-api: 固定 4096 * 2 = 8192 tokens

    Args:
        model_id: 模型 ID

    Returns:
        int: 估算的 token 数量
    """
    return 8192


def estimate_file_tokens(model_id: str) -> int:
    """
    估算文件的 token 数量（未验证过）

    基于 new-api: 固定 4096 tokens

    Args:
        model_id: 模型 ID

    Returns:
        int: 估算的 token 数量
    """
    return 4096


def _get_content_type(item: dict) -> str:
    """
    获取多模态内容项的类型（未验证过）

    Args:
        item: 内容项

    Returns:
        str: 类型 (text, image, audio, video, file)
    """
    item_type = item.get("type", "")

    if item_type == "text":
        return "text"
    elif item_type in ("image_url", "image"):
        return "image"
    elif item_type in ("input_audio", "audio"):
        return "audio"
    elif item_type == "video":
        return "video"
    elif item_type == "file":
        return "file"

    # 尝试从 URL 推断
    url = ""
    if "image_url" in item:
        url = item["image_url"].get("url", "")
    elif "url" in item:
        url = item.get("url", "")

    if url:
        url_lower = url.lower()
        if any(ext in url_lower for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]):
            return "image"
        elif any(ext in url_lower for ext in [".mp3", ".wav", ".ogg", ".m4a", ".flac"]):
            return "audio"
        elif any(ext in url_lower for ext in [".mp4", ".avi", ".mov", ".webm"]):
            return "video"

    return "unknown"


def estimate_prompt_tokens(messages: list, model_id: str) -> int:
    """
    使用 tiktoken 预估 prompt tokens

    支持多模态内容：
    - 文本: tiktoken 编码
    - 图片: 基于模型的固定估算
    - 音频: 基于时长估算（如有）
    - 视频/文件: 固定估算

    Args:
        messages: OpenAI 格式消息 [{"role": "user", "content": "..."}]
        model_id: 模型 ID

    Returns:
        int: 预估的 prompt tokens 数量
    """
    try:
        import tiktoken

        # 选择 encoding（GPT-4/3.5/Claude 都用 cl100k_base）
        encoding = tiktoken.get_encoding("cl100k_base")

        total_tokens = 0
        for message in messages:
            # 每条消息有 4 tokens 开销（role + content 结构）
            total_tokens += 4
            for key, value in message.items():
                if isinstance(value, str):
                    total_tokens += len(encoding.encode(value))
                elif isinstance(value, list):
                    # 处理多模态消息
                    for item in value:
                        if not isinstance(item, dict):
                            continue

                        content_type = _get_content_type(item)

                        if content_type == "text":
                            text = item.get("text", "")
                            total_tokens += len(encoding.encode(text))
                        elif content_type == "image":
                            total_tokens += estimate_image_tokens(item, model_id)
                        elif content_type == "audio":
                            # 音频通常需要时长信息，这里用默认值
                            total_tokens += 1000  # 约 1 分钟音频
                        elif content_type == "video":
                            total_tokens += estimate_video_tokens(model_id)
                        elif content_type == "file":
                            total_tokens += estimate_file_tokens(model_id)
                        # unknown 类型跳过

        # 额外的系统开销
        total_tokens += 2

        return total_tokens

    except Exception as e:
        # tiktoken 失败时降级为字符估算
        log.warning(f"tiktoken 预估失败，降级为字符估算: {e}")
        return _estimate_prompt_tokens_fallback(messages, model_id)


def _estimate_prompt_tokens_fallback(messages: list, model_id: str) -> int:
    """
    降级的 token 估算（不依赖 tiktoken）

    Args:
        messages: 消息列表
        model_id: 模型 ID

    Returns:
        int: 估算的 token 数量
    """
    char_count = 0
    image_count = 0
    audio_count = 0
    video_count = 0
    file_count = 0

    for message in messages:
        content = message.get("content", "")
        if isinstance(content, str):
            char_count += len(content)
        elif isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue

                content_type = _get_content_type(item)

                if content_type == "text":
                    char_count += len(item.get("text", ""))
                elif content_type == "image":
                    image_count += 1
                elif content_type == "audio":
                    audio_count += 1
                elif content_type == "video":
                    video_count += 1
                elif content_type == "file":
                    file_count += 1

    # 文本: 1 token ≈ 4 字符
    text_tokens = max(char_count // 4, 10)

    # 多模态
    multimodal_tokens = (
        image_count * estimate_image_tokens({}, model_id)
        + audio_count * 1000  # 约 1 分钟
        + video_count * estimate_video_tokens(model_id)
        + file_count * estimate_file_tokens(model_id)
    )

    return text_tokens + multimodal_tokens


def estimate_completion_tokens(content: str, model_id: str) -> int:
    """
    使用tiktoken估算completion tokens

    用于API未返回usage时的后备估算

    Args:
        content: 累计的输出文本
        model_id: 模型ID

    Returns:
        int: 估算的completion tokens数量
    """
    if not content:
        return 0

    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(content))
    except Exception as e:
        log.warning(f"tiktoken估算completion_tokens失败，降级为字符估算: {e}")
        return max(len(content) // 4, 10)  # 1 token ≈ 4字符


# ============================================================================
# 费用计算
# ============================================================================

# 缓存 token 价格倍率（通常为原价的 10%）
CACHE_TOKEN_RATIO = 0.1

# 信任额度阈值（毫）：余额超过此值的用户跳过预扣费
# 默认 0.1 元 = 1000 毫
TRUST_QUOTA_THRESHOLD = 1000


def check_trust_quota(user_id: str) -> bool:
    """
    检查用户是否满足信任额度条件

    信任额度机制：
    - 余额超过阈值的用户可以跳过预扣费
    - 直接进行后付费结算，提升响应速度

    Args:
        user_id: 用户 ID

    Returns:
        bool: True 表示用户可以使用信任额度（跳过预扣费）
    """
    try:
        balance_info = get_user_balance(user_id)
        if not balance_info:
            return False

        balance, _, status = balance_info

        # 账户冻结不享受信任额度
        # if status == "frozen":
        #     return False

        # 余额超过阈值才享受信任额度
        return balance >= TRUST_QUOTA_THRESHOLD

    except Exception as e:
        log.debug(f"检查信任额度失败: {e}")
        return False


def get_model_pricing(model_id: str) -> Tuple[int, int]:
    """
    获取模型定价

    Args:
        model_id: 模型标识

    Returns:
        Tuple[int, int]: (input_price, output_price) 毫/百万tokens
    """
    pricing = ModelPricings.get_by_model_id(model_id)

    if pricing:
        return pricing.input_price, pricing.output_price
    else:
        default = DEFAULT_PRICING.get(model_id, DEFAULT_PRICING["default"])
        return default["input"], default["output"]


def calculate_cost(
    model_id: str, prompt_tokens: int, completion_tokens: int
) -> int:
    """
    计算费用（基础版本，内部调用 calculate_cost_with_usage）

    Args:
        model_id: 模型标识
        prompt_tokens: 输入 token 数
        completion_tokens: 输出 token 数

    Returns:
        int: 费用（毫），1元 = 10000毫，精度为 0.0001元
    """
    from open_webui.billing.usage import UsageInfo

    usage = UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return calculate_cost_with_usage(model_id, usage)


def calculate_cost_with_usage(model_id: str, usage: "UsageInfo") -> int:
    """
    计算费用（完整版本，支持缓存和推理 token）

    费用公式：
    - 输入费用 = prompt_tokens * input_price + cached_tokens * input_price * CACHE_RATIO
    - 输出费用 = (completion_tokens + reasoning_tokens) * output_price

    注意：
    - cached_tokens 按 10% 原价计费（Claude/OpenAI 缓存命中优惠）
    - reasoning_tokens 按输出价格计费（推理模型思考 token）
    - cache_creation_tokens 按原价计费（首次写入缓存）

    Args:
        model_id: 模型标识
        usage: 标准化的 UsageInfo 对象

    Returns:
        int: 费用（毫）
    """
    # 延迟导入避免循环引用
    from open_webui.billing.usage import UsageInfo

    input_price, output_price = get_model_pricing(model_id)

    # 输入费用
    # - 普通 prompt: 全价
    # - 缓存命中: 10% 价格
    # - 缓存创建: 全价（首次写入）
    input_cost_raw = (
        usage.prompt_tokens * input_price
        + int(usage.cached_tokens * input_price * CACHE_TOKEN_RATIO)
        + usage.cache_creation_tokens * input_price
    )

    # 输出费用
    # - completion + reasoning 都按输出价格
    output_cost_raw = (usage.completion_tokens + usage.reasoning_tokens) * output_price

    total_cost_raw = input_cost_raw + output_cost_raw

    return _finalize_cost(total_cost_raw)


def _finalize_cost(total_cost_raw: int) -> int:
    """
    费用最终处理（向上取整，最小 1 毫）

    Args:
        total_cost_raw: 原始费用（未除以 1000000）

    Returns:
        int: 最终费用（毫）
    """
    if total_cost_raw > 0:
        # 向上取整: ceil(a/b) = (a + b - 1) // b
        total_cost = (total_cost_raw + 999999) // 1000000
        # 如果计算结果 < 1 毫，至少扣 1 毫
        total_cost = max(1, total_cost)
    else:
        total_cost = 0

    return total_cost


def deduct_balance(
    user_id: str,
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    log_type: str = "deduct",
    estimated_tokens: Optional[int] = None,
    custom_input_price: Optional[int] = None,
    custom_output_price: Optional[int] = None,
) -> Tuple[int, int]:
    """
    扣除用户余额（带行锁，防止并发超扣）

    Args:
        user_id: 用户ID
        model_id: 模型标识
        prompt_tokens: 输入token数
        completion_tokens: 输出token数
        log_type: 日志类型（deduct/refund/precharge/deduct_summary等）
        custom_input_price: 自定义输入价格（毫/百万tokens），None时使用数据库/默认价格
        custom_output_price: 自定义输出价格（毫/百万tokens），None时使用数据库/默认价格

    Returns:
        Tuple[int, int]: (本次费用（毫）, 扣费后余额（毫）)

    Raises:
        HTTPException: 用户不存在、账户冻结、余额不足

    Examples:
        # 标准用法（使用数据库/默认价格）
        cost, balance = deduct_balance(
            user_id="user123",
            model_id="gpt-4o",
            prompt_tokens=1000,
            completion_tokens=500
        )

        # 自定义价格（如摘要生成使用特殊价格）
        cost, balance = deduct_balance(
            user_id="user123",
            model_id="gpt-4o-mini",
            prompt_tokens=2000,
            completion_tokens=800,
            log_type="deduct_summary",
            custom_input_price=1000,   # 0.1元/M
            custom_output_price=2000   # 0.2元/M
        )
    """
    with get_db() as db:
        # 1. 行锁获取用户（防止并发）
        user = db.query(User).filter_by(id=user_id).with_for_update().first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 2. 检查账户状态
        # if user.billing_status == "frozen":
        #     raise HTTPException(status_code=403, detail="账户已冻结，请联系管理员充值")

        # 3. 计算费用（毫）
        if custom_input_price is not None or custom_output_price is not None:
            # 使用自定义价格
            pricing = ModelPricings.get_by_model_id(model_id)
            if pricing:
                base_input_price = pricing.input_price
                base_output_price = pricing.output_price
            else:
                default = DEFAULT_PRICING.get(model_id, DEFAULT_PRICING["default"])
                base_input_price = default["input"]
                base_output_price = default["output"]

            final_input_price = custom_input_price if custom_input_price is not None else base_input_price
            final_output_price = custom_output_price if custom_output_price is not None else base_output_price

            # 计算总费用
            input_cost_raw = prompt_tokens * final_input_price
            output_cost_raw = completion_tokens * final_output_price
            total_cost_raw = input_cost_raw + output_cost_raw

            if total_cost_raw > 0:
                cost = (total_cost_raw + 999999) // 1000000
                cost = max(1, cost)
            else:
                cost = 0
        else:
            # 使用标准价格计算
            cost = calculate_cost(model_id, prompt_tokens, completion_tokens)

        # 4. 检查余额
        balance_before = user.balance or 0
        if balance_before < cost:
            raise HTTPException(
                status_code=402,
                detail=f"余额不足：当前 {balance_before / 10000:.4f} 元，需要 {cost / 10000:.4f} 元",
            )

        # 5. 扣费
        user.balance = balance_before - cost
        user.total_consumed = (user.total_consumed or 0) + cost

        # 6. 余额不足时冻结账户（< 0.01元 = 100毫）
        # if user.balance < 100:
        #     user.billing_status = "frozen"
        #     log.warning(f"用户 {user_id} 余额不足，账户已冻结")

        # 7. 记录日志
        billing_log = BillingLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            model_id=model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_cost=cost,
            balance_after=user.balance,
            log_type=log_type,
            estimated_tokens=estimated_tokens
            if estimated_tokens is not None
            else prompt_tokens + completion_tokens,
            created_at=int(time.time() * 1000000000),  # 纳秒级时间戳
        )
        db.add(billing_log)

        # 8. 提交事务
        db.commit()

        # 9. 日志输出
        pricing_info = ""
        if custom_input_price is not None or custom_output_price is not None:
            parts = []
            if custom_input_price is not None:
                parts.append(f"自定义输入={custom_input_price / 10000:.4f}元/M")
            if custom_output_price is not None:
                parts.append(f"自定义输出={custom_output_price / 10000:.4f}元/M")
            pricing_info = f" ({', '.join(parts)})"

        log.info(
            f"用户 {user_id} 使用模型 {model_id} 扣费 {cost / 10000:.4f} 元，"
            f"余额 {balance_before / 10000:.4f} -> {user.balance / 10000:.4f}"
            f"{pricing_info}"
        )

        return cost, user.balance


def deduct_balance_with_usage(
    user_id: str,
    model_id: str,
    usage_info: "UsageInfo",
    log_type: str = "deduct",
) -> Tuple[int, int]:
    """
    扣除用户余额（使用完整 UsageInfo，支持缓存和推理 token）

    Args:
        user_id: 用户ID
        model_id: 模型标识
        usage_info: 完整的 UsageInfo 对象
        log_type: 日志类型

    Returns:
        Tuple[int, int]: (本次费用（毫）, 扣费后余额（毫）)

    Raises:
        HTTPException: 用户不存在、账户冻结、余额不足
    """
    from open_webui.billing.usage import UsageInfo

    with get_db() as db:
        # 1. 行锁获取用户
        user = db.query(User).filter_by(id=user_id).with_for_update().first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 2. 检查账户状态
        # if user.billing_status == "frozen":
        #     raise HTTPException(status_code=403, detail="账户已冻结，请联系管理员充值")

        # 3. 使用完整 UsageInfo 计算费用
        cost = calculate_cost_with_usage(model_id, usage_info)

        # 4. 检查余额
        balance_before = user.balance or 0
        if balance_before < cost:
            raise HTTPException(
                status_code=402,
                detail=f"余额不足：当前 {balance_before / 10000:.4f} 元，需要 {cost / 10000:.4f} 元",
            )

        # 5. 扣费
        user.balance = balance_before - cost
        user.total_consumed = (user.total_consumed or 0) + cost

        # 6. 余额不足时冻结账户
        # if user.balance < 100:
        #     user.billing_status = "frozen"
        #     log.warning(f"用户 {user_id} 余额不足，账户已冻结")

        # 7. 记录日志（包含完整 token 信息）
        billing_log = BillingLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            model_id=model_id,
            prompt_tokens=usage_info.prompt_tokens + usage_info.cached_tokens,
            completion_tokens=usage_info.completion_tokens + usage_info.reasoning_tokens,
            total_cost=cost,
            balance_after=user.balance,
            log_type=log_type,
            created_at=int(time.time() * 1000000000),
        )
        db.add(billing_log)

        # 8. 提交事务
        db.commit()

        # 9. 日志输出
        log.info(
            f"用户 {user_id} 使用模型 {model_id} 扣费 {cost / 10000:.4f} 元，"
            f"prompt={usage_info.prompt_tokens} cached={usage_info.cached_tokens} "
            f"completion={usage_info.completion_tokens} reasoning={usage_info.reasoning_tokens} "
            f"余额 {balance_before / 10000:.4f} -> {user.balance / 10000:.4f}"
        )

        return cost, user.balance


def recharge_user(
    user_id: str, amount: int, operator_id: str, remark: str = ""
) -> int:
    """
    用户充值/扣费

    Args:
        user_id: 用户ID
        amount: 充值金额（毫），正数充值，负数扣费，1元 = 10000毫
        operator_id: 操作员ID
        remark: 备注

    Returns:
        int: 充值/扣费后余额（毫）

    Raises:
        HTTPException: 用户不存在、金额无效或余额不足
    """
    if amount == 0:
        raise HTTPException(status_code=400, detail="金额不能为0")

    with get_db() as db:
        # 1. 行锁获取用户
        user = db.query(User).filter_by(id=user_id).with_for_update().first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 2. 扣费时检查余额是否足够
        balance_before = user.balance or 0
        if amount < 0:
            if balance_before + amount < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"余额不足,当前余额 {balance_before / 10000:.2f} 元"
                )

        # 3. 充值/扣费
        user.balance = balance_before + amount

        # 4. 账户状态自动管理（< 0.01元 = 100毫）
        # if user.balance < 100:
        #     user.billing_status = "frozen"
        if user.balance >= 100:
            user.billing_status = "active"

        # 5. 记录充值日志
        recharge_log = RechargeLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount=amount,
            operator_id=operator_id,
            remark=remark,
            created_at=int(time.time() * 1000000000),  # 纳秒级时间戳
        )
        db.add(recharge_log)

        # 6. 提交事务
        db.commit()

        operation_text = "充值" if amount > 0 else "扣费"
        log.info(
            f"用户 {user_id} {operation_text} {abs(amount) / 10000:.2f} 元，"
            f"余额 {balance_before / 10000:.4f} -> {user.balance / 10000:.4f}，"
            f"操作员 {operator_id}"
        )

        return user.balance


def get_user_balance(user_id: str) -> Optional[Tuple[int, int, str]]:
    """
    获取用户余额信息

    Args:
        user_id: 用户ID

    Returns:
        Optional[Tuple[int, int, str]]: (余额（毫）, 累计消费（毫）, 账户状态) 或 None
    """
    try:
        with get_db() as db:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return None

            return (
                user.balance or 0,
                user.total_consumed or 0,
                user.billing_status or "active",
            )
    except Exception as e:
        log.error(f"获取用户余额失败: {e}")
        return None


def precharge_balance(
    user_id: str,
    model_id: str,
    estimated_prompt_tokens: int,
    max_completion_tokens: int = 4096,
) -> Tuple[str, int, int]:
    """
    预扣费（冻结余额）

    Args:
        user_id: 用户ID
        model_id: 模型ID
        estimated_prompt_tokens: 预估的输入tokens
        max_completion_tokens: 最大输出tokens

    Returns:
        Tuple[str, int, int]: (预扣费ID, 预扣金额（毫）, 剩余余额（毫）)

    Raises:
        HTTPException: 余额不足或账户冻结
    """
    with get_db() as db:
        # 1. 行锁获取用户
        user = db.query(User).filter_by(id=user_id).with_for_update().first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # if user.billing_status == "frozen":
        #     raise HTTPException(status_code=403, detail="账户已冻结")

        # 2. 计算最大可能费用
        max_cost = calculate_cost(model_id, estimated_prompt_tokens, max_completion_tokens)

        # 3. 检查余额
        balance_before = user.balance or 0
        if balance_before < max_cost:
            raise HTTPException(
                status_code=402,
                detail=f"余额不足：当前 {balance_before / 10000:.4f} 元，预估需要 {max_cost / 10000:.4f} 元",
            )

        # 4. 预扣费
        user.balance = balance_before - max_cost

        # 5. 创建预扣费记录
        precharge_id = str(uuid.uuid4())
        billing_log = BillingLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            model_id=model_id,
            prompt_tokens=0,  # 实际tokens在settle时更新
            completion_tokens=0,
            total_cost=max_cost,
            balance_after=user.balance,
            log_type="precharge",
            precharge_id=precharge_id,
            status="precharge",
            estimated_tokens=estimated_prompt_tokens + max_completion_tokens,
            created_at=int(time.time() * 1000000000),
        )
        db.add(billing_log)
        db.commit()

        log.info(
            f"预扣费成功: user={user_id} model={model_id} "
            f"estimated={estimated_prompt_tokens}+{max_completion_tokens}tokens "
            f"cost={max_cost / 10000:.4f}元 precharge_id={precharge_id}"
        )

        return precharge_id, max_cost, user.balance


def settle_precharge_with_usage(
    precharge_id: str, usage_info: "UsageInfo"
) -> Tuple[int, int, int]:
    """
    结算预扣费（使用完整 UsageInfo，支持缓存和推理 token）

    Args:
        precharge_id: 预扣费事务ID
        usage_info: 完整的 UsageInfo 对象

    Returns:
        Tuple[int, int, int]: (实际费用（毫）, 退款金额（毫）, 结算后余额（毫）)
    """
    from open_webui.billing.usage import UsageInfo

    with get_db() as db:
        # 1. 查询预扣费记录
        precharge_log = (
            db.query(BillingLog)
            .filter_by(precharge_id=precharge_id, status="precharge")
            .first()
        )

        if not precharge_log:
            log.warning(f"预扣费记录不存在: precharge_id={precharge_id}")
            return 0, 0, 0

        # 2. 行锁获取用户
        user = db.query(User).filter_by(id=precharge_log.user_id).with_for_update().first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 3. 使用完整 UsageInfo 计算实际费用
        actual_cost = calculate_cost_with_usage(precharge_log.model_id, usage_info)

        # 4. 计算差额
        precharged_cost = precharge_log.total_cost
        diff = precharged_cost - actual_cost

        # 5. 调整余额
        if diff > 0:
            user.balance += diff
            refund_amount = diff
        elif diff < 0:
            additional_cost = abs(diff)
            if user.balance < additional_cost:
                log.warning(
                    f"补扣余额不足: user={user.id} need={additional_cost / 10000:.4f}元 "
                    f"balance={user.balance / 10000:.4f}元"
                )
                user.balance = 0
                # user.billing_status = "frozen"
            else:
                user.balance -= additional_cost
            refund_amount = -additional_cost
        else:
            refund_amount = 0

        # 6. 更新累计消费
        user.total_consumed = (user.total_consumed or 0) + actual_cost

        # 7. 更新预扣费记录状态
        precharge_log.status = "settled"

        # 8. 创建结算记录（包含完整 token 信息）
        settle_log = BillingLog(
            id=str(uuid.uuid4()),
            user_id=user.id,
            model_id=precharge_log.model_id,
            prompt_tokens=usage_info.prompt_tokens + usage_info.cached_tokens,
            completion_tokens=usage_info.completion_tokens + usage_info.reasoning_tokens,
            total_cost=actual_cost,
            balance_after=user.balance,
            log_type="settle",
            precharge_id=precharge_id,
            status="settled",
            refund_amount=refund_amount,
            created_at=int(time.time() * 1000000000),
        )
        db.add(settle_log)

        # 9. 提交事务
        db.commit()

        log.info(
            f"结算成功(精确): user={user.id} precharge_id={precharge_id} "
            f"prompt={usage_info.prompt_tokens} cached={usage_info.cached_tokens} "
            f"completion={usage_info.completion_tokens} reasoning={usage_info.reasoning_tokens} "
            f"cost={actual_cost / 10000:.4f}元 refund={refund_amount / 10000:.4f}元"
        )

        return actual_cost, refund_amount, user.balance


def settle_precharge(
    precharge_id: str, actual_prompt_tokens: int, actual_completion_tokens: int
) -> Tuple[int, int, int]:
    """
    结算预扣费（退还差额或补扣不足）

    Args:
        precharge_id: 预扣费事务ID
        actual_prompt_tokens: 实际消费的prompt tokens
        actual_completion_tokens: 实际消费的completion tokens

    Returns:
        Tuple[int, int, int]: (实际费用（毫）, 退款金额（毫）, 结算后余额（毫）)
    """
    with get_db() as db:
        # 1. 查询预扣费记录
        precharge_log = (
            db.query(BillingLog)
            .filter_by(precharge_id=precharge_id, status="precharge")
            .first()
        )

        if not precharge_log:
            log.warning(f"预扣费记录不存在: precharge_id={precharge_id}")
            # 降级为直接扣费
            if actual_prompt_tokens > 0 or actual_completion_tokens > 0:
                cost, balance_after = deduct_balance(
                    user_id="unknown",
                    model_id="unknown",
                    prompt_tokens=actual_prompt_tokens,
                    completion_tokens=actual_completion_tokens,
                    log_type="deduct",
                )
                return cost, 0, balance_after
            return 0, 0, 0

        # 2. 行锁获取用户
        user = db.query(User).filter_by(id=precharge_log.user_id).with_for_update().first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 3. 计算实际费用
        actual_cost = calculate_cost(
            precharge_log.model_id, actual_prompt_tokens, actual_completion_tokens
        )

        # 4. 计算差额
        precharged_cost = precharge_log.total_cost
        diff = precharged_cost - actual_cost  # 正数=退款，负数=补扣

        # 5. 调整余额
        if diff > 0:
            # 退款
            user.balance += diff
            refund_amount = diff
        elif diff < 0:
            # 补扣
            additional_cost = abs(diff)
            if user.balance < additional_cost:
                # 余额不足以补扣
                log.warning(
                    f"补扣余额不足: user={user.id} need={additional_cost / 10000:.4f}元 "
                    f"balance={user.balance / 10000:.4f}元"
                )
                # 扣除所有余额，标记账户冻结
                user.balance = 0
                # user.billing_status = "frozen"
            else:
                user.balance -= additional_cost
            refund_amount = -additional_cost
        else:
            refund_amount = 0

        # 6. 更新累计消费
        user.total_consumed = (user.total_consumed or 0) + actual_cost

        # 7. 更新预扣费记录状态
        precharge_log.status = "settled"

        # 8. 创建结算记录
        settle_log = BillingLog(
            id=str(uuid.uuid4()),
            user_id=user.id,
            model_id=precharge_log.model_id,
            prompt_tokens=actual_prompt_tokens,
            completion_tokens=actual_completion_tokens,
            total_cost=actual_cost,
            balance_after=user.balance,
            log_type="settle",
            precharge_id=precharge_id,
            status="settled",
            refund_amount=refund_amount,
            created_at=int(time.time() * 1000000000),
        )
        db.add(settle_log)

        # 9. 提交事务
        db.commit()

        log.info(
            f"结算成功: user={user.id} precharge_id={precharge_id} "
            f"actual={actual_prompt_tokens}+{actual_completion_tokens}tokens "
            f"cost={actual_cost / 10000:.4f}元 refund={refund_amount / 10000:.4f}元 "
            f"balance={user.balance / 10000:.4f}元"
        )

        return actual_cost, refund_amount, user.balance


def check_user_balance_threshold(
    user_id: str,
    threshold: int = 100  # 默认100毫 = 0.01元
) -> None:
    """
    检查用户余额是否满足阈值要求

    Args:
        user_id: 用户ID
        threshold: 最低余额阈值（毫），默认100毫 = 0.01元

    Raises:
        HTTPException:
            - 402: 余额不足
            - 403: 账户已冻结

    Note:
        - 如果billing模块不存在，静默跳过
        - 如果发生其他异常，静默跳过（记录日志但不阻断请求）
    """
    try:
        balance_info = get_user_balance(user_id)
        if not balance_info:
            return  # 用户不存在或查询失败，跳过检查

        balance, _, status = balance_info

        # # 检查账户状态
        # if status == "frozen":
        #     raise HTTPException(
        #         status_code=403,
        #         detail="账户已冻结，请联系管理员充值"
        #     )

        # 检查余额阈值
        if balance < threshold:
            raise HTTPException(
                status_code=402,
                detail=f"余额不足: 当前余额 {balance / 10000:.4f} 元，"
                       f"最低需要 {threshold / 10000:.4f} 元，请前往计费中心充值"
            )

    except HTTPException:
        # 业务异常（余额不足/账户冻结），向上抛出
        raise

    except Exception as e:
        # 其他异常仅记录日志，不阻断请求
        log.error(f"计费预检查异常: {e}")


def convert_billing_exception_to_customized_error(e: Exception) -> "CustmizedError":
    """
    将计费相关的 HTTPException 转换为 CustmizedError

    Args:
        e: HTTPException 实例

    Returns:
        CustmizedError: 包含用户友好错误信息的自定义异常
    """
    from open_webui.utils.chat_error_boundary import CustmizedError

    if not isinstance(e, HTTPException):
        return CustmizedError("计费系统错误", cause=e)

    # 根据状态码映射用户友好的错误信息
    if e.status_code == 402:
        # 余额不足 - 保留原始详细信息
        user_message = f"{e.detail}\n\n请前往【计费中心】充值后继续使用。"
    elif e.status_code == 403:
        # 账户冻结
        user_message = f"{e.detail}\n\n请联系管理员处理。"
    elif e.status_code == 404:
        # 用户不存在
        user_message = "用户信息异常，请重新登录。"
    else:
        # 其他计费错误
        user_message = f"计费系统错误：{e.detail}"

    return CustmizedError(user_message, cause=e)
