"""报告查询路由

接口:
- GET /api/v1/reports              报告列表
- GET /api/v1/reports/{id}         报告详情
- GET /api/v1/reports/trends       趋势数据
- GET /api/v1/reports/top-failures Top N 失败用例

所有接口已切换到数据库查询。
趋势和 Top N 失败使用 ReportService（已有实现）。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session
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
from framework.persistence.models.execution import ExecutionModel
from framework.persistence.models.report import ReportModel
from framework.persistence.services.report_service import ReportService

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


# ── Helpers ───────────────────────────────────────────────


def _parse_summary(summary_json: str | None) -> dict:
    """从 ReportModel.summary JSON 字段提取统计信息。"""
    if not summary_json:
        return {}
    try:
        return json.loads(summary_json)
    except (json.JSONDecodeError, TypeError):
        return {}


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
    session: AsyncSession = Depends(get_db_session),
):
    """分页查询报告列表，可按环境过滤。

    通过 JOIN ReportModel 与 ExecutionModel 获取完整数据，
    统计字段从 ReportModel.summary JSON 反序列化。
    """
    # 构建查询
    cols = [
        ReportModel.id,
        ReportModel.execution_id,
        ReportModel.summary,
        ReportModel.created_at,
        ExecutionModel.status,
        ExecutionModel.env,
    ]
    stmt = (
        select(*cols)
        .join(ExecutionModel, ReportModel.execution_id == ExecutionModel.id)
    )

    if env:
        stmt = stmt.where(ExecutionModel.env == env)

    # 计数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    # 分页 + 排序
    offset = (page - 1) * page_size
    stmt = stmt.order_by(ReportModel.created_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(stmt)
    rows = result.all()

    report_items: list[ReportListItem] = []
    for row in rows:
        summary = _parse_summary(row.summary)
        report_items.append(
            ReportListItem(
                id=str(row.id),
                execution_id=str(row.execution_id),
                execution_name=f"exec-{str(row.execution_id)[:12]}",
                status=row.status or "PENDING",
                total_cases=summary.get("total", 0),
                passed=summary.get("passed", 0),
                failed=summary.get("failed", 0),
                pass_rate=(
                    (summary.get("passed", 0) / summary["total"] * 100)
                    if summary.get("total", 0) > 0
                    else 0.0
                ),
                env=row.env or "dev",
                created_at=row.created_at,
            )
        )

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
