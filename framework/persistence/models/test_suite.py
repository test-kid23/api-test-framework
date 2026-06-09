"""测试套件 ORM 模型 — 对应 test_suites 表

字段说明（按开发计划 T2-2）：
- id: 主键
- name: 套件名称
- description: 套件描述
- config: 套件配置（JSON）
- created_at: 创建时间
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from framework.persistence.models.base import Base


class TestSuiteModel(Base):
    __tablename__ = "test_suites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键 UUID",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="套件名称",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="套件描述",
    )
    config: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="套件配置（JSON）",
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="所属项目 ID（多租户隔离）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<TestSuiteModel id={self.id} name={self.name!r}>"
