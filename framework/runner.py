"""测试执行引擎 — 编排用例执行、变量传递、断言、提取

采用策略模式（Strategy Pattern）将协议执行逻辑解耦到独立的 StepExecutor 中。
新增协议（如 gRPC）只需新建一个 executor 文件并注册，无需修改 runner.py。
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
from framework.report import AllureAdapter
from framework.utils.logger import Logger
from framework.utils.template import TemplateEngine

logger = Logger.get("runner")


class TestRunner:
    """测试执行引擎

    负责编排用例执行的完整流程：
    1. 合并变量（环境 → 套件 → 用例 → extract）
    2. 执行 setup
    3. 通过 StepExecutor 策略执行协议逻辑（HTTP/WebSocket/gRPC/...）
    4. 执行 DB 断言
    5. 执行 teardown

    扩展新协议：新建 StepExecutor 子类，传入 executors 参数即可。
    """

    def __init__(
        self,
        config: ProjectConfig,
        env: EnvConfig,
        http_client: Any,  # HttpClient
        db_manager: DBConnectionManager | None = None,
        context: TestContext | None = None,
        executors: list[StepExecutor] | None = None,
    ) -> None:
        self._config = config
        self._env = env
        self._http_client = http_client
        self._context = context or TestContext()
        self._template = TemplateEngine()
        self._assertion_engine = AssertionEngine()
        self._extractor = Extractor()
        self._allure = AllureAdapter()

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
                    allure=self._allure,
                    env=env,
                ),
            ]
        self._executors: list[StepExecutor] = executors

    def run_suite(self, suite: TestSuite) -> SuiteResult:
        """执行整个测试套件"""
        suite_result = SuiteResult(suite_name=suite.name)
        logger.info(f"{'=' * 60}")
        logger.info(f"开始执行套件: {suite.name}")
        logger.info(f"用例数: {len(suite.cases)}")
        logger.info(f"{'=' * 60}")

        # 构建套件级变量
        suite_variables = self._build_suite_variables(suite)

        # 执行套件级 setup
        setup_extracted: dict[str, Any] = {}
        if suite.setup:
            try:
                setup_extracted = self._fixture_loader.run_setup(suite.setup, suite_variables)
                suite_variables.update(setup_extracted)
                logger.info(f"套件 setup 完成，提取变量: {list(setup_extracted.keys())}")
            except Exception as e:
                suite_result.setup_error = str(e)
                logger.error(f"套件 setup 失败: {e}")
                return suite_result

        # 执行每个用例
        for i, case in enumerate(suite.cases):
            logger.info(f"\n{'─' * 40}")
            logger.info(f"[{i + 1}/{len(suite.cases)}] {case.name}")

            case_result = self.run_case(case, suite_variables)
            suite_result.case_results.append(case_result)

            # 将提取的变量传递给后续用例
            if case_result.extracted_vars:
                suite_variables.update(case_result.extracted_vars)
                self._context.get_variables().update(case_result.extracted_vars)

            # Allure 报告
            self._allure.set_case_labels(case.tags, case.priority)

        # 执行套件级 teardown
        if suite.teardown:
            try:
                self._fixture_loader.run_teardown(suite.teardown, suite_variables)
                logger.info("套件 teardown 完成")
            except Exception as e:
                suite_result.teardown_error = str(e)
                logger.warning(f"套件 teardown 失败: {e}")

        # 输出套件结果摘要
        logger.info(f"\n{'=' * 60}")
        logger.info(
            f"套件完成: {suite.name} | "
            f"总计 {suite_result.total} | "
            f"通过 {suite_result.passed_count} | "
            f"失败 {suite_result.failed_count}"
        )
        logger.info(f"{'=' * 60}")

        return suite_result

    def run_case(self, case: TestCase, suite_variables: dict[str, Any]) -> CaseResult:
        """执行单个测试用例

        策略路由：遍历 self._executors，找到首个 supports(case) 为 True 的
        executor 并调用其 execute 方法。找不到时抛出 NoExecutorFoundError。
        """
        start_time = time.time()

        # 检查是否跳过
        if case.skip:
            logger.info(f"跳过用例: {case.name}")
            return CaseResult(
                case_name=case.name,
                passed=True,
                error="SKIPPED",
            )

        # 构建用例级变量
        variables = {**suite_variables, **case.variables}

        # 初始化上下文
        self._context.init()
        self._context.get_variables().update(variables)

        case_result = CaseResult(case_name=case.name, passed=True)

        try:
            # 执行用例级 setup
            if case.setup:
                setup_vars = self._fixture_loader.run_setup(case.setup, variables)
                variables.update(setup_vars)
                self._context.get_variables().update(setup_vars)

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
                    db_result = self._db_asserter.assert_query(db_assert, variables)
                    if not db_result.passed:
                        case_result.passed = False
                        if case_result.error:
                            case_result.error += f"; DB断言失败: {db_result}"
                        else:
                            case_result.error = f"DB断言失败: {db_result}"

            # 执行用例级 teardown
            if case.teardown:
                self._fixture_loader.run_teardown(case.teardown, variables)

        except NoExecutorFoundError:
            raise  # 框架配置错误，直接向上传播，不做捕获
        except Exception as e:
            case_result.passed = False
            case_result.error = str(e)
            logger.error(f"用例执行异常: {case.name} - {e}")

        case_result.elapsed_ms = (time.time() - start_time) * 1000
        case_result.extracted_vars = self._context.get_variables()

        status = "✅ PASS" if case_result.passed else "❌ FAIL"
        logger.info(f"{status} {case.name} ({case_result.elapsed_ms:.0f}ms)")

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
