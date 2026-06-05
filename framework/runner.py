"""测试执行引擎 — 编排用例执行、变量传递、断言、提取

采用策略模式（Strategy Pattern）将协议执行逻辑解耦到独立的 StepExecutor 中。
新增协议（如 gRPC）只需新建一个 executor 文件并注册，无需修改 runner.py。

插件系统集成：
- 通过 PluginManager 在关键生命周期点分发事件
- 插件可按 priority 排序，高优先级插件（数值小）先执行
- 插件间通过 PluginContext 共享数据
"""

from __future__ import annotations

import time
from typing import Any

from framework.assertion import AssertionEngine
from framework.context import TestContext
from framework.db import DBAsserter, DBConnectionManager, DBExecutor
from framework.exceptions import NoExecutorFoundError
from framework.executors.base import StepExecutor
from framework.executors.http_executor import HttpStepExecutor
from framework.executors.ws_executor import WsStepExecutor
from framework.extractor import Extractor
from framework.fixtures_loader import FixtureLoader
from framework.models import CaseResult, EnvConfig, ProjectConfig, SuiteResult, TestCase, TestSuite
from framework.plugins.base import PluginBase
from framework.plugins.manager import PluginContext, PluginManager
from framework.report.base import NoopReportAdapter, ReportAdapter
from framework.utils.logger import Logger, clear_trace_id, set_trace_id
from framework.utils.template import TemplateEngine

logger = Logger.get("runner")


class TestRunner:
    """测试执行引擎

    负责编排用例执行的完整流程：
    1. 合并变量（环境 → 套件 → 用例 → extract）
    2. 执行 setup → 插件钩子 on_setup
    3. 通过 StepExecutor 策略执行协议逻辑（HTTP/WebSocket/gRPC/...）
    4. 执行 DB 断言 → 插件钩子 on_db_query
    5. 执行 teardown → 插件钩子 on_teardown

    扩展新协议：新建 StepExecutor 子类，传入 executors 参数即可。
    """

    def __init__(
        self,
        config: ProjectConfig,
        env: EnvConfig,
        http_client: Any,  # HttpClient
        db_manager: DBConnectionManager | None = None,
        context: TestContext | None = None,
        report_adapter: ReportAdapter | None = None,
        executors: list[StepExecutor] | None = None,
        plugin_manager: PluginManager | None = None,
        plugins: list[PluginBase] | None = None,
        auto_discover_plugins: bool = True,
    ) -> None:
        self._config = config
        self._env = env
        self._http_client = http_client
        self._context = context or TestContext()
        self._template = TemplateEngine()
        self._assertion_engine = AssertionEngine()
        self._extractor = Extractor()
        self._report_adapter = report_adapter or NoopReportAdapter()

        # ── 插件系统 ──
        if plugin_manager is not None:
            self._plugin_manager = plugin_manager
        else:
            self._plugin_manager = PluginManager()
            if auto_discover_plugins:
                self._plugin_manager.discover()
            if plugins:
                for p in plugins:
                    self._plugin_manager.register(p)

        plugin_names = self._plugin_manager.plugin_names
        if plugin_names:
            logger.info("plugins_loaded", count=len(plugin_names), names=plugin_names)

        # 数据库相关（可选）
        self._db_executor: DBExecutor | None = None
        self._db_asserter: DBAsserter | None = None
        if db_manager and env.db:
            self._db_executor = DBExecutor(db_manager, env.db, self._template)
            self._db_asserter = DBAsserter(self._db_executor, self._template)

        # Fixture 加载器
        self._fixture_loader = FixtureLoader(
            http_client=http_client,
            db_executor=self._db_executor,
            template_engine=self._template,
            extractor=self._extractor,
            fixtures_config=config.fixtures,
        )

        # StepExecutor 策略链（默认：WS → HTTP）
        if executors is None:
            executors = [
                WsStepExecutor(self._template),
                HttpStepExecutor(
                    http_client=http_client,
                    template_engine=self._template,
                    assertion_engine=self._assertion_engine,
                    extractor=self._extractor,
                    report_adapter=self._report_adapter,
                    env=env,
                    plugin_manager=self._plugin_manager,
                ),
            ]
        self._executors: list[StepExecutor] = executors

    # ── 公共属性 ─────────────────────────────────────

    @property
    def plugin_manager(self) -> PluginManager:
        """插件管理器"""
        return self._plugin_manager

    @property
    def plugin_context(self) -> PluginContext:
        """插件间共享数据容器"""
        return self._plugin_manager.context

    def run_suite(self, suite: TestSuite) -> SuiteResult:
        """执行整个测试套件"""
        suite_result = SuiteResult(suite_name=suite.name)
        logger.info(
            "suite_started",
            suite_name=suite.name,
            case_count=len(suite.cases),
            tags=suite.tags,
        )

        # ── 插件钩子：on_suite_start ──
        self._plugin_manager.dispatch("suite_start", suite=suite)

        # 构建套件级变量并注入上下文
        suite_variables = self._build_suite_variables(suite)
        self._context.set_suite_vars(suite_variables)

        # 执行套件级 setup
        setup_extracted: dict[str, Any] = {}
        if suite.setup:
            try:
                # ── 插件钩子：on_setup (before) ──
                self._plugin_manager.dispatch(
                    "setup", phase="before", case=suite, variables=suite_variables
                )
                setup_extracted = self._fixture_loader.run_setup(suite.setup, suite_variables)
                suite_variables.update(setup_extracted)
                # ── 插件钩子：on_setup (after) ──
                self._plugin_manager.dispatch(
                    "setup", phase="after", case=suite, variables=suite_variables
                )
                logger.info(
                    "suite_setup_done",
                    extracted_vars=list(setup_extracted.keys()),
                )
            except Exception as e:
                self._plugin_manager.dispatch("error", error=e, case=suite)
                suite_result.setup_error = str(e)
                logger.error("suite_setup_failed", error=str(e), suite_name=suite.name)
                return suite_result

        # 执行每个用例
        for i, case in enumerate(suite.cases):
            logger.info(
                "case_starting",
                index=i + 1,
                total=len(suite.cases),
                case_name=case.name,
            )

            case_result = self.run_case(case, suite_variables)
            suite_result.case_results.append(case_result)

            # 将提取的变量传递给后续用例
            if case_result.extracted_vars:
                suite_variables.update(case_result.extracted_vars)
                self._context.update_suite_vars(case_result.extracted_vars)

            # 报告标签（通过适配器接口）
            self._report_adapter.set_case_labels(case.tags, case.priority)

        # 执行套件级 teardown
        if suite.teardown:
            try:
                # ── 插件钩子：on_teardown (before) ──
                self._plugin_manager.dispatch(
                    "teardown", phase="before", case=suite, variables=suite_variables
                )
                self._fixture_loader.run_teardown(suite.teardown, suite_variables)
                # ── 插件钩子：on_teardown (after) ──
                self._plugin_manager.dispatch(
                    "teardown", phase="after", case=suite, variables=suite_variables
                )
                logger.info("suite_teardown_done")
            except Exception as e:
                self._plugin_manager.dispatch("error", error=e, case=suite)
                suite_result.teardown_error = str(e)
                logger.warning("suite_teardown_failed", error=str(e), suite_name=suite.name)

        # ── 插件钩子：on_suite_end ──
        self._plugin_manager.dispatch("suite_end", suite=suite, result=suite_result)

        # 输出套件结果摘要
        logger.info(
            "suite_completed",
            suite_name=suite.name,
            total=suite_result.total,
            passed=suite_result.passed_count,
            failed=suite_result.failed_count,
        )

        return suite_result

    def run_case(self, case: TestCase, suite_variables: dict[str, Any]) -> CaseResult:
        """执行单个测试用例

        策略路由：遍历 self._executors，找到首个 supports(case) 为 True 的
        executor 并调用其 execute 方法。找不到时抛出 NoExecutorFoundError。
        """
        start_time = time.time()

        # ── 绑定用例级 trace_id ──
        set_trace_id(case.name)

        # ── 插件钩子：on_case_start ──
        self._plugin_manager.dispatch("case_start", case=case)

        # 检查是否跳过
        if case.skip:
            logger.info("case_skipped", case_name=case.name, reason="skip flag set")
            result = CaseResult(case_name=case.name, passed=True, error="SKIPPED")
            self._plugin_manager.dispatch("case_end", case=case, result=result)
            clear_trace_id()
            return result

        # 构建用例级变量
        variables = {**suite_variables, **case.variables}

        # 初始化上下文
        self._context.init()
        self._context.set_case_vars(variables)

        # ── 开始步骤上下文：创建 step 级隔离副本 ──
        self._context.start_step()
        # 将当前 merged vars 也写入 step 层供 executor 读取（保持兼容）
        self._context.get_variables().update(variables)

        case_result = CaseResult(case_name=case.name, passed=True)

        try:
            # 执行用例级 setup
            if case.setup:
                # ── 插件钩子：on_setup (before) ──
                self._plugin_manager.dispatch(
                    "setup", phase="before", case=case, variables=variables
                )
                setup_vars = self._fixture_loader.run_setup(case.setup, variables)
                variables.update(setup_vars)
                self._context.get_variables().update(setup_vars)
                # ── 插件钩子：on_setup (after) ──
                self._plugin_manager.dispatch(
                    "setup", phase="after", case=case, variables=variables
                )

            # 策略路由：遍历 executors 找到匹配的执行器
            matched = False
            for executor in self._executors:
                if executor.supports(case):
                    case_result = executor.execute(case, self._context, variables)
                    matched = True
                    break

            if not matched:
                raise NoExecutorFoundError(case.name)

            # 执行数据库断言
            if case.db_asserts and self._db_asserter:
                for db_assert in case.db_asserts:
                    # ── 插件钩子：on_db_query (before) ──
                    self._plugin_manager.dispatch(
                        "db_query",
                        phase="before",
                        case=case,
                        sql=db_assert.sql,
                    )
                    db_result = self._db_asserter.assert_query(db_assert, variables)
                    # ── 插件钩子：on_db_query (after) ──
                    self._plugin_manager.dispatch(
                        "db_query",
                        phase="after",
                        case=case,
                        sql=db_assert.sql,
                        result=db_result,
                    )
                    if not db_result.passed:
                        case_result.passed = False
                        if case_result.error:
                            case_result.error += f"; DB断言失败: {db_result}"
                        else:
                            case_result.error = f"DB断言失败: {db_result}"

            # 执行用例级 teardown
            if case.teardown:
                # ── 插件钩子：on_teardown (before) ──
                self._plugin_manager.dispatch(
                    "teardown", phase="before", case=case, variables=variables
                )
                self._fixture_loader.run_teardown(case.teardown, variables)
                # ── 插件钩子：on_teardown (after) ──
                self._plugin_manager.dispatch(
                    "teardown", phase="after", case=case, variables=variables
                )

        except NoExecutorFoundError:
            self._plugin_manager.dispatch("case_end", case=case, result=case_result)
            raise  # 框架配置错误，直接向上传播，不做捕获
        except Exception as e:
            case_result.passed = False
            case_result.error = str(e)
            # ── 插件钩子：on_error ──
            self._plugin_manager.dispatch("error", error=e, case=case)
            logger.error("case_execution_error", case_name=case.name, error=str(e), exc_info=True)

        case_result.elapsed_ms = (time.time() - start_time) * 1000

        # ── 结束步骤上下文：将步骤提取变量提升到 case 层 ──
        self._context.end_step(promote=True)
        # 记录用例执行后的全量变量（含 suite + case + 步骤提取）
        case_result.extracted_vars = self._context.get_all_variables()

        # ── 插件钩子：on_case_end ──
        self._plugin_manager.dispatch("case_end", case=case, result=case_result)

        status = "PASS" if case_result.passed else "FAIL"
        logger.info(
            "case_completed",
            case_name=case.name,
            status=status,
            elapsed_ms=round(case_result.elapsed_ms),
            error=case_result.error if not case_result.passed else None,
        )

        # ── 解绑 trace_id ──
        clear_trace_id()

        return case_result

    def _build_suite_variables(self, suite: TestSuite) -> dict[str, Any]:
        """构建套件级变量（合并环境 + 套件）"""
        variables: dict[str, Any] = {}

        # 内置变量
        variables["base_url"] = suite.base_url or self._env.base_url

        # 环境变量
        env_vars = {**self._env.variables}
        env_vars["base_url"] = self._env.base_url
        env_vars["ws_url"] = self._env.ws_url
        variables["env"] = env_vars

        # 套件变量
        variables.update(suite.variables)

        return variables
