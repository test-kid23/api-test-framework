"""执行触发与结果查询路由

接口:
- POST /api/v1/executions              触发执行（202 立即返回，后台 asyncio 执行）
- GET  /api/v1/executions              执行历史列表
- GET  /api/v1/executions/{id}         查询执行结果
- GET  /api/v1/executions/{id}/report  执行报告详情

T2-7 异步执行支持：
- POST 触发时使用 asyncio.create_task() 在后台执行用例
- 请求线程不被阻塞，立即返回 202 + execution_id
- 后台任务使用独立 AsyncSession，执行结果持久化到 execution_results 和 reports 表
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

from api.dependencies import create_independent_session, create_runner, get_db_session, parse_yaml_case
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


def _execution_to_response(exec_model: ExecutionModel) -> ExecutionResponse:
    """将 ExecutionModel 转换为 API 响应（不含 results/summary 详情）。"""
    return ExecutionResponse(
        id=str(exec_model.id),
        name=f"exec-{str(exec_model.id)[:12]}",
        status=ExecutionStatus(exec_model.status),
        trigger=ExecutionTrigger(exec_model.trigger) if exec_model.trigger in ["manual", "api", "scheduled", "webhook"] else ExecutionTrigger.API,
        env=exec_model.env or "dev",
        case_ids=[],  # 不在 execution 表存储，由 results 关联推导
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
):
    """提交用例执行任务。

    - 立即返回 202 + execution_id
    - 后台通过 asyncio.create_task() 异步执行，不阻塞请求线程
    - 执行结果持久化到 execution_results 表，报告存入 reports 表
    - 执行结果可通过 GET /executions/{id} 查询
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
    session.add(exec_model)
    await session.commit()

    # ── 后台异步执行（不阻塞请求线程）──
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
        case_ids=body.case_ids,
        suite_id=body.suite_id,
        results=[],
        created_at=exec_model.created_at,
        updated_at=exec_model.created_at,
    )
    return SuccessResponse(data=response)


async def _execute_cases_in_background(
    exec_id: str,
    case_ids: list[str],
    env_name: str,
) -> None:
    """后台异步执行用例序列

    在 asyncio 事件循环中依次执行多个用例，使用独立 AsyncSession 将结果持久化到数据库。
    """
    session: AsyncSession | None = None
    try:
        exec_uuid = uuid.UUID(exec_id)
        runner = create_runner(env_name)

        # 创建独立 session
        session = create_independent_session()
        exec_repo = ExecutionRepository(session)
        result_repo = ExecutionResultRepository(session)

        # 更新状态为 RUNNING
        exec_model = await exec_repo.get(exec_uuid)
        if exec_model is None:
            _log.error("execution_not_found_in_background", exec_id=exec_id)
            return
        exec_model.status = ExecutionStatus.RUNNING.value
        exec_model.started_at = datetime.now(timezone.utc)
        await exec_repo.update(exec_model)

        results: list[dict[str, Any]] = []

        # 解析并依次执行每个用例
        for cid in case_ids:
            try:
                case_uuid = uuid.UUID(cid)
            except ValueError:
                _log.warning("invalid_case_id_in_background", case_id=cid)
                results.append({
                    "case_id": cid,
                    "case_name": "unknown",
                    "status": "ERROR",
                    "error": f"用例 ID 格式无效: {cid}",
                    "elapsed_ms": 0,
                })
                continue

            # 查询 yaml_content
            case_result_row = await session.execute(
                select(TestCaseModel.yaml_content, TestCaseModel.name).where(
                    TestCaseModel.id == case_uuid
                )
            )
            case_row = case_result_row.first()
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
                # 保存空 YAML 错误到 DB
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

            # 解析 YAML
            try:
                test_case = parse_yaml_case(yaml_content)
            except Exception as e:
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

            # 执行用例
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

            # 持久化成功/失败结果
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
            }            )

            # 汇总
        summary = _compute_summary(results)
        final_status = _execution_status_from_summary(summary)

        # 更新执行记录
        now = datetime.now(timezone.utc)
        exec_model = await exec_repo.get(exec_uuid)
        if exec_model is not None:
            exec_model.status = final_status.value
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
            "background_execution_completed",
            exec_id=exec_id,
            status=final_status.value,
            total=summary["total"],
            passed=summary["passed"],
        )

    except Exception as e:
        _log.error("background_execution_failed", exec_id=exec_id, error=str(e), exc_info=True)
        if session is not None:
            try:
                await session.rollback()
                # 尝试更新执行状态为 error
                exec_uuid = uuid.UUID(exec_id)
                exec_model = await ExecutionRepository(session).get(exec_uuid)
                if exec_model is not None:
                    exec_model.status = ExecutionStatus.ERROR.value
                    exec_model.finished_at = datetime.now(timezone.utc)
                    await ExecutionRepository(session).update(exec_model)

                # 创建失败报告
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


def _make_error_case_result(case_name: str, error_msg: str) -> Any:
    """创建表示错误的伪 CaseResult 对象，用于 save_result 调用。"""
    from framework.models import CaseResult, CaseStatus

    return CaseResult(
        case_name=case_name,
        status=CaseStatus.ERROR,
        passed=False,
        error=error_msg,
        elapsed_ms=0.0,
    )


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
):
    """查询执行历史记录（分页，按创建时间倒序）。"""
    # 计数
    count_stmt = select(func.count(ExecutionModel.id))
    total = (await session.execute(count_stmt)).scalar_one()

    # 分页查询
    offset = (page - 1) * page_size
    stmt = (
        select(ExecutionModel)
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

    results = exec_model.results or []
    case_results = _result_models_to_case_results(list(results))
    summary = _compute_summary([
        {"status": r.status} for r in case_results
    ])

    response = ExecutionResponse(
        id=str(exec_model.id),
        name=f"exec-{str(exec_model.id)[:12]}",
        status=ExecutionStatus(exec_model.status),
        trigger=ExecutionTrigger(exec_model.trigger) if exec_model.trigger in ["manual", "api", "scheduled", "webhook"] else ExecutionTrigger.API,
        env=exec_model.env or "dev",
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


# ── GET /executions/{execution_id}/report ──────────────────


@router.get(
    "/{execution_id}/report",
    response_model=SuccessResponse[ExecutionReportResponse],
    summary="执行报告详情",
)
async def get_execution_report(
    execution_id: str,
    session: AsyncSession = Depends(get_db_session),
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
