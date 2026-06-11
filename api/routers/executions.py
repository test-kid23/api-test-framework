"""执行触发与结果查询路由

接口:
- POST /api/v1/executions              触发执行（202 立即返回，按模式分发）
- POST /api/v1/executions/{id}/cancel  取消执行（分布式模式）
- GET  /api/v1/executions              执行历史列表
- GET  /api/v1/executions/{id}         查询执行结果
- GET  /api/v1/executions/{id}/status  查询 Celery 任务实时状态（分布式模式）
- GET  /api/v1/executions/{id}/report  执行报告详情

执行模式分发:
- execution.mode=local：asyncio.create_task() 后台异步执行（默认）
- execution.mode=distributed：Celery + Redis 分布式执行
  - 支持多个 Worker 并行执行不同用例集
  - 任务入队后立即返回 task_id
  - 可从 Celery result backend 查询任务状态
  - 若 Celery/Redis 不可用，自动降级为本地模式
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser, check_project_access, get_current_user, require_role
from api.dependencies import create_independent_session, create_runner, get_db_session
from api.schemas.common import (
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)
from api.schemas.execution import (
    ExecutionCaseResult,
    ExecutionReportResponse,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatus,
    ExecutionTrigger,
)
from framework.config import ConfigLoader
from framework.models import CaseResult, CaseStatus
from framework.persistence.models.execution import ExecutionModel, ExecutionResultModel
from framework.persistence.models.report import ReportModel
from framework.persistence.models.test_case import TestCaseModel
from framework.persistence.repositories.execution_repo import ExecutionRepository, ExecutionResultRepository
from framework.utils.logger import Logger

router = APIRouter(prefix="/api/v1/executions", tags=["executions"])
_log = Logger.get("api.executions")

# 持有后台任务引用，防止 GC 提前回收
_background_tasks: set[asyncio.Task] = set()


# ── Helpers ───────────────────────────────────────────────


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


def _execution_status_from_summary(summary: dict[str, int]) -> ExecutionStatus:
    """根据汇总数据推断执行状态。"""
    if summary["total"] == 0:
        return ExecutionStatus.ERROR
    if summary["error"] == summary["total"]:
        return ExecutionStatus.ERROR
    if summary["passed"] == summary["total"]:
        return ExecutionStatus.PASSED
    return ExecutionStatus.FAILED


def _safe_parse_status(raw: str) -> ExecutionStatus:
    """安全解析执行状态枚举，对数据库中的不规范值做容错。

    Args:
        raw: 数据库中的原始状态字符串。

    Returns:
        对应的 ExecutionStatus 枚举值；无法匹配时返回 ERROR 并记录警告。
    """
    # 大小写不敏感匹配：兼容 DB 默认值 "pending" 与枚举 "PENDING" 的差异
    normalized = raw.upper() if raw else ""
    try:
        return ExecutionStatus(normalized)
    except ValueError:
        _log.warning(
            "unknown_execution_status",
            raw_value=raw,
            fallback="ERROR",
        )
        return ExecutionStatus.ERROR


def _safe_parse_trigger(raw: str) -> ExecutionTrigger:
    """安全解析触发方式枚举，对数据库中的不规范值做容错。

    Args:
        raw: 数据库中的原始 trigger 字符串。

    Returns:
        对应的 ExecutionTrigger 枚举值；无法匹配时返回 API 并记录警告。
    """
    # 大小写不敏感匹配：兼容 DB 默认值 "manual" 与枚举 "MANUAL" 的差异
    normalized = raw.lower() if raw else ""
    try:
        return ExecutionTrigger(normalized)
    except ValueError:
        _log.warning(
            "unknown_execution_trigger",
            raw_value=raw,
            fallback="api",
        )
        return ExecutionTrigger.API


def _execution_to_response(exec_model: ExecutionModel) -> ExecutionResponse:
    """将 ExecutionModel 转换为 API 响应（不含 results/summary 详情）。"""
    return ExecutionResponse(
        id=str(exec_model.id),
        name=f"exec-{str(exec_model.id)[:12]}",
        status=_safe_parse_status(exec_model.status),
        trigger=_safe_parse_trigger(exec_model.trigger),
        env=exec_model.env or "dev",
        mode="distributed" if exec_model.celery_task_id else "local",
        celery_task_id=exec_model.celery_task_id,
        case_ids=[],
        suite_id=str(exec_model.suite_id) if exec_model.suite_id else None,
        results=[],
        started_at=exec_model.started_at,
        finished_at=exec_model.finished_at,
        summary={},
        created_at=exec_model.created_at,
        updated_at=exec_model.finished_at or exec_model.created_at,
    )


def _result_models_to_case_results(results: list[ExecutionResultModel]) -> list[ExecutionCaseResult]:
    """将 ExecutionResultModel 列表转换为 ExecutionCaseResult 列表。"""
    return [
        ExecutionCaseResult(
            case_id=str(r.case_id) if r.case_id else "",
            case_name=r.case_name or "",
            status=r.status,
            error=r.error,
            elapsed_ms=r.elapsed_ms or 0.0,
        )
        for r in results
    ]


def _make_error_case_result(case_name: str, error_msg: str) -> Any:
    """创建表示错误的伪 CaseResult 对象，用于 save_result 调用。"""
    return CaseResult(
        case_name=case_name,
        status=CaseStatus.ERROR,
        passed=False,
        error=error_msg,
        elapsed_ms=0.0,
    )


def _get_execution_mode(env_name: str) -> str:
    """读取当前配置的执行模式。

    Args:
        env_name: 环境名称。

    Returns:
        执行模式字符串: "local" 或 "distributed"
    """
    try:
        loader = ConfigLoader()
        project_config, _ = loader.load(env_name)
        return project_config.execution.get("mode", "local")
    except Exception:
        _log.warning("failed_to_read_execution_mode", defaulting_to="local")
        return "local"


# ── POST /executions ──────────────────────────────────────


@router.post(
    "",
    response_model=SuccessResponse[ExecutionResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="触发执行",
    responses={
        202: {"description": "执行已接收，后台异步运行"},
        404: {"description": "指定的用例 ID 不存在"},
    },
)
async def trigger_execution(
    body: ExecutionRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """提交用例执行任务。

    根据 execution.mode 配置自动选择执行路径:

    - **local**（默认）: asyncio.create_task() 在 FastAPI 进程内后台执行。
      立即返回 202 + execution_id。

    - **distributed**: 通过 Celery 发送到 Worker 集群执行。
      任务入队后返回 202 + execution_id + celery_task_id。
      若 Celery/Redis 不可用，自动降级为本地模式。

    执行结果可通过 GET /executions/{id} 查询，
    分布式模式下还可通过 GET /executions/{id}/status 查询 Celery 任务实时状态。
    """
    # 验证所有 case_ids 存在
    for cid in body.case_ids:
        try:
            case_uuid = uuid.UUID(cid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用例 ID 格式无效: {cid}",
            )
        result = await session.execute(
            select(func.count(TestCaseModel.id)).where(TestCaseModel.id == case_uuid)
        )
        if result.scalar_one() == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用例不存在: {cid}",
            )

    # 解析 suite_id（可选）
    suite_uuid: uuid.UUID | None = None
    if body.suite_id:
        try:
            suite_uuid = uuid.UUID(body.suite_id)
        except ValueError:
            suite_uuid = None

    # 创建执行记录
    exec_id = uuid.uuid4()
    exec_model = ExecutionModel(
        id=exec_id,
        suite_id=suite_uuid,
        status=ExecutionStatus.PENDING.value,
        trigger=body.trigger.value,
        env=body.env,
    )
    if current_user.primary_project_id:
        exec_model.project_id = uuid.UUID(current_user.primary_project_id)
    session.add(exec_model)
    await session.commit()

    # ── 模式分发 ──
    mode = _get_execution_mode(body.env)
    celery_task_id: str | None = None
    actual_mode: str = mode

    if mode == "distributed":
        celery_task_id = await _dispatch_to_celery(
            exec_id=str(exec_id),
            case_ids=body.case_ids,
            env_name=body.env,
            session=session,
            exec_uuid=exec_id,
        )
        if celery_task_id is None:
            # Celery 不可用，降级为本地模式
            actual_mode = "local"
            _log.warning(
                "execution_fell_back_to_local",
                exec_id=str(exec_id),
                reason="celery_unavailable",
            )

    if actual_mode == "local":
        # ── 本地异步执行 ──
        bg_task = asyncio.create_task(
            _execute_cases_in_background(
                exec_id=str(exec_id),
                case_ids=body.case_ids,
                env_name=body.env,
            )
        )
        _background_tasks.add(bg_task)
        bg_task.add_done_callback(_background_tasks.discard)

    response = ExecutionResponse(
        id=str(exec_id),
        name=f"exec-{str(exec_id)[:12]}",
        status=ExecutionStatus.PENDING,
        trigger=body.trigger,
        env=body.env,
        mode=actual_mode,
        celery_task_id=celery_task_id,
        case_ids=body.case_ids,
        suite_id=body.suite_id,
        results=[],
        created_at=exec_model.created_at,
        updated_at=exec_model.created_at,
    )
    return SuccessResponse(data=response)


async def _dispatch_to_celery(
    exec_id: str,
    case_ids: list[str],
    env_name: str,
    session: AsyncSession,
    exec_uuid: uuid.UUID,
) -> str | None:
    """尝试将执行任务发送到 Celery 队列。

    Args:
        exec_id: 执行记录 UUID。
        case_ids: 用例 ID 列表。
        env_name: 环境名称。
        session: 数据库会话（用于更新 celery_task_id）。
        exec_uuid: 执行记录 UUID 对象。

    Returns:
        Celery 任务 ID。若 Celery 不可用返回 None，调用方应降级为本地模式。
    """
    try:
        from worker.tasks import run_execution_task

        task = run_execution_task.delay(
            exec_id=exec_id,
            case_ids=case_ids,
            env_name=env_name,
        )

        # 将 celery_task_id 持久化到执行记录
        exec_model = await session.get(ExecutionModel, exec_uuid)
        if exec_model is not None:
            exec_model.celery_task_id = task.id
            await session.commit()

        _log.info(
            "execution_dispatched_to_celery",
            exec_id=exec_id,
            celery_task_id=task.id,
            case_count=len(case_ids),
        )
        return task.id

    except Exception as e:
        _log.error("celery_dispatch_failed", exec_id=exec_id, error=str(e))
        return None


# ── 本地后台执行（委托给 ExecutionOrchestrator 统一编排） ──


async def _execute_cases_in_background(
    exec_id: str,
    case_ids: list[str],
    env_name: str,
) -> None:
    """后台异步执行用例序列（本地模式）

    委托给 ExecutionOrchestrator 统一编排，消除与 worker/tasks.py 的重复代码。
    """
    session: AsyncSession | None = None
    try:
        exec_uuid = uuid.UUID(exec_id)
        runner = create_runner(env_name)

        session = create_independent_session()
        exec_repo = ExecutionRepository(session)
        result_repo = ExecutionResultRepository(session)

        # 构建编排器上下文并委托执行
        from framework.execution_orchestrator import ExecutionContext, ExecutionOrchestrator

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
            "background_execution_completed",
            exec_id=exec_id,
            status=result.get("status"),
            total=result.get("total"),
            passed=result.get("passed"),
        )

    except Exception as e:
        _log.error("background_execution_failed", exec_id=exec_id, error=str(e), exc_info=True)
        if session is not None:
            try:
                await session.rollback()
                exec_uuid = uuid.UUID(exec_id)
                exec_model = await ExecutionRepository(session).get(exec_uuid)
                if exec_model is not None:
                    exec_model.status = ExecutionStatus.ERROR.value
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
                _log.error("background_cleanup_failed", exec_id=exec_id, error=str(commit_err))

    finally:
        if session is not None:
            await session.close()


# ── POST /executions/{execution_id}/cancel ─────────────────


@router.post(
    "/{execution_id}/cancel",
    response_model=SuccessResponse[dict],
    summary="取消执行（分布式模式）",
    responses={
        200: {"description": "取消请求已发送"},
        404: {"description": "执行记录不存在"},
        400: {"description": "仅分布式执行支持取消"},
    },
)
async def cancel_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """取消正在运行的分布式执行任务。

    仅对 execution.mode=distributed 且状态为 PENDING/RUNNING 的执行有效。
    本地模式执行无法取消（asyncio Task 取消需要额外机制）。
    """
    try:
        uid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    exec_repo = ExecutionRepository(session)
    exec_model = await exec_repo.get(uid)
    if exec_model is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    check_project_access(str(exec_model.project_id) if exec_model.project_id else None, current_user, "执行记录")

    if not exec_model.celery_task_id:
        raise HTTPException(
            status_code=400,
            detail="仅分布式执行支持取消操作",
        )

    if exec_model.status not in ("PENDING", "RUNNING"):
        raise HTTPException(
            status_code=400,
            detail=f"无法取消状态为 {exec_model.status} 的执行",
        )

    try:
        from worker.celery_app import celery_app

        celery_app.control.revoke(exec_model.celery_task_id, terminate=True)

        exec_model.status = ExecutionStatus.CANCELLED.value
        exec_model.finished_at = datetime.now(timezone.utc)
        await exec_repo.update(exec_model)

        _log.info(
            "execution_cancelled",
            exec_id=execution_id,
            celery_task_id=exec_model.celery_task_id,
        )
        return SuccessResponse(data={"message": "执行已取消", "execution_id": execution_id})

    except Exception as e:
        _log.error("cancel_execution_failed", exec_id=execution_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"取消失败: {str(e)}")


# ── GET /executions ───────────────────────────────────────


@router.get(
    "",
    response_model=SuccessResponse[PaginatedResponse[ExecutionResponse]],
    summary="执行历史列表",
)
async def list_executions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """查询执行历史记录（分页，按创建时间倒序）。"""
    stmt = select(ExecutionModel)

    # 项目隔离：非 admin 用户只能看自己项目的执行
    if not current_user.is_admin():
        if current_user.project_ids:
            stmt = stmt.where(
                ExecutionModel.project_id.in_([uuid.UUID(pid) for pid in current_user.project_ids])
                | ExecutionModel.project_id.is_(None)
            )
        else:
            stmt = stmt.where(ExecutionModel.project_id.is_(None))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    stmt = (
        stmt
        .order_by(ExecutionModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    exec_models = result.scalars().all()

    exec_items = [_execution_to_response(m) for m in exec_models]

    meta = PaginationMeta(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )
    return SuccessResponse(data=PaginatedResponse(items=exec_items, pagination=meta))


# ── GET /executions/{execution_id} ─────────────────────────


@router.get(
    "/{execution_id}",
    response_model=SuccessResponse[ExecutionResponse],
    summary="查询执行结果",
)
async def get_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """根据 ID 获取单次执行的详细结果。"""
    try:
        uid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    exec_repo = ExecutionRepository(session)
    exec_model = await exec_repo.get_with_results(uid)
    if exec_model is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    check_project_access(str(exec_model.project_id) if exec_model.project_id else None, current_user, "执行记录")

    results = exec_model.results or []
    case_results = _result_models_to_case_results(list(results))
    summary = _compute_summary([
        {"status": r.status} for r in case_results
    ])

    response = ExecutionResponse(
        id=str(exec_model.id),
        name=f"exec-{str(exec_model.id)[:12]}",
        status=_safe_parse_status(exec_model.status),
        trigger=_safe_parse_trigger(exec_model.trigger),
        env=exec_model.env or "dev",
        mode="distributed" if exec_model.celery_task_id else "local",
        celery_task_id=exec_model.celery_task_id,
        case_ids=[str(r.case_id) if r.case_id else "" for r in results],
        suite_id=str(exec_model.suite_id) if exec_model.suite_id else None,
        results=case_results,
        started_at=exec_model.started_at,
        finished_at=exec_model.finished_at,
        summary=summary,
        created_at=exec_model.created_at,
        updated_at=exec_model.finished_at or exec_model.created_at,
    )
    return SuccessResponse(data=response)


# ── GET /executions/{execution_id}/status ──────────────────


@router.get(
    "/{execution_id}/status",
    response_model=SuccessResponse[dict],
    summary="查询 Celery 任务实时状态",
)
async def get_execution_status(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """查询分布式执行的实时任务状态。

    对于本地模式执行，仅返回 DB 中的状态。
    对于分布式模式执行，同时查询 Celery result backend 获取 Worker 端实时状态。

    返回字段:
    - execution_id: 执行 ID
    - db_status: 数据库中的状态
    - celery_status: Celery 后端状态（分布式模式）
    - celery_task_id: Celery 任务 ID（分布式模式）
    - mode: 执行模式
    """
    try:
        uid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    exec_repo = ExecutionRepository(session)
    exec_model = await exec_repo.get(uid)
    if exec_model is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    check_project_access(str(exec_model.project_id) if exec_model.project_id else None, current_user, "执行记录")

    is_distributed = exec_model.celery_task_id is not None
    celery_status: str | None = None

    if is_distributed and exec_model.celery_task_id:
        try:
            from worker.celery_app import celery_app

            result = celery_app.AsyncResult(exec_model.celery_task_id)
            celery_status = result.state
        except Exception as e:
            _log.warning(
                "celery_status_query_failed",
                exec_id=execution_id,
                celery_task_id=exec_model.celery_task_id,
                error=str(e),
            )
            celery_status = "UNKNOWN"

    return SuccessResponse(data={
        "execution_id": execution_id,
        "db_status": exec_model.status,
        "celery_status": celery_status,
        "celery_task_id": exec_model.celery_task_id,
        "mode": "distributed" if is_distributed else "local",
        "started_at": exec_model.started_at.isoformat() if exec_model.started_at else None,
        "finished_at": exec_model.finished_at.isoformat() if exec_model.finished_at else None,
    })


# ── GET /executions/{execution_id}/report ──────────────────


@router.get(
    "/{execution_id}/report",
    response_model=SuccessResponse[ExecutionReportResponse],
    summary="执行报告详情",
)
async def get_execution_report(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取指定执行的详细报告，包含通过率、耗时统计等聚合信息。"""
    try:
        uid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    exec_repo = ExecutionRepository(session)
    exec_model = await exec_repo.get_with_results(uid)
    if exec_model is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    check_project_access(str(exec_model.project_id) if exec_model.project_id else None, current_user, "执行记录")

    results = exec_model.results or []
    case_results = _result_models_to_case_results(list(results))

    passed = sum(1 for r in case_results if r.status == "PASS")
    failed = sum(1 for r in case_results if r.status == "FAIL")
    skipped = sum(1 for r in case_results if r.status == "SKIP")
    error = sum(1 for r in case_results if r.status == "ERROR")
    total = len(case_results)

    avg_elapsed = (
        sum(r.elapsed_ms for r in case_results) / total if total > 0 else 0.0
    )

    report = ExecutionReportResponse(
        execution_id=str(exec_model.id),
        status=ExecutionStatus(exec_model.status),
        total=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
        error=error,
        pass_rate=(passed / total * 100) if total > 0 else 0.0,
        avg_elapsed_ms=round(avg_elapsed, 2),
        results=case_results,
        created_at=exec_model.created_at,
        finished_at=exec_model.finished_at,
    )
    return SuccessResponse(data=report)


# ── GET /executions/{execution_id}/snapshot ───────────────


@router.get(
    "/{execution_id}/snapshot",
    response_model=SuccessResponse[dict],
    summary="查询执行上下文快照",
    responses={
        200: {"description": "快照数据"},
        404: {"description": "快照不存在"},
    },
)
async def get_execution_snapshot(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取指定执行失败时的上下文快照（三层变量状态）。

    用于失败现场回溯和复现。
    """
    try:
        uid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    from framework.persistence.repositories.context_snapshot_repo import (
        ContextSnapshotRepository,
    )

    exec_repo = ExecutionRepository(session)
    exec_model = await exec_repo.get(uid)
    if exec_model is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    check_project_access(
        str(exec_model.project_id) if exec_model.project_id else None,
        current_user,
        "执行记录",
    )

    snapshot_repo = ContextSnapshotRepository(session)
    snapshot_model = await snapshot_repo.get_by_execution(uid)
    if snapshot_model is None:
        raise HTTPException(status_code=404, detail="快照不存在")

    return SuccessResponse(data={
        "execution_id": str(snapshot_model.execution_id),
        "step_index": snapshot_model.step_index,
        "run_vars": snapshot_model.run_vars,
        "case_vars": snapshot_model.case_vars,
        "step_vars": snapshot_model.step_vars,
        "error_message": snapshot_model.error_message,
        "traceback": snapshot_model.traceback,
        "created_at": snapshot_model.created_at.isoformat() if snapshot_model.created_at else None,
    })
