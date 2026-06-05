"""WebSocket 客户端 — 支持 WebSocket 接口测试"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from framework.models import WSConfig, WSResult
from framework.utils.logger import Logger
from framework.utils.template import TemplateEngine

logger = Logger.get("ws")

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


def _ws_connect_kwargs(headers: dict[str, str], timeout: int) -> dict:
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


class WSClient:
    """WebSocket 异步客户端"""

    def __init__(self, config: WSConfig, template_engine: TemplateEngine | None = None) -> None:
        self._config = config
        self._template = template_engine or TemplateEngine()

    async def execute(self, variables: dict[str, Any]) -> WSResult:
        """执行完整的 WebSocket 交互流程"""
        if not _has_websockets:
            raise ImportError("websockets 未安装，请运行: pip install websockets")

        url = self._template.render(self._config.url, variables)
        headers = self._template.render_dict(self._config.headers, variables)
        received_messages: list[str | bytes] = []
        errors: list[str] = []
        total_sent = 0

        logger.info(f"连接 WebSocket: {url}")

        connect_kwargs = _ws_connect_kwargs(headers, self._config.timeout)

        try:
            async with websockets.connect(
                url,
                **connect_kwargs,
            ) as ws:
                for msg_config in self._config.messages:
                    msg_type = msg_config.type

                    if msg_type == "send":
                        data = self._template.render(str(msg_config.data), variables)
                        logger.debug(f"发送: {data[:200]}")
                        await ws.send(data)
                        total_sent += 1

                    elif msg_type == "receive":
                        timeout = msg_config.timeout or self._config.timeout
                        try:
                            data = await asyncio.wait_for(ws.recv(), timeout=timeout)
                            logger.debug(f"接收: {str(data)[:200]}")
                            received_messages.append(data)

                            # 如果有断言配置
                            if msg_config.expect:
                                parsed = json.loads(data) if isinstance(data, str) else data
                                self._assert_message(parsed, msg_config.expect)

                        except asyncio.TimeoutError:
                            errors.append(f"接收消息超时 ({timeout}s)")
                            break

                    elif msg_type == "close":
                        await ws.close()
                        break

        except Exception as e:
            errors.append(f"WebSocket 错误: {e}")
            logger.error(f"WebSocket 错误: {e}")

        return WSResult(
            received_messages=received_messages,
            errors=errors,
            total_sent=total_sent,
            total_received=len(received_messages),
        )

    def _assert_message(self, data: Any, expect: dict[str, Any]) -> None:
        """对接收到的消息做简单断言"""
        from framework.utils.jsonpath_util import extract_value

        jsonpath_expect = expect.get("jsonpath", {})
        for path, expected in jsonpath_expect.items():
            actual = extract_value(data, path)
            if actual != expected:
                logger.warning(f"WS 消息断言失败: {path} 期望={expected} 实际={actual}")


class WSSyncClient:
    """WebSocket 同步客户端（适配 pytest）"""

    def __init__(self, config: WSConfig, template_engine: TemplateEngine | None = None) -> None:
        self._async_client = WSClient(config, template_engine)

    def execute(self, variables: dict[str, Any]) -> WSResult:
        """同步执行 WebSocket 交互"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 在已有事件循环中（如 pytest-asyncio），使用 nest_asyncio
            try:
                import nest_asyncio

                nest_asyncio.apply()
                return loop.run_until_complete(self._async_client.execute(variables))
            except ImportError:
                # 降级：创建新线程运行
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(asyncio.run, self._async_client.execute(variables))
                    return future.result(timeout=60)

        return asyncio.run(self._async_client.execute(variables))
