"""Add sign-in system

Revision ID: add_sign_in_001
Revises: tier_based_bonus_001
Create Date: 2026-01-18

添加签到系统：
- 创建 sign_in_log 表
- 支持每日签到奖励
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_sign_in_001'
down_revision = 'tier_based_bonus_001'
branch_labels = None
depends_on = None


def upgrade():
    """创建签到表"""
    op.create_table(
        'sign_in_log',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('sign_in_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'sign_in_date', name='uq_user_sign_in_date')
    )

    # 创建索引
    op.create_index('ix_sign_in_log_user_id', 'sign_in_log', ['user_id'])
    op.create_index('ix_sign_in_log_created_at', 'sign_in_log', ['created_at'])


def downgrade():
    """删除签到表"""
    op.drop_index('ix_sign_in_log_created_at', table_name='sign_in_log')
    op.drop_index('ix_sign_in_log_user_id', table_name='sign_in_log')
    op.drop_table('sign_in_log')
