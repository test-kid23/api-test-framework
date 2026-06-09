"""断言子系统 — 包含断言引擎和智能断言

模块:
- framework.assertion.engine: 断言引擎（16 种操作符 + AssertionEngine）
- framework.assertion.smart: 智能断言（Schema 推断 + 变更检测）

向后兼容: 从 framework.assertion 直接导入，与原来 framework.assertion.py 行为一致。
"""

from framework.assertion.engine import (
    AssertionEngine,
    _BUILTIN_OPERATORS,
    op_between,
    op_contains,
    op_eq,
    op_gt,
    op_gte,
    op_in,
    op_is_null,
    op_length,
    op_lt,
    op_lte,
    op_matches,
    op_ne,
    op_not_contains,
    op_not_in,
    op_not_null,
    op_type,
)

__all__ = [
    "AssertionEngine",
    "_BUILTIN_OPERATORS",
    "op_between",
    "op_contains",
    "op_eq",
    "op_gt",
    "op_gte",
    "op_in",
    "op_is_null",
    "op_length",
    "op_lt",
    "op_lte",
    "op_matches",
    "op_ne",
    "op_not_contains",
    "op_not_in",
    "op_not_null",
    "op_type",
]
