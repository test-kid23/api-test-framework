"""智能断言引擎集成测试

覆盖：
- Schema 推断：字段类型推断、必填检测、值模式检测
- 断言生成：从 Schema 生成 AssertItem 列表
- 变更检测：新增字段、缺失字段、类型变更检测
"""

from __future__ import annotations

import uuid

import pytest

from framework.assertion.smart import (
    ChangeDetectionReport,
    ChangeDetector,
    FieldSchema,
    InferredSchema,
    SchemaInferrer,
    StructureChange,
    _detect_value_pattern,
    _infer_python_type,
)
from framework.models import AssertItem


# ==================== 类型推断工具测试 ====================


class TestInferPythonType:
    def test_primitive_types(self):
        assert _infer_python_type("hello") == "str"
        assert _infer_python_type(42) == "int"
        assert _infer_python_type(3.14) == "float"
        assert _infer_python_type(True) == "bool"
        assert _infer_python_type(False) == "bool"
        assert _infer_python_type(None) == "NoneType"

    def test_collection_types(self):
        assert _infer_python_type([1, 2, 3]) == "list"
        assert _infer_python_type({"key": "val"}) == "dict"


class TestDetectValuePattern:
    def test_uuid(self):
        assert _detect_value_pattern("550e8400-e29b-41d4-a716-446655440000") == "uuid"

    def test_email(self):
        assert _detect_value_pattern("user@example.com") == "email"

    def test_url(self):
        assert _detect_value_pattern("https://api.example.com/v1/users") == "url"

    def test_iso_date(self):
        assert _detect_value_pattern("2024-01-15") == "iso_date"
        assert _detect_value_pattern("2024-01-15T10:30:00") == "iso_date"

    def test_phone(self):
        assert _detect_value_pattern("13800138000") == "phone"

    def test_ip(self):
        assert _detect_value_pattern("192.168.1.1") == "ip"

    def test_numeric_string(self):
        assert _detect_value_pattern("-123.45") == "numeric_string"

    def test_no_pattern(self):
        assert _detect_value_pattern("random text here!!") is None
        assert _detect_value_pattern(12345) is None


# ==================== Schema 推断器测试 ====================


class TestSchemaInferrerCollectFields:
    def test_flat_dict(self):
        body = {"code": 0, "message": "success", "data": {"id": 1, "name": "test"}}
        fields = SchemaInferrer._collect_fields(body)
        assert "body.code" in fields
        assert "body.message" in fields
        assert "body.data" in fields
        assert "body.data.id" in fields
        assert "body.data.name" in fields

    def test_nested_list(self):
        body = {"items": [{"id": 1}, {"id": 2}]}
        fields = SchemaInferrer._collect_fields(body)
        assert "body.items" in fields
        assert "body.items[0].id" in fields
        assert "body.items[1].id" in fields

    def test_list_body(self):
        body = [{"a": 1}, {"a": 2}]
        fields = SchemaInferrer._collect_fields(body)
        assert "body[0].a" in fields


class TestSchemaInferrerInferField:
    def test_stable_string_field(self):
        fs = SchemaInferrer._infer_field_schema(
            "body.name", ["Alice", "Bob", "Charlie"], 3
        )
        assert fs.dominant_type == "str"
        assert fs.required is True
        assert fs.occurrence_rate == 1.0

    def test_optional_field(self):
        fs = SchemaInferrer._infer_field_schema(
            "body.optional", ["val1", "val2"], 5
        )
        assert fs.occurrence_rate == 0.4  # 2 out of 5 samples
        assert fs.required is False

    def test_int_field_with_range(self):
        fs = SchemaInferrer._infer_field_schema(
            "body.count", [1, 2, 3, 5, 10], 5
        )
        assert fs.dominant_type == "int"
        assert fs.min_value == 1.0
        assert fs.max_value == 10.0

    def test_enum_detection(self):
        fs = SchemaInferrer._infer_field_schema(
            "body.status", ["active", "active", "inactive", "active", "pending"], 5
        )
        assert fs.distinct_count == 3
        assert len(fs.sample_values) > 0

    def test_null_field(self):
        fs = SchemaInferrer._infer_field_schema(
            "body.maybe_null", [None, "val", None], 3
        )
        assert fs.null_rate == pytest.approx(2 / 3)
        assert fs.dominant_type == "str"

    def test_type_inconsistency_warning(self):
        fs = SchemaInferrer._infer_field_schema(
            "body.unstable", [1, "string", 2], 3
        )
        assert "int" in fs.types
        assert "str" in fs.types
        assert len(fs.warnings) > 0

    def test_empty_values(self):
        fs = SchemaInferrer._infer_field_schema("body.empty", [], 3)
        assert fs.warnings[0] == "无样本数据"


class TestSchemaInferrerInfer:
    def test_infer_from_multiple_responses(self):
        responses = [
            {"code": 0, "message": "ok", "data": {"id": 1, "name": "Alice"}},
            {"code": 0, "message": "ok", "data": {"id": 2, "name": "Bob"}},
            {"code": 0, "message": "ok", "data": {"id": 3, "name": "Charlie", "extra": "new"}},
        ]
        schema = SchemaInferrer.infer(responses, case_name="test_api")

        assert schema.case_name == "test_api"
        assert schema.sample_count == 3
        assert schema.response_count == 3
        assert len(schema.fields) >= 5  # code, message, data, data.id, data.name, data.extra

        # code 应该是必填的 int
        code_field = schema.fields.get("body.code")
        assert code_field is not None
        assert code_field.dominant_type == "int"
        assert code_field.required is True

    def test_infer_empty_responses(self):
        schema = SchemaInferrer.infer([], case_name="empty")
        assert schema.sample_count == 0
        assert len(schema.fields) == 0


# ==================== 断言生成测试 ====================


class TestGenerateAssertions:
    def test_generates_assertions_for_required_fields(self):
        responses = [
            {"code": 0, "message": "success", "data": {"total": 100, "list": []}},
            {"code": 0, "message": "ok", "data": {"total": 200, "list": []}},
            {"code": 0, "message": "ok", "data": {"total": 300, "list": []}},
        ]
        schema = SchemaInferrer.infer(responses, case_name="test")
        assertions = SchemaInferrer.generate_assertions(schema)

        # 应该包含 status_code 断言
        status_assertions = [a for a in assertions if a.path == "status_code"]
        assert len(status_assertions) >= 1

        # 必填字段应该有 not_null 断言
        not_null_assertions = [a for a in assertions if a.operator == "not_null"]
        assert len(not_null_assertions) > 0

    def test_exclude_paths(self):
        responses = [
            {"code": 0, "message": "ok", "data": {"id": 1}},
            {"code": 0, "message": "ok", "data": {"id": 2}},
        ]
        schema = SchemaInferrer.infer(responses)
        assertions = SchemaInferrer.generate_assertions(
            schema, exclude_paths=["body.data", "body.data.id"]
        )

        # 排除的路径不应该出现在断言中
        for a in assertions:
            assert not a.path.startswith("body.data")

    def test_generates_type_assertions(self):
        responses = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]
        schema = SchemaInferrer.infer(responses)
        assertions = SchemaInferrer.generate_assertions(schema)

        type_assertions = {a.path: a for a in assertions if a.operator == "type"}
        assert "body.name" in type_assertions
        assert type_assertions["body.name"].expected == "str"
        assert "body.age" in type_assertions
        assert type_assertions["body.age"].expected == "int"


# ==================== 变更检测测试 ====================


class TestChangeDetector:
    def test_no_changes_for_matching_response(self):
        responses = [
            {"code": 0, "message": "ok", "data": {"id": 1}},
            {"code": 0, "message": "ok", "data": {"id": 2}},
        ]
        schema = SchemaInferrer.infer(responses)
        report = ChangeDetector.detect(schema, {"code": 0, "message": "ok", "data": {"id": 3}})
        assert report.has_errors is False

    def test_detects_new_field(self):
        responses = [
            {"code": 0, "message": "ok"},
            {"code": 0, "message": "ok"},
        ]
        schema = SchemaInferrer.infer(responses)
        report = ChangeDetector.detect(schema, {"code": 0, "message": "ok", "new_field": "unexpected"})
        new_changes = [c for c in report.changes if c.change_type == "new_field"]
        assert len(new_changes) >= 1

    def test_detects_missing_required_field(self):
        responses = [
            {"code": 0, "message": "ok"},
            {"code": 0, "message": "ok"},
        ]
        schema = SchemaInferrer.infer(responses)
        report = ChangeDetector.detect(schema, {"code": 0})
        # message 是必填的（出现率 100%），缺失应报告
        missing = [c for c in report.changes if c.path == "body.message"]
        assert len(missing) > 0
        assert missing[0].severity in ("error", "warning")

    def test_detects_type_change(self):
        responses = [
            {"code": 0},
            {"code": 0},
            {"code": 0},
        ]
        schema = SchemaInferrer.infer(responses)
        report = ChangeDetector.detect(schema, {"code": "not_a_number"})
        type_changes = [c for c in report.changes if c.change_type == "type_changed"]
        assert len(type_changes) >= 1

    def test_detects_required_field_null(self):
        responses = [
            {"name": "Alice"},
            {"name": "Bob"},
        ]
        schema = SchemaInferrer.infer(responses)
        report = ChangeDetector.detect(schema, {"name": None})
        null_changes = [c for c in report.changes if c.change_type == "null_required"]
        assert len(null_changes) >= 1

    def test_non_dict_body(self):
        responses = [{"key": "val"}]
        schema = SchemaInferrer.infer(responses)
        report = ChangeDetector.detect(schema, "not a dict")  # type: ignore[arg-type]
        assert report.has_errors is True


# ==================== 集成：完整流程测试 ====================


class TestEndToEnd:
    """模拟真实场景：从多次成功响应 → 推断 → 生成断言 → 检测变更"""

    def test_stable_api_scenario(self):
        """稳定接口：多次执行响应结构一致"""
        responses = [
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "Alice",
                    "email": "alice@example.com",
                    "age": 25,
                },
            },
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": "660e8400-e29b-41d4-a716-446655440001",
                    "name": "Bob",
                    "email": "bob@example.com",
                    "age": 30,
                },
            },
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": "770e8400-e29b-41d4-a716-446655440002",
                    "name": "Charlie",
                    "email": "charlie@example.com",
                    "age": 28,
                },
            },
        ]

        # Step 1: 推断 Schema
        schema = SchemaInferrer.infer(responses, case_name="user_api")
        assert schema.case_name == "user_api"
        assert schema.sample_count == 3
        assert "body.data.id" in schema.fields
        assert "body.data.email" in schema.fields
        assert "body.data.age" in schema.fields

        # 验证 email 模式被检测
        email_field = schema.fields.get("body.data.email")
        assert email_field is not None
        assert email_field.value_pattern == "email"

        # 验证 id 模式（UUID）
        id_field = schema.fields.get("body.data.id")
        assert id_field is not None
        assert id_field.value_pattern == "uuid"

        # Step 2: 生成断言
        assertions = SchemaInferrer.generate_assertions(schema)
        assert len(assertions) >= 6  # status_code + 5+ field assertions

        # 验证生成的断言可以覆盖基础断言
        assertion_paths = {a.path for a in assertions}
        assert "status_code" in assertion_paths
        assert "body.code" in assertion_paths

        # Step 3: 对相同结构的响应检测变更 — 应该无错误
        new_response = {
            "code": 0,
            "message": "success",
            "data": {
                "id": "880e8400-e29b-41d4-a716-446655440003",
                "name": "Diana",
                "email": "diana@example.com",
                "age": 35,
            },
        }
        report = ChangeDetector.detect(schema, new_response)
        assert report.has_errors is False, f"Unexpected errors: {report.changes}"

    def test_schema_to_dict_serialization(self):
        """验证 Schema 可以正确序列化"""
        responses = [{"code": 0, "message": "ok"}]
        schema = SchemaInferrer.infer(responses, case_id="test-id-123")
        d = schema.to_dict()
        assert d["case_id"] == "test-id-123"
        assert d["sample_count"] == 1
        assert "body.code" in d["fields"]
        assert "body.message" in d["fields"]

    def test_boolean_field_correct_handling(self):
        """验证布尔值不会被误判为 int"""
        responses = [
            {"success": True, "active": False},
            {"success": False, "active": True},
        ]
        schema = SchemaInferrer.infer(responses)
        success_field = schema.fields.get("body.success")
        assert success_field is not None
        # 布尔值在 JSON 中通过 isinstance 检测为 bool，不会误判为 int
        assert "bool" in success_field.types
