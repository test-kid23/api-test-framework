"""用户与项目 Repository — 用户认证和项目隔离的持久化层"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from framework.persistence.models.user import ProjectModel, UserModel, UserProjectModel
from framework.persistence.repositories.base import BaseRepository


class UserRepository(BaseRepository[UserModel]):
    """用户 Repository — 提供按用户名查询、账号管理等功能。"""

    model_class = UserModel

    async def find_by_username(self, username: str) -> UserModel | None:
        """按用户名查询用户。

        Args:
            username: 用户名（区分大小写）。

        Returns:
            UserModel 或 None。
        """
        stmt = (
            select(UserModel)
            .where(UserModel.username == username)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_username_with_projects(
        self, username: str
    ) -> UserModel | None:
        """按用户名查询用户，同时加载关联的项目。

        Args:
            username: 用户名。

        Returns:
            带 project 关联的 UserModel 或 None。
        """
        stmt = (
            select(UserModel)
            .where(UserModel.username == username)
            .options(selectinload(UserModel.projects).selectinload(UserProjectModel.project))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_project_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        """获取用户参与的所有项目 ID 列表。

        Args:
            user_id: 用户 UUID。

        Returns:
            项目 ID 列表。
        """
        stmt = select(UserProjectModel.project_id).where(
            UserProjectModel.user_id == user_id
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]


class ProjectRepository(BaseRepository[ProjectModel]):
    """项目 Repository — 提供项目 CRUD 和用户绑定。"""

    model_class = ProjectModel

    async def find_by_name(self, name: str) -> ProjectModel | None:
        """按名称查询项目。"""
        stmt = select(ProjectModel).where(ProjectModel.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_user(
        self, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> UserProjectModel:
        """将用户绑定到项目。

        Args:
            project_id: 项目 UUID。
            user_id: 用户 UUID。

        Returns:
            UserProjectModel 关联记录。
        """
        assoc = UserProjectModel(user_id=user_id, project_id=project_id)
        self._session.add(assoc)
        await self._session.flush()
        return assoc

    async def get_users(self, project_id: uuid.UUID) -> list[UserModel]:
        """获取项目下的所有用户。

        Args:
            project_id: 项目 UUID。

        Returns:
            用户列表。
        """
        stmt = (
            select(UserModel)
            .join(UserProjectModel)
            .where(UserProjectModel.project_id == project_id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
