"""覆盖率分析请求/响应 Schema"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ==================== 请求体 ====================


class CoverageAnalysisRequest(BaseModel):
    """覆盖率分析请求"""

    spec_url: str = Field(
        ...,
        min_length=1,
        description="OpenAPI spec 的 URL 或本地文件路径",
        examples=["https://petstore3.swagger.io/api/v3/openapi.json"],
    )


class CoverageGenerateRequest(BaseModel):
    """一键生成缺失用例请求"""

    spec_url: str = Field(
        ...,
        min_length=1,
        description="OpenAPI spec 的 URL 或本地文件路径",
    )
    endpoints: Optional[list[dict[str, str]]] = Field(
        default=None,
        description="要生成的 endpoint 列表，每项含 method 和 path。为空则生成所有未覆盖项。",
        examples=[[
            {"method": "POST", "path": "/users"},
            {"method": "GET", "path": "/users/{id}"},
        ]],
    )
    suite_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="生成用例的套件名称，为空则使用 spec info.title",
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=500,
        description="最多生成的用例数量，为空则生成全部",
    )


# ==================== 响应体 ====================


class EndpointInfoResponse(BaseModel):
    """单个 endpoint 信息"""

    method: str = Field(..., description="HTTP 方法")
    path: str = Field(..., description="API 路径模式")
    summary: str = Field(default="", description="接口摘要")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    operation_id: str = Field(default="", description="OpenAPI operationId")
    priority: str = Field(default="P1", description="推断的优先级")


class CoverageGapResponse(BaseModel):
    """覆盖率缺口"""

    endpoint: EndpointInfoResponse = Field(..., description="未覆盖的 endpoint")
    has_similar: bool = Field(default=False, description="是否有近似用例")
    similar_case_names: list[str] = Field(default_factory=list, description="近似用例名称列表")


class CoverageGroupResponse(BaseModel):
    """分组覆盖率统计"""

    group_key: str = Field(..., description="分组键（tag名/method名/priority名）")
    total: int = Field(..., description="总 endpoint 数")
    covered: int = Field(..., description="已覆盖数")
    uncovered: int = Field(..., description="未覆盖数")
    coverage_rate: float = Field(..., description="覆盖率（0.0-1.0）")


class CoverageReportResponse(BaseModel):
    """覆盖率分析报告"""

    spec_title: str = Field(..., description="OpenAPI spec 标题")
    spec_version: str = Field(default="", description="OpenAPI 版本号")
    total_endpoints: int = Field(..., description="总 endpoint 数")
    covered_endpoints: int = Field(..., description="已覆盖 endpoint 数")
    uncovered_endpoints: int = Field(..., description="未覆盖 endpoint 数")
    coverage_rate: float = Field(..., description="总体覆盖率（0.0-1.0）")
    coverage_percent: float = Field(..., description="覆盖率百分比（0-100）")
    by_tag: list[CoverageGroupResponse] = Field(default_factory=list, description="按 tag 分组统计")
    by_method: list[CoverageGroupResponse] = Field(default_factory=list, description="按 method 分组统计")
    by_priority: list[CoverageGroupResponse] = Field(default_factory=list, description="按优先级分组统计")
    gaps: list[CoverageGapResponse] = Field(default_factory=list, description="覆盖率缺口列表")
    recommendations: list[EndpointInfoResponse] = Field(default_factory=list, description="推荐生成的用例")


class GeneratedCaseItem(BaseModel):
    """生成的单个用例"""

    name: str = Field(..., description="用例名称")
    method: str = Field(..., description="HTTP 方法")
    path: str = Field(..., description="请求路径")
    description: str = Field(default="", description="用例描述")
    tags: list[str] = Field(default_factory=list, description="标签")
    priority: str = Field(default="P1", description="优先级")
    yaml_content: str = Field(..., description="YAML 内容")


class GenerateResultResponse(BaseModel):
    """一键生成结果"""

    total_generated: int = Field(..., description="成功生成的用例数")
    generated_cases: list[GeneratedCaseItem] = Field(default_factory=list, description="生成的用例列表")
    errors: list[str] = Field(default_factory=list, description="生成过程中的错误")
