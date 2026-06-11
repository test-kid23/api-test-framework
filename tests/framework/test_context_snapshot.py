"""ContextSnapshot 单元测试

测试覆盖：
- ContextSnapshot 不可变 dataclass
- _is_sensitive_key 敏感字段检测
- _mask_sensitive_vars 脱敏逻辑
- _safe_serialize 安全序列化
- ContextSnapshotManager.capture_on_failure
- ContextSnapshotManager.get_snapshot
- ContextSnapshotManager.cache_step_snapshot (Redis, T5-12)
- ContextSnapshotManager.get_cached_snapshot (Redis, T5-12)
- Redis 不可用时降级（不阻塞执行）
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


# ═══════════════════════════════════════════════════════════
# T5-12: Redis 缓存测试
# ═══════════════════════════════════════════════════════════


class MockRedisForSnapshot:
    """模拟 Redis 客户端（用于快照缓存测试）."""

    def __init__(self, available: bool = True) -> None:
        self._store: dict[str, str] = {}
        self._available = available
        self.ping_called = False

    async def ping(self) -> bool:
        self.ping_called = True
        if not self._available:
            raise ConnectionError("Redis connection failed")
        return True

    async def set(self, key: str, value: str, ex: int = 0) -> None:
        self._store[key] = value

    async def get(self, key: str) -> str | None:
        return self._store.get(key)


class TestContextSnapshotRedisCache:
    """T5-12: Redis 快照缓存测试."""

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
    def redis_available(self) -> MockRedisForSnapshot:
        """Redis 可用的 mock."""
        return MockRedisForSnapshot(available=True)

    @pytest.fixture
    def redis_unavailable(self) -> MockRedisForSnapshot:
        """Redis 不可用的 mock."""
        return MockRedisForSnapshot(available=False)

    @pytest.mark.asyncio
    async def test_cache_step_snapshot_stores_to_redis(
        self,
        mock_repo: MagicMock,
        redis_available: MockRedisForSnapshot,
    ) -> None:
        """cache_step_snapshot 将数据写入 Redis."""
        manager = ContextSnapshotManager(
            repo=mock_repo,
            redis_client=redis_available,  # type: ignore[arg-type]
        )

        await manager.cache_step_snapshot(
            execution_id="exec-redis-1",
            step_index=3,
            run_vars={"env": "prod", "token": "secret123"},
            case_vars={"user": "admin", "password": "pw"},
            step_vars={"result": "ok"},
        )

        # 验证 Redis 中有数据
        key = "autotest:snapshot:exec-redis-1"
        assert key in redis_available._store

        import json
        data = json.loads(redis_available._store[key])
        assert data["execution_id"] == "exec-redis-1"
        assert data["step_index"] == 3
        # 验证脱敏
        assert data["run_vars"]["token"] == "***REDACTED***"
        assert data["run_vars"]["env"] == "prod"
        assert data["case_vars"]["password"] == "***REDACTED***"
        assert data["case_vars"]["user"] == "admin"

    @pytest.mark.asyncio
    async def test_get_cached_snapshot_returns_snapshot(
        self,
        mock_repo: MagicMock,
        redis_available: MockRedisForSnapshot,
    ) -> None:
        """get_cached_snapshot 从 Redis 读取快照."""
        manager = ContextSnapshotManager(
            repo=mock_repo,
            redis_client=redis_available,  # type: ignore[arg-type]
        )

        # 先缓存
        await manager.cache_step_snapshot(
            execution_id="exec-redis-2",
            step_index=5,
            run_vars={"env": "dev"},
            case_vars={"case": "test"},
            step_vars={"step": "data"},
        )

        # 读取缓存
        snapshot = await manager.get_cached_snapshot("exec-redis-2")
        assert snapshot is not None
        assert snapshot.execution_id == "exec-redis-2"
        assert snapshot.step_index == 5
        assert snapshot.run_vars.get("env") == "dev"

    @pytest.mark.asyncio
    async def test_get_cached_snapshot_returns_none_on_miss(
        self,
        mock_repo: MagicMock,
        redis_available: MockRedisForSnapshot,
    ) -> None:
        """缓存未命中时返回 None."""
        manager = ContextSnapshotManager(
            repo=mock_repo,
            redis_client=redis_available,  # type: ignore[arg-type]
        )

        snapshot = await manager.get_cached_snapshot("nonexistent")
        assert snapshot is None

    @pytest.mark.asyncio
    async def test_cache_step_snapshot_degraded_when_redis_unavailable(
        self,
        mock_repo: MagicMock,
        redis_unavailable: MockRedisForSnapshot,
    ) -> None:
        """Redis 不可用时 cache_step_snapshot 静默降级（不抛异常）."""
        manager = ContextSnapshotManager(
            repo=mock_repo,
            redis_client=redis_unavailable,  # type: ignore[arg-type]
        )

        # 不应抛出异常
        await manager.cache_step_snapshot(
            execution_id="exec-degraded",
            step_index=1,
            run_vars={"key": "value"},
            case_vars={},
            step_vars={},
        )

        # Redis 存储应为空
        assert "autotest:snapshot:exec-degraded" not in redis_unavailable._store

    @pytest.mark.asyncio
    async def test_get_cached_snapshot_degraded_when_redis_unavailable(
        self,
        mock_repo: MagicMock,
        redis_unavailable: MockRedisForSnapshot,
    ) -> None:
        """Redis 不可用时 get_cached_snapshot 返回 None."""
        manager = ContextSnapshotManager(
            repo=mock_repo,
            redis_client=redis_unavailable,  # type: ignore[arg-type]
        )

        snapshot = await manager.get_cached_snapshot("any-exec")
        assert snapshot is None

    @pytest.mark.asyncio
    async def test_no_redis_client_skips_cache(
        self,
        mock_repo: MagicMock,
    ) -> None:
        """未配置 Redis 时跳过缓存操作."""
        manager = ContextSnapshotManager(repo=mock_repo)

        # 不应抛出异常
        await manager.cache_step_snapshot(
            execution_id="exec-no-redis",
            step_index=1,
            run_vars={},
            case_vars={},
            step_vars={},
        )

        snapshot = await manager.get_cached_snapshot("exec-no-redis")
        assert snapshot is None

    @pytest.mark.asyncio
    async def test_get_snapshot_falls_back_to_db_on_cache_miss(
        self,
        mock_repo: MagicMock,
        redis_available: MockRedisForSnapshot,
    ) -> None:
        """get_snapshot 在 Redis 未命中时回退 DB."""
        manager = ContextSnapshotManager(
            repo=mock_repo,
            redis_client=redis_available,  # type: ignore[arg-type]
        )

        # DB 有数据
        mock_model = MagicMock()
        mock_model.execution_id = uuid.uuid4()
        mock_model.step_index = 1
        mock_model.run_vars = {"a": 1}
        mock_model.case_vars = {}
        mock_model.step_vars = {}
        mock_model.error_message = "error"
        mock_model.traceback = "tb"
        mock_repo.get_by_execution.return_value = mock_model

        exec_id = uuid.uuid4()
        snapshot = await manager.get_snapshot(exec_id)

        # 应从 DB 获取
        assert snapshot is not None
        assert snapshot.step_index == 1
        mock_repo.get_by_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_availability_is_cached(
        self,
        mock_repo: MagicMock,
        redis_available: MockRedisForSnapshot,
    ) -> None:
        """Redis 可用性检测结果被缓存（不重复 ping）."""
        manager = ContextSnapshotManager(
            repo=mock_repo,
            redis_client=redis_available,  # type: ignore[arg-type]
        )

        # 第一次调用 — ping
        await manager.cache_step_snapshot(
            execution_id="exec-1",
            step_index=1,
            run_vars={},
            case_vars={},
            step_vars={},
        )
        assert redis_available.ping_called is True

        # 重置 ping 调用计数
        redis_available.ping_called = False

        # 第二次调用 — 不 ping（缓存了可用性结果）
        await manager.cache_step_snapshot(
            execution_id="exec-2",
            step_index=1,
            run_vars={},
            case_vars={},
            step_vars={},
        )
        # 可用性被缓存，不会再次 ping
        assert redis_available.ping_called is False

    @pytest.mark.asyncio
    async def test_cache_uses_correct_ttl(
        self,
        mock_repo: MagicMock,
    ) -> None:
        """验证 REDIS_CACHE_TTL 默认值为 3600."""
        assert ContextSnapshotManager.REDIS_CACHE_TTL == 3600

    @pytest.mark.asyncio
    async def test_cache_key_prefix(
        self,
        mock_repo: MagicMock,
        redis_available: MockRedisForSnapshot,
    ) -> None:
        """验证缓存键前缀."""
        manager = ContextSnapshotManager(
            repo=mock_repo,
            redis_client=redis_available,  # type: ignore[arg-type]
        )
        assert manager._REDIS_KEY_PREFIX == "autotest:snapshot:"
