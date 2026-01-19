"""
邀请码生成工具

使用 secrets 模块生成加密安全的随机邀请码，排除易混淆字符
"""

import secrets
import logging

log = logging.getLogger(__name__)

# 排除易混淆字符的字符集: 0O, 1Il 等
INVITE_CODE_CHARSET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def generate_invite_code(length: int = 6) -> str:
    """
    生成随机邀请码

    Args:
        length: 邀请码长度，默认6位

    Returns:
        随机邀请码字符串
    """
    return ''.join(secrets.choice(INVITE_CODE_CHARSET) for _ in range(length))


def generate_unique_invite_code(
    check_exists_fn,
    default_length: int = 6,
    fallback_length: int = 8,
    max_retries: int = 10
) -> str:
    """
    生成唯一邀请码（带冲突重试）

    Args:
        check_exists_fn: 检查邀请码是否存在的函数，接受邀请码字符串，返回布尔值
        default_length: 默认长度，默认6位
        fallback_length: 冲突时回退到的长度，默认8位
        max_retries: 最大重试次数，默认10次

    Returns:
        唯一的邀请码字符串

    Raises:
        RuntimeError: 超过最大重试次数仍未生成唯一邀请码
    """
    # 首先尝试默认长度
    for attempt in range(max_retries):
        code = generate_invite_code(default_length)
        if not check_exists_fn(code):
            log.info(f"Generated unique invite code: {code} (length={default_length}, attempt={attempt+1})")
            return code

    # 默认长度冲突太多，切换到更长的长度
    log.warning(f"Failed to generate unique {default_length}-char invite code after {max_retries} attempts, switching to {fallback_length}-char")

    for attempt in range(max_retries):
        code = generate_invite_code(fallback_length)
        if not check_exists_fn(code):
            log.info(f"Generated unique invite code: {code} (length={fallback_length}, attempt={attempt+1})")
            return code

    # 仍然失败，抛出异常
    raise RuntimeError(f"Failed to generate unique invite code after {max_retries * 2} total attempts")
