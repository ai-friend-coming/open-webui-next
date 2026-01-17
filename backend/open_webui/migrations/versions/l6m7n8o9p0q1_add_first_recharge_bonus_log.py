"""Add first recharge bonus log table

Revision ID: l6m7n8o9p0q1
Revises: k5l6m7n8o9p0
Create Date: 2026-01-17 14:00:00.000000

添加首充优惠日志表
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'l6m7n8o9p0q1'
down_revision: Union[str, None] = 'k5l6m7n8o9p0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库：添加首充优惠日志表"""
    # 创建 first_recharge_bonus_log 表
    op.create_table(
        'first_recharge_bonus_log',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('recharge_amount', sa.Integer(), nullable=False),
        sa.Column('bonus_amount', sa.Integer(), nullable=False),
        sa.Column('bonus_rate', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_first_recharge_bonus_user_id')
    )

    # 创建索引
    op.create_index(
        'ix_first_recharge_bonus_log_user_id',
        'first_recharge_bonus_log',
        ['user_id'],
        unique=False
    )
    op.create_index(
        'ix_first_recharge_bonus_log_created_at',
        'first_recharge_bonus_log',
        ['created_at'],
        unique=False
    )


def downgrade() -> None:
    """降级数据库：移除首充优惠日志表"""
    # 删除索引
    op.drop_index('ix_first_recharge_bonus_log_created_at', table_name='first_recharge_bonus_log')
    op.drop_index('ix_first_recharge_bonus_log_user_id', table_name='first_recharge_bonus_log')

    # 删除表
    op.drop_table('first_recharge_bonus_log')
