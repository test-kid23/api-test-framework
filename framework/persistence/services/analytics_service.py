"""高级分析聚合服务 — 接口稳定性排行、响应时间分位数、失败原因分类、ROI 统计。

提供跨 execution_results / executions / test_cases 表的聚合分析查询。
所有方法均接收 AsyncSession，不持有持久状态。
查询兼容 SQLite / PostgreSQL，使用 SQLAlchemy text() 原生 SQL 避免方言分歧。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from framework.persistence.models.execution import ExecutionModel, ExecutionResultModel

# ── 工具函数 ────────────────────────────────────────────────


def _days_ago_utc(days: int) -> datetime:
    """返回 days 天前的 UTC datetime。"""
    return datetime.now(timezone.utc) - timedelta(days=days)


# ── AnalyticsService ────────────────────────────────────────


class AnalyticsService:
    """高级分析聚合服务。

    封装稳定性排行、分位数、失败分类、ROI 等统计查询。
    调用方在需要时创建实例并传入 AsyncSession。
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── 接口稳定性排行 ──────────────────────────────────

    async def get_stability_ranking(
        self,
        days: int = 30,
        limit: int = 20,
        suite_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """查询接口稳定性排行，按失败率降序排列。

        对 execution_results 表按 case_name 分组，统计每个接口的
        总执行次数、通过次数、失败次数、失败率、平均耗时、最近执行时间。

        Args:
            days: 统计时间范围（天）。
            limit: 返回条数上限。
            suite_id: 按套件 ID 过滤（可选）。

        Returns:
            [{case_name, case_id, total, passed, failed, failure_rate, avg_elapsed_ms, last_executed_at}, ...]
        """
        start = _days_ago_utc(days)
        params: dict[str, Any] = {"start": start, "limit": limit}

        if suite_id is not None:
            params["suite_id"] = str(suite_id)
            sql = sa_text("""
                SELECT
                    er.case_name,
                    er.case_id,
                    COUNT(*) AS total,
                    SUM(CASE WHEN er.passed THEN 1 ELSE 0 END) AS passed,
                    SUM(CASE WHEN NOT er.passed THEN 1 ELSE 0 END) AS failed,
                    CAST(SUM(CASE WHEN NOT er.passed THEN 1 ELSE 0 END) AS FLOAT)
                        / COUNT(*) AS failure_rate,
                    AVG(er.elapsed_ms) AS avg_elapsed_ms,
                    MAX(er.created_at) AS last_executed_at
                FROM execution_results er
                JOIN executions e ON er.execution_id = e.id
                WHERE er.created_at >= :start AND e.suite_id = :suite_id
                GROUP BY er.case_name, er.case_id
                HAVING COUNT(*) > 0
                ORDER BY failure_rate DESC
                LIMIT :limit
            """)
        else:
            sql = sa_text("""
                SELECT
                    case_name,
                    case_id,
                    COUNT(*) AS total,
                    SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS passed,
                    SUM(CASE WHEN NOT passed THEN 1 ELSE 0 END) AS failed,
                    CAST(SUM(CASE WHEN NOT passed THEN 1 ELSE 0 END) AS FLOAT)
                        / COUNT(*) AS failure_rate,
                    AVG(elapsed_ms) AS avg_elapsed_ms,
                    MAX(created_at) AS last_executed_at
                FROM execution_results
                WHERE created_at >= :start
                GROUP BY case_name, case_id
                HAVING COUNT(*) > 0
                ORDER BY failure_rate DESC
                LIMIT :limit
            """)

        result = await self._session.execute(sql, params)
        rows = result.all()

        return [
            {
                "case_name": row.case_name or "",
                "case_id": str(row.case_id) if row.case_id else "",
                "total": row.total,
                "passed": row.passed or 0,
                "failed": row.failed or 0,
                "failure_rate": round(row.failure_rate or 0.0, 4),
                "avg_elapsed_ms": round(row.avg_elapsed_ms or 0.0, 2),
                "last_executed_at": row.last_executed_at,
            }
            for row in rows
        ]

    # ── 响应时间分位数 ──────────────────────────────────

    async def get_response_time_percentiles(
        self,
        days: int = 30,
        suite_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """查询指定时间范围内所有执行结果的响应时间分位数 P50/P95/P99。

        通过 SQL 窗口函数 NTILE 或子查询计算分位数。
        SQLite 环境下使用子查询 + LIMIT/OFFSET 近似计算。

        Args:
            days: 统计时间范围（天）。
            suite_id: 按套件 ID 过滤（可选）。

        Returns:
            {p50, p95, p99, avg, min, max, total_samples} 字典。
        """
        start = _days_ago_utc(days)

        # 获取所有 elapsed_ms 值（排除 NULL）
        if suite_id is not None:
            sql = sa_text("""
                SELECT er.elapsed_ms
                FROM execution_results er
                JOIN executions e ON er.execution_id = e.id
                WHERE er.created_at >= :start
                  AND er.elapsed_ms IS NOT NULL
                  AND e.suite_id = :suite_id
                ORDER BY er.elapsed_ms ASC
            """)
            params = {"start": start, "suite_id": str(suite_id)}
        else:
            sql = sa_text("""
                SELECT elapsed_ms
                FROM execution_results
                WHERE created_at >= :start AND elapsed_ms IS NOT NULL
                ORDER BY elapsed_ms ASC
            """)
            params = {"start": start}

        result = await self._session.execute(sql, params)
        values = [row.elapsed_ms for row in result.all()]

        if not values:
            return {
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "total_samples": 0,
            }

        n = len(values)

        def _percentile(sorted_vals: list[float], pct: float) -> float:
            """计算分位数（线性插值）。"""
            k = (pct / 100.0) * (n - 1)
            f = int(k)
            c = k - f
            if f + 1 < n:
                return round(sorted_vals[f] + c * (sorted_vals[f + 1] - sorted_vals[f]), 2)
            return round(sorted_vals[f], 2)

        return {
            "p50": _percentile(values, 50),
            "p95": _percentile(values, 95),
            "p99": _percentile(values, 99),
            "avg": round(sum(values) / n, 2),
            "min": round(values[0], 2),
            "max": round(values[-1], 2),
            "total_samples": n,
        }

    # ── 失败原因分类 ────────────────────────────────────

    async def get_failure_categories(
        self,
        days: int = 30,
        suite_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """对失败用例按原因进行分类统计。

        分类规则（基于 error 字段关键词匹配）：
        - assertion_failure: 包含 "assert" / "expect" / "验证" / "断言"
        - connection_timeout: 包含 "timeout" / "timed out" / "超时"
        - connection_error: 包含 "connection" / "refused" / "unreachable" / "DNS"
        - http_error: 包含 "4xx" / "5xx" / "status" / "HTTP"
        - other: 无法匹配上述分类

        Args:
            days: 统计时间范围（天）。
            suite_id: 按套件 ID 过滤（可选）。

        Returns:
            [{category, count, percentage, examples: [...]}, ...]
        """
        start = _days_ago_utc(days)

        if suite_id is not None:
            sql = sa_text("""
                SELECT er.error, er.case_name
                FROM execution_results er
                JOIN executions e ON er.execution_id = e.id
                WHERE er.created_at >= :start
                  AND er.passed = FALSE
                  AND e.suite_id = :suite_id
            """)
            params = {"start": start, "suite_id": str(suite_id)}
        else:
            sql = sa_text("""
                SELECT error, case_name
                FROM execution_results
                WHERE created_at >= :start AND passed = FALSE
            """)
            params = {"start": start}

        result = await self._session.execute(sql, params)
        rows = result.all()

        if not rows:
            return []

        # 分类统计
        categories: dict[str, dict[str, Any]] = {
            "assertion_failure": {"category": "assertion_failure", "label": "断言失败", "count": 0, "examples": []},
            "connection_timeout": {"category": "connection_timeout", "label": "连接超时", "count": 0, "examples": []},
            "connection_error": {"category": "connection_error", "label": "连接错误", "count": 0, "examples": []},
            "http_error": {"category": "http_error", "label": "HTTP 错误", "count": 0, "examples": []},
            "other": {"category": "other", "label": "其他", "count": 0, "examples": []},
        }

        for row in rows:
            error_text = (row.error or "").lower()
            case_name = row.case_name or "unknown"

            if any(kw in error_text for kw in ("assert", "expect", "验证", "断言")):
                cat = "assertion_failure"
            elif any(kw in error_text for kw in ("timeout", "timed out", "超时")):
                cat = "connection_timeout"
            elif any(kw in error_text for kw in ("connection", "refused", "unreachable", "dns", "resolve")):
                cat = "connection_error"
            elif any(kw in error_text for kw in ("4xx", "5xx", "status", "http", "response code")):
                cat = "http_error"
            else:
                cat = "other"

            categories[cat]["count"] += 1
            if len(categories[cat]["examples"]) < 3:
                categories[cat]["examples"].append(case_name)

        total_failures = sum(c["count"] for c in categories.values())

        result_list = []
        for cat_data in categories.values():
            if cat_data["count"] > 0:
                result_list.append({
                    "category": cat_data["category"],
                    "label": cat_data["label"],
                    "count": cat_data["count"],
                    "percentage": round(cat_data["count"] / total_failures * 100, 2) if total_failures > 0 else 0.0,
                    "examples": cat_data["examples"],
                })

        # 按 count 降序排列
        result_list.sort(key=lambda x: x["count"], reverse=True)
        return result_list

    # ── ROI 统计 ────────────────────────────────────────

    async def get_roi_stats(self) -> dict[str, Any]:
        """获取 ROI（投资回报率）统计信息。

        统计内容：
        - 自动化用例总数（test_cases 表中 active 状态的用例数）
        - 覆盖接口数（去重后的 case_name 数量）
        - 总执行次数
        - 历史总通过率
        - 节省工时估算（手动执行每次按 3 分钟计，自动化按 5 秒计）
        - 最近 30 天执行趋势

        Returns:
            ROI 统计字典。
        """
        # 用例总数
        case_count_sql = sa_text("SELECT COUNT(*) AS cnt FROM test_cases WHERE status = 'active'")
        case_result = await self._session.execute(case_count_sql)
        total_cases = case_result.scalar_one()

        # 去重接口数（按 case_name 去重）
        endpoint_sql = sa_text("""
            SELECT COUNT(DISTINCT case_name) AS cnt
            FROM execution_results
            WHERE case_name IS NOT NULL
        """)
        endpoint_result = await self._session.execute(endpoint_sql)
        covered_endpoints = endpoint_result.scalar_one()

        # 总执行次数
        exec_count_sql = sa_text("SELECT COUNT(*) AS cnt FROM executions")
        exec_result = await self._session.execute(exec_count_sql)
        total_executions = exec_result.scalar_one()

        # 历史总通过率
        pass_rate_sql = sa_text("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS passed
            FROM execution_results
        """)
        pass_result = await self._session.execute(pass_rate_sql)
        pass_row = pass_result.first()
        if pass_row and pass_row.total > 0:
            overall_pass_rate = round(pass_row.passed / pass_row.total * 100, 2)
            total_results = pass_row.total
        else:
            overall_pass_rate = 0.0
            total_results = 0

        # 节省工时估算
        # 假设：手动执行每次 3 分钟，自动化每次 5 秒
        MANUAL_MINUTES_PER_RUN = 3.0
        AUTO_MINUTES_PER_RUN = 5.0 / 60.0  # 5 秒转分钟
        manual_hours = (total_results * MANUAL_MINUTES_PER_RUN) / 60.0
        auto_hours = (total_results * AUTO_MINUTES_PER_RUN) / 60.0
        saved_hours = manual_hours - auto_hours

        # 最近 30 天执行统计
        thirty_days_ago = _days_ago_utc(30)
        recent_sql = sa_text("""
            SELECT
                COUNT(DISTINCT execution_id) AS exec_count,
                COUNT(*) AS result_count,
                SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS passed_count
            FROM execution_results
            WHERE created_at >= :start
        """)
        recent_result = await self._session.execute(recent_sql, {"start": thirty_days_ago})
        recent_row = recent_result.first()
        recent_exec_count = recent_row.exec_count if recent_row else 0
        recent_result_count = recent_row.result_count if recent_row else 0
        recent_passed = recent_row.passed_count if recent_row else 0
        recent_pass_rate = (
            round(recent_passed / recent_result_count * 100, 2) if recent_result_count > 0 else 0.0
        )

        return {
            "total_automated_cases": total_cases,
            "covered_endpoints": covered_endpoints,
            "total_executions": total_executions,
            "total_test_runs": total_results,
            "overall_pass_rate": overall_pass_rate,
            "estimated_manual_hours": round(manual_hours, 1),
            "estimated_auto_hours": round(auto_hours, 1),
            "estimated_hours_saved": round(saved_hours, 1),
            "recent_30d": {
                "execution_count": recent_exec_count,
                "test_run_count": recent_result_count,
                "pass_rate": recent_pass_rate,
            },
        }
