"""测试用例 ORM 模型 — 对应 test_cases 表

字段说明（按开发计划 T2-2）：
- id: 主键
- name: 用例名称
- yaml_content: 原始 YAML 内容
- tags: 标签列表（JSON 存储）
- priority: 优先级（P0/P1/P2/P3）
- created_at / updated_at: 时间戳
- version: 版本号（乐观锁 / 历史追踪）
- source_file: 来源 YAML 文件路径（用于 YAML ↔ DB 双向同步）
- suite_name: 所属套件名称（用于导出时重建套件结构）
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from framework.persistence.models.base import Base


class TestCaseModel(Base):
    __tablename__ = "test_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键 UUID",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="用例名称",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="用例描述",
    )
    yaml_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="原始 YAML 内容",
    )
    tags: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="标签列表（JSON 数组）",
    )
    priority: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="P1",
        comment="优先级: P0/P1/P2/P3",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        comment="状态: active/archived",
    )
    source_file: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="来源 YAML 文件路径（用于同步追踪）",
    )
    suite_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="所属套件名称（用于导出重建）",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="版本号",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    __test__ = False  # 防止 pytest 将此 ORM 模型误识别为测试类
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<TestCaseModel id={self.id} name={self.name!r} priority={self.priority}>"
