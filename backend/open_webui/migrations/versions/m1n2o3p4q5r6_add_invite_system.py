"""Add invite system

Revision ID: m1n2o3p4q5r6
Revises: l6m7n8o9p0q1
Create Date: 2026-01-19 10:00:00.000000

添加推广邀请系统表和字段
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'm1n2o3p4q5r6'
down_revision: Union[str, None] = 'l6m7n8o9p0q1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库：添加邀请系统"""
    # 1. 在 user 表添加邀请相关字段
    op.add_column('user', sa.Column('invite_code', sa.String(8), nullable=True))
    op.add_column('user', sa.Column('invited_by', sa.String(), nullable=True))

    # 创建唯一约束和索引
    op.create_unique_constraint('uq_user_invite_code', 'user', ['invite_code'])
    op.create_index('ix_user_invite_code', 'user', ['invite_code'], unique=False)
    op.create_index('ix_user_invited_by', 'user', ['invited_by'], unique=False)

    # 2. 创建邀请返现日志表
    op.create_table(
        'invite_rebate_log',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('inviter_id', sa.String(), nullable=False),
        sa.Column('invitee_id', sa.String(), nullable=False),
        sa.Column('recharge_amount', sa.Integer(), nullable=False),
        sa.Column('rebate_amount', sa.Integer(), nullable=False),
        sa.Column('rebate_rate', sa.Integer(), nullable=False),
        sa.Column('inviter_balance_before', sa.Integer(), nullable=False),
        sa.Column('inviter_balance_after', sa.Integer(), nullable=False),
        sa.Column('recharge_log_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index('ix_invite_rebate_log_inviter_id', 'invite_rebate_log', ['inviter_id'], unique=False)
    op.create_index('ix_invite_rebate_log_invitee_id', 'invite_rebate_log', ['invitee_id'], unique=False)
    op.create_index('ix_invite_rebate_log_created_at', 'invite_rebate_log', ['created_at'], unique=False)

    # 3. 创建邀请统计表
    op.create_table(
        'invite_stats',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('total_invitees', sa.Integer(), default=0, nullable=False),
        sa.Column('total_rebate_amount', sa.Integer(), default=0, nullable=False),
        sa.Column('last_rebate_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('user_id')
    )

    # 创建索引
    op.create_index('ix_invite_stats_updated_at', 'invite_stats', ['updated_at'], unique=False)


def downgrade() -> None:
    """降级数据库：移除邀请系统"""
    # 删除邀请统计表
    op.drop_index('ix_invite_stats_updated_at', table_name='invite_stats')
    op.drop_table('invite_stats')

    # 删除邀请返现日志表
    op.drop_index('ix_invite_rebate_log_created_at', table_name='invite_rebate_log')
    op.drop_index('ix_invite_rebate_log_invitee_id', table_name='invite_rebate_log')
    op.drop_index('ix_invite_rebate_log_inviter_id', table_name='invite_rebate_log')
    op.drop_table('invite_rebate_log')

    # 删除 user 表的邀请字段
    op.drop_index('ix_user_invited_by', table_name='user')
    op.drop_index('ix_user_invite_code', table_name='user')
    op.drop_constraint('uq_user_invite_code', 'user', type_='unique')
    op.drop_column('user', 'invited_by')
    op.drop_column('user', 'invite_code')
