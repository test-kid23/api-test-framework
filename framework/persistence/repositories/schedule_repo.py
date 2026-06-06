"""调度任务 Repository"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from framework.persistence.models.schedule import ScheduleModel
from framework.persistence.repositories.base import BaseRepository


class ScheduleRepository(BaseRepository[ScheduleModel]):
    """调度任务数据访问层。"""

    model_class = ScheduleModel

    async def find_enabled(self) -> Sequence[ScheduleModel]:
        """获取所有启用的调度任务。

        Returns:
            所有 enabled=True 的调度任务列表。
        """
        stmt = (
            select(self.model_class)
            .where(self.model_class.enabled == True)
            .order_by(self.model_class.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
