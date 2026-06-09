"""高级分析报表路由

接口:
- GET /api/v1/analytics/stability-ranking    接口稳定性排行（按失败率降序）
- GET /api/v1/analytics/percentiles           响应时间分位数 P50/P95/P99
- GET /api/v1/analytics/failure-categories    失败原因分类统计
- GET /api/v1/analytics/roi                   ROI 统计（自动化覆盖率、节省工时等）
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db_session
from api.schemas.analytics import (
    FailureCategoryItem,
    FailureCategoryResponse,
    PercentileItem,
    PercentileResponse,
    RoiStatsItem,
    StabilityRankingItem,
    StabilityRankingResponse,
)
from api.schemas.common import SuccessResponse
from framework.persistence.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


# ── GET /analytics/stability-ranking ─────────────────────


@router.get(
    "/stability-ranking",
    response_model=SuccessResponse[StabilityRankingResponse],
    summary="接口稳定性排行",
)
async def get_stability_ranking(
    days: int = Query(default=30, ge=1, le=90, description="统计天数"),
    limit: int = Query(default=20, ge=1, le=100, description="返回条数"),
    suite_id: Optional[str] = Query(default=None, description="按套件 ID 过滤（UUID 格式）"),
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """查询接口稳定性排行，按失败率降序排列。

    统计每个接口（按 case_name 分组）在指定天数内的：
    - 总执行次数、通过/失败次数、失败率
    - 平均响应时间、最近执行时间

    按失败率从高到低排序，最不稳定的接口排在最前。
    """
    suite_uuid: uuid.UUID | None = None
    if suite_id:
        try:
            suite_uuid = uuid.UUID(suite_id)
        except ValueError:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"suite_id 格式无效: {suite_id}",
            )

    service = AnalyticsService(session)
    rows = await service.get_stability_ranking(days=days, limit=limit, suite_id=suite_uuid)

    items = [
        StabilityRankingItem(
            case_name=r["case_name"],
            case_id=r["case_id"],
            total=r["total"],
            passed=r["passed"],
            failed=r["failed"],
            failure_rate=r["failure_rate"],
            avg_elapsed_ms=r["avg_elapsed_ms"],
            last_executed_at=r["last_executed_at"],
        )
        for r in rows
    ]
    return SuccessResponse(data=StabilityRankingResponse(days=days, items=items))


# ── GET /analytics/percentiles ──────────────────────────


@router.get(
    "/percentiles",
    response_model=SuccessResponse[PercentileResponse],
    summary="响应时间分位数",
)
async def get_percentiles(
    days: int = Query(default=30, ge=1, le=90, description="统计天数"),
    suite_id: Optional[str] = Query(default=None, description="按套件 ID 过滤（UUID 格式）"),
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """查询响应时间分位数 P50 / P95 / P99。

    基于 execution_results 表中 elapsed_ms 字段，计算指定时间范围内
    所有执行结果的响应时间分布。同时返回平均值、最小值、最大值和样本数。
    """
    suite_uuid: uuid.UUID | None = None
    if suite_id:
        try:
            suite_uuid = uuid.UUID(suite_id)
        except ValueError:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"suite_id 格式无效: {suite_id}",
            )

    service = AnalyticsService(session)
    data = await service.get_response_time_percentiles(days=days, suite_id=suite_uuid)

    percentile_item = PercentileItem(
        p50=data["p50"],
        p95=data["p95"],
        p99=data["p99"],
        avg=data["avg"],
        min=data["min"],
        max=data["max"],
        total_samples=data["total_samples"],
    )
    return SuccessResponse(data=PercentileResponse(days=days, data=percentile_item))


# ── GET /analytics/failure-categories ───────────────────


@router.get(
    "/failure-categories",
    response_model=SuccessResponse[FailureCategoryResponse],
    summary="失败原因分类",
)
async def get_failure_categories(
    days: int = Query(default=30, ge=1, le=90, description="统计天数"),
    suite_id: Optional[str] = Query(default=None, description="按套件 ID 过滤（UUID 格式）"),
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """对失败用例按原因进行分类统计。

    分类规则（基于 error 字段关键词匹配）：
    - 断言失败：包含 "assert" / "expect" / "验证" / "断言"
    - 连接超时：包含 "timeout" / "超时"
    - 连接错误：包含 "connection" / "refused" / "unreachable" / "DNS"
    - HTTP 错误：包含 "4xx" / "5xx" / "status" / "HTTP"
    - 其他：无法匹配上述分类

    每类返回失败次数、占比和最多 3 个示例用例名。
    """
    suite_uuid: uuid.UUID | None = None
    if suite_id:
        try:
            suite_uuid = uuid.UUID(suite_id)
        except ValueError:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"suite_id 格式无效: {suite_id}",
            )

    service = AnalyticsService(session)
    rows = await service.get_failure_categories(days=days, suite_id=suite_uuid)

    items = [
        FailureCategoryItem(
            category=r["category"],
            label=r["label"],
            count=r["count"],
            percentage=r["percentage"],
            examples=r["examples"],
        )
        for r in rows
    ]
    return SuccessResponse(data=FailureCategoryResponse(days=days, items=items))


# ── GET /analytics/roi ──────────────────────────────────


@router.get(
    "/roi",
    response_model=SuccessResponse[RoiStatsItem],
    summary="ROI 统计",
)
async def get_roi(
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取自动化测试 ROI（投资回报率）统计。

    统计内容：
    - 自动化用例总数、覆盖接口数
    - 总执行次数、历史总通过率
    - 预估手动执行 vs 自动化执行耗时对比
    - 节省工时估算（手动按 3 分钟/次，自动化按 5 秒/次）
    - 最近 30 天执行趋势
    """
    service = AnalyticsService(session)
    data = await service.get_roi_stats()

    from api.schemas.analytics import Recent30dStats

    roi_item = RoiStatsItem(
        total_automated_cases=data["total_automated_cases"],
        covered_endpoints=data["covered_endpoints"],
        total_executions=data["total_executions"],
        total_test_runs=data["total_test_runs"],
        overall_pass_rate=data["overall_pass_rate"],
        estimated_manual_hours=data["estimated_manual_hours"],
        estimated_auto_hours=data["estimated_auto_hours"],
        estimated_hours_saved=data["estimated_hours_saved"],
        recent_30d=Recent30dStats(
            execution_count=data["recent_30d"]["execution_count"],
            test_run_count=data["recent_30d"]["test_run_count"],
            pass_rate=data["recent_30d"]["pass_rate"],
        ),
    )
    return SuccessResponse(data=roi_item)
