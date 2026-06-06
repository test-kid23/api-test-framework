"""add environments table

Revision ID: 6a2c3d8e4f5a
Revises: 57a1b9c8d2e3
Create Date: 2026-06-06 17:22:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a2c3d8e4f5a'
down_revision: Union[str, Sequence[str], None] = '57a1b9c8d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create environments table."""
    op.create_table(
        'environments',
        sa.Column('id', sa.UUID(), nullable=False, comment='主键 UUID'),
        sa.Column(
            'name',
            sa.String(length=100),
            nullable=False,
            comment='环境名称（唯一）',
        ),
        sa.Column(
            'description',
            sa.Text(),
            nullable=True,
            comment='环境描述',
        ),
        sa.Column(
            'base_url',
            sa.String(length=500),
            nullable=True,
            comment='被测服务 HTTP 基础 URL',
        ),
        sa.Column(
            'ws_url',
            sa.String(length=500),
            nullable=True,
            comment='WebSocket 服务 URL',
        ),
        sa.Column(
            'variables',
            sa.JSON(),
            nullable=True,
            comment='环境级变量字典',
        ),
        sa.Column(
            'http_config',
            sa.JSON(),
            nullable=True,
            comment='HTTP 客户端覆盖配置（timeout/verify_ssl 等）',
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
            comment='创建时间',
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
            comment='更新时间',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_environments_name'),
    )
    op.create_index('ix_environments_name', 'environments', ['name'])


def downgrade() -> None:
    """Drop environments table."""
    op.drop_index('ix_environments_name', table_name='environments')
    op.drop_table('environments')
