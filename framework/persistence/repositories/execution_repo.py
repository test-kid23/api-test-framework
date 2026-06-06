"""执行 Repository"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from framework.models import CaseResult
from framework.persistence.models.execution import ExecutionModel, ExecutionResultModel
from framework.persistence.repositories.base import BaseRepository


def _serialize_dataclass(obj: object) -> str | None:
    """将 dataclass 序列化为 JSON 字符串，失败返回 None。"""
    if obj is None:
        return None
    try:
        return json.dumps(asdict(obj), ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return None


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

    async def save_result(
        self,
        execution_id: uuid.UUID,
        case_result: CaseResult,
        case_id: uuid.UUID | None = None,
    ) -> ExecutionResultModel:
        """将 CaseResult 序列化后持久化到 execution_results 表。

        Args:
            execution_id: 关联的执行记录 ID。
            case_result: 用例执行结果（dataclass）。
            case_id: 关联的测试用例 ID（可选）。

        Returns:
            持久化后的 ExecutionResultModel 实例。
        """
        request_json = _serialize_dataclass(case_result.request) if case_result.request else None
        response_json = _serialize_dataclass(case_result.response) if case_result.response else None

        record = ExecutionResultModel(
            execution_id=execution_id,
            case_id=case_id,
            case_name=case_result.case_name,
            passed=case_result.passed,
            status=case_result.status.value,
            error=case_result.error,
            request=request_json,
            response=response_json,
            elapsed_ms=case_result.elapsed_ms,
        )
        self._session.add(record)
        await self._session.flush()
        return record
