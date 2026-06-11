"""ContextSnapshot 单元测试

测试覆盖：
- ContextSnapshot 不可变 dataclass
- _is_sensitive_key 敏感字段检测
- _mask_sensitive_vars 脱敏逻辑
- _safe_serialize 安全序列化
- ContextSnapshotManager.capture_on_failure
- ContextSnapshotManager.get_snapshot
"""

from __future__ import annotations

import uuid
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock

import pytest

from framework.context_snapshot import (
    ContextSnapshot,
    ContextSnapshotManager,
    _is_sensitive_key,
    _mask_sensitive_vars,
    _safe_serialize,
)


class TestIsSensitiveKey:
    """敏感字段检测测试."""

    def test_token_is_sensitive(self) -> None:
        assert _is_sensitive_key("access_token") is True
        assert _is_sensitive_key("refresh_token") is True
        assert _is_sensitive_key("TOKEN") is True

    def test_password_is_sensitive(self) -> None:
        assert _is_sensitive_key("password") is True
        assert _is_sensitive_key("PASSWORD") is True
        assert _is_sensitive_key("admin_password") is True

    def test_secret_is_sensitive(self) -> None:
        assert _is_sensitive_key("api_secret") is True
        assert _is_sensitive_key("client_secret") is True

    def test_api_key_is_sensitive(self) -> None:
        assert _is_sensitive_key("api_key") is True
        assert _is_sensitive_key("apikey") is True

    def test_authorization_is_sensitive(self) -> None:
        assert _is_sensitive_key("authorization") is True
        assert _is_sensitive_key("Authorization") is True

    def test_credential_is_sensitive(self) -> None:
        assert _is_sensitive_key("credential") is True
        assert _is_sensitive_key("credentials") is True

    def test_normal_keys_are_not_sensitive(self) -> None:
        assert _is_sensitive_key("username") is False
        assert _is_sensitive_key("user_id") is False
        assert _is_sensitive_key("name") is False
        assert _is_sensitive_key("email") is False
        assert _is_sensitive_key("base_url") is False


class TestMaskSensitiveVars:
    """脱敏逻辑测试."""

    def test_masks_sensitive_fields(self) -> None:
        vars_dict = {
            "username": "test_user",
            "access_token": "secret123",
            "password": "p@ssw0rd",
            "name": "John",
        }
        result = _mask_sensitive_vars(vars_dict)
        assert result["username"] == "test_user"
        assert result["access_token"] == "***REDACTED***"
        assert result["password"] == "***REDACTED***"
        assert result["name"] == "John"

    def test_empty_dict(self) -> None:
        result = _mask_sensitive_vars({})
        assert result == {}

    def test_all_sensitive(self) -> None:
        vars_dict = {
            "api_key": "key123",
            "api_secret": "secret123",
            "token": "tok123",
        }
        result = _mask_sensitive_vars(vars_dict)
        for v in result.values():
            assert v == "***REDACTED***"


class TestSafeSerialize:
    """安全序列化测试."""

    def test_primitives(self) -> None:
        assert _safe_serialize("hello") == "hello"
        assert _safe_serialize(42) == 42
        assert _safe_serialize(3.14) == 3.14
        assert _safe_serialize(True) is True
        assert _safe_serialize(None) is None

    def test_list(self) -> None:
        assert _safe_serialize([1, "a", True]) == [1, "a", True]

    def test_tuple(self) -> None:
        assert _safe_serialize((1, 2)) == [1, 2]

    def test_dict(self) -> None:
        assert _safe_serialize({"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_non_serializable_object(self) -> None:
        result = _safe_serialize(uuid.UUID("12345678-1234-1234-1234-123456789abc"))
        assert isinstance(result, str)
        assert "12345678" in result


class TestContextSnapshot:
    """ContextSnapshot dataclass 测试."""

    def test_frozen_dataclass(self) -> None:
        snapshot = ContextSnapshot(
            execution_id="exec-1",
            step_index=0,
            run_vars=MappingProxyType({"a": 1}),
            case_vars=MappingProxyType({"b": 2}),
            step_vars=MappingProxyType({"c": 3}),
            error_message="test error",
            traceback="traceback info",
        )
        assert snapshot.execution_id == "exec-1"
        assert snapshot.step_index == 0
        assert snapshot.run_vars["a"] == 1
        assert snapshot.case_vars["b"] == 2
        assert snapshot.step_vars["c"] == 3
        assert snapshot.error_message == "test error"
        assert snapshot.traceback == "traceback info"

        # 验证不可变性
        with pytest.raises(Exception):
            snapshot.step_index = 1  # type: ignore[misc]


class TestContextSnapshotManager:
    """ContextSnapshotManager 测试."""

    @pytest.fixture
    def mock_repo(self) -> MagicMock:
        """创建 mock ContextSnapshotRepository."""
        repo = MagicMock()
        repo._session = MagicMock()
        repo._session.add = MagicMock()
        repo._session.flush = AsyncMock()
        repo.get_by_execution = AsyncMock()
        return repo

    @pytest.fixture
    def mock_test_context(self) -> MagicMock:
        """创建 mock TestContext."""
        ctx = MagicMock()
        ctx.get_all_variables.return_value = {"base_url": "http://test", "token": "sensitive"}
        ctx.get_suite_vars.return_value = {"env": "test", "access_token": "secret123"}
        ctx.get_case_vars.return_value = {"case_var": "value", "api_key": "key123"}
        ctx.get_step_vars.return_value = {"step_var": "value"}
        return ctx

    @pytest.mark.asyncio
    async def test_capture_on_failure(self, mock_repo, mock_test_context):
        """测试失败时捕获快照."""
        manager = ContextSnapshotManager(mock_repo)
        exec_id = uuid.uuid4()
        error = ValueError("test error message")

        snapshot = await manager.capture_on_failure(
            execution_id=exec_id,
            step_index=2,
            test_context=mock_test_context,
            error=error,
        )

        assert snapshot.execution_id == str(exec_id)
        assert snapshot.step_index == 2
        assert snapshot.error_message == "test error message"
        assert "ValueError" in snapshot.traceback
        # 验证脱敏 - run_vars 中的敏感字段
        assert snapshot.run_vars.get("access_token") == "***REDACTED***"
        assert snapshot.run_vars.get("env") == "test"
        # 验证脱敏 - case_vars 中的敏感字段
        assert snapshot.case_vars.get("api_key") == "***REDACTED***"
        assert snapshot.case_vars.get("case_var") == "value"

        # 验证持久化
        mock_repo._session.add.assert_called_once()
        mock_repo._session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_snapshot_found(self, mock_repo):
        """测试查询存在的快照."""
        manager = ContextSnapshotManager(mock_repo)

        mock_model = MagicMock()
        mock_model.execution_id = uuid.uuid4()
        mock_model.step_index = 1
        mock_model.run_vars = {"a": 1}
        mock_model.case_vars = {"b": 2}
        mock_model.step_vars = {"c": 3}
        mock_model.error_message = "error"
        mock_model.traceback = "tb"

        mock_repo.get_by_execution.return_value = mock_model

        exec_id = uuid.uuid4()
        snapshot = await manager.get_snapshot(exec_id)

        assert snapshot is not None
        assert snapshot.step_index == 1
        assert snapshot.run_vars["a"] == 1
        assert snapshot.case_vars["b"] == 2
        assert snapshot.step_vars["c"] == 3

    @pytest.mark.asyncio
    async def test_get_snapshot_not_found(self, mock_repo):
        """测试查询不存在的快照."""
        manager = ContextSnapshotManager(mock_repo)
        mock_repo.get_by_execution.return_value = None

        snapshot = await manager.get_snapshot(uuid.uuid4())
        assert snapshot is None
