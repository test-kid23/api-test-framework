"""插件基类 — 定义插件接口

生命周期钩子一览：
┌──────────────┬────────────────────────────────────────────┐
│ 钩子方法       │ 触发时机                                    │
├──────────────┼────────────────────────────────────────────┤
│ on_suite_start│ 套件开始前                                  │
│ on_suite_end  │ 套件结束后                                  │
│ on_case_start │ 用例开始前                                  │
│ on_case_end   │ 用例结束后                                  │
│ on_setup      │ setup 执行前后（phase="before"/"after"）      │
│ on_teardown   │ teardown 执行前后（phase="before"/"after"）   │
│ on_request    │ 请求发送前（可修改请求）                       │
│ on_response   │ 响应接收后（可修改响应）                       │
│ on_assertion  │ 断言执行后（含断言报告）                       │
│ on_extract    │ 变量提取后                                    │
│ on_retry      │ 重试发生时                                    │
│ on_db_query   │ 数据库查询前后（phase="before"/"after"）       │
│ on_error      │ 发生错误时                                    │
└──────────────┴────────────────────────────────────────────┘
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PluginBase(ABC):
    """插件基类

    所有自定义插件继承此类，重写需要的钩子方法。
    所有钩子方法均为可选（默认空实现），仅需覆盖感兴趣的方法。

    Attributes:
        priority: 插件优先级（数值越小越先执行），默认 100。
    """

    priority: int = 100

    @abstractmethod
    def name(self) -> str:
        """插件名称（必须实现）"""
        ...

    # ── 套件级 ──────────────────────────────────────

    def on_suite_start(self, suite: Any) -> None:
        """套件开始前"""
        pass

    def on_suite_end(self, suite: Any, result: Any = None) -> None:
        """套件结束后"""
        pass

    # ── 用例级 ──────────────────────────────────────

    def on_case_start(self, case: Any) -> None:
        """用例开始前"""
        pass

    def on_case_end(self, case: Any, result: Any) -> None:
        """用例结束后"""
        pass

    # ── Setup / Teardown ────────────────────────────

    def on_setup(self, phase: str, case: Any, variables: dict[str, Any]) -> None:
        """setup 执行前后

        Args:
            phase: "before" 或 "after"
            case: 当前用例（或套件）
            variables: 当前变量上下文（\"after\" 时可读取 setup 提取的变量）
        """
        pass

    def on_teardown(self, phase: str, case: Any, variables: dict[str, Any]) -> None:
        """teardown 执行前后

        Args:
            phase: "before" 或 "after"
            case: 当前用例（或套件）
            variables: 当前变量上下文
        """
        pass

    # ── 请求 / 响应 ─────────────────────────────────

    def on_request(self, request: Any) -> Any:
        """请求发送前（可修改请求，返回修改后的请求）"""
        return request

    def on_response(self, response: Any) -> Any:
        """响应接收后（可修改响应，返回修改后的响应）"""
        return response

    # ── 断言 / 提取 ─────────────────────────────────

    def on_assertion(self, case: Any, report: Any) -> None:
        """断言执行后

        Args:
            case: 当前用例
            report: AssertionReport 断言报告
        """
        pass

    def on_extract(self, case: Any, extracted: dict[str, Any]) -> None:
        """变量提取后

        Args:
            case: 当前用例
            extracted: 本次提取的变量字典
        """
        pass

    # ── 错误 / 重试 / 数据库 ─────────────────────────

    def on_error(self, error: Exception, case: Any = None) -> None:
        """发生错误时

        Args:
            error: 异常对象
            case: 发生异常的用例（可选）
        """
        pass

    def on_retry(self, case: Any, attempt: int, max_retries: int, reason: str = "") -> None:
        """重试发生时

        Args:
            case: 当前用例
            attempt: 当前重试次数（从 1 开始）
            max_retries: 最大重试次数
            reason: 重试原因
        """
        pass

    def on_db_query(
        self,
        phase: str,
        case: Any,
        sql: str = "",
        result: Any = None,
    ) -> None:
        """数据库查询前后

        Args:
            phase: "before" 或 "after"
            case: 当前用例
            sql: 执行的 SQL（\"after\" 时为渲染后的 SQL）
            result: 查询结果（仅 \"after\" 时有值）
        """
        pass
