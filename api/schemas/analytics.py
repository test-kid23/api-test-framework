"""高级分析请求/响应 Schema — 稳定性排行、分位数、失败分类、ROI"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==================== 接口稳定性排行 ====================


class StabilityRankingItem(BaseModel):
    """稳定性排行项"""

    case_name: str = Field(..., description="用例/接口名称")
    case_id: str = Field(default="", description="用例 ID")
    total: int = Field(default=0, description="总执行次数")
    passed: int = Field(default=0, description="通过次数")
    failed: int = Field(default=0, description="失败次数")
    failure_rate: float = Field(default=0.0, description="失败率")
    avg_elapsed_ms: float = Field(default=0.0, description="平均耗时（ms）")
    last_executed_at: Optional[datetime] = Field(default=None, description="最近执行时间")


class StabilityRankingResponse(BaseModel):
    """稳定性排行响应"""

    days: int = Field(..., description="统计天数")
    items: list[StabilityRankingItem] = Field(default_factory=list, description="排行列表")


# ==================== 响应时间分位数 ====================


class PercentileItem(BaseModel):
    """响应时间分位数"""

    p50: float = Field(default=0.0, description="P50 分位数（ms）")
    p95: float = Field(default=0.0, description="P95 分位数（ms）")
    p99: float = Field(default=0.0, description="P99 分位数（ms）")
    avg: float = Field(default=0.0, description="平均响应时间（ms）")
    min: float = Field(default=0.0, description="最小响应时间（ms）")
    max: float = Field(default=0.0, description="最大响应时间（ms）")
    total_samples: int = Field(default=0, description="样本数量")


class PercentileResponse(BaseModel):
    """分位数响应"""

    days: int = Field(..., description="统计天数")
    data: PercentileItem = Field(default_factory=PercentileItem, description="分位数数据")


# ==================== 失败原因分类 ====================


class FailureCategoryItem(BaseModel):
    """失败分类项"""

    category: str = Field(..., description="分类标识: assertion_failure/connection_timeout/connection_error/http_error/other")
    label: str = Field(..., description="分类中文标签")
    count: int = Field(default=0, description="失败次数")
    percentage: float = Field(default=0.0, description="占比（%）")
    examples: list[str] = Field(default_factory=list, description="示例用例名（最多 3 个）")


class FailureCategoryResponse(BaseModel):
    """失败分类响应"""

    days: int = Field(..., description="统计天数")
    items: list[FailureCategoryItem] = Field(default_factory=list, description="分类列表")


# ==================== ROI 统计 ====================


class Recent30dStats(BaseModel):
    """最近 30 天统计"""

    execution_count: int = Field(default=0, description="执行次数")
    test_run_count: int = Field(default=0, description="用例运行次数")
    pass_rate: float = Field(default=0.0, description="通过率（%）")


class RoiStatsItem(BaseModel):
    """ROI 统计"""

    total_automated_cases: int = Field(default=0, description="自动化用例总数")
    covered_endpoints: int = Field(default=0, description="覆盖接口数（去重）")
    total_executions: int = Field(default=0, description="总执行次数")
    total_test_runs: int = Field(default=0, description="总用例运行次数")
    overall_pass_rate: float = Field(default=0.0, description="历史总通过率（%）")
    estimated_manual_hours: float = Field(default=0.0, description="预估手动执行耗时（小时）")
    estimated_auto_hours: float = Field(default=0.0, description="预估自动化执行耗时（小时）")
    estimated_hours_saved: float = Field(default=0.0, description="预估节省工时（小时）")
    recent_30d: Recent30dStats = Field(default_factory=Recent30dStats, description="最近 30 天统计")
