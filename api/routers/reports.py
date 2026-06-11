"""报告查询路由

接口:
- GET /api/v1/reports                     报告列表
- GET /api/v1/reports/{id}                报告详情
- GET /api/v1/reports/trends              趋势数据
- GET /api/v1/reports/trend/pass-rate     通过率趋势（支持 day/week/month 粒度）
- GET /api/v1/reports/trend/response-time 响应时间分位数趋势
- GET /api/v1/reports/failure-categories  失败原因分类
- GET /api/v1/reports/unstable-endpoints  不稳定接口
- GET /api/v1/reports/top-failures        Top N 失败用例

所有接口已切换到数据库查询。
趋势和 Top N 失败使用 ReportService（已有实现）。
失败分类和不稳定接口使用 AnalyticsService。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db_session
from api.schemas.common import (
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)
from api.schemas.report import (
    FailureCategoryItem,
    FailureCategoryResponse,
    ReportListItem,
    ResponseTimeTrendItem,
    ResponseTimeTrendResponse,
    TopFailure,
    TopFailuresResponse,
    TrendItem,
    TrendResponse,
    UnstableEndpointItem,
    UnstableEndpointResponse,
)
from framework.persistence.models.execution import ExecutionModel
from framework.persistence.models.report import ReportModel
from framework.persistence.services.analytics_service import AnalyticsService
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


def _parse_suite_id(suite_id: str | None) -> uuid.UUID | None:
    """解析 suite_id 参数."""
    if not suite_id:
        return None
    try:
        return uuid.UUID(suite_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"suite_id 格式无效: {suite_id}",
        )


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
    current_user: CurrentUser = Depends(get_current_user),
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
        ExecutionModel.project_id,
    ]
    stmt = (
        select(*cols)
        .join(ExecutionModel, ReportModel.execution_id == ExecutionModel.id)
    )

    # 项目隔离：非 admin 用户只能看自己项目的报告
    if not current_user.is_admin():
        if current_user.project_ids:
            stmt = stmt.where(
                ExecutionModel.project_id.in_([uuid.UUID(pid) for pid in current_user.project_ids])
                | ExecutionModel.project_id.is_(None)
            )
        else:
            stmt = stmt.where(ExecutionModel.project_id.is_(None))

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
    current_user: CurrentUser = Depends(get_current_user),
):
    """查询指定时间范围内每日的通过率与平均响应时间趋势。

    返回每天的总用例数、通过数、失败数、通过率、平均耗时。
    支持按 suite_id 过滤，仅统计该套件下的执行结果。
    """
    suite_uuid = _parse_suite_id(suite_id)
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


# ── GET /reports/trend/pass-rate ──────────────────────────


@router.get(
    "/trend/pass-rate",
    response_model=SuccessResponse[TrendResponse],
    summary="通过率趋势（支持粒度）",
)
async def get_pass_rate_trend(
    days: int = Query(default=30, ge=1, le=365, description="统计天数"),
    granularity: str = Query(
        default="day",
        pattern="^(day|week|month)$",
        description="粒度: day/week/month",
    ),
    suite_id: Optional[str] = Query(
        default=None,
        description="按套件 ID 过滤（UUID 格式）",
    ),
    session: AsyncSession = Depends(get_db_session),
):
    """查询通过率趋势，支持 day/week/month 三种粒度。

    - day: 按天聚合
    - week: 按 ISO 周聚合
    - month: 按月聚合
    """
    suite_uuid = _parse_suite_id(suite_id)
    service = ReportService(session)
    rows = await service.get_pass_rate_trend_with_granularity(
        days=days, granularity=granularity, suite_id=suite_uuid
    )

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
    return SuccessResponse(data=TrendResponse(days=days, granularity=granularity, items=items))


# ── GET /reports/trend/response-time ──────────────────────


@router.get(
    "/trend/response-time",
    response_model=SuccessResponse[ResponseTimeTrendResponse],
    summary="响应时间分位数趋势",
)
async def get_response_time_trend(
    days: int = Query(default=30, ge=1, le=365, description="统计天数"),
    suite_id: Optional[str] = Query(
        default=None,
        description="按套件 ID 过滤（UUID 格式）",
    ),
    session: AsyncSession = Depends(get_db_session),
):
    """查询每日响应时间分位数 P50/P90/P95/P99 趋势。

    返回每天的分位数、平均值、最小值、最大值和样本数量。
    """
    suite_uuid = _parse_suite_id(suite_id)
    service = ReportService(session)
    rows = await service.get_response_time_percentiles_trend(
        days=days, suite_id=suite_uuid
    )

    items = [
        ResponseTimeTrendItem(
            date=r["date"],
            p50=r["p50"],
            p90=r["p90"],
            p95=r["p95"],
            p99=r["p99"],
            avg=r["avg"],
            min=r["min"],
            max=r["max"],
            total=r["total"],
        )
        for r in rows
    ]
    return SuccessResponse(data=ResponseTimeTrendResponse(days=days, items=items))


# ── GET /reports/failure-categories ───────────────────────


@router.get(
    "/failure-categories",
    response_model=SuccessResponse[FailureCategoryResponse],
    summary="失败原因分类",
)
async def get_failure_categories(
    days: int = Query(default=30, ge=1, le=365, description="统计天数"),
    suite_id: Optional[str] = Query(
        default=None,
        description="按套件 ID 过滤（UUID 格式）",
    ),
    session: AsyncSession = Depends(get_db_session),
):
    """对失败用例按原因进行分类统计。

    分类: assertion_failure / connection_timeout / connection_error / http_error / other
    """
    suite_uuid = _parse_suite_id(suite_id)
    service = AnalyticsService(session)
    rows = await service.get_failure_categories(days=days, suite_id=suite_uuid)

    items = [
        FailureCategoryItem(
            category=r["category"],
            count=r["count"],
            percentage=r["percentage"],
        )
        for r in rows
    ]
    return SuccessResponse(data=FailureCategoryResponse(days=days, items=items))


# ── GET /reports/unstable-endpoints ───────────────────────


@router.get(
    "/unstable-endpoints",
    response_model=SuccessResponse[UnstableEndpointResponse],
    summary="不稳定接口",
)
async def get_unstable_endpoints(
    days: int = Query(default=30, ge=1, le=365, description="统计天数"),
    threshold: float = Query(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="通过率阈值（低于此值视为不稳定）",
    ),
    suite_id: Optional[str] = Query(
        default=None,
        description="按套件 ID 过滤（UUID 格式）",
    ),
    session: AsyncSession = Depends(get_db_session),
):
    """查询通过率低于指定阈值的接口（不稳定接口）。

    仅统计至少执行 5 次的接口，避免样本过少导致误判。
    """
    suite_uuid = _parse_suite_id(suite_id)
    service = ReportService(session)
    rows = await service.get_unstable_endpoints(
        days=days, threshold=threshold, suite_id=suite_uuid
    )

    items = [
        UnstableEndpointItem(
            endpoint=r["case_name"],
            pass_rate=r["pass_rate"],
            total_runs=r["total"],
        )
        for r in rows
    ]
    return SuccessResponse(
        data=UnstableEndpointResponse(days=days, threshold=threshold, items=items)
    )


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
    current_user: CurrentUser = Depends(get_current_user),
):
    """查询失败次数最多的 Top N 用例。

    按失败次数降序排列，包含最近失败时间和错误信息。
    支持按 suite_id 过滤。
    """
    suite_uuid = _parse_suite_id(suite_id)
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
