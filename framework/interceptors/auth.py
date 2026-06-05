"""认证拦截器 — 自动为请求添加认证信息

支持 Bearer Token 和 HTTP Basic Auth 两种模式。
从原始 client.py 的 auth 逻辑迁移而来。
"""

from __future__ import annotations

from typing import Any

import httpx

from framework.interceptors.base import RequestInterceptor
from framework.models import HttpRequest, HttpResponse


class AuthInterceptor(RequestInterceptor):
    """自动认证拦截器。

    检查 HttpRequest.auth 字段，根据类型添加认证信息：
    - bearer：设置 Authorization: Bearer <token> 头
    - basic：通过 context["httpx_kwargs"]["auth"] 传递 BasicAuth

    可以通过 add_interceptor() 预先注册，或在每个请求上设置 auth 字段。
    """

    def on_request(
        self, request: HttpRequest, context: dict[str, Any]
    ) -> HttpRequest:
        if not request.auth:
            return request

        auth_type = request.auth.get("type", "bearer").lower()

        if auth_type == "bearer":
            request.headers["Authorization"] = (
                f"Bearer {request.auth.get('token', '')}"
            )

        elif auth_type == "basic":
            context.setdefault("httpx_kwargs", {})
            context["httpx_kwargs"]["auth"] = httpx.BasicAuth(
                request.auth.get("username", ""),
                request.auth.get("password", ""),
            )

        return request

    def on_response(
        self, response: HttpResponse, context: dict[str, Any]
    ) -> HttpResponse:
        # 认证拦截器对响应不做处理
        return response
