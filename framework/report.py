"""报告模块 — 向后兼容重导出

本文件保留以支持已有代码中的 `from framework.report import AllureAdapter` 引用。
新代码请使用 `from framework.report import AllureReportAdapter`。
"""

from __future__ import annotations

# 重导出新架构的核心类，保持旧名称兼容
from framework.report.allure import AllureReportAdapter as AllureAdapter  # noqa: F401
from framework.report.base import NoopReportAdapter, ReportAdapter  # noqa: F401
from framework.report.html_adapter import HtmlReportAdapter  # noqa: F401
from framework.report.models import ReportAdapterType  # noqa: F401
