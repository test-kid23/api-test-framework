"""Extractor 变量提取器测试套件

覆盖：
1. 6 种 source_type：jsonpath / header / body_regex / status_code / elapsed / sql_column
2. 自动类型推断（auto-inference）
3. 默认值回退（default fallback）
4. ExtractorError 异常（继承自 AutoTestException）
5. extract_from_db 数据库结果提取
6. 边界情况
"""

from __future__ import annotations

import pytest

from framework.exceptions import AutoTestException, ExtractorError
from framework.extractor import Extractor
from framework.models import ExtractItem, HttpResponse


# ══════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════


@pytest.fixture
def extractor() -> Extractor:
    return Extractor()


@pytest.fixture
def response() -> HttpResponse:
    return HttpResponse(
        status_code=200,
        headers={
            "Content-Type": "application/json",
            "X-Request-Id": "req-abc-123",
        },
        body={
            "code": 0,
            "message": "success",
            "data": {
                "token": "jwt-token-value",
                "user": {"id": 42, "name": "Alice"},
                "items": [{"id": 1}, {"id": 2}, {"id": 3}],
            },
        },
        elapsed_ms=150.5,
        size_bytes=2048,
        url="http://test/api",
    )


def make_item(
    var_name: str,
    source: str,
    source_type: str = "jsonpath",
    default: object = None,
) -> ExtractItem:
    return ExtractItem(var_name=var_name, source=source, source_type=source_type, default=default)


# ══════════════════════════════════════════════════════════
# 1. jsonpath 提取
# ══════════════════════════════════════════════════════════


class TestJsonPathExtraction:
    """验证 JSONPath 提取功能"""

    def test_extract_simple_field(self, extractor: Extractor, response: HttpResponse) -> None:
        item = make_item("msg", "$.message", "jsonpath")
        result = extractor.extract(response, [item])
        assert result["msg"] == "success"

    def test_extract_nested_field(self, extractor: Extractor, response: HttpResponse) -> None:
        item = make_item("token", "$.data.token", "jsonpath")
        result = extractor.extract(response, [item])
        assert result["token"] == "jwt-token-value"

    def test_extract_deep_nested(self, extractor: Extractor, response: HttpResponse) -> None:
        item = make_item("user_name", "$.data.user.name", "jsonpath")
        result = extractor.extract(response, [item])
        assert result["user_name"] == "Alice"

    def test_extract_list_item(self, extractor: Extractor, response: HttpResponse) -> None:
        item = make_item("first_item_id", "$.data.items[0].id", "jsonpath")
        result = extractor.extract(response, [item])
        assert result["first_item_id"] == 1

    def test_extract_nonexistent_path(self, extractor: Extractor, response: HttpResponse) -> None:
        item = make_item("missing", "$.nonexistent.path", "jsonpath")
        result = extractor.extract(response, [item])
        # None 值不加入结果
        assert "missing" not in result

    def test_extract_nonexistent_with_default(self, extractor: Extractor, response: HttpResponse) -> None:
        item = ExtractItem(var_name="missing", source="$.nonexistent.path", source_type="jsonpath", default="fallback")
        result = extractor.extract(response, [item])
        assert result["missing"] == "fallback"

    def test_multiple_jsonpath_extracts(self, extractor: Extractor, response: HttpResponse) -> None:
        items = [
            make_item("code", "$.code", "jsonpath"),
            make_item("token", "$.data.token", "jsonpath"),
            make_item("user_id", "$.data.user.id", "jsonpath"),
        ]
        result = extractor.extract(response, items)
        assert result["code"] == 0
        assert result["token"] == "jwt-token-value"
        assert result["user_id"] == 42


# ══════════════════════════════════════════════════════════
# 2. header 提取
# ══════════════════════════════════════════════════════════


class TestHeaderExtraction:
    """验证响应头提取（大小写不敏感）"""

    def test_extract_header_exact_case(self, extractor: Extractor, response: HttpResponse) -> None:
        item = make_item("content_type", "Content-Type", "header")
        result = extractor.extract(response, [item])
        assert result["content_type"] == "application/json"

    def test_extract_header_lowercase(self, extractor: Extractor, response: HttpResponse) -> None:
        item = make_item("ctype", "content-type", "header")
        result = extractor.extract(response, [item])
        assert result["ctype"] == "application/json"

    def test_extract_header_uppercase(self, extractor: Extractor, response: HttpResponse) -> None:
        item = make_item("ctype", "CONTENT-TYPE", "header")
        result = extractor.extract(response, [item])
        assert result["ctype"] == "application/json"

    def test_extract_header_mixed_case(self, extractor: Extractor, response: HttpResponse) -> None:
        item = make_item("req_id", "x-request-id", "header")
        result = extractor.extract(response, [item])
        assert result["req_id"] == "req-abc-123"

    def test_extract_nonexistent_header(self, extractor: Extractor, response: HttpResponse) -> None:
        item = make_item("missing", "X-Not-Exists", "header")
        result = extractor.extract(response, [item])
        assert "missing" not in result

    def test_extract_nonexistent_header_with_default(self, extractor: Extractor, response: HttpResponse) -> None:
        item = ExtractItem(var_name="missing", source="X-Not-Exists", source_type="header", default="n/a")
        result = extractor.extract(response, [item])
        assert result["missing"] == "n/a"


# ══════════════════════════════════════════════════════════
# 3. body_regex 提取
# ══════════════════════════════════════════════════════════


class TestBodyRegexExtraction:
    """验证正则提取"""

    def test_extract_regex_with_capture_group(self, extractor: Extractor) -> None:
        response = HttpResponse(
            status_code=200,
            headers={},
            body='{"token": "abc-def-123", "type": "bearer"}',
            elapsed_ms=100,
            size_bytes=100,
            url="http://test",
        )
        item = make_item("token_value", r'"token":\s*"([^"]+)"', "body_regex")
        result = extractor.extract(response, [item])
        assert result["token_value"] == "abc-def-123"

    def test_extract_regex_no_capture_group(self, extractor: Extractor) -> None:
        response = HttpResponse(
            status_code=200,
            headers={},
            body="Response contains ERROR_CODE_42",
            elapsed_ms=100,
            size_bytes=100,
            url="http://test",
        )
        item = make_item("error_code", r"ERROR_CODE_\d+", "body_regex")
        result = extractor.extract(response, [item])
        assert result["error_code"] == "ERROR_CODE_42"

    def test_extract_regex_no_match(self, extractor: Extractor) -> None:
        response = HttpResponse(
            status_code=200,
            headers={},
            body="no match here",
            elapsed_ms=100,
            size_bytes=100,
            url="http://test",
        )
        item = make_item("nothing", r"not_found_\d+", "body_regex")
        result = extractor.extract(response, [item])
        assert "nothing" not in result

    def test_extract_regex_no_match_with_default(self, extractor: Extractor) -> None:
        response = HttpResponse(
            status_code=200,
            headers={},
            body="no match here",
            elapsed_ms=100,
            size_bytes=100,
            url="http://test",
        )
        item = ExtractItem(
            var_name="val",
            source=r"not_found_\d+",
            source_type="body_regex",
            default="default_val",
        )
        result = extractor.extract(response, [item])
        assert result["val"] == "default_val"

    def test_extract_regex_from_dict_body(self, extractor: Extractor) -> None:
        """body 为 dict 时会自动 str() 转换"""
        response = HttpResponse(
            status_code=200,
            headers={},
            body={"token": "xyz-999"},
            elapsed_ms=100,
            size_bytes=100,
            url="http://test",
        )
        item = make_item("tok", r"xyz-\d+", "body_regex")
        result = extractor.extract(response, [item])
        assert result["tok"] == "xyz-999"


# ══════════════════════════════════════════════════════════
# 4. status_code 提取
# ══════════════════════════════════════════════════════════


class TestStatusCodeExtraction:
    """验证状态码提取"""

    def test_extract_status_code_200(self, extractor: Extractor, response: HttpResponse) -> None:
        item = make_item("sc", "", "status_code")
        result = extractor.extract(response, [item])
        assert result["sc"] == 200

    def test_extract_status_code_404(self, extractor: Extractor) -> None:
        response = HttpResponse(
            status_code=404,
            headers={},
            body={},
            elapsed_ms=100,
            size_bytes=100,
            url="http://test",
        )
        item = make_item("sc", "", "status_code")
        result = extractor.extract(response, [item])
        assert result["sc"] == 404

    def test_extract_status_code_500(self, extractor: Extractor) -> None:
        response = HttpResponse(
            status_code=500,
            headers={},
            body={},
            elapsed_ms=100,
            size_bytes=100,
            url="http://test",
        )
        item = make_item("sc", "", "status_code")
        result = extractor.extract(response, [item])
        assert result["sc"] == 500


# ══════════════════════════════════════════════════════════
# 5. elapsed 提取
# ══════════════════════════════════════════════════════════


class TestElapsedExtraction:
    """验证响应时间提取"""

    def test_extract_elapsed(self, extractor: Extractor, response: HttpResponse) -> None:
        item = make_item("resp_time", "", "elapsed")
        result = extractor.extract(response, [item])
        assert result["resp_time"] == 150.5

    def test_extract_elapsed_zero(self, extractor: Extractor) -> None:
        response = HttpResponse(
            status_code=200,
            headers={},
            body={},
            elapsed_ms=0.0,
            size_bytes=100,
            url="http://test",
        )
        item = make_item("rt", "", "elapsed")
        result = extractor.extract(response, [item])
        assert result["rt"] == 0.0


# ══════════════════════════════════════════════════════════
# 6. sql_column 提取 (extract_from_db)
# ══════════════════════════════════════════════════════════


class TestDBExtraction:
    """验证数据库结果提取"""

    def test_extract_from_single_row_dict(self, extractor: Extractor) -> None:
        rows: dict[str, object] = {"id": 1, "name": "Alice", "email": "alice@test.com"}
        items = [make_item("user_name", "name", "sql_column")]
        result = extractor.extract_from_db(rows, items)
        assert result["user_name"] == "Alice"

    def test_extract_from_list_of_rows(self, extractor: Extractor) -> None:
        rows: list[dict[str, object]] = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        items = [make_item("first_name", "name", "sql_column")]
        result = extractor.extract_from_db(rows, items)
        # 取第一行
        assert result["first_name"] == "Alice"

    def test_extract_multiple_columns(self, extractor: Extractor) -> None:
        rows: dict[str, object] = {"id": 42, "token": "abc", "status": "active"}
        items = [
            make_item("uid", "id", "sql_column"),
            make_item("tok", "token", "sql_column"),
        ]
        result = extractor.extract_from_db(rows, items)
        assert result["uid"] == 42
        assert result["tok"] == "abc"

    def test_extract_nonexistent_column(self, extractor: Extractor) -> None:
        rows: dict[str, object] = {"id": 1}
        items = [make_item("missing_col", "nonexistent", "sql_column")]
        result = extractor.extract_from_db(rows, items)
        assert "missing_col" not in result

    def test_extract_nonexistent_column_with_default(self, extractor: Extractor) -> None:
        rows: dict[str, object] = {"id": 1}
        item = ExtractItem(var_name="missing_col", source="nonexistent", source_type="sql_column", default="N/A")
        result = extractor.extract_from_db(rows, [item])
        assert result["missing_col"] == "N/A"

    def test_extract_from_none_rows(self, extractor: Extractor) -> None:
        items = [make_item("any", "col", "sql_column")]
        result = extractor.extract_from_db(None, items)
        assert result == {}

    def test_extract_from_empty_list(self, extractor: Extractor) -> None:
        items = [make_item("any", "col", "sql_column")]
        result = extractor.extract_from_db([], items)
        assert result == {}


# ══════════════════════════════════════════════════════════
# 7. 自动类型推断
# ══════════════════════════════════════════════════════════


class TestAutoInference:
    """验证 source_type 自动推断"""

    def test_infer_jsonpath_from_dollar_prefix(self, extractor: Extractor, response: HttpResponse) -> None:
        """$. 前缀自动推断为 jsonpath"""
        item = ExtractItem(var_name="tok", source="$.data.token")  # source_type 使用默认值 jsonpath
        result = extractor.extract(response, [item])
        assert result["tok"] == "jwt-token-value"

    def test_infer_jsonpath_when_no_source_type(self, extractor: Extractor, response: HttpResponse) -> None:
        """无 source_type + $. 前缀 → jsonpath"""
        # _extract_single 中 else 分支：$. 前缀 → jsonpath
        item = ExtractItem(var_name="msg", source="$.message")
        result = extractor.extract(response, [item])
        assert result["msg"] == "success"

    def test_infer_header_from_prefix(self, extractor: Extractor, response: HttpResponse) -> None:
        """header. 前缀自动推断为 header，strip 'header.'"""
        # _extract_single 中 else 分支：source.startswith("header.") → header
        # 需要 source_type 为空或不识别，才触发自动推断
        item = ExtractItem(var_name="ctype", source="header.Content-Type", source_type="")
        result = extractor.extract(response, [item])
        assert result["ctype"] == "application/json"

    def test_unknown_source_type_falls_to_jsonpath(self, extractor: Extractor, response: HttpResponse) -> None:
        """未知 source_type → 进入 else 分支尝试 jsonpath"""
        item = ExtractItem(var_name="code", source="$.code", source_type="unknown_type")
        result = extractor.extract(response, [item])
        assert result["code"] == 0


# ══════════════════════════════════════════════════════════
# 8. 默认值回退
# ══════════════════════════════════════════════════════════


class TestDefaultFallback:
    """验证默认值回退机制"""

    def test_default_on_none_result(self, extractor: Extractor, response: HttpResponse) -> None:
        """提取返回 None + 有 default → 使用 default"""
        item = ExtractItem(var_name="missing", source="$.not.exist", source_type="jsonpath", default="fallback_val")
        result = extractor.extract(response, [item])
        assert result["missing"] == "fallback_val"

    def test_default_on_exception(self, extractor: Extractor, response: HttpResponse) -> None:
        """提取异常 + 有 default → 使用 default（不抛异常）"""
        # 使用无效正则造成异常
        item = ExtractItem(var_name="val", source=r"[invalid", source_type="body_regex", default="safe")
        result = extractor.extract(response, [item])
        assert result["val"] == "safe"

    def test_no_default_on_none_result(self, extractor: Extractor, response: HttpResponse) -> None:
        """提取返回 None + 无 default → 不加入结果"""
        item = make_item("missing", "$.not.exist", "jsonpath")
        result = extractor.extract(response, [item])
        assert "missing" not in result

    def test_extract_error_on_exception_without_default(self, extractor: Extractor) -> None:
        """提取异常 + 无 default → 抛出 ExtractorError"""
        response = HttpResponse(
            status_code=200,
            headers={},
            body='{"data": "test"}',
            elapsed_ms=100,
            size_bytes=100,
            url="http://test",
        )
        # 使用无效正则触发 re.error
        item = ExtractItem(var_name="val", source=r"[bad_regex", source_type="body_regex")
        with pytest.raises(ExtractorError) as exc_info:
            extractor.extract(response, [item])
        assert "val" in str(exc_info.value)


# ══════════════════════════════════════════════════════════
# 9. 组合提取 & 边界情况
# ══════════════════════════════════════════════════════════


class TestCombinedAndEdgeCases:
    """组合提取与边界情况"""

    def test_combined_multiple_source_types(self, extractor: Extractor, response: HttpResponse) -> None:
        """同时使用多种 source_type 提取"""
        items = [
            make_item("sc", "", "status_code"),
            make_item("rt", "", "elapsed"),
            make_item("ctype", "Content-Type", "header"),
            make_item("token", "$.data.token", "jsonpath"),
        ]
        result = extractor.extract(response, items)
        assert result["sc"] == 200
        assert result["rt"] == 150.5
        assert result["ctype"] == "application/json"
        assert result["token"] == "jwt-token-value"
        assert len(result) == 4

    def test_empty_extracts_list(self, extractor: Extractor, response: HttpResponse) -> None:
        result = extractor.extract(response, [])
        assert result == {}

    def test_empty_extracts_list_from_db(self, extractor: Extractor) -> None:
        result = extractor.extract_from_db({"a": 1}, [])
        assert result == {}

    def test_sql_column_with_exception_and_default(self, extractor: Extractor) -> None:
        """extract_from_db 中异常 + default → 使用 default"""
        item = ExtractItem(var_name="safe", source="col", source_type="sql_column", default="safe_val")
        # 传入不支持的 rows 类型来触发异常
        result = extractor.extract_from_db("invalid_type", [item])
        assert result["safe"] == "safe_val"

    def test_extract_none_status_code_with_default(self, extractor: Extractor, response: HttpResponse) -> None:
        """status_code 永远有值，此测试验证 default 在正常场景下不被使用"""
        item = ExtractItem(var_name="sc", source="", source_type="status_code", default=999)
        result = extractor.extract(response, [item])
        # status_code 被成功提取，不使用 default
        assert result["sc"] == 200


# ══════════════════════════════════════════════════════════
# 10. ExtractError 异常验证
# ══════════════════════════════════════════════════════════


class TestExtractError:
    """验证 ExtractorError 异常类（继承自 AutoTestException）"""

    def test_extract_error_inherits_from_autotest_exception(self) -> None:
        """ExtractorError 应是 AutoTestException 子类"""
        assert issubclass(ExtractorError, AutoTestException)

    def test_extract_error_message(self) -> None:
        err = ExtractorError("变量提取失败: key not found")
        assert "变量提取失败" in str(err)
        assert "key not found" in str(err)

    def test_extract_error_with_cause(self) -> None:
        """ExtractorError 支持异常链"""
        try:
            raise ValueError("original error")
        except ValueError as cause:
            err = ExtractorError("提取失败: token")
            err.__cause__ = cause
            assert err.__cause__ is not None
