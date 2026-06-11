"""add_mock_rules_table

Revision ID: b2d4e9f5c7a8
Revises: a7b1c9d8e4f6
Create Date: 2026-06-11 14:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b2d4e9f5c7a8'
down_revision: Union[str, Sequence[str], None] = 'a7b1c9d8e4f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 mock_rules 表 — 持久化 Mock 规则."""
    op.create_table(
        'mock_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='主键 UUID'),
        sa.Column('url_pattern', sa.String(500), nullable=False, comment='URL 匹配模式（支持通配符 *）'),
        sa.Column('method', sa.String(10), nullable=False, server_default='ANY', comment='HTTP 方法'),
        sa.Column('status_code', sa.Integer(), nullable=False, server_default='200', comment='响应状态码'),
        sa.Column('response_body', sa.JSON(), nullable=True, comment='响应体（JSON 或字符串）'),
        sa.Column('response_headers', sa.JSON(), nullable=True, server_default='{}', comment='响应头'),
        sa.Column('description', sa.Text(), nullable=False, server_default='', comment='规则描述'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true'), comment='是否启用'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0', comment='优先级（数值越大越先匹配）'),
        sa.Column('delay_ms', sa.Integer(), nullable=False, server_default='0', comment='模拟延迟（毫秒）'),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True, comment='所属项目 ID（多租户隔离）'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mock_rules_project_id', 'mock_rules', ['project_id'], unique=False)


def downgrade() -> None:
    """回滚 — 删除 mock_rules 表."""
    op.drop_index('ix_mock_rules_project_id', table_name='mock_rules')
    op.drop_table('mock_rules')
