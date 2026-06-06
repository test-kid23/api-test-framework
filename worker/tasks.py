"""Celery 任务定义

定义分布式执行任务，负责在 Worker 进程内:
1. 从数据库加载用例 YAML 内容
2. 解析并调用 TestRunner.arun_case() 执行
3. 将结果持久化到数据库
4. 返回执行摘要供 Celery result backend 存储
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import create_independent_session, create_runner, parse_yaml_case
from framework.models import CaseResult, CaseStatus
from framework.persistence.models.execution import ExecutionModel
from framework.persistence.models.report import ReportModel
from framework.persistence.models.test_case import TestCaseModel
from framework.persistence.repositories.execution_repo import (
    ExecutionRepository,
    ExecutionResultRepository,
)
from framework.utils.logger import Logger
from worker.celery_app import celery_app

_log = Logger.get("worker.tasks")


def _compute_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    """根据结果列表计算汇总统计。"""
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
    """根据汇总数据推断执行状态。"""
    if summary["total"] == 0:
        return "ERROR"
    if summary["error"] == summary["total"]:
        return "ERROR"
    if summary["passed"] == summary["total"]:
        return "PASSED"
    return "FAILED"


def _make_error_case_result(case_name: str, error_msg: str) -> CaseResult:
    """创建表示错误的伪 CaseResult 对象。"""
    return CaseResult(
        case_name=case_name,
        status=CaseStatus.ERROR,
        passed=False,
        error=error_msg,
        elapsed_ms=0.0,
    )


# ═══════════════════════════════════════════════════════════════
# Celery Task
# ═══════════════════════════════════════════════════════════════


@celery_app.task(
    bind=True,
    name="worker.tasks.run_execution",
    max_retries=0,
    acks_late=True,
)
def run_execution_task(
    self,
    exec_id: str,
    case_ids: list[str],
    env_name: str,
) -> dict[str, Any]:
    """Celery 分布式执行任务

    在 Worker 进程中执行测试用例序列。使用 asyncio.run() 在独立
    事件循环中运行异步执行逻辑，完成后通过 Celery result backend
    返回摘要。

    Args:
        exec_id: 执行记录 UUID 字符串。
        case_ids: 要执行的用例 ID 列表。
        env_name: 目标环境名称。

    Returns:
        执行摘要字典，包含 total/passed/failed/error/skipped 和 status。
    """
    _log.info(
        "celery_task_started",
        task_id=self.request.id,
        exec_id=exec_id,
        case_count=len(case_ids),
    )
    return asyncio.run(_execute_cases_async(exec_id, case_ids, env_name))


async def _execute_cases_async(
    exec_id: str,
    case_ids: list[str],
    env_name: str,
) -> dict[str, Any]:
    """核心异步执行逻辑（被 Celery 任务和本地模式共享）

    Args:
        exec_id: 执行记录 UUID 字符串。
        case_ids: 要执行的用例 ID 列表。
        env_name: 目标环境名称。

    Returns:
        执行摘要字典。
    """
    session: AsyncSession | None = None
    try:
        exec_uuid = uuid.UUID(exec_id)
        runner = create_runner(env_name)

        session = create_independent_session()
        exec_repo = ExecutionRepository(session)
        result_repo = ExecutionResultRepository(session)

        # 更新状态为 RUNNING
        exec_model = await exec_repo.get(exec_uuid)
        if exec_model is None:
            _log.error("execution_not_found_in_worker", exec_id=exec_id)
            return {"error": "execution_not_found", "total": 0}

        exec_model.status = "RUNNING"
        exec_model.started_at = datetime.now(timezone.utc)
        await exec_repo.update(exec_model)

        results: list[dict[str, Any]] = []

        for cid in case_ids:
            try:
                case_uuid = uuid.UUID(cid)
            except ValueError:
                _log.warning("invalid_case_id_in_worker", case_id=cid)
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
                await result_repo.save_result(
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
                test_case = parse_yaml_case(yaml_content)
            except yaml.YAMLError as e:
                await result_repo.save_result(
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
                case_result = await runner.arun_case(test_case, {})
            except Exception as e:
                await result_repo.save_result(
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

            await result_repo.save_result(
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
        exec_model = await exec_repo.get(exec_uuid)
        if exec_model is not None:
            exec_model.status = final_status
            exec_model.finished_at = now
            await exec_repo.update(exec_model)

        # 创建报告
        report = ReportModel(
            execution_id=exec_uuid,
            summary=json.dumps(summary, ensure_ascii=False),
            detail_data=json.dumps(results, ensure_ascii=False, default=str),
        )
        session.add(report)
        await session.commit()

        _log.info(
            "worker_execution_completed",
            exec_id=exec_id,
            status=final_status,
            total=summary["total"],
            passed=summary["passed"],
        )

        return {
            "exec_id": exec_id,
            "status": final_status,
            **summary,
        }

    except Exception as e:
        _log.error("worker_execution_failed", exec_id=exec_id, error=str(e), exc_info=True)
        if session is not None:
            try:
                await session.rollback()
                exec_uuid = uuid.UUID(exec_id)
                exec_model = await ExecutionRepository(session).get(exec_uuid)
                if exec_model is not None:
                    exec_model.status = "ERROR"
                    exec_model.finished_at = datetime.now(timezone.utc)
                    await ExecutionRepository(session).update(exec_model)

                report = ReportModel(
                    execution_id=exec_uuid,
                    summary=json.dumps({"total": 0, "passed": 0, "failed": 0, "error": 1, "skipped": 0}),
                    detail_data=json.dumps({"error": str(e)}),
                )
                session.add(report)
                await session.commit()
            except Exception as commit_err:
                _log.error("worker_cleanup_failed", exec_id=exec_id, error=str(commit_err))

        return {"error": str(e), "total": 0}

    finally:
        if session is not None:
            await session.close()
