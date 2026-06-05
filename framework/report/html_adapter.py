"""pytest-html 报告适配器 — 实现 ReportAdapter 接口

将测试信息以 HTML 友好的方式输出，配合 pytest-html 插件使用。
当前为基础骨架实现，后续可按需扩展为生成独立 HTML 报告。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from framework.report.base import ReportAdapter
from framework.report.models import AssertionReport, EnvConfig, HttpRequest, HttpResponse
from framework.utils.logger import Logger

logger = Logger.get("report.html")

_has_pytest_html = False
try:
    import pytest_html  # noqa: F401

    _has_pytest_html = True
except ImportError:
    pass


class HtmlReportAdapter(ReportAdapter):
    """HTML 报告适配器

    当前为基础实现，通过 pytest-html 的 extra 机制附加信息。
    后续可扩展为独立 HTML 报告生成。
    """

    def __init__(self) -> None:
        self._request_data: list[dict[str, Any]] = []
        self._response_data: list[dict[str, Any]] = []
        self._assertions_data: list[dict[str, Any]] = []
        self._db_queries: list[dict[str, Any]] = []
        self._extra_items: list[tuple[str, str]] = []

    def attach_request(self, request: HttpRequest, url: str) -> None:
        body_str = (
            json.dumps(request.body, ensure_ascii=False, indent=2, default=str)
            if request.body
            else "(empty)"
        )
        self._request_data.append(
            {
                "method": request.method.value,
                "url": url,
                "headers": dict(request.headers),
                "body": body_str,
            }
        )

    def attach_response(self, response: HttpResponse) -> None:
        body_str = (
            json.dumps(response.body, ensure_ascii=False, indent=2, default=str)
            if isinstance(response.body, (dict, list))
            else str(response.body)
        )
        self._response_data.append(
            {
                "status": response.status_code,
                "time_ms": response.elapsed_ms,
                "size_bytes": response.size_bytes,
                "headers": dict(response.headers),
                "body": body_str[:10000],
            }
        )

    def attach_assertions(self, report: AssertionReport) -> None:
        for r in report.results:
            self._assertions_data.append(
                {
                    "passed": r.passed,
                    "path": r.path,
                    "operator": r.operator,
                    "expected": r.expected,
                    "actual": r.actual,
                    "message": r.message,
                }
            )

    def attach_db_query(self, sql: str, result: Any, connection: str) -> None:
        self._db_queries.append(
            {
                "connection": connection,
                "sql": sql,
                "result": result,
            }
        )

    def set_environment(self, env: EnvConfig) -> None:
        env_dir = Path("reports/html")
        env_dir.mkdir(parents=True, exist_ok=True)
        (env_dir / "environment.json").write_text(
            json.dumps(
                {
                    "environment": env.name,
                    "base_url": env.base_url,
                    "python": "3.10+",
                    "framework": "AutoTest v1.0",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def set_case_labels(self, tags: list[str], priority: str) -> None:
        logger.debug(f"HTML 报告标签: tags={tags}, priority={priority}")

    # ── HTML 专有方法（供 conftest hook 调用） ─────────

    def get_extra_items(self) -> list[tuple[str, str]]:
        """获取 pytest-html extra 条目列表

        Returns:
            [(name, html_content), ...] 列表，可直接传给 extras.append()。
            pytest-html 需要自行安装：pip install pytest-html
        """
        return list(self._extra_items)

    def clear(self) -> None:
        """清空当前用例的累积数据（每个用例调用前重置）"""
        self._request_data.clear()
        self._response_data.clear()
        self._assertions_data.clear()
        self._db_queries.clear()
        self._extra_items.clear()

    def build_summary_html(self) -> str:
        """构建当前用例的报告摘要 HTML

        Returns:
            格式化的 HTML 片段字符串。
        """
        parts: list[str] = []

        # 请求信息
        for i, req in enumerate(self._request_data):
            parts.append(
                f"<details open>"
                f"<summary>📤 Request #{i + 1}: {req['method']} {req['url']}</summary>"
                f"<pre>{json.dumps(req, ensure_ascii=False, indent=2)}</pre>"
                f"</details>"
            )

        # 响应信息
        for i, resp in enumerate(self._response_data):
            parts.append(
                f"<details open>"
                f"<summary>📥 Response #{i + 1}: {resp['status']}</summary>"
                f"<pre>{json.dumps(resp, ensure_ascii=False, indent=2)}</pre>"
                f"</details>"
            )

        # 断言信息
        if self._assertions_data:
            passed = sum(1 for a in self._assertions_data if a["passed"])
            failed = len(self._assertions_data) - passed
            parts.append(
                f"<details open><summary>"
                f"✅ Assertions: {passed} passed, {failed} failed"
                f"</summary>"
                f"<pre>{json.dumps(self._assertions_data, ensure_ascii=False, indent=2)}</pre>"
                f"</details>"
            )

        # DB 查询
        for i, db in enumerate(self._db_queries):
            parts.append(
                f"<details><summary>🗄️ DB Query #{i + 1}: {db['connection']}</summary>"
                f"<pre>SQL: {db['sql']}<br>Result: {json.dumps(db['result'], ensure_ascii=False, indent=2, default=str)}</pre>"
                f"</details>"
            )

        return "\n".join(parts)


__all__ = ["HtmlReportAdapter"]
