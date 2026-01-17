"""add phone field and make email nullable for phone registration

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-01-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k5l6m7n8o9p0'
down_revision: Union[str, None] = 'j4k5l6m7n8o9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 使用 batch_alter_table 兼容 SQLite
    with op.batch_alter_table('user', schema=None) as batch_op:
        # 1. 添加 phone 字段
        batch_op.add_column(sa.Column('phone', sa.String(20), nullable=True))
        # 2. 将 email 字段改为可空（支持手机号注册）
        batch_op.alter_column('email', existing_type=sa.String(), nullable=True)

    # 创建索引加速查询（在 batch 外部创建）
    op.create_index('ix_user_phone', 'user', ['phone'], unique=False)

    with op.batch_alter_table('auth', schema=None) as batch_op:
        # 3. 添加 phone 字段
        batch_op.add_column(sa.Column('phone', sa.String(20), nullable=True))
        # 4. 将 email 字段改为可空
        batch_op.alter_column('email', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('auth', schema=None) as batch_op:
        # 1. 将 email 字段改回非空（注意：如果有 email 为空的记录会失败）
        batch_op.alter_column('email', existing_type=sa.String(), nullable=False)
        # 2. 删除 phone 字段
        batch_op.drop_column('phone')

    # 删除索引
    op.drop_index('ix_user_phone', table_name='user')

    with op.batch_alter_table('user', schema=None) as batch_op:
        # 3. 将 email 字段改回非空
        batch_op.alter_column('email', existing_type=sa.String(), nullable=False)
        # 4. 删除 phone 字段
        batch_op.drop_column('phone')
