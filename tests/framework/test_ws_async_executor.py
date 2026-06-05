"""AsyncWsStepExecutor 测试

验证：
1. 原生异步执行器可连接回显 WebSocket 服务并正确收发消息
2. supports() 匹配逻辑正确
3. 连接超时、接收超时等异常场景
4. DeprecationWarning 在旧 WsStepExecutor 上正常触发
5. 在已有事件循环中 aexecute() 正常工作
6. execute() 同步入口通过 asyncio.run() 正常工作
"""

from __future__ import annotations

import asyncio
import warnings
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
import websockets

from framework.context import TestContext
from framework.executors.ws_async_executor import AsyncWsStepExecutor
from framework.models import TestCase, WSConfig, WSMessage
from framework.utils.template import TemplateEngine


# ══════════════════════════════════════════════════════════
# 本地 WebSocket 回显服务
# ══════════════════════════════════════════════════════════


class EchoServer:
    """本地 WebSocket 回显服务器

    用于测试 AsyncWsStepExecutor 的完整交互流程。
    收到消息后原样返回，支持文本和二进制消息。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 18765):
        self._host = host
        self._port = port
        self._server = None
        self._stop_event = asyncio.Event()
        self._received_count = 0

    @property
    def url(self) -> str:
        return f"ws://{self._host}:{self._port}"

    @property
    def received_count(self) -> int:
        return self._received_count

    async def _handler(self, ws):
        """处理每个 WebSocket 连接：回显收到的消息"""
        try:
            async for message in ws:
                self._received_count += 1
                await ws.send(message)
        except websockets.exceptions.ConnectionClosed:
            pass

    async def start(self):
        """启动回显服务器"""
        self._stop_event.clear()
        self._server = await websockets.serve(
            self._handler,
            self._host,
            self._port,
        )

    async def stop(self):
        """停止回显服务器"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None


class SlowEchoServer:
    """延迟回显服务器 — 用于测试接收超时"""

    def __init__(self, host: str = "127.0.0.1", port: int = 18766, delay: float = 5.0):
        self._host = host
        self._port = port
        self._delay = delay
        self._server = None

    @property
    def url(self) -> str:
        return f"ws://{self._host}:{self._port}"

    async def _handler(self, ws):
        try:
            async for message in ws:
                await asyncio.sleep(self._delay)
                await ws.send(message)
        except websockets.exceptions.ConnectionClosed:
            pass

    async def start(self):
        self._server = await websockets.serve(
            self._handler,
            self._host,
            self._port,
        )

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None


# ══════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════


@pytest.fixture
def template_engine() -> TemplateEngine:
    return TemplateEngine()


@pytest.fixture
def test_context() -> TestContext:
    return TestContext()


@pytest.fixture
def executor(template_engine) -> AsyncWsStepExecutor:
    return AsyncWsStepExecutor(template_engine)


@pytest_asyncio.fixture
async def echo_server():
    """启动回显服务器，测试结束后自动关闭"""
    server = EchoServer()
    await server.start()
    try:
        yield server
    finally:
        await server.stop()


# ══════════════════════════════════════════════════════════
# 辅助工厂
# ══════════════════════════════════════════════════════════


def make_ws_case(url: str, messages: list[WSMessage] | None = None, **kwargs) -> TestCase:
    """创建 WebSocket TestCase"""
    defaults: dict = {
        "name": "test_ws",
        "ws_config": WSConfig(
            url=url,
            messages=messages or [],
            timeout=5,
        ),
    }
    defaults.update(kwargs)
    return TestCase(**defaults)


def make_echo_messages(count: int = 3) -> list[WSMessage]:
    """生成回显测试消息序列：发送 → 接收 → 发送 → 接收 ..."""
    messages: list[WSMessage] = []
    for i in range(count):
        messages.append(WSMessage(type="send", data=f"hello_{i}"))
        messages.append(WSMessage(type="receive", timeout=5))
    return messages


# ══════════════════════════════════════════════════════════
# 1. supports() 路由匹配
# ══════════════════════════════════════════════════════════


class TestSupports:
    def test_supports_ws_case(self, executor):
        case = make_ws_case("ws://localhost/ws")
        assert executor.supports(case) is True

    def test_does_not_support_none_ws_config(self, executor):
        case = TestCase(name="no_ws")
        assert executor.supports(case) is False

    def test_supports_with_full_config(self, executor):
        case = make_ws_case(
            "ws://localhost/chat",
            messages=[WSMessage(type="send", data="hello")],
            timeout=10,
        )
        assert executor.supports(case) is True


# ══════════════════════════════════════════════════════════
# 2. 异步执行 — 回显测试
# ══════════════════════════════════════════════════════════


class TestAsyncEchoFlow:
    """使用本地回显服务器验证完整交互流程"""

    @pytest.mark.asyncio
    async def test_send_receive_echo(self, echo_server, executor, test_context):
        """发送 3 条消息，验证收到的回显内容"""
        case = make_ws_case(echo_server.url, messages=make_echo_messages(3))
        variables: dict = {}

        result = await executor.aexecute(case, test_context, variables)

        assert result.passed is True
        assert result.error is None
        assert echo_server.received_count == 3

    @pytest.mark.asyncio
    async def test_single_send_receive(self, echo_server, executor, test_context):
        """单条消息的回显"""
        messages = [
            WSMessage(type="send", data="ping"),
            WSMessage(type="receive", timeout=5),
        ]
        case = make_ws_case(echo_server.url, messages=messages)

        result = await executor.aexecute(case, test_context, {})

        assert result.passed is True
        assert echo_server.received_count == 1

    @pytest.mark.asyncio
    async def test_template_rendering_in_url(self, executor, test_context):
        """验证 URL 模板渲染"""
        server = EchoServer(port=18767)
        await server.start()
        try:
            case = make_ws_case(
                "ws://{{ host }}:{{ port }}",
                messages=make_echo_messages(1),
            )
            variables = {"host": "127.0.0.1", "port": "18767"}

            result = await executor.aexecute(case, test_context, variables)

            assert result.passed is True
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_template_rendering_in_message_data(self, echo_server, executor, test_context):
        """验证消息体模板渲染"""
        messages = [
            WSMessage(type="send", data="Hello, {{ name }}!"),
            WSMessage(type="receive", timeout=5),
        ]
        case = make_ws_case(echo_server.url, messages=messages)
        variables = {"name": "World"}

        result = await executor.aexecute(case, test_context, variables)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_close_message(self, echo_server, executor, test_context):
        """验证 close 类型的消息"""
        messages = [
            WSMessage(type="send", data="msg1"),
            WSMessage(type="receive", timeout=5),
            WSMessage(type="close"),
        ]
        case = make_ws_case(echo_server.url, messages=messages)

        result = await executor.aexecute(case, test_context, {})

        assert result.passed is True


# ══════════════════════════════════════════════════════════
# 3. 异常场景
# ══════════════════════════════════════════════════════════


class TestErrorScenarios:
    """验证异常场景的错误处理"""

    @pytest.mark.asyncio
    async def test_connection_timeout(self, executor, test_context):
        """连接不存在的服务器应超时报错"""
        # 使用不可路由的 IP（TEST-NET-1），确保连接超时
        case = make_ws_case(
            "ws://192.0.2.1:1",
            messages=[WSMessage(type="send", data="hello")],
            timeout=1,
        )

        result = await executor.aexecute(case, test_context, {})

        assert result.passed is False
        assert result.error is not None
        assert "超时" in result.error or "WebSocket 错误" in result.error

    @pytest.mark.asyncio
    async def test_receive_timeout(self, executor, test_context):
        """发送消息后，服务器不回复导致接收超时"""
        server = SlowEchoServer(delay=10.0, port=18768)
        await server.start()
        try:
            messages = [
                WSMessage(type="send", data="hello"),
                WSMessage(type="receive", timeout=1),  # 1s 超时，服务器 10s 延迟
            ]
            case = make_ws_case(server.url, messages=messages)

            result = await executor.aexecute(case, test_context, {})

            assert result.passed is False
            assert result.error is not None
            assert "超时" in result.error
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_invalid_url(self, executor, test_context):
        """无效 URL 应产生错误"""
        case = make_ws_case(
            "ws://invalid-host-that-does-not-exist.local:9999",
            messages=[WSMessage(type="send", data="hello")],
            timeout=2,
        )

        result = await executor.aexecute(case, test_context, {})

        assert result.passed is False
        assert result.error is not None


# ══════════════════════════════════════════════════════════
# 4. execute() 同步入口
# ══════════════════════════════════════════════════════════


class TestSyncExecute:
    """验证 execute() 通过 asyncio.run() 正常工作"""

    def test_sync_execute_with_echo_server(self, template_engine, test_context):
        """同步执行器在回显服务器上正常工作

        execute() 内部调用 asyncio.run()，测试代码本身运行在同步上下文中，
        避免嵌套 asyncio.run() 冲突。
        """
        import threading
        import queue

        server_ready = threading.Event()
        server_stop = threading.Event()
        port = 18769
        error_q: queue.Queue = queue.Queue()

        def _run_server():
            async def _serve():
                server = EchoServer(port=port)
                await server.start()
                server_ready.set()
                try:
                    # 等待停止信号
                    while not server_stop.is_set():
                        await asyncio.sleep(0.1)
                finally:
                    await server.stop()

            try:
                asyncio.run(_serve())
            except Exception as e:
                error_q.put(e)

        server_thread = threading.Thread(target=_run_server, daemon=True)
        server_thread.start()

        if not server_ready.wait(timeout=5):
            server_stop.set()
            server_thread.join(timeout=2)
            pytest.fail("服务器启动超时")

        if not error_q.empty():
            server_stop.set()
            server_thread.join(timeout=2)
            pytest.fail(f"服务器启动失败: {error_q.get()}")

        try:
            executor = AsyncWsStepExecutor(template_engine)
            case = make_ws_case(
                f"ws://127.0.0.1:{port}", messages=make_echo_messages(2)
            )

            # 同步上下文，execute() 内部 asyncio.run() 安全
            result = executor.execute(case, test_context, {})

            assert result.passed is True
        finally:
            server_stop.set()
            server_thread.join(timeout=5)

    def test_sync_execute_error_case(self, executor, test_context):
        """同步执行器正确处理错误"""
        case = make_ws_case(
            "ws://192.0.2.1:1",
            messages=[WSMessage(type="send", data="hello")],
            timeout=1,
        )

        result = executor.execute(case, test_context, {})

        assert result.passed is False
        assert result.error is not None


# ══════════════════════════════════════════════════════════
# 5. DeprecationWarning
# ══════════════════════════════════════════════════════════


class TestDeprecation:
    """验证旧 WsStepExecutor 触发 DeprecationWarning"""

    def test_ws_step_executor_emits_deprecation_warning(self):
        """实例化 WsStepExecutor 应触发 DeprecationWarning"""
        from framework.executors.ws_executor import WsStepExecutor

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            WsStepExecutor(template_engine=MagicMock())

            deprecation_warnings = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "AsyncWsStepExecutor" in str(deprecation_warnings[0].message)


# ══════════════════════════════════════════════════════════
# 6. 在已有事件循环中 aexecute()
# ══════════════════════════════════════════════════════════


class TestInExistingEventLoop:
    """验证在已有事件循环中 aexecute() 不产生冲突"""

    @pytest.mark.asyncio
    async def test_aexecute_in_existing_loop(self, echo_server, executor, test_context):
        """在 pytest-asyncio 提供的事件循环中直接调用 aexecute()"""
        case = make_ws_case(echo_server.url, messages=make_echo_messages(2))

        # 直接 await，无 nest_asyncio，无线程池
        result = await executor.aexecute(case, test_context, {})

        assert result.passed is True
        # 验证事件循环没有被破坏
        loop = asyncio.get_running_loop()
        assert loop.is_running()

    @pytest.mark.asyncio
    async def test_multiple_concurrent_ws_calls(self, echo_server, executor, test_context):
        """并发执行多个 WS 用例，验证无事件循环冲突"""
        async def run_one(name: str):
            case = make_ws_case(
                echo_server.url,
                messages=make_echo_messages(1),
                name=name,
            )
            return await executor.aexecute(case, test_context, {})

        results = await asyncio.gather(
            run_one("ws_1"),
            run_one("ws_2"),
            run_one("ws_3"),
        )

        for r in results:
            assert r.passed is True


# ══════════════════════════════════════════════════════════
# 7. 消息断言
# ══════════════════════════════════════════════════════════


class TestMessageAssertion:
    """验证 WS 消息 JSONPath 断言"""

    @pytest.mark.asyncio
    async def test_jsonpath_assertion_on_received_message(self, executor, test_context):
        """对回显的 JSON 消息执行 JSONPath 断言"""
        server = EchoServer(port=18770)
        await server.start()
        try:
            import json

            payload = json.dumps({"status": "ok", "code": 200})
            messages = [
                WSMessage(type="send", data=payload),
                WSMessage(
                    type="receive",
                    timeout=5,
                    expect={"jsonpath": {"$.status": "ok", "$.code": 200}},
                ),
            ]
            case = make_ws_case(server.url, messages=messages)

            result = await executor.aexecute(case, test_context, {})

            assert result.passed is True
        finally:
            await server.stop()


# ══════════════════════════════════════════════════════════
# 8. Runner 集成 — WS 用例走原生异步路径
# ══════════════════════════════════════════════════════════


class TestRunnerIntegration:
    """验证 runner.arun_case() 对 WS 用例使用原生异步路径"""

    @pytest.mark.asyncio
    async def test_arun_case_uses_async_executor(self, echo_server, test_context):
        """arun_case 对 WS 用例应直接走 aexecute()，不走线程池桥接"""
        from framework.models import EnvConfig, ProjectConfig
        from framework.runner import TestRunner

        config = ProjectConfig(project_name="test", case_timeout=10)
        env = EnvConfig(name="test", base_url="http://localhost")

        runner = TestRunner(
            config=config,
            env=env,
            http_client=MagicMock(),
            context=test_context,
            auto_discover_plugins=False,
        )

        case = make_ws_case(echo_server.url, messages=make_echo_messages(2))

        result = await runner.arun_case(case, {})

        assert result.passed is True
        assert result.status == "PASS"

    @pytest.mark.asyncio
    async def test_arun_case_ws_execution_completes_in_event_loop(
        self, echo_server, test_context
    ):
        """验证 WS 用例在事件循环中执行完毕后状态正常"""
        from framework.models import EnvConfig, ProjectConfig
        from framework.runner import TestRunner

        config = ProjectConfig(project_name="test", case_timeout=10)
        env = EnvConfig(name="test", base_url="http://localhost")

        runner = TestRunner(
            config=config,
            env=env,
            http_client=MagicMock(),
            context=test_context,
            auto_discover_plugins=False,
        )

        case = make_ws_case(echo_server.url, messages=make_echo_messages(3))

        result = await runner.arun_case(case, {})

        assert result.passed is True
        # 验证事件循环仍在正常运行
        loop = asyncio.get_running_loop()
        assert loop.is_running()
