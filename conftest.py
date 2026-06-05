"""pytest conftest — 收集逻辑已下沉至 framework.collector，fixture 走原生路径"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Generator

import pytest

from framework.client import HttpClient
from framework.collector import YamlCollector
from framework.config import ConfigLoader
from framework.context import TestContext
from framework.db import DBConnectionManager
from framework.models import EnvConfig, ProjectConfig
from framework.report import AllureReportAdapter, create_report_adapter
from framework.report.base import ReportAdapter
from framework.runner import TestRunner
from framework.utils.logger import Logger


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--env", default="dev", help="测试环境: dev/staging/production")
    parser.addoption("--tags", default="", help="标签过滤: smoke,regression,P0")


# ── Session Fixtures ──────────────────────────────────────────────


@pytest.fixture(scope="session")
def project_config(request: pytest.FixtureRequest) -> ProjectConfig:
    env_name = request.config.getoption("--env")
    loader = ConfigLoader()
    config, _ = loader.load(env_name)
    Logger.setup(config.logging)
    return config


@pytest.fixture(scope="session")
def report_adapter(project_config: ProjectConfig) -> ReportAdapter:
    return create_report_adapter(project_config)


@pytest.fixture(scope="session")
def env_config(
    request: pytest.FixtureRequest, report_adapter: ReportAdapter,
) -> EnvConfig:
    env_name = request.config.getoption("--env")
    loader = ConfigLoader()
    _, env = loader.load(env_name)
    report_adapter.set_environment(env)
    return env


@pytest.fixture(scope="session")
def db_manager(env_config: EnvConfig) -> Generator[DBConnectionManager, None, None]:
    manager = DBConnectionManager()
    yield manager
    manager.close_all()


@pytest.fixture(scope="session")
def http_client(
    project_config: ProjectConfig, env_config: EnvConfig,
) -> Generator[HttpClient, None, None]:
    client = HttpClient(config=project_config.http, base_url=env_config.base_url)
    yield client
    client.close()


# ── Case Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def test_context() -> Generator[TestContext, None, None]:
    ctx = TestContext()
    ctx.init()
    yield ctx


@pytest.fixture
def runner(
    project_config: ProjectConfig,
    env_config: EnvConfig,
    http_client: HttpClient,
    db_manager: DBConnectionManager,
    test_context: TestContext,
    report_adapter: ReportAdapter,
) -> TestRunner:
    return TestRunner(
        config=project_config,
        env=env_config,
        http_client=http_client,
        db_manager=db_manager,
        context=test_context,
        report_adapter=report_adapter,
    )


# ── YAML 收集 + 报告 ──────────────────────────────────────────────


def pytest_collect_file(parent: Any, file_path: Path) -> Any:
    return YamlCollector.collect_file(parent, file_path)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: Any, call: Any) -> Any:
    outcome = yield
    report = outcome.get_result()
    case_result = getattr(item, "_case_result", None)
    if report.when == "call" and case_result:
        adapter = AllureReportAdapter()
        if case_result.request:
            adapter.attach_request(case_result.request, case_result.url)
        if case_result.response:
            adapter.attach_response(case_result.response)
        if case_result.assertion_report:
            adapter.attach_assertions(case_result.assertion_report)
