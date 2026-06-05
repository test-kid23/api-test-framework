"""线程安全的测试上下文 — 并发执行时变量隔离"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any


class TestContext:
    """线程安全的测试上下文

    每个测试用例有独立的上下文，存储变量、请求/响应等。
    并发执行时互不干扰。
    """

    _local = threading.local()

    @classmethod
    def init(cls) -> None:
        """初始化当前线程的上下文"""
        cls._local.variables = {}
        cls._local.request = None
        cls._local.response = None
        cls._local.assertion_report = None
        cls._local.url = ""

    @classmethod
    def ensure_initialized(cls) -> None:
        """确保上下文已初始化"""
        if not hasattr(cls._local, "variables"):
            cls.init()

    @classmethod
    def get_variables(cls) -> dict[str, Any]:
        cls.ensure_initialized()
        return cls._local.variables  # type: ignore[no-any-return]

    @classmethod
    def set_variable(cls, key: str, value: Any) -> None:
        cls.get_variables()[key] = value

    @classmethod
    def get_variable(cls, key: str, default: Any = None) -> Any:
        return cls.get_variables().get(key, default)

    @classmethod
    def set_request(cls, request: Any) -> None:
        cls.ensure_initialized()
        cls._local.request = request

    @classmethod
    def get_request(cls) -> Any:
        cls.ensure_initialized()
        return cls._local.request

    @classmethod
    def set_response(cls, response: Any) -> None:
        cls.ensure_initialized()
        cls._local.response = response

    @classmethod
    def get_response(cls) -> Any:
        cls.ensure_initialized()
        return cls._local.response

    @classmethod
    def set_url(cls, url: str) -> None:
        cls.ensure_initialized()
        cls._local.url = url

    @classmethod
    def get_url(cls) -> str:
        cls.ensure_initialized()
        return cls._local.url  # type: ignore[no-any-return]

    @classmethod
    @contextmanager
    def scope(cls):  # type: ignore[no-untyped-def]
        """创建一个新的上下文作用域"""
        cls.init()
        try:
            yield cls
        finally:
            pass  # 清理由 GC 处理
