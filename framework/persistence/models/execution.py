"""执行记录 ORM 模型 — 对应 executions 和 execution_results 表

字段说明（按开发计划 T2-2）：
executions:
- id: 主键
- suite_id: 关联的套件 ID（可为空，支持单独执行用例）
- status: 执行状态（pending/running/passed/failed/error/timeout）
- trigger: 触发方式（manual/schedule/api）
- started_at / finished_at: 执行起止时间
- env: 执行环境名

execution_results:
- id: 主键
- execution_id: 关联的执行记录 ID
- case_id: 关联的用例 ID
- passed: 是否通过
- error: 错误信息
- request: 请求内容（JSON）
- response: 响应内容（JSON）
- elapsed_ms: 耗时（毫秒）
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from framework.persistence.models.base import Base


class ExecutionModel(Base):
    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键 UUID",
    )
    suite_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_suites.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联套件 ID",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="状态: pending/running/passed/failed/error/timeout",
    )
    trigger: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual",
        comment="触发方式: manual/schedule/api",
    )
    env: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="执行环境",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="开始时间",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="完成时间",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    # 关联
    results: Mapped[list["ExecutionResultModel"]] = relationship(
        "ExecutionResultModel",
        back_populates="execution",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ExecutionModel id={self.id} status={self.status!r}>"


class ExecutionResultModel(Base):
    __tablename__ = "execution_results"

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
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="关联用例 ID",
    )
    case_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="用例名称（冗余，便于查询）",
    )
    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否通过",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PASS",
        comment="详细状态: PASS/FAIL/SKIP/TIMEOUT/ERROR",
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息",
    )
    request: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="请求内容（JSON）",
    )
    response: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="响应内容（JSON）",
    )
    elapsed_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="耗时（毫秒）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    # 关联
    execution: Mapped["ExecutionModel"] = relationship(
        "ExecutionModel",
        back_populates="results",
    )

    def __repr__(self) -> str:
        return f"<ExecutionResultModel id={self.id} case={self.case_name!r} passed={self.passed}>"
