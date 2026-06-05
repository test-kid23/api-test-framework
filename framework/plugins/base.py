"""插件基类 — 定义插件接口"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PluginBase(ABC):
    """插件基类

    所有自定义插件继承此类，重写需要的钩子方法。
    """

    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        ...

    def on_suite_start(self, suite: Any) -> None:
        """套件开始前"""
        pass

    def on_suite_end(self, suite: Any) -> None:
        """套件结束后"""
        pass

    def on_case_start(self, case: Any) -> None:
        """用例开始前"""
        pass

    def on_case_end(self, case: Any, result: Any) -> None:
        """用例结束后"""
        pass

    def on_request(self, request: Any) -> Any:
        """请求发送前（可修改请求）"""
        return request

    def on_response(self, response: Any) -> Any:
        """响应接收后（可修改响应）"""
        return response

    def on_error(self, error: Exception) -> None:
        """发生错误时"""
        pass
