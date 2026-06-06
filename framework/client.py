"""HTTP 客户端封装 — 基于 httpx 的请求引擎

支持拦截器链：通过 add_interceptor() 注册 RequestInterceptor，
在请求发送前后按洋葱模型依次执行 on_request / on_response。
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from framework.interceptors.auth import AuthInterceptor
from framework.interceptors.base import RequestInterceptor
from framework.interceptors.logging import LoggingInterceptor
from framework.models import BodyType, HttpRequest, HttpResponse
from framework.utils.file_loader import is_file_ref, load_file_ref
from framework.utils.logger import Logger
from framework.utils.retry import retry

logger = Logger.get("client")


class HttpClient:
    """HTTP 客户端封装

    基于 httpx，支持连接池复用、重试、超时控制等。
    """

    def __init__(self, config: dict[str, Any], base_url: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        timeout = config.get("timeout", 30)
        verify_ssl = config.get("verify_ssl", False)
        max_retries = config.get("max_retries", 0)
        retry_delay = config.get("retry_delay", 1)
        retry_on_status = config.get("retry_on", [502, 503, 504])
        follow_redirects = config.get("follow_redirects", True)

        # 默认请求头
        self._default_headers = config.get(
            "default_headers",
            {
                "Accept": "application/json",
                "User-Agent": "AutoTest/1.0",
            },
        )

        # 创建 httpx 客户端（连接池复用）
        self._client = httpx.Client(
            base_url=self._base_url or None,  # type: ignore[arg-type]
            timeout=httpx.Timeout(timeout),
            verify=verify_ssl,
            follow_redirects=follow_redirects,
            limits=httpx.Limits(
                max_connections=config.get("pool_connections", 10),
                max_keepalive_connections=config.get("pool_maxsize", 10),
            ),
        )

        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._retry_on_status = retry_on_status

        # 拦截器链
        self._interceptors: list[RequestInterceptor] = []
        # 默认注册内置拦截器（保持向后兼容）
        self.add_interceptor(AuthInterceptor())
        self.add_interceptor(LoggingInterceptor())

    def add_interceptor(self, interceptor: RequestInterceptor) -> None:
        """注册拦截器。

        拦截器按注册顺序执行 on_request，逆序执行 on_response（洋葱模型）。
        """
        self._interceptors.append(interceptor)

    def request(self, req: HttpRequest, variables: dict[str, Any] | None = None) -> HttpResponse:
        """发送 HTTP 请求

        Args:
            req: 请求对象
            variables: 变量字典（用于日志记录）

        Returns:
            HttpResponse 对象
        """
        # 合并请求头
        headers = {**self._default_headers, **req.headers}

        # 构建请求参数
        kwargs: dict[str, Any] = {
            "method": req.method.value,
            "url": req.path,
            "headers": headers,
            "params": req.params or None,
        }

        # 超时覆盖
        if req.timeout is not None:
            kwargs["timeout"] = httpx.Timeout(req.timeout)

        # SSL 覆盖
        if req.verify_ssl is not None:
            # 需要重新创建客户端以修改 verify
            pass  # httpx 不支持单请求覆盖 verify，忽略

        # 请求体
        if req.body is not None:
            body_kwargs = self._build_body(req)
            # _build_body 可能返回 "headers" 键（如 JSON 的 Content-Type），
            # 必须合并到已有的 headers 中，避免覆盖 Authorization 等关键头
            if "headers" in body_kwargs:
                headers.update(body_kwargs.pop("headers"))
                kwargs["headers"] = headers
            kwargs.update(body_kwargs)

        # 文件上传
        if req.files:
            kwargs["files"] = self._build_files(req.files)

        # ── 拦截器链：on_request（按注册顺序）──
        context: dict[str, Any] = {}
        for interceptor in self._interceptors:
            req = interceptor.on_request(req, context)

        # 合并拦截器设置的 httpx 级参数（如 BasicAuth）
        httpx_kwargs = context.pop("httpx_kwargs", {})
        kwargs.update(httpx_kwargs)

        # 发送请求（带重试）
        response = self._send_with_retry(**kwargs)

        # 转换为内部 HttpResponse
        http_resp = self._to_response(response, req)

        # ── 拦截器链：on_response（逆序，洋葱模型）──
        for interceptor in reversed(self._interceptors):
            http_resp = interceptor.on_response(http_resp, context)

        return http_resp

    def get(self, path: str, **kwargs: Any) -> HttpResponse:
        kwargs.setdefault("method", "GET")
        return self.request(HttpRequest(method="GET", path=path, **kwargs))  # type: ignore[arg-type]

    def post(self, path: str, **kwargs: Any) -> HttpResponse:
        return self.request(HttpRequest(method="POST", path=path, **kwargs))  # type: ignore[arg-type]

    def put(self, path: str, **kwargs: Any) -> HttpResponse:
        return self.request(HttpRequest(method="PUT", path=path, **kwargs))  # type: ignore[arg-type]

    def delete(self, path: str, **kwargs: Any) -> HttpResponse:
        return self.request(HttpRequest(method="DELETE", path=path, **kwargs))  # type: ignore[arg-type]

    def patch(self, path: str, **kwargs: Any) -> HttpResponse:
        return self.request(HttpRequest(method="PATCH", path=path, **kwargs))  # type: ignore[arg-type]

    def close(self) -> None:
        """关闭客户端，释放连接池"""
        self._client.close()

    # ---------- 内部方法 ----------

    def _send_with_retry(self, **kwargs: Any) -> httpx.Response:
        """发送请求（带重试逻辑）"""
        if self._max_retries > 0:
            retry_decorator = retry(
                max_retries=self._max_retries,
                delay=self._retry_delay,
                retry_on_status=self._retry_on_status,
            )
            send_fn = retry_decorator(self._client.request)
            return send_fn(**kwargs)  # type: ignore[no-any-return]
        return self._client.request(**kwargs)

    def _build_body(self, req: HttpRequest) -> dict[str, Any]:
        """根据 body_type 构建请求体"""
        body = req.body

        if req.body_type == BodyType.JSON:
            return {
                "content": json.dumps(body, ensure_ascii=False, default=str).encode(),
                "headers": {"Content-Type": "application/json"},
            }

        elif req.body_type == BodyType.FORM:
            return {"data": body}

        elif req.body_type == BodyType.MULTIPART:
            return {"files": self._build_multipart(body)}

        elif req.body_type == BodyType.RAW:
            if isinstance(body, str):
                return {"content": body.encode()}
            return {"content": body}

        return {}

    def _build_multipart(self, body: Any) -> list[tuple[str, Any]]:
        """构建 multipart 请求体"""
        if not isinstance(body, dict):
            return []

        parts: list[tuple[str, Any]] = []
        for key, value in body.items():
            if is_file_ref(str(value)):
                file_path = load_file_ref(str(value))
                parts.append((key, (file_path.name, open(file_path, "rb"))))
            else:
                parts.append((key, (None, str(value).encode())))
        return parts

    def _build_files(self, files: dict[str, str]) -> list[tuple[str, Any]]:
        """构建文件上传"""
        result: list[tuple[str, Any]] = []
        for field_name, file_ref in files.items():
            if is_file_ref(file_ref):
                file_path = load_file_ref(file_ref)
                result.append((field_name, (file_path.name, open(file_path, "rb"))))
            else:
                result.append((field_name, open(file_ref, "rb")))
        return result

    def _to_response(self, resp: httpx.Response, req: HttpRequest) -> HttpResponse:
        """将 httpx.Response 转换为 HttpResponse"""
        # 解析响应体
        body: Any
        try:
            body = resp.json()
        except (json.JSONDecodeError, ValueError):
            body = resp.text

        # 计算大小
        size_bytes = len(resp.content)

        return HttpResponse(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            body=body,
            elapsed_ms=resp.elapsed.total_seconds() * 1000,
            size_bytes=size_bytes,
            url=str(resp.url),
            request_body=req.body,
        )


class AsyncHttpClient:
    """异步 HTTP 客户端封装

    基于 httpx.AsyncClient，接口与 HttpClient 一致但所有 I/O 方法为 async。
    支持连接池复用、拦截器链（洋葱模型）、重试机制。

    与同步 HttpClient 的对应关系：
    - HttpClient.request()    → AsyncHttpClient.request()
    - HttpClient.get/post/... → AsyncHttpClient.get/post/...
    - HttpClient.close()      → AsyncHttpClient.aclose()
    """

    def __init__(self, config: dict[str, Any], base_url: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        timeout = config.get("timeout", 30)
        verify_ssl = config.get("verify_ssl", False)
        max_retries = config.get("max_retries", 0)
        retry_delay = config.get("retry_delay", 1)
        retry_on_status = config.get("retry_on", [502, 503, 504])
        follow_redirects = config.get("follow_redirects", True)

        self._default_headers = config.get(
            "default_headers",
            {
                "Accept": "application/json",
                "User-Agent": "AutoTest/1.0",
            },
        )

        self._client = httpx.AsyncClient(
            base_url=self._base_url or None,  # type: ignore[arg-type]
            timeout=httpx.Timeout(timeout),
            verify=verify_ssl,
            follow_redirects=follow_redirects,
            limits=httpx.Limits(
                max_connections=config.get("pool_connections", 10),
                max_keepalive_connections=config.get("pool_maxsize", 10),
            ),
        )

        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._retry_on_status = retry_on_status

        # 拦截器链（与 HttpClient 共享相同的拦截器类型）
        self._interceptors: list[RequestInterceptor] = []
        self.add_interceptor(AuthInterceptor())
        self.add_interceptor(LoggingInterceptor())

    def add_interceptor(self, interceptor: RequestInterceptor) -> None:
        """注册拦截器（洋葱模型）"""
        self._interceptors.append(interceptor)

    async def request(
        self, req: HttpRequest, variables: dict[str, Any] | None = None
    ) -> HttpResponse:
        """异步发送 HTTP 请求

        Args:
            req: 请求对象
            variables: 变量字典（用于日志记录）

        Returns:
            HttpResponse 对象
        """
        headers = {**self._default_headers, **req.headers}

        kwargs: dict[str, Any] = {
            "method": req.method.value,
            "url": req.path,
            "headers": headers,
            "params": req.params or None,
        }

        if req.timeout is not None:
            kwargs["timeout"] = httpx.Timeout(req.timeout)

        if req.body is not None:
            body_kwargs = self._build_body(req)
            if "headers" in body_kwargs:
                headers.update(body_kwargs.pop("headers"))
                kwargs["headers"] = headers
            kwargs.update(body_kwargs)

        if req.files:
            kwargs["files"] = self._build_files(req.files)

        # 拦截器链：on_request（按注册顺序）
        context: dict[str, Any] = {}
        for interceptor in self._interceptors:
            req = interceptor.on_request(req, context)

        httpx_kwargs = context.pop("httpx_kwargs", {})
        kwargs.update(httpx_kwargs)

        # 异步发送请求（带重试）
        response = await self._send_with_retry(**kwargs)

        http_resp = self._to_response(response, req)

        # 拦截器链：on_response（逆序）
        for interceptor in reversed(self._interceptors):
            http_resp = interceptor.on_response(http_resp, context)

        return http_resp

    async def get(self, path: str, **kwargs: Any) -> HttpResponse:
        kwargs.setdefault("method", "GET")
        return await self.request(HttpRequest(method="GET", path=path, **kwargs))  # type: ignore[arg-type]

    async def post(self, path: str, **kwargs: Any) -> HttpResponse:
        return await self.request(HttpRequest(method="POST", path=path, **kwargs))  # type: ignore[arg-type]

    async def put(self, path: str, **kwargs: Any) -> HttpResponse:
        return await self.request(HttpRequest(method="PUT", path=path, **kwargs))  # type: ignore[arg-type]

    async def delete(self, path: str, **kwargs: Any) -> HttpResponse:
        return await self.request(HttpRequest(method="DELETE", path=path, **kwargs))  # type: ignore[arg-type]

    async def patch(self, path: str, **kwargs: Any) -> HttpResponse:
        return await self.request(HttpRequest(method="PATCH", path=path, **kwargs))  # type: ignore[arg-type]

    async def aclose(self) -> None:
        """关闭异步客户端，释放连接池"""
        await self._client.aclose()

    # ---------- 内部方法 ----------

    async def _send_with_retry(self, **kwargs: Any) -> httpx.Response:
        """异步发送请求（带重试逻辑）

        注意：为保持与同步版一致的行为，重试逻辑不使用 async 装饰器，
        而是手动实现带 asyncio.sleep 的重试循环。
        """
        import asyncio as _asyncio

        last_response: httpx.Response | None = None
        current_delay = self._retry_delay

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(**kwargs)

                if self._retry_on_status and response.status_code in self._retry_on_status:
                    if attempt < self._max_retries:
                        logger.warning(
                            "状态码 %d 触发重试 (%d/%d), 等待 %.1fs",
                            response.status_code,
                            attempt + 1,
                            self._max_retries,
                            current_delay,
                        )
                        await _asyncio.sleep(current_delay)
                        current_delay *= 1.0  # 线性延迟，与同步版保持一致
                        last_response = response
                        continue

                return response

            except Exception as e:
                if attempt < self._max_retries:
                    logger.warning(
                        "异常 %s: %s 触发重试 (%d/%d), 等待 %.1fs",
                        type(e).__name__,
                        e,
                        attempt + 1,
                        self._max_retries,
                        current_delay,
                    )
                    await _asyncio.sleep(current_delay)
                    current_delay *= 1.0
                else:
                    raise

        # 所有重试都用完，返回最后一次响应
        if last_response is not None:
            return last_response

        # 不应到达这里，但安全返回
        return await self._client.request(**kwargs)

    def _build_body(self, req: HttpRequest) -> dict[str, Any]:
        """根据 body_type 构建请求体（逻辑与 HttpClient 一致）"""
        body = req.body

        if req.body_type == BodyType.JSON:
            return {
                "content": json.dumps(body, ensure_ascii=False, default=str).encode(),
                "headers": {"Content-Type": "application/json"},
            }
        elif req.body_type == BodyType.FORM:
            return {"data": body}
        elif req.body_type == BodyType.MULTIPART:
            return {"files": self._build_multipart(body)}
        elif req.body_type == BodyType.RAW:
            if isinstance(body, str):
                return {"content": body.encode()}
            return {"content": body}
        return {}

    def _build_multipart(self, body: Any) -> list[tuple[str, Any]]:
        """构建 multipart 请求体"""
        if not isinstance(body, dict):
            return []
        parts: list[tuple[str, Any]] = []
        for key, value in body.items():
            if is_file_ref(str(value)):
                file_path = load_file_ref(str(value))
                parts.append((key, (file_path.name, open(file_path, "rb"))))
            else:
                parts.append((key, (None, str(value).encode())))
        return parts

    def _build_files(self, files: dict[str, str]) -> list[tuple[str, Any]]:
        """构建文件上传"""
        result: list[tuple[str, Any]] = []
        for field_name, file_ref in files.items():
            if is_file_ref(file_ref):
                file_path = load_file_ref(file_ref)
                result.append((field_name, (file_path.name, open(file_path, "rb"))))
            else:
                result.append((field_name, open(file_ref, "rb")))
        return result

    @staticmethod
    def _to_response(resp: httpx.Response, req: HttpRequest) -> HttpResponse:
        """将 httpx.Response 转换为 HttpResponse（与 HttpClient 一致）"""
        body: Any
        try:
            body = resp.json()
        except (json.JSONDecodeError, ValueError):
            body = resp.text

        size_bytes = len(resp.content)

        return HttpResponse(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            body=body,
            elapsed_ms=resp.elapsed.total_seconds() * 1000,
            size_bytes=size_bytes,
            url=str(resp.url),
            request_body=req.body,
        )
