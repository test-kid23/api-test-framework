"""环境配置请求/响应 Schema"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ==================== 请求体 ====================


class EnvironmentCreate(BaseModel):
    """创建环境请求"""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="环境名称（唯一）",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="环境描述",
    )
    base_url: str | None = Field(
        default=None,
        max_length=500,
        description="被测服务 HTTP 基础 URL",
    )
    ws_url: str | None = Field(
        default=None,
        max_length=500,
        description="WebSocket 服务 URL",
    )
    variables: dict | None = Field(
        default=None,
        description="环境级变量字典（如 admin_user/dev123）",
    )
    http_config: dict | None = Field(
        default=None,
        description="HTTP 客户端覆盖配置（timeout/verify_ssl 等）",
    )


class EnvironmentUpdate(BaseModel):
    """更新环境请求（所有字段可选）"""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="环境名称（唯一）",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="环境描述",
    )
    base_url: str | None = Field(
        default=None,
        max_length=500,
        description="被测服务 HTTP 基础 URL",
    )
    ws_url: str | None = Field(
        default=None,
        max_length=500,
        description="WebSocket 服务 URL",
    )
    variables: dict | None = Field(
        default=None,
        description="环境级变量字典",
    )
    http_config: dict | None = Field(
        default=None,
        description="HTTP 客户端覆盖配置",
    )


# ==================== 响应体 ====================


class EnvironmentResponse(BaseModel):
    """环境配置响应"""

    id: str = Field(..., description="环境 ID")
    name: str = Field(..., description="环境名称")
    description: str | None = Field(default=None, description="环境描述")
    base_url: str | None = Field(default=None, description="被测服务 HTTP 基础 URL")
    ws_url: str | None = Field(default=None, description="WebSocket 服务 URL")
    variables: dict | None = Field(default=None, description="环境级变量字典（敏感字段已脱敏）")
    http_config: dict | None = Field(default=None, description="HTTP 客户端覆盖配置")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")

    model_config = {"from_attributes": True}
