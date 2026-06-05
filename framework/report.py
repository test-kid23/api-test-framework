"""Allure 报告适配器 — 将请求/响应/断言信息附加到 Allure 报告"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from framework.utils.logger import Logger

logger = Logger.get("report")

# 延迟导入 allure（可选依赖）
_has_allure = False
try:
    import allure

    _has_allure = True
except ImportError:
    pass


class AllureAdapter:
    """Allure 报告适配器"""

    @staticmethod
    def attach_request(request: Any, url: str) -> None:
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

    @staticmethod
    def attach_response(response: Any) -> None:
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

    @staticmethod
    def attach_assertions(report: Any) -> None:
        """将断言结果附加到 Allure 报告"""
        if not _has_allure:
            return

        lines = []
        for r in report.results:
            status = "✅" if r.passed else "❌"
            lines.append(
                f"{status} {r.path} | {r.operator} | " f"expected={r.expected} | actual={r.actual}"
            )
        allure.attach(
            "\n".join(lines),
            name="Assertions",
            attachment_type=allure.attachment_type.TEXT,
        )

    @staticmethod
    def attach_db_query(sql: str, result: Any, connection: str) -> None:
        """将数据库查询附加到 Allure 报告"""
        if not _has_allure:
            return

        content = (
            f"Connection: {connection}\n"
            f"SQL: {sql}\n"
            f"Result:\n{json.dumps(result, ensure_ascii=False, indent=2, default=str)}"
        )
        allure.attach(content, name="DB Query", attachment_type=allure.attachment_type.TEXT)

    @staticmethod
    def set_environment(env_config: Any) -> None:
        """写入 Allure 环境信息"""
        if not _has_allure:
            return

        env_dir = Path("reports/allure-results")
        env_dir.mkdir(parents=True, exist_ok=True)
        (env_dir / "environment.properties").write_text(
            f"Environment={env_config.name}\n"
            f"Base URL={env_config.base_url}\n"
            f"Python=3.10+\n"
            f"Framework=AutoTest v1.0\n"
        )

    @staticmethod
    def set_case_labels(tags: list[str], priority: str) -> None:
        """设置 Allure 用例标签"""
        if not _has_allure:
            return

        try:
            allure.dynamic.priority(priority)
            for tag in tags:
                allure.dynamic.tag(tag)
        except Exception:
            pass
