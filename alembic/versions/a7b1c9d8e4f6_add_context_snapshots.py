"""add_context_snapshots

Revision ID: a7b1c9d8e4f6
Revises: 6a2c3d8e4f5a
Create Date: 2026-06-11 00:28:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b1c9d8e4f6'
down_revision: Union[str, Sequence[str], None] = '6a2c3d8e4f5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 context_snapshots 表 — 用于持久化执行失败时的上下文快照."""
    op.create_table(
        'context_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='自增主键'),
        sa.Column('execution_id', sa.UUID(), sa.ForeignKey('executions.id', ondelete='CASCADE'), nullable=False, comment='关联执行记录 ID'),
        sa.Column('step_index', sa.Integer(), nullable=False, server_default='0', comment='失败步骤索引'),
        sa.Column('run_vars', sa.JSON(), nullable=False, server_default='{}', comment='运行级变量快照（JSON）'),
        sa.Column('case_vars', sa.JSON(), nullable=False, server_default='{}', comment='用例级变量快照（JSON）'),
        sa.Column('step_vars', sa.JSON(), nullable=False, server_default='{}', comment='步骤级变量快照（JSON）'),
        sa.Column('error_message', sa.Text(), nullable=False, server_default='', comment='失败信息'),
        sa.Column('traceback', sa.Text(), nullable=True, comment='完整堆栈'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='创建时间'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_context_snapshots_execution_id', 'context_snapshots', ['execution_id'], unique=False)


def downgrade() -> None:
    """回滚 — 删除 context_snapshots 表."""
    op.drop_index('ix_context_snapshots_execution_id', table_name='context_snapshots')
    op.drop_table('context_snapshots')
