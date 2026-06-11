"""AsyncEngine 工厂 — 支持 SQLite 和 PostgreSQL

用法：
    from framework.config import ConfigLoader
    from framework.persistence.database import create_async_engine

    loader = ConfigLoader()
    project_config, _ = loader.load()
    engine = create_async_engine(project_config.db)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine as _create_async_engine

from framework.utils.logger import Logger

logger = Logger.get("persistence")


def get_db_url(db_config: dict[str, Any]) -> str:
    """根据配置构建异步数据库连接 URL。

    Args:
        db_config: 字典，包含 driver, dsn 等字段。
                   若提供了 dsn，优先使用 dsn。

    Returns:
        SQLAlchemy 异步连接 URL 字符串。

    Raises:
        ValueError: driver 类型不支持。
    """
    raw_dsn: str = db_config.get("dsn", "")
    if raw_dsn:
        return _ensure_async_scheme(raw_dsn)

    driver: str = db_config.get("driver", "sqlite")

    if driver == "sqlite":
        database = db_config.get("database", "data/test.db")
        # 确保数据库文件的父目录存在（换环境首次启动时 data/ 可能不存在）
        db_path = Path(database)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{database}"
    elif driver == "postgresql":
        host = db_config.get("host", "localhost")
        port = db_config.get("port", 5432)
        user = db_config.get("user", "postgres")
        password = db_config.get("password", "")
        database = db_config.get("database", "autotest")
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    elif driver == "mysql":
        host = db_config.get("host", "localhost")
        port = db_config.get("port", 3306)
        user = db_config.get("user", "root")
        password = db_config.get("password", "")
        database = db_config.get("database", "autotest")
        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"
    else:
        raise ValueError(f"不支持的数据库驱动: {driver}")


def _ensure_async_scheme(dsn: str) -> str:
    """确保 DSN 使用异步驱动方案。

    自动将同步驱动替换为异步驱动：
    - sqlite:/// → sqlite+aiosqlite:///
    - postgresql:// → postgresql+asyncpg://
    - postgresql+psycopg2:// → postgresql+asyncpg://
    - mysql+pymysql:// → mysql+aiomysql://
    """
    replacements = [
        ("sqlite:///", "sqlite+aiosqlite:///"),
        ("postgresql+psycopg2://", "postgresql+asyncpg://"),
        ("postgresql://", "postgresql+asyncpg://"),
        ("mysql+pymysql://", "mysql+aiomysql://"),
        ("mysql://", "mysql+aiomysql://"),
    ]
    for old, new in replacements:
        if dsn.startswith(old):
            return dsn.replace(old, new, 1)
    return dsn


def create_async_engine(
    db_config: dict[str, Any],
    echo: bool = False,
) -> AsyncEngine:
    """创建 AsyncEngine 实例。

    Args:
        db_config: 数据库配置字典。
        echo: 是否打印 SQL 语句（调试用）。

    Returns:
        SQLAlchemy AsyncEngine 实例。
    """
    url = get_db_url(db_config)
    logger.info(f"创建数据库引擎: driver={db_config.get('driver', 'auto')}")

    connect_args: dict[str, Any] = {}
    if "aiosqlite" in url:
        connect_args["check_same_thread"] = False

    # SQLite 不支持 pool_size/max_overflow，仅对非 SQLite 设置
    engine_kwargs: dict[str, Any] = {
        "echo": echo,
        "connect_args": connect_args,
        "pool_pre_ping": db_config.get("pool_pre_ping", True),
    }
    if "aiosqlite" not in url:
        engine_kwargs["pool_size"] = db_config.get("pool_size", 5)
        engine_kwargs["max_overflow"] = db_config.get("max_overflow", 10)

    engine = _create_async_engine(url, **engine_kwargs)

    # SQLite: 启用 WAL 模式以支持并发读写（读不阻塞写，写不阻塞读）
    if "aiosqlite" in url:
        _enable_sqlite_wal(engine)

    return engine


def _enable_sqlite_wal(engine: AsyncEngine) -> None:
    """为 SQLite 启用 WAL 模式，提升并发性能。

    WAL (Write-Ahead Logging) 模式下：
    - 读操作不会阻塞写操作
    - 写操作不会阻塞读操作
    - 并发性能显著提升

    Args:
        engine: SQLAlchemy AsyncEngine（SQLite 驱动）。
    """
    import asyncio

    async def _set_wal() -> None:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            await conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
            await conn.commit()
        logger.info("sqlite_wal_enabled")

    try:
        # 在事件循环中执行（如果当前没有运行中的事件循环，用 asyncio.run）
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 在已有事件循环中，创建新 task 执行
            import threading

            def _run_in_thread() -> None:
                new_loop = asyncio.new_event_loop()
                new_loop.run_until_complete(_set_wal())
                new_loop.close()

            t = threading.Thread(target=_run_in_thread, daemon=True)
            t.start()
            t.join(timeout=5)
        else:
            loop.run_until_complete(_set_wal())
    except RuntimeError:
        asyncio.run(_set_wal())


def create_async_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker:
    """创建异步 session 工厂。

    Args:
        engine: AsyncEngine 实例。

    Returns:
        async_sessionmaker 实例。
    """
    return async_sessionmaker(
        engine,
        expire_on_commit=False,
    )
