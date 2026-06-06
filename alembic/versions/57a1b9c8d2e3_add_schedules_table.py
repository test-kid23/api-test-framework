"""add schedules table

Revision ID: 57a1b9c8d2e3
Revises: 46c790b96d37
Create Date: 2026-06-06 16:56:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '57a1b9c8d2e3'
down_revision: Union[str, Sequence[str], None] = '46c790b96d37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create schedules table."""
    op.create_table(
        'schedules',
        sa.Column('id', sa.UUID(), nullable=False, comment='主键 UUID'),
        sa.Column('name', sa.String(length=100), nullable=False, comment='调度名称'),
        sa.Column(
            'suite_id',
            sa.UUID(),
            nullable=False,
            comment='关联测试套件 ID',
        ),
        sa.Column(
            'env_name',
            sa.String(length=50),
            nullable=False,
            comment='执行环境名称',
        ),
        sa.Column(
            'trigger_type',
            sa.String(length=20),
            nullable=False,
            comment='触发类型: cron/interval',
        ),
        sa.Column(
            'cron_expression',
            sa.String(length=100),
            nullable=True,
            comment='Cron 表达式 (分 时 日 月 周)',
        ),
        sa.Column(
            'interval_seconds',
            sa.Integer(),
            nullable=True,
            comment='间隔秒数 (仅 trigger_type=interval)',
        ),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('1'), comment='是否启用'),
        sa.Column(
            'last_run_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='上次执行时间',
        ),
        sa.Column(
            'next_run_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='下次执行时间',
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
        sa.ForeignKeyConstraint(
            ['suite_id'], ['test_suites.id'], ondelete='CASCADE'
        ),
    )


def downgrade() -> None:
    """Drop schedules table."""
    op.drop_table('schedules')
