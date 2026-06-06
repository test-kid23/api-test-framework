"""调度任务 ORM 模型 — 对应 schedules 表

字段说明:
- id: 主键 UUID
- name: 调度名称
- suite_id: 关联的测试套件 ID
- env_name: 执行环境名称
- trigger_type: 触发类型 (cron/interval)
- cron_expression: Cron 表达式 (仅 trigger_type=cron)
- interval_seconds: 间隔秒数 (仅 trigger_type=interval)
- enabled: 是否启用
- last_run_at: 上次执行时间
- next_run_at: 下次执行时间
- created_at / updated_at: 时间戳
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from framework.persistence.models.base import Base


class ScheduleModel(Base):
    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键 UUID",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="调度名称",
    )
    suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_suites.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联测试套件 ID",
    )
    env_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="执行环境名称",
    )
    trigger_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="触发类型: cron/interval",
    )
    cron_expression: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Cron 表达式 (分 时 日 月 周)",
    )
    interval_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="间隔秒数 (仅 trigger_type=interval)",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用",
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="上次执行时间",
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="下次执行时间",
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
        return (
            f"<ScheduleModel id={self.id} name={self.name!r} "
            f"trigger={self.trigger_type!r} enabled={self.enabled}>"
        )
