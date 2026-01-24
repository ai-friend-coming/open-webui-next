"""Add soft delete to user model credentials

Revision ID: soft_delete_cred_001
Revises: tier_based_bonus_001
Create Date: 2026-01-24

修改说明：
- 添加 deleted_at 字段（软删除时间戳，单位：秒）
- 支持软删除凭据，保留历史聊天记录中的凭据引用
- 防止旧聊天记录因凭据删除而无法打开
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'soft_delete_cred_001'
down_revision = 'tier_based_bonus_001'
branch_labels = None
depends_on = None


def upgrade():
    """升级数据库"""
    # 检测数据库类型
    bind = op.get_bind()
    dialect_name = bind.engine.dialect.name

    # 添加 deleted_at 字段（允许为空，默认为 NULL 表示未删除）
    if dialect_name == 'sqlite':
        # SQLite 使用 batch_alter_table
        with op.batch_alter_table('user_model_credential', schema=None) as batch_op:
            batch_op.add_column(sa.Column('deleted_at', sa.BigInteger(), nullable=True))
    else:
        # PostgreSQL 和其他数据库
        op.add_column('user_model_credential',
                      sa.Column('deleted_at', sa.BigInteger(), nullable=True))


def downgrade():
    """回滚数据库"""
    # 检测数据库类型
    bind = op.get_bind()
    dialect_name = bind.engine.dialect.name

    # 删除 deleted_at 字段
    if dialect_name == 'sqlite':
        with op.batch_alter_table('user_model_credential', schema=None) as batch_op:
            batch_op.drop_column('deleted_at')
    else:
        op.drop_column('user_model_credential', 'deleted_at')
