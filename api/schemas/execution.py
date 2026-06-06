"""执行请求/响应 Schema"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from api.schemas.common import TimestampMixin


class ExecutionStatus(str, Enum):
    """执行状态"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class ExecutionTrigger(str, Enum):
    """执行触发方式"""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    API = "api"


# ==================== 请求体 ====================


class ExecutionRequest(BaseModel):
    """触发执行请求"""

    case_ids: list[str] = Field(
        ...,
        min_length=1,
        description="要执行的用例 ID 列表",
    )
    suite_id: Optional[str] = Field(default=None, description="套件 ID（可选）")
    env: str = Field(default="dev", description="目标环境名称")
    trigger: ExecutionTrigger = Field(
        default=ExecutionTrigger.API,
        description="触发方式",
    )


# ==================== 响应体 ====================


class ExecutionCaseResult(BaseModel):
    """执行中单个用例结果"""

    case_id: str = Field(..., description="用例 ID")
    case_name: str = Field(..., description="用例名称")
    status: str = Field(..., description="PASS / FAIL / SKIP / ERROR")
    error: Optional[str] = Field(default=None, description="错误信息")
    elapsed_ms: float = Field(default=0.0, description="执行耗时（毫秒）")


class ExecutionResponse(TimestampMixin):
    """执行响应"""

    name: str = Field(default="", description="执行名称")
    status: ExecutionStatus = Field(
        default=ExecutionStatus.PENDING,
        description="执行状态",
    )
    trigger: ExecutionTrigger = Field(
        default=ExecutionTrigger.API,
        description="触发方式",
    )
    env: str = Field(default="dev", description="目标环境")
    mode: str = Field(default="local", description="执行模式: local / distributed")
    celery_task_id: Optional[str] = Field(
        default=None, description="Celery 任务 ID（分布式模式专用）"
    )
    case_ids: list[str] = Field(default_factory=list, description="包含的用例 ID 列表")
    suite_id: Optional[str] = Field(default=None, description="关联套件 ID")
    results: list[ExecutionCaseResult] = Field(
        default_factory=list,
        description="用例执行结果",
    )
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    finished_at: Optional[datetime] = Field(default=None, description="完成时间")
    summary: dict[str, Any] = Field(default_factory=dict, description="执行摘要")


class ExecutionReportResponse(BaseModel):
    """执行报告详情"""

    execution_id: str = Field(..., description="执行 ID")
    status: ExecutionStatus = Field(..., description="执行状态")
    total: int = Field(default=0, description="用例总数")
    passed: int = Field(default=0, description="通过数")
    failed: int = Field(default=0, description="失败数")
    skipped: int = Field(default=0, description="跳过数")
    error: int = Field(default=0, description="错误数")
    pass_rate: float = Field(default=0.0, description="通过率")
    avg_elapsed_ms: float = Field(default=0.0, description="平均耗时（ms）")
    results: list[ExecutionCaseResult] = Field(
        default_factory=list,
        description="详细结果",
    )
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    finished_at: Optional[datetime] = Field(default=None, description="完成时间")
