"""
用户统计工具模块

提供用户行为统计相关的辅助函数，统计数据存储在 user.info JSON 字段中。

数据结构：
{
  "daily_interaction": {
    "count": 42,
    "date": "2025-12-28",
    "last_interaction_at": 1735383600
  },
  "interaction_history": {
    "2025-12-26": 35,
    "2025-12-27": 48,
    "2025-12-28": 42
  },
  "total_interaction_count": 280
}
"""

from logging import getLogger
from datetime import date, timedelta
import time
from typing import Dict, Optional

log = getLogger(__name__)

# 配置：历史记录保留天数（默认90天）
INTERACTION_HISTORY_RETENTION_DAYS = 90


def increment_daily_interaction_count(user_id: str) -> None:
    """
    增加用户的当日交互计数（存储在 user.info.daily_interaction 中）

    功能：
    - 检测日期变化，跨天时自动重置计数
    - 记录最后交互时间
    - 同时维护累计总交互次数
    - 维护每日交互历史记录（interaction_history）
    - 自动清理超过保留期的历史数据

    参数：
        user_id: 用户 ID

    示例：
        >>> increment_daily_interaction_count("user-123")
        # user.info.daily_interaction.count: 0 -> 1
        # user.info.interaction_history["2025-12-28"]: 0 -> 1
    """
    try:
        from open_webui.models.users import Users

        user = Users.get_user_by_id(user_id)
        if not user:
            log.warning(f"用户不存在，无法统计交互: {user_id}")
            return

        # 获取或初始化 info 字段
        info = user.info or {}

        # 获取当前日期（ISO格式）
        today = date.today().isoformat()  # 格式: "2025-12-28"

        # 获取或初始化 daily_interaction 对象
        daily_interaction = info.get("daily_interaction", {})
        last_date = daily_interaction.get("date")
        current_count = daily_interaction.get("count", 0)

        # 获取或初始化 interaction_history 字典
        interaction_history = info.get("interaction_history", {})

        # 检测跨天，重置当日计数
        if last_date != today:
            log.info(f"用户 {user_id} 跨天检测: {last_date} -> {today}，重置当日计数")
            current_count = 0

        # 计算新的计数
        new_count = current_count + 1

        # 更新当日统计数据
        info["daily_interaction"] = {
            "count": new_count,
            "date": today,
            "last_interaction_at": int(time.time())
        }

        # 更新历史记录（直接覆盖今天的计数）
        interaction_history[today] = new_count

        # 清理超过保留期的历史数据
        interaction_history = _cleanup_old_history(interaction_history)
        info["interaction_history"] = interaction_history

        # 同时维护累计总交互次数
        total_count = info.get("total_interaction_count", 0)
        info["total_interaction_count"] = total_count + 1

        # 更新用户信息
        Users.update_user_by_id(user_id, {"info": info})

        log.info(
            f"用户 {user_id} 交互计数已更新: "
            f"当日 {current_count} -> {new_count}, "
            f"累计 {total_count} -> {total_count + 1}, "
            f"历史记录天数: {len(interaction_history)}"
        )

    except Exception as e:
        log.error(f"更新用户交互计数失败 (user_id={user_id}): {e}")


def get_daily_interaction_count(user_id: str) -> int:
    """
    获取用户的当日交互次数

    参数：
        user_id: 用户 ID

    返回：
        当日交互次数（跨天时返回 0）
    """
    try:
        from open_webui.models.users import Users

        user = Users.get_user_by_id(user_id)
        if not user:
            return 0

        info = user.info or {}
        daily_interaction = info.get("daily_interaction", {})

        # 检查日期是否为今天
        today = date.today().isoformat()
        last_date = daily_interaction.get("date")

        if last_date == today:
            return daily_interaction.get("count", 0)
        else:
            return 0

    except Exception as e:
        log.error(f"获取用户交互计数失败 (user_id={user_id}): {e}")
        return 0


def get_interaction_history(
    user_id: str,
    days: Optional[int] = None
) -> Dict[str, int]:
    """
    获取用户的交互历史记录

    参数：
        user_id: 用户 ID
        days: 返回最近N天的记录（None表示返回全部）

    返回：
        字典 {日期: 交互次数}，按日期降序排序
        例如: {"2025-12-28": 42, "2025-12-27": 35, ...}
    """
    try:
        from open_webui.models.users import Users

        user = Users.get_user_by_id(user_id)
        if not user:
            return {}

        info = user.info or {}
        interaction_history = info.get("interaction_history", {})

        # 如果指定了天数，只返回最近N天的记录
        if days is not None and days > 0:
            cutoff_date = (date.today() - timedelta(days=days)).isoformat()
            interaction_history = {
                d: count for d, count in interaction_history.items()
                if d >= cutoff_date
            }

        # 按日期降序排序
        sorted_history = dict(
            sorted(interaction_history.items(), key=lambda x: x[0], reverse=True)
        )

        return sorted_history

    except Exception as e:
        log.error(f"获取用户交互历史失败 (user_id={user_id}): {e}")
        return {}


def get_interaction_stats(user_id: str, days: int = 7) -> Dict:
    """
    获取用户的交互统计摘要

    参数：
        user_id: 用户 ID
        days: 统计最近N天（默认7天）

    返回：
        统计摘要字典，包含：
        - history: 每日交互次数
        - total: 期间总交互次数
        - average: 日均交互次数（只计算有交互的天数）
        - max_day: 交互最多的一天
        - max_count: 最大交互次数
        - active_days: 有交互的天数
    """
    try:
        history = get_interaction_history(user_id, days=days)

        if not history:
            return {
                "history": {},
                "total": 0,
                "average": 0.0,
                "max_day": None,
                "max_count": 0,
                "days_count": 0,
                "active_days": 0
            }

        total = sum(history.values())

        # 只计算交互次数大于0的天数
        active_days = sum(1 for count in history.values() if count > 0)
        average = total / active_days if active_days > 0 else 0.0

        max_day = max(history, key=history.get) if history else None
        max_count = history[max_day] if max_day else 0

        return {
            "history": history,
            "total": total,
            "average": round(average, 2),
            "max_day": max_day,
            "max_count": max_count,
            "days_count": len(history),
            "active_days": active_days
        }

    except Exception as e:
        log.error(f"获取用户交互统计失败 (user_id={user_id}): {e}")
        return {
            "history": {},
            "total": 0,
            "average": 0.0,
            "max_day": None,
            "max_count": 0,
            "days_count": 0,
            "active_days": 0
        }


def _cleanup_old_history(
    interaction_history: Dict[str, int],
    retention_days: int = INTERACTION_HISTORY_RETENTION_DAYS
) -> Dict[str, int]:
    """
    清理超过保留期的历史数据（内部函数）

    参数：
        interaction_history: 交互历史字典
        retention_days: 保留天数

    返回：
        清理后的历史字典
    """
    if not interaction_history or retention_days <= 0:
        return interaction_history

    cutoff_date = (date.today() - timedelta(days=retention_days)).isoformat()

    # 过滤掉过期的数据
    cleaned_history = {
        d: count for d, count in interaction_history.items()
        if d >= cutoff_date
    }

    removed_count = len(interaction_history) - len(cleaned_history)
    if removed_count > 0:
        log.debug(f"清理了 {removed_count} 天的过期交互记录")

    return cleaned_history


def reset_daily_interaction_counts() -> None:
    """
    重置所有用户的当日交互计数（每日定时任务，可选）

    注意：由于统计函数会自动检测跨天，此函数通常不是必需的。
    仅当需要在凌晨统一清空数据时使用。

    用法：
        在系统定时任务（如 cron）中每日凌晨调用
    """
    try:
        from open_webui.models.users import Users

        users_data = Users.get_users(skip=0, limit=100000)
        users = users_data.get("users", [])

        today = date.today().isoformat()
        reset_count = 0

        for user in users:
            info = user.info or {}
            daily_interaction = info.get("daily_interaction", {})

            # 只重置非今日的数据
            if daily_interaction.get("date") != today:
                info["daily_interaction"] = {
                    "count": 0,
                    "date": today,
                    "last_interaction_at": daily_interaction.get("last_interaction_at")
                }
                Users.update_user_by_id(user.id, {"info": info})
                reset_count += 1

        log.info(f"每日交互计数重置完成: 共重置 {reset_count} 个用户")

    except Exception as e:
        log.error(f"重置每日交互计数失败: {e}")
