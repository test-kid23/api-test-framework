"""调度任务请求/响应 Schema"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ScheduleTriggerType(str, Enum):
    """调度触发类型"""

    CRON = "cron"
    INTERVAL = "interval"


# ==================== 请求体 ====================


class ScheduleCreate(BaseModel):
    """创建调度任务请求"""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="调度名称",
    )
    suite_id: str = Field(
        ...,
        description="关联测试套件 ID",
    )
    env_name: str = Field(
        default="dev",
        description="执行环境名称",
    )
    trigger_type: ScheduleTriggerType = Field(
        ...,
        description="触发类型: cron / interval",
    )
    cron_expression: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Cron 表达式，如 '0 8 * * *'（仅 cron 类型必填）",
    )
    interval_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        le=86400,
        description="间隔秒数，最大 86400（仅 interval 类型必填）",
    )
    enabled: bool = Field(
        default=True,
        description="是否启用",
    )


class ScheduleUpdate(BaseModel):
    """更新调度任务请求"""

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="调度名称",
    )
    env_name: Optional[str] = Field(
        default=None,
        description="执行环境名称",
    )
    enabled: Optional[bool] = Field(
        default=None,
        description="是否启用",
    )
    cron_expression: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Cron 表达式",
    )
    interval_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        le=86400,
        description="间隔秒数",
    )


# ==================== 响应体 ====================


class ScheduleResponse(BaseModel):
    """调度任务响应"""

    id: str = Field(..., description="调度 ID")
    name: str = Field(..., description="调度名称")
    suite_id: str = Field(..., description="关联测试套件 ID")
    env_name: str = Field(..., description="执行环境名称")
    trigger_type: str = Field(..., description="触发类型")
    cron_expression: Optional[str] = Field(default=None, description="Cron 表达式")
    interval_seconds: Optional[int] = Field(default=None, description="间隔秒数")
    enabled: bool = Field(..., description="是否启用")
    last_run_at: Optional[datetime] = Field(default=None, description="上次执行时间")
    next_run_at: Optional[datetime] = Field(default=None, description="下次执行时间")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")

    model_config = {"from_attributes": True}
