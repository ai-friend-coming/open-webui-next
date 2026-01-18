"""Add tier-based first recharge bonus support

Revision ID: tier_based_bonus_001
Revises: l6m7n8o9p0q1
Create Date: 2026-01-18

修改说明：
- 添加 tier_amount 字段（档位金额，单位：毫）
- 将 user_id 唯一索引改为 (user_id, tier_amount) 复合唯一索引
- 支持每个档位独立的首充资格
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'tier_based_bonus_001'
down_revision = 'l6m7n8o9p0q1'
branch_labels = None
depends_on = None


def upgrade():
    """升级数据库"""
    # 1. 删除旧的唯一索引
    with op.batch_alter_table('first_recharge_bonus_log') as batch_op:
        batch_op.drop_constraint('uq_first_recharge_bonus_log_user_id', type_='unique')

    # 2. 添加 tier_amount 字段（默认值为 recharge_amount，表示将现有记录视为该金额的档位）
    op.add_column('first_recharge_bonus_log',
                  sa.Column('tier_amount', sa.Integer(), nullable=True))

    # 3. 将现有记录的 tier_amount 设置为 recharge_amount（保持兼容性）
    op.execute("""
        UPDATE first_recharge_bonus_log
        SET tier_amount = recharge_amount
        WHERE tier_amount IS NULL
    """)

    # 4. 将 tier_amount 设置为 NOT NULL
    with op.batch_alter_table('first_recharge_bonus_log') as batch_op:
        batch_op.alter_column('tier_amount', nullable=False)

    # 5. 创建新的复合唯一索引
    with op.batch_alter_table('first_recharge_bonus_log') as batch_op:
        batch_op.create_index(
            'idx_user_tier',
            ['user_id', 'tier_amount'],
            unique=True
        )


def downgrade():
    """回滚数据库"""
    # 1. 删除复合唯一索引
    with op.batch_alter_table('first_recharge_bonus_log') as batch_op:
        batch_op.drop_index('idx_user_tier')

    # 2. 删除 tier_amount 字段
    op.drop_column('first_recharge_bonus_log', 'tier_amount')

    # 3. 恢复原来的 user_id 唯一索引
    with op.batch_alter_table('first_recharge_bonus_log') as batch_op:
        batch_op.create_unique_constraint('uq_first_recharge_bonus_log_user_id', ['user_id'])
