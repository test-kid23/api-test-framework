"""Celery 任务定义

定义分布式执行任务，负责在 Worker 进程内:
1. 从数据库加载用例 YAML 内容
2. 解析并调用 TestRunner.arun_case() 执行
3. 将结果持久化到数据库
4. 返回执行摘要供 Celery result backend 存储

重构说明 (T5-01):
- 核心执行逻辑已迁移至 framework/execution_orchestrator.py
- 本模块仅负责 Celery 任务入口和异常处理包装
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import create_independent_session, create_runner
from framework.execution_orchestrator import (
    ExecutionContext,
    ExecutionOrchestrator,
)
from framework.persistence.models.execution import ExecutionModel
from framework.persistence.models.report import ReportModel
from framework.persistence.repositories.execution_repo import (
    ExecutionRepository,
    ExecutionResultRepository,
)
from framework.utils.logger import Logger
from worker.celery_app import celery_app

_log = Logger.get("worker.tasks")


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
    """核心异步执行逻辑 — 委托给 ExecutionOrchestrator 统一编排.

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

        # 构建编排器上下文并委托执行
        ctx = ExecutionContext(
            runner=runner,
            execution_repo=exec_repo,
            result_repo=result_repo,
            env_name=env_name,
        )
        orchestrator = ExecutionOrchestrator(ctx)
        result = await orchestrator.execute_case_list_for_execution(
            exec_uuid=exec_uuid,
            case_ids=case_ids,
            session=session,
        )

        _log.info(
            "worker_execution_completed",
            exec_id=exec_id,
            status=result.get("status"),
            total=result.get("total"),
            passed=result.get("passed"),
        )
        return result

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

                import json
                from framework.persistence.models.report import ReportModel

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
