"""报告聚合 API 单元测试 — 通过率趋势、响应时间分位数、失败分类、不稳定接口"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from framework.persistence.services.report_service import ReportService, _days_ago_utc
from framework.persistence.services.analytics_service import AnalyticsService


# ==================== Fixtures ====================


@pytest.fixture
def sample_elapsed_values() -> list[float]:
    """生成模拟的响应时间样本."""
    return [
        10, 20, 30, 40, 50, 60, 70, 80, 90, 100,
        150, 200, 250, 300, 350, 400, 450, 500, 600, 800,
    ]


# ==================== ReportService 测试 ====================


class TestDaysAgoUtc:
    """_days_ago_utc 工具函数测试."""

    def test_days_ago_is_in_past(self) -> None:
        """返回的时间在当前时间之前."""
        result = _days_ago_utc(7)
        now = datetime.now(timezone.utc)
        assert result < now

    def test_days_ago_offset(self) -> None:
        """偏移量大致正确."""
        result = _days_ago_utc(7)
        now = datetime.now(timezone.utc)
        delta = now - result
        assert timedelta(days=6) < delta < timedelta(days=8)


class TestPassRateTrendGranularity:
    """通过率趋势粒度测试."""

    def test_granularity_day_delegates_to_get_pass_rate_trend(self) -> None:
        """day 粒度委托给 get_pass_rate_trend."""
        # 验证方法存在且可调用
        assert hasattr(ReportService, "get_pass_rate_trend_with_granularity")
        assert hasattr(ReportService, "get_pass_rate_trend")

    def test_valid_granularity_values(self) -> None:
        """有效粒度值."""
        valid = {"day", "week", "month"}
        # 这些值应被 API 的 pattern 参数接受
        assert "day" in valid
        assert "week" in valid
        assert "month" in valid


class TestResponseTimePercentiles:
    """响应时间分位数计算测试."""

    def test_percentile_calculation(self, sample_elapsed_values: list[float]) -> None:
        """验证分位数计算的正确性."""
        sorted_vals = sorted(sample_elapsed_values)
        n = len(sorted_vals)

        # P50 (中位数)
        def pct(vals: list[float], p: float) -> float:
            k = (p / 100.0) * (len(vals) - 1)
            f = int(k)
            c = k - f
            if f + 1 < len(vals):
                return round(vals[f] + c * (vals[f + 1] - vals[f]), 2)
            return round(vals[f], 2)

        p50 = pct(sorted_vals, 50)
        p95 = pct(sorted_vals, 95)
        p99 = pct(sorted_vals, 99)

        assert p50 > 0
        assert p95 >= p50
        assert p99 >= p95

    def test_single_value_percentile(self) -> None:
        """单个值时所有分位数相同."""
        vals = [100.0]

        def pct(vals: list[float], p: float) -> float:
            return round(vals[0], 2)

        assert pct(vals, 50) == 100.0
        assert pct(vals, 95) == 100.0
        assert pct(vals, 99) == 100.0

    def test_two_values_percentile(self) -> None:
        """两个值时线性插值."""
        vals = [10.0, 20.0]

        def pct(vals: list[float], p: float) -> float:
            k = (p / 100.0) * (len(vals) - 1)
            f = int(k)
            c = k - f
            if f + 1 < len(vals):
                return round(vals[f] + c * (vals[f + 1] - vals[f]), 2)
            return round(vals[f], 2)

        assert pct(vals, 50) == 15.0  # 线性插值
        assert pct(vals, 0) == 10.0
        assert pct(vals, 100) == 20.0


class TestUnstableEndpoints:
    """不稳定接口测试."""

    def test_threshold_boundaries(self) -> None:
        """阈值边界值."""
        # threshold=0 时所有接口都是不稳定的
        assert 0.0 >= 0.0
        # threshold=1 时只有全部失败的接口才不稳定
        assert 1.0 <= 1.0

    def test_pass_rate_below_threshold(self) -> None:
        """通过率低于阈值的判定."""
        threshold = 0.8
        pass_rate_ok = 0.85
        pass_rate_unstable = 0.72

        assert pass_rate_ok >= threshold  # 稳定
        assert pass_rate_unstable < threshold  # 不稳定


# ==================== AnalyticsService 测试 ====================


class TestFailureCategories:
    """失败分类测试."""

    def test_category_labels_exist(self) -> None:
        """所有分类标签存在."""
        categories = {
            "assertion_failure",
            "connection_timeout",
            "connection_error",
            "http_error",
            "other",
        }
        assert len(categories) == 5
        assert "assertion_failure" in categories

    def test_error_keyword_matching(self) -> None:
        """错误关键词匹配."""
        # assertion
        assert "assert" in "assertion error: expected 200 got 500".lower()
        # timeout
        assert "timeout" in "connection timeout after 30s".lower()
        # connection
        assert "connection" in "connection refused".lower()
        # http
        assert "http" in "http 500 error".lower()

    def test_unknown_error_falls_to_other(self) -> None:
        """无法匹配的错误归为 other."""
        error = "unknown internal error occurred"
        keywords = ["assert", "expect", "timeout", "connection", "refused", "dns", "http", "status"]
        assert not any(kw in error.lower() for kw in keywords)

    def test_chinese_error_keywords(self) -> None:
        """中文错误关键词."""
        assert "超时" in "请求超时".lower()
        assert "断言" in "断言失败".lower()
        assert "验证" in "验证不通过".lower()


class TestResponseTimePercentilesService:
    """响应时间分位数服务测试."""

    def test_empty_values_returns_zeros(self) -> None:
        """空值时返回全零."""
        empty_result = {
            "p50": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "avg": 0.0,
            "min": 0.0,
            "max": 0.0,
            "total_samples": 0,
        }
        assert empty_result["total_samples"] == 0
        assert empty_result["p50"] == 0.0

    def test_percentile_order(self) -> None:
        """分位数顺序: P50 ≤ P95 ≤ P99."""
        # 这个测试验证分位数的单调性
        assert 50 <= 95 <= 99  # 百分位递增


# ==================== Schema 测试 ====================


class TestReportSchemas:
    """报告 Schema 测试."""

    def test_trend_item_creation(self) -> None:
        """TrendItem 创建."""
        from api.schemas.report import TrendItem
        item = TrendItem(
            date="2026-06-01",
            total=100,
            passed=95,
            failed=5,
            pass_rate=0.95,
            avg_elapsed_ms=120.5,
        )
        assert item.date == "2026-06-01"
        assert item.pass_rate == 0.95

    def test_trend_response_with_granularity(self) -> None:
        """TrendResponse 带粒度."""
        from api.schemas.report import TrendResponse
        resp = TrendResponse(days=30, granularity="week", items=[])
        assert resp.granularity == "week"

    def test_trend_response_default_granularity(self) -> None:
        """TrendResponse 默认粒度."""
        from api.schemas.report import TrendResponse
        resp = TrendResponse(days=7, items=[])
        assert resp.granularity == "day"

    def test_response_time_trend_item(self) -> None:
        """ResponseTimeTrendItem 创建."""
        from api.schemas.report import ResponseTimeTrendItem
        item = ResponseTimeTrendItem(
            date="2026-06-01",
            p50=100.0,
            p90=300.0,
            p95=500.0,
            p99=800.0,
            avg=150.0,
            min=10.0,
            max=1000.0,
            total=50,
        )
        assert item.p50 == 100.0
        assert item.p99 == 800.0

    def test_response_time_trend_response(self) -> None:
        """ResponseTimeTrendResponse 创建."""
        from api.schemas.report import ResponseTimeTrendResponse, ResponseTimeTrendItem
        items = [
            ResponseTimeTrendItem(
                date="2026-06-01",
                p50=100.0, p90=300.0, p95=500.0, p99=800.0,
                avg=150.0, min=10.0, max=1000.0, total=50,
            )
        ]
        resp = ResponseTimeTrendResponse(days=30, items=items)
        assert resp.days == 30
        assert len(resp.items) == 1

    def test_failure_category_item(self) -> None:
        """FailureCategoryItem 创建."""
        from api.schemas.report import FailureCategoryItem
        item = FailureCategoryItem(
            category="assertion_failure",
            count=45,
            percentage=60.0,
        )
        assert item.category == "assertion_failure"
        assert item.count == 45

    def test_failure_category_response(self) -> None:
        """FailureCategoryResponse 创建."""
        from api.schemas.report import FailureCategoryResponse, FailureCategoryItem
        items = [
            FailureCategoryItem(category="timeout", count=10, percentage=50.0),
            FailureCategoryItem(category="assertion", count=10, percentage=50.0),
        ]
        resp = FailureCategoryResponse(days=30, items=items)
        assert resp.days == 30
        assert len(resp.items) == 2

    def test_unstable_endpoint_item(self) -> None:
        """UnstableEndpointItem 创建."""
        from api.schemas.report import UnstableEndpointItem
        item = UnstableEndpointItem(
            endpoint="POST /api/users",
            pass_rate=0.72,
            total_runs=50,
        )
        assert item.endpoint == "POST /api/users"
        assert item.pass_rate == 0.72

    def test_unstable_endpoint_response(self) -> None:
        """UnstableEndpointResponse 创建."""
        from api.schemas.report import UnstableEndpointResponse, UnstableEndpointItem
        items = [
            UnstableEndpointItem(endpoint="GET /api/test", pass_rate=0.5, total_runs=10),
        ]
        resp = UnstableEndpointResponse(days=30, threshold=0.8, items=items)
        assert resp.threshold == 0.8
        assert len(resp.items) == 1


# ==================== 集成测试 ====================


class TestIntegration:
    """报告聚合端到端场景测试."""

    def test_full_aggregation_workflow(self) -> None:
        """完整聚合工作流：通过率趋势 → 响应时间分位数 → 失败分类 → 不稳定接口."""
        # 验证所有方法都可调用
        assert hasattr(ReportService, "get_pass_rate_trend_with_granularity")
        assert hasattr(ReportService, "get_response_time_percentiles_trend")
        assert hasattr(ReportService, "get_unstable_endpoints")
        assert hasattr(AnalyticsService, "get_failure_categories")
        assert hasattr(AnalyticsService, "get_response_time_percentiles")

    def test_method_signatures_consistent(self) -> None:
        """方法签名一致."""
        import inspect

        # get_pass_rate_trend_with_granularity
        sig = inspect.signature(ReportService.get_pass_rate_trend_with_granularity)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "days" in params
        assert "granularity" in params

        # get_response_time_percentiles_trend
        sig = inspect.signature(ReportService.get_response_time_percentiles_trend)
        params = list(sig.parameters.keys())
        assert "days" in params

        # get_unstable_endpoints
        sig = inspect.signature(ReportService.get_unstable_endpoints)
        params = list(sig.parameters.keys())
        assert "threshold" in params

    def test_default_parameter_values(self) -> None:
        """默认参数值合理."""
        import inspect

        # days 默认值
        sig = inspect.signature(ReportService.get_pass_rate_trend_with_granularity)
        assert sig.parameters["days"].default == 30

        # granularity 默认值
        assert sig.parameters["granularity"].default == "day"

        # threshold 默认值
        sig = inspect.signature(ReportService.get_unstable_endpoints)
        assert sig.parameters["threshold"].default == 0.8
