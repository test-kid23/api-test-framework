"""智能断言引擎 — 基于历史成功响应的 Schema 推断与变更检测

核心能力：
1. Schema 推断：收集同一接口的多次成功响应，推断字段类型、必填性、值模式
2. 响应结构变更检测：当新响应字段与模型不符时标记 warning
3. 断言生成：从推断的 Schema 自动生成 Pydantic 模型校验断言

设计原则：
- 纯推断引擎，不依赖数据库 — 由调用方传入响应数据列表
- 与现有 AssertionEngine 完全兼容 — 输出标准 AssertItem 列表
- 线程安全 — 所有方法为纯函数，无共享可变状态
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from framework.models import AssertItem
from framework.utils.logger import Logger

logger = Logger.get("smart_assertion")


# ==================== 数据模型 ====================


@dataclass
class FieldSchema:
    """单个字段的推断 Schema

    Attributes:
        path: 字段路径（如 body.code, body.data.name）。
        types: 观测到的类型集合。
        dominant_type: 出现频率最高的类型。
        required: 是否在所有样本中都出现（必填判断）。
        occurrence_rate: 字段出现率（1.0 = 100%，即必填）。
        null_rate: null 值出现率（仅在类型中包含 None 时统计）。
        sample_count: 用于推断的样本总数。
        sample_values: 采样值列表（去重，最多保留 10 个）。
        value_pattern: 检测到的值模式（email/url/date/uuid/phone/numeric/alphanumeric）。
        min_value: 数值字段的最小值。
        max_value: 数值字段的最大值。
        min_length: 字符串/数组字段的最小长度。
        max_length: 字符串/数组字段的最大长度。
        distinct_count: 去重后的不同值数量（用于枚举检测）。
        warnings: 推断过程中的警告信息。
    """

    path: str
    types: set[str] = field(default_factory=set)
    dominant_type: str = "str"
    required: bool = False
    occurrence_rate: float = 0.0
    null_rate: float = 0.0
    sample_count: int = 0
    sample_values: list[Any] = field(default_factory=list)
    value_pattern: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    distinct_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class InferredSchema:
    """从多次成功响应推断出的完整 Schema

    Attributes:
        case_id: 关联的用例 ID（可选）。
        case_name: 用例名称。
        fields: 字段 → FieldSchema 映射。
        sample_count: 用于推断的样本数量。
        response_count: 实际分析的成功响应数。
        generated_at: Schema 生成时间戳。
        top_level_type: 响应体的顶层类型（dict/list）。
    """

    case_id: str | None = None
    case_name: str = ""
    fields: dict[str, FieldSchema] = field(default_factory=dict)
    sample_count: int = 0
    response_count: int = 0
    generated_at: str = ""
    top_level_type: str = "dict"

    def to_dict(self) -> dict[str, Any]:
        """序列化为可 JSON 化的字典"""
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "fields": {
                path: {
                    "path": fs.path,
                    "types": sorted(fs.types),
                    "dominant_type": fs.dominant_type,
                    "required": fs.required,
                    "occurrence_rate": round(fs.occurrence_rate, 2),
                    "null_rate": round(fs.null_rate, 2),
                    "sample_count": fs.sample_count,
                    "sample_values": fs.sample_values[:5],
                    "value_pattern": fs.value_pattern,
                    "min_value": fs.min_value,
                    "max_value": fs.max_value,
                    "min_length": fs.min_length,
                    "max_length": fs.max_length,
                    "distinct_count": fs.distinct_count,
                    "warnings": fs.warnings,
                }
                for path, fs in self.fields.items()
            },
            "sample_count": self.sample_count,
            "response_count": self.response_count,
            "generated_at": self.generated_at,
            "top_level_type": self.top_level_type,
        }


@dataclass
class StructureChange:
    """响应结构变更检测结果

    Attributes:
        path: 变更字段路径。
        change_type: 变更类型（new_field/missing_field/type_changed/null_became_required）。
        severity: 严重程度（info/warning/error）。
        expected: 推断的期望值/类型。
        actual: 实际观测值/类型。
        message: 人类可读的变更描述。
    """

    path: str
    change_type: str
    severity: str  # info / warning / error
    expected: Any
    actual: Any
    message: str


@dataclass
class ChangeDetectionReport:
    """单次响应与 Schema 的变更对比报告

    Attributes:
        case_id: 关联用例 ID。
        case_name: 用例名称。
        changes: 变更项列表。
        has_warnings: 是否有 warning 级别及以上的变更。
        has_errors: 是否有 error 级别的变更。
    """

    case_id: str | None = None
    case_name: str = ""
    changes: list[StructureChange] = field(default_factory=list)
    has_warnings: bool = False
    has_errors: bool = False

    @property
    def summary(self) -> str:
        if not self.changes:
            return "响应结构与推断 Schema 一致"
        parts = []
        err_count = sum(1 for c in self.changes if c.severity == "error")
        warn_count = sum(1 for c in self.changes if c.severity == "warning")
        info_count = sum(1 for c in self.changes if c.severity == "info")
        if err_count:
            parts.append(f"{err_count} 个错误")
        if warn_count:
            parts.append(f"{warn_count} 个警告")
        if info_count:
            parts.append(f"{info_count} 个提示")
        return "响应结构变更: " + ", ".join(parts)


# ==================== 类型推断工具 ====================


def _infer_python_type(value: Any) -> str:
    """推断单个值的 Python 类型名

    Args:
        value: 任意 Python 值。

    Returns:
        类型名（str/int/float/bool/list/dict/NoneType）。
    """
    if value is None:
        return "NoneType"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def _detect_value_pattern(value: Any) -> str | None:
    """检测值的语义模式（email/url/date/uuid/phone 等）

    Args:
        value: 待检测的值。

    Returns:
        模式名，无匹配返回 None。
    """
    if not isinstance(value, str):
        return None

    # UUID
    if re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", value, re.I):
        return "uuid"

    # Email
    if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value):
        return "email"

    # URL
    if re.match(r"^https?://", value):
        return "url"

    # ISO date
    if re.match(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?", value):
        return "iso_date"

    # Phone (Chinese mobile)
    if re.match(r"^1[3-9]\d{9}$", value):
        return "phone"

    # IP address
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", value):
        return "ip"

    # Pure numeric string
    if re.match(r"^-?\d+(\.\d+)?$", value):
        return "numeric_string"

    # Alphanumeric only
    if re.match(r"^[a-zA-Z0-9_]+$", value):
        return "alphanumeric"

    return None


# ==================== Schema 推断器 ====================


class SchemaInferrer:
    """Schema 推断器 — 从多组成功响应中推断字段结构

    使用方式:
        inferrer = SchemaInferrer()
        schema = inferrer.infer(responses, case_name="user_api")
        assertions = inferrer.generate_assertions(schema)

    线程安全: 无实例状态，所有方法为纯函数。
    """

    @staticmethod
    def _collect_fields(
        obj: Any, prefix: str = "body", separator: str = "."
    ) -> dict[str, list[Any]]:
        """递归收集对象的所有字段路径及其值

        Args:
            obj: 待遍历的对象（dict/list/其他）。
            prefix: 当前路径前缀。
            separator: 路径分隔符。

        Returns:
            路径 → 值列表 的映射（每个路径对应的所有样本值）。
        """
        fields: dict[str, list[Any]] = {}

        if isinstance(obj, dict):
            for key, value in obj.items():
                full_path = f"{prefix}{separator}{key}"
                # 记录当前字段的值
                if full_path not in fields:
                    fields[full_path] = []
                fields[full_path].append(value)
                # 递归处理嵌套结构
                if isinstance(value, (dict, list)):
                    nested = SchemaInferrer._collect_fields(
                        value, full_path, separator
                    )
                    for k, v in nested.items():
                        if k not in fields:
                            fields[k] = []
                        fields[k].extend(v)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                item_path = f"{prefix}[{i}]"
                if isinstance(item, (dict, list)):
                    nested = SchemaInferrer._collect_fields(
                        item, item_path, separator
                    )
                    for k, v in nested.items():
                        if k not in fields:
                            fields[k] = []
                        fields[k].extend(v)
                else:
                    if item_path not in fields:
                        fields[item_path] = []
                    fields[item_path].append(item)

        return fields

    @staticmethod
    def _infer_field_schema(
        path: str, values: list[Any], total_samples: int
    ) -> FieldSchema:
        """从值列表推断单个字段的 Schema

        Args:
            path: 字段路径。
            values: 该字段在所有样本中的值列表。
            total_samples: 样本总数（用于计算出现率）。

        Returns:
            推断出的 FieldSchema。
        """
        fs = FieldSchema(path=path, sample_count=total_samples)

        if not values:
            fs.warnings.append("无样本数据")
            return fs

        # 去除 None 后统计
        non_null_values = [v for v in values if v is not None]
        null_count = sum(1 for v in values if v is None)

        # 出现率
        fs.occurrence_rate = len(values) / max(total_samples, 1)
        fs.null_rate = null_count / max(len(values), 1)

        # 必填判断：在所有样本中都出现了非 null 值
        fs.required = fs.occurrence_rate >= 0.95 and null_count == 0

        # 类型统计
        type_counts = Counter(_infer_python_type(v) for v in non_null_values)
        if type_counts:
            fs.types = set(type_counts.keys())
            fs.dominant_type = type_counts.most_common(1)[0][0]

        # 如果大多数为 None
        if not non_null_values:
            fs.types = {"NoneType"}
            fs.dominant_type = "NoneType"
            return fs

        # 采样值（去重后最多保留 10 个）
        seen: set[Any] = set()
        for v in non_null_values:
            if len(fs.sample_values) >= 10:
                break
            # 对于不可哈希类型，用字符串表示
            try:
                if v not in seen:
                    seen.add(v)
                    fs.sample_values.append(v)
            except TypeError:
                if str(v) not in {str(s) for s in fs.sample_values}:
                    fs.sample_values.append(v)

        # 值模式检测
        pattern_counts: Counter[str] = Counter()
        for v in non_null_values[:100]:  # 最多分析 100 个样本
            pattern = _detect_value_pattern(v)
            if pattern:
                pattern_counts[pattern] += 1
        if pattern_counts:
            most_common_pattern, count = pattern_counts.most_common(1)[0]
            # 至少 60% 的样本匹配才认定模式
            if count >= max(len(non_null_values) * 0.6, 2):
                fs.value_pattern = most_common_pattern

        # 数值范围
        numeric_vals: list[float] = []
        for v in non_null_values:
            try:
                if not isinstance(v, bool):
                    numeric_vals.append(float(v))
            except (ValueError, TypeError):
                pass
        if numeric_vals:
            fs.min_value = min(numeric_vals)
            fs.max_value = max(numeric_vals)

        # 长度范围（字符串和数组）
        lengths: list[int] = []
        for v in non_null_values:
            try:
                lengths.append(len(v))  # type: ignore[arg-type]
            except TypeError:
                pass
        if lengths:
            fs.min_length = min(lengths)
            fs.max_length = max(lengths)

        # 枚举检测：如果 values 数量大但 distinct 计数小
        distinct_vals = set()
        for v in non_null_values:
            try:
                distinct_vals.add(v)
            except TypeError:
                distinct_vals.add(str(v))
        fs.distinct_count = len(distinct_vals)

        # 类型漂移警告
        if len(fs.types) > 1:
            minor_types = fs.types - {fs.dominant_type}
            fs.warnings.append(
                f"类型不一致: 主类型={fs.dominant_type}, "
                f"次类型={','.join(sorted(minor_types))}"
            )

        return fs

    @staticmethod
    def infer(
        response_bodies: list[dict[str, Any]],
        case_id: str | None = None,
        case_name: str = "",
    ) -> InferredSchema:
        """从多组成功响应中推断 Schema

        Args:
            response_bodies: 成功响应的 body 部分列表（已解析为 dict）。
            case_id: 关联用例 ID（可选）。
            case_name: 用例名称。

        Returns:
            推断出的 InferredSchema。
        """
        if not response_bodies:
            logger.warning("schema_infer_no_data", case_name=case_name)
            return InferredSchema(
                case_id=case_id,
                case_name=case_name,
                sample_count=0,
                response_count=0,
                generated_at=datetime.now(timezone.utc).isoformat(),
            )

        total = len(response_bodies)

        # 收集所有字段
        all_fields: dict[str, list[Any]] = {}
        for body in response_bodies:
            if not isinstance(body, (dict, list)):
                logger.debug(
                    "schema_skip_non_dict",
                    case_name=case_name,
                    body_type=type(body).__name__,
                )
                continue
            field_map = SchemaInferrer._collect_fields(body)
            for path, vals in field_map.items():
                if path not in all_fields:
                    all_fields[path] = []
                all_fields[path].extend(vals)

        # 推断每个字段的 Schema
        fields: dict[str, FieldSchema] = {}
        for path, values in sorted(all_fields.items()):
            fields[path] = SchemaInferrer._infer_field_schema(
                path, values, total
            )

        # 确定顶层类型
        top_types = Counter(
            type(b).__name__ for b in response_bodies if isinstance(b, (dict, list))
        )
        top_level_type = top_types.most_common(1)[0][0] if top_types else "dict"

        schema = InferredSchema(
            case_id=case_id,
            case_name=case_name,
            fields=fields,
            sample_count=total,
            response_count=total,
            generated_at=datetime.now(timezone.utc).isoformat(),
            top_level_type=top_level_type,
        )

        logger.info(
            "schema_inferred",
            case_name=case_name,
            field_count=len(fields),
            sample_count=total,
            required_count=sum(1 for f in fields.values() if f.required),
        )

        return schema

    @staticmethod
    def generate_assertions(
        schema: InferredSchema,
        exclude_paths: list[str] | None = None,
        include_only: list[str] | None = None,
    ) -> list[AssertItem]:
        """从推断的 Schema 生成断言列表

        生成策略：
        - status_code → eq 200（始终添加）
        - 必填字段 → not_null 断言
        - 有明确类型的字段 → type 断言
        - 枚举字段（distinct_count ≤ 5 且 sample_count ≥ 3）→ in 断言
        - 数值字段 → between 断言（含范围）
        - 字符串字段 → length 断言（含长度范围）

        Args:
            schema: 推断出的 Schema。
            exclude_paths: 要排除的字段路径列表。
            include_only: 仅包含这些路径（为空则包含所有）。

        Returns:
            AssertItem 列表，可直接用于 TestCase.assertions。
        """
        assertions: list[AssertItem] = []

        # 始终添加状态码断言
        assertions.append(
            AssertItem(path="status_code", expected=200, operator="eq")
        )

        exclude = set(exclude_paths or [])
        include = set(include_only) if include_only else None

        for path, fs in schema.fields.items():
            if path in exclude:
                continue
            if include is not None and path not in include:
                continue

            # 1. 必填字段 → not_null
            if fs.required:
                assertions.append(
                    AssertItem(
                        path=path,
                        expected=None,
                        operator="not_null",
                        message=f"[Auto] 必填字段 {path}",
                    )
                )

            # 2. 类型断言（对单一主类型）
            if fs.dominant_type in ("str", "int", "float", "bool", "list", "dict"):
                assertions.append(
                    AssertItem(
                        path=path,
                        expected=fs.dominant_type,
                        operator="type",
                        message=f"[Auto] 字段 {path} 类型为 {fs.dominant_type}",
                    )
                )

            # 3. 枚举字段 → in 断言
            if (
                fs.distinct_count <= 5
                and fs.sample_count >= 3
                and len(fs.sample_values) >= 1
                and fs.dominant_type not in ("list", "dict")
            ):
                assertions.append(
                    AssertItem(
                        path=path,
                        expected=fs.sample_values,
                        operator="in",
                        message=f"[Auto] 字段 {path} 值应在 {fs.sample_values} 中",
                    )
                )

            # 4. 数值范围 → between 断言
            if fs.min_value is not None and fs.max_value is not None:
                if fs.min_value != fs.max_value:
                    assertions.append(
                        AssertItem(
                            path=path,
                            expected=[fs.min_value, fs.max_value],
                            operator="between",
                            message=f"[Auto] 字段 {path} 范围 [{fs.min_value}, {fs.max_value}]",
                        )
                    )

            # 5. 长度范围 → length 断言
            if fs.min_length is not None and fs.max_length is not None:
                if fs.min_length > 0 or fs.max_length > 0:
                    if fs.min_length == fs.max_length:
                        assertions.append(
                            AssertItem(
                                path=path,
                                expected=fs.min_length,
                                operator="length",
                                message=f"[Auto] 字段 {path} 长度 = {fs.min_length}",
                            )
                        )
                    else:
                        # 使用字符串格式的长度范围
                        assertions.append(
                            AssertItem(
                                path=path,
                                expected=f">={fs.min_length}",
                                operator="length",
                                message=(
                                    f"[Auto] 字段 {path} 长度范围 "
                                    f"[{fs.min_length}, {fs.max_length}]"
                                ),
                            )
                        )

        logger.info(
            "assertions_generated",
            case_name=schema.case_name,
            assertion_count=len(assertions),
            field_count=len(schema.fields),
        )

        return assertions


# ==================== 变更检测器 ====================


class ChangeDetector:
    """响应结构变更检测器

    对比新响应与推断 Schema，检测：
    - new_field: 出现新字段（info 级别）
    - missing_required: 必填字段缺失（error 级别）
    - type_mismatch: 字段类型与推断不一致（warning 级别）
    - null_required: 必填字段为 null（error 级别）

    线程安全: 无实例状态，所有方法为纯函数。
    """

    @staticmethod
    def detect(
        schema: InferredSchema,
        response_body: dict[str, Any],
        case_id: str | None = None,
        case_name: str = "",
    ) -> ChangeDetectionReport:
        """检测单次响应结构变更

        Args:
            schema: 推断出的 Schema。
            response_body: 新的响应体（已解析为 dict）。
            case_id: 关联用例 ID（可选）。
            case_name: 用例名称。

        Returns:
            变更检测报告。
        """
        changes: list[StructureChange] = []

        if not isinstance(response_body, dict):
            return ChangeDetectionReport(
                case_id=case_id,
                case_name=case_name,
                changes=[
                    StructureChange(
                        path="(root)",
                        change_type="type_mismatch",
                        severity="error",
                        expected="dict",
                        actual=type(response_body).__name__,
                        message=f"响应体类型不匹配: 期望 dict，实际 {type(response_body).__name__}",
                    )
                ],
                has_warnings=True,
                has_errors=True,
            )

        # 收集新响应中的所有字段
        actual_fields = SchemaInferrer._collect_fields(response_body)

        # 检查推断 Schema 中的每个字段
        for path, fs in schema.fields.items():
            if path not in actual_fields:
                # 字段缺失
                severity = "error" if fs.required else "warning"
                changes.append(
                    StructureChange(
                        path=path,
                        change_type="missing_field",
                        severity=severity,
                        expected=f"存在 ({fs.dominant_type})",
                        actual="缺失",
                        message=(
                            f"{'必填' if fs.required else '可选'}字段 {path} 在响应中缺失"
                        ),
                    )
                )
                continue

            # 取第一个值进行分析（响应中通常只有一个值）
            actual_value = actual_fields[path][0] if actual_fields[path] else None
            actual_type = _infer_python_type(actual_value)

            # 类型检查
            if fs.dominant_type != "NoneType" and actual_type not in fs.types:
                # 允许 int→float 的向上兼容（JSON 中常见）
                if not (
                    actual_type == "int" and "float" in fs.types
                ) and not (
                    actual_type == "float" and "int" in fs.types
                ):
                    changes.append(
                        StructureChange(
                            path=path,
                            change_type="type_changed",
                            severity="warning",
                            expected=fs.dominant_type,
                            actual=actual_type,
                            message=(
                                f"字段 {path} 类型变更: "
                                f"期望 {fs.dominant_type}，实际 {actual_type}"
                            ),
                        )
                    )

            # 必填但为 null
            if fs.required and actual_value is None:
                changes.append(
                    StructureChange(
                        path=path,
                        change_type="null_required",
                        severity="error",
                        expected=f"非 null ({fs.dominant_type})",
                        actual="null",
                        message=f"必填字段 {path} 值为 null",
                    )
                )

        # 检查新字段
        for path in actual_fields:
            if path not in schema.fields:
                changes.append(
                    StructureChange(
                        path=path,
                        change_type="new_field",
                        severity="info",
                        expected="不存在",
                        actual=type(actual_fields[path][0]).__name__
                        if actual_fields[path]
                        else "未知",
                        message=f"发现新字段 {path}（不在推断 Schema 中）",
                    )
                )

        has_errors = any(c.severity == "error" for c in changes)
        has_warnings = any(c.severity in ("warning", "error") for c in changes)

        report = ChangeDetectionReport(
            case_id=case_id,
            case_name=case_name,
            changes=sorted(changes, key=lambda c: (c.severity, c.path)),
            has_warnings=has_warnings,
            has_errors=has_errors,
        )

        if changes:
            log_level = "error" if has_errors else ("warning" if has_warnings else "info")
            getattr(logger, log_level)(
                "structure_change_detected",
                case_name=case_name,
                change_count=len(changes),
                has_errors=has_errors,
                has_warnings=has_warnings,
            )

        return report
