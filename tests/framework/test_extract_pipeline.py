"""提取器管道单元测试 (T5-06)

测试覆盖：
- ExtractStep 数据模型
- ExtractStepType 枚举
- ExtractPipeline 基本流程（单步 / 多步链式）
- 5 种步骤类型（jsonpath / regex / base64_decode / base64_encode / json_parse）
- 管道错误处理（jsonpath 无匹配 / regex 无匹配 / base64 解码失败 / json 解析失败）
- 管道空 steps 抛出异常
- ExtractPipelineError 异常信息（step_index / step_type / expression）
- Extractor 集成 pipeline source_type
- 向后兼容：非 pipeline 提取行为不变
"""

from __future__ import annotations

import base64
import json

import pytest

from framework.exceptions import ExtractorError
from framework.extract_pipeline import (
    ExtractPipeline,
    ExtractPipelineError,
    ExtractStep,
    ExtractStepType,
)
from framework.extractor import Extractor
from framework.models import ExtractItem, HttpResponse


# ── 辅助工厂 ──────────────────────────────────────────────


def make_response(body: dict | list | str | None = None) -> HttpResponse:
    """创建测试用 HttpResponse."""
    if body is None:
        body = {}
    return HttpResponse(
        status_code=200,
        headers={"Content-Type": "application/json"},
        body=body,
        elapsed_ms=100.0,
        size_bytes=1024,
        url="http://test.local/api",
    )


# ── ExtractStepType 枚举测试 ───────────────────────────────


class TestExtractStepType:
    """ExtractStepType 枚举测试."""

    def test_all_five_types_defined(self) -> None:
        """5 种步骤类型都已定义."""
        assert ExtractStepType.JSONPATH == "jsonpath"
        assert ExtractStepType.REGEX == "regex"
        assert ExtractStepType.BASE64_DECODE == "base64_decode"
        assert ExtractStepType.BASE64_ENCODE == "base64_encode"
        assert ExtractStepType.JSON_PARSE == "json_parse"

    def test_enum_is_string_enum(self) -> None:
        """枚举值是 str 类型."""
        assert isinstance(ExtractStepType.JSONPATH, str)


# ── ExtractStep 数据模型测试 ───────────────────────────────


class TestExtractStep:
    """ExtractStep 数据模型测试."""

    def test_default_values(self) -> None:
        """默认值：expression="" group=1."""
        step = ExtractStep(type=ExtractStepType.JSONPATH)
        assert step.type == ExtractStepType.JSONPATH
        assert step.expression == ""
        assert step.group == 1

    def test_with_expression(self) -> None:
        """带 expression."""
        step = ExtractStep(type=ExtractStepType.JSONPATH, expression="$.data.token")
        assert step.expression == "$.data.token"

    def test_with_custom_group(self) -> None:
        """自定义 regex 捕获组."""
        step = ExtractStep(type=ExtractStepType.REGEX, expression=r"(\d+)", group=2)
        assert step.group == 2


# ── ExtractPipeline 基本流程测试 ───────────────────────────


class TestExtractPipelineBasic:
    """ExtractPipeline 基本流程测试."""

    def test_single_jsonpath_step(self) -> None:
        """单步 jsonpath 提取."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSONPATH, expression="$.data.name"),
        ])
        result = pipeline.execute({"data": {"name": "hello"}})
        assert result == "hello"

    def test_two_step_chain(self) -> None:
        """两步链式：jsonpath → regex."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSONPATH, expression="$.data.url"),
            ExtractStep(type=ExtractStepType.REGEX, expression=r"/api/(.+)"),
        ])
        result = pipeline.execute({"data": {"url": "https://example.com/api/users/123"}})
        assert result == "users/123"

    def test_three_step_chain(self) -> None:
        """三步链式：jsonpath → regex → base64_encode."""
        token = "my-secret-token"
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSONPATH, expression="$.data.token"),
            ExtractStep(type=ExtractStepType.REGEX, expression=r"my-(.+)"),
            ExtractStep(type=ExtractStepType.BASE64_ENCODE),
        ])
        result = pipeline.execute({"data": {"token": token}})
        expected = base64.b64encode(b"secret-token").decode("ascii")
        assert result == expected

    def test_empty_steps_raises(self) -> None:
        """空 steps 列表抛出 ValueError."""
        with pytest.raises(ValueError, match="不能为空"):
            ExtractPipeline(steps=[])


# ── jsonpath 步骤测试 ──────────────────────────────────────


class TestJsonpathStep:
    """jsonpath 步骤测试."""

    def test_extract_string(self) -> None:
        """提取字符串."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSONPATH, expression="$.msg"),
        ])
        assert pipeline.execute({"msg": "ok"}) == "ok"

    def test_extract_number_preserves_type(self) -> None:
        """提取数字 → 保持数字类型."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSONPATH, expression="$.code"),
        ])
        result = pipeline.execute({"code": 200})
        assert result == 200

    def test_extract_nested(self) -> None:
        """提取嵌套字段."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSONPATH, expression="$.data.user.id"),
        ])
        result = pipeline.execute({"data": {"user": {"id": 42}}})
        assert result == 42

    def test_extract_list_item(self) -> None:
        """提取列表元素."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSONPATH, expression="$.items[0].name"),
        ])
        result = pipeline.execute({"items": [{"name": "first"}, {"name": "second"}]})
        assert result == "first"

    def test_no_match_raises(self) -> None:
        """无匹配抛出 ExtractPipelineError."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSONPATH, expression="$.nonexistent"),
        ])
        with pytest.raises(ExtractPipelineError, match="未匹配"):
            pipeline.execute({"data": {}})

    def test_no_match_error_has_step_info(self) -> None:
        """无匹配异常包含步骤信息."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSONPATH, expression="$.bad.path"),
        ])
        with pytest.raises(ExtractPipelineError) as exc_info:
            pipeline.execute({})
        assert exc_info.value.step_index == 0
        assert exc_info.value.step_type == "jsonpath"
        assert exc_info.value.expression == "$.bad.path"


# ── regex 步骤测试 ─────────────────────────────────────────


class TestRegexStep:
    """regex 步骤测试."""

    def test_extract_with_capture_group(self) -> None:
        """带捕获组提取."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.REGEX, expression=r'"token":"([^"]+)"', group=1),
        ])
        result = pipeline.execute('{"token":"abc123","other":"x"}')
        assert result == "abc123"

    def test_extract_full_match(self) -> None:
        """完整匹配（group=0）."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.REGEX, expression=r"\d+", group=0),
        ])
        result = pipeline.execute("code: 200")
        assert result == "200"

    def test_no_match_raises(self) -> None:
        """无匹配抛出 ExtractPipelineError."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.REGEX, expression=r"NOT_FOUND"),
        ])
        with pytest.raises(ExtractPipelineError, match="未匹配"):
            pipeline.execute("some text")

    def test_group_out_of_range_falls_back_to_full(self) -> None:
        """捕获组索引超出范围时回退到完整匹配."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.REGEX, expression=r"(\d+)", group=99),
        ])
        # 只有 1 个捕获组，group=99 不存在，回退到 group(0)
        result = pipeline.execute("code: 200")
        assert result == "200"


# ── base64 步骤测试 ────────────────────────────────────────


class TestBase64Step:
    """base64 编解码步骤测试."""

    def test_decode(self) -> None:
        """base64 解码."""
        encoded = base64.b64encode(b"hello world").decode("ascii")
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.BASE64_DECODE),
        ])
        result = pipeline.execute(encoded)
        assert result == "hello world"

    def test_encode(self) -> None:
        """base64 编码."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.BASE64_ENCODE),
        ])
        result = pipeline.execute("hello world")
        assert result == base64.b64encode(b"hello world").decode("ascii")

    def test_decode_invalid_raises(self) -> None:
        """无效 base64 抛出 ExtractPipelineError."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.BASE64_DECODE),
        ])
        with pytest.raises(ExtractPipelineError, match="Base64 解码失败"):
            pipeline.execute("!!!not-valid-base64!!!")

    def test_encode_decode_roundtrip(self) -> None:
        """编解码往返."""
        original = "test-data-123"
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.BASE64_ENCODE),
            ExtractStep(type=ExtractStepType.BASE64_DECODE),
        ])
        result = pipeline.execute(original)
        assert result == original

    def test_decode_bytes_input(self) -> None:
        """bytes 输入解码."""
        encoded_bytes = base64.b64encode(b"bytes-test")
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.BASE64_DECODE),
        ])
        result = pipeline.execute(encoded_bytes)
        assert result == "bytes-test"


# ── json_parse 步骤测试 ────────────────────────────────────


class TestJsonParseStep:
    """json_parse 步骤测试."""

    def test_parse_json_string(self) -> None:
        """解析 JSON 字符串."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSON_PARSE),
        ])
        result = pipeline.execute('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_already_dict_passthrough(self) -> None:
        """已是 dict 则透传."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSON_PARSE),
        ])
        result = pipeline.execute({"already": "dict"})
        assert result == {"already": "dict"}

    def test_parse_already_list_passthrough(self) -> None:
        """已是 list 则透传."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSON_PARSE),
        ])
        result = pipeline.execute([1, 2, 3])
        assert result == [1, 2, 3]

    def test_parse_invalid_json_raises(self) -> None:
        """无效 JSON 抛出 ExtractPipelineError."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSON_PARSE),
        ])
        with pytest.raises(ExtractPipelineError, match="JSON 解析失败"):
            pipeline.execute("not json")

    def test_chain_jsonpath_json_parse(self) -> None:
        """链式：jsonpath → json_parse."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSONPATH, expression="$.data.nested"),
            ExtractStep(type=ExtractStepType.JSON_PARSE),
        ])
        result = pipeline.execute({"data": {"nested": '{"inner": "value"}'}})
        assert isinstance(result, dict)
        assert result == {"inner": "value"}


# ── 组合链式场景测试 ──────────────────────────────────────


class TestChainScenarios:
    """真实场景的链式提取测试."""

    def test_jwt_token_decode(self) -> None:
        """模拟 JWT payload 提取：jsonpath → regex → base64_decode → json_parse."""
        payload = {"sub": "user123", "role": "admin"}
        payload_json = json.dumps(payload)
        payload_b64 = base64.b64encode(payload_json.encode()).decode()
        # 模拟 JWT: header.payload.signature
        jwt_body = {"data": {"auth": f"Bearer eyJ.{payload_b64}.sig"}}

        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSONPATH, expression="$.data.auth"),
            ExtractStep(type=ExtractStepType.REGEX, expression=r"\.(.+?)\."),
            ExtractStep(type=ExtractStepType.BASE64_DECODE),
            ExtractStep(type=ExtractStepType.JSON_PARSE),
        ])
        result = pipeline.execute(jwt_body)
        assert result == payload

    def test_error_in_middle_step(self) -> None:
        """管道中间步骤失败时 step_index 正确."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSONPATH, expression="$.data.value"),
            ExtractStep(type=ExtractStepType.REGEX, expression=r"WILL_NOT_MATCH"),
            ExtractStep(type=ExtractStepType.BASE64_ENCODE),
        ])
        with pytest.raises(ExtractPipelineError) as exc_info:
            pipeline.execute({"data": {"value": "some text"}})
        assert exc_info.value.step_index == 1  # 第二步失败

    def test_string_source_direct(self) -> None:
        """字符串直接作为 pipeline 输入（非 dict）."""
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.REGEX, expression=r"code: (\d+)"),
        ])
        result = pipeline.execute("response code: 200 OK")
        assert result == "200"


# ── Extractor 集成 pipeline 测试 ──────────────────────────


class TestExtractorPipelineIntegration:
    """Extractor 类集成 pipeline source_type 测试."""

    def test_pipeline_source_type(self) -> None:
        """source_type="pipeline" 通过管道提取."""
        extractor = Extractor()
        response = make_response(body={
            "data": {
                "token": base64.b64encode(b"secret-value").decode("ascii"),
            },
        })
        item = ExtractItem(
            var_name="decoded_token",
            source="pipeline",
            source_type="pipeline",
            pipeline=[
                {"type": "jsonpath", "expression": "$.data.token"},
                {"type": "base64_decode"},
            ],
        )
        results = extractor.extract(response, [item])
        assert results["decoded_token"] == "secret-value"

    def test_pipeline_with_default_on_failure(self) -> None:
        """管道失败但有 default 值时使用默认值."""
        extractor = Extractor()
        response = make_response(body={"data": {}})
        item = ExtractItem(
            var_name="token",
            source="pipeline",
            source_type="pipeline",
            default="fallback_token",
            pipeline=[
                {"type": "jsonpath", "expression": "$.nonexistent"},
            ],
        )
        results = extractor.extract(response, [item])
        assert results["token"] == "fallback_token"

    def test_pipeline_without_default_raises(self) -> None:
        """管道失败且无 default 时抛出 ExtractorError."""
        extractor = Extractor()
        response = make_response(body={"data": {}})
        item = ExtractItem(
            var_name="token",
            source="pipeline",
            source_type="pipeline",
            pipeline=[
                {"type": "jsonpath", "expression": "$.nonexistent"},
            ],
        )
        with pytest.raises(ExtractorError, match="管道提取"):
            extractor.extract(response, [item])

    def test_empty_pipeline_raises(self) -> None:
        """空 pipeline 抛出 ExtractPipelineError."""
        extractor = Extractor()
        response = make_response()
        item = ExtractItem(
            var_name="x",
            source="pipeline",
            source_type="pipeline",
            pipeline=[],
        )
        with pytest.raises(ExtractorError, match="管道提取"):
            extractor.extract(response, [item])

    def test_mixed_pipeline_and_normal_extracts(self) -> None:
        """混合 pipeline 和普通提取."""
        extractor = Extractor()
        response = make_response(body={
            "code": 0,
            "data": {
                "encoded": base64.b64encode(b"hello").decode("ascii"),
            },
        })
        items = [
            ExtractItem(var_name="code", source="$.code", source_type="jsonpath"),
            ExtractItem(
                var_name="decoded",
                source="pipeline",
                source_type="pipeline",
                pipeline=[
                    {"type": "jsonpath", "expression": "$.data.encoded"},
                    {"type": "base64_decode"},
                ],
            ),
        ]
        results = extractor.extract(response, items)
        assert results["code"] == 0
        assert results["decoded"] == "hello"

    def test_backward_compatible_non_pipeline(self) -> None:
        """向后兼容：非 pipeline 提取行为不变."""
        extractor = Extractor()
        response = make_response(body={"status": "ok", "count": 42})
        items = [
            ExtractItem(var_name="status", source="$.status", source_type="jsonpath"),
            ExtractItem(var_name="count", source="$.count", source_type="jsonpath"),
        ]
        results = extractor.extract(response, items)
        assert results["status"] == "ok"
        assert results["count"] == 42
