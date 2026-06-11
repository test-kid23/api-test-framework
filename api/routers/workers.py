"""Worker 健康监控 API 路由

接口:
- GET  /api/v1/workers          所有 Worker 状态列表
- GET  /api/v1/workers/{id}     单个 Worker 详情
- POST /api/v1/workers/{id}/restart  重启 Worker（预留）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import get_current_user, require_role
from framework.utils.logger import Logger
from framework.worker_health import (
    WorkerHealthMonitor,
    WorkerInfo,
    get_worker_health_monitor,
)

router = APIRouter(prefix="/api/v1/workers", tags=["workers"])
_log = Logger.get("api.workers")


# ── Helpers ───────────────────────────────────────────────


def _get_monitor() -> WorkerHealthMonitor:
    """获取 WorkerHealthMonitor 实例的依赖注入函数。

    Returns:
        WorkerHealthMonitor 实例。

    Raises:
        HTTPException: 监控器未初始化时返回 503。
    """
    try:
        return get_worker_health_monitor()
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Worker 健康监控服务未启动",
        ) from e


def _worker_to_response(worker: WorkerInfo) -> dict:
    """将 WorkerInfo 转换为 API 响应字典。

    Args:
        worker: WorkerInfo 实例。

    Returns:
        API 响应字典。
    """
    return {
        "worker_id": worker.worker_id,
        "hostname": worker.hostname,
        "status": worker.status,
        "last_heartbeat": worker.last_heartbeat.isoformat(),
        "current_task": worker.current_task,
        "uptime_seconds": worker.uptime_seconds,
    }


# ── Routes ────────────────────────────────────────────────


@router.get("")
async def list_workers(
    monitor: WorkerHealthMonitor = Depends(_get_monitor),
    _current_user=Depends(get_current_user),
) -> list[dict]:
    """获取所有 Worker 节点状态列表。

    返回所有注册 Worker 的在线/离线/忙碌状态和心跳信息。
    按 hostname 排序。
    """
    workers = await monitor.get_all_workers()
    _log.debug("list_workers", count=len(workers))
    return [_worker_to_response(w) for w in workers]


@router.get("/{worker_id}")
async def get_worker(
    worker_id: str,
    monitor: WorkerHealthMonitor = Depends(_get_monitor),
    _current_user=Depends(get_current_user),
) -> dict:
    """获取单个 Worker 节点详情。

    Args:
        worker_id: Worker 唯一标识。
    """
    worker = await monitor.get_worker(worker_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker 不存在: {worker_id}",
        )
    _log.debug("get_worker", worker_id=worker_id, status=worker.status)
    return _worker_to_response(worker)


@router.post("/{worker_id}/restart")
async def restart_worker(
    worker_id: str,
    monitor: WorkerHealthMonitor = Depends(_get_monitor),
    _current_user=Depends(require_role("admin")),
) -> dict:
    """重启指定 Worker（预留接口）。

    当前版本仅验证 Worker 存在并返回状态，实际重启功能
    将在后续版本中实现（需集成 Celery 远程控制）。

    Args:
        worker_id: Worker 唯一标识。
    """
    worker = await monitor.get_worker(worker_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker 不存在: {worker_id}",
        )

    _log.info("worker_restart_requested", worker_id=worker_id, hostname=worker.hostname)

    return {
        "message": f"Worker {worker_id} ({worker.hostname}) 重启请求已收到（功能预留）",
        "worker_id": worker_id,
        "hostname": worker.hostname,
        "status": worker.status,
    }


@router.post("/health-check")
async def trigger_health_check(
    monitor: WorkerHealthMonitor = Depends(_get_monitor),
    _current_user=Depends(require_role("admin")),
) -> dict:
    """手动触发一次全量健康检查（含离线告警）。

    此接口会主动检测所有 Worker 状态并对离线节点发送告警通知。
    仅管理员可调用。
    """
    workers = await monitor.check_health()
    online_count = sum(1 for w in workers if w.status == "online")
    offline_count = sum(1 for w in workers if w.status == "offline")
    busy_count = sum(1 for w in workers if w.status == "busy")

    _log.info(
        "health_check_triggered",
        total=len(workers),
        online=online_count,
        offline=offline_count,
        busy=busy_count,
    )

    return {
        "total": len(workers),
        "online": online_count,
        "offline": offline_count,
        "busy": busy_count,
        "workers": [_worker_to_response(w) for w in workers],
    }
