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
    items: list[TrendItem] = Field(default_factory=list, description="趋势数据点")


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
