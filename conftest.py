"""pytest 全局 conftest — YAML 用例收集 + Fixture 注入"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Generator

import pytest
import yaml

from framework.client import HttpClient
from framework.config import ConfigLoader
from framework.context import TestContext
from framework.db import DBConnectionManager
from framework.models import CaseResult, EnvConfig, ProjectConfig
from framework.parser import YAMLParser
from framework.report import AllureAdapter
from framework.runner import TestRunner
from framework.utils.logger import Logger

# ==================== pytest 命令行选项 ====================


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--env", default="dev", help="测试环境: dev/staging/production")
    parser.addoption("--tags", default="", help="标签过滤: smoke,regression,P0")


# ==================== Session 级 Fixture ====================


@pytest.fixture(scope="session")
def project_config(request: pytest.FixtureRequest) -> ProjectConfig:
    """加载项目配置"""
    env_name = request.config.getoption("--env")
    loader = ConfigLoader()
    config, _ = loader.load(env_name)
    Logger.setup(config.logging)
    return config


@pytest.fixture(scope="session")
def env_config(request: pytest.FixtureRequest) -> EnvConfig:
    """环境配置"""
    env_name = request.config.getoption("--env")
    loader = ConfigLoader()
    _, env = loader.load(env_name)
    AllureAdapter.set_environment(env)
    return env


@pytest.fixture(scope="session")
def db_manager(env_config: EnvConfig) -> Generator[DBConnectionManager, None, None]:
    """数据库连接管理器"""
    manager = DBConnectionManager()
    yield manager
    manager.close_all()


@pytest.fixture(scope="session")
def http_client(
    project_config: ProjectConfig, env_config: EnvConfig
) -> Generator[HttpClient, None, None]:
    """HTTP 客户端（session 级复用连接）"""
    client = HttpClient(
        config=project_config.http,
        base_url=env_config.base_url,
    )
    yield client
    client.close()


# ==================== Case 级 Fixture ====================


@pytest.fixture
def test_context() -> Generator[TestContext, None, None]:
    """每个用例独立的测试上下文"""
    TestContext.init()
    yield TestContext()


@pytest.fixture
def runner(
    project_config: ProjectConfig,
    env_config: EnvConfig,
    http_client: HttpClient,
    db_manager: DBConnectionManager,
    test_context: TestContext,
) -> TestRunner:
    """测试执行引擎"""
    return TestRunner(
        config=project_config,
        env=env_config,
        http_client=http_client,
        db_manager=db_manager,
        context=test_context,
    )


# ==================== 套件变量缓存（跨用例变量传递）====================

import threading as _threading  # noqa: E402

_suite_var_cache: dict[str, dict[str, Any]] = {}
_suite_var_lock = _threading.Lock()


def _suite_key(name: str, path: Path) -> str:
    return f"{name}::{path}"


def _get_suite_variables(name: str, path: Path) -> dict[str, Any]:
    key = _suite_key(name, path)
    with _suite_var_lock:
        return dict(_suite_var_cache.get(key, {}))


def _update_suite_variables(name: str, path: Path, new_vars: dict[str, Any]) -> None:
    key = _suite_key(name, path)
    with _suite_var_lock:
        if key not in _suite_var_cache:
            _suite_var_cache[key] = {}
        _suite_var_cache[key].update(new_vars)


# ==================== YAML 用例收集 ====================


def pytest_collect_file(parent: Any, file_path: Path) -> Any:
    """pytest hook: 收集 YAML 文件作为测试用例"""
    if file_path.suffix in (".yaml", ".yml"):
        return YamlFile.from_parent(parent, path=file_path)


class YamlFile(pytest.File):
    """YAML 文件收集器"""

    def collect(self) -> Any:
        # 读取 YAML 获取用例列表
        with open(self.path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict) or "cases" not in raw:
            return

        cases_raw = raw.get("cases", [])
        suite_name = raw.get("name", self.path.stem)
        data_driven = raw.get("data_driven", {})
        parameters = data_driven.get("parameters", []) if isinstance(data_driven, dict) else []

        # 标签过滤
        tags_filter = self.config.getoption("--tags")

        # 构建用例列表（含数据驱动展开）
        expanded_cases: list[tuple[str, dict[str, Any]]] = []
        if parameters:
            for param_set in parameters:
                for case_raw in cases_raw:
                    # 用参数替换用例名中的变量
                    from framework.utils.template import TemplateEngine

                    tpl = TemplateEngine()
                    merged = {**(raw.get("variables", {})), **param_set}
                    rendered_name = tpl.render(case_raw.get("name", "unnamed"), merged)
                    expanded_cases.append((rendered_name, {**case_raw, "name": rendered_name}))
        else:
            for case_raw in cases_raw:
                expanded_cases.append((case_raw.get("name", "unnamed"), case_raw))

        for idx, (case_name, case_spec) in enumerate(expanded_cases):
            # 标签过滤
            if tags_filter:
                case_tags = set(case_spec.get("tags", []))
                suite_tags = set(raw.get("tags", []))
                all_tags = case_tags | suite_tags
                filter_tags = {t.strip() for t in tags_filter.split(",")}
                if not all_tags.intersection(filter_tags):
                    continue

            yield YamlItem.from_parent(
                self,
                name=case_name,
                spec=case_spec,
                suite_raw=raw,
                suite_name=suite_name,
                case_index=idx,
            )


class YamlItem(pytest.Item):
    """单个 YAML 测试用例"""

    def __init__(
        self,
        name: str,
        parent: Any,
        spec: dict[str, Any],
        suite_raw: dict[str, Any],
        suite_name: str,
        case_index: int = 0,
    ) -> None:
        super().__init__(name, parent)
        self.spec = spec
        self.suite_raw = suite_raw
        self.suite_name = suite_name
        self.case_index = case_index
        self._case_result: CaseResult | None = None

        # 注册 markers，使 pytest -m 过滤生效
        case_tags = set(spec.get("tags", []))
        suite_tags = set(suite_raw.get("tags", []))
        all_tags = case_tags | suite_tags
        for tag in all_tags:
            self.add_marker(pytest.mark.__getattr__(tag))

    def runtest(self) -> None:
        """执行测试用例"""
        # 解析用例
        parser = YAMLParser()
        suite = parser.parse_file(str(self.path))

        # 通过索引找到对应的用例（避免名称匹配问题）
        if self.case_index >= len(suite.cases):
            raise YamlTestException(f"用例索引越界: {self.case_index} (共 {len(suite.cases)} 个)")

        target_case = suite.cases[self.case_index]

        # 获取 runner（从 fixture）
        runner = self._get_runner()

        # 使用 session 级变量缓存，实现跨用例变量传递
        session_vars = _get_suite_variables(self.suite_name, self.path)
        suite_variables = runner._build_suite_variables(suite)
        suite_variables.update(session_vars)

        # 执行用例
        case_result = runner.run_case(target_case, suite_variables)
        self._case_result = case_result

        # 将提取的变量存回 session 缓存
        if case_result.extracted_vars:
            _update_suite_variables(self.suite_name, self.path, case_result.extracted_vars)

        if not case_result.passed:
            raise YamlTestException(case_result.error or "断言失败")

    def _get_runner(self) -> TestRunner:
        """获取 TestRunner 实例"""
        # 从 session 的 fixture cache 中获取
        session = self.session
        # 直接构造（简化实现，实际可通过 fixture 注入）
        env_name = session.config.getoption("--env")
        loader = ConfigLoader()
        project_cfg, env_cfg = loader.load(env_name)
        Logger.setup(project_cfg.logging)

        client = HttpClient(config=project_cfg.http, base_url=env_cfg.base_url)
        db_mgr = DBConnectionManager()
        ctx = TestContext()

        return TestRunner(
            config=project_cfg,
            env=env_cfg,
            http_client=client,
            db_manager=db_mgr,
            context=ctx,
        )

    def repr_failure(self, excinfo: Any, style: Any = None) -> str:
        """自定义失败信息"""
        if isinstance(excinfo.value, YamlTestException):
            lines = [
                f"用例失败: {self.name}",
                f"套件: {self.suite_name}",
                f"原因: {excinfo.value}",
            ]
            if self._case_result and self._case_result.assertion_report:
                lines.append("断言详情:")
                for r in self._case_result.assertion_report.results:
                    lines.append(f"  {r}")
            return "\n".join(lines)
        return super().repr_failure(excinfo, style)

    def reportinfo(self) -> tuple:
        return self.path, None, f"{self.suite_name}::{self.name}"


class YamlTestException(Exception):  # noqa: N818
    """YAML 测试用例失败异常"""

    pass


# ==================== Allure 集成 ====================


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: Any, call: Any) -> Any:
    """pytest hook: 测试完成后附加信息到 Allure"""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and isinstance(item, YamlItem):
        if item._case_result:
            result = item._case_result
            if result.request:
                AllureAdapter.attach_request(result.request, result.url)
            if result.response:
                AllureAdapter.attach_response(result.response)
            if result.assertion_report:
                AllureAdapter.attach_assertions(result.assertion_report)
