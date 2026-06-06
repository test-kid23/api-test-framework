"""环境配置 Repository"""

from __future__ import annotations

from sqlalchemy import func, select

from framework.persistence.models.environment import EnvironmentModel
from framework.persistence.repositories.base import BaseRepository


class EnvironmentRepository(BaseRepository[EnvironmentModel]):
    """环境配置数据访问层。"""

    model_class = EnvironmentModel

    async def find_by_name(self, name: str) -> EnvironmentModel | None:
        """按名称查找环境（精确匹配）。

        Args:
            name: 环境名称。

        Returns:
            匹配的 EnvironmentModel，未找到返回 None。
        """
        stmt = select(self.model_class).where(self.model_class.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_name_ignore_case(self, name: str) -> EnvironmentModel | None:
        """按名称查找环境（忽略大小写）。

        作为 find_by_name 的容错补充，在精确匹配未命中时尝试。

        Args:
            name: 环境名称（忽略大小写比较）。

        Returns:
            匹配的 EnvironmentModel，未找到返回 None。
        """
        stmt = select(self.model_class).where(
            func.lower(self.model_class.name) == name.lower()
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def name_exists(self, name: str, exclude_id: str | None = None) -> bool:
        """检查环境名称是否已存在。

        Args:
            name: 待检查的名称。
            exclude_id: 排除的环境 ID（用于更新时不校验自身）。

        Returns:
            True 表示名称已存在。
        """
        stmt = select(func.count(self.model_class.id)).where(
            self.model_class.name == name
        )
        if exclude_id is not None:
            stmt = stmt.where(self.model_class.id != exclude_id)
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0
