"""智能断言请求/响应 Schema"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ==================== 请求体 ====================


class InferSchemaRequest(BaseModel):
    """触发 Schema 推断的请求"""

    sample_limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="最多使用的成功响应样本数",
    )
    case_id: Optional[str] = Field(
        default=None,
        description="用例 ID（若 URL 中未提供）",
    )
    case_name: str = Field(
        default="",
        description="用例名称（用于标识）",
    )


class ValidateResponseRequest(BaseModel):
    """手动传入响应体进行校验的请求"""

    response_body: dict[str, Any] = Field(
        ...,
        description="待校验的响应体（JSON 对象）",
    )
    case_id: str = Field(
        ...,
        description="关联的用例 ID（用于查找已推断的 Schema）",
    )


class GenerateAssertionsRequest(BaseModel):
    """从 Schema 生成断言的请求"""

    case_id: str = Field(
        ...,
        description="用例 ID",
    )
    exclude_paths: list[str] = Field(
        default_factory=list,
        description="要排除的字段路径列表",
    )
    include_only: list[str] = Field(
        default_factory=list,
        description="仅包含这些路径（为空则包含所有）",
    )


# ==================== 响应体 ====================


class FieldSchemaResponse(BaseModel):
    """字段 Schema 响应"""

    path: str = Field(..., description="字段路径")
    types: list[str] = Field(default_factory=list, description="观测到的类型集合")
    dominant_type: str = Field(default="str", description="主类型")
    required: bool = Field(default=False, description="是否必填")
    occurrence_rate: float = Field(default=0.0, description="出现率")
    null_rate: float = Field(default=0.0, description="null 率")
    sample_count: int = Field(default=0, description="样本数")
    sample_values: list[Any] = Field(default_factory=list, description="采样值（最多5个）")
    value_pattern: Optional[str] = Field(default=None, description="值模式")
    min_value: Optional[float] = Field(default=None, description="最小值")
    max_value: Optional[float] = Field(default=None, description="最大值")
    min_length: Optional[int] = Field(default=None, description="最小长度")
    max_length: Optional[int] = Field(default=None, description="最大长度")
    distinct_count: int = Field(default=0, description="去重值数量")
    warnings: list[str] = Field(default_factory=list, description="推断警告")


class InferredSchemaResponse(BaseModel):
    """推断的 Schema 响应"""

    case_id: Optional[str] = Field(default=None, description="用例 ID")
    case_name: str = Field(default="", description="用例名称")
    fields: dict[str, FieldSchemaResponse] = Field(
        default_factory=dict, description="字段映射"
    )
    sample_count: int = Field(default=0, description="分析样本数")
    response_count: int = Field(default=0, description="成功响应数")
    generated_at: str = Field(default="", description="生成时间")
    top_level_type: str = Field(default="dict", description="顶层类型")


class AssertionItemResponse(BaseModel):
    """断言项响应"""

    path: str = Field(..., description="断言目标路径")
    expected: Any = Field(..., description="期望值")
    operator: str = Field(default="eq", description="断言操作符")
    message: str = Field(default="", description="描述信息")


class SmartAssertionResponse(BaseModel):
    """智能断言生成结果"""

    case_id: Optional[str] = Field(default=None, description="用例 ID")
    case_name: str = Field(default="", description="用例名称")
    schema: Optional[InferredSchemaResponse] = Field(
        default=None, description="推断的 Schema"
    )
    assertions: list[AssertionItemResponse] = Field(
        default_factory=list, description="生成的断言列表"
    )
    sample_count: int = Field(default=0, description="使用的成功响应样本数")


class StructureChangeResponse(BaseModel):
    """结构变更项响应"""

    path: str = Field(..., description="变更字段路径")
    change_type: str = Field(..., description="变更类型")
    severity: str = Field(..., description="严重程度")
    expected: Any = Field(..., description="期望值")
    actual: Any = Field(..., description="实际值")
    message: str = Field(..., description="变更描述")


class ChangeDetectionResponse(BaseModel):
    """变更检测报告响应"""

    case_id: Optional[str] = Field(default=None, description="用例 ID")
    case_name: str = Field(default="", description="用例名称")
    changes: list[StructureChangeResponse] = Field(
        default_factory=list, description="变更列表"
    )
    has_warnings: bool = Field(default=False, description="是否有警告")
    has_errors: bool = Field(default=False, description="是否有错误")
    summary: str = Field(default="", description="变更摘要")
