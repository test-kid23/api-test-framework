"""掩码器测试入口 — Phase 0a 已完成

SensitiveDataMasker 的完整单元测试位于 tests/framework/utils/test_masker.py。
本文件提供模块导入验证和基础功能确认。
"""

from __future__ import annotations

import pytest

from framework.utils.masker import SensitiveDataMasker


class TestMaskerImports:
    """验证 masker 模块可正常导入"""

    def test_sensitive_data_masker_importable(self) -> None:
        masker = SensitiveDataMasker()
        assert masker is not None

    def test_default_fields_present(self) -> None:
        masker = SensitiveDataMasker()
        assert len(masker.DEFAULT_SENSITIVE_FIELDS) >= 10
        for field in ["authorization", "password", "token", "secret", "api_key"]:
            assert field in masker.DEFAULT_SENSITIVE_FIELDS

    def test_basic_mask_works(self) -> None:
        masker = SensitiveDataMasker()
        data = {"password": "secret123", "username": "john"}
        result = masker.mask_dict(data)
        assert result["password"] == "******"
        assert result["username"] == "john"

    def test_extra_fields_accepted(self) -> None:
        masker = SensitiveDataMasker(extra_fields=["x-api-key", "private_token"])
        data = {"x-api-key": "sk-abc123", "public": "visible"}
        result = masker.mask_dict(data)
        assert result["x-api-key"] == "******"
        assert result["public"] == "visible"

    def test_mask_string_bearer(self) -> None:
        masker = SensitiveDataMasker()
        text = "Authorization: Bearer token123abc"
        result = masker.mask_string(text)
        assert "Bearer ******" in result
        assert "token123abc" not in result

    def test_placeholder_class_attr(self) -> None:
        assert SensitiveDataMasker.MASK_PLACEHOLDER == "******"
