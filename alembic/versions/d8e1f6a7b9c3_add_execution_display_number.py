"""add_execution_display_number

Revision ID: d8e1f6a7b9c3
Revises: a7b1c9d8e4f6
Create Date: 2026-06-22 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8e1f6a7b9c3'
down_revision: Union[str, Sequence[str], None] = 'a7b1c9d8e4f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 executions 表添加 display_number 列并回填已有数据."""
    # 1. 添加列（SQLite 不支持后续 ALTER NOT NULL，直接用默认值）
    with op.batch_alter_table('executions') as batch_op:
        batch_op.add_column(
            sa.Column(
                'display_number',
                sa.Integer(),
                nullable=False,
                server_default='0',
                comment='人类可读的展示序号（自增，从 1 开始）',
            ),
        )

    # 2. 按创建时间升序回填序号
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id FROM executions ORDER BY created_at ASC")
    ).fetchall()
    for idx, (uid,) in enumerate(rows, start=1):
        conn.execute(
            sa.text("UPDATE executions SET display_number = :num WHERE id = :id"),
            {"num": idx, "id": uid},
        )

    # 3. 创建索引
    op.create_index('ix_executions_display_number', 'executions', ['display_number'])


def downgrade() -> None:
    """移除 display_number 列."""
    op.drop_index('ix_executions_display_number', table_name='executions')
    op.drop_column('executions', 'display_number')
