"""Merge soft_delete_cred and sign_in branch heads

Revision ID: merge_heads_001
Revises: soft_delete_cred_001, n7o8p9q0r1s2
Create Date: 2026-01-25

说明：合并两个分支的迁移头，解决 multiple heads 问题
- soft_delete_cred_001: 添加凭据软删除字段
- n7o8p9q0r1s2: 签到系统配置初始化（sign_in 分支的最后一个迁移）
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_heads_001'
down_revision = ('soft_delete_cred_001', 'n7o8p9q0r1s2')
branch_labels = None
depends_on = None


def upgrade():
    """合并迁移，无需执行任何操作"""
    pass


def downgrade():
    """回滚时无需操作"""
    pass
