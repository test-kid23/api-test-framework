"""执行 Repository"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from framework.persistence.models.execution import ExecutionModel, ExecutionResultModel
from framework.persistence.repositories.base import BaseRepository


class ExecutionRepository(BaseRepository[ExecutionModel]):
    """执行记录数据访问层。"""

    model_class = ExecutionModel

    async def get_with_results(self, id: object) -> ExecutionModel | None:
        """查询执行记录，同时预加载关联的执行结果。"""
        stmt = (
            select(ExecutionModel)
            .where(ExecutionModel.id == id)
            .options(selectinload(ExecutionModel.results))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class ExecutionResultRepository(BaseRepository[ExecutionResultModel]):
    """执行结果数据访问层。"""

    model_class = ExecutionResultModel

    async def list_by_execution(
        self,
        execution_id: object,
    ) -> Sequence[ExecutionResultModel]:
        """查询某个执行记录的所有结果。"""
        stmt = select(ExecutionResultModel).where(
            ExecutionResultModel.execution_id == execution_id
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
