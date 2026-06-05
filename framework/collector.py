"""pytest YAML 用例收集器 — 基于 pytest.Function 的原生 fixture 注入

将 YAML 文件收集→用例展开→标签过滤等逻辑封装为独立收集器。
通过 pytest.Function（而非 pytest.Item）生成测试用例，使 fixture 注入走
pytest 原生路径，无需手动桥接。

核心组件：
- YamlCollector: 收集入口
- YamlFile: 文件级收集器 (pytest.File)
- YamlFunction: 单用例节点 (pytest.Function)，定制 reportinfo
- _execute_yaml_case: 用例执行函数（fixture 参数由 pytest 自动解析）
- YamlTestException: 用例执行失败异常
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from framework.parser import YAMLParser

# ═══════════════════════════════════════════════════════════════════
# Suite 变量缓存（跨用例传递 variables/extract）
# ═══════════════════════════════════════════════════════════════════

_suite_var_cache: dict[str, dict[str, Any]] = {}


def _suite_key(name: str, path: Path) -> str:
    return f"{name}::{path}"


def _get_suite_variables(name: str, path: Path) -> dict[str, Any]:
    return dict(_suite_var_cache.get(_suite_key(name, path), {}))


def _update_suite_variables(name: str, path: Path, new_vars: dict[str, Any]) -> None:
    key = _suite_key(name, path)
    if key not in _suite_var_cache:
        _suite_var_cache[key] = {}
    _suite_var_cache[key].update(new_vars)


# ═══════════════════════════════════════════════════════════════════
# YamlCollector — 收集入口
# ═══════════════════════════════════════════════════════════════════


class YamlCollector:
    """YAML 用例收集器 — 封装 pytest 收集入口

    使用方式（在 conftest.py 中）::

        def pytest_collect_file(parent, file_path):
            return YamlCollector.collect_file(parent, file_path)
    """

    @staticmethod
    def collect_file(parent: Any, file_path: Path) -> YamlFile | None:
        if file_path.suffix in (".yaml", ".yml"):
            return YamlFile.from_parent(parent, path=file_path)
        return None


# ═══════════════════════════════════════════════════════════════════
# YamlFile — 文件级收集器
# ═══════════════════════════════════════════════════════════════════


class YamlFile(pytest.File):
    """YAML 文件收集器 — 读取 YAML 并为每个用例生成 YamlFunction(pytest.Function)"""

    def collect(self) -> Any:
        with open(self.path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict) or "cases" not in raw:
            return

        cases_raw = raw.get("cases", [])
        suite_name = raw.get("name", self.path.stem)
        data_driven = raw.get("data_driven", {})
        parameters = data_driven.get("parameters", []) if isinstance(data_driven, dict) else []
        suite_tags = set(raw.get("tags", []))
        tags_filter = self.config.getoption("--tags")

        # 数据驱动展开
        expanded_cases: list[tuple[str, dict[str, Any]]] = []
        if parameters:
            from framework.utils.template import TemplateEngine

            tpl = TemplateEngine()
            merged_base = raw.get("variables", {})
            for param_set in parameters:
                merged = {**merged_base, **param_set}
                for c in cases_raw:
                    rendered_name = tpl.render(c.get("name", "unnamed"), merged)
                    expanded_cases.append((rendered_name, {**c, "name": rendered_name}))
        else:
            for c in cases_raw:
                expanded_cases.append((c.get("name", "unnamed"), c))

        for idx, (case_name, case_spec) in enumerate(expanded_cases):
            case_tags = set(case_spec.get("tags", []))
            all_tags = case_tags | suite_tags

            if tags_filter:
                filter_tags = {t.strip() for t in tags_filter.split(",")}
                if not all_tags.intersection(filter_tags):
                    continue

            # 生成 pytest.Function 子类节点 — 原生享受完整 fixture 注入
            item = YamlFunction.from_parent(
                self,
                name=case_name,
                callobj=_execute_yaml_case,
            )
            item._yaml_spec = case_spec
            item._yaml_suite_raw = raw
            item._yaml_suite_name = suite_name
            item._yaml_case_index = idx
            item._yaml_file_path = self.path

            for tag in all_tags:
                item.add_marker(pytest.mark.__getattr__(tag))

            yield item


# ═══════════════════════════════════════════════════════════════════
# YamlFunction(pytest.Function) — 定制 reportinfo
# ═══════════════════════════════════════════════════════════════════


class YamlFunction(pytest.Function):
    """pytest.Function 子类 — 为 YAML 用例定制 nodeid 与报告路径"""

    def reportinfo(self) -> tuple:
        file_path = getattr(self, "_yaml_file_path", self.path)
        suite = getattr(self, "_yaml_suite_name", "unknown")
        return file_path, None, f"{suite}::{self.name}"


# ═══════════════════════════════════════════════════════════════════
# _execute_yaml_case — 模块级执行函数（fixture 由 pytest 自动注入）
# ═══════════════════════════════════════════════════════════════════


def _execute_yaml_case(runner, request):
    """执行单个 YAML 测试用例。

    fixture 'runner'（function scope）由 pytest 根据 conftest.py 中定义的
    runner fixture 自动解析并注入，其依赖链（http_client, db_manager,
    test_context 等）也由 pytest 原生管理。

    fixture 'request'（内置）用于访问 request.node 获取 YAML 元数据。
    """
    from framework.models import TestSuite

    item = request.node

    parser = YAMLParser()
    suite: TestSuite = parser.parse_file(str(item._yaml_file_path))

    if item._yaml_case_index >= len(suite.cases):
        raise YamlTestException(
            f"用例索引越界: {item._yaml_case_index} (共 {len(suite.cases)} 个)"
        )

    target_case = suite.cases[item._yaml_case_index]

    # 跨用例变量传递
    session_vars = _get_suite_variables(item._yaml_suite_name, item._yaml_file_path)
    suite_variables = runner._build_suite_variables(suite)
    suite_variables.update(session_vars)

    case_result = runner.run_case(target_case, suite_variables)
    item._case_result = case_result

    if case_result.extracted_vars:
        _update_suite_variables(
            item._yaml_suite_name, item._yaml_file_path, case_result.extracted_vars,
        )

    if not case_result.passed:
        raise YamlTestException(case_result.error or "断言失败")


# ═══════════════════════════════════════════════════════════════════
# YamlTestException
# ═══════════════════════════════════════════════════════════════════


class YamlTestException(Exception):  # noqa: N818
    """YAML 测试用例失败异常"""

    pass


# ═══════════════════════════════════════════════════════════════════
# 公开 API
# ═══════════════════════════════════════════════════════════════════

__all__ = [
    "YamlCollector",
    "YamlFile",
    "YamlFunction",
    "YamlTestException",
    "_get_suite_variables",
    "_update_suite_variables",
]
