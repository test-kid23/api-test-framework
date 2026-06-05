"""报告 ORM 模型 — 对应 reports 表

字段说明（按开发计划 T2-2）：
- id: 主键
- execution_id: 关联的执行记录 ID
- summary: 报告摘要（JSON）
- detail_data: 详细数据（JSON）
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from framework.persistence.models.base import Base


class ReportModel(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键 UUID",
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="关联执行记录 ID",
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="报告摘要（JSON）",
    )
    detail_data: Mapped[str | None] = mapped_column(
        "detail_data",
        Text,
        nullable=True,
        comment="详细数据（JSON）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<ReportModel id={self.id} execution_id={self.execution_id}>"
