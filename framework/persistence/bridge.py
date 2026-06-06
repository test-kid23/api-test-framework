"""同步/异步桥接 — 在 pytest 同步钩子中安全执行异步数据库操作。

pytest 的 hooks/fixtures 运行在同步线程中，但 SQLAlchemy ORM 使用
AsyncSession。此模块提供 run_async() 将 async 协程桥接到同步上下文中。

使用示例：
    from framework.persistence.bridge import run_async

    async def _save(session):
        session.add(record)
        await session.commit()

    run_async(_save(session))
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """在同步代码中安全执行异步协程。

    - 无运行中事件循环时：直接 asyncio.run()
    - 有运行中事件循环时：在新线程中创建独立 loop 执行
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # 已有事件循环（极少场景，如 Jupyter/某些 async fixture）
    result: dict[str, Any] = {"value": None, "error": None}

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:
            result["error"] = exc

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join()

    if result["error"] is not None:
        raise result["error"]  # type: ignore[misc]
    return result["value"]  # type: ignore[no-any-return]
