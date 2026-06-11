"""Worker 健康监控 — Redis 心跳机制 + 失联告警

通过 Redis 心跳键实现 Worker 存活检测：
- Worker 启动后每隔 30s 写入心跳键（TTL 90s）
- 健康检查读取所有心跳键，超过 60s 未心跳判定为离线
- 离线 Worker 通过 NotificationService 发送告警

用法:
    import redis.asyncio as aioredis
    from framework.worker_health import WorkerHealthMonitor

    redis_client = aioredis.from_url("redis://localhost:6379/0")
    monitor = WorkerHealthMonitor(redis_client)

    # Worker 启动时注册心跳
    await monitor.start_heartbeat(worker_id="worker-1", hostname="node01")

    # API 查询所有 Worker 状态
    workers = await monitor.get_all_workers()

    # 健康检查（含离线检测与告警）
    health = await monitor.check_health()

    # Worker 关闭时停止心跳
    await monitor.stop_heartbeat(worker_id="worker-1")
"""

from __future__ import annotations

import asyncio
import socket
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

from framework.notifications.service import NotificationService
from framework.utils.logger import Logger

_log = Logger.get("framework.worker_health")

# Redis 心跳键前缀
_HEARTBEAT_KEY_PREFIX = "autotest:worker:heartbeat:"
# 存储 Worker 元信息的键（Hash，与心跳键并存）
_WORKER_INFO_KEY_PREFIX = "autotest:worker:info:"


@dataclass
class WorkerInfo:
    """Worker 节点信息。

    Attributes:
        worker_id: Worker 唯一标识。
        hostname: 主机名。
        status: 当前状态（online / offline / busy）。
        last_heartbeat: 最后一次心跳时间。
        current_task: 当前正在执行的任务 ID（可选）。
        uptime_seconds: 运行时长（秒）。
    """

    worker_id: str
    hostname: str
    status: str  # "online" | "offline" | "busy"
    last_heartbeat: datetime
    current_task: str | None = None
    uptime_seconds: int = 0


class WorkerHealthMonitor:
    """Worker 健康监控器。

    通过 Redis 心跳键实现 Worker 存活检测和失联告警。

    Attributes:
        HEARTBEAT_INTERVAL: 心跳间隔 30s。
        HEARTBEAT_TTL: 心跳键过期时间 90s。
        OFFLINE_THRESHOLD: 失联阈值 60s。
    """

    HEARTBEAT_INTERVAL: int = 30
    HEARTBEAT_TTL: int = 90
    OFFLINE_THRESHOLD: int = 60

    def __init__(
        self,
        redis_client: Redis,
        notification_service: NotificationService | None = None,
    ) -> None:
        """初始化监控器。

        Args:
            redis_client: Redis 异步客户端。
            notification_service: 通知服务（用于失联告警），为 None 时跳过告警。
        """
        self._redis = redis_client
        self._notification_service = notification_service
        # 存储活跃心跳任务的内部状态
        self._heartbeat_tasks: dict[str, asyncio.Task[None]] = {}
        # 已告警的 Worker ID 集合（去重，避免重复告警）
        self._alerted_workers: set[str] = set()

    # ── 心跳生命周期 ────────────────────────────────────────

    async def start_heartbeat(self, worker_id: str, hostname: str | None = None) -> None:
        """启动心跳循环。

        在后台启动一个 asyncio.Task，每隔 HEARTBEAT_INTERVAL 秒向 Redis
        写入心跳键。同时写入 Worker 元信息到 Hash 键中。

        Args:
            worker_id: Worker 唯一标识。
            hostname: 主机名，为 None 时自动检测。
        """
        if hostname is None:
            hostname = socket.gethostname()

        # 存储 Worker 元信息
        await self._save_worker_info(worker_id, hostname)

        # 写入初始心跳
        await self._send_heartbeat(worker_id, hostname)

        # 启动后台心跳任务
        if worker_id in self._heartbeat_tasks:
            _log.warning(
                "heartbeat_already_running",
                worker_id=worker_id,
            )
            return

        task = asyncio.create_task(
            self._heartbeat_loop(worker_id, hostname),
            name=f"heartbeat-{worker_id}",
        )
        self._heartbeat_tasks[worker_id] = task

        _log.info(
            "heartbeat_started",
            worker_id=worker_id,
            hostname=hostname,
            interval_s=self.HEARTBEAT_INTERVAL,
        )

    async def stop_heartbeat(self, worker_id: str) -> None:
        """停止心跳并清理 Redis 键。

        Args:
            worker_id: Worker 唯一标识。
        """
        # 取消后台任务
        task = self._heartbeat_tasks.pop(worker_id, None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # 清理 Redis 键
        heartbeat_key = f"{_HEARTBEAT_KEY_PREFIX}{worker_id}"
        info_key = f"{_WORKER_INFO_KEY_PREFIX}{worker_id}"
        try:
            await self._redis.delete(heartbeat_key, info_key)
        except Exception as e:
            _log.warning(
                "heartbeat_cleanup_failed",
                worker_id=worker_id,
                error=str(e),
            )

        # 从已告警集合中移除（Worker 正常下线）
        self._alerted_workers.discard(worker_id)

        _log.info("heartbeat_stopped", worker_id=worker_id)

    # ── 健康检查 ────────────────────────────────────────────

    async def get_all_workers(self) -> list[WorkerInfo]:
        """获取所有 Worker 节点信息。

        扫描 Redis 中所有心跳键，根据最后心跳时间判定在线/离线状态。

        Returns:
            WorkerInfo 列表，按 hostname 排序。
        """
        workers: list[WorkerInfo] = []
        now = datetime.now(timezone.utc)

        # 扫描所有心跳键
        pattern = f"{_HEARTBEAT_KEY_PREFIX}*"
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(cursor=cursor, match=pattern)
            for key_bytes in keys:
                key = key_bytes.decode("utf-8") if isinstance(key_bytes, bytes) else key_bytes
                worker_id = key[len(_HEARTBEAT_KEY_PREFIX):]
                worker_info = await self._build_worker_info(worker_id, now)
                if worker_info is not None:
                    workers.append(worker_info)

            if cursor == 0:
                break

        workers.sort(key=lambda w: w.hostname)
        return workers

    async def get_worker(self, worker_id: str) -> WorkerInfo | None:
        """获取单个 Worker 节点信息。

        Args:
            worker_id: Worker 唯一标识。

        Returns:
            WorkerInfo 或 None（Worker 不存在）。
        """
        heartbeat_key = f"{_HEARTBEAT_KEY_PREFIX}{worker_id}"
        exists = await self._redis.exists(heartbeat_key)
        if not exists:
            return None

        now = datetime.now(timezone.utc)
        return await self._build_worker_info(worker_id, now)

    async def check_health(self) -> list[WorkerInfo]:
        """健康检查并触发失联告警。

        与 get_all_workers 类似，但额外检测离线 Worker 并通过
        NotificationService 发送告警通知。

        Returns:
            所有 Worker 信息（含失联标记）。
        """
        workers = await self.get_all_workers()

        offline_workers = [w for w in workers if w.status == "offline"]

        if offline_workers and self._notification_service is not None:
            # 对新离线 Worker 发送告警（已告警的不重复）
            new_offline = [
                w for w in offline_workers if w.worker_id not in self._alerted_workers
            ]

            for worker in new_offline:
                await self._send_offline_alert(worker)
                self._alerted_workers.add(worker.worker_id)

        # 清理已恢复的 Worker（从告警集合中移除）
        # 只清理当前在线的 Worker，保留仍离线的 Worker 告警状态
        online_ids = {w.worker_id for w in workers if w.status == "online"}
        recovered = self._alerted_workers & online_ids
        if recovered:
            _log.info(
                "worker_recovered",
                worker_ids=list(recovered),
            )
        self._alerted_workers -= recovered

        return workers

    # ── 内部方法 ────────────────────────────────────────────

    async def _heartbeat_loop(self, worker_id: str, hostname: str) -> None:
        """心跳循环协程。

        在后台无限循环，每隔 HEARTBEAT_INTERVAL 秒发送一次心跳。
        异常时记录日志但不退出循环。

        Args:
            worker_id: Worker 唯一标识。
            hostname: 主机名。
        """
        while True:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                await self._send_heartbeat(worker_id, hostname)
            except asyncio.CancelledError:
                _log.debug("heartbeat_loop_cancelled", worker_id=worker_id)
                break
            except Exception as e:
                _log.error(
                    "heartbeat_send_failed",
                    worker_id=worker_id,
                    error=str(e),
                    exc_info=True,
                )

    async def _send_heartbeat(self, worker_id: str, hostname: str) -> None:
        """向 Redis 写入心跳键。

        Args:
            worker_id: Worker 唯一标识。
            hostname: 主机名。
        """
        heartbeat_key = f"{_HEARTBEAT_KEY_PREFIX}{worker_id}"
        timestamp = datetime.now(timezone.utc).isoformat()

        await self._redis.set(
            heartbeat_key,
            timestamp,
            ex=self.HEARTBEAT_TTL,
        )

        # 更新 Worker 元信息中的心跳时间
        info_key = f"{_WORKER_INFO_KEY_PREFIX}{worker_id}"
        await self._redis.hset(info_key, "last_heartbeat", timestamp)

    async def _save_worker_info(self, worker_id: str, hostname: str) -> None:
        """保存 Worker 元信息到 Redis Hash。

        Args:
            worker_id: Worker 唯一标识。
            hostname: 主机名。
        """
        info_key = f"{_WORKER_INFO_KEY_PREFIX}{worker_id}"
        now = datetime.now(timezone.utc).isoformat()
        await self._redis.hset(
            info_key,
            mapping={
                "worker_id": worker_id,
                "hostname": hostname,
                "started_at": now,
                "last_heartbeat": now,
                "current_task": "",
            },
        )
        # 设置较长的过期时间，使元信息比心跳键更持久
        await self._redis.expire(info_key, self.HEARTBEAT_TTL * 2)

    async def _build_worker_info(
        self,
        worker_id: str,
        now: datetime,
    ) -> WorkerInfo | None:
        """根据 Redis 数据构建 WorkerInfo 对象。

        Args:
            worker_id: Worker 唯一标识。
            now: 当前 UTC 时间。

        Returns:
            WorkerInfo 或 None（数据不完整时）。
        """
        info_key = f"{_WORKER_INFO_KEY_PREFIX}{worker_id}"
        raw = await self._redis.hgetall(info_key)
        if not raw:
            return None

        def _decode(v: bytes | str) -> str:
            return v.decode("utf-8") if isinstance(v, bytes) else v

        hostname = _decode(raw.get(b"hostname", raw.get("hostname", "")))
        started_at_str = _decode(raw.get(b"started_at", raw.get("started_at", "")))
        heartbeat_str = _decode(raw.get(b"last_heartbeat", raw.get("last_heartbeat", "")))
        current_task = _decode(raw.get(b"current_task", raw.get("current_task", "")))

        # 解析心跳时间
        last_heartbeat: datetime
        try:
            last_heartbeat = datetime.fromisoformat(heartbeat_str)
        except (ValueError, TypeError):
            last_heartbeat = now

        # 判定在线/离线状态
        elapsed = (now - last_heartbeat).total_seconds()
        if elapsed > self.OFFLINE_THRESHOLD:
            status = "offline"
        elif current_task:
            status = "busy"
        else:
            status = "online"

        # 计算运行时长
        uptime_seconds = 0
        if started_at_str:
            try:
                started_at = datetime.fromisoformat(started_at_str)
                uptime_seconds = int((now - started_at).total_seconds())
            except (ValueError, TypeError):
                pass

        return WorkerInfo(
            worker_id=worker_id,
            hostname=hostname or "unknown",
            status=status,
            last_heartbeat=last_heartbeat,
            current_task=current_task if current_task else None,
            uptime_seconds=max(uptime_seconds, 0),
        )

    async def _send_offline_alert(self, worker: WorkerInfo) -> None:
        """发送 Worker 离线告警。

        Args:
            worker: 离线的 Worker 信息。
        """
        if self._notification_service is None:
            return

        try:
            elapsed = int(
                (datetime.now(timezone.utc) - worker.last_heartbeat).total_seconds()
            )
            message = (
                f"> Worker: **{worker.worker_id}**\n"
                f"> 主机: **{worker.hostname}**\n"
                f"> 最后心跳: {worker.last_heartbeat.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"> 失联时长: **{elapsed}s**\n"
                f"> 当前任务: {worker.current_task or '无'}\n"
            )

            await self._notification_service.send_alert(
                title=f"Worker 离线告警 - {worker.hostname}",
                level="warning",
                message=message,
            )
            _log.info(
                "worker_offline_alert_sent",
                worker_id=worker.worker_id,
                hostname=worker.hostname,
                elapsed_s=elapsed,
            )
        except Exception as e:
            _log.error(
                "worker_offline_alert_failed",
                worker_id=worker.worker_id,
                error=str(e),
                exc_info=True,
            )


# ═══════════════════════════════════════════════════════════
# 全局单例管理
# ═══════════════════════════════════════════════════════════

_monitor: WorkerHealthMonitor | None = None


def get_worker_health_monitor(
    redis_url: str = "",
    notification_service: NotificationService | None = None,
) -> WorkerHealthMonitor:
    """获取全局 WorkerHealthMonitor 单例。

    首次调用时需提供 redis_url，后续调用可不传参数直接获取已存在的实例。

    Args:
        redis_url: Redis 连接 URL（首次初始化时必需）。
        notification_service: 通知服务（可选）。

    Returns:
        WorkerHealthMonitor 实例。

    Raises:
        RuntimeError: 监控器未初始化且未提供 redis_url。
    """
    global _monitor
    if _monitor is None:
        if not redis_url:
            raise RuntimeError(
                "WorkerHealthMonitor 未初始化，首次调用需提供 redis_url"
            )
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        _monitor = WorkerHealthMonitor(
            redis_client=redis_client,
            notification_service=notification_service,
        )
    return _monitor


def has_monitor() -> bool:
    """检查 WorkerHealthMonitor 是否已初始化。"""
    return _monitor is not None


def reset_monitor() -> None:
    """重置监控器单例（仅供测试使用）。"""
    global _monitor
    _monitor = None
