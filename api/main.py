"""FastAPI 应用入口

启动服务: uvicorn api.main:app --reload
访问 Swagger: http://localhost:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import cases, environments, executions, reports, schedules, suites
from api.schemas.common import ErrorDetail, ErrorResponse
from framework.scheduler import get_scheduler
from framework.utils.logger import Logger

# ==================== 应用描述 ====================

DESCRIPTION = """
## AutoTest Framework REST API

企业级 API 自动化测试框架的 REST 服务层。

### 核心功能

- **用例管理**: CRUD 操作，标签/优先级分类，版本历史
- **OpenAPI 导入**: 从 OpenAPI 3.x / Swagger spec 一键导入测试用例
- **套件管理**: 将多个用例组合为测试套件
- **执行管理**: 触发执行，查询执行状态和结果
- **报告查询**: 执行报告、通过率趋势、失败分析

### 版本路线

| 版本 | 状态 | 说明 |
|------|------|------|
| v2.0.0-alpha | 🚧 开发中 | T2-1: FastAPI REST 服务层（当前） |
| v2.0.0 | 📋 计划中 | T2-2: PostgreSQL 持久化 |
| v3.0.0 | 📋 计划中 | Phase 4: 完整测试平台 |
"""

TAGS_METADATA = [
    {"name": "cases", "description": "测试用例 CRUD 操作"},
    {"name": "suites", "description": "测试套件管理"},
    {"name": "executions", "description": "执行触发与结果查询"},
    {"name": "reports", "description": "报告查询与分析"},
    {"name": "schedules", "description": "定时调度管理"},
    {"name": "environments", "description": "环境配置管理"},
]


# ==================== 生命周期 ====================

_log = Logger.get("api.main")


def _to_sync_db_url(async_url: str) -> str:
    """将异步数据库 URL 转换为同步 URL（供 APScheduler SQLAlchemyJobStore 使用）。

    Args:
        async_url: 异步驱动 URL，如 postgresql+asyncpg://... 或 sqlite+aiosqlite://...

    Returns:
        同步驱动 URL，如 postgresql://... 或 sqlite:///...
    """
    if "+aiosqlite" in async_url:
        return async_url.replace("+aiosqlite", "")
    if "+asyncpg" in async_url:
        return async_url.replace("+asyncpg", "")
    if "+aiomysql" in async_url:
        return async_url.replace("+aiomysql", "+pymysql")
    return async_url


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用启动/关闭时的生命周期管理"""
    import os

    # ── 启动调度器 ──
    try:
        from api.dependencies import _init_db, _session_factory

        # 确保数据库已初始化
        _init_db()

        # 获取数据库 URL
        dsn_override = os.environ.get("AUTOTEST_DB_URL")
        if dsn_override:
            sync_url = _to_sync_db_url(dsn_override)
        else:
            from framework.config import ConfigLoader

            loader = ConfigLoader()
            project_config, _ = loader.load()
            db_config = project_config.db
            # 构建同步 URL
            if hasattr(db_config, "dsn"):
                sync_url = _to_sync_db_url(db_config.dsn)
            else:
                sync_url = "sqlite:///data/autotest.db"

        scheduler = get_scheduler(_session_factory, sync_url)
        await scheduler.start()
        _log.info("scheduler_lifecycle_started")
    except Exception as e:
        _log.error("scheduler_lifecycle_start_failed", error=str(e))

    yield

    # ── 关闭调度器 ──
    try:
        from framework.scheduler import _scheduler

        if _scheduler is not None:
            await _scheduler.stop()
            _log.info("scheduler_lifecycle_stopped")
    except Exception as e:
        _log.error("scheduler_lifecycle_stop_failed", error=str(e))


# ==================== App 工厂 ====================


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例"""

    app = FastAPI(
        title="AutoTest Framework API",
        description=DESCRIPTION,
        version="2.0.0-alpha",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=TAGS_METADATA,
        lifespan=lifespan,
    )

    # ── CORS 中间件 ──────────────────────────────────

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应限制为具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── 路由注册 ─────────────────────────────────────

    app.include_router(cases.router)
    app.include_router(suites.router)
    app.include_router(executions.router)
    app.include_router(reports.router)
    app.include_router(schedules.router)
    app.include_router(environments.router)

    # ── 根路径 ───────────────────────────────────────

    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "name": "AutoTest Framework API",
            "version": "2.0.0-alpha",
            "docs": "/docs",
            "status": "running",
        }

    # ── 健康检查 ────────────────────────────────────

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"status": "healthy"}

    # ── 全局异常处理器 ──────────────────────────────

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="请求参数无效",
                detail=[ErrorDetail(loc=[], msg=str(exc), type="value_error")],
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="服务器内部错误",
                detail=[ErrorDetail(loc=[], msg=str(exc), type="internal_error")],
            ).model_dump(),
        )

    return app


# ==================== 应用实例 ====================

app = create_app()
