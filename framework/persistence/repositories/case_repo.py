"""用例 Repository"""

from __future__ import annotations

from sqlalchemy import select

from framework.persistence.models.test_case import TestCaseModel
from framework.persistence.repositories.base import BaseRepository


class CaseRepository(BaseRepository[TestCaseModel]):
    """测试用例数据访问层。"""

    model_class = TestCaseModel

    async def find_by_name(self, name: str) -> TestCaseModel | None:
        """按用例名称精确查找。

        Args:
            name: 用例名称。

        Returns:
            匹配的 TestCaseModel 实例，未找到返回 None。
        """
        stmt = select(self.model_class).where(self.model_class.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_source_file(self, source_file: str) -> list[TestCaseModel]:
        """按来源文件查找所有用例。

        Args:
            source_file: YAML 文件路径。

        Returns:
            匹配的 TestCaseModel 列表。
        """
        stmt = select(self.model_class).where(self.model_class.source_file == source_file)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_suite_name(self, suite_name: str) -> list[TestCaseModel]:
        """按套件名称查找所有用例。

        Args:
            suite_name: 套件名称。

        Returns:
            匹配的 TestCaseModel 列表。
        """
        stmt = select(self.model_class).where(self.model_class.suite_name == suite_name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_source_files(self) -> list[str]:
        """列出所有不同的来源文件路径。

        Returns:
            去重后的 source_file 列表。
        """
        stmt = select(self.model_class.source_file).distinct().where(
            self.model_class.source_file.isnot(None)
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

    async def list_all_suite_names(self) -> list[str]:
        """列出所有不同的套件名称。

        Returns:
            去重后的 suite_name 列表。
        """
        stmt = select(self.model_class.suite_name).distinct().where(
            self.model_class.suite_name.isnot(None)
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]
