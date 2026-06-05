"""报告模块 — 多引擎报告适配器

提供统一的 ReportAdapter 接口，支持：
- Allure 报告（allure-pytest）
- HTML 报告（pytest-html）
- 空操作适配器（无报告输出）

工厂函数 create_report_adapter 根据 ProjectConfig.report.adapter 配置
自动创建对应的适配器实例。
"""

from __future__ import annotations

from typing import Any

from framework.report.base import NoopReportAdapter, ReportAdapter
from framework.report.allure import AllureReportAdapter
from framework.report.html_adapter import HtmlReportAdapter
from framework.report.models import ReportAdapterType


def create_report_adapter(config: Any) -> ReportAdapter:
    """根据配置创建报告适配器实例

    读取 config.report 字典中的 adapter 字段：
    - "allure" → AllureReportAdapter
    - "html"   → HtmlReportAdapter
    - 其他/未配置 → NoopReportAdapter

    Args:
        config: ProjectConfig 实例，其 report 字段为 dict[str, Any]。

    Returns:
        对应的 ReportAdapter 实例。

    Example:
        >>> adapter = create_report_adapter(project_config)
        >>> runner = TestRunner(config, env, client, report_adapter=adapter)
    """
    report_cfg: dict[str, Any] = getattr(config, "report", {}) or {}
    adapter_name = report_cfg.get("adapter", "allure")

    if adapter_name == ReportAdapterType.ALLURE:
        return AllureReportAdapter()
    elif adapter_name == ReportAdapterType.HTML:
        return HtmlReportAdapter()
    elif adapter_name == ReportAdapterType.NOOP:
        return NoopReportAdapter()
    else:
        # 未知适配器，fallback 到 Allure（保持向后兼容）
        from framework.utils.logger import Logger

        Logger.get("report").warning(
            f"未知的报告适配器 '{adapter_name}'，fallback 到 Allure"
        )
        return AllureReportAdapter()


__all__ = [
    "ReportAdapter",
    "NoopReportAdapter",
    "AllureReportAdapter",
    "HtmlReportAdapter",
    "ReportAdapterType",
    "create_report_adapter",
]
