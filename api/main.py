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

from api.routers import cases, executions, reports, suites
from api.schemas.common import ErrorDetail, ErrorResponse

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
]


# ==================== 生命周期 ====================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用启动/关闭时的生命周期管理"""
    # 启动时
    yield
    # 关闭时


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
