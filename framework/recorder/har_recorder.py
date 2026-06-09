"""HAR 录制拦截器 — 基于 RequestInterceptor 的流量录制

实现 RequestInterceptor 接口，在 on_request/on_response 中捕获
HttpRequest/HttpResponse 并转换为 HAR 格式条目。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from framework.models import HttpRequest, HttpResponse
from framework.interceptors.base import RequestInterceptor
from framework.recorder.har_models import (
    HAR,
    HAREntry,
    HARNameValue,
    HARPostData,
    HARRequest,
    HARResponse,
    HARTimings,
)
from framework.utils.logger import Logger

logger = Logger.get("recorder.har")


class HARRecorder(RequestInterceptor):
    """HAR 录制拦截器

    作为 RequestInterceptor 插入 HttpClient 的拦截器链中，
    在 on_request 阶段记录 HTTP 请求，在 on_response 阶段记录响应与计时信息。

    使用方式::

        recorder = HARRecorder(har=har_instance)
        client.add_interceptor(recorder)

        # 执行请求...
        response = client.get("/api/users")

        # 保存录制文件
        recorder.save("recording.har")

    Attributes:
        har: 被录制的 HAR 对象引用。
        entry_count: 已录制的请求/响应对数量（只读）。
        _last_entry_start: 最近一次请求的 startedDateTime（用于计时）。
    """

    def __init__(self, har: HAR | None = None) -> None:
        """初始化 HAR 录制拦截器。

        Args:
            har: 要填充的 HAR 对象。若为 None，自动创建一个新的。
        """
        self.har = har or HAR.create()
        self._last_entry_start: str | None = None

    @property
    def entry_count(self) -> int:
        """已录制的条目数。"""
        return len(self.har.log.entries)

    def on_request(
        self, request: HttpRequest, context: dict[str, Any]
    ) -> HttpRequest:
        """记录 HTTP 请求快照。

        在请求发送前调用，将 HttpRequest 转换为 HARRequest 并记录开始时间。

        Args:
            request: 当前 HttpRequest。
            context: 拦截器上下文（用于在 on_request/on_response 间传递状态）。

        Returns:
            原封不动返回 request（不修改）。
        """
        # 计算完整 URL（路径 + 查询参数）
        url = request.path
        if request.params:
            from urllib.parse import urlencode

            query_str = urlencode(request.params, doseq=True)
            url = f"{url}?{query_str}"

        # 构建 HAR 请求
        har_req = HARRequest(
            method=request.method.value,
            url=url,
            httpVersion="HTTP/1.1",
            headers=[
                HARNameValue(name=k, value=str(v))
                for k, v in request.headers.items()
            ],
            queryString=[
                HARNameValue(name=k, value=str(v))
                for k, v in request.params.items()
            ],
            headersSize=-1,
            bodySize=-1,
        )

        # 构建 POST 数据
        if request.body is not None:
            body_text = ""
            if isinstance(request.body, (dict, list)):
                body_text = json.dumps(request.body, ensure_ascii=False, default=str)
            elif isinstance(request.body, str):
                body_text = request.body
            else:
                body_text = str(request.body)

            mime_type = "application/json"
            if request.body_type.value == "form":
                mime_type = "application/x-www-form-urlencoded"
            elif request.body_type.value == "raw":
                mime_type = "text/plain"

            har_req.postData = HARPostData(
                mimeType=mime_type,
                text=body_text,
            )
            har_req.bodySize = len(body_text.encode("utf-8"))

        # 记录开始时间并保存到 context
        now = datetime.now(timezone.utc).isoformat()
        self._last_entry_start = now
        context["_har_recorder"] = {
            "started_at": now,
            "har_request": har_req,
        }

        return request

    def on_response(
        self, response: HttpResponse, context: dict[str, Any]
    ) -> HttpResponse:
        """记录 HTTP 响应快照并生成完整 HAR 条目。

        Args:
            response: 当前 HttpResponse。
            context: 拦截器上下文（从 on_request 传入）。

        Returns:
            原封不动返回 response（不修改）。
        """
        rec_ctx: dict[str, Any] = context.get("_har_recorder", {})
        if not rec_ctx:
            logger.warning("on_response_without_on_request_context")
            return response

        started_at = rec_ctx.get("started_at", datetime.now(timezone.utc).isoformat())
        har_req: HARRequest = rec_ctx.get("har_request")
        if har_req is None:
            return response

        # 构建响应体内容
        body_text = ""
        body_size = 0
        mime_type = "application/octet-stream"

        if response.body is not None:
            if isinstance(response.body, (dict, list)):
                body_text = json.dumps(response.body, ensure_ascii=False, default=str)
                mime_type = "application/json"
            elif isinstance(response.body, str):
                body_text = response.body
                mime_type = "text/plain"
            else:
                body_text = str(response.body)
            body_size = len(body_text.encode("utf-8"))

        # 构建 HAR 响应
        har_resp = HARResponse(
            status=response.status_code,
            statusText=_status_text(response.status_code),
            httpVersion="HTTP/1.1",
            headers=[
                HARNameValue(name=k, value=str(v))
                for k, v in response.headers.items()
            ],
            content={
                "size": response.size_bytes if response.size_bytes else body_size,
                "mimeType": mime_type,
                "text": body_text,
            },
            headersSize=-1,
            bodySize=response.size_bytes if response.size_bytes else body_size,
        )

        # 时间指标
        elapsed_ms = response.elapsed_ms
        timings = HARTimings(
            send=0.0,
            wait=elapsed_ms,
            receive=0.0,
            blocked=-1.0,
            dns=-1.0,
            connect=-1.0,
            ssl=-1.0,
        )

        # 组装 HAR 条目
        entry = HAREntry(
            startedDateTime=started_at,
            time=elapsed_ms,
            request=har_req,
            response=har_resp,
            timings=timings,
        )

        self.har.add_entry(entry)

        return response

    def save(self, filepath: str) -> str:
        """将录制数据保存为 HAR 文件。

        Args:
            filepath: 保存路径（.har 文件）。

        Returns:
            保存的文件路径。
        """
        from pathlib import Path

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        har_json = self.har.to_dict()
        path.write_text(
            json.dumps(har_json, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        logger.info("har_saved", path=str(path), entries=self.entry_count)
        return str(path)

    def clear(self) -> None:
        """清除所有已录制的条目。"""
        self.har = HAR.create()
        self._last_entry_start = None


def _status_text(code: int) -> str:
    """获取状态码对应的标准文本。"""
    texts: dict[int, str] = {
        200: "OK",
        201: "Created",
        202: "Accepted",
        204: "No Content",
        301: "Moved Permanently",
        302: "Found",
        304: "Not Modified",
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }
    return texts.get(code, "")
