"""Celery 应用工厂

从配置文件的 execution.celery 段创建 Celery 实例。

Usage:
    # Worker 启动命令
    celery -A worker.celery_app worker --loglevel=info --concurrency=4

    # 在代码中获取 app 实例
    from worker.celery_app import get_celery_app
    app = get_celery_app()
"""

from __future__ import annotations

import threading

from celery import Celery

from framework.config import ConfigLoader
from framework.utils.logger import Logger

_log = Logger.get("worker.celery_app")

_celery_app: Celery | None = None
_app_lock = threading.Lock()


def get_celery_app() -> Celery:
    """获取 Celery 应用单例

    延迟初始化：首次调用时从配置文件读取 Celery 配置并创建实例。
    线程安全。

    Returns:
        已配置的 Celery 应用实例
    """
    global _celery_app

    if _celery_app is not None:
        return _celery_app

    with _app_lock:
        if _celery_app is not None:
            return _celery_app

        loader = ConfigLoader()
        project_config, _ = loader.load()
        celery_config: dict = project_config.execution.get("celery", {})

        broker_url = celery_config.get("broker_url", "redis://localhost:6379/0")
        result_backend = celery_config.get("result_backend", "redis://localhost:6379/0")

        _celery_app = Celery(
            "autotest",
            broker=broker_url,
            backend=result_backend,
            include=["worker.tasks"],
        )

        _celery_app.conf.update(
            task_serializer=celery_config.get("task_serializer", "json"),
            result_serializer=celery_config.get("result_serializer", "json"),
            task_track_started=celery_config.get("task_track_started", True),
            worker_concurrency=celery_config.get("worker_concurrency", 4),
            task_acks_late=True,
            task_reject_on_worker_lost=True,
            worker_prefetch_multiplier=1,
            result_expires=3600,  # 结果过期 1 小时
        )

        _log.info(
            "celery_app_created",
            broker=broker_url,
            backend=result_backend,
        )

        return _celery_app


# 模块级实例：供 celery CLI 使用（-A worker.celery_app）
celery_app = get_celery_app()
