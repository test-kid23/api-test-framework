"""报告聚合服务 — 提供趋势分析、Top N 失败等跨 Repository 的聚合查询。

所有方法均接收 AsyncSession，不持有持久状态。
查询自动适配 SQLite / PostgreSQL，使用 SQLAlchemy 标准 func 避免方言分歧。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, desc, func, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from framework.persistence.models.execution import ExecutionModel, ExecutionResultModel

# ── 工具函数 ────────────────────────────────────────────────


def _days_ago_utc(days: int) -> datetime:
    """返回 days 天前的 UTC datetime（用于 created_at 过滤）。"""
    return datetime.now(timezone.utc) - timedelta(days=days)


async def _fetch_last_errors(
    session: AsyncSession,
    case_names: list[str],
) -> dict[str, str | None]:
    """批量查询每个 case_name 最近一次失败的错误信息。

    对每个 case_name 单独查询最近一条失败记录（ORDER BY created_at DESC LIMIT 1），
    兼容 SQLite / PostgreSQL，避免 row_number().over() 编译问题。

    Returns:
        {case_name: error_text} 映射，无失败记录时 key 不存在。
    """
    if not case_names:
        return {}

    results: dict[str, str | None] = {}

    for name in case_names:
        stmt = (
            select(ExecutionResultModel.error)
            .where(
                and_(
                    ExecutionResultModel.case_name == name,
                    ExecutionResultModel.passed == False,
                )
            )
            .order_by(ExecutionResultModel.created_at.desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).first()
        if row is not None:
            results[name] = row.error

    return results


# ── ReportService ────────────────────────────────────────────


class ReportService:
    """测试报告聚合服务。

    封装从 execution_results / executions 表中提取的统计查询。
    不作为单例使用 — 调用方在需要时创建实例并传入 AsyncSession。
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── 通过率趋势 ──────────────────────────────────────

    async def get_pass_rate_trend(
        self,
        days: int = 7,
        suite_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """查询指定时间范围内的每日通过率趋势。

        返回每日的总数/通过数/失败数/通过率/平均耗时。
        若 suite_id 指定，仅统计该套件下的执行。

        Returns:
            [{date, total, passed, failed, pass_rate, avg_elapsed_ms}, ...]
        """
        start = _days_ago_utc(days)

        # TODO(Phase2): 当前使用 text() 原生 SQL 是为了绕过 SQLAlchemy 2.0 异步编译器处理
        # func.date() / func.row_number().over() 等复杂聚合函数时可能存在的方言兼容性 bug。
        # 已在 SQLite 3.45+ 和 PostgreSQL 16+ 验证通过。
        # 后续应评估并尽量重写为 ORM 查询，以获得编译时检查和方言自动适配。
        if suite_id is not None:
            sql = sa_text("""
                SELECT
                    DATE(er.created_at) AS date,
                    COUNT(*) AS total,
                    SUM(CASE WHEN er.passed THEN 1 ELSE 0 END) AS passed,
                    SUM(CASE WHEN NOT er.passed THEN 1 ELSE 0 END) AS failed,
                    CAST(SUM(CASE WHEN er.passed THEN 1 ELSE 0 END) AS FLOAT)
                        / COUNT(*) AS pass_rate,
                    AVG(er.elapsed_ms) AS avg_elapsed_ms
                FROM execution_results er
                JOIN executions e ON er.execution_id = e.id
                WHERE er.created_at >= :start AND e.suite_id = :suite_id
                GROUP BY DATE(er.created_at)
                ORDER BY DATE(er.created_at) ASC
            """)
            params = {"start": start, "suite_id": str(suite_id)}
        else:
            sql = sa_text("""
                SELECT
                    DATE(created_at) AS date,
                    COUNT(*) AS total,
                    SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS passed,
                    SUM(CASE WHEN NOT passed THEN 1 ELSE 0 END) AS failed,
                    CAST(SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS FLOAT)
                        / COUNT(*) AS pass_rate,
                    AVG(elapsed_ms) AS avg_elapsed_ms
                FROM execution_results
                WHERE created_at >= :start
                GROUP BY DATE(created_at)
                ORDER BY DATE(created_at) ASC
            """)
            params = {"start": start}

        result = await self._session.execute(sql, params)
        rows = result.all()

        return [
            {
                "date": str(row.date),
                "total": row.total,
                "passed": row.passed or 0,
                "failed": row.failed or 0,
                "pass_rate": round(row.pass_rate or 0.0, 4),
                "avg_elapsed_ms": round(row.avg_elapsed_ms or 0.0, 2),
            }
            for row in rows
        ]

    # ── 平均响应时间趋势 ────────────────────────────────

    async def get_avg_response_time_trend(
        self,
        days: int = 7,
        suite_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """查询指定时间范围内的每日平均响应时间趋势。

        Returns:
            [{date, avg_elapsed_ms, max_elapsed_ms, min_elapsed_ms}, ...]
        """
        start = _days_ago_utc(days)

        # TODO(Phase2): 同 get_pass_rate_trend。当前使用 text() 原生 SQL 是为了绕过 SQLAlchemy
        # 2.0 异步编译器处理 func.date() 等聚合函数时可能存在的方言兼容性 bug。
        # 已在 SQLite 3.45+ 和 PostgreSQL 16+ 验证通过。
        # 后续应评估并尽量重写为 ORM 查询，以获得编译时检查和方言自动适配。
        if suite_id is not None:
            sql = sa_text("""
                SELECT
                    DATE(er.created_at) AS date,
                    AVG(er.elapsed_ms) AS avg_elapsed_ms,
                    MAX(er.elapsed_ms) AS max_elapsed_ms,
                    MIN(er.elapsed_ms) AS min_elapsed_ms
                FROM execution_results er
                JOIN executions e ON er.execution_id = e.id
                WHERE er.created_at >= :start AND e.suite_id = :suite_id
                GROUP BY DATE(er.created_at)
                ORDER BY DATE(er.created_at) ASC
            """)
            params = {"start": start, "suite_id": str(suite_id)}
        else:
            sql = sa_text("""
                SELECT
                    DATE(created_at) AS date,
                    AVG(elapsed_ms) AS avg_elapsed_ms,
                    MAX(elapsed_ms) AS max_elapsed_ms,
                    MIN(elapsed_ms) AS min_elapsed_ms
                FROM execution_results
                WHERE created_at >= :start
                GROUP BY DATE(created_at)
                ORDER BY DATE(created_at) ASC
            """)
            params = {"start": start}

        result = await self._session.execute(sql, params)
        rows = result.all()

        return [
            {
                "date": str(row.date),
                "avg_elapsed_ms": round(row.avg_elapsed_ms or 0.0, 2),
                "max_elapsed_ms": round(row.max_elapsed_ms or 0.0, 2),
                "min_elapsed_ms": round(row.min_elapsed_ms or 0.0, 2),
            }
            for row in rows
        ]

    # ── 通过率趋势（支持粒度） ──────────────────────────

    async def get_pass_rate_trend_with_granularity(
        self,
        days: int = 30,
        granularity: str = "day",
        suite_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """查询指定时间范围内的通过率趋势，支持 day/week/month 粒度.

        对 week/month 粒度，使用 strftime 格式化日期到周/月级别。

        Args:
            days: 统计时间范围（天）.
            granularity: 粒度 (day/week/month).
            suite_id: 按套件 ID 过滤（可选）.

        Returns:
            [{date, total, passed, failed, pass_rate, avg_elapsed_ms}, ...]
        """
        if granularity == "day":
            return await self.get_pass_rate_trend(days=days, suite_id=suite_id)

        start = _days_ago_utc(days)

        if granularity == "week":
            # 按 ISO 周分组: %Y-%W
            date_format = "%Y-%W"
        else:
            # month: %Y-%m
            date_format = "%Y-%m"

        if suite_id is not None:
            sql = sa_text(f"""
                SELECT
                    STRFTIME('{date_format}', er.created_at) AS date,
                    COUNT(*) AS total,
                    SUM(CASE WHEN er.passed THEN 1 ELSE 0 END) AS passed,
                    SUM(CASE WHEN NOT er.passed THEN 1 ELSE 0 END) AS failed,
                    CAST(SUM(CASE WHEN er.passed THEN 1 ELSE 0 END) AS FLOAT)
                        / COUNT(*) AS pass_rate,
                    AVG(er.elapsed_ms) AS avg_elapsed_ms
                FROM execution_results er
                JOIN executions e ON er.execution_id = e.id
                WHERE er.created_at >= :start AND e.suite_id = :suite_id
                GROUP BY STRFTIME('{date_format}', er.created_at)
                ORDER BY STRFTIME('{date_format}', er.created_at) ASC
            """)
            params = {"start": start, "suite_id": str(suite_id)}
        else:
            sql = sa_text(f"""
                SELECT
                    STRFTIME('{date_format}', created_at) AS date,
                    COUNT(*) AS total,
                    SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS passed,
                    SUM(CASE WHEN NOT passed THEN 1 ELSE 0 END) AS failed,
                    CAST(SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS FLOAT)
                        / COUNT(*) AS pass_rate,
                    AVG(elapsed_ms) AS avg_elapsed_ms
                FROM execution_results
                WHERE created_at >= :start
                GROUP BY STRFTIME('{date_format}', created_at)
                ORDER BY STRFTIME('{date_format}', created_at) ASC
            """)
            params = {"start": start}

        result = await self._session.execute(sql, params)
        rows = result.all()

        return [
            {
                "date": str(row.date),
                "total": row.total,
                "passed": row.passed or 0,
                "failed": row.failed or 0,
                "pass_rate": round(row.pass_rate or 0.0, 4),
                "avg_elapsed_ms": round(row.avg_elapsed_ms or 0.0, 2),
            }
            for row in rows
        ]

    # ── 每日响应时间分位数趋势 ──────────────────────────

    async def get_response_time_percentiles_trend(
        self,
        days: int = 30,
        suite_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """查询每日响应时间分位数 P50/P90/P95/P99.

        先获取每天所有 elapsed_ms 值，然后在 Python 内存中计算分位数。
        这是为了兼容 SQLite / PostgreSQL 的通用实现。

        Args:
            days: 统计时间范围（天）.
            suite_id: 按套件 ID 过滤（可选）.

        Returns:
            [{date, p50, p90, p95, p99, avg, min, max, total}, ...]
        """
        start = _days_ago_utc(days)

        if suite_id is not None:
            sql = sa_text("""
                SELECT
                    DATE(er.created_at) AS date,
                    er.elapsed_ms
                FROM execution_results er
                JOIN executions e ON er.execution_id = e.id
                WHERE er.created_at >= :start
                  AND er.elapsed_ms IS NOT NULL
                  AND e.suite_id = :suite_id
                ORDER BY DATE(er.created_at) ASC
            """)
            params = {"start": start, "suite_id": str(suite_id)}
        else:
            sql = sa_text("""
                SELECT
                    DATE(created_at) AS date,
                    elapsed_ms
                FROM execution_results
                WHERE created_at >= :start AND elapsed_ms IS NOT NULL
                ORDER BY DATE(created_at) ASC
            """)
            params = {"start": start}

        result = await self._session.execute(sql, params)
        rows = result.all()

        if not rows:
            return []

        # 按日期分组
        from collections import defaultdict
        date_values: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            date_values[str(row.date)].append(float(row.elapsed_ms))

        def _percentile(sorted_vals: list[float], pct: float) -> float:
            n = len(sorted_vals)
            k = (pct / 100.0) * (n - 1)
            f = int(k)
            c = k - f
            if f + 1 < n:
                return round(sorted_vals[f] + c * (sorted_vals[f + 1] - sorted_vals[f]), 2)
            return round(sorted_vals[f], 2)

        results: list[dict[str, Any]] = []
        for date_str in sorted(date_values.keys()):
            vals = sorted(date_values[date_str])
            n = len(vals)
            results.append({
                "date": date_str,
                "p50": _percentile(vals, 50),
                "p90": _percentile(vals, 90),
                "p95": _percentile(vals, 95),
                "p99": _percentile(vals, 99),
                "avg": round(sum(vals) / n, 2),
                "min": round(vals[0], 2),
                "max": round(vals[-1], 2),
                "total": n,
            })

        return results

    # ── 不稳定接口 ──────────────────────────────────────

    async def get_unstable_endpoints(
        self,
        days: int = 30,
        threshold: float = 0.8,
        suite_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """查询通过率低于阈值的接口（不稳定接口）.

        按 case_name 分组，统计每个接口的通过率，返回低于 threshold 的接口。
        仅统计至少有 5 次执行记录的接口，避免样本过少导致误判。

        Args:
            days: 统计时间范围（天）.
            threshold: 通过率阈值（0-1），低于此值的视为不稳定.
            suite_id: 按套件 ID 过滤（可选）.

        Returns:
            [{case_name, case_id, total, passed, failed, pass_rate, avg_elapsed_ms}, ...]
        """
        start = _days_ago_utc(days)
        params: dict[str, Any] = {
            "start": start,
            "threshold": threshold,
            "min_runs": 5,
        }

        if suite_id is not None:
            params["suite_id"] = str(suite_id)
            sql = sa_text("""
                SELECT
                    er.case_name,
                    er.case_id,
                    COUNT(*) AS total,
                    SUM(CASE WHEN er.passed THEN 1 ELSE 0 END) AS passed,
                    SUM(CASE WHEN NOT er.passed THEN 1 ELSE 0 END) AS failed,
                    CAST(SUM(CASE WHEN er.passed THEN 1 ELSE 0 END) AS FLOAT)
                        / COUNT(*) AS pass_rate,
                    AVG(er.elapsed_ms) AS avg_elapsed_ms
                FROM execution_results er
                JOIN executions e ON er.execution_id = e.id
                WHERE er.created_at >= :start AND e.suite_id = :suite_id
                GROUP BY er.case_name, er.case_id
                HAVING COUNT(*) >= :min_runs
                   AND CAST(SUM(CASE WHEN er.passed THEN 1 ELSE 0 END) AS FLOAT)
                       / COUNT(*) < :threshold
                ORDER BY pass_rate ASC
            """)
        else:
            sql = sa_text("""
                SELECT
                    case_name,
                    case_id,
                    COUNT(*) AS total,
                    SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS passed,
                    SUM(CASE WHEN NOT passed THEN 1 ELSE 0 END) AS failed,
                    CAST(SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS FLOAT)
                        / COUNT(*) AS pass_rate,
                    AVG(elapsed_ms) AS avg_elapsed_ms
                FROM execution_results
                WHERE created_at >= :start
                GROUP BY case_name, case_id
                HAVING COUNT(*) >= :min_runs
                   AND CAST(SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS FLOAT)
                       / COUNT(*) < :threshold
                ORDER BY pass_rate ASC
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
                "pass_rate": round(row.pass_rate or 0.0, 4),
                "avg_elapsed_ms": round(row.avg_elapsed_ms or 0.0, 2),
            }
            for row in rows
        ]

    # ── Top N 失败用例 ──────────────────────────────────

    async def get_top_failures(
        self,
        limit: int = 10,
        suite_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """查询失败次数最多的 Top N 用例。

        先按 case_name 分组计数，再批量查询每个 case_name 最近一次失败的错误信息。

        Returns:
            [{case_id, case_name, fail_count, last_failed_at, last_error}, ...]
        """
        conditions = [ExecutionResultModel.passed == False]
        join_clauses: list[tuple] = []

        if suite_id is not None:
            join_clauses.append(
                (ExecutionModel, ExecutionResultModel.execution_id == ExecutionModel.id)
            )
            conditions.append(ExecutionModel.suite_id == suite_id)

        # 聚合查询
        agg_cols = [
            ExecutionResultModel.case_id,
            ExecutionResultModel.case_name,
            func.count().label("fail_count"),
            func.max(ExecutionResultModel.created_at).label("last_failed_at"),
        ]

        stmt = select(*agg_cols)
        for join_model, join_on in join_clauses:
            stmt = stmt.join(join_model, join_on)

        stmt = (
            stmt.where(and_(*conditions))
            .group_by(
                ExecutionResultModel.case_id,
                ExecutionResultModel.case_name,
            )
            .order_by(desc("fail_count"))
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        if not rows:
            return []

        # 批量获取最近一次错误信息
        case_names = [row.case_name for row in rows]
        last_errors = await _fetch_last_errors(self._session, case_names)

        return [
            {
                "case_id": str(row.case_id) if row.case_id else "",
                "case_name": row.case_name or "",
                "fail_count": row.fail_count,
                "last_failed_at": row.last_failed_at,
                "last_error": last_errors.get(row.case_name or ""),
            }
            for row in rows
        ]
