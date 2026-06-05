"""通用 Schema: 分页、错误响应、标准 API 应答"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ==================== 分页 ====================


class PaginationParams(BaseModel):
    """分页请求参数"""

    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数，最大 100")


class PaginationMeta(BaseModel):
    """分页元信息"""

    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    total: int = Field(..., description="总条数")
    total_pages: int = Field(..., description="总页数")

    @classmethod
    def from_params(cls, params: PaginationParams, total: int) -> PaginationMeta:
        total_pages = (total + params.page_size - 1) // params.page_size
        return cls(
            page=params.page,
            page_size=params.page_size,
            total=total,
            total_pages=total_pages,
        )


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""

    items: list[T] = Field(default_factory=list, description="数据列表")
    pagination: PaginationMeta = Field(..., description="分页信息")


# ==================== 错误响应 ====================


class ErrorDetail(BaseModel):
    """单条错误信息"""

    loc: list[str] = Field(default_factory=list, description="错误位置")
    msg: str = Field(..., description="错误描述")
    type: str = Field(default="", description="错误类型")


class ErrorResponse(BaseModel):
    """标准错误响应"""

    success: bool = Field(default=False, description="始终为 false")
    error: str = Field(..., description="错误摘要")
    detail: list[ErrorDetail] = Field(default_factory=list, description="详细错误列表")
    trace_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex[:8],
        description="请求追踪 ID",
    )


# ==================== 通用成功响应 ====================


class SuccessResponse(BaseModel, Generic[T]):
    """标准成功响应"""

    success: bool = Field(default=True, description="始终为 true")
    data: T = Field(..., description="响应数据")


class MessageResponse(BaseModel):
    """简单消息响应"""

    success: bool = Field(default=True)
    message: str = Field(..., description="提示消息")


# ==================== 时间戳 Mixin ====================


class TimestampMixin(BaseModel):
    """带时间戳的模型基类"""

    id: str = Field(
        default_factory=lambda: uuid.uuid4().hex[:12],
        description="唯一标识符",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="创建时间 (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="更新时间 (UTC)",
    )
