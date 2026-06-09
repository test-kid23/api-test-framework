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

    async def get_successful_responses_by_case_id(
        self,
        case_id: uuid.UUID,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        """查询指定用例最近 N 次执行成功的响应体列表（用于智能断言）。

        Args:
            case_id: 用例 UUID。
            limit: 最多返回的响应数量。

        Returns:
            响应体 dict 列表（JSON 解析后的 body 部分）。
        """
        from sqlalchemy import desc

        stmt = (
            select(ExecutionResultModel)
            .where(
                ExecutionResultModel.case_id == case_id,
                ExecutionResultModel.passed == True,  # noqa: E712
                ExecutionResultModel.response.isnot(None),
            )
            .order_by(desc(ExecutionResultModel.created_at))
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        records = result.scalars().all()

        response_bodies: list[dict[str, object]] = []
        for record in records:
            if record.response is None:
                continue
            try:
                resp_data: dict[str, object] = json.loads(record.response)
                body = resp_data.get("body")
                if isinstance(body, dict):
                    response_bodies.append(body)
                elif isinstance(body, list):
                    # 将 list 类型 body 包装为 {"data": body}
                    response_bodies.append({"data": body})
            except (json.JSONDecodeError, TypeError):
                continue

        return response_bodies

    async def get_recent_responses_by_case_id(
        self,
        case_id: uuid.UUID,
        limit: int = 20,
    ) -> list[tuple[bool, dict[str, object] | None]]:
        """查询指定用例最近 N 次执行的响应（含成功和失败）。

        Args:
            case_id: 用例 UUID。
            limit: 最多返回的记录数。

        Returns:
            (passed, response_body_dict) 元组列表，response_body_dict 为 None 表示解析失败。
        """
        from sqlalchemy import desc

        stmt = (
            select(ExecutionResultModel)
            .where(
                ExecutionResultModel.case_id == case_id,
                ExecutionResultModel.response.isnot(None),
            )
            .order_by(desc(ExecutionResultModel.created_at))
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        records = result.scalars().all()

        results: list[tuple[bool, dict[str, object] | None]] = []
        for record in records:
            if record.response is None:
                continue
            try:
                resp_data: dict[str, object] = json.loads(record.response)
                body = resp_data.get("body")
                if isinstance(body, dict):
                    results.append((record.passed, body))
                elif isinstance(body, list):
                    results.append((record.passed, {"data": body}))
                else:
                    results.append((record.passed, None))
            except (json.JSONDecodeError, TypeError):
                results.append((record.passed, None))

        return results

    async def count_results_by_case_id(
        self,
        case_id: uuid.UUID,
        passed_only: bool = False,
    ) -> int:
        """统计指定用例的执行结果数量。

        Args:
            case_id: 用例 UUID。
            passed_only: 是否仅统计通过的结果。

        Returns:
            结果数量。
        """
        from sqlalchemy import func

        stmt = select(func.count()).select_from(ExecutionResultModel).where(
            ExecutionResultModel.case_id == case_id,
            ExecutionResultModel.response.isnot(None),
        )
        if passed_only:
            stmt = stmt.where(ExecutionResultModel.passed == True)  # noqa: E712

        result = await self._session.execute(stmt)
        return result.scalar_one()
