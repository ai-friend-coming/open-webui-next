"""add payment_type column to payment_order

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-01-13 02:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j4k5l6m7n8o9'
down_revision: Union[str, None] = 'i3j4k5l6m7n8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加 payment_type 字段
    op.add_column('payment_order', sa.Column('payment_type', sa.String(20), server_default='qrcode', nullable=False))


def downgrade() -> None:
    # 删除 payment_type 字段
    op.drop_column('payment_order', 'payment_type')
