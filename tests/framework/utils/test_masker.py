"""Tests for framework.utils.masker — 敏感数据脱敏模块单元测试

覆盖所有内置规则、自定义字段、边界条件和 Logger 集成。
"""

from __future__ import annotations

import pytest

from framework.utils.masker import SensitiveDataMasker

# ==================== Fixtures ====================


@pytest.fixture
def masker() -> SensitiveDataMasker:
    """默认脱敏器（无额外字段）"""
    return SensitiveDataMasker()


@pytest.fixture
def masker_with_extra() -> SensitiveDataMasker:
    """带自定义额外字段的脱敏器"""
    return SensitiveDataMasker(extra_fields=["x-custom-key", "private_data"])


# ==================== mask_dict — 基本功能 ====================


class TestMaskDictBasic:
    """mask_dict 基本功能测试"""

    def test_mask_flat_dict_sensitive_key(self, masker: SensitiveDataMasker) -> None:
        """扁平字典中敏感字段的值应被替换"""
        data = {
            "Authorization": "Bearer abc123xyz",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        result = masker.mask_dict(data)
        assert result["Authorization"] == "******"
        assert result["Content-Type"] == "application/json"
        assert result["Accept"] == "application/json"

    def test_mask_case_insensitive(self, masker: SensitiveDataMasker) -> None:
        """敏感字段匹配应大小写不敏感"""
        cases: list[dict[str, str]] = [
            {"authorization": "secret1"},
            {"AUTHORIZATION": "secret2"},
            {"Authorization": "secret3"},
            {"AuThOrIzAtIoN": "secret4"},
        ]
        for data in cases:
            result = masker.mask_dict(data)
            key = next(iter(data))
            assert result[key] == "******", f"大小写匹配失败: {key}"

    def test_mask_all_default_fields(self, masker: SensitiveDataMasker) -> None:
        """覆盖所有 DEFAULT_SENSITIVE_FIELDS"""
        data = {
            "authorization": "val_auth",
            "password": "val_pass",
            "token": "val_token",
            "secret": "val_secret",
            "api_key": "val_apikey",
            "cookie": "val_cookie",
            "set-cookie": "val_setcookie",
            "access_token": "val_access",
            "refresh_token": "val_refresh",
            "apikey": "val_apikey2",
        }
        result = masker.mask_dict(data)
        for key in data:
            assert result[key] == "******", f"默认字段 {key} 未脱敏"

    def test_non_sensitive_fields_unchanged(self, masker: SensitiveDataMasker) -> None:
        """非敏感字段应保持原值"""
        data = {
            "username": "john",
            "email": "john@example.com",
            "role": "admin",
            "page": 1,
            "limit": 50,
        }
        result = masker.mask_dict(data)
        assert result == data


# ==================== mask_dict — 嵌套与递归 ====================


class TestMaskDictNested:
    """mask_dict 嵌套字典与递归测试"""

    def test_mask_nested_dict(self, masker: SensitiveDataMasker) -> None:
        """嵌套字典中的敏感字段应递归脱敏"""
        data = {
            "user": {
                "name": "john",
                "password": "s3cret!",
                "settings": {
                    "token": "nested-token-123",
                    "theme": "dark",
                },
            },
            "status": "ok",
        }
        result = masker.mask_dict(data)
        assert result["user"]["password"] == "******"
        assert result["user"]["settings"]["token"] == "******"
        assert result["user"]["name"] == "john"
        assert result["user"]["settings"]["theme"] == "dark"
        assert result["status"] == "ok"

    def test_mask_list_of_dicts(self, masker: SensitiveDataMasker) -> None:
        """列表中的字典元素应递归脱敏"""
        data = [
            {"name": "item1", "token": "t1"},
            {"name": "item2", "password": "p2"},
            {"name": "item3"},
        ]
        result = masker.mask_dict(data)
        assert result[0]["token"] == "******"
        assert result[1]["password"] == "******"
        assert result[2]["name"] == "item3"

    def test_mask_deeply_nested_structure(self, masker: SensitiveDataMasker) -> None:
        """深层嵌套（字典内含列表含字典）应正确处理"""
        data = {
            "results": [
                {
                    "id": 1,
                    "auth": {"token": "deep-token-1"},
                },
                {
                    "id": 2,
                    "auth": {"token": "deep-token-2", "secret": "deep-secret"},
                },
            ],
            "api_key": "top-level-key",
        }
        result = masker.mask_dict(data)
        assert result["api_key"] == "******"
        assert result["results"][0]["auth"]["token"] == "******"
        assert result["results"][1]["auth"]["token"] == "******"
        assert result["results"][1]["auth"]["secret"] == "******"

    def test_mask_dict_preserves_keys(self, masker: SensitiveDataMasker) -> None:
        """脱敏后字典结构应保持不变（仅值变化）"""
        data = {
            "headers": {
                "Authorization": "Bearer xyz",
                "X-Request-Id": "req-001",
            },
            "body": {"password": "old_pass", "username": "user1"},
        }
        result = masker.mask_dict(data)
        assert set(result.keys()) == {"headers", "body"}
        assert set(result["headers"].keys()) == {"Authorization", "X-Request-Id"}
        assert set(result["body"].keys()) == {"password", "username"}


# ==================== mask_dict — 自定义字段 ====================


class TestMaskDictExtraFields:
    """mask_dict 自定义额外字段测试"""

    def test_extra_fields_take_effect(self, masker_with_extra: SensitiveDataMasker) -> None:
        """自定义额外字段应有效脱敏"""
        data = {
            "x-custom-key": "sensitive_value",
            "private_data": "should-be-masked",
            "normal_field": "visible",
        }
        result = masker_with_extra.mask_dict(data)
        assert result["x-custom-key"] == "******"
        assert result["private_data"] == "******"
        assert result["normal_field"] == "visible"

    def test_extra_fields_case_insensitive(self) -> None:
        """自定义字段也大小写不敏感"""
        masker = SensitiveDataMasker(extra_fields=["X-Secret-Header"])
        data = {
            "x-secret-header": "secret1",
            "X-Secret-Header": "secret2",
            "X-SECRET-HEADER": "secret3",
        }
        result = masker.mask_dict(data)
        for key in data:
            assert result[key] == "******"

    def test_no_extra_fields_argument(self) -> None:
        """不传 extra_fields 时应正常工作"""
        masker = SensitiveDataMasker()
        assert masker.fields == {f.lower() for f in SensitiveDataMasker.DEFAULT_SENSITIVE_FIELDS}


# ==================== mask_dict — 边界条件 ====================


class TestMaskDictEdgeCases:
    """mask_dict 边界条件与异常安全测试"""

    def test_empty_dict(self, masker: SensitiveDataMasker) -> None:
        """空字典返回空字典"""
        assert masker.mask_dict({}) == {}

    def test_non_dict_input(self, masker: SensitiveDataMasker) -> None:
        """非字典输入应原样返回"""
        assert masker.mask_dict("string") == "string"
        assert masker.mask_dict(42) == 42
        assert masker.mask_dict(None) is None
        assert masker.mask_dict(3.14) == 3.14
        assert masker.mask_dict(True) is True

    def test_dict_with_non_string_keys(self, masker: SensitiveDataMasker) -> None:
        """非字符串 key 的字典应正确处理"""
        data = {1: "value1", "password": "s3cret", (1, 2): "tuple_key"}
        result = masker.mask_dict(data)
        assert result[1] == "value1"
        assert result["password"] == "******"
        assert result[(1, 2)] == "tuple_key"

    def test_none_values_unaffected(self, masker: SensitiveDataMasker) -> None:
        """None 值应保持不变"""
        data = {"password": None, "token": None, "name": "test"}
        result = masker.mask_dict(data)
        assert result["password"] is None
        assert result["token"] is None
        assert result["name"] == "test"

    def test_int_values_in_sensitive_field(self, masker: SensitiveDataMasker) -> None:
        """敏感字段的数值型 value 也应被替换"""
        data = {"password": 12345, "token": 98765}
        result = masker.mask_dict(data)
        assert result["password"] == "******"
        assert result["token"] == "******"

    def test_list_with_non_dict_items(self, masker: SensitiveDataMasker) -> None:
        """列表中含非 dict 元素应正确处理"""
        data = {"items": [1, "str", None, {"token": "secret"}, 3.14]}
        result = masker.mask_dict(data)
        assert result["items"][0] == 1
        assert result["items"][1] == "str"
        assert result["items"][2] is None
        assert result["items"][3]["token"] == "******"
        assert result["items"][4] == 3.14

    def test_mask_does_not_mutate_original(self, masker: SensitiveDataMasker) -> None:
        """脱敏不应修改原始数据"""
        data = {
            "Authorization": "secret",
            "nested": {"password": "s3cret"},
        }
        original = {
            "Authorization": "secret",
            "nested": {"password": "s3cret"},
        }
        masker.mask_dict(data)
        assert data == original


# ==================== mask_string ====================


class TestMaskString:
    """mask_string 文本正则脱敏测试"""

    def test_mask_bearer_token(self, masker: SensitiveDataMasker) -> None:
        """Bearer token 应替换为 Bearer ****"""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = masker.mask_string(text)
        assert "Bearer ******" in result
        assert "eyJhbGci" not in result

    def test_mask_basic_auth(self, masker: SensitiveDataMasker) -> None:
        """Basic auth 应替换为 Basic ****"""
        text = "Authorization: Basic dXNlcjpwYXNz"
        result = masker.mask_string(text)
        assert "Basic ******" in result
        assert "dXNlcjpwYXNz" not in result

    def test_mask_json_style_password(self, masker: SensitiveDataMasker) -> None:
        """ "password": "value" 模式应替换"""
        text = '{"username": "john", "password": "mysecret123"}'
        result = masker.mask_string(text)
        assert '"password": "******"' in result
        assert "mysecret123" not in result

    def test_mask_token_colon_value(self, masker: SensitiveDataMasker) -> None:
        """token: value 模式应替换"""
        text = "token: abc-def-123"
        result = masker.mask_string(text)
        assert "token=******" in result or "******" in result
        assert "abc-def-123" not in result

    def test_mask_api_key_equals_value(self, masker: SensitiveDataMasker) -> None:
        """api_key=value 模式应替换"""
        text = "api_key=sk-1234567890abcdef"
        result = masker.mask_string(text)
        assert "******" in result
        assert "sk-1234567890abcdef" not in result

    def test_case_insensitive_masking(self, masker: SensitiveDataMasker) -> None:
        """文本脱敏大小写不敏感"""
        text = "Authorization: Bearer token123 AUTH: value456"
        result = masker.mask_string(text)
        assert "token123" not in result or "Bearer ******" in result

    def test_non_sensitive_text_unchanged(self, masker: SensitiveDataMasker) -> None:
        """不含敏感信息的文本应不变"""
        text = "Request succeeded with status 200"
        result = masker.mask_string(text)
        assert result == text

    def test_non_string_input(self, masker: SensitiveDataMasker) -> None:
        """非字符串输入应原样返回"""
        assert masker.mask_string(123) == 123
        assert masker.mask_string(None) is None
        assert masker.mask_string(True) is True

    def test_empty_string(self, masker: SensitiveDataMasker) -> None:
        """空字符串应返回空字符串"""
        assert masker.mask_string("") == ""


# ==================== mask_string — 自定义字段 ====================


class TestMaskStringExtraFields:
    """mask_string 自定义字段正则脱敏测试"""

    def test_extra_field_in_string(self, masker_with_extra: SensitiveDataMasker) -> None:
        """自定义字段在文本中也应被脱敏"""
        text = 'x-custom-key: "very-secret-value" and private_data="confidential"'
        result = masker_with_extra.mask_string(text)
        assert "very-secret-value" not in result
        assert "confidential" not in result


# ==================== 属性与方法 ====================


class TestMaskerProperties:
    """脱敏器属性与方法测试"""

    def test_fields_property(self, masker: SensitiveDataMasker) -> None:
        """fields 属性应返回所有敏感字段集合"""
        fields = masker.fields
        for default_field in SensitiveDataMasker.DEFAULT_SENSITIVE_FIELDS:
            assert default_field.lower() in fields

    def test_fields_is_copy(self, masker: SensitiveDataMasker) -> None:
        """fields 属性应返回副本而非引用"""
        f1 = masker.fields
        _f2 = masker.fields
        f1.add("new_field")
        assert "new_field" not in masker.fields

    def test_placeholder_property(self, masker: SensitiveDataMasker) -> None:
        """placeholder 属性应返回默认占位符"""
        assert masker.placeholder == "******"


# ==================== 集成 — Logger 脱敏 ====================


class TestLoggerMaskIntegration:
    """Logger 脱敏集成测试"""

    @pytest.fixture(autouse=True)
    def _setup_logger_masker(self, request: pytest.FixtureRequest) -> None:
        """确保 Logger 已初始化且启用了脱敏"""
        from framework.utils.logger import Logger

        if not Logger._initialized:
            Logger.setup(
                {
                    "level": "DEBUG",
                    "mask_enabled": True,
                    "sensitive_fields": ["x-integration-key"],
                }
            )

    def test_logger_mask_sensitive_dict(self) -> None:
        """Logger.mask_sensitive 应对字典脱敏"""
        from framework.utils.logger import Logger

        data = {"Authorization": "secret", "Content-Type": "json"}
        result = Logger.mask_sensitive(data)
        assert result["Authorization"] == "******"
        assert result["Content-Type"] == "json"

    def test_logger_mask_sensitive_str(self) -> None:
        """Logger.mask_sensitive_str 应对文本脱敏"""
        from framework.utils.logger import Logger

        text = "Authorization: Bearer token-abc-123"
        result = Logger.mask_sensitive_str(text)
        assert "token-abc-123" not in result
        assert "Bearer" in result

    def test_logger_mask_disabled(self) -> None:
        """禁用脱敏时应返回原始数据"""
        from framework.utils.logger import Logger

        # 临时禁用
        original = Logger._mask_enabled
        Logger._mask_enabled = False
        try:
            data = {"password": "s3cret"}
            result = Logger.mask_sensitive(data)
            assert result == data
        finally:
            Logger._mask_enabled = original

    def test_custom_field_via_config(self) -> None:
        """通过配置注册的自定义字段应生效"""
        from framework.utils.logger import Logger

        data = {"x-integration-key": "should-be-masked"}
        result = Logger.mask_sensitive(data)
        assert result["x-integration-key"] == "******"


# ==================== 完整请求场景 ====================


class TestRealWorldScenarios:
    """真实请求/响应场景测试"""

    def test_full_http_request_headers(self, masker: SensitiveDataMasker) -> None:
        """模拟完整 HTTP 请求头脱敏"""
        headers = {
            "Host": "api.example.com",
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Cookie": "session_id=abc123; token=xyz789",
            "X-Request-Id": "req-001",
        }
        result = masker.mask_dict(headers)
        assert result["Authorization"] == "******"
        assert result["Cookie"] == "******"
        assert result["Host"] == "api.example.com"
        assert result["Content-Type"] == "application/json"
        assert result["X-Request-Id"] == "req-001"

    def test_full_request_body(self, masker: SensitiveDataMasker) -> None:
        """模拟 JSON 请求体脱敏"""
        body = {
            "username": "admin",
            "password": "SuperSecret123!",
            "email": "admin@example.com",
            "auth": {
                "token": "jwt-token-here",
                "refresh_token": "refresh-token-here",
            },
            "profile": {
                "api_key": "sk-proj-abc123",
                "settings": {"theme": "dark"},
            },
        }
        result = masker.mask_dict(body)
        assert result["password"] == "******"
        assert result["username"] == "admin"
        assert result["auth"]["token"] == "******"
        assert result["auth"]["refresh_token"] == "******"
        assert result["profile"]["api_key"] == "******"
        assert result["profile"]["settings"]["theme"] == "dark"

    def test_response_with_set_cookie(self, masker: SensitiveDataMasker) -> None:
        """响应头含 Set-Cookie 应脱敏"""
        headers = {
            "Content-Type": "application/json",
            "Set-Cookie": "session=abc123; HttpOnly; Secure",
            "X-RateLimit-Remaining": "99",
        }
        result = masker.mask_dict(headers)
        assert result["Set-Cookie"] == "******"
        assert result["Content-Type"] == "application/json"

    def test_auth_dict_in_request(self, masker: SensitiveDataMasker) -> None:
        """认证信息字典脱敏"""
        auth_data = {
            "type": "bearer",
            "token": "my-super-secret-token",
            "username": "admin",
            "password": "admin123",
        }
        result = masker.mask_dict(auth_data)
        assert result["token"] == "******"
        assert result["password"] == "******"
        assert result["type"] == "bearer"
