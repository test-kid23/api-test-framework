"""Mock 规则 Repository — 异步 CRUD + 批量操作

继承 BaseRepository 提供标准 CRUD，额外提供：
- list_by_project(): 按项目 ID 查询规则列表
- list_all_enabled(): 获取所有启用的规则（用于 mock 服务加载）
- delete_all_by_project(): 清空项目下所有规则
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from framework.persistence.models.mock_rule import MockRuleModel
from framework.persistence.repositories.base import BaseRepository


class MockRuleRepository(BaseRepository[MockRuleModel]):
    """Mock 规则 Repository。

    Usage:
        repo = MockRuleRepository(session)
        rule = await repo.create(MockRuleModel(url_pattern="/api/*", method="GET"))
    """

    model_class = MockRuleModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_by_project(
        self,
        project_id: uuid.UUID | None,
        *,
        offset: int = 0,
        limit: int = 100,
        url_pattern: str | None = None,
        method: str | None = None,
        enabled_only: bool = False,
    ) -> tuple[list[MockRuleModel], int]:
        """按项目 ID 查询规则列表（按优先级降序）。

        Args:
            project_id: 项目 ID（None 表示查询全局规则）。
            offset: 偏移量。
            limit: 每页条数。
            url_pattern: URL 模式模糊筛选。
            method: HTTP 方法筛选。
            enabled_only: 仅返回启用的规则。

        Returns:
            (规则列表, 总数) 元组。
        """
        stmt = select(self.model_class)

        if project_id is not None:
            stmt = stmt.where(self.model_class.project_id == project_id)
        else:
            stmt = stmt.where(self.model_class.project_id.is_(None))

        if url_pattern:
            stmt = stmt.where(self.model_class.url_pattern.contains(url_pattern))

        if method:
            stmt = stmt.where(
                (self.model_class.method == method.upper())
                | (self.model_class.method == "ANY")
            )

        if enabled_only:
            stmt = stmt.where(self.model_class.enabled.is_(True))

        stmt = stmt.order_by(
            self.model_class.priority.desc(),
            self.model_class.url_pattern.asc(),
        )

        # 总数查询
        from sqlalchemy import func as sql_func

        count_stmt = select(sql_func.count()).select_from(stmt.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def list_all_enabled(self) -> list[MockRuleModel]:
        """获取所有启用的规则（用于 mock 服务启动时加载到内存）。

        Returns:
            启用的规则列表，按优先级降序排列。
        """
        stmt = (
            select(self.model_class)
            .where(self.model_class.enabled.is_(True))
            .order_by(
                self.model_class.priority.desc(),
                self.model_class.url_pattern.asc(),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_all_by_project(self, project_id: uuid.UUID) -> int:
        """清空指定项目下的所有规则。

        Args:
            project_id: 项目 ID。

        Returns:
            删除的规则数量。
        """
        stmt = delete(self.model_class).where(
            self.model_class.project_id == project_id
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount
