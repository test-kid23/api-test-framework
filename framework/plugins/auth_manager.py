"""认证管理插件 — 自动处理 token 刷新"""

from __future__ import annotations

import time
from typing import Any

from framework.plugins.base import PluginBase
from framework.utils.logger import Logger

logger = Logger.get("plugin.auth")


class AuthManager(PluginBase):
    """认证管理插件 — 自动处理 token 刷新

    priority=10 确保在请求链的最前端执行，
    保证其他 on_request 插件拿到的是已注入 token 的请求。
    """

    priority: int = 10

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expires_at: float = 0
        self._refresh_callback: Any = None

    def name(self) -> str:
        return "auth_manager"

    def set_token(self, token: str, expires_in: int = 3600) -> None:
        """设置 token"""
        self._token = token
        self._token_expires_at = time.time() + expires_in

    def set_refresh_callback(self, callback: Any) -> None:
        """设置 token 刷新回调函数"""
        self._refresh_callback = callback

    def on_request(self, request: Any) -> Any:
        """请求发送前，自动注入 Authorization 头"""
        if self._token and not self._token_expired():
            request.headers["Authorization"] = f"Bearer {self._token}"
        elif self._token_expired() and self._refresh_callback:
            self._refresh_token()
            if self._token:
                request.headers["Authorization"] = f"Bearer {self._token}"
        return request

    def on_error(self, error: Exception, case: Any = None) -> None:
        """发生错误时记录认证相关信息"""
        if self._token_expired():
            logger.warning(f"Token 已过期，用例: {getattr(case, 'name', 'unknown')}")

    def _token_expired(self) -> bool:
        """检查 token 是否过期"""
        return time.time() >= self._token_expires_at

    def _refresh_token(self) -> None:
        """刷新 token"""
        try:
            self._refresh_callback()
            logger.info("Token 刷新成功")
        except Exception as e:
            logger.error(f"Token 刷新失败: {e}")
