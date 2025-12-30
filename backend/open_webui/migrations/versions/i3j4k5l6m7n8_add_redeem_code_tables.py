"""Add redeem code tables

Revision ID: i3j4k5l6m7n8
Revises: 85f7b5b5ef68
Create Date: 2025-12-29 12:00:00.000000

添加兑换码模块相关表：
- 新增 redeem_code 表（兑换码主表）
- 新增 redeem_log 表（兑换日志表）
"""

from alembic import op
import sqlalchemy as sa

revision = "i3j4k5l6m7n8"
down_revision = "85f7b5b5ef68"
branch_labels = None
depends_on = None


def upgrade():
    """升级数据库：添加兑换码系统"""
    # 检查数据库类型
    connection = op.get_bind()
    is_postgresql = connection.dialect.name == "postgresql"

    # 1. 创建 redeem_code 表
    op.create_table(
        "redeem_code",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),  # 毫
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("current_uses", sa.Integer(), server_default="0", nullable=False),
        sa.Column("start_time", sa.BigInteger(), nullable=False),
        sa.Column("end_time", sa.BigInteger(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default="true" if is_postgresql else "1",
            nullable=False,
        ),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_redeem_code_code"),
    )

    # 创建 redeem_code 索引
    op.create_index(
        "idx_redeem_code_code", "redeem_code", ["code"], unique=False
    )

    # 2. 创建 redeem_log 表
    op.create_table(
        "redeem_log",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("code_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),  # 毫
        sa.Column("balance_before", sa.Integer(), nullable=False),  # 毫
        sa.Column("balance_after", sa.Integer(), nullable=False),  # 毫
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_id", "user_id", name="uq_code_user"),
    )

    # 创建 redeem_log 索引
    op.create_index(
        "idx_redeem_log_code_id", "redeem_log", ["code_id"], unique=False
    )
    op.create_index(
        "idx_redeem_log_user_id", "redeem_log", ["user_id"], unique=False
    )
    op.create_index(
        "idx_redeem_log_created_at", "redeem_log", ["created_at"], unique=False
    )


def downgrade():
    """降级数据库：移除兑换码系统"""
    # 删除 redeem_log 索引和表
    op.drop_index("idx_redeem_log_created_at", "redeem_log")
    op.drop_index("idx_redeem_log_user_id", "redeem_log")
    op.drop_index("idx_redeem_log_code_id", "redeem_log")
    op.drop_table("redeem_log")

    # 删除 redeem_code 索引和表
    op.drop_index("idx_redeem_code_code", "redeem_code")
    op.drop_table("redeem_code")
