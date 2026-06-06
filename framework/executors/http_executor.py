"""HttpStepExecutor — HTTP 协议执行器

从 runner.py 的 _run_http_case 迁移而来，独立封装 HTTP 用例的完整执行逻辑。
"""

from __future__ import annotations

from typing import Any

from framework.assertion import AssertionEngine
from framework.context import TestContext
from framework.executors.base import StepExecutor
from framework.extractor import Extractor
from framework.models import CaseResult, EnvConfig, HttpRequest, TestCase
from framework.report.base import ReportAdapter
from framework.utils.logger import Logger
from framework.utils.template import TemplateEngine

logger = Logger.get("executor.http")


class HttpStepExecutor(StepExecutor):
    """HTTP 协议执行器

    负责：
    1. 模板渲染请求参数
    2. 通过插件链处理请求（on_request）
    3. 发送 HTTP 请求
    4. 通过插件链处理响应（on_response）
    5. 执行响应断言 → 插件钩子 on_assertion
    6. 提取变量 → 插件钩子 on_extract

    支持同步和异步两种路径：
    - execute():  同步入口，使用同步 HttpClient
    - aexecute(): 异步入口，使用 AsyncHttpClient（在 asyncio 环境中直接 await）
    """

    def __init__(
        self,
        http_client: Any,
        template_engine: TemplateEngine,
        assertion_engine: AssertionEngine,
        extractor: Extractor,
        report_adapter: ReportAdapter,
        env: EnvConfig,
        plugin_manager: Any = None,  # PluginManager
        async_http_client: Any = None,  # AsyncHttpClient
    ) -> None:
        self._http_client = http_client
        self._async_http_client = async_http_client
        self._template = template_engine
        self._assertion_engine = assertion_engine
        self._extractor = extractor
        self._report_adapter = report_adapter
        self._env = env
        self._plugin_manager = plugin_manager

    # ── StepExecutor 接口 ──────────────────────────────

    def supports(self, case: TestCase) -> bool:
        return case.request is not None

    def execute(
        self,
        case: TestCase,
        context: TestContext,
        variables: dict[str, Any],
    ) -> CaseResult:
        req = case.request
        assert req is not None

        case_result = CaseResult(case_name=case.name, passed=True)

        # 模板替换请求参数
        rendered_req = self._render_request(req, variables)

        # 构建完整 URL
        base_url = self._template.render(
            case.variables.get("base_url", self._env.base_url), variables
        )
        full_url = f"{base_url}{rendered_req.path}"

        case_result.request = rendered_req
        case_result.url = full_url
        context.set_request(rendered_req)
        context.set_url(full_url)

        # 报告附加请求信息
        self._report_adapter.attach_request(rendered_req, full_url)

        # ── 插件链：on_request ──
        if self._plugin_manager:
            rendered_req = self._plugin_manager.dispatch_chain(
                "request", chain_value=rendered_req
            )

        # 发送请求
        response = self._http_client.request(rendered_req, variables)
        case_result.response = response
        context.set_response(response)

        # ── 插件链：on_response ──
        if self._plugin_manager:
            response = self._plugin_manager.dispatch_chain(
                "response", chain_value=response
            )
            case_result.response = response

        # 报告附加响应信息
        self._report_adapter.attach_response(response)

        # 执行断言
        if case.assertions:
            assertion_report = self._assertion_engine.assert_response(
                response, case.assertions, variables
            )
            case_result.assertion_report = assertion_report
            self._report_adapter.attach_assertions(assertion_report)

            # ── 插件钩子：on_assertion ──
            if self._plugin_manager:
                self._plugin_manager.dispatch(
                    "assertion", case=case, report=assertion_report
                )

            if not assertion_report.passed:
                case_result.passed = False
                case_result.error = assertion_report.summary()

        # 提取变量
        if case.extracts:
            extracted = self._extractor.extract(response, case.extracts, variables)
            case_result.extracted_vars.update(extracted)
            context.get_variables().update(extracted)

            # ── 插件钩子：on_extract ──
            if self._plugin_manager:
                self._plugin_manager.dispatch(
                    "extract", case=case, extracted=extracted
                )

            logger.info("variables_extracted", var_names=list(extracted.keys()))

        return case_result

    async def aexecute(
        self,
        case: TestCase,
        context: TestContext,
        variables: dict[str, Any],
    ) -> CaseResult:
        """异步入口：在 asyncio 环境中直接执行 HTTP 用例

        与 execute() 逻辑一致，但通过 AsyncHttpClient 异步发送请求，
        不阻塞事件循环。适用于 FastAPI / Celery Worker 等纯 asyncio 环境。

        Args:
            case: 当前测试用例
            context: 测试上下文
            variables: 合并后的用例变量

        Returns:
            CaseResult: 执行结果

        Raises:
            RuntimeError: 当 async_http_client 未注入时抛出
        """
        if self._async_http_client is None:
            raise RuntimeError(
                "HttpStepExecutor.aexecute() 需要注入 async_http_client，"
                "请通过 TestRunner(async_http_client=...) 传入"
            )

        req = case.request
        assert req is not None

        case_result = CaseResult(case_name=case.name, passed=True)

        # 模板替换请求参数
        rendered_req = self._render_request(req, variables)

        # 构建完整 URL
        base_url = self._template.render(
            case.variables.get("base_url", self._env.base_url), variables
        )
        full_url = f"{base_url}{rendered_req.path}"

        case_result.request = rendered_req
        case_result.url = full_url
        context.set_request(rendered_req)
        context.set_url(full_url)

        self._report_adapter.attach_request(rendered_req, full_url)

        # 插件链：on_request
        if self._plugin_manager:
            rendered_req = self._plugin_manager.dispatch_chain(
                "request", chain_value=rendered_req
            )

        # 异步发送请求
        response = await self._async_http_client.request(rendered_req, variables)
        case_result.response = response
        context.set_response(response)

        # 插件链：on_response
        if self._plugin_manager:
            response = self._plugin_manager.dispatch_chain(
                "response", chain_value=response
            )
            case_result.response = response

        self._report_adapter.attach_response(response)

        # 执行断言
        if case.assertions:
            assertion_report = self._assertion_engine.assert_response(
                response, case.assertions, variables
            )
            case_result.assertion_report = assertion_report
            self._report_adapter.attach_assertions(assertion_report)

            if self._plugin_manager:
                self._plugin_manager.dispatch(
                    "assertion", case=case, report=assertion_report
                )

            if not assertion_report.passed:
                case_result.passed = False
                case_result.error = assertion_report.summary()

        # 提取变量
        if case.extracts:
            extracted = self._extractor.extract(response, case.extracts, variables)
            case_result.extracted_vars.update(extracted)
            context.get_variables().update(extracted)

            if self._plugin_manager:
                self._plugin_manager.dispatch(
                    "extract", case=case, extracted=extracted
                )

            logger.info("variables_extracted", var_names=list(extracted.keys()))

        return case_result

    # ── 内部方法 ───────────────────────────────────────

    def _render_request(self, req: HttpRequest, variables: dict[str, Any]) -> HttpRequest:
        """对请求做模板替换"""
        return HttpRequest(
            method=req.method,
            path=self._template.render(req.path, variables),
            headers=self._template.render_dict(req.headers, variables),
            params=self._template.render_dict(req.params, variables) if req.params else {},
            body=self._template.render_value(req.body, variables) if req.body is not None else None,
            body_type=req.body_type,
            timeout=req.timeout,
            verify_ssl=req.verify_ssl,
            files=req.files,
            auth=self._template.render_dict(req.auth, variables) if req.auth else None,
        )
