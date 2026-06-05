"""拦截器模块 — 请求/响应拦截器链

提供可扩展的拦截器机制，支持在请求发送前后插入自定义逻辑：
- RequestInterceptor：抽象基类
- AuthInterceptor：自动认证
- LoggingInterceptor：请求/响应日志记录

使用方式::

    from framework.interceptors import AuthInterceptor, LoggingInterceptor
    client.add_interceptor(AuthInterceptor())
    client.add_interceptor(LoggingInterceptor())
"""

from __future__ import annotations

from framework.interceptors.auth import AuthInterceptor
from framework.interceptors.base import RequestInterceptor
from framework.interceptors.logging import LoggingInterceptor

__all__ = [
    "AuthInterceptor",
    "LoggingInterceptor",
    "RequestInterceptor",
]
