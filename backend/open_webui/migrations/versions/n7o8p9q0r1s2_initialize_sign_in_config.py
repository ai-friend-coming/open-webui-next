"""Initialize sign-in config

Revision ID: n7o8p9q0r1s2
Revises: m1n2o3p4q5r6
Create Date: 2026-01-20

修改说明：
- 初始化签到系统配置到 config 表
- 设置默认的正态分布参数（均值、标准差、最小值、最大值）
- 默认禁用签到功能，管理员可在后台启用
"""

from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'n7o8p9q0r1s2'
down_revision: Union[str, None] = 'm1n2o3p4q5r6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """初始化签到配置"""
    conn = op.get_bind()
    dialect_name = conn.engine.dialect.name

    # 签到系统默认配置
    default_sign_in_config = {
        "enabled": False,       # 默认禁用，管理员手动启用
        "mean": 1.0,           # 均值 1.0 元
        "std": 0.5,            # 标准差 0.5 元
        "min_amount": 0.1,     # 最小 0.1 元
        "max_amount": 5.0,     # 最大 5.0 元
    }

    # 获取当前配置
    result = conn.execute(text("SELECT id, data FROM config ORDER BY id DESC LIMIT 1"))
    row = result.fetchone()

    if row:
        # 配置表已有记录，更新现有配置
        config_id = row[0]

        # 根据数据库类型解析 JSON
        if dialect_name == 'postgresql':
            current_data = row[1]  # PostgreSQL JSONB 类型自动解析
        else:
            # SQLite 存储为文本，需要手动解析
            current_data = json.loads(row[1]) if isinstance(row[1], str) else row[1]

        # 确保路径存在
        if "ui" not in current_data:
            current_data["ui"] = {}

        # 只有当签到配置不存在时才初始化
        if "sign_in" not in current_data["ui"]:
            current_data["ui"]["sign_in"] = default_sign_in_config

            # 更新配置
            if dialect_name == 'postgresql':
                # PostgreSQL 使用 JSONB
                conn.execute(
                    text("UPDATE config SET data = :data::jsonb, updated_at = NOW() WHERE id = :id"),
                    {"data": json.dumps(current_data), "id": config_id}
                )
            else:
                # SQLite
                conn.execute(
                    text("UPDATE config SET data = :data, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                    {"data": json.dumps(current_data), "id": config_id}
                )

            print(f"✓ 已更新 config 记录 {config_id}，添加签到配置")
        else:
            print(f"✓ 签到配置已存在于 config 记录 {config_id}，跳过初始化")
    else:
        # 配置表为空，插入新记录
        new_config = {
            "version": 0,
            "ui": {
                "sign_in": default_sign_in_config
            }
        }

        if dialect_name == 'postgresql':
            conn.execute(
                text("INSERT INTO config (data, version, created_at) VALUES (:data::jsonb, 0, NOW())"),
                {"data": json.dumps(new_config)}
            )
        else:
            conn.execute(
                text("INSERT INTO config (data, version, created_at) VALUES (:data, 0, CURRENT_TIMESTAMP)"),
                {"data": json.dumps(new_config)}
            )

        print("✓ 已创建新的 config 记录并初始化签到配置")

    # 注意: Alembic 会自动管理事务，不需要手动 commit


def downgrade() -> None:
    """移除签到配置"""
    conn = op.get_bind()
    dialect_name = conn.engine.dialect.name

    # 获取当前配置
    result = conn.execute(text("SELECT id, data FROM config ORDER BY id DESC LIMIT 1"))
    row = result.fetchone()

    if row:
        config_id = row[0]

        # 根据数据库类型解析 JSON
        if dialect_name == 'postgresql':
            current_data = row[1]
        else:
            current_data = json.loads(row[1]) if isinstance(row[1], str) else row[1]

        # 移除签到配置
        if "ui" in current_data and "sign_in" in current_data["ui"]:
            del current_data["ui"]["sign_in"]

            # 更新配置
            if dialect_name == 'postgresql':
                conn.execute(
                    text("UPDATE config SET data = :data::jsonb, updated_at = NOW() WHERE id = :id"),
                    {"data": json.dumps(current_data), "id": config_id}
                )
            else:
                conn.execute(
                    text("UPDATE config SET data = :data, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                    {"data": json.dumps(current_data), "id": config_id}
                )

            print(f"✓ 已从 config 记录 {config_id} 中移除签到配置")
