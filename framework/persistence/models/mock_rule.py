"""Mock 规则 ORM 模型 — 对应 mock_rules 表

字段说明:
- id: 主键 UUID
- url_pattern: URL 匹配模式（支持通配符 *）
- method: HTTP 方法（GET/POST/PUT/DELETE/PATCH/ANY）
- status_code: 响应状态码，默认 200
- response_body: 响应体（JSON）
- response_headers: 响应头（JSON）
- description: 规则描述
- enabled: 是否启用
- priority: 优先级（数值越大越先匹配）
- delay_ms: 模拟延迟（毫秒）
- project_id: 所属项目 ID（多租户隔离）
- created_at / updated_at: 时间戳
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from framework.persistence.models.base import Base


class MockRuleModel(Base):
    __tablename__ = "mock_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键 UUID",
    )
    url_pattern: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="URL 匹配模式（支持通配符 *）",
    )
    method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="ANY",
        comment="HTTP 方法",
    )
    status_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=200,
        comment="响应状态码",
    )
    response_body: Mapped[dict | str | None] = mapped_column(
        JSON,
        nullable=True,
        comment="响应体（JSON 或字符串）",
    )
    response_headers: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="响应头",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="规则描述",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="优先级（数值越大越先匹配）",
    )
    delay_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="模拟延迟（毫秒）",
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
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
        return (
            f"<MockRuleModel id={self.id} url_pattern={self.url_pattern!r} "
            f"method={self.method!r}>"
        )
