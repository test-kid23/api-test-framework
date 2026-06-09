"""用例推荐与智能生成引擎 — 基于 OpenAPI 覆盖率分析

核心能力：
- 对比 Swagger/OpenAPI spec 定义和已有用例，计算 API 覆盖率
- 识别未覆盖的 endpoint（path + method 组合），生成推荐列表
- 支持一键生成缺失用例（委托 openapi_parser 生成 TestCase）
- 输出结构化覆盖率报告（按 tag/priority/HTTP method 分组统计）

典型用法::

    from framework.generator import CoverageAnalyzer

    analyzer = CoverageAnalyzer()
    report = analyzer.analyze(spec_url="https://api.example.com/openapi.json",
                              existing_cases=db_cases)
    print(f"覆盖率: {report.coverage_rate:.1%}")
    for rec in report.recommendations:
        print(f"  未覆盖: {rec.method} {rec.path}")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from framework.importers.openapi_parser import OpenAPICaseParser, testcase_to_yaml_content
from framework.models import TestCase
from framework.utils.logger import Logger

logger = Logger.get("generator")


# ==================== 数据模型 ====================


@dataclass
class EndpointInfo:
    """单个 API endpoint 的标识信息。

    Attributes:
        method: HTTP 方法（GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS）。
        path: API 路径模式（含 {param} 占位符）。
        summary: 接口摘要（来自 OpenAPI operation.summary）。
        tags: 接口标签列表。
        operation_id: OpenAPI operationId。
        priority: 推断的优先级（P0-P3）。
    """

    method: str
    path: str
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    operation_id: str = ""
    priority: str = "P1"


@dataclass
class CoverageGap:
    """单个覆盖率缺口（未覆盖的 endpoint）。

    Attributes:
        endpoint: 未覆盖的 endpoint 信息。
        has_similar: 是否有近似用例（路径部分匹配）。
        similar_case_names: 近似用例名称列表。
    """

    endpoint: EndpointInfo
    has_similar: bool = False
    similar_case_names: list[str] = field(default_factory=list)


@dataclass
class CoverageGroup:
    """按维度分组的覆盖率统计。

    Attributes:
        group_key: 分组键值（如 tag 名、method 名、priority 名）。
        total: 该组总 endpoint 数。
        covered: 已覆盖 endpoint 数。
        uncovered: 未覆盖 endpoint 数。
        coverage_rate: 覆盖率（0.0-1.0）。
    """

    group_key: str
    total: int
    covered: int
    uncovered: int
    coverage_rate: float = 0.0


@dataclass
class CoverageReport:
    """OpenAPI 覆盖率分析报告。

    Attributes:
        spec_title: OpenAPI spec 标题。
        spec_version: OpenAPI 版本号。
        total_endpoints: spec 中定义的 endpoint 总数。
        covered_endpoints: 已有用例覆盖的 endpoint 数。
        uncovered_endpoints: 未覆盖的 endpoint 数。
        coverage_rate: 总体覆盖率（0.0-1.0）。
        by_tag: 按 tag 分组的覆盖率。
        by_method: 按 HTTP method 分组的覆盖率。
        by_priority: 按优先级分组的覆盖率。
        gaps: 覆盖率缺口列表（未覆盖的 endpoint）。
        recommendations: 推荐生成的用例列表（优先 P0/P1 未覆盖项）。
    """

    spec_title: str = ""
    spec_version: str = ""
    total_endpoints: int = 0
    covered_endpoints: int = 0
    uncovered_endpoints: int = 0
    coverage_rate: float = 0.0
    by_tag: list[CoverageGroup] = field(default_factory=list)
    by_method: list[CoverageGroup] = field(default_factory=list)
    by_priority: list[CoverageGroup] = field(default_factory=list)
    gaps: list[CoverageGap] = field(default_factory=list)
    recommendations: list[EndpointInfo] = field(default_factory=list)

    @property
    def coverage_percent(self) -> float:
        """覆盖率百分比（0-100）。"""
        return round(self.coverage_rate * 100, 1)


@dataclass
class GenerateResult:
    """一键生成结果。

    Attributes:
        total_generated: 成功生成的用例数。
        generated_cases: 生成的用例列表（TestCase + YAML 内容）。
        errors: 生成过程中的错误列表。
    """

    total_generated: int
    generated_cases: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ==================== 覆盖率分析引擎 ====================


class CoverageAnalyzer:
    """OpenAPI 覆盖率分析器。

    对比 OpenAPI spec 中定义的 endpoint 与已有测试用例，
    计算覆盖率、识别缺口、生成推荐列表。

    用法::

        analyzer = CoverageAnalyzer()
        report = analyzer.analyze(
            spec_url="https://petstore3.swagger.io/api/v3/openapi.json",
            existing_cases=[...],  # TestCase 列表 或 dict 列表
        )
    """

    # OpenAPI 支持的 HTTP 方法
    _HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}

    def __init__(self) -> None:
        self._parser = OpenAPICaseParser()

    # ── Public API ─────────────────────────────────────────

    def analyze(
        self,
        spec_url: str = "",
        spec_dict: dict[str, Any] | None = None,
        existing_cases: list[TestCase] | list[dict[str, Any]] | None = None,
        base_url: str = "",
    ) -> CoverageReport:
        """分析 OpenAPI spec 的用例覆盖率。

        Args:
            spec_url: OpenAPI spec 的 URL 或本地文件路径。
            spec_dict: OpenAPI spec 字典（与 spec_url 二选一）。
            existing_cases: 已有用例列表（TestCase 对象或含 name/request 的 dict）。
            base_url: 覆盖 spec 中的 base URL。

        Returns:
            CoverageReport: 包含覆盖率、分组统计、缺口列表和推荐列表。
        """
        # 1. 解析 OpenAPI spec
        if spec_dict is not None:
            spec = spec_dict
        elif spec_url:
            from framework.importers.openapi_parser import _load_spec_content, _parse_spec_content

            content = _load_spec_content(spec_url)
            spec = _parse_spec_content(content)
        else:
            raise ValueError("必须提供 spec_url 或 spec_dict 其中之一")

        # 验证 OpenAPI 版本
        version = spec.get("openapi", "")
        if not version.startswith("3."):
            raise ValueError(f"仅支持 OpenAPI 3.x 规范，当前版本: {version}")

        info = spec.get("info", {})
        spec_title = info.get("title", "Unknown API")
        spec_version = info.get("version", "")

        # 2. 提取 spec 中所有 endpoint
        spec_endpoints = self._extract_endpoints(spec)

        # 3. 提取已有用例覆盖的 endpoint
        covered = self._extract_covered_endpoints(existing_cases or [])

        # 4. 计算覆盖率
        coverage_rate, gaps = self._calculate_coverage(spec_endpoints, covered)

        # 5. 分组统计
        by_tag = self._group_by_tag(spec_endpoints, covered)
        by_method = self._group_by_method(spec_endpoints, covered)
        by_priority = self._group_by_priority(spec_endpoints, covered)

        # 6. 生成推荐列表（优先 P0/P1 未覆盖项）
        recommendations = self._build_recommendations(gaps)

        report = CoverageReport(
            spec_title=spec_title,
            spec_version=spec_version,
            total_endpoints=len(spec_endpoints),
            covered_endpoints=len(spec_endpoints) - len(gaps),
            uncovered_endpoints=len(gaps),
            coverage_rate=coverage_rate,
            by_tag=by_tag,
            by_method=by_method,
            by_priority=by_priority,
            gaps=gaps,
            recommendations=recommendations,
        )

        logger.info(
            "coverage_analysis_complete",
            spec_title=spec_title,
            total=len(spec_endpoints),
            covered=report.covered_endpoints,
            uncovered=len(gaps),
            rate=f"{coverage_rate:.1%}",
        )

        return report

    def generate_missing(
        self,
        spec_url: str = "",
        spec_dict: dict[str, Any] | None = None,
        endpoints: list[dict[str, str]] | None = None,
        base_url: str = "",
    ) -> GenerateResult:
        """为一组 endpoint 生成测试用例。

        委托 OpenAPICaseParser 解析 spec 并筛选目标 endpoint，
        生成对应的 TestCase 和 YAML 内容。

        Args:
            spec_url: OpenAPI spec URL 或本地路径。
            spec_dict: OpenAPI spec 字典。
            endpoints: 要生成的 endpoint 列表，每项含 method 和 path。
                       为 None 时生成所有未覆盖的 endpoint。
            base_url: 覆盖 spec 中的 base URL。

        Returns:
            GenerateResult: 包含生成的用例列表和错误信息。
        """
        # 解析 spec
        if spec_dict is not None:
            spec = spec_dict
        elif spec_url:
            from framework.importers.openapi_parser import _load_spec_content, _parse_spec_content

            content = _load_spec_content(spec_url)
            spec = _parse_spec_content(content)
        else:
            raise ValueError("必须提供 spec_url 或 spec_dict 其中之一")

        # 生成完整 suite
        suite = self._parser.parse_spec(
            spec, base_url=base_url, source_url=spec_url,
        )

        # 筛选目标 endpoint
        target_set: set[tuple[str, str]] | None = None
        if endpoints:
            target_set = {self._normalize(e["method"], e["path"]) for e in endpoints}

        generated_cases: list[dict[str, Any]] = []
        errors: list[str] = []

        for case in suite.cases:
            if case.request is None:
                continue

            method = case.request.method.value
            path = case.request.path
            key = self._normalize(method, path)

            if target_set is not None and key not in target_set:
                continue

            try:
                yaml_content = testcase_to_yaml_content(case)
                generated_cases.append({
                    "name": case.name,
                    "method": method,
                    "path": path,
                    "description": case.description,
                    "tags": case.tags,
                    "priority": case.priority,
                    "yaml_content": yaml_content,
                })
            except Exception as exc:
                errors.append(f"[{method} {path}] {exc}")
                logger.warning("case_generation_error", method=method, path=path, error=str(exc))

        logger.info(
            "generation_complete",
            total=len(generated_cases),
            errors=len(errors),
        )

        return GenerateResult(
            total_generated=len(generated_cases),
            generated_cases=generated_cases,
            errors=errors,
        )

    # ── Endpoint 提取 ─────────────────────────────────────

    def _extract_endpoints(self, spec: dict[str, Any]) -> list[EndpointInfo]:
        """从 OpenAPI spec 中提取所有 endpoint 定义。

        Args:
            spec: OpenAPI 3.x 规范字典。

        Returns:
            EndpointInfo 列表。
        """
        endpoints: list[EndpointInfo] = []
        paths = spec.get("paths", {})

        for path_pattern, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method_name in self._HTTP_METHODS:
                operation = path_item.get(method_name)
                if not operation or not isinstance(operation, dict):
                    continue

                op_tags = [
                    t if isinstance(t, str) else t.get("name", str(t))
                    for t in operation.get("tags", [])
                ]
                priority = self._infer_priority(op_tags)

                endpoints.append(EndpointInfo(
                    method=method_name.upper(),
                    path=path_pattern,
                    summary=operation.get("summary", ""),
                    tags=op_tags,
                    operation_id=operation.get("operationId", ""),
                    priority=priority,
                ))

        logger.debug("endpoints_extracted", count=len(endpoints))
        return endpoints

    def _extract_covered_endpoints(
        self,
        existing_cases: list[TestCase] | list[dict[str, Any]],
    ) -> set[tuple[str, str]]:
        """从已有用例中提取已覆盖的 (method, normalized_path) 集合。

        Args:
            existing_cases: TestCase 列表或包含 method/path 信息的 dict 列表。

        Returns:
            已覆盖的 (method, path) 集合。
        """
        covered: set[tuple[str, str]] = set()

        for case in existing_cases:
            method = ""
            path = ""

            if isinstance(case, TestCase):
                if case.request:
                    method = case.request.method.value
                    path = case.request.path
            elif isinstance(case, dict):
                # 支持 dict 格式：含 request.method 和 request.path
                req = case.get("request", {})
                if isinstance(req, dict):
                    method = req.get("method", "")
                    path = req.get("path", "")
                else:
                    method = case.get("method", "")
                    path = case.get("path", "")
            else:
                continue

            if method and path:
                covered.add(self._normalize(method, path))

        return covered

    # ── 覆盖率计算 ────────────────────────────────────────

    def _calculate_coverage(
        self,
        spec_endpoints: list[EndpointInfo],
        covered: set[tuple[str, str]],
    ) -> tuple[float, list[CoverageGap]]:
        """计算覆盖率并识别缺口。

        Args:
            spec_endpoints: spec 中所有 endpoint。
            covered: 已覆盖的 (method, path) 集合。

        Returns:
            (coverage_rate, gaps) 元组。
        """
        if not spec_endpoints:
            return 1.0, []

        gaps: list[CoverageGap] = []
        covered_count = 0

        for ep in spec_endpoints:
            key = self._normalize(ep.method, ep.path)
            if key in covered:
                covered_count += 1
            else:
                # 检查是否有近似匹配（路径相似但参数化不同）
                has_similar, similar_names = self._find_similar(ep, covered)
                gaps.append(CoverageGap(
                    endpoint=ep,
                    has_similar=has_similar,
                    similar_case_names=similar_names,
                ))

        rate = covered_count / len(spec_endpoints)
        return rate, gaps

    def _find_similar(
        self,
        endpoint: EndpointInfo,
        covered: set[tuple[str, str]],
    ) -> tuple[bool, list[str]]:
        """查找与指定 endpoint 方法相同且路径相似的已覆盖用例。

        相似匹配规则：将路径参数 {param} 替换为通用占位符后比较。
        例如 /users/{id} 和 /users/123 视为相似。

        Args:
            endpoint: 待查找的 endpoint。
            covered: 已覆盖的 (method, path) 集合。

        Returns:
            (has_similar, similar_names) 元组。
        """
        import re

        # 将 spec 路径模板转为正则（{param} → [^/]+）
        pattern_str = re.escape(endpoint.path)
        pattern_str = re.sub(r"\\\{[^}]+\\\}", r"[^/]+", pattern_str)
        try:
            pattern = re.compile(f"^{pattern_str}$")
        except re.error:
            return False, []

        similar: list[str] = []
        method_lower = endpoint.method.lower()
        for m, p in covered:
            if m.lower() == method_lower and pattern.match(p):
                similar.append(f"{m} {p}")

        return len(similar) > 0, similar

    # ── 分组统计 ──────────────────────────────────────────

    def _group_by_tag(
        self,
        endpoints: list[EndpointInfo],
        covered: set[tuple[str, str]],
    ) -> list[CoverageGroup]:
        """按 tag 分组统计覆盖率。"""
        groups: dict[str, dict[str, int]] = {}

        for ep in endpoints:
            tags = ep.tags if ep.tags else ["(无标签)"]
            key = self._normalize(ep.method, ep.path)
            is_covered = key in covered

            for tag in tags:
                if tag not in groups:
                    groups[tag] = {"total": 0, "covered": 0}
                groups[tag]["total"] += 1
                if is_covered:
                    groups[tag]["covered"] += 1

        return sorted(
            [
                CoverageGroup(
                    group_key=tag,
                    total=stats["total"],
                    covered=stats["covered"],
                    uncovered=stats["total"] - stats["covered"],
                    coverage_rate=stats["covered"] / stats["total"] if stats["total"] > 0 else 0.0,
                )
                for tag, stats in groups.items()
            ],
            key=lambda g: g.coverage_rate,
        )

    def _group_by_method(
        self,
        endpoints: list[EndpointInfo],
        covered: set[tuple[str, str]],
    ) -> list[CoverageGroup]:
        """按 HTTP method 分组统计覆盖率。"""
        groups: dict[str, dict[str, int]] = {}

        for ep in endpoints:
            if ep.method not in groups:
                groups[ep.method] = {"total": 0, "covered": 0}
            groups[ep.method]["total"] += 1
            if self._normalize(ep.method, ep.path) in covered:
                groups[ep.method]["covered"] += 1

        return sorted(
            [
                CoverageGroup(
                    group_key=method,
                    total=stats["total"],
                    covered=stats["covered"],
                    uncovered=stats["total"] - stats["covered"],
                    coverage_rate=stats["covered"] / stats["total"] if stats["total"] > 0 else 0.0,
                )
                for method, stats in groups.items()
            ],
            key=lambda g: g.coverage_rate,
        )

    def _group_by_priority(
        self,
        endpoints: list[EndpointInfo],
        covered: set[tuple[str, str]],
    ) -> list[CoverageGroup]:
        """按优先级分组统计覆盖率。"""
        priority_order = ["P0", "P1", "P2", "P3"]
        groups: dict[str, dict[str, int]] = {p: {"total": 0, "covered": 0} for p in priority_order}

        for ep in endpoints:
            key = self._normalize(ep.method, ep.path)
            groups[ep.priority]["total"] += 1
            if key in covered:
                groups[ep.priority]["covered"] += 1

        return [
            CoverageGroup(
                group_key=p,
                total=stats["total"],
                covered=stats["covered"],
                uncovered=stats["total"] - stats["covered"],
                coverage_rate=stats["covered"] / stats["total"] if stats["total"] > 0 else 0.0,
            )
            for p, stats in groups.items()
            if stats["total"] > 0
        ]

    # ── 推荐生成 ──────────────────────────────────────────

    def _build_recommendations(self, gaps: list[CoverageGap]) -> list[EndpointInfo]:
        """从覆盖率缺口中构建推荐列表。

        排序优先级：P0 > P1 > P2 > P3，
        同优先级内按 path 字母序。

        Args:
            gaps: 覆盖率缺口列表。

        Returns:
            推荐生成的 EndpointInfo 列表。
        """
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

        sorted_gaps = sorted(
            gaps,
            key=lambda g: (priority_order.get(g.endpoint.priority, 99), g.endpoint.path),
        )

        return [g.endpoint for g in sorted_gaps]

    # ── 工具方法 ──────────────────────────────────────────

    @staticmethod
    def _normalize(method: str, path: str) -> tuple[str, str]:
        """标准化 (method, path) 为统一的比较键。

        将路径中的具体参数值替换为 {param} 占位符形式，
        以便 spec 中 /users/{id} 能与用例中 /users/123 匹配。

        Args:
            method: HTTP 方法。
            path: 请求路径。

        Returns:
            (method_upper, normalized_path) 元组。
        """
        import re

        method_upper = method.upper().strip()

        # 将路径中的数字/UUID/日期段替换为 {param}
        # 例如 /users/123 → /users/{param}
        # 例如 /users/abc-123-def → /users/{param}
        normalized = re.sub(
            r"/\d+",
            "/{param}",
            path.strip().rstrip("/"),
        )
        # 处理 UUID 格式
        normalized = re.sub(
            r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            "/{param}",
            normalized,
        )
        # 处理纯字母数字 ID（长度 > 4 的不含特殊字符的路径段，可能是 hash/ID）
        # 这个保守一些，只替换明显是 ID 的模式
        normalized = re.sub(
            r"/[0-9a-fA-F]{24,}",
            "/{param}",
            normalized,
        )

        return (method_upper, normalized)

    @staticmethod
    def _infer_priority(tags: list[str]) -> str:
        """从标签推断优先级，默认 P1。"""
        tag_lower = [t.lower() for t in tags]
        if "p0" in tag_lower or "critical" in tag_lower:
            return "P0"
        if "p1" in tag_lower:
            return "P1"
        if "p2" in tag_lower:
            return "P2"
        if "p3" in tag_lower:
            return "P3"
        return "P1"


# ==================== 便捷函数 ====================


def analyze_coverage(
    spec_url: str,
    existing_cases: list[TestCase] | list[dict[str, Any]] | None = None,
) -> CoverageReport:
    """快速分析 OpenAPI spec 覆盖率。

    Args:
        spec_url: OpenAPI spec URL 或本地路径。
        existing_cases: 已有用例列表。

    Returns:
        CoverageReport 对象。
    """
    analyzer = CoverageAnalyzer()
    return analyzer.analyze(spec_url=spec_url, existing_cases=existing_cases)


def generate_missing_cases(
    spec_url: str,
    existing_cases: list[TestCase] | list[dict[str, Any]] | None = None,
    limit: int | None = None,
) -> GenerateResult:
    """快速生成缺失的测试用例。

    Args:
        spec_url: OpenAPI spec URL 或本地路径。
        existing_cases: 已有用例列表（用于识别缺口）。
        limit: 最多生成数量，None 表示全部。

    Returns:
        GenerateResult 对象。
    """
    analyzer = CoverageAnalyzer()

    # 先分析覆盖率
    report = analyzer.analyze(spec_url=spec_url, existing_cases=existing_cases)

    # 提取推荐 endpoint
    endpoints = [
        {"method": ep.method, "path": ep.path}
        for ep in report.recommendations
    ]
    if limit is not None and limit > 0:
        endpoints = endpoints[:limit]

    # 生成用例
    return analyzer.generate_missing(
        spec_url=spec_url,
        endpoints=endpoints,
    )
