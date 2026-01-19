"""Add invite system

Revision ID: m1n2o3p4q5r6
Revises: add_sign_in_001
Create Date: 2026-01-19 10:00:00.000000

添加推广邀请系统表和字段
"""

from typing import Sequence, Union
import secrets

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'm1n2o3p4q5r6'
down_revision: Union[str, None] = 'add_sign_in_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def generate_invite_code(length: int = 6) -> str:
    """生成邀请码（排除易混淆字符）"""
    charset = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    return ''.join(secrets.choice(charset) for _ in range(length))


def upgrade() -> None:
    """升级数据库：添加邀请系统"""
    # 1. 在 user 表添加邀请相关字段
    op.add_column('user', sa.Column('invite_code', sa.String(8), nullable=True))
    op.add_column('user', sa.Column('invited_by', sa.String(), nullable=True))

    # 创建唯一约束和索引
    op.create_unique_constraint('uq_user_invite_code', 'user', ['invite_code'])
    op.create_index('ix_user_invite_code', 'user', ['invite_code'], unique=False)
    op.create_index('ix_user_invited_by', 'user', ['invited_by'], unique=False)

    # 2. 为所有现有用户生成邀请码
    conn = op.get_bind()

    # 获取所有没有邀请码的用户
    result = conn.execute(text("SELECT id FROM \"user\" WHERE invite_code IS NULL"))
    users = result.fetchall()

    print(f"Found {len(users)} existing users without invite codes")

    # 为每个用户生成唯一邀请码
    generated_codes = set()
    for user_row in users:
        user_id = user_row[0]

        # 生成唯一邀请码（避免冲突）
        max_retries = 10
        for attempt in range(max_retries):
            invite_code = generate_invite_code(6 if attempt < 5 else 8)

            # 检查是否已存在（包括本次生成的）
            existing = conn.execute(
                text("SELECT COUNT(*) FROM \"user\" WHERE invite_code = :code"),
                {"code": invite_code}
            ).scalar()

            if existing == 0 and invite_code not in generated_codes:
                generated_codes.add(invite_code)
                break
        else:
            # 10次都冲突，使用更长的码
            invite_code = generate_invite_code(8)

        # 更新用户
        conn.execute(
            text("UPDATE \"user\" SET invite_code = :code WHERE id = :user_id"),
            {"code": invite_code, "user_id": user_id}
        )

    # 注意: 不要手动调用 conn.commit()，Alembic 会自动管理事务

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
        sa.Column('total_invitees', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_rebate_amount', sa.Integer(), server_default='0', nullable=False),
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
