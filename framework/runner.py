"""测试执行引擎 — 编排用例执行、变量传递、断言、提取

采用策略模式（Strategy Pattern）将协议执行逻辑解耦到独立的 StepExecutor 中。
新增协议（如 gRPC）只需新建一个 executor 文件并注册，无需修改 runner.py。

插件系统集成：
- 通过 PluginManager 在关键生命周期点分发事件
- 插件可按 priority 排序，高优先级插件（数值小）先执行
- 插件间通过 PluginContext 共享数据

通知系统集成：
- 在 run_suite() 完成后，根据通知规则评估并发送多渠道通知
- 通过 NotificationService 编排渠道分发

超时控制：
- 同步路径 (run_case): 在后台线程中执行用例，主线程 join 等待，超时返回 TIMEOUT
- 异步路径 (arun_case): 使用 asyncio.wait_for() 包裹协程执行
- 单个用例可覆盖全局 case_timeout（TestCase.timeout）
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import httpx

from framework.assertion import AssertionEngine
from framework.context import TestContext
from framework.db import DBAsserter, DBConnectionManager, DBExecutor
from framework.exceptions import AutoTestException, CaseTimeoutError, NoExecutorFoundError
from framework.executors.base import StepExecutor
from framework.executors.http_executor import HttpStepExecutor
from framework.executors.ws_async_executor import AsyncWsStepExecutor
from framework.extractor import Extractor
from framework.fixtures_loader import FixtureLoader
from framework.models import CaseResult, CaseStatus, EnvConfig, ProjectConfig, SuiteResult, TestCase, TestSuite
from framework.notifications.service import NotificationService, ServiceConfig
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
        async_http_client: Any = None,  # AsyncHttpClient
        notification_service: NotificationService | None = None,
    ) -> None:
        self._config = config
        self._env = env
        self._http_client = http_client
        self._async_http_client = async_http_client
        self._context = context or TestContext()
        self._template = TemplateEngine()
        self._assertion_engine = AssertionEngine()
        self._extractor = Extractor()
        self._report_adapter = report_adapter or NoopReportAdapter()

        # ── 通知服务 ──
        if notification_service is not None:
            self._notification_service = notification_service
        elif config.notifications.get("enabled", False):
            self._notification_service = NotificationService.from_config(
                config.notifications,
                env_name=env.name,
            )
        else:
            self._notification_service = None

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

        # Fixture 加载器（注入 Mock 存储）
        from framework.mock.rule_store import get_mock_store
        self._fixture_loader = FixtureLoader(
            http_client=http_client,
            db_executor=self._db_executor,
            template_engine=self._template,
            extractor=self._extractor,
            fixtures_config=config.fixtures,
            mock_store=get_mock_store(),
        )

        # StepExecutor 策略链（默认：gRPC → WS(Async) → HTTP）
        if executors is None:
            executors = [
                self._try_create_grpc_executor(),
                AsyncWsStepExecutor(self._template),
                HttpStepExecutor(
                    http_client=http_client,
                    template_engine=self._template,
                    assertion_engine=self._assertion_engine,
                    extractor=self._extractor,
                    report_adapter=self._report_adapter,
                    env=env,
                    plugin_manager=self._plugin_manager,
                    async_http_client=self._async_http_client,
                ),
            ]
            # 过滤掉 None（未安装 grpc 时 _try_create_grpc_executor 返回 None）
            executors = [e for e in executors if e is not None]
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
            except (AutoTestException, httpx.HTTPError, asyncio.TimeoutError) as e:
                self._plugin_manager.dispatch("error", error=e, case=suite)
                suite_result.setup_error = str(e)
                logger.error("suite_setup_failed", error=str(e), suite_name=suite.name)
                return suite_result
            except Exception as e:
                logger.error(
                    "suite_setup_unexpected_error",
                    error=str(e),
                    suite_name=suite.name,
                    exc_info=True,
                )
                self._plugin_manager.dispatch("error", error=e, case=suite)
                suite_result.setup_error = str(e)
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
            except (AutoTestException, httpx.HTTPError, asyncio.TimeoutError) as e:
                self._plugin_manager.dispatch("error", error=e, case=suite)
                suite_result.teardown_error = str(e)
                logger.warning("suite_teardown_failed", error=str(e), suite_name=suite.name)
            except Exception as e:
                logger.error(
                    "suite_teardown_unexpected_error",
                    error=str(e),
                    suite_name=suite.name,
                    exc_info=True,
                )
                self._plugin_manager.dispatch("error", error=e, case=suite)
                suite_result.teardown_error = str(e)
                logger.warning("suite_teardown_failed", error=str(e), suite_name=suite.name)

        # ── 插件钩子：on_suite_end ──
        self._plugin_manager.dispatch("suite_end", suite=suite, result=suite_result)

        # ── 通知分发 ──
        self._dispatch_notifications(suite_result)

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
        """执行单个测试用例（同步路径，带超时控制）

        策略路由：遍历 self._executors，找到首个 supports(case) 为 True 的
        executor 并调用其 execute 方法。找不到时抛出 NoExecutorFoundError。

        超时控制：在后台线程执行用例，主线程带超时 join。超时阈值取
        case.timeout 或 config.case_timeout。
        """
        timeout = case.timeout if case.timeout is not None else self._config.case_timeout

        if timeout <= 0:
            return self._do_run_case(case, suite_variables)

        # ── 在后台线程执行用例，主线程带超时等待 ──
        result_holder: dict[str, CaseResult | None] = {"value": None}
        error_holder: dict[str, Exception | None] = {"exception": None}

        def _execute() -> None:
            try:
                result_holder["value"] = self._do_run_case(case, suite_variables)
            except (AutoTestException, httpx.HTTPError, asyncio.TimeoutError) as e:
                error_holder["exception"] = e
            except Exception as e:
                logger.error(
                    "unexpected_case_execution_error",
                    case_name=case.name,
                    error=str(e),
                    exc_info=True,
                )
                error_holder["exception"] = e

        thread = threading.Thread(
            target=_execute, daemon=True, name=f"case-{case.name}"
        )
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            # 超时：后台线程仍在执行，标记为 TIMEOUT
            self._cleanup_on_timeout(case)
            elapsed_ms = timeout * 1000.0
            logger.warning(
                "case_timeout",
                case_name=case.name,
                timeout=timeout,
                current_step=getattr(self, "_current_step", "unknown"),
            )
            return CaseResult(
                case_name=case.name,
                passed=False,
                status=CaseStatus.TIMEOUT,
                error=f"用例执行超时: 超过 {timeout}s",
                elapsed_ms=elapsed_ms,
            )

        if error_holder["exception"] is not None:
            raise error_holder["exception"]

        return result_holder["value"]  # type: ignore[return-value]

    def _do_run_case(self, case: TestCase, suite_variables: dict[str, Any]) -> CaseResult:
        """执行单个测试用例的核心逻辑（供超时控制复用）

        将原始 run_case() 的完整流程提取为独立方法，同时被同步和异步路径调用。
        """
        start_time = time.time()

        # 记录当前步骤（供超时信息使用）
        self._current_step = "start"

        # ── 绑定用例级 trace_id ──
        set_trace_id(case.name)

        # ── 插件钩子：on_case_start ──
        self._plugin_manager.dispatch("case_start", case=case)

        # 检查是否跳过
        if case.skip:
            logger.info("case_skipped", case_name=case.name, reason="skip flag set")
            result = CaseResult(
                case_name=case.name, passed=True, status=CaseStatus.SKIP, error="SKIPPED"
            )
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

        case_result = CaseResult(case_name=case.name, passed=True, status=CaseStatus.PASS)

        try:
            # 执行用例级 setup
            if case.setup:
                self._current_step = "setup"
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
            self._current_step = "execute"
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
                self._current_step = "db_asserts"
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
                        case_result.status = CaseStatus.FAIL
                        if case_result.error:
                            case_result.error += f"; DB断言失败: {db_result}"
                        else:
                            case_result.error = f"DB断言失败: {db_result}"

            # 执行用例级 teardown
            if case.teardown:
                self._current_step = "teardown"
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
        except (AutoTestException, httpx.HTTPError, asyncio.TimeoutError) as e:
            case_result.passed = False
            case_result.status = CaseStatus.FAIL
            case_result.error = str(e)
            # ── 插件钩子：on_error ──
            self._plugin_manager.dispatch("error", error=e, case=case)
            logger.error("case_execution_error", case_name=case.name, error=str(e), exc_info=True)
        except Exception as e:
            logger.error(
                "case_unexpected_error",
                case_name=case.name,
                error=str(e),
                exc_info=True,
            )
            case_result.passed = False
            case_result.status = CaseStatus.FAIL
            case_result.error = str(e)
            self._plugin_manager.dispatch("error", error=e, case=case)

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

    async def arun_case(
        self, case: TestCase, suite_variables: dict[str, Any]
    ) -> CaseResult:
        """执行单个测试用例（异步路径，使用 asyncio.wait_for 超时控制）

        在 asyncio 事件循环中执行，适用于 WebSocket 原生异步等场景。
        """
        timeout = case.timeout if case.timeout is not None else self._config.case_timeout

        try:
            if timeout > 0:
                # asyncio.wait_for 在超时时取消内部协程并抛出 TimeoutError
                result = await asyncio.wait_for(
                    self._ado_run_case(case, suite_variables),
                    timeout=timeout,
                )
            else:
                result = await self._ado_run_case(case, suite_variables)
        except asyncio.TimeoutError:
            self._cleanup_on_timeout(case)
            logger.warning(
                "case_timeout_async",
                case_name=case.name,
                timeout=timeout,
            )
            return CaseResult(
                case_name=case.name,
                passed=False,
                status=CaseStatus.TIMEOUT,
                error=f"用例执行超时 (asyncio): 超过 {timeout}s",
                elapsed_ms=timeout * 1000.0,
            )

        return result

    async def _ado_run_case(
        self, case: TestCase, suite_variables: dict[str, Any]
    ) -> CaseResult:
        """异步核心执行逻辑

        路由策略：
        - WebSocket 用例：AsyncWsStepExecutor.aexecute() 原生异步执行
        - HTTP 用例（有 async_http_client 时）：HttpStepExecutor.aexecute() 原生异步执行
        - 其他用例（无 async executor）：线程池桥接同步 _do_run_case
        """
        # WS 用例 / 有 async_http_client 的 HTTP 用例 — 原生异步路径
        use_async = (
            case.ws_config is not None
            or self._async_http_client is not None
        )
        if use_async:
            return await self._ado_run_case_async(case, suite_variables)

        # 纯同步 fallback — 线程池桥接
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._do_run_case, case, suite_variables
        )

    async def _ado_run_case_async(
        self, case: TestCase, suite_variables: dict[str, Any]
    ) -> CaseResult:
        """用例的原生异步执行路径（WebSocket / HTTP / 其他支持 aexecute 的协议）

        与 _do_run_case 等价，但 executor 步骤通过 await aexecute() 原生执行，
        不经过线程池桥接。setup / teardown / DB 断言等同步步骤在 async 上下文中
        直接调用（均为非阻塞操作，不影响事件循环）。

        在 Celery Worker / FastAPI 等纯 asyncio 环境中，此路径不产生事件循环冲突。
        """
        start_time = time.time()

        self._current_step = "start"
        set_trace_id(case.name)

        self._plugin_manager.dispatch("case_start", case=case)

        if case.skip:
            logger.info("case_skipped", case_name=case.name, reason="skip flag set")
            result = CaseResult(
                case_name=case.name, passed=True, status=CaseStatus.SKIP, error="SKIPPED"
            )
            self._plugin_manager.dispatch("case_end", case=case, result=result)
            clear_trace_id()
            return result

        variables = {**suite_variables, **case.variables}
        self._context.init()
        self._context.set_case_vars(variables)
        self._context.start_step()
        self._context.get_variables().update(variables)

        case_result = CaseResult(case_name=case.name, passed=True, status=CaseStatus.PASS)

        try:
            # 用例级 setup（同步，在 async 上下文中安全）
            if case.setup:
                self._current_step = "setup"
                self._plugin_manager.dispatch(
                    "setup", phase="before", case=case, variables=variables
                )
                setup_vars = self._fixture_loader.run_setup(case.setup, variables)
                variables.update(setup_vars)
                self._context.get_variables().update(setup_vars)
                self._plugin_manager.dispatch(
                    "setup", phase="after", case=case, variables=variables
                )

            # ═══ 原生异步执行（WS / HTTP）════
            self._current_step = "execute"
            matched = False
            for executor in self._executors:
                if executor.supports(case):
                    # 支持 aexecute() 的执行器直接 await（AsyncWsStepExecutor / HttpStepExecutor）
                    if hasattr(executor, "aexecute"):
                        case_result = await executor.aexecute(
                            case, self._context, variables
                        )
                    else:
                        # 降级：非 async executor 走同步路径（线程池桥接）
                        loop = asyncio.get_running_loop()
                        case_result = await loop.run_in_executor(
                            None, executor.execute, case, self._context, variables
                        )
                    matched = True
                    break

            if not matched:
                raise NoExecutorFoundError(case.name)

            # DB 断言（同步）
            if case.db_asserts and self._db_asserter:
                self._current_step = "db_asserts"
                for db_assert in case.db_asserts:
                    self._plugin_manager.dispatch(
                        "db_query",
                        phase="before",
                        case=case,
                        sql=db_assert.sql,
                    )
                    db_result = self._db_asserter.assert_query(db_assert, variables)
                    self._plugin_manager.dispatch(
                        "db_query",
                        phase="after",
                        case=case,
                        sql=db_assert.sql,
                        result=db_result,
                    )
                    if not db_result.passed:
                        case_result.passed = False
                        case_result.status = CaseStatus.FAIL
                        if case_result.error:
                            case_result.error += f"; DB断言失败: {db_result}"
                        else:
                            case_result.error = f"DB断言失败: {db_result}"

            # 用例级 teardown（同步）
            if case.teardown:
                self._current_step = "teardown"
                self._plugin_manager.dispatch(
                    "teardown", phase="before", case=case, variables=variables
                )
                self._fixture_loader.run_teardown(case.teardown, variables)
                self._plugin_manager.dispatch(
                    "teardown", phase="after", case=case, variables=variables
                )

        except NoExecutorFoundError:
            self._plugin_manager.dispatch("case_end", case=case, result=case_result)
            raise
        except (AutoTestException, httpx.HTTPError, asyncio.TimeoutError) as e:
            case_result.passed = False
            case_result.status = CaseStatus.FAIL
            case_result.error = str(e)
            self._plugin_manager.dispatch("error", error=e, case=case)
            logger.error(
                "case_execution_error", case_name=case.name, error=str(e), exc_info=True
            )
        except Exception as e:
            logger.error(
                "case_unexpected_error",
                case_name=case.name,
                error=str(e),
                exc_info=True,
            )
            case_result.passed = False
            case_result.status = CaseStatus.FAIL
            case_result.error = str(e)
            self._plugin_manager.dispatch("error", error=e, case=case)

        case_result.elapsed_ms = (time.time() - start_time) * 1000

        self._context.end_step(promote=True)
        case_result.extracted_vars = self._context.get_all_variables()

        self._plugin_manager.dispatch("case_end", case=case, result=case_result)

        status = "PASS" if case_result.passed else "FAIL"
        logger.info(
            "case_completed",
            case_name=case.name,
            status=status,
            elapsed_ms=round(case_result.elapsed_ms),
            error=case_result.error if not case_result.passed else None,
        )

        clear_trace_id()

        return case_result

    def _cleanup_on_timeout(self, case: TestCase) -> None:
        """超时后的资源清理

        - 分发超时事件通知插件
        - 清除 trace_id 避免日志串扰
        - 不清除 http_client 连接（共享资源，不应在单用例超时时关闭）

        Note:
            后台线程可能仍在执行，但由于设为 daemon，进程退出时会终止。
            不与后台线程争用共享状态（context、client），只做通知和标记。
        """
        try:
            # 通知插件超时事件
            self._plugin_manager.dispatch(
                "error",
                error=CaseTimeoutError(
                    case_name=case.name,
                    timeout_seconds=case.timeout or self._config.case_timeout,
                    current_step=getattr(self, "_current_step", "unknown"),
                ),
                case=case,
            )
        except Exception:
            logger.warning("cleanup_stage_exception", exc_info=True)
        finally:
            clear_trace_id()

    def _try_create_grpc_executor(self) -> Any:
        """尝试创建 GrpcStepExecutor（懒加载，兼容未安装 grpc 的环境）

        如果 grpcio / grpcio-tools 未安装，返回 None 并记录 debug 日志，
        不影响其他协议的执行。

        Returns:
            GrpcStepExecutor 实例或 None。
        """
        try:
            import grpc  # noqa: F401
            from framework.executors.grpc_executor import GrpcStepExecutor

            return GrpcStepExecutor(
                template_engine=self._template,
                assertion_engine=self._assertion_engine,
                report_adapter=self._report_adapter,
                plugin_manager=self._plugin_manager,
            )
        except ImportError:
            logger.debug("grpc_not_installed", hint="pip install auto-test-framework[grpc]")
            return None

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

    def _dispatch_notifications(self, suite_result: SuiteResult) -> None:
        """调度异步通知（从同步上下文中安全调用）

        仅在通知服务已配置且启用时执行。
        使用 asyncio.run() 桥接异步通知发送到同步 run_suite() 线程。

        Args:
            suite_result: 套件执行结果。
        """
        if self._notification_service is None:
            return

        try:
            asyncio.run(self._notification_service.notify(suite_result))
        except (AutoTestException, httpx.HTTPError, asyncio.TimeoutError) as e:
            logger.warning("notification_dispatch_failed", error=str(e))
        except Exception as e:
            logger.error("notification_dispatch_unexpected_error", error=str(e), exc_info=True)
