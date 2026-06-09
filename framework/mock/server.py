"""Mock 服务器 — FastAPI 子应用

嵌入到主 FastAPI 应用中，提供内嵌的 HTTP Mock 服务。
支持任意 URL 路径，根据注册的规则返回预设响应。

作为 FastAPI 子应用挂载，路径前缀为 /_mock：
  - /_mock/admin/rules  → 规则管理 API
  - /_mock/{path}       → Mock 请求处理
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from framework.mock.models import MockRule
from framework.mock.rule_store import MockRuleStore, get_mock_store
from framework.utils.logger import Logger

logger = Logger.get("mock.server")


def create_mock_app(store: MockRuleStore | None = None) -> FastAPI:
    """创建 Mock 服务器 FastAPI 子应用。

    Args:
        store: MockRuleStore 实例，不传则使用全局单例。

    Returns:
        FastAPI 子应用实例。
    """
    _store = store or get_mock_store()

    app = FastAPI(
        title="AutoTest Mock Server",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # ── 规则管理 API ──────────────────────────────────

    @app.get("/admin/rules")
    async def list_rules() -> dict[str, Any]:
        """列出所有 Mock 规则"""
        rules = _store.list_all()
        return {
            "total": len(rules),
            "rules": [_rule_to_dict(r) for r in rules],
        }

    @app.post("/admin/rules")
    async def create_rule(body: dict[str, Any]) -> dict[str, Any]:
        """注册一条 Mock 规则

        请求体示例:
        {
            "url_pattern": "/api/users/*",
            "method": "POST",
            "status_code": 201,
            "response_body": {"id": 1, "name": "test"},
            "description": "创建用户 Mock"
        }
        """
        rule = _store.register(
            url_pattern=body.get("url_pattern", "/*"),
            method=body.get("method", "ANY"),
            status_code=body.get("status_code", 200),
            response_body=body.get("response_body"),
            response_headers=body.get("response_headers"),
            description=body.get("description", ""),
            priority=body.get("priority", 0),
            delay_ms=body.get("delay_ms", 0),
            rule_id=body.get("id"),
        )
        return _rule_to_dict(rule)

    @app.get("/admin/rules/{rule_id}")
    async def get_rule(rule_id: str) -> dict[str, Any]:
        """获取单条规则"""
        rule = _store.get(rule_id)
        if rule is None:
            return {"error": "规则不存在", "rule_id": rule_id}
        return _rule_to_dict(rule)

    @app.put("/admin/rules/{rule_id}")
    async def update_rule(rule_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """更新一条规则"""
        rule = _store.update(rule_id, **body)
        if rule is None:
            return {"error": "规则不存在", "rule_id": rule_id}
        return _rule_to_dict(rule)

    @app.delete("/admin/rules/{rule_id}")
    async def delete_rule(rule_id: str) -> dict[str, Any]:
        """删除单条规则"""
        deleted = _store.delete(rule_id)
        return {"deleted": deleted, "rule_id": rule_id}

    @app.delete("/admin/rules")
    async def clear_rules() -> dict[str, Any]:
        """清空所有规则"""
        count = _store.clear()
        return {"deleted_count": count}

    # ── Mock 请求处理（Catch-all）───────────────

    @app.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    )
    async def mock_handler(request: Request, path: str = "") -> Response:
        """处理 Mock 请求 — 匹配规则并返回预设响应。

        对于 HEAD 和 OPTIONS 请求跳过匹配直接返回 200。
        其他请求按优先级匹配规则，未命中返回 404。
        """
        req_path = f"/{path}" if path else "/"
        req_method = request.method

        logger.debug(
            "mock_request_received",
            path=req_path,
            method=req_method,
        )

        # HEAD / OPTIONS 直接放行
        if req_method in ("HEAD", "OPTIONS"):
            return Response(status_code=200)

        # 查找匹配规则
        rule = _store.match(req_path, req_method)
        if rule is None:
            logger.debug("mock_no_match", path=req_path, method=req_method)
            return JSONResponse(
                status_code=404,
                content={
                    "error": "No mock rule matched",
                    "path": req_path,
                    "method": req_method,
                },
            )

        # 模拟延迟
        if rule.delay_ms > 0:
            time.sleep(rule.delay_ms / 1000.0)

        # 构建响应
        return _build_response(rule)

    return app


def _rule_to_dict(rule: MockRule) -> dict[str, Any]:
    """将 MockRule 转为可序列化的字典"""
    return {
        "id": rule.id,
        "url_pattern": rule.url_pattern,
        "method": rule.method,
        "status_code": rule.status_code,
        "response_body": rule.response_body,
        "response_headers": rule.response_headers,
        "description": rule.description,
        "enabled": rule.enabled,
        "priority": rule.priority,
        "delay_ms": rule.delay_ms,
    }


def _build_response(rule: MockRule) -> Response:
    """根据规则构建 HTTP 响应"""
    headers = dict(rule.response_headers)

    body = rule.response_body
    if isinstance(body, dict):
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        return JSONResponse(
            status_code=rule.status_code,
            content=body,
            headers=headers,
        )
    elif isinstance(body, str):
        if "Content-Type" not in headers:
            headers["Content-Type"] = "text/plain"
        return PlainTextResponse(
            status_code=rule.status_code,
            content=body,
            headers=headers,
        )
    else:
        return Response(
            status_code=rule.status_code,
            headers=headers,
        )
