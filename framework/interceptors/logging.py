"""日志拦截器 — 记录请求/响应的结构化日志

将日志记录逻辑从 HttpClient 核心分离，使 client 逻辑更聚焦。
"""

from __future__ import annotations

import json
from typing import Any

from framework.interceptors.base import RequestInterceptor
from framework.models import HttpRequest, HttpResponse
from framework.utils.logger import Logger

logger = Logger.get("client")


class LoggingInterceptor(RequestInterceptor):
    """请求/响应日志记录拦截器。

    职责：
    - on_request：记录请求方法、路径、请求体（DEBUG）、请求头（DEBUG）
    - on_response：记录响应状态码、耗时、内容长度、响应头（DEBUG）

    所有敏感数据通过 Logger.mask_sensitive / mask_sensitive_str 脱敏。
    """

    def on_request(
        self, request: HttpRequest, context: dict[str, Any]
    ) -> HttpRequest:
        logger.info(
            "request_started",
            method=request.method.value,
            url=request.path,
            body_type=request.body_type.value if request.body else None,
        )

        if Logger.is_debug_enabled("framework.client"):
            if request.body:
                body_log = json.dumps(
                    request.body, ensure_ascii=False, default=str
                )[:500]
                body_log = Logger.mask_sensitive_str(body_log)
                logger.debug("request_body", body=body_log)

            # 保存一份快照用于 on_response 时的日志关联
            safe_headers = Logger.mask_sensitive(dict(request.headers))
            context["logging_request_headers"] = safe_headers
            logger.debug("request_headers", headers=safe_headers)

        return request

    def on_response(
        self, response: HttpResponse, context: dict[str, Any]
    ) -> HttpResponse:
        if Logger.is_debug_enabled("framework.client"):
            safe_resp_headers = Logger.mask_sensitive(dict(response.headers))
            logger.debug("response_headers", headers=safe_resp_headers)

        elapsed_ms = round(response.elapsed_ms)
        logger.info(
            "request_completed",
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            content_length=response.size_bytes,
        )

        return response
