"""环境配置 ORM 模型 — 对应 environments 表

字段说明:
- id: 主键 UUID
- name: 环境名称（唯一键，与 schedule.env_name 联动）
- description: 环境描述
- base_url: 被测服务 HTTP 基础 URL
- ws_url: WebSocket 服务 URL
- variables: 环境级变量字典 (JSON)
- http_config: HTTP 客户端覆盖配置 (JSON)
- created_at / updated_at: 时间戳
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from framework.persistence.models.base import Base


class EnvironmentModel(Base):
    __tablename__ = "environments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键 UUID",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="环境名称（唯一）",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="环境描述",
    )
    base_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="被测服务 HTTP 基础 URL",
    )
    ws_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="WebSocket 服务 URL",
    )
    variables: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="环境级变量字典",
    )
    http_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="HTTP 客户端覆盖配置（timeout/verify_ssl 等）",
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
            f"<EnvironmentModel id={self.id} name={self.name!r}>"
        )
