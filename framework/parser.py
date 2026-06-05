"""YAML 用例解析器 — 解析 YAML 文件为结构化 TestCase/TestSuite 对象"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from framework.models import (
    AssertItem,
    BodyType,
    DBAssertItem,
    ExtractItem,
    FixtureAction,
    HttpMethod,
    HttpRequest,
    TestCase,
    TestSuite,
    WSConfig,
    WSMessage,
)
from framework.utils.logger import Logger
from framework.utils.template import TemplateEngine

logger = Logger.get("parser")


class YAMLParser:
    """YAML 用例解析器"""

    def __init__(self, template_engine: TemplateEngine | None = None) -> None:
        self._template = template_engine or TemplateEngine()

    def parse_file(self, file_path: str, variables: dict[str, Any] | None = None) -> TestSuite:
        """解析单个 YAML 文件为 TestSuite"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"用例文件不存在: {file_path}")

        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise ValueError(f"YAML 文件格式错误（应为字典）: {file_path}")

        variables = variables or {}

        # 解析阶段不做模板替换，保留原始 {{var}} 占位符
        # 模板替换在 runner 执行时按实际变量进行
        rendered_raw = raw

        suite = self._parse_suite(rendered_raw, str(path))
        logger.info(f"解析用例文件: {path.name}, 用例数: {len(suite.cases)}")
        return suite

    def parse_dir(self, dir_path: str, variables: dict[str, Any] | None = None) -> list[TestSuite]:
        """解析目录下所有 YAML 文件"""
        path = Path(dir_path)
        if not path.is_dir():
            raise NotADirectoryError(f"目录不存在: {dir_path}")

        suites: list[TestSuite] = []
        for yaml_file in sorted(path.rglob("*.yaml")):
            try:
                suite = self.parse_file(str(yaml_file), variables)
                suites.append(suite)
            except Exception as e:
                logger.error(f"解析文件失败 {yaml_file}: {e}")

        # 也支持 .yml 后缀
        for yml_file in sorted(path.rglob("*.yml")):
            if yml_file.with_suffix(".yaml").exists():
                continue  # 避免重复
            try:
                suite = self.parse_file(str(yml_file), variables)
                suites.append(suite)
            except Exception as e:
                logger.error(f"解析文件失败 {yml_file}: {e}")

        logger.info(f"目录解析完成: {dir_path}, 共 {len(suites)} 个套件")
        return suites

    def collect(self, path: str, tags: list[str] | None = None) -> list[tuple[str, TestSuite]]:
        """收集用例，支持文件或目录，可按标签过滤"""
        target = Path(path)
        suites: list[TestSuite] = []

        if target.is_file():
            suites.append(self.parse_file(str(target)))
        elif target.is_dir():
            suites = self.parse_dir(str(target))
        else:
            logger.error(f"路径不存在: {path}")
            return []

        if tags:
            suites = self._filter_by_tags(suites, tags)

        result: list[tuple[str, TestSuite]] = []
        for suite in suites:
            for case in suite.cases:
                result.append((case.name, suite))
        return result

    # ---------- 解析内部方法 ----------

    def _parse_suite(self, raw: dict[str, Any], source_file: str) -> TestSuite:
        """解析顶层套件配置"""
        suite = TestSuite(
            name=raw.get("name", "Unnamed Suite"),
            description=raw.get("description", ""),
            base_url=raw.get("base_url", ""),
            tags=raw.get("tags", []),
            priority=raw.get("priority", "P1"),
            variables=raw.get("variables", {}),
            setup=self._parse_fixtures(raw.get("setup", [])),
            teardown=self._parse_fixtures(raw.get("teardown", [])),
            data_driven=(
                raw.get("data_driven", {}).get("parameters", [])
                if isinstance(raw.get("data_driven"), dict)
                else []
            ),
            source_file=source_file,
        )

        # 解析用例列表（数据驱动展开）
        cases_raw = raw.get("cases", [])
        if suite.data_driven:
            import copy

            for param_set in suite.data_driven:
                for case_raw in cases_raw:
                    merged_vars = {**suite.variables, **param_set}
                    case_raw_copy = copy.deepcopy(case_raw)
                    case = self._parse_case(case_raw_copy, suite)
                    case.name = self._template.render(case.name, merged_vars)
                    case.variables.update(param_set)
                    suite.cases.append(case)
        else:
            for case_raw in cases_raw:
                case = self._parse_case(case_raw, suite)
                suite.cases.append(case)

        return suite

    def _parse_case(self, raw: dict[str, Any], suite: TestSuite) -> TestCase:
        """解析单个测试用例"""
        # 合并标签（套件级 + 用例级）
        tags = list(set(suite.tags + raw.get("tags", [])))

        case = TestCase(
            name=raw.get("name", "Unnamed Case"),
            description=raw.get("description", ""),
            tags=tags,
            priority=raw.get("priority", suite.priority),
            skip=raw.get("skip", False),
            skip_if=raw.get("skip_if", ""),
            variables=raw.get("variables", {}),
            setup=self._parse_fixtures(raw.get("setup", [])),
            teardown=self._parse_fixtures(raw.get("teardown", [])),
            source_file=suite.source_file,
        )

        # 解析请求
        req_raw = raw.get("request")
        if req_raw:
            case.request = self._parse_request(req_raw)

        # 解析 WebSocket 配置
        ws_raw = raw.get("ws_config")
        if ws_raw:
            case.ws_config = self._parse_ws_config(ws_raw)

        # 解析断言
        expect_raw = raw.get("expect", {})
        case.assertions = self._parse_assertions(expect_raw)

        # 解析提取
        extract_raw = raw.get("extract", {})
        case.extracts = self._parse_extracts(extract_raw)

        # 解析数据库断言
        db_assert_raw = raw.get("db_assert", [])
        case.db_asserts = self._parse_db_asserts(db_assert_raw)

        return case

    def _parse_request(self, raw: dict[str, Any]) -> HttpRequest:
        """解析 HTTP 请求"""
        method_str = raw.get("method", "GET").upper()
        try:
            method = HttpMethod(method_str)
        except ValueError:
            logger.warning(f"未知 HTTP 方法: {method_str}，默认使用 GET")
            method = HttpMethod.GET

        body_type_str = raw.get("body_type", "json")
        try:
            body_type = BodyType(body_type_str)
        except ValueError:
            body_type = BodyType.JSON

        # 自动推断 body_type
        if body_type == BodyType.JSON and raw.get("body") is None and raw.get("files"):
            body_type = BodyType.MULTIPART

        return HttpRequest(
            method=method,
            path=raw.get("path", ""),
            headers=raw.get("headers", {}),
            params=raw.get("params", {}),
            body=raw.get("body"),
            body_type=body_type,
            timeout=raw.get("timeout"),
            verify_ssl=raw.get("verify_ssl"),
            files=raw.get("files", {}),
            auth=raw.get("auth"),
        )

    def _parse_ws_config(self, raw: dict[str, Any]) -> WSConfig:
        """解析 WebSocket 配置"""
        messages: list[WSMessage] = []
        for msg_raw in raw.get("messages", []):
            messages.append(
                WSMessage(
                    type=msg_raw.get("type", "send"),
                    data=msg_raw.get("data", ""),
                    timeout=msg_raw.get("timeout"),
                    expect=msg_raw.get("expect", {}),
                )
            )

        return WSConfig(
            url=raw.get("url", ""),
            headers=raw.get("headers", {}),
            timeout=raw.get("timeout", 30),
            messages=messages,
            close_after=raw.get("close_after", True),
        )

    def _parse_assertions(self, expect: dict[str, Any]) -> list[AssertItem]:
        """解析断言配置"""
        items: list[AssertItem] = []

        # 状态码断言
        if "status_code" in expect:
            items.append(
                AssertItem(
                    path="status_code",
                    expected=expect["status_code"],
                    operator="eq",
                )
            )

        # 响应时间断言
        if "response_time" in expect:
            rt_val = expect["response_time"]
            # 支持 "<2000" 简写形式，自动解析为 lt 操作符
            if isinstance(rt_val, str) and rt_val.startswith("<"):
                items.append(
                    AssertItem(path="response_time", expected=float(rt_val[1:]), operator="lt")
                )
            elif isinstance(rt_val, str) and rt_val.startswith(">"):
                items.append(
                    AssertItem(path="response_time", expected=float(rt_val[1:]), operator="gt")
                )
            else:
                items.append(AssertItem(path="response_time", expected=rt_val, operator="lt"))

        # Body 断言
        body_expect = expect.get("body", {})
        if body_expect:
            items.extend(self._parse_body_assertions(body_expect, prefix="body"))

        # JSONPath 断言
        jsonpath_expect = expect.get("jsonpath", {})
        if jsonpath_expect:
            for path, spec in jsonpath_expect.items():
                if isinstance(spec, dict):
                    items.append(
                        AssertItem(
                            path=path,
                            expected=spec.get("value", spec.get("expected")),
                            operator=spec.get("operator", "eq"),
                        )
                    )
                else:
                    # 简写形式: $.path: "value" 或 $.path: "regex"
                    if isinstance(spec, str) and (spec.startswith(".*") or spec.startswith("^")):
                        items.append(AssertItem(path=path, expected=spec, operator="matches"))
                    else:
                        items.append(AssertItem(path=path, expected=spec, operator="eq"))

        # Header 断言
        header_expect = expect.get("headers", {})
        if header_expect:
            for name, value in header_expect.items():
                items.append(
                    AssertItem(
                        path=f"headers.{name}",
                        expected=value,
                        operator=(
                            "eq"
                            if not isinstance(value, str) or not value.startswith("not_")
                            else value
                        ),
                    )
                )

        return items

    def _parse_body_assertions(
        self, body: dict[str, Any], prefix: str = "body"
    ) -> list[AssertItem]:
        """递归解析 Body 断言"""
        items: list[AssertItem] = []
        for key, value in body.items():
            path = f"{prefix}.{key}"
            if isinstance(value, dict):
                # 递归处理嵌套对象
                items.extend(self._parse_body_assertions(value, prefix=path))
            elif isinstance(value, str) and value == "not_null":
                items.append(AssertItem(path=path, expected=None, operator="not_null"))
            elif isinstance(value, str) and value == "is_null":
                items.append(AssertItem(path=path, expected=None, operator="is_null"))
            else:
                items.append(AssertItem(path=path, expected=value, operator="eq"))
        return items

    def _parse_extracts(self, raw: dict[str, Any]) -> list[ExtractItem]:
        """解析变量提取配置"""
        items: list[ExtractItem] = []
        for var_name, source in raw.items():
            if isinstance(source, str):
                # 判断 source 类型
                if source.startswith("$."):
                    source_type = "jsonpath"
                elif source.startswith("header."):
                    source_type = "header"
                    source = source[7:]  # 去掉 header. 前缀
                elif source.startswith("regex:"):
                    source_type = "body_regex"
                    source = source[6:]
                else:
                    source_type = "jsonpath"

                items.append(
                    ExtractItem(
                        var_name=var_name,
                        source=source,
                        source_type=source_type,
                    )
                )
            elif isinstance(source, dict):
                items.append(
                    ExtractItem(
                        var_name=var_name,
                        source=source.get("source", source.get("path", "")),
                        source_type=source.get("type", "jsonpath"),
                        default=source.get("default"),
                    )
                )
        return items

    def _parse_db_asserts(self, raw: list[dict[str, Any]]) -> list[DBAssertItem]:
        """解析数据库断言"""
        items: list[DBAssertItem] = []
        for item in raw:
            items.append(
                DBAssertItem(
                    connection=item.get("connection", "main_db"),
                    sql=item.get("sql", ""),
                    expect=item.get("expect", {}),
                    fetch_one=item.get("fetch_one", True),
                )
            )
        return items

    def _parse_fixtures(self, raw: list[dict[str, Any] | str]) -> list[FixtureAction]:
        """解析 fixture 动作列表"""
        actions: list[FixtureAction] = []
        for item in raw:
            if isinstance(item, dict):
                # 支持两种格式:
                # 1. action_type: xxx / config: {...}
                # 2. 直接用 key 表示类型: db_execute: {...}
                if "action_type" in item:
                    actions.append(
                        FixtureAction(
                            action_type=item["action_type"],
                            config=item.get("config", {}),
                        )
                    )
                else:
                    # 尝试从 key 推断类型
                    for key, value in item.items():
                        if key in ("api_call", "db_execute", "wait", "shell"):
                            actions.append(
                                FixtureAction(
                                    action_type=key,
                                    config=value if isinstance(value, dict) else {},
                                )
                            )
                            break
        return actions

    def _filter_by_tags(self, suites: list[TestSuite], tags: list[str]) -> list[TestSuite]:
        """按标签过滤用例"""
        filtered: list[TestSuite] = []
        for suite in suites:
            matching_cases = [case for case in suite.cases if any(tag in case.tags for tag in tags)]
            if matching_cases:
                new_suite = TestSuite(
                    name=suite.name,
                    description=suite.description,
                    base_url=suite.base_url,
                    tags=suite.tags,
                    priority=suite.priority,
                    variables=suite.variables,
                    setup=suite.setup,
                    teardown=suite.teardown,
                    cases=matching_cases,
                    source_file=suite.source_file,
                )
                filtered.append(new_suite)
        return filtered
