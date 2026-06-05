"""ReportAdapter 抽象基类 — 报告适配器接口定义

所有报告引擎（Allure / pytest-html / JSON / 自定义）均需实现此接口。
TestRunner 通过此抽象与具体报告引擎解耦。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from framework.report.models import AssertionReport, EnvConfig, HttpRequest, HttpResponse


class ReportAdapter(ABC):
    """报告适配器抽象基类

    定义了将测试信息（请求、响应、断言、数据库查询）附加到
    具体报告引擎的统一接口。子类只需实现附着逻辑即可接入任意报告系统。

    Usage:
        class MyCustomReporter(ReportAdapter):
            def attach_request(self, request, url): ...
            ...
    """

    # ── 请求生命周期钩子 ──────────────────────────────

    @abstractmethod
    def attach_request(self, request: HttpRequest, url: str) -> None:
        """将请求信息附加到报告

        Args:
            request: 渲染后的 HTTP 请求对象。
            url: 完整的请求 URL。
        """
        ...

    @abstractmethod
    def attach_response(self, response: HttpResponse) -> None:
        """将响应信息附加到报告

        Args:
            response: HTTP 响应对象，含状态码 / 耗时 / Body 等。
        """
        ...

    @abstractmethod
    def attach_assertions(self, report: AssertionReport) -> None:
        """将断言结果附加到报告

        Args:
            report: 断言报告，含所有 AssertResult。
        """
        ...

    @abstractmethod
    def attach_db_query(self, sql: str, result: Any, connection: str) -> None:
        """将数据库查询附加到报告

        Args:
            sql: 执行的 SQL 语句（模板渲染后）。
            result: 查询返回的结果。
            connection: 数据库连接名称。
        """
        ...

    # ── 环境 / 标签钩子 ──────────────────────────────

    @abstractmethod
    def set_environment(self, env: EnvConfig) -> None:
        """设置报告的环境信息

        Args:
            env: 当前环境配置（名称 / base_url 等）。
        """
        ...

    @abstractmethod
    def set_case_labels(self, tags: list[str], priority: str) -> None:
        """设置报告中的用例标签

        Args:
            tags: 用例标签列表（如 ["smoke", "regression"]）。
            priority: 优先级字符串（如 "P0", "P1"）。
        """
        ...


class NoopReportAdapter(ReportAdapter):
    """空操作报告适配器 — 当未配置报告引擎时使用

    所有方法均为空实现，不产生任何报告输出。
    """

    def attach_request(self, request: HttpRequest, url: str) -> None:
        pass

    def attach_response(self, response: HttpResponse) -> None:
        pass

    def attach_assertions(self, report: AssertionReport) -> None:
        pass

    def attach_db_query(self, sql: str, result: Any, connection: str) -> None:
        pass

    def set_environment(self, env: EnvConfig) -> None:
        pass

    def set_case_labels(self, tags: list[str], priority: str) -> None:
        pass


__all__ = ["ReportAdapter", "NoopReportAdapter"]
