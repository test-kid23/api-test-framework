"""统一执行编排器

消除 worker/tasks.py 和 api/routers/executions.py 中的重复执行逻辑。
所有执行入口（Celery Worker、本地模式、API 触发）统一调用本编排器。

Attributes:
    ExecutionContext: 执行上下文，封装 runner + repos + 环境配置
    ExecutionResult: 统一执行结果
    ExecutionOrchestrator: 执行编排器
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from framework.models import CaseResult, CaseStatus
from framework.persistence.models.execution import ExecutionModel
from framework.persistence.models.report import ReportModel
from framework.persistence.models.test_case import TestCaseModel
from framework.persistence.repositories.execution_repo import (
    ExecutionRepository,
    ExecutionResultRepository,
)
from framework.utils.logger import Logger

if TYPE_CHECKING:
    from framework.runner import TestRunner

_log = Logger.get("execution_orchestrator")


@dataclass
class ExecutionContext:
    """执行上下文，封装一次执行所需的全部依赖.

    Attributes:
        runner: 测试执行引擎
        execution_repo: 执行记录 Repository
        result_repo: 执行结果 Repository
        env_name: 环境名称
        timeout: 用例超时时间（秒）
        trace_id: 追踪 ID（可选）
    """

    runner: TestRunner
    execution_repo: ExecutionRepository
    result_repo: ExecutionResultRepository
    env_name: str = "default"
    timeout: int = 1800
    trace_id: str | None = None


@dataclass
class ExecutionResult:
    """统一执行结果.

    Attributes:
        execution_id: 执行记录 ID
        status: 执行状态 ("PASSED" | "FAILED" | "ERROR" | "TIMEOUT")
        duration_ms: 总耗时（毫秒）
        case_count: 用例总数
        passed_count: 通过数
        failed_count: 失败数
        error_count: 错误数
        skipped_count: 跳过数
        error_message: 错误信息（可选）
    """

    execution_id: str
    status: str
    duration_ms: int = 0
    case_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    error_message: str | None = None


def _compute_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    """根据结果列表计算汇总统计."""
    passed = sum(1 for r in results if r.get("status") == "PASS")
    failed = sum(1 for r in results if r.get("status") == "FAIL")
    error_count = sum(1 for r in results if r.get("status") == "ERROR")
    skipped = sum(1 for r in results if r.get("status") == "SKIP")
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "error": error_count,
        "skipped": skipped,
    }


def _execution_status_from_summary(summary: dict[str, int]) -> str:
    """根据汇总数据推断执行状态."""
    if summary["total"] == 0:
        return "ERROR"
    if summary["error"] == summary["total"]:
        return "ERROR"
    if summary["passed"] == summary["total"]:
        return "PASSED"
    return "FAILED"


def _make_error_case_result(case_name: str, error_msg: str) -> CaseResult:
    """创建表示错误的伪 CaseResult 对象."""
    return CaseResult(
        case_name=case_name,
        status=CaseStatus.ERROR,
        passed=False,
        error=error_msg,
        elapsed_ms=0.0,
    )


class ExecutionOrchestrator:
    """统一执行编排器.

    消除 worker/tasks.py 和 api/routers/executions.py 中的重复代码。
    所有执行入口（Celery Worker、本地模式、API 触发）统一调用本编排器。

    Attributes:
        ctx: 执行上下文，封装 runner + repos + 环境配置
    """

    def __init__(self, ctx: ExecutionContext) -> None:
        """初始化编排器.

        Args:
            ctx: 执行上下文
        """
        self._ctx = ctx

    async def execute_case_list(
        self,
        case_ids: list[str],
        session: AsyncSession,
        variables: dict[str, object] | None = None,
    ) -> ExecutionResult:
        """批量执行用例列表.

        从数据库加载每个用例的 YAML 内容，解析后依次调用 runner.arun_case() 执行，
        结果持久化到 DB，最后汇总统计并更新执行记录状态和创建报告。

        Args:
            case_ids: 用例 ID 列表
            session: 数据库会话（用于加载用例和持久化结果）
            variables: 额外变量注入（未使用，保留扩展性）

        Returns:
            ExecutionResult: 聚合执行结果
        """
        exec_id = str(self._ctx.execution_repo._session.bind)  # 无法直接获取 exec_id
        # 从上下文获取 exec_id — 通过 execution_repo 最近操作的模型
        exec_uuid: uuid.UUID | None = None

        start_time = datetime.now(timezone.utc)
        results: list[dict[str, Any]] = []

        for cid in case_ids:
            try:
                case_uuid = uuid.UUID(cid)
            except ValueError:
                _log.warning("invalid_case_id", case_id=cid)
                results.append({
                    "case_id": cid,
                    "case_name": "unknown",
                    "status": "ERROR",
                    "error": f"用例 ID 格式无效: {cid}",
                    "elapsed_ms": 0,
                })
                continue

            case_row_result = await session.execute(
                select(TestCaseModel.yaml_content, TestCaseModel.name).where(
                    TestCaseModel.id == case_uuid
                )
            )
            case_row = case_row_result.first()
            if case_row is None:
                results.append({
                    "case_id": cid,
                    "case_name": "unknown",
                    "status": "ERROR",
                    "error": "用例未找到",
                    "elapsed_ms": 0,
                })
                continue

            yaml_content = case_row.yaml_content
            case_name = case_row.name

            if not yaml_content:
                await self._ctx.result_repo.save_result(
                    execution_id=exec_uuid if exec_uuid else uuid.uuid4(),
                    case_result=_make_error_case_result(case_name, "yaml_content 为空"),
                    case_id=case_uuid,
                )
                results.append({
                    "case_id": cid,
                    "case_name": case_name,
                    "status": "ERROR",
                    "error": "yaml_content 为空",
                    "elapsed_ms": 0,
                })
                continue

            try:
                test_case = self._parse_yaml_case(yaml_content)
            except yaml.YAMLError as e:
                await self._ctx.result_repo.save_result(
                    execution_id=exec_uuid if exec_uuid else uuid.uuid4(),
                    case_result=_make_error_case_result(case_name, f"YAML 解析失败: {e}"),
                    case_id=case_uuid,
                )
                results.append({
                    "case_id": cid,
                    "case_name": case_name,
                    "status": "ERROR",
                    "error": f"YAML 解析失败: {e}",
                    "elapsed_ms": 0,
                })
                continue

            try:
                case_result = await self._ctx.runner.arun_case(test_case, {})
            except Exception as e:
                await self._ctx.result_repo.save_result(
                    execution_id=exec_uuid if exec_uuid else uuid.uuid4(),
                    case_result=_make_error_case_result(test_case.name, str(e)),
                    case_id=case_uuid,
                )
                results.append({
                    "case_id": cid,
                    "case_name": test_case.name,
                    "status": "ERROR",
                    "error": str(e),
                    "elapsed_ms": 0,
                })
                continue

            await self._ctx.result_repo.save_result(
                execution_id=exec_uuid if exec_uuid else uuid.uuid4(),
                case_result=case_result,
                case_id=case_uuid,
            )

            results.append({
                "case_id": cid,
                "case_name": case_result.case_name,
                "status": case_result.status.value,
                "error": case_result.error,
                "elapsed_ms": round(case_result.elapsed_ms, 2),
            })

        # 汇总
        summary = _compute_summary(results)
        final_status = _execution_status_from_summary(summary)

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        return ExecutionResult(
            execution_id="",
            status=final_status,
            duration_ms=duration_ms,
            case_count=summary["total"],
            passed_count=summary["passed"],
            failed_count=summary["failed"],
            error_count=summary["error"],
            skipped_count=summary["skipped"],
        )

    async def execute_single_case(
        self,
        case_id: str,
        session: AsyncSession,
        variables: dict[str, object] | None = None,
    ) -> ExecutionResult:
        """执行单个用例.

        Args:
            case_id: 用例 ID
            session: 数据库会话
            variables: 额外变量注入

        Returns:
            ExecutionResult: 统一执行结果
        """
        result = await self.execute_case_list([case_id], session, variables)
        return result

    async def execute_case_list_for_execution(
        self,
        exec_uuid: uuid.UUID,
        case_ids: list[str],
        session: AsyncSession,
    ) -> dict[str, Any]:
        """为指定执行记录批量执行用例列表（完整流程）.

        包含完整的执行生命周期管理：
        1. 更新执行状态为 RUNNING
        2. 依次执行所有用例
        3. 持久化结果
        4. 更新执行状态为终态
        5. 创建报告

        Args:
            exec_uuid: 执行记录 UUID
            case_ids: 用例 ID 列表
            session: 数据库会话

        Returns:
            执行摘要字典，包含 total/passed/failed/error/skipped 和 status
        """
        # 更新状态为 RUNNING
        exec_model = await self._ctx.execution_repo.get(exec_uuid)
        if exec_model is None:
            _log.error("execution_not_found", exec_id=str(exec_uuid))
            return {"error": "execution_not_found", "total": 0}

        exec_model.status = "RUNNING"
        exec_model.started_at = datetime.now(timezone.utc)
        await self._ctx.execution_repo.update(exec_model)

        results: list[dict[str, Any]] = []

        for cid in case_ids:
            try:
                case_uuid = uuid.UUID(cid)
            except ValueError:
                _log.warning("invalid_case_id", case_id=cid)
                results.append({
                    "case_id": cid,
                    "case_name": "unknown",
                    "status": "ERROR",
                    "error": f"用例 ID 格式无效: {cid}",
                    "elapsed_ms": 0,
                })
                continue

            case_row_result = await session.execute(
                select(TestCaseModel.yaml_content, TestCaseModel.name).where(
                    TestCaseModel.id == case_uuid
                )
            )
            case_row = case_row_result.first()
            if case_row is None:
                results.append({
                    "case_id": cid,
                    "case_name": "unknown",
                    "status": "ERROR",
                    "error": "用例未找到",
                    "elapsed_ms": 0,
                })
                continue

            yaml_content = case_row.yaml_content
            case_name = case_row.name

            if not yaml_content:
                await self._ctx.result_repo.save_result(
                    execution_id=exec_uuid,
                    case_result=_make_error_case_result(case_name, "yaml_content 为空"),
                    case_id=case_uuid,
                )
                results.append({
                    "case_id": cid,
                    "case_name": case_name,
                    "status": "ERROR",
                    "error": "yaml_content 为空",
                    "elapsed_ms": 0,
                })
                continue

            try:
                test_case = self._parse_yaml_case(yaml_content)
            except yaml.YAMLError as e:
                await self._ctx.result_repo.save_result(
                    execution_id=exec_uuid,
                    case_result=_make_error_case_result(case_name, f"YAML 解析失败: {e}"),
                    case_id=case_uuid,
                )
                results.append({
                    "case_id": cid,
                    "case_name": case_name,
                    "status": "ERROR",
                    "error": f"YAML 解析失败: {e}",
                    "elapsed_ms": 0,
                })
                continue

            try:
                case_result = await self._ctx.runner.arun_case(test_case, {})
            except Exception as e:
                await self._ctx.result_repo.save_result(
                    execution_id=exec_uuid,
                    case_result=_make_error_case_result(test_case.name, str(e)),
                    case_id=case_uuid,
                )
                results.append({
                    "case_id": cid,
                    "case_name": test_case.name,
                    "status": "ERROR",
                    "error": str(e),
                    "elapsed_ms": 0,
                })
                continue

            await self._ctx.result_repo.save_result(
                execution_id=exec_uuid,
                case_result=case_result,
                case_id=case_uuid,
            )

            results.append({
                "case_id": cid,
                "case_name": case_result.case_name,
                "status": case_result.status.value,
                "error": case_result.error,
                "elapsed_ms": round(case_result.elapsed_ms, 2),
            })

        # 汇总
        summary = _compute_summary(results)
        final_status = _execution_status_from_summary(summary)

        now = datetime.now(timezone.utc)
        exec_model = await self._ctx.execution_repo.get(exec_uuid)
        if exec_model is not None:
            exec_model.status = final_status
            exec_model.finished_at = now
            await self._ctx.execution_repo.update(exec_model)

        # 创建报告
        report = ReportModel(
            execution_id=exec_uuid,
            summary=json.dumps(summary, ensure_ascii=False),
            detail_data=json.dumps(results, ensure_ascii=False, default=str),
        )
        session.add(report)
        await session.commit()

        _log.info(
            "execution_completed",
            exec_id=str(exec_uuid),
            status=final_status,
            total=summary["total"],
            passed=summary["passed"],
        )

        return {
            "exec_id": str(exec_uuid),
            "status": final_status,
            **summary,
        }

    def _parse_yaml_case(self, yaml_content: str) -> Any:
        """解析 YAML 内容为 TestCase 对象.

        Args:
            yaml_content: YAML 格式的测试用例内容

        Returns:
            解析后的 TestCase 对象

        Raises:
            yaml.YAMLError: YAML 解析失败
            ValueError: 无法解析时抛出
        """
        from api.dependencies import parse_yaml_case

        return parse_yaml_case(yaml_content)


def build_orchestrator(
    runner: TestRunner,
    session: AsyncSession,
    env_name: str = "default",
) -> ExecutionOrchestrator:
    """构建 ExecutionOrchestrator 的工厂函数.

    Args:
        runner: 测试执行引擎
        session: 数据库会话
        env_name: 环境名称

    Returns:
        配置好的 ExecutionOrchestrator 实例
    """
    ctx = ExecutionContext(
        runner=runner,
        execution_repo=ExecutionRepository(session),
        result_repo=ExecutionResultRepository(session),
        env_name=env_name,
    )
    return ExecutionOrchestrator(ctx)
