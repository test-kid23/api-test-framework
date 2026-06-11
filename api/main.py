"""FastAPI 应用入口

启动服务: uvicorn api.main:app --reload
访问 Swagger: http://localhost:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from api.routers import analytics, assertions, auth, cases, coverage, environments, executions, mocks, recorder, reports, schedules, suites, users, workers
from api.schemas.common import ErrorDetail, ErrorResponse
from framework.mock.server import create_mock_app
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
    {"name": "auth", "description": "用户认证与授权"},
    {"name": "cases", "description": "测试用例 CRUD 操作"},
    {"name": "suites", "description": "测试套件管理"},
    {"name": "executions", "description": "执行触发与结果查询"},
    {"name": "reports", "description": "报告查询与分析"},
    {"name": "schedules", "description": "定时调度管理"},
    {"name": "environments", "description": "环境配置管理"},
    {"name": "mocks", "description": "Mock 规则管理"},
    {"name": "recorder", "description": "流量录制与回放"},
    {"name": "smart-assertions", "description": "智能断言 — Schema 推断与变更检测"},
    {"name": "analytics", "description": "高级分析 — 稳定性排行、分位数、失败分类、ROI"},
    {"name": "coverage", "description": "覆盖率分析 — OpenAPI 覆盖率、缺口识别、智能生成"},
    {"name": "users", "description": "用户管理（admin）"},
    {"name": "workers", "description": "Worker 健康监控 — 在线状态、心跳检测、离线告警"},
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

    # ── 数据库初始化 ──
    import api.dependencies as deps

    deps._init_db()

    # ── 首次启动初始化（建表 + 默认管理员） ──
    if deps._engine is not None:
        try:
            from api.init import init_app

            await init_app(deps._engine, deps._session_factory)
        except Exception as e:
            _log.error("init_app_failed", error=str(e), exc_info=True)

    # ── 启动调度器 ──
    try:
        # 获取数据库 URL（同步引擎 URL，供 APScheduler SQLAlchemyJobStore 使用）
        dsn_override = os.environ.get("AUTOTEST_DB_URL")
        if dsn_override:
            sync_url = _to_sync_db_url(dsn_override)
        else:
            from framework.persistence.database import get_db_url
            from framework.config import ConfigLoader

            loader = ConfigLoader()
            project_config, _ = loader.load()
            async_url = get_db_url(project_config.db)
            sync_url = _to_sync_db_url(async_url)

        # 通过模块属性访问 _session_factory，而非导入时的快照值
        scheduler = get_scheduler(deps._session_factory, sync_url)
        await scheduler.start()
        _log.info("scheduler_started")
    except Exception as e:
        _log.error("scheduler_start_failed", error=str(e), exc_info=True)

    # ── 初始化 Worker 健康监控 ──
    try:
        from framework.config import ConfigLoader

        loader = ConfigLoader()
        project_config, _ = loader.load()
        celery_config: dict = project_config.execution.get("celery", {})
        redis_url = celery_config.get("broker_url", "redis://localhost:6379/0")

        # 尝试初始化 NotificationService（用于离线告警）
        notification_service = None
        try:
            notifications_config = project_config.notifications
            if notifications_config:
                from framework.notifications.service import NotificationService
                notification_service = NotificationService.from_config(
                    notifications_config.model_dump() if hasattr(notifications_config, 'model_dump') else {},
                    "",
                )
        except Exception:
            pass

        from framework.worker_health import get_worker_health_monitor

        get_worker_health_monitor(
            redis_url=redis_url,
            notification_service=notification_service,
        )
        _log.info("worker_health_monitor_initialized")
    except Exception as e:
        _log.error("worker_health_monitor_init_failed", error=str(e), exc_info=True)

    # ── Mock 规则从 DB 加载到内存 ──
    try:
        from framework.mock.rule_store import get_mock_store
        from framework.persistence.repositories.mock_rule_repo import MockRuleRepository

        mock_store = get_mock_store()
        async with deps._session_factory() as session:
            repo = MockRuleRepository(session)
            enabled_rules = await repo.list_all_enabled()
            await mock_store.load_from_db(enabled_rules)
        _log.info("mock_rules_loaded_from_db_on_startup")
    except Exception as e:
        _log.error("mock_rules_load_from_db_failed", error=str(e), exc_info=True)

    yield

    # ── 关闭调度器 ──
    try:
        from framework.scheduler import _scheduler

        if _scheduler is not None:
            await _scheduler.stop()
            _log.info("scheduler_lifecycle_stopped")
    except Exception as e:
        _log.error("scheduler_lifecycle_stop_failed", error=str(e), exc_info=True)


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

    app.include_router(auth.router)
    app.include_router(cases.router)
    app.include_router(suites.router)
    app.include_router(executions.router)
    app.include_router(reports.router)
    app.include_router(analytics.router)
    app.include_router(coverage.router)
    app.include_router(schedules.router)
    app.include_router(environments.router)
    app.include_router(mocks.router)
    app.include_router(recorder.router)
    app.include_router(assertions.router)
    app.include_router(users.router)
    app.include_router(workers.router)

    # ── Mock 服务器子应用 ────────────────────────────
    app.mount("/_mock", create_mock_app())

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

    # ── OpenAPI Security Scheme ────────────────────
    # 将 Bearer Token 认证添加到 Swagger UI，使"Authorize"按钮可见

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
        )
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "输入登录接口返回的 access_token（格式：Bearer {token}）",
            }
        }
        # 不设置全局 security 要求，各端点自行通过 Depends 声明
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    # ── 全局异常处理器 ──────────────────────────────

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        _log.warning(
            "value_error_caught",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True,
        )
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
