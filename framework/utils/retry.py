"""重试装饰器 — 支持可配置的重试策略"""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable

from framework.utils.logger import Logger

logger = Logger.get("retry")


def retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 1.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    retry_on_status: list[int] | None = None,
) -> Callable[..., Any]:
    """重试装饰器

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 退避系数（每次重试延迟 * backoff）
        retry_on: 触发重试的异常类型
        retry_on_status: 触发重试的 HTTP 状态码
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)

                    # 检查是否需要基于状态码重试
                    if retry_on_status and hasattr(result, "status_code"):
                        if result.status_code in retry_on_status:
                            if attempt < max_retries:
                                logger.warning(
                                    f"状态码 {result.status_code} 触发重试 "
                                    f"({attempt + 1}/{max_retries}), 等待 {current_delay}s"
                                )
                                time.sleep(current_delay)
                                current_delay *= backoff
                                continue

                    return result

                except retry_on as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"异常 {type(e).__name__}: {e} 触发重试 "
                            f"({attempt + 1}/{max_retries}), 等待 {current_delay}s"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"重试 {max_retries} 次后仍然失败: {e}")

            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator
