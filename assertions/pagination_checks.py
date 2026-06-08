"""自定义断言函数示例

注意：自 v2.0 起，register_operator 为实例方法，需要先创建 AssertionEngine 实例，
再向指定实例注册自定义操作符。参见 register_custom_operators() 函数。
"""

from __future__ import annotations

from typing import Any

from framework.assertion import AssertionEngine


def check_pagination(actual: Any, expected: Any = None) -> bool:
    """检查分页结构是否完整

    期望 actual 是一个分页响应，包含 list 和 total 字段
    """
    if not isinstance(actual, dict):
        return False
    return "list" in actual and "total" in actual


def register_custom_operators(engine: AssertionEngine) -> None:
    """向指定 AssertionEngine 实例注册自定义操作符

    每个 AssertionEngine 实例拥有独立的操作符注册表，
    注册仅影响当前实例，不会污染其他实例。

    Usage:
        engine = AssertionEngine()
        register_custom_operators(engine)
        # 现在 engine 支持 "check_pagination" 操作符
    """
    engine.register_operator("check_pagination")(check_pagination)


def verify_pagination(response_body: dict[str, Any], min_items: int = 1) -> bool:
    """验证分页响应

    Args:
        response_body: 响应体
        min_items: 最少条目数
    """
    data = response_body.get("data", response_body)
    items = data.get("list", [])
    total = data.get("total", 0)
    return len(items) >= min_items and total >= min_items
