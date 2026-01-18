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
    # 检测数据库类型
    bind = op.get_bind()
    dialect_name = bind.engine.dialect.name

    # 1. 删除旧的唯一索引（如果存在）
    # PostgreSQL 和 SQLite 的约束名称可能不同
    try:
        if dialect_name == 'postgresql':
            # PostgreSQL 可能使用不同的约束名称
            op.drop_constraint('uq_first_recharge_bonus_user_id', 'first_recharge_bonus_log', type_='unique')
        elif dialect_name == 'sqlite':
            # SQLite 使用 batch_alter_table
            with op.batch_alter_table('first_recharge_bonus_log') as batch_op:
                batch_op.drop_constraint('uq_first_recharge_bonus_user_id', type_='unique')
        else:
            # 其他数据库
            op.drop_constraint('uq_first_recharge_bonus_user_id', 'first_recharge_bonus_log', type_='unique')
    except Exception as e:
        print(f"Warning: Could not drop old constraint: {e}")
        # 约束可能不存在，继续执行

    # 2. 添加 tier_amount 字段
    op.add_column('first_recharge_bonus_log',
                  sa.Column('tier_amount', sa.Integer(), nullable=True))

    # 3. 将现有记录的 tier_amount 设置为 recharge_amount（保持兼容性）
    op.execute("""
        UPDATE first_recharge_bonus_log
        SET tier_amount = recharge_amount
        WHERE tier_amount IS NULL
    """)

    # 4. 将 tier_amount 设置为 NOT NULL
    if dialect_name == 'sqlite':
        # SQLite 需要使用 batch_alter_table
        with op.batch_alter_table('first_recharge_bonus_log') as batch_op:
            batch_op.alter_column('tier_amount', nullable=False)
    else:
        # PostgreSQL 和其他数据库
        op.alter_column('first_recharge_bonus_log', 'tier_amount',
                       existing_type=sa.Integer(),
                       nullable=False)

    # 5. 创建新的复合唯一索引
    op.create_index('idx_user_tier', 'first_recharge_bonus_log',
                    ['user_id', 'tier_amount'], unique=True)


def downgrade():
    """回滚数据库"""
    # 检测数据库类型
    bind = op.get_bind()
    dialect_name = bind.engine.dialect.name

    # 1. 删除复合唯一索引
    op.drop_index('idx_user_tier', table_name='first_recharge_bonus_log')

    # 2. 删除 tier_amount 字段
    op.drop_column('first_recharge_bonus_log', 'tier_amount')

    # 3. 恢复原来的 user_id 唯一索引
    if dialect_name == 'sqlite':
        with op.batch_alter_table('first_recharge_bonus_log') as batch_op:
            batch_op.create_unique_constraint('uq_first_recharge_bonus_user_id', ['user_id'])
    else:
        op.create_unique_constraint('uq_first_recharge_bonus_user_id',
                                   'first_recharge_bonus_log', ['user_id'])
