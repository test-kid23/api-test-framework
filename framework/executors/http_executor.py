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
from framework.report import AllureAdapter
from framework.utils.logger import Logger
from framework.utils.template import TemplateEngine

logger = Logger.get("executor.http")


class HttpStepExecutor(StepExecutor):
    """HTTP 协议执行器

    负责：
    1. 模板渲染请求参数
    2. 发送 HTTP 请求
    3. 执行响应断言
    4. 提取变量
    """

    def __init__(
        self,
        http_client: Any,
        template_engine: TemplateEngine,
        assertion_engine: AssertionEngine,
        extractor: Extractor,
        allure: AllureAdapter,
        env: EnvConfig,
    ) -> None:
        self._http_client = http_client
        self._template = template_engine
        self._assertion_engine = assertion_engine
        self._extractor = extractor
        self._allure = allure
        self._env = env

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

        # Allure 附加请求信息
        self._allure.attach_request(rendered_req, full_url)

        # 发送请求
        response = self._http_client.request(rendered_req, variables)
        case_result.response = response
        context.set_response(response)

        # Allure 附加响应信息
        self._allure.attach_response(response)

        # 执行断言
        if case.assertions:
            assertion_report = self._assertion_engine.assert_response(
                response, case.assertions, variables
            )
            case_result.assertion_report = assertion_report
            self._allure.attach_assertions(assertion_report)

            if not assertion_report.passed:
                case_result.passed = False
                case_result.error = assertion_report.summary()

        # 提取变量
        if case.extracts:
            extracted = self._extractor.extract(response, case.extracts, variables)
            case_result.extracted_vars.update(extracted)
            context.get_variables().update(extracted)
            logger.info(f"提取变量: {list(extracted.keys())}")

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
