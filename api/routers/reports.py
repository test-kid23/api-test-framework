"""报告查询路由

接口:
- GET /api/v1/reports              报告列表
- GET /api/v1/reports/{id}         报告详情
- GET /api/v1/reports/trends       趋势数据
- GET /api/v1/reports/top-failures Top N 失败用例

报告列表仍使用 InMemoryStore（与执行记录联动），
趋势和 Top N 失败已接入真实数据库 ReportService。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import InMemoryStore, get_db_session, get_store
from api.schemas.common import (
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)
from api.schemas.report import (
    ReportListItem,
    TopFailure,
    TopFailuresResponse,
    TrendItem,
    TrendResponse,
)
from framework.persistence.services.report_service import ReportService

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


# ── GET /reports ──────────────────────────────────────────


@router.get(
    "",
    response_model=SuccessResponse[PaginatedResponse[ReportListItem]],
    summary="报告列表",
)
async def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    env: Optional[str] = Query(default=None, description="按环境过滤"),
    store: InMemoryStore = Depends(get_store),
):
    """分页查询报告列表，可按环境过滤。"""
    items, total = store.list_reports(page=page, page_size=page_size, env=env)
    report_items = [
        ReportListItem(
            id=r.get("id", ""),
            execution_id=r.get("execution_id", ""),
            execution_name=r.get("execution_name", ""),
            status=r.get("status", "PENDING"),
            total_cases=r.get("total_cases", 0),
            passed=r.get("passed", 0),
            failed=r.get("failed", 0),
            pass_rate=r.get("pass_rate", 0.0),
            env=r.get("env", "dev"),
            created_at=r.get("created_at"),
        )
        for r in items
    ]
    meta = PaginationMeta(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )
    return SuccessResponse(data=PaginatedResponse(items=report_items, pagination=meta))


# ── GET /reports/trends ───────────────────────────────────


@router.get(
    "/trends",
    response_model=SuccessResponse[TrendResponse],
    summary="测试通过率趋势",
)
async def get_trends(
    days: int = Query(default=7, ge=1, le=90, description="统计天数"),
    suite_id: Optional[str] = Query(
        default=None,
        description="按套件 ID 过滤（UUID 格式）",
    ),
    session: AsyncSession = Depends(get_db_session),
):
    """查询指定时间范围内每日的通过率与平均响应时间趋势。

    返回每天的总用例数、通过数、失败数、通过率、平均耗时。
    支持按 suite_id 过滤，仅统计该套件下的执行结果。
    """
    suite_uuid: uuid.UUID | None = None
    if suite_id:
        try:
            suite_uuid = uuid.UUID(suite_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"suite_id 格式无效: {suite_id}",
            )

    service = ReportService(session)
    rows = await service.get_pass_rate_trend(days=days, suite_id=suite_uuid)

    items = [
        TrendItem(
            date=r["date"],
            total=r["total"],
            passed=r["passed"],
            failed=r["failed"],
            pass_rate=r["pass_rate"],
            avg_elapsed_ms=r["avg_elapsed_ms"],
        )
        for r in rows
    ]
    return SuccessResponse(data=TrendResponse(days=days, items=items))


# ── GET /reports/top-failures ─────────────────────────────


@router.get(
    "/top-failures",
    response_model=SuccessResponse[TopFailuresResponse],
    summary="Top N 失败用例",
)
async def get_top_failures(
    limit: int = Query(default=10, ge=1, le=50, description="返回数量"),
    suite_id: Optional[str] = Query(
        default=None,
        description="按套件 ID 过滤（UUID 格式）",
    ),
    session: AsyncSession = Depends(get_db_session),
):
    """查询失败次数最多的 Top N 用例。

    按失败次数降序排列，包含最近失败时间和错误信息。
    支持按 suite_id 过滤。
    """
    suite_uuid: uuid.UUID | None = None
    if suite_id:
        try:
            suite_uuid = uuid.UUID(suite_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"suite_id 格式无效: {suite_id}",
            )

    service = ReportService(session)
    rows = await service.get_top_failures(limit=limit, suite_id=suite_uuid)

    items = [
        TopFailure(
            case_id=r["case_id"],
            case_name=r["case_name"],
            fail_count=r["fail_count"],
            last_failed_at=r["last_failed_at"],
            last_error=r["last_error"],
        )
        for r in rows
    ]
    return SuccessResponse(data=TopFailuresResponse(items=items))
