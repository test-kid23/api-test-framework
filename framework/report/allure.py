"""Allure 报告适配器 — 将请求/响应/断言信息附加到 Allure 报告

从 framework/report.py 迁移而来，实现 ReportAdapter 接口。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from framework.report.base import ReportAdapter
from framework.report.models import AssertionReport, EnvConfig, HttpRequest, HttpResponse
from framework.utils.logger import Logger

logger = Logger.get("report.allure")

# 延迟导入 allure（可选依赖）
_has_allure = False
try:
    import allure

    _has_allure = True
except ImportError:
    pass


class AllureReportAdapter(ReportAdapter):
    """Allure 报告适配器 — 实现 ReportAdapter 接口

    将测试执行过程中的请求/响应/断言/数据库查询信息
    通过 allure-pytest API 附加到 Allure 报告中。
    """

    def attach_request(self, request: HttpRequest, url: str) -> None:
        """将请求信息附加到 Allure 报告"""
        if not _has_allure:
            return

        body_str = (
            json.dumps(request.body, ensure_ascii=False, indent=2, default=str)
            if request.body
            else "(empty)"
        )

        content = (
            f"Method: {request.method.value}\n"
            f"URL: {url}\n"
            f"Headers: {json.dumps(dict(request.headers), ensure_ascii=False, indent=2)}\n"
            f"Body:\n{body_str}"
        )
        allure.attach(content, name="Request", attachment_type=allure.attachment_type.TEXT)

    def attach_response(self, response: HttpResponse) -> None:
        """将响应信息附加到 Allure 报告"""
        if not _has_allure:
            return

        body_str = (
            json.dumps(response.body, ensure_ascii=False, indent=2, default=str)
            if isinstance(response.body, (dict, list))
            else str(response.body)
        )

        content = (
            f"Status: {response.status_code}\n"
            f"Time: {response.elapsed_ms:.1f}ms\n"
            f"Size: {response.size_bytes} bytes\n"
            f"Headers: {json.dumps(dict(response.headers), ensure_ascii=False, indent=2)}\n"
            f"Body:\n{body_str[:10000]}"
        )
        allure.attach(content, name="Response", attachment_type=allure.attachment_type.TEXT)

    def attach_assertions(self, report: AssertionReport) -> None:
        """将断言结果附加到 Allure 报告"""
        if not _has_allure:
            return

        lines = []
        for r in report.results:
            status = "✅" if r.passed else "❌"
            lines.append(
                f"{status} {r.path} | {r.operator} | "
                f"expected={r.expected} | actual={r.actual}"
            )
        allure.attach(
            "\n".join(lines),
            name="Assertions",
            attachment_type=allure.attachment_type.TEXT,
        )

    def attach_db_query(self, sql: str, result: Any, connection: str) -> None:
        """将数据库查询附加到 Allure 报告"""
        if not _has_allure:
            return

        content = (
            f"Connection: {connection}\n"
            f"SQL: {sql}\n"
            f"Result:\n{json.dumps(result, ensure_ascii=False, indent=2, default=str)}"
        )
        allure.attach(content, name="DB Query", attachment_type=allure.attachment_type.TEXT)

    def set_environment(self, env: EnvConfig) -> None:
        """写入 Allure 环境信息文件"""
        if not _has_allure:
            return

        env_dir = Path("reports/allure-results")
        env_dir.mkdir(parents=True, exist_ok=True)
        (env_dir / "environment.properties").write_text(
            f"Environment={env.name}\n"
            f"Base URL={env.base_url}\n"
            f"Python=3.10+\n"
            f"Framework=AutoTest v1.0\n"
        )

    def set_case_labels(self, tags: list[str], priority: str) -> None:
        """设置 Allure 用例标签"""
        if not _has_allure:
            return

        try:
            allure.dynamic.priority(priority)
            for tag in tags:
                allure.dynamic.tag(tag)
        except Exception:
            pass


__all__ = ["AllureReportAdapter"]
