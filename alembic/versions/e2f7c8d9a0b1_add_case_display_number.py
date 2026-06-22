"""add_case_display_number

Revision ID: e2f7c8d9a0b1
Revises: d8e1f6a7b9c3
Create Date: 2026-06-22 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f7c8d9a0b1'
down_revision: Union[str, Sequence[str], None] = 'd8e1f6a7b9c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 test_cases 表添加 display_number 列并回填已有数据."""
    # 1. 添加列（SQLite 兼容：直接 NOT NULL + server_default）
    with op.batch_alter_table('test_cases') as batch_op:
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
        sa.text("SELECT id FROM test_cases ORDER BY created_at ASC")
    ).fetchall()
    for idx, (uid,) in enumerate(rows, start=1):
        conn.execute(
            sa.text("UPDATE test_cases SET display_number = :num WHERE id = :id"),
            {"num": idx, "id": uid},
        )

    # 3. 创建索引
    op.create_index('ix_test_cases_display_number', 'test_cases', ['display_number'])


def downgrade() -> None:
    """移除 display_number 列."""
    op.drop_index('ix_test_cases_display_number', table_name='test_cases')
    with op.batch_alter_table('test_cases') as batch_op:
        batch_op.drop_column('display_number')
