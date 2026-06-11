"""上下文快照 Repository"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from framework.persistence.models.context_snapshot import ContextSnapshotModel
from framework.persistence.repositories.base import BaseRepository


class ContextSnapshotRepository(BaseRepository[ContextSnapshotModel]):
    """上下文快照数据访问层."""

    model_class = ContextSnapshotModel

    async def get_by_execution(self, execution_id: uuid.UUID) -> ContextSnapshotModel | None:
        """按执行 ID 查询最新快照.

        Args:
            execution_id: 执行记录 ID

        Returns:
            快照模型或 None
        """
        stmt = (
            select(ContextSnapshotModel)
            .where(ContextSnapshotModel.execution_id == execution_id)
            .order_by(ContextSnapshotModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_execution(self, execution_id: uuid.UUID) -> list[ContextSnapshotModel]:
        """查询指定执行的所有快照.

        Args:
            execution_id: 执行记录 ID

        Returns:
            快照模型列表
        """
        stmt = (
            select(ContextSnapshotModel)
            .where(ContextSnapshotModel.execution_id == execution_id)
            .order_by(ContextSnapshotModel.step_index.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
