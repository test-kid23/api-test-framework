"""AsyncEngine 工厂 — 支持 SQLite 和 PostgreSQL

用法：
    from framework.config import ConfigLoader
    from framework.persistence.database import create_async_engine

    loader = ConfigLoader()
    project_config, _ = loader.load()
    engine = create_async_engine(project_config.db)
"""

from __future__ import annotations

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
    return engine


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
