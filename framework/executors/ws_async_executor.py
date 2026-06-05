"""AsyncWsStepExecutor — 原生 asyncio WebSocket 协议执行器

完全使用 asyncio 和 websockets 库实现 WebSocket 连接、发送、接收、关闭。
不依赖 nest_asyncio，可在 Celery Worker 等纯 asyncio 环境下安全运行。

设计：
- execute(): 同步入口，通过 asyncio.run() 桥接到异步逻辑
- aexecute(): 原生异步入口，供 TestRunner._ado_run_case() 直接 await
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from framework.context import TestContext
from framework.executors.base import StepExecutor
from framework.models import CaseResult, TestCase, WSConfig, WSResult
from framework.utils.logger import Logger
from framework.utils.template import TemplateEngine

logger = Logger.get("executor.ws_async")

# 延迟导入 websockets（可选依赖）
_has_websockets = False
_websockets_version: tuple[int, ...] = (0,)
try:
    import websockets

    _has_websockets = True
    _websockets_version = tuple(
        int(x) for x in websockets.__version__.split(".")[:2]
    )
except ImportError:
    pass


def _ws_connect_kwargs(url: str, headers: dict[str, str], timeout: int) -> dict:
    """构建 websockets.connect() 的关键字参数

    兼容 websockets < 14（extra_headers）和 >= 14（additional_headers）。
    """
    kwargs: dict = {
        "open_timeout": timeout,
        "close_timeout": 5,
    }
    if _websockets_version >= (14,):
        kwargs["additional_headers"] = headers
    else:
        kwargs["extra_headers"] = headers
    return kwargs


class AsyncWsStepExecutor(StepExecutor):
    """原生 asyncio WebSocket 协议执行器

    与 WsStepExecutor (deprecated) 的区别：
    - 完全基于 asyncio，不依赖 nest_asyncio
    - execute() 使用 asyncio.run() 安全创建新事件循环
    - aexecute() 提供原生 async 入口，供 Runner 的异步路径直接调用

    Usage:
        # 同步路径（测试代码 / pytest）
        executor = AsyncWsStepExecutor(template_engine)
        result = executor.execute(case, context, variables)

        # 异步路径（asyncio 环境 / Celery Worker）
        result = await executor.aexecute(case, context, variables)
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
        """同步入口：通过 asyncio.run() 执行异步 WebSocket 逻辑

        每次调用创建独立的事件循环，避免与外部事件循环冲突。
        适用于 pytest 同步测试、CLI 等非 asyncio 上下文。
        """
        return asyncio.run(self.aexecute(case, context, variables))

    async def aexecute(
        self,
        case: TestCase,
        context: TestContext,
        variables: dict[str, Any],
    ) -> CaseResult:
        """原生异步入口：直接执行 WebSocket 交互流程

        在已有事件循环中直接 await，零线程开销。
        适用于 Celery Worker、FastAPI、asyncio 应用等场景。

        Args:
            case: 当前测试用例。
            context: 测试上下文。
            variables: 合并后的用例变量。

        Returns:
            CaseResult: 包含 passed / error 的执行结果。
        """
        if not _has_websockets:
            raise ImportError("websockets 未安装，请运行: pip install websockets")

        ws_config = case.ws_config
        assert ws_config is not None

        case_result = CaseResult(case_name=case.name, passed=True)

        # 模板渲染 WS 配置
        rendered_headers = self._template.render_dict(ws_config.headers, variables)
        rendered_url = self._template.render(ws_config.url, variables)

        rendered_ws_config = WSConfig(
            url=rendered_url,
            headers=rendered_headers,
            timeout=ws_config.timeout,
            messages=ws_config.messages,
            close_after=ws_config.close_after,
        )

        ws_result = await self._run_ws_flow(rendered_ws_config, variables)

        if not ws_result.success:
            case_result.passed = False
            case_result.error = "; ".join(ws_result.errors)

        return case_result

    # ── 核心 WebSocket 流程 ────────────────────────────

    async def _run_ws_flow(
        self,
        config: WSConfig,
        variables: dict[str, Any],
    ) -> WSResult:
        """执行完整的 WebSocket 交互流程（纯 asyncio）"""
        received_messages: list[str | bytes] = []
        errors: list[str] = []
        total_sent = 0

        logger.info(f"连接 WebSocket: {config.url}")

        connect_kwargs = _ws_connect_kwargs(config.url, config.headers, config.timeout)

        try:
            async with websockets.connect(
                config.url,
                **connect_kwargs,
            ) as ws:
                for msg_config in config.messages:
                    msg_type = msg_config.type

                    if msg_type == "send":
                        data = self._template.render(str(msg_config.data), variables)
                        logger.debug(f"发送: {data[:200]}")
                        await ws.send(data)
                        total_sent += 1

                    elif msg_type == "receive":
                        timeout = msg_config.timeout or config.timeout
                        try:
                            data = await asyncio.wait_for(ws.recv(), timeout=timeout)
                            logger.debug(f"接收: {str(data)[:200]}")
                            received_messages.append(data)

                            # 消息断言
                            if msg_config.expect:
                                parsed = (
                                    json.loads(data) if isinstance(data, str) else data
                                )
                                self._assert_message(parsed, msg_config.expect)

                        except asyncio.TimeoutError:
                            errors.append(f"接收消息超时 ({timeout}s)")
                            break

                    elif msg_type == "close":
                        await ws.close()
                        break

        except asyncio.TimeoutError:
            errors.append(f"WebSocket 连接超时 ({config.timeout}s)")
            logger.error(f"WebSocket 连接超时: {config.url}")
        except Exception as e:
            errors.append(f"WebSocket 错误: {e}")
            logger.error(f"WebSocket 错误: {e}")

        return WSResult(
            received_messages=received_messages,
            errors=errors,
            total_sent=total_sent,
            total_received=len(received_messages),
        )

    # ── 消息断言 ───────────────────────────────────────

    def _assert_message(self, data: Any, expect: dict[str, Any]) -> None:
        """对接收到的消息做 JSONPath 断言"""
        from framework.utils.jsonpath_util import extract_value

        jsonpath_expect = expect.get("jsonpath", {})
        for path, expected in jsonpath_expect.items():
            actual = extract_value(data, path)
            if actual != expected:
                logger.warning(
                    f"WS 消息断言失败: {path} 期望={expected} 实际={actual}"
                )
