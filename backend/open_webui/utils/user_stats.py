"""
用户统计工具模块

提供用户行为统计相关的辅助函数，统计数据存储在 user.info JSON 字段中。
"""

from logging import getLogger
from datetime import date
import time

log = getLogger(__name__)


def increment_daily_interaction_count(user_id: str) -> None:
    """
    增加用户的当日交互计数（存储在 user.info.daily_interaction 中）

    功能：
    - 检测日期变化，跨天时自动重置计数
    - 记录最后交互时间
    - 同时维护累计总交互次数

    参数：
        user_id: 用户 ID

    示例：
        >>> increment_daily_interaction_count("user-123")
        # user.info.daily_interaction.count: 0 -> 1
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

        # 检测跨天，重置计数
        if last_date != today:
            log.info(f"用户 {user_id} 跨天检测: {last_date} -> {today}，重置当日计数")
            current_count = 0

        # 更新统计数据
        info["daily_interaction"] = {
            "count": current_count + 1,
            "date": today,
            "last_interaction_at": int(time.time())
        }

        # 同时维护累计总交互次数（可选）
        total_count = info.get("total_interaction_count", 0)
        info["total_interaction_count"] = total_count + 1

        # 更新用户信息
        Users.update_user_by_id(user_id, {"info": info})

        log.info(
            f"用户 {user_id} 交互计数已更新: "
            f"当日 {current_count} -> {current_count + 1}, "
            f"累计 {total_count} -> {total_count + 1}"
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
