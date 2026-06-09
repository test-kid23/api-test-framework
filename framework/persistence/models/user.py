"""用户与项目 ORM 模型 — 多租户 RBAC 数据层

字段说明:
- UserModel: 平台用户，支持 admin/editor/viewer 三种角色
- ProjectModel: 项目/租户，资源隔离的基本单位
- UserProjectModel: 用户-项目多对多关联
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from framework.persistence.models.base import Base


class UserModel(Base):
    """平台用户。

    Attributes:
        id: 主键 UUID。
        username: 唯一用户名。
        password_hash: bcrypt 哈希密码。
        role: 角色（admin/editor/viewer）。
        is_active: 是否启用。
        created_at / updated_at: 时间戳。
        projects: 关联的项目列表（多对多）。
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键 UUID",
    )
    username: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=False,
        comment="用户名（唯一）",
    )
    password_hash: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="bcrypt 密码哈希",
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="viewer",
        comment="角色: admin/editor/viewer",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        comment="是否启用",
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

    # 关联
    projects: Mapped[list[UserProjectModel]] = relationship(
        "UserProjectModel",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    __test__ = False

    def __repr__(self) -> str:
        return f"<UserModel id={self.id} username={self.username!r} role={self.role}>"


class ProjectModel(Base):
    """项目/租户 — 资源隔离的基本单位。

    Attributes:
        id: 主键 UUID。
        name: 项目名称（唯一）。
        description: 项目描述。
        created_at / updated_at: 时间戳。
        users: 关联的用户列表（多对多）。
    """

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键 UUID",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="项目名称（唯一）",
    )
    description: Mapped[str | None] = mapped_column(
        comment="项目描述",
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

    users: Mapped[list[UserProjectModel]] = relationship(
        "UserProjectModel",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    __test__ = False

    def __repr__(self) -> str:
        return f"<ProjectModel id={self.id} name={self.name!r}>"


class UserProjectModel(Base):
    """用户-项目多对多关联表。

    Attributes:
        user_id: 用户外键。
        project_id: 项目外键。
        user / project: ORM relationship backref。
    """

    __tablename__ = "user_projects"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_user_project"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        comment="用户 ID",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
        comment="项目 ID",
    )

    user: Mapped[UserModel] = relationship("UserModel", back_populates="projects")
    project: Mapped[ProjectModel] = relationship("ProjectModel", back_populates="users")

    def __repr__(self) -> str:
        return f"<UserProject user={self.user_id} project={self.project_id}>"
