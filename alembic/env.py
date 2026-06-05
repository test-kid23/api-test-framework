"""Alembic 环境配置 — 异步数据库迁移支持"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

# Alembic Config 对象
config = context.config

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── 导入所有 ORM 模型的 Base.metadata ──
from framework.persistence.models import Base  # noqa: E402

target_metadata = Base.metadata

# ── 数据库 URL ──
# 优先级: AUTOTEST_DB_URL 环境变量 > alembic.ini 中的 sqlalchemy.url
_db_url = os.environ.get("AUTOTEST_DB_URL") or config.get_main_option("sqlalchemy.url")


def _ensure_async_driver(url: str) -> str:
    """确保使用异步驱动。"""
    if "+aiosqlite" in url or "+asyncpg" in url or "+aiomysql" in url:
        return url
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    return url


_url = _ensure_async_driver(_db_url)


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本而不连接数据库。"""
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """在同步连接上执行迁移。"""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """在线模式：连接数据库并执行迁移（异步引擎）。"""
    connectable = _create_async_engine(
        _url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # run_sync 将异步连接转换为同步连接供 Alembic 使用
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
