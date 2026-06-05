"""执行触发与结果查询路由（占位）

接口:
- POST /api/v1/executions              触发执行
- GET  /api/v1/executions              执行历史列表
- GET  /api/v1/executions/{id}         查询执行结果
- GET  /api/v1/executions/{id}/report  执行报告详情

当前 Phase 2 T2-1 阶段为占位实现：
- 触发执行仅创建记录并返回占位状态
- 实际调用 TestRunner 将在 T2-7（异步执行支持）完成后接入
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import InMemoryStore, get_store
from api.schemas.common import (
    MessageResponse,
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)
from api.schemas.execution import (
    ExecutionReportResponse,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatus,
)

router = APIRouter(prefix="/api/v1/executions", tags=["executions"])


@router.post(
    "",
    response_model=SuccessResponse[ExecutionResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="触发执行",
    responses={
        202: {"description": "执行已接收，排队中"},
        404: {"description": "指定的用例 ID 不存在"},
    },
)
async def trigger_execution(
    body: ExecutionRequest,
    store: InMemoryStore = Depends(get_store),
):
    """提交用例执行任务。当前为占位实现，仅创建记录并返回 PENDING 状态。

    正式版本（T2-7）将接入 TestRunner 异步执行。
    """
    # 验证所有 case_ids 存在
    missing_ids = [cid for cid in body.case_ids if store.get_case(cid) is None]
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用例不存在: {', '.join(missing_ids)}",
        )

    now = datetime.now(timezone.utc)
    exec_id = uuid.uuid4().hex[:12]

    record = {
        "id": exec_id,
        "name": f"exec-{exec_id}",
        "status": ExecutionStatus.PENDING.value,
        "trigger": body.trigger.value,
        "env": body.env,
        "case_ids": body.case_ids,
        "suite_id": body.suite_id,
        "results": [],
        "started_at": None,
        "finished_at": None,
        "summary": {},
        "created_at": now,
        "updated_at": now,
    }
    store.create_execution(record)

    response = ExecutionResponse(
        id=exec_id,
        name=record["name"],
        status=ExecutionStatus.PENDING,
        trigger=body.trigger,
        env=body.env,
        case_ids=body.case_ids,
        suite_id=body.suite_id,
        results=[],
        created_at=now,
        updated_at=now,
    )
    return SuccessResponse(data=response)


@router.get(
    "",
    response_model=SuccessResponse[PaginatedResponse[ExecutionResponse]],
    summary="执行历史列表",
)
async def list_executions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    store: InMemoryStore = Depends(get_store),
):
    """查询执行历史记录（分页，按创建时间倒序）。"""
    items, total = store.list_executions(page=page, page_size=page_size)
    exec_items = [
        ExecutionResponse(
            id=r["id"],
            name=r.get("name", ""),
            status=ExecutionStatus(r.get("status", "PENDING")),
            trigger=r.get("trigger", "api"),
            env=r.get("env", "dev"),
            case_ids=r.get("case_ids", []),
            suite_id=r.get("suite_id"),
            results=r.get("results", []),
            started_at=r.get("started_at"),
            finished_at=r.get("finished_at"),
            summary=r.get("summary", {}),
            created_at=r.get("created_at"),
            updated_at=r.get("updated_at"),
        )
        for r in items
    ]
    meta = PaginationMeta(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )
    return SuccessResponse(data=PaginatedResponse(items=exec_items, pagination=meta))


@router.get(
    "/{execution_id}",
    response_model=SuccessResponse[ExecutionResponse],
    summary="查询执行结果",
)
async def get_execution(
    execution_id: str,
    store: InMemoryStore = Depends(get_store),
):
    """根据 ID 获取单次执行的详细结果。"""
    record = store.get_execution(execution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    response = ExecutionResponse(
        id=record["id"],
        name=record.get("name", ""),
        status=ExecutionStatus(record.get("status", "PENDING")),
        trigger=record.get("trigger", "api"),
        env=record.get("env", "dev"),
        case_ids=record.get("case_ids", []),
        suite_id=record.get("suite_id"),
        results=record.get("results", []),
        started_at=record.get("started_at"),
        finished_at=record.get("finished_at"),
        summary=record.get("summary", {}),
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
    )
    return SuccessResponse(data=response)


@router.get(
    "/{execution_id}/report",
    response_model=SuccessResponse[ExecutionReportResponse],
    summary="执行报告详情",
)
async def get_execution_report(
    execution_id: str,
    store: InMemoryStore = Depends(get_store),
):
    """获取指定执行的详细报告，包含通过率、耗时统计等聚合信息。"""
    record = store.get_execution(execution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    results = record.get("results", [])
    passed = sum(1 for r in results if r.get("status") == "PASS")
    failed = sum(1 for r in results if r.get("status") == "FAIL")
    skipped = sum(1 for r in results if r.get("status") == "SKIP")
    error = sum(1 for r in results if r.get("status") == "ERROR")
    total = len(results)

    avg_elapsed = (
        sum(r.get("elapsed_ms", 0) for r in results) / total if total > 0 else 0.0
    )

    report = ExecutionReportResponse(
        execution_id=execution_id,
        status=ExecutionStatus(record.get("status", "PENDING")),
        total=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
        error=error,
        pass_rate=(passed / total * 100) if total > 0 else 0.0,
        avg_elapsed_ms=round(avg_elapsed, 2),
        results=results,
        created_at=record.get("created_at"),
        finished_at=record.get("finished_at"),
    )
    return SuccessResponse(data=report)
