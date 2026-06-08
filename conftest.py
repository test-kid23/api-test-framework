"""pytest conftest — 收集逻辑已下沉至 framework.collector，fixture 走原生路径

持久化报告：
- _persistence  fixture（session scope）：创建 SQLAlchemy AsyncEngine + 执行记录。
- pytest_runtest_makereport 钩子：每个用例结束后将 CaseResult 写入 execution_results 表。
- pytest_sessionfinish 钩子：全部用例结束后更新 execution 状态为 passed/failed，
  并根据配置触发通知。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from framework.client import HttpClient
from framework.collector import YamlCollector
from framework.config import ConfigLoader
from framework.context import TestContext
from framework.db import DBConnectionManager
from framework.models import EnvConfig, ProjectConfig
from framework.notifications.service import NotificationService
from framework.persistence.bridge import run_async
from framework.persistence.database import create_async_engine
from framework.persistence.models.base import Base
from framework.persistence.models.execution import ExecutionModel, ExecutionResultModel
from framework.persistence.repositories.execution_repo import ExecutionResultRepository
from framework.report import AllureReportAdapter, create_report_adapter
from framework.report.base import ReportAdapter
from framework.runner import TestRunner
from framework.utils.logger import Logger


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--env", default="dev", help="测试环境: dev/staging/production")
    parser.addoption("--tags", default="", help="标签过滤: smoke,regression,P0")
    parser.addoption("--no-persist", action="store_true", default=False, help="禁用本次测试结果持久化到数据库")


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


# ── 数据库持久化 ──────────────────────────────────────────────────


_saved_results: int = 0  # 计数器：已持久化的用例数
_failed_cases: list[dict[str, str]] = []  # 失败用例收集器（供通知使用）


@pytest.fixture(scope="session")
def _persistence(request: pytest.FixtureRequest) -> Generator[dict[str, Any], None, None]:
    """Session 级持久化基础设施：引擎 + 执行记录。

    自动建表 → 创建 execution 记录 → 测试执行 → 更新 execution 状态。
    """
    global _saved_results
    _saved_results = 0

    env_name = request.config.getoption("--env", "local")
    loader = ConfigLoader()
    config, _ = loader.load(env_name)

    # --no-persist 命令行开关：优先级最高，传参时跳过所有持久化
    if request.config.getoption("--no-persist", default=False):
        yield {}
        return

    # 持久化开关：关闭时跳过所有数据库操作
    if not config.persistence.get("enabled", True):
        yield {}
        return

    engine = create_async_engine(config.db, echo=False)

    # 建表（幂等）
    async def _create_tables() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    run_async(_create_tables())

    # 创建执行记录
    execution_id = uuid.uuid4()

    async def _start_execution() -> None:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            record = ExecutionModel(
                id=execution_id,
                status="running",
                trigger="manual",
                env=env_name,
                started_at=datetime.now(timezone.utc),
            )
            session.add(record)
            await session.commit()

    run_async(_start_execution())

    state: dict[str, Any] = {"engine": engine, "execution_id": execution_id}
    request.config._persistence_state = state  # type: ignore[attr-defined]

    yield state

    # ── session 结束：更新执行记录最终状态 ──
    async def _finish_execution() -> None:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            result = await session.execute(
                select(ExecutionModel).where(ExecutionModel.id == execution_id)
            )
            exec_record = result.scalar_one_or_none()
            if exec_record is None:
                return
            exec_record.finished_at = datetime.now(timezone.utc)
            # 根据持久化结果数推断状态
            if _saved_results == 0:
                exec_record.status = "error"
            else:
                # 用 passed 计数判断
                count_result = await session.execute(
                    select(ExecutionResultModel).where(
                        ExecutionResultModel.execution_id == execution_id,
                        ExecutionResultModel.passed == True,  # noqa: E712
                    )
                )
                passed_count = len(count_result.scalars().all())
                exec_record.status = "failed" if passed_count < _saved_results else "passed"
            await session.commit()

    run_async(_finish_execution())

    async def _dispose() -> None:
        await engine.dispose()

    run_async(_dispose())


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session) -> None:
    """Session 结束时触发通知（如已配置）。

    集成 NotificationService，根据配置的通知规则发送多渠道通知。
    """
    global _saved_results, _failed_cases

    # 通知仅在持久化启用且有结果时才运行
    if _saved_results == 0:
        return

    # 获取配置
    env_name = session.config.getoption("--env", "dev")
    loader = ConfigLoader()
    project_config, env_config = loader.load(env_name)

    notifications_cfg = project_config.notifications
    if not notifications_cfg.get("enabled", False):
        return

    try:
        service = NotificationService.from_config(notifications_cfg, env_name=env_config.name)
        passed_count = _saved_results - len(_failed_cases)
        failed_count = len(_failed_cases)

        import asyncio

        asyncio.run(
            service.notify_result(
                suite_name=f"pytest-{env_name}",
                total=_saved_results,
                passed=passed_count,
                failed=failed_count,
                failed_cases=_failed_cases,
            )
        )
    except Exception as e:
        Logger.get("conftest").warning(
            "pytest_notification_failed",
            error=str(e),
        )


# ── YAML 收集 + 报告 + 持久化 ──────────────────────────────────────


def pytest_collect_file(parent: Any, file_path: Path) -> Any:
    return YamlCollector.collect_file(parent, file_path)


@pytest.fixture(scope="session", autouse=True)
def _auto_persistence(_persistence: dict[str, Any]) -> dict[str, Any]:
    """自动注入持久化基础设施，确保所有 session 都会创建 engine + execution。"""
    return _persistence


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

        # ── 持久化到数据库 ──
        _save_case_result(item, case_result)


def _save_case_result(item: Any, case_result: Any) -> None:
    """将单个 CaseResult 通过 ExecutionResultRepository 写入 execution_results 表。"""
    global _saved_results, _failed_cases

    persistence = getattr(item.config, "_persistence_state", None)
    if persistence is None:
        return

    engine = persistence["engine"]
    execution_id = persistence["execution_id"]
    suite_name = getattr(item, "_yaml_suite_name", "unknown")
    case_name = getattr(case_result, "case_name", item.name)

    # 跟踪失败用例
    if getattr(case_result, "passed", True) is False:
        _failed_cases.append({
            "name": f"{suite_name}::{case_name}",
            "error": getattr(case_result, "error", "未知错误") or "未知错误",
        })

    async def _save() -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            repo = ExecutionResultRepository(session)
            await repo.save_result(
                execution_id=execution_id,
                case_result=case_result,
                case_id=None,
            )
            # 更新 case_name 为完整的 suite::case 格式
            saved = await repo.list_by_execution(execution_id)
            for record in saved:
                if record.case_name == case_result.case_name:
                    record.case_name = f"{suite_name}::{case_name}"
            await session.commit()

    try:
        run_async(_save())
        _saved_results += 1
    except Exception:
        Logger.get("conftest").warning(
            "persist_case_result_failed",
            case_name=f"{suite_name}::{case_name}",
            exc_info=True,
        )
