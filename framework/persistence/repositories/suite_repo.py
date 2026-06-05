"""套件 Repository"""

from __future__ import annotations

from sqlalchemy import select

from framework.persistence.models.test_suite import TestSuiteModel
from framework.persistence.repositories.base import BaseRepository


class SuiteRepository(BaseRepository[TestSuiteModel]):
    """测试套件数据访问层。"""

    model_class = TestSuiteModel

    async def find_by_name(self, name: str) -> TestSuiteModel | None:
        """按套件名称精确查找。

        Args:
            name: 套件名称。

        Returns:
            匹配的 TestSuiteModel 实例，未找到返回 None。
        """
        stmt = select(self.model_class).where(self.model_class.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
