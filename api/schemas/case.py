"""用例请求/响应 Schema"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from api.schemas.common import TimestampMixin


# ==================== 请求体 ====================


class CaseCreateRequest(BaseModel):
    """创建用例请求"""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="用例名称",
        examples=["登录接口 - 正确凭据"],
    )
    description: str = Field(default="", description="用例描述")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    priority: str = Field(
        default="P1",
        pattern=r"^P[0-3]$",
        description="优先级: P0/P1/P2/P3",
    )
    yaml_content: str = Field(
        ...,
        min_length=1,
        description="用例 YAML 内容",
    )
    timeout: Optional[int] = Field(
        default=None,
        ge=1,
        le=3600,
        description="自定义超时（秒），为空则使用全局配置",
    )


class CaseUpdateRequest(BaseModel):
    """更新用例请求（所有字段可选）"""

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="用例名称",
    )
    description: Optional[str] = Field(default=None, description="用例描述")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    priority: Optional[str] = Field(
        default=None,
        pattern=r"^P[0-3]$",
        description="优先级: P0/P1/P2/P3",
    )
    yaml_content: Optional[str] = Field(
        default=None,
        min_length=1,
        description="用例 YAML 内容",
    )
    timeout: Optional[int] = Field(
        default=None,
        ge=1,
        le=3600,
        description="自定义超时（秒）",
    )


# ==================== 响应体 ====================


class CaseResponse(TimestampMixin):
    """用例响应"""

    name: str = Field(..., description="用例名称")
    description: str = Field(default="", description="用例描述")
    tags: list[str] = Field(default_factory=list, description="标签")
    priority: str = Field(default="P1", description="优先级")
    yaml_content: str = Field(..., description="YAML 内容")
    timeout: Optional[int] = Field(default=None, description="自定义超时")
    version: int = Field(default=1, description="版本号")


class CaseListItem(BaseModel):
    """用例列表项（精简版，不含 yaml_content）"""

    id: str = Field(..., description="唯一标识符")
    name: str = Field(..., description="用例名称")
    description: str = Field(default="", description="用例描述")
    tags: list[str] = Field(default_factory=list, description="标签")
    priority: str = Field(default="P1", description="优先级")
    timeout: Optional[int] = Field(default=None, description="自定义超时")
    version: int = Field(default=1, description="版本号")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class CaseQueryParams(BaseModel):
    """用例列表查询参数"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")
    tag: Optional[str] = Field(default=None, description="按标签过滤")
    priority: Optional[str] = Field(
        default=None,
        pattern=r"^P[0-3]$",
        description="按优先级过滤",
    )
    search: Optional[str] = Field(
        default=None,
        min_length=1,
        description="按名称/描述模糊搜索",
    )


# ==================== 导入请求/响应 ====================


class CaseImportRequest(BaseModel):
    """OpenAPI / Swagger 导入请求"""

    spec_url: str = Field(
        ...,
        min_length=1,
        description="OpenAPI spec 的 URL 或本地文件路径",
        examples=["https://petstore3.swagger.io/api/v3/openapi.json"],
    )
    suite_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="导入后的套件名称，不指定则使用 spec info.title",
    )


class CaseImportResult(BaseModel):
    """导入结果"""

    total_discovered: int = Field(..., description="发现的接口总数")
    total_imported: int = Field(..., description="成功导入的用例数")
    total_skipped: int = Field(default=0, description="跳过的用例数")
    suite_name: str = Field(..., description="生成的套件名称")
    case_ids: list[str] = Field(default_factory=list, description="导入的用例 ID 列表")
    errors: list[str] = Field(default_factory=list, description="导入过程中的错误信息")
