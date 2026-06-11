"""Worker 健康监控单元测试

测试覆盖：
- WorkerInfo dataclass 正确性
- WorkerHealthMonitor 初始化
- start_heartbeat / stop_heartbeat 心跳生命周期
- get_all_workers 返回正确状态列表
- get_worker 单个 Worker 查询
- check_health 离线检测与告警
- 告警去重（同一 Worker 不重复告警）
- 告警恢复（Worker 重新上线后清除告警状态）
- 全局单例 get_worker_health_monitor / reset_monitor
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from framework.worker_health import (
    WorkerHealthMonitor,
    WorkerInfo,
    get_worker_health_monitor,
    has_monitor,
    reset_monitor,
)


class TestWorkerInfo:
    """WorkerInfo dataclass 测试."""

    def test_default_values(self) -> None:
        """默认字段值正确."""
        info = WorkerInfo(
            worker_id="w1",
            hostname="node01",
            status="online",
            last_heartbeat=datetime.now(timezone.utc),
        )
        assert info.worker_id == "w1"
        assert info.hostname == "node01"
        assert info.status == "online"
        assert info.current_task is None
        assert info.uptime_seconds == 0

    def test_with_all_fields(self) -> None:
        """全部字段赋值正确."""
        now = datetime.now(timezone.utc)
        info = WorkerInfo(
            worker_id="w2",
            hostname="node02",
            status="busy",
            last_heartbeat=now,
            current_task="task-123",
            uptime_seconds=3600,
        )
        assert info.current_task == "task-123"
        assert info.uptime_seconds == 3600


# ── Redis 模拟辅助 ────────────────────────────────────────


class MockRedis:
    """模拟 Redis 异步客户端.

    提供 set/exists/scan/hgetall/hset/expire/delete 方法，
    行为与真实 Redis 客户端一致。
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._hash_store: dict[str, dict[str, str]] = {}
        self._expirations: dict[str, int] = {}

    async def set(self, key: str, value: str, ex: int = 0) -> None:
        self._store[key] = value
        if ex > 0:
            self._expirations[key] = ex

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def scan(
        self,
        cursor: int = 0,
        match: str | None = None,
    ) -> tuple[int, list[bytes]]:
        if cursor != 0:
            return (0, [])
        pattern = match.replace("*", "") if match else ""
        keys = [k.encode() for k in self._store if k.startswith(pattern)]
        return (0, keys)

    async def hgetall(self, key: str) -> dict[bytes, bytes]:
        data = self._hash_store.get(key, {})
        return {k.encode(): v.encode() for k, v in data.items()}

    async def hset(
        self,
        key: str,
        mapping_or_field: dict[str, str] | str | None = None,
        value: str | None = None,
        mapping: dict[str, str] | None = None,
        **kwargs: str,
    ) -> None:
        if key not in self._hash_store:
            self._hash_store[key] = {}
        # Support hset(key, field, value) — 3-arg form
        if isinstance(mapping_or_field, str) and value is not None:
            self._hash_store[key][mapping_or_field] = value
        # Support hset(key, mapping={...}) — keyword form
        elif isinstance(mapping_or_field, dict):
            self._hash_store[key].update(mapping_or_field)
        if mapping:
            self._hash_store[key].update(mapping)
        if kwargs:
            self._hash_store[key].update(kwargs)

    async def expire(self, key: str, ttl: int) -> None:
        self._expirations[key] = ttl

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self._store.pop(key, None)
            self._hash_store.pop(key, None)
            self._expirations.pop(key, None)


@pytest.fixture
def mock_redis() -> MockRedis:
    """提供模拟 Redis 客户端."""
    return MockRedis()


@pytest.fixture
def mock_notification_service() -> MagicMock:
    """提供模拟 NotificationService."""
    svc = MagicMock()
    svc.send_alert = AsyncMock(return_value=True)
    return svc


@pytest.fixture
def monitor(mock_redis: MockRedis) -> WorkerHealthMonitor:
    """提供 WorkerHealthMonitor 实例（无通知服务）."""
    return WorkerHealthMonitor(redis_client=mock_redis)  # type: ignore[arg-type]


@pytest.fixture
def monitor_with_alert(
    mock_redis: MockRedis,
    mock_notification_service: MagicMock,
) -> WorkerHealthMonitor:
    """提供带通知服务的 WorkerHealthMonitor 实例."""
    return WorkerHealthMonitor(
        redis_client=mock_redis,  # type: ignore[arg-type]
        notification_service=mock_notification_service,  # type: ignore[arg-type]
    )


# ── 心跳生命周期测试 ──────────────────────────────────────


class TestHeartbeatLifecycle:
    """心跳启动/停止测试."""

    @pytest.mark.asyncio
    async def test_start_heartbeat_creates_redis_keys(
        self,
        monitor: WorkerHealthMonitor,
        mock_redis: MockRedis,
    ) -> None:
        """启动心跳后 Redis 中存在心跳键和元信息键."""
        await monitor.start_heartbeat("worker-1", "node01")

        # 心跳键存在
        assert await mock_redis.exists("autotest:worker:heartbeat:worker-1") == 1

        # 元信息键存在
        info = await mock_redis.hgetall("autotest:worker:info:worker-1")
        assert b"hostname" in info
        assert info[b"hostname"] == b"node01"
        assert info[b"worker_id"] == b"worker-1"

        # 清理心跳任务
        await monitor.stop_heartbeat("worker-1")

    @pytest.mark.asyncio
    async def test_start_heartbeat_auto_hostname(
        self,
        monitor: WorkerHealthMonitor,
        mock_redis: MockRedis,
    ) -> None:
        """不传 hostname 时自动检测."""
        await monitor.start_heartbeat("worker-2")

        info = await mock_redis.hgetall("autotest:worker:info:worker-2")
        # hostname 应为 socket.gethostname() 返回的值
        assert b"hostname" in info
        assert info[b"hostname"] != b""

        await monitor.stop_heartbeat("worker-2")

    @pytest.mark.asyncio
    async def test_stop_heartbeat_cleans_redis_keys(
        self,
        monitor: WorkerHealthMonitor,
        mock_redis: MockRedis,
    ) -> None:
        """停止心跳后 Redis 键被清理."""
        await monitor.start_heartbeat("worker-3", "node03")
        await monitor.stop_heartbeat("worker-3")

        assert await mock_redis.exists("autotest:worker:heartbeat:worker-3") == 0

    @pytest.mark.asyncio
    async def test_double_start_heartbeat_is_safe(
        self,
        monitor: WorkerHealthMonitor,
        mock_redis: MockRedis,
    ) -> None:
        """重复启动心跳不会崩溃."""
        await monitor.start_heartbeat("worker-4", "node04")
        await monitor.start_heartbeat("worker-4", "node04")  # 第二次调用

        assert await mock_redis.exists("autotest:worker:heartbeat:worker-4") == 1

        await monitor.stop_heartbeat("worker-4")

    @pytest.mark.asyncio
    async def test_stop_nonexistent_heartbeat_is_safe(
        self,
        monitor: WorkerHealthMonitor,
    ) -> None:
        """停止不存在的心跳不会崩溃."""
        await monitor.stop_heartbeat("nonexistent")


# ── Worker 查询测试 ───────────────────────────────────────


class TestGetAllWorkers:
    """get_all_workers 测试."""

    @pytest.mark.asyncio
    async def test_empty_when_no_workers(
        self,
        monitor: WorkerHealthMonitor,
    ) -> None:
        """没有注册 Worker 时返回空列表."""
        workers = await monitor.get_all_workers()
        assert workers == []

    @pytest.mark.asyncio
    async def test_returns_online_worker(
        self,
        monitor: WorkerHealthMonitor,
    ) -> None:
        """刚注册的 Worker 状态为 online."""
        await monitor.start_heartbeat("w1", "node01")

        workers = await monitor.get_all_workers()
        assert len(workers) == 1
        assert workers[0].worker_id == "w1"
        assert workers[0].hostname == "node01"
        assert workers[0].status == "online"

        await monitor.stop_heartbeat("w1")

    @pytest.mark.asyncio
    async def test_returns_offline_worker(
        self,
        monitor: WorkerHealthMonitor,
        mock_redis: MockRedis,
    ) -> None:
        """超过阈值未心跳的 Worker 状态为 offline."""
        # 手动写入一个过期的心跳时间
        old_time = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        await mock_redis.set(
            "autotest:worker:heartbeat:stale",
            old_time,
            ex=90,
        )
        await mock_redis.hset(
            "autotest:worker:info:stale",
            mapping={
                "worker_id": "stale",
                "hostname": "old-node",
                "started_at": old_time,
                "last_heartbeat": old_time,
                "current_task": "",
            },
        )

        workers = await monitor.get_all_workers()
        assert len(workers) == 1
        assert workers[0].status == "offline"
        assert workers[0].worker_id == "stale"

    @pytest.mark.asyncio
    async def test_sorted_by_hostname(
        self,
        monitor: WorkerHealthMonitor,
    ) -> None:
        """返回结果按 hostname 排序."""
        await monitor.start_heartbeat("w-z", "z-host")
        await monitor.start_heartbeat("w-a", "a-host")
        await monitor.start_heartbeat("w-m", "m-host")

        workers = await monitor.get_all_workers()
        hostnames = [w.hostname for w in workers]
        assert hostnames == sorted(hostnames)

        for wid in ["w-z", "w-a", "w-m"]:
            await monitor.stop_heartbeat(wid)

    @pytest.mark.asyncio
    async def test_busy_status_with_current_task(
        self,
        monitor: WorkerHealthMonitor,
        mock_redis: MockRedis,
    ) -> None:
        """有 current_task 的 Worker 状态为 busy."""
        now = datetime.now(timezone.utc).isoformat()
        await mock_redis.set(
            "autotest:worker:heartbeat:busy-w",
            now,
            ex=90,
        )
        await mock_redis.hset(
            "autotest:worker:info:busy-w",
            mapping={
                "worker_id": "busy-w",
                "hostname": "busy-node",
                "started_at": now,
                "last_heartbeat": now,
                "current_task": "task-abc-123",
            },
        )

        workers = await monitor.get_all_workers()
        assert len(workers) == 1
        assert workers[0].status == "busy"
        assert workers[0].current_task == "task-abc-123"


class TestGetWorker:
    """get_worker 测试."""

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent(
        self,
        monitor: WorkerHealthMonitor,
    ) -> None:
        """不存在的 Worker 返回 None."""
        result = await monitor.get_worker("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_worker_info(
        self,
        monitor: WorkerHealthMonitor,
    ) -> None:
        """存在的 Worker 返回正确信息."""
        await monitor.start_heartbeat("single-w", "single-node")

        worker = await monitor.get_worker("single-w")
        assert worker is not None
        assert worker.worker_id == "single-w"
        assert worker.hostname == "single-node"
        assert worker.status == "online"

        await monitor.stop_heartbeat("single-w")


# ── 健康检查与告警测试 ───────────────────────────────────


class TestCheckHealth:
    """check_health 离线检测与告警测试."""

    @pytest.mark.asyncio
    async def test_no_alert_for_online_workers(
        self,
        monitor_with_alert: WorkerHealthMonitor,
        mock_notification_service: MagicMock,
    ) -> None:
        """在线 Worker 不触发告警."""
        await monitor_with_alert.start_heartbeat("w-online", "online-node")

        workers = await monitor_with_alert.check_health()
        assert len(workers) == 1
        assert workers[0].status == "online"

        # 不应发送告警
        mock_notification_service.send_alert.assert_not_called()

        await monitor_with_alert.stop_heartbeat("w-online")

    @pytest.mark.asyncio
    async def test_sends_alert_for_offline_worker(
        self,
        monitor_with_alert: WorkerHealthMonitor,
        mock_redis: MockRedis,
        mock_notification_service: MagicMock,
    ) -> None:
        """离线 Worker 触发告警通知."""
        old_time = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        await mock_redis.set(
            "autotest:worker:heartbeat:offline-w",
            old_time,
            ex=90,
        )
        await mock_redis.hset(
            "autotest:worker:info:offline-w",
            mapping={
                "worker_id": "offline-w",
                "hostname": "offline-node",
                "started_at": old_time,
                "last_heartbeat": old_time,
                "current_task": "",
            },
        )

        workers = await monitor_with_alert.check_health()
        assert len(workers) == 1
        assert workers[0].status == "offline"

        # 应发送告警
        mock_notification_service.send_alert.assert_called_once()
        call_kwargs = mock_notification_service.send_alert.call_args.kwargs
        assert call_kwargs["level"] == "warning"
        assert "offline-node" in call_kwargs["title"]

    @pytest.mark.asyncio
    async def test_alert_deduplication(
        self,
        monitor_with_alert: WorkerHealthMonitor,
        mock_redis: MockRedis,
        mock_notification_service: MagicMock,
    ) -> None:
        """同一离线 Worker 不重复告警."""
        old_time = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        await mock_redis.set(
            "autotest:worker:heartbeat:dup-w",
            old_time,
            ex=90,
        )
        await mock_redis.hset(
            "autotest:worker:info:dup-w",
            mapping={
                "worker_id": "dup-w",
                "hostname": "dup-node",
                "started_at": old_time,
                "last_heartbeat": old_time,
                "current_task": "",
            },
        )

        # 第一次检查 — 发送告警
        await monitor_with_alert.check_health()
        assert mock_notification_service.send_alert.call_count == 1

        # 第二次检查 — 不重复发送
        await monitor_with_alert.check_health()
        assert mock_notification_service.send_alert.call_count == 1

    @pytest.mark.asyncio
    async def test_alert_recovery_clears_alerted_set(
        self,
        monitor_with_alert: WorkerHealthMonitor,
        mock_redis: MockRedis,
        mock_notification_service: MagicMock,
    ) -> None:
        """Worker 恢复上线后，再次离线时重新告警."""
        old_time = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        await mock_redis.set(
            "autotest:worker:heartbeat:recover-w",
            old_time,
            ex=90,
        )
        await mock_redis.hset(
            "autotest:worker:info:recover-w",
            mapping={
                "worker_id": "recover-w",
                "hostname": "recover-node",
                "started_at": old_time,
                "last_heartbeat": old_time,
                "current_task": "",
            },
        )

        # 第一次检查 — 离线，发送告警
        await monitor_with_alert.check_health()
        assert mock_notification_service.send_alert.call_count == 1

        # 模拟 Worker 恢复 — 更新心跳时间
        now = datetime.now(timezone.utc).isoformat()
        await mock_redis.set(
            "autotest:worker:heartbeat:recover-w",
            now,
            ex=90,
        )
        await mock_redis.hset(
            "autotest:worker:info:recover-w",
            mapping={
                "worker_id": "recover-w",
                "hostname": "recover-node",
                "started_at": old_time,
                "last_heartbeat": now,
                "current_task": "",
            },
        )

        # 第二次检查 — 在线，不告警
        await monitor_with_alert.check_health()
        assert mock_notification_service.send_alert.call_count == 1

        # 模拟再次离线
        await mock_redis.set(
            "autotest:worker:heartbeat:recover-w",
            old_time,
            ex=90,
        )
        await mock_redis.hset(
            "autotest:worker:info:recover-w",
            mapping={
                "worker_id": "recover-w",
                "hostname": "recover-node",
                "started_at": old_time,
                "last_heartbeat": old_time,
                "current_task": "",
            },
        )

        # 第三次检查 — 再次离线，重新告警
        await monitor_with_alert.check_health()
        assert mock_notification_service.send_alert.call_count == 2

    @pytest.mark.asyncio
    async def test_no_alert_when_notification_service_is_none(
        self,
        monitor: WorkerHealthMonitor,
        mock_redis: MockRedis,
    ) -> None:
        """未配置通知服务时不告警也不崩溃."""
        old_time = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        await mock_redis.set(
            "autotest:worker:heartbeat:no-alert",
            old_time,
            ex=90,
        )
        await mock_redis.hset(
            "autotest:worker:info:no-alert",
            mapping={
                "worker_id": "no-alert",
                "hostname": "silent-node",
                "started_at": old_time,
                "last_heartbeat": old_time,
                "current_task": "",
            },
        )

        # 不应抛出异常
        workers = await monitor.check_health()
        assert len(workers) == 1
        assert workers[0].status == "offline"


# ── 全局单例测试 ──────────────────────────────────────────


class TestGlobalSingleton:
    """全局单例管理测试."""

    def setup_method(self) -> None:
        """每个测试前重置单例."""
        reset_monitor()

    def teardown_method(self) -> None:
        """每个测试后重置单例."""
        reset_monitor()

    def test_get_monitor_requires_redis_url(self) -> None:
        """未初始化时调用 get_worker_health_monitor 无参数抛出异常."""
        with pytest.raises(RuntimeError, match="未初始化"):
            get_worker_health_monitor()

    def test_get_monitor_creates_singleton(self, mock_redis: MockRedis) -> None:
        """首次调用创建单例."""
        with patch(
            "redis.asyncio.from_url",
            return_value=mock_redis,
        ):
            m1 = get_worker_health_monitor(redis_url="redis://test:6379/0")
            m2 = get_worker_health_monitor()
            assert m1 is m2
            assert has_monitor() is True

    def test_reset_monitor_clears_singleton(self, mock_redis: MockRedis) -> None:
        """reset_monitor 清除单例."""
        with patch(
            "redis.asyncio.from_url",
            return_value=mock_redis,
        ):
            get_worker_health_monitor(redis_url="redis://test:6379/0")
            assert has_monitor() is True

            reset_monitor()
            assert has_monitor() is False

    def test_has_monitor_returns_false_when_not_initialized(self) -> None:
        """未初始化时 has_monitor 返回 False."""
        assert has_monitor() is False


# ── 心跳循环内部测试 ──────────────────────────────────────


class TestHeartbeatLoop:
    """心跳循环内部机制测试."""

    @pytest.mark.asyncio
    async def test_heartbeat_sets_expiry(
        self,
        monitor: WorkerHealthMonitor,
        mock_redis: MockRedis,
    ) -> None:
        """心跳键设置了正确的 TTL."""
        await monitor.start_heartbeat("ttl-test", "ttl-node")

        # 检查过期时间设置
        assert "autotest:worker:heartbeat:ttl-test" in mock_redis._expirations
        assert mock_redis._expirations["autotest:worker:heartbeat:ttl-test"] == 90

        await monitor.stop_heartbeat("ttl-test")

    @pytest.mark.asyncio
    async def test_worker_info_has_longer_ttl(
        self,
        monitor: WorkerHealthMonitor,
        mock_redis: MockRedis,
    ) -> None:
        """Worker 元信息 TTL 为心跳 TTL 的 2 倍."""
        await monitor.start_heartbeat("info-ttl", "info-node")

        info_key = "autotest:worker:info:info-ttl"
        assert info_key in mock_redis._expirations
        assert mock_redis._expirations[info_key] == 180  # 90 * 2

        await monitor.stop_heartbeat("info-ttl")
