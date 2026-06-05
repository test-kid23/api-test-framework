"""拦截器抽象基类 — 定义请求/响应拦截器接口

拦截器链遵循洋葱模型：
- on_request：外→内顺序执行（先注册的先调用）
- on_response：内→外顺序执行（先注册的后调用，即逆序）

每个拦截器可以通过 context 字典在 on_request / on_response 之间传递状态。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from framework.models import HttpRequest, HttpResponse


class RequestInterceptor(ABC):
    """请求/响应拦截器抽象基类。

    子类只需覆盖 on_request 和/或 on_response 方法。
    两个方法默认返回原对象（透传）。

    Context 字典用于：
    - 传递 httpx 级参数（如 BasicAuth）：context["httpx_kwargs"]["auth"]
    - 在 on_request / on_response 之间共享数据
    """

    def on_request(
        self, request: HttpRequest, context: dict[str, Any]
    ) -> HttpRequest:
        """请求发送前调用。

        Args:
            request: 当前 HttpRequest 对象（可修改后返回）
            context: 拦截器上下文字典（可变，可在 on_request/on_response 间共享）

        Returns:
            处理后的 HttpRequest
        """
        return request

    def on_response(
        self, response: HttpResponse, context: dict[str, Any]
    ) -> HttpResponse:
        """响应返回后调用。

        Args:
            response: 当前 HttpResponse 对象（可修改后返回）
            context: 拦截器上下文字典

        Returns:
            处理后的 HttpResponse
        """
        return response
