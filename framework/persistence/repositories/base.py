"""Repository 基类 — 通用异步 CRUD + 列表查询（分页、过滤）"""

from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from framework.persistence.models.base import Base

TModel = TypeVar("TModel", bound=Base)


class BaseRepository(Generic[TModel]):
    """泛型异步 Repository 基类。

    提供标准 CRUD 操作：create / get / list / update / delete。
    子类只需指定 model_class 即可。

    用法:
        class CaseRepository(BaseRepository[TestCaseModel]):
            model_class = TestCaseModel
    """

    model_class: type[TModel]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── CRUD ──────────────────────────────────────────────

    async def create(self, instance: TModel) -> TModel:
        """持久化一个新建实例。"""
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def get(self, id: Any) -> TModel | None:
        """按主键查询。"""
        return await self._session.get(self.model_class, id)

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        order_by: Any = None,
        **filters: Any,
    ) -> tuple[Sequence[TModel], int]:
        """分页列表查询。

        Args:
            offset: 偏移量。
            limit: 每页条数。
            order_by: 排序列（如 TestCaseModel.created_at.desc()）。
            **filters: 列名 = 值的等值过滤。

        Returns:
            (结果列表, 总数) 元组。
        """
        stmt = select(self.model_class)

        for col_name, col_value in filters.items():
            col = getattr(self.model_class, col_name, None)
            if col is not None:
                stmt = stmt.where(col == col_value)

        # 总数查询
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        if order_by is not None:
            stmt = stmt.order_by(order_by)

        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        items = result.scalars().all()
        return items, total

    async def update(self, instance: TModel) -> TModel:
        """更新已存在的实例（需在 session 内已 tracked）。"""
        await self._session.flush()
        return instance

    async def delete(self, instance: TModel) -> None:
        """删除实例。"""
        await self._session.delete(instance)
        await self._session.flush()

    async def delete_by_id(self, id: Any) -> bool:
        """按主键删除，返回是否成功。"""
        instance = await self.get(id)
        if instance is None:
            return False
        await self.delete(instance)
        return True

    async def count(self, **filters: Any) -> int:
        """按过滤条件计数。"""
        stmt = select(func.count(self.model_class.id))
        for col_name, col_value in filters.items():
            col = getattr(self.model_class, col_name, None)
            if col is not None:
                stmt = stmt.where(col == col_value)
        result = await self._session.execute(stmt)
        return result.scalar_one()
