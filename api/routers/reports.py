"""报告查询路由

接口:
- GET /api/v1/reports              报告列表
- GET /api/v1/reports/{id}         报告详情
- GET /api/v1/reports/trends       趋势数据
- GET /api/v1/reports/top-failures Top N 失败用例

当前 Phase 2 T2-1 阶段为占位实现。
完整的趋势分析、聚合统计将在 T2-4 完成后接入。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import InMemoryStore, get_store
from api.schemas.common import (
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)
from api.schemas.report import (
    ReportListItem,
    TopFailuresResponse,
    TrendItem,
    TrendResponse,
)

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
):
    """查询测试通过率趋势数据。

    当前为占位实现，返回空趋势。T2-4 完成后接入真实数据。
    """
    return SuccessResponse(data=TrendResponse(days=days, items=[]))


# ── GET /reports/top-failures ─────────────────────────────


@router.get(
    "/top-failures",
    response_model=SuccessResponse[TopFailuresResponse],
    summary="Top N 失败用例",
)
async def get_top_failures(
    limit: int = Query(default=10, ge=1, le=50, description="返回数量"),
):
    """查询失败次数最多的用例排行。

    当前为占位实现，返回空列表。T2-4 完成后接入真实数据。
    """
    return SuccessResponse(data=TopFailuresResponse(items=[]))
