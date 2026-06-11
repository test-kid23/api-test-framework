"""断言引擎 — 支持多种操作符和嵌套校验

线程安全设计：
- DEFAULT_OPERATORS 为类级别不可变映射（MappingProxyType），所有实例共享只读默认值
- 每个实例通过 __init__() 深拷贝获得独立的 self._operators，互不干扰
- register_operator 为实例方法，仅在当前实例注册，不影响其他实例
"""

from __future__ import annotations

import copy
import re
from types import MappingProxyType
from typing import Any, Callable

from framework.models import (
    AssertionReport,
    AssertItem,
    AssertResult,
    CompositeAssertItem,
    HttpResponse,
)
from framework.utils.jsonpath_util import extract_value
from framework.utils.logger import Logger

logger = Logger.get("assertion")


# ==================== 内置操作符函数（模块级，纯函数） ====================


def op_eq(actual: Any, expected: Any) -> bool:
    """等于"""
    if actual == expected:
        return True
    # 类型感知比较：尝试数值匹配
    try:
        if float(actual) == float(expected):
            return True
    except (ValueError, TypeError):
        pass
    return str(actual) == str(expected)


def op_ne(actual: Any, expected: Any) -> bool:
    """不等于"""
    return not op_eq(actual, expected)


def op_gt(actual: Any, expected: Any) -> bool:
    """大于"""
    return float(actual) > float(expected)


def op_gte(actual: Any, expected: Any) -> bool:
    """大于等于"""
    return float(actual) >= float(expected)


def op_lt(actual: Any, expected: Any) -> bool:
    """小于"""
    return float(actual) < float(expected)


def op_lte(actual: Any, expected: Any) -> bool:
    """小于等于"""
    return float(actual) <= float(expected)


def op_contains(actual: Any, expected: Any) -> bool:
    """包含"""
    return expected in actual


def op_not_contains(actual: Any, expected: Any) -> bool:
    """不包含"""
    return expected not in actual


def op_matches(actual: Any, expected: Any) -> bool:
    """正则匹配"""
    return bool(re.match(expected, str(actual)))


def op_in(actual: Any, expected: Any) -> bool:
    """在...中"""
    return actual in expected


def op_not_in(actual: Any, expected: Any) -> bool:
    """不在...中"""
    return actual not in expected


def op_not_null(actual: Any, expected: Any = None) -> bool:
    """非空"""
    return actual is not None


def op_is_null(actual: Any, expected: Any = None) -> bool:
    """为空"""
    return actual is None


def op_type(actual: Any, expected: Any) -> bool:
    """类型检查"""
    type_map: dict[str, type] = {
        "str": str,
        "string": str,
        "int": int,
        "integer": int,
        "float": float,
        "bool": bool,
        "boolean": bool,
        "list": list,
        "array": list,
        "dict": dict,
        "object": dict,
        "none": type(None),
    }
    expected_type = type_map.get(str(expected), str)
    return isinstance(actual, expected_type)


def op_length(actual: Any, expected: Any) -> bool:
    """长度校验：支持 length: 3 或 length: ">0" 或 length: "[1,10]" """
    length = len(actual) if hasattr(actual, "__len__") else 0
    if isinstance(expected, int):
        return length == expected
    if isinstance(expected, str):
        return _compare(length, expected)
    return False


def op_between(actual: Any, expected: Any) -> bool:
    """区间校验：expected = [min, max]"""
    if isinstance(expected, (list, tuple)) and len(expected) == 2:
        return float(expected[0]) <= float(actual) <= float(expected[1])
    return False


def _compare(actual: Any, expected: str) -> bool:
    """解析比较表达式，如 ">0", "<100", "!=null" """
    match = re.match(r"^([><=!]+)\s*(.+)$", expected)
    if not match:
        return str(actual) == expected

    op, val_str = match.groups()
    try:
        val: float = float(val_str)
        actual_f: float = float(actual)
    except (ValueError, TypeError):
        val_as_str: str = val_str
        actual_s: str = str(actual)
        if op == "!=":
            return actual_s != val_as_str
        if op == "==":
            return actual_s == val_as_str
        return False

    if op == ">":
        return actual_f > val
    elif op == ">=":
        return actual_f >= val
    elif op == "<":
        return actual_f < val
    elif op == "<=":
        return actual_f <= val
    elif op == "!=":
        return actual_f != val
    elif op == "==":
        return actual_f == val
    return False


# ==================== 不可变默认操作符注册表 ====================

_BUILTIN_OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": op_eq,
    "ne": op_ne,
    "gt": op_gt,
    "gte": op_gte,
    "lt": op_lt,
    "lte": op_lte,
    "contains": op_contains,
    "not_contains": op_not_contains,
    "matches": op_matches,
    "in": op_in,
    "not_in": op_not_in,
    "not_null": op_not_null,
    "is_null": op_is_null,
    "type": op_type,
    "length": op_length,
    "between": op_between,
}


class AssertionEngine:
    """断言引擎 — 支持多种操作符和嵌套校验

    线程安全：
    - DEFAULT_OPERATORS：类级别不可变映射，所有实例共享（只读）
    - self._operators：实例级别字典，通过深拷贝初始化，各实例独立
    - register_operator：实例方法，仅影响当前实例
    """

    # 类级别不可变默认注册表（包含全部 16 种内置操作符）
    DEFAULT_OPERATORS: MappingProxyType[str, Callable[[Any, Any], bool]] = MappingProxyType(
        _BUILTIN_OPERATORS
    )

    def __init__(self) -> None:
        """初始化断言引擎实例

        从类级别不可变默认注册表深拷贝一份独立的操作符映射，
        确保不同实例之间的操作符注册互不干扰。
        """
        self._operators: dict[str, Callable[[Any, Any], bool]] = copy.deepcopy(
            dict(AssertionEngine.DEFAULT_OPERATORS)
        )

    def register_operator(
        self, name: str
    ) -> Callable[[Callable[[Any, Any], bool]], Callable[[Any, Any], bool]]:
        """装饰器：注册自定义操作符（仅影响当前实例，线程安全）

        Usage:
            engine = AssertionEngine()
            @engine.register_operator("my_check")
            def my_check(actual, expected):
                return actual == expected
        """

        def decorator(func: Callable[[Any, Any], bool]) -> Callable[[Any, Any], bool]:
            self._operators[name] = func
            return func

        return decorator

    def _get_operator(self, name: str) -> Callable[[Any, Any], bool] | None:
        """从当前实例的操作符注册表中查找操作符"""
        return self._operators.get(name)

    def assert_response(
        self,
        response: HttpResponse,
        assertions: list[AssertItem | CompositeAssertItem],
        variables: dict[str, Any] | None = None,
    ) -> AssertionReport:
        """执行所有断言（支持普通断言和组合断言），返回断言报告.

        对普通 AssertItem 调用 _assert_single()；
        对 CompositeAssertItem 调用 _assert_composite() 进行 AND/OR 短路求值。
        所有子断言的结果会被扁平化收集到最终报告中。
        """
        results: list[AssertResult] = []

        for item in assertions:
            if isinstance(item, CompositeAssertItem):
                composite_results = self._assert_composite(response, item, variables or {})
                results.extend(composite_results)
            else:
                try:
                    result = self._assert_single(response, item, variables or {})
                    results.append(result)
                    if not result.passed:
                        logger.warning(
                            "assertion_failed",
                            path=result.path,
                            expected=result.expected,
                            actual=result.actual,
                            operator=result.operator,
                        )
                except (AssertionError, TypeError, KeyError) as e:
                    results.append(
                        AssertResult(
                            passed=False,
                            path=item.path,
                            expected=item.expected,
                            actual=None,
                            operator=item.operator,
                            message=f"断言执行异常: {e}",
                        )
                    )

        report = AssertionReport(results=results)
        logger.info(
            "assertion_report",
            total=len(results),
            passed=report.pass_count,
            failed=report.fail_count,
        )
        return report

    def _assert_composite(
        self,
        response: HttpResponse,
        composite: CompositeAssertItem,
        variables: dict[str, Any],
    ) -> list[AssertResult]:
        """执行组合断言（AND/OR），支持短路求值和任意深度嵌套.

        Args:
            response: HTTP 响应对象。
            composite: 组合断言项。
            variables: 模板变量字典。

        Returns:
            所有子断言的扁平化结果列表。

        AND 短路逻辑：遇到第一个失败即停止，后续子断言不再执行。
        OR 短路逻辑：遇到第一个成功即停止，后续子断言不再执行。
        """
        results: list[AssertResult] = []
        combinator = composite.combinator

        for child in composite.children:
            if isinstance(child, CompositeAssertItem):
                child_results = self._assert_composite(response, child, variables)
                results.extend(child_results)
                # 短路判断：根据嵌套组合的 combinator 判断其整体通过/失败
                child_passed = self._composite_passed(child.combinator, child_results)
                if combinator == "all_of" and not child_passed:
                    break
                elif combinator == "any_of" and child_passed:
                    break
            else:
                try:
                    result = self._assert_single(response, child, variables)
                    results.append(result)
                    if not result.passed:
                        logger.warning(
                            "assertion_failed",
                            path=result.path,
                            expected=result.expected,
                            actual=result.actual,
                            operator=result.operator,
                        )
                    # 短路判断
                    if combinator == "all_of" and not result.passed:
                        break
                    elif combinator == "any_of" and result.passed:
                        break
                except (AssertionError, TypeError, KeyError) as e:
                    err_result = AssertResult(
                        passed=False,
                        path=child.path,
                        expected=child.expected,
                        actual=None,
                        operator=child.operator,
                        message=f"断言执行异常: {e}",
                    )
                    results.append(err_result)
                    if combinator == "all_of":
                        break

        return results

    @staticmethod
    def _composite_passed(combinator: str, results: list[AssertResult]) -> bool:
        """根据 combinator 判断组合断言整体是否通过.

        Args:
            combinator: "all_of" 或 "any_of"。
            results: 该组合下已执行的所有子结果。

        Returns:
            all_of 时所有结果都通过才为 True；any_of 时任一结果通过即为 True。
            空结果列表返回 False。
        """
        if not results:
            return False
        if combinator == "all_of":
            return all(r.passed for r in results)
        elif combinator == "any_of":
            return any(r.passed for r in results)
        return False

    def _assert_single(
        self,
        response: HttpResponse,
        item: AssertItem,
        variables: dict[str, Any],
    ) -> AssertResult:
        """执行单个断言"""
        # 获取实际值
        actual = self._get_actual_value(response, item.path)

        # 处理期望值中的变量替换
        expected = item.expected
        if isinstance(expected, str) and "{{" in expected:
            from framework.utils.template import TemplateEngine

            template = TemplateEngine()
            expected = template.render(expected, variables)

        # 从实例注册表查找操作符
        operator_func = self._get_operator(item.operator)
        if operator_func is None:
            return AssertResult(
                passed=False,
                path=item.path,
                expected=expected,
                actual=actual,
                operator=item.operator,
                message=f"未知操作符: {item.operator}",
            )

        # 特殊处理：not_null 和 is_null 不需要 expected 比较
        if item.operator in ("not_null", "is_null"):
            passed = bool(operator_func(actual, None))
        else:
            passed = operator_func(actual, expected)

        return AssertResult(
            passed=passed,
            path=item.path,
            expected=expected,
            actual=actual,
            operator=item.operator,
            message="" if passed else f"期望 {item.operator} {expected}，实际 {actual}",
        )

    def _get_actual_value(self, response: HttpResponse, path: str) -> Any:
        """从响应中获取实际值"""
        # 状态码
        if path == "status_code":
            return response.status_code

        # 响应时间
        if path == "response_time":
            return response.elapsed_ms

        # 响应体大小
        if path == "body_size":
            return response.size_bytes

        # 响应头
        if path.startswith("headers."):
            header_name = path[8:]
            return response.headers.get(header_name)

        # Body 直接字段
        if path.startswith("body."):
            field_path = path[5:]
            return self._get_nested_value(response.body, field_path)

        # JSONPath（默认）
        if path.startswith("$."):
            return extract_value(response.body, path)

        # 尝试作为 body 字段
        return self._get_nested_value(response.body, path)

    @staticmethod
    def _get_nested_value(obj: Any, path: str) -> Any:
        """获取嵌套对象的值，支持 a.b.c 风格路径"""
        parts = path.split(".")
        current = obj
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    idx = int(part)
                    current = current[idx] if 0 <= idx < len(current) else None
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current
