"""WsStepExecutor — WebSocket 协议执行器

从 runner.py 的 _run_ws_case 迁移而来，独立封装 WebSocket 用例的完整执行逻辑。
"""

from __future__ import annotations

from typing import Any

from framework.context import TestContext
from framework.executors.base import StepExecutor
from framework.models import CaseResult, TestCase, WSConfig, WSResult
from framework.utils.logger import Logger
from framework.utils.template import TemplateEngine

logger = Logger.get("executor.ws")


class WsStepExecutor(StepExecutor):
    """WebSocket 协议执行器

    负责：
    1. 模板渲染 WS 配置（headers 等）
    2. 建立 WebSocket 连接
    3. 按消息序列执行 send/receive/close
    4. 收集结果并设置错误信息
    """

    def __init__(self, template_engine: TemplateEngine) -> None:
        self._template = template_engine

    # ── StepExecutor 接口 ──────────────────────────────

    def supports(self, case: TestCase) -> bool:
        return case.ws_config is not None

    def execute(
        self,
        case: TestCase,
        context: TestContext,
        variables: dict[str, Any],
    ) -> CaseResult:
        from framework.ws import WSSyncClient

        ws_config = case.ws_config
        assert ws_config is not None

        case_result = CaseResult(case_name=case.name, passed=True)

        # 模板替换 WS 配置
        rendered_headers = self._template.render_dict(ws_config.headers, variables)

        rendered_ws_config = WSConfig(
            url=ws_config.url,
            headers=rendered_headers,
            timeout=ws_config.timeout,
            messages=ws_config.messages,
            close_after=ws_config.close_after,
        )

        ws_client = WSSyncClient(rendered_ws_config, self._template)
        ws_result: WSResult = ws_client.execute(variables)

        if not ws_result.success:
            case_result.passed = False
            case_result.error = "; ".join(ws_result.errors)

        return case_result
