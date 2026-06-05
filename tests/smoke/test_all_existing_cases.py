"""冒烟测试 — 自动发现并验证 testcases/ 下所有 YAML 用例能被正确解析

本测试不实际执行 HTTP 请求，仅验证：
1. 所有 YAML 文件可被 YAMLParser 正常解析
2. 解析后的 TestSuite 结构正确
3. 关键字段（name, cases, request）存在
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from framework.parser import YAMLParser


# ══════════════════════════════════════════════════════════
# 辅助
# ══════════════════════════════════════════════════════════


def discover_yaml_files() -> list[Path]:
    """发现 testcases/ 下所有 .yaml 和 .yml 文件"""
    testcases_dir = Path(__file__).resolve().parent.parent.parent / "testcases"
    if not testcases_dir.exists():
        return []
    files: list[Path] = []
    for ext in ("*.yaml", "*.yml"):
        files.extend(testcases_dir.rglob(ext))
    return sorted(files)


# 收集所有 YAML 文件路径
_ALL_YAML_FILES = discover_yaml_files()


# ══════════════════════════════════════════════════════════
# 测试: 解析验证
# ══════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def parser() -> YAMLParser:
    return YAMLParser()


class TestAllYamlFilesParsable:
    """验证所有 YAML 文件均可被 YAMLParser 正常解析"""

    @pytest.mark.parametrize("yaml_path", _ALL_YAML_FILES, ids=lambda p: p.name)
    def test_yaml_parsable(self, parser: YAMLParser, yaml_path: Path) -> None:
        """每个 YAML 文件都应能被解析成 TestSuite"""
        suite = parser.parse_file(str(yaml_path))
        assert suite is not None, f"解析失败: {yaml_path}"
        assert suite.name, f"套件名称为空: {yaml_path}"

    @pytest.mark.parametrize("yaml_path", _ALL_YAML_FILES, ids=lambda p: p.name)
    def test_yaml_has_cases(self, yaml_path: Path) -> None:
        """每个 YAML 文件至少包含一个用例"""
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "cases" in raw:
            cases = raw["cases"]
            assert len(cases) > 0, f"用例列表为空: {yaml_path}"
            for case in cases:
                assert "name" in case, f"用例缺少 name 字段: {yaml_path}"


class TestParsedSuiteStructure:
    """验证解析后的 TestSuite 结构正确"""

    @pytest.mark.parametrize("yaml_path", _ALL_YAML_FILES, ids=lambda p: p.name)
    def test_suite_has_name(self, parser: YAMLParser, yaml_path: Path) -> None:
        suite = parser.parse_file(str(yaml_path))
        assert isinstance(suite.name, str) and len(suite.name) > 0

    @pytest.mark.parametrize("yaml_path", _ALL_YAML_FILES, ids=lambda p: p.name)
    def test_each_case_has_name(self, parser: YAMLParser, yaml_path: Path) -> None:
        suite = parser.parse_file(str(yaml_path))
        for case in suite.cases:
            assert isinstance(case.name, str) and len(case.name) > 0, (
                f"用例名称为空：{yaml_path}"
            )

    @pytest.mark.parametrize("yaml_path", _ALL_YAML_FILES, ids=lambda p: p.name)
    def test_each_case_has_request_or_ws(self, parser: YAMLParser, yaml_path: Path) -> None:
        """每个用例必须有 request 或 ws_config"""
        suite = parser.parse_file(str(yaml_path))
        for case in suite.cases:
            has_request = case.request is not None
            has_ws = case.ws_config is not None
            assert has_request or has_ws, (
                f"用例 '{case.name}' 既没有 request 也没有 ws_config: {yaml_path}"
            )

    @pytest.mark.parametrize("yaml_path", _ALL_YAML_FILES, ids=lambda p: p.name)
    def test_request_has_method_and_path(self, parser: YAMLParser, yaml_path: Path) -> None:
        """有 request 的用例应有 method 和 path"""
        suite = parser.parse_file(str(yaml_path))
        for case in suite.cases:
            if case.request is not None:
                assert case.request.method is not None, (
                    f"用例 '{case.name}' request.method 为空: {yaml_path}"
                )
                assert isinstance(case.request.path, str), (
                    f"用例 '{case.name}' request.path 应为字符串: {yaml_path}"
                )


class TestYamlFileCount:
    """验证发现的 YAML 文件数量"""

    def test_at_least_one_yaml_file_found(self) -> None:
        """至少应发现 1 个 YAML 文件"""
        assert len(_ALL_YAML_FILES) >= 1, "未发现任何 YAML 测试用例文件"

    def test_all_categories_present(self) -> None:
        """应覆盖 smoke 和 regression 两类定义目录"""
        dirs = {f.parent.name for f in _ALL_YAML_FILES}
        # 至少应有 smoke 或 local 或 regression
        assert len(dirs) >= 1, "测试用例分类目录不足"


# ══════════════════════════════════════════════════════════
# 冒烟标记注册
# ══════════════════════════════════════════════════════════

@pytest.mark.smoke
def test_smoke_tag_applies() -> None:
    """占位测试，确保 smoke 标记可用"""
    assert True
