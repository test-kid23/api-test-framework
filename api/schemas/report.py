"""报告请求/响应 Schema"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from api.schemas.common import TimestampMixin


# ==================== 响应体 ====================


class ReportListItem(BaseModel):
    """报告列表项"""

    id: str = Field(..., description="报告 ID")
    execution_id: str = Field(..., description="关联执行 ID")
    execution_name: str = Field(default="", description="执行名称")
    status: str = Field(default="PENDING", description="执行状态")
    total_cases: int = Field(default=0, description="用例总数")
    passed: int = Field(default=0, description="通过数")
    failed: int = Field(default=0, description="失败数")
    pass_rate: float = Field(default=0.0, description="通过率")
    env: str = Field(default="dev", description="目标环境")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")


class TrendItem(BaseModel):
    """趋势数据点"""

    date: str = Field(..., description="日期 (YYYY-MM-DD)")
    total: int = Field(default=0, description="执行总数")
    passed: int = Field(default=0, description="通过数")
    failed: int = Field(default=0, description="失败数")
    pass_rate: float = Field(default=0.0, description="通过率")
    avg_elapsed_ms: float = Field(default=0.0, description="平均耗时")


class TrendResponse(BaseModel):
    """趋势响应"""

    days: int = Field(..., description="统计天数")
    granularity: str = Field(default="day", description="粒度: day/week/month")
    items: list[TrendItem] = Field(default_factory=list, description="趋势数据点")


class ResponseTimeTrendItem(BaseModel):
    """每日响应时间分位数数据点"""

    date: str = Field(..., description="日期 (YYYY-MM-DD)")
    p50: float = Field(default=0.0, description="P50 分位数（ms）")
    p90: float = Field(default=0.0, description="P90 分位数（ms）")
    p95: float = Field(default=0.0, description="P95 分位数（ms）")
    p99: float = Field(default=0.0, description="P99 分位数（ms）")
    avg: float = Field(default=0.0, description="平均响应时间（ms）")
    min: float = Field(default=0.0, description="最小响应时间（ms）")
    max: float = Field(default=0.0, description="最大响应时间（ms）")
    total: int = Field(default=0, description="样本数量")


class ResponseTimeTrendResponse(BaseModel):
    """响应时间趋势响应"""

    days: int = Field(..., description="统计天数")
    items: list[ResponseTimeTrendItem] = Field(default_factory=list, description="分位数趋势数据")


class FailureCategoryItem(BaseModel):
    """失败分类项"""

    category: str = Field(..., description="分类标识")
    count: int = Field(default=0, description="失败次数")
    percentage: float = Field(default=0.0, description="占比")


class FailureCategoryResponse(BaseModel):
    """失败分类响应"""

    days: int = Field(..., description="统计天数")
    items: list[FailureCategoryItem] = Field(default_factory=list, description="分类列表")


class UnstableEndpointItem(BaseModel):
    """不稳定接口项"""

    endpoint: str = Field(..., description="接口/用例名称")
    pass_rate: float = Field(default=0.0, description="通过率")
    total_runs: int = Field(default=0, description="总执行次数")


class UnstableEndpointResponse(BaseModel):
    """不稳定接口响应"""

    days: int = Field(..., description="统计天数")
    threshold: float = Field(..., description="不稳定阈值")
    items: list[UnstableEndpointItem] = Field(default_factory=list, description="不稳定接口列表")


class TopFailure(BaseModel):
    """Top N 失败用例"""

    case_id: str = Field(..., description="用例 ID")
    case_name: str = Field(..., description="用例名称")
    fail_count: int = Field(default=0, description="失败次数")
    last_failed_at: Optional[datetime] = Field(default=None, description="最近失败时间")
    last_error: Optional[str] = Field(default=None, description="最近错误信息")


class TopFailuresResponse(BaseModel):
    """Top N 失败响应"""

    items: list[TopFailure] = Field(default_factory=list, description="失败用例列表")
