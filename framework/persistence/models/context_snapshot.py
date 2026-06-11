"""上下文快照 ORM 模型 — 对应 context_snapshots 表

用于持久化执行失败时的三层变量状态快照（run/case/step），
支持失败现场回溯和复现。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from framework.persistence.models.base import Base


class ContextSnapshotModel(Base):
    __tablename__ = "context_snapshots"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="自增主键",
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联执行记录 ID",
    )
    step_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="失败步骤索引",
    )
    run_vars: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="运行级变量快照（JSON）",
    )
    case_vars: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="用例级变量快照（JSON）",
    )
    step_vars: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="步骤级变量快照（JSON）",
    )
    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="失败信息",
    )
    traceback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="完整堆栈",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return (
            f"<ContextSnapshotModel id={self.id} "
            f"execution_id={self.execution_id} "
            f"step_index={self.step_index}>"
        )
