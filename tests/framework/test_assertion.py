"""AssertionEngine 测试套件

覆盖：
1. 16 种内置操作符功能验证
2. DEFAULT_OPERATORS 不可变性
3. 实例操作符隔离（核心线程安全验证）
4. 并发安全测试（多线程 + 多实例互不干扰）
5. register_operator 实例方法
6. _get_operator 查找
7. assert_response / _assert_single 完整流程
8. 自定义操作符覆盖内置操作符
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import MappingProxyType
from typing import Any

import pytest

from framework.assertion import (
    AssertionEngine,
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
from framework.models import AssertionReport, AssertItem, AssertResult, HttpResponse

# ══════════════════════════════════════════════════════════
# 辅助工厂函数
# ══════════════════════════════════════════════════════════


def make_response(
    status_code: int = 200,
    body: Any = None,
    headers: dict[str, str] | None = None,
    elapsed_ms: float = 100.0,
    size_bytes: int = 1024,
) -> HttpResponse:
    """创建测试用 HttpResponse"""
    if headers is None:
        headers = {}
    if body is None:
        body = {}
    return HttpResponse(
        status_code=status_code,
        headers=headers,
        body=body,
        elapsed_ms=elapsed_ms,
        size_bytes=size_bytes,
        url="http://test/api",
    )


def make_assert_item(
    path: str,
    expected: Any,
    operator: str = "eq",
    message: str = "",
) -> AssertItem:
    """创建测试用 AssertItem"""
    return AssertItem(
        path=path,
        expected=expected,
        operator=operator,
        message=message,
    )


# ══════════════════════════════════════════════════════════
# 1. DEFAULT_OPERATORS 不可变性
# ══════════════════════════════════════════════════════════


class TestDefaultOperators:
    """验证 DEFAULT_OPERATORS 为不可变映射，包含全部 16 种操作符"""

    OPERATOR_NAMES = [
        "eq",
        "ne",
        "gt",
        "gte",
        "lt",
        "lte",
        "contains",
        "not_contains",
        "matches",
        "in",
        "not_in",
        "not_null",
        "is_null",
        "type",
        "length",
        "between",
    ]

    def test_contains_all_16_operators(self):
        for name in self.OPERATOR_NAMES:
            assert name in AssertionEngine.DEFAULT_OPERATORS, f"缺少操作符: {name}"

    def test_is_mapping_proxy_type(self):
        assert isinstance(AssertionEngine.DEFAULT_OPERATORS, MappingProxyType)

    def test_is_immutable__cannot_setitem(self):
        with pytest.raises(TypeError):
            AssertionEngine.DEFAULT_OPERATORS["new_op"] = lambda a, e: True  # type: ignore[index]

    def test_is_immutable__cannot_delitem(self):
        with pytest.raises(TypeError):
            del AssertionEngine.DEFAULT_OPERATORS["eq"]  # type: ignore[arg-type]

    def test_exact_count_16(self):
        assert len(AssertionEngine.DEFAULT_OPERATORS) == 16


# ══════════════════════════════════════════════════════════
# 2. 内置操作符函数单元测试
# ══════════════════════════════════════════════════════════


class TestOperatorEq:
    def test_equal_numbers(self):
        assert op_eq(100, 100) is True

    def test_equal_strings(self):
        assert op_eq("hello", "hello") is True

    def test_not_equal(self):
        assert op_eq(1, 2) is False

    def test_type_aware__int_string(self):
        assert op_eq(10, "10") is True

    def test_type_aware__float_string(self):
        assert op_eq(3.14, "3.14") is True

    def test_string_comparison_fallback(self):
        assert op_eq("abc", "abc") is True


class TestOperatorNe:
    def test_not_equal(self):
        assert op_ne(1, 2) is True

    def test_equal__should_fail(self):
        assert op_ne(1, 1) is False


class TestOperatorGt:
    def test_greater(self):
        assert op_gt(10, 5) is True

    def test_not_greater(self):
        assert op_gt(5, 10) is False

    def test_equal__not_greater(self):
        assert op_gt(5, 5) is False


class TestOperatorGte:
    def test_greater(self):
        assert op_gte(10, 5) is True

    def test_equal(self):
        assert op_gte(5, 5) is True

    def test_less(self):
        assert op_gte(3, 5) is False


class TestOperatorLt:
    def test_less(self):
        assert op_lt(3, 10) is True

    def test_not_less(self):
        assert op_lt(10, 5) is False


class TestOperatorLte:
    def test_less(self):
        assert op_lte(3, 10) is True

    def test_equal(self):
        assert op_lte(5, 5) is True

    def test_greater(self):
        assert op_lte(10, 3) is False


class TestOperatorContains:
    def test_substring_found(self):
        assert op_contains("hello world", "world") is True

    def test_substring_not_found(self):
        assert op_contains("hello world", "xyz") is False

    def test_list_contains(self):
        assert op_contains([1, 2, 3], 2) is True

    def test_list_not_contains(self):
        assert op_contains([1, 2, 3], 5) is False


class TestOperatorNotContains:
    def test_not_found(self):
        assert op_not_contains("hello", "xyz") is True

    def test_found__should_fail(self):
        assert op_not_contains("hello", "ell") is False


class TestOperatorMatches:
    def test_regex_match(self):
        assert op_matches("abc123", r"^abc\d{3}$") is True

    def test_regex_no_match(self):
        assert op_matches("abc1234", r"^abc\d{3}$") is False


class TestOperatorIn:
    def test_in_list(self):
        assert op_in(2, [1, 2, 3]) is True

    def test_not_in_list(self):
        assert op_in(5, [1, 2, 3]) is False

    def test_in_string(self):
        assert op_in("a", "abc") is True


class TestOperatorNotIn:
    def test_not_in_list(self):
        assert op_not_in(5, [1, 2, 3]) is True

    def test_in_list__should_fail(self):
        assert op_not_in(2, [1, 2, 3]) is False


class TestOperatorNotNull:
    def test_not_none(self):
        assert op_not_null("value") is True

    def test_zero_is_not_none(self):
        assert op_not_null(0) is True

    def test_empty_string_is_not_none(self):
        assert op_not_null("") is True

    def test_none(self):
        assert op_not_null(None) is False


class TestOperatorIsNull:
    def test_none(self):
        assert op_is_null(None) is True

    def test_not_none(self):
        assert op_is_null("value") is False


class TestOperatorType:
    def test_str(self):
        assert op_type("hello", "str") is True

    def test_int(self):
        assert op_type(42, "int") is True

    def test_float(self):
        assert op_type(3.14, "float") is True

    def test_bool(self):
        assert op_type(True, "bool") is True

    def test_list(self):
        assert op_type([1, 2], "list") is True

    def test_dict(self):
        assert op_type({"a": 1}, "dict") is True

    def test_wrong_type(self):
        assert op_type("hello", "int") is False


class TestOperatorLength:
    def test_exact_length(self):
        assert op_length([1, 2, 3], 3) is True

    def test_wrong_length(self):
        assert op_length([1, 2, 3], 5) is False

    def test_string_length_gt(self):
        assert op_length("hello", ">3") is True

    def test_string_length_gte(self):
        assert op_length("hello", ">=5") is True

    def test_string_length_lt(self):
        assert op_length("hi", "<5") is True

    def test_no_len_object(self):
        # 整数无 __len__，默认 length=0；期望 0 时当然相等
        assert op_length(42, 0) is True


class TestOperatorBetween:
    def test_in_range(self):
        assert op_between(5, [1, 10]) is True

    def test_at_lower_bound(self):
        assert op_between(1, [1, 10]) is True

    def test_at_upper_bound(self):
        assert op_between(10, [1, 10]) is True

    def test_below_range(self):
        assert op_between(0, [1, 10]) is False

    def test_above_range(self):
        assert op_between(11, [1, 10]) is False

    def test_invalid_expected(self):
        assert op_between(5, "invalid") is False


# ══════════════════════════════════════════════════════════
# 3. AssertionEngine 实例初始化
# ══════════════════════════════════════════════════════════


class TestAssertionEngineInit:
    """验证实例初始化：每个实例拥有独立的操作符表"""

    def test_default_operators_copied_to_instance(self):
        engine = AssertionEngine()
        for name in AssertionEngine.DEFAULT_OPERATORS:
            assert engine._get_operator(name) is not None, f"实例缺少操作符: {name}"

    def test_instance_count_matches_default(self):
        engine = AssertionEngine()
        assert len(engine._operators) == len(AssertionEngine.DEFAULT_OPERATORS)

    def test_instance_operators_are_independent__add(self):
        """向一个实例注册操作符，不应影响另一个实例"""
        engine1 = AssertionEngine()
        engine2 = AssertionEngine()

        @engine1.register_operator("custom_only_in_1")
        def custom_op(actual, expected):
            return True

        assert engine1._get_operator("custom_only_in_1") is not None
        assert engine2._get_operator("custom_only_in_1") is None

    def test_instance_operators_are_independent__override(self):
        """一个实例覆盖内置操作符，不应影响另一个实例"""
        engine1 = AssertionEngine()
        engine2 = AssertionEngine()

        @engine1.register_operator("eq")
        def always_true(actual, expected):
            return True

        # engine1 的 eq 被覆盖
        assert engine1._get_operator("eq")(1, 2) is True  # always returns True
        # engine2 的 eq 仍是原始的
        assert engine2._get_operator("eq")(1, 2) is False  # original behavior

    def test_default_operators_unchanged_after_instance_override(self):
        """实例覆盖操作符后，DEFAULT_OPERATORS 保持不变"""
        engine = AssertionEngine()

        @engine.register_operator("eq")
        def custom_eq(a, e):
            return True

        # DEFAULT_OPERATORS 仍是原始值
        assert AssertionEngine.DEFAULT_OPERATORS["eq"](1, 2) is False


# ══════════════════════════════════════════════════════════
# 4. register_operator 实例方法
# ══════════════════════════════════════════════════════════


class TestRegisterOperator:
    def test_register_new_operator(self):
        engine = AssertionEngine()

        @engine.register_operator("custom_sum")
        def custom_sum(actual, expected):
            return sum(actual) == expected

        assert engine._get_operator("custom_sum") is not None
        assert engine._get_operator("custom_sum")([1, 2, 3], 6) is True

    def test_register_overrides_existing(self):
        engine = AssertionEngine()

        @engine.register_operator("eq")
        def always_false(a, e):
            return False

        assert engine._get_operator("eq")(100, 100) is False

    def test_register_returns_function(self):
        engine = AssertionEngine()

        @engine.register_operator("my_op")
        def my_op(a, e):
            return True

        assert callable(my_op)
        assert my_op(1, 2) is True

    def test_register_does_not_affect_class_default(self):
        engine = AssertionEngine()
        original_len = len(engine._operators)

        @engine.register_operator("custom_new")
        def custom_new(a, e):
            return True

        assert len(engine._operators) == original_len + 1
        # 类级别不受影响
        assert "custom_new" not in AssertionEngine.DEFAULT_OPERATORS


# ══════════════════════════════════════════════════════════
# 5. _get_operator 查找
# ══════════════════════════════════════════════════════════


class TestGetOperator:
    def test_get_builtin(self):
        engine = AssertionEngine()
        op = engine._get_operator("eq")
        assert op is not None
        assert op(1, 1) is True

    def test_get_unknown_returns_none(self):
        engine = AssertionEngine()
        assert engine._get_operator("nonexistent") is None

    def test_get_custom_after_register(self):
        engine = AssertionEngine()

        @engine.register_operator("hello")
        def hello(a, e):
            return True

        assert engine._get_operator("hello") is not None


# ══════════════════════════════════════════════════════════
# 6. assert_response 完整流程
# ══════════════════════════════════════════════════════════


class TestAssertResponse:
    def test_status_code_assertion_passes(self):
        engine = AssertionEngine()
        response = make_response(status_code=200)
        items = [make_assert_item("status_code", 200, "eq")]
        report = engine.assert_response(response, items)
        assert report.passed is True
        assert report.pass_count == 1

    def test_status_code_assertion_fails(self):
        engine = AssertionEngine()
        response = make_response(status_code=200)
        items = [make_assert_item("status_code", 404, "eq")]
        report = engine.assert_response(response, items)
        assert report.passed is False
        assert report.fail_count == 1

    def test_body_field_assertion(self):
        engine = AssertionEngine()
        response = make_response(body={"user": {"name": "Alice", "age": 30}})
        items = [
            make_assert_item("body.user.name", "Alice", "eq"),
            make_assert_item("body.user.age", 30, "eq"),
        ]
        report = engine.assert_response(response, items)
        assert report.passed is True
        assert report.pass_count == 2

    def test_body_field_nested(self):
        engine = AssertionEngine()
        response = make_response(body={"data": {"items": [1, 2, 3, 4, 5]}})
        items = [make_assert_item("body.data.items", [1, 2, 3, 4, 5], "eq")]
        report = engine.assert_response(response, items)
        assert report.passed is True

    def test_contains_operator_on_body(self):
        engine = AssertionEngine()
        response = make_response(body={"message": "Hello World"})
        items = [make_assert_item("body.message", "World", "contains")]
        report = engine.assert_response(response, items)
        assert report.passed is True

    def test_type_operator_on_body(self):
        engine = AssertionEngine()
        response = make_response(body={"data": {"nested": {"key": "value"}}})
        items = [make_assert_item("body.data.nested", "dict", "type")]
        report = engine.assert_response(response, items)
        assert report.passed is True

    def test_not_null_operator(self):
        engine = AssertionEngine()
        response = make_response(body={"name": "Bob"})
        items = [make_assert_item("body.name", None, "not_null")]
        report = engine.assert_response(response, items)
        assert report.passed is True

    def test_is_null_operator(self):
        engine = AssertionEngine()
        response = make_response(body={"name": None})
        items = [make_assert_item("body.name", None, "is_null")]
        report = engine.assert_response(response, items)
        assert report.passed is True

    def test_response_time_assertion(self):
        engine = AssertionEngine()
        response = make_response(elapsed_ms=150)
        items = [make_assert_item("response_time", 100, "gt")]
        report = engine.assert_response(response, items)
        assert report.passed is True

    def test_body_size_assertion(self):
        engine = AssertionEngine()
        response = make_response(size_bytes=2048)
        items = [make_assert_item("body_size", 1024, "gt")]
        report = engine.assert_response(response, items)
        assert report.passed is True

    def test_header_assertion(self):
        engine = AssertionEngine()
        response = make_response(headers={"Content-Type": "application/json"})
        items = [make_assert_item("headers.Content-Type", "application/json", "eq")]
        report = engine.assert_response(response, items)
        assert report.passed is True

    def test_unknown_operator_returns_failure(self):
        engine = AssertionEngine()
        response = make_response(status_code=200)
        items = [make_assert_item("status_code", 200, "unknown_op")]
        report = engine.assert_response(response, items)
        assert report.passed is False
        assert "未知操作符" in report.results[0].message

    def test_multiple_assertions_mixed_results(self):
        engine = AssertionEngine()
        response = make_response(status_code=200, body={"name": "Alice"})
        items = [
            make_assert_item("status_code", 200, "eq"),
            make_assert_item("status_code", 404, "eq"),  # fails
            make_assert_item("body.name", "Alice", "eq"),
        ]
        report = engine.assert_response(response, items)
        assert report.passed is False
        assert report.pass_count == 2
        assert report.fail_count == 1

    def test_custom_operator_used_in_assert_response(self):
        engine = AssertionEngine()

        @engine.register_operator("starts_with")
        def starts_with(actual, expected):
            return str(actual).startswith(str(expected))

        response = make_response(body={"prefix": "hello_world"})
        items = [make_assert_item("body.prefix", "hello", "starts_with")]
        report = engine.assert_response(response, items)
        assert report.passed is True

    def test_empty_assertions_list(self):
        engine = AssertionEngine()
        response = make_response()
        report = engine.assert_response(response, [])
        assert report.passed is True
        assert report.pass_count == 0

    def test_length_operator_in_assert_response(self):
        engine = AssertionEngine()
        response = make_response(body={"items": [1, 2, 3]})
        items = [make_assert_item("body.items", 3, "length")]
        report = engine.assert_response(response, items)
        assert report.passed is True

    def test_between_operator_in_assert_response(self):
        engine = AssertionEngine()
        response = make_response(body={"score": 85})
        items = [make_assert_item("body.score", [0, 100], "between")]
        report = engine.assert_response(response, items)
        assert report.passed is True


# ══════════════════════════════════════════════════════════
# 7. 实例隔离 — 多实例互不干扰（核心线程安全验证）
# ══════════════════════════════════════════════════════════


class TestInstanceIsolation:
    """验证多实例场景下的操作符隔离"""

    def test_multiple_instances_with_different_custom_operators(self):
        engine_a = AssertionEngine()
        engine_b = AssertionEngine()
        engine_c = AssertionEngine()

        @engine_a.register_operator("op_a")
        def op_a(actual, expected):
            return True

        @engine_b.register_operator("op_b")
        def op_b(actual, expected):
            return True

        @engine_c.register_operator("op_c")
        def op_c(actual, expected):
            return True

        # 各实例只能看到自己的操作符
        assert engine_a._get_operator("op_a") is not None
        assert engine_a._get_operator("op_b") is None
        assert engine_a._get_operator("op_c") is None

        assert engine_b._get_operator("op_b") is not None
        assert engine_b._get_operator("op_a") is None
        assert engine_b._get_operator("op_c") is None

        assert engine_c._get_operator("op_c") is not None
        assert engine_c._get_operator("op_a") is None
        assert engine_c._get_operator("op_b") is None

    def test_override_same_operator_differently(self):
        """多实例各自覆盖同一个内置操作符为不同行为"""
        engine_a = AssertionEngine()
        engine_b = AssertionEngine()

        @engine_a.register_operator("gt")
        def gt_a(actual, expected):
            return True  # 永远返回 True

        @engine_b.register_operator("gt")
        def gt_b(actual, expected):
            return False  # 永远返回 False

        assert engine_a._get_operator("gt")(1, 100) is True
        assert engine_b._get_operator("gt")(100, 1) is False

    def test_instances_do_not_share_custom_registrations(self):
        N = 10  # noqa: N806
        engines = [AssertionEngine() for _ in range(N)]

        for i, engine in enumerate(engines):
            op_name = f"custom_{i}"

            def make_op(idx):
                def op(a, e):
                    return idx

                return op

            engine.register_operator(op_name)(make_op(i))

        for i, engine in enumerate(engines):
            op_name = f"custom_{i}"
            # 当前引擎应有自己的操作符
            assert engine._get_operator(op_name) is not None
            # 其他引擎不应有
            for j, other in enumerate(engines):
                if i != j:
                    assert other._get_operator(op_name) is None


# ══════════════════════════════════════════════════════════
# 8. 并发安全测试（多线程）
# ══════════════════════════════════════════════════════════


class TestConcurrency:
    """并发安全测试：验证多线程环境下实例操作符互不干扰"""

    def test_concurrent_registrations_do_not_interfere(self):
        """多线程并发注册操作符到不同实例，互不干扰"""
        N_INSTANCES = 20  # noqa: N806
        N_THREADS = 10  # noqa: N806
        engines = [AssertionEngine() for _ in range(N_INSTANCES)]

        # 每个线程向自己分配的引擎实例注册操作符
        def register_for_instance(idx: int) -> int:
            engine = engines[idx]
            op_name = f"thread_op_{idx}"

            @engine.register_operator(op_name)
            def op(a, e):
                return idx

            # 验证只有自己的引擎有该操作符
            assert engine._get_operator(op_name) is not None
            assert engine._get_operator(op_name)(None, None) == idx
            return idx

        with ThreadPoolExecutor(max_workers=N_THREADS) as executor:
            futures = [executor.submit(register_for_instance, i) for i in range(N_INSTANCES)]
            results = [f.result(timeout=5) for f in as_completed(futures)]

        assert len(results) == N_INSTANCES

        # 交叉验证：每个引擎只有自己的操作符
        for i, engine in enumerate(engines):
            op_name = f"thread_op_{i}"
            assert (
                engine._get_operator(op_name) is not None
            ), f"engine[{i}] 缺少自己的操作符 {op_name}"
            for j in range(N_INSTANCES):
                if i != j:
                    assert (
                        engines[j]._get_operator(op_name) is None
                    ), f"engine[{j}] 不应有 engine[{i}] 的操作符 {op_name}"

    def test_concurrent_assertions_on_same_engine(self):
        """多线程在同一引擎实例上并发执行断言，应无竞争或错误"""
        engine = AssertionEngine()
        response = make_response(status_code=200, body={"value": 42})

        N_THREADS = 20  # noqa: N806
        errors = []
        lock = threading.Lock()

        def run_assertions() -> None:
            try:
                items = [
                    make_assert_item("status_code", 200, "eq"),
                    make_assert_item("body.value", 42, "eq"),
                    make_assert_item("body.value", 10, "gt"),
                ]
                report = engine.assert_response(response, items)
                if not report.passed:
                    with lock:
                        errors.append(f"assertions failed: {report.summary()}")
            except Exception as e:
                with lock:
                    errors.append(f"exception: {e}")

        threads = [threading.Thread(target=run_assertions) for _ in range(N_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"并发断言出现错误: {errors}"

    def test_concurrent_read_write_no_keyerror(self):
        """多线程同时读写同一引擎的操作符表，不应出现 KeyError"""
        engine = AssertionEngine()
        N_THREADS = 16  # noqa: N806
        N_OPERATIONS = 100  # noqa: N806

        errors = []
        lock = threading.Lock()

        def read_operators() -> None:
            try:
                for _ in range(N_OPERATIONS):
                    # 读取所有内置操作符
                    for op_name in AssertionEngine.DEFAULT_OPERATORS:
                        op = engine._get_operator(op_name)
                        if op is None:
                            with lock:
                                errors.append(f"KeyError-like: {op_name} is None")
            except Exception as e:
                with lock:
                    errors.append(f"read exception: {e}")

        def write_custom_operator(thread_id: int) -> None:
            try:
                for _ in range(N_OPERATIONS):
                    name = f"tmp_op_{thread_id}_{_}"

                    @engine.register_operator(name)
                    def tmp_op(a, e):
                        return True

            except Exception as e:
                with lock:
                    errors.append(f"write exception: {e}")

        threads = []
        for i in range(N_THREADS // 2):
            threads.append(threading.Thread(target=read_operators))
        for i in range(N_THREADS // 2):
            threads.append(threading.Thread(target=write_custom_operator, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"并发读写出现错误: {errors}"

    def test_concurrent_multi_engine_custom_operators(self):
        """模拟 pytest-xdist 场景：多个 worker 各自创建引擎、注册自定义操作符"""
        N_WORKERS = 4  # noqa: N806
        worker_engines: list[tuple[int, AssertionEngine, str]] = []

        def worker_setup(worker_id: int) -> tuple[int, AssertionEngine, str]:
            engine = AssertionEngine()
            custom_name = f"worker_{worker_id}_op"

            @engine.register_operator(custom_name)
            def worker_op(actual, expected):
                return True

            worker_engines.append((worker_id, engine, custom_name))
            return worker_id, engine, custom_name

        with ThreadPoolExecutor(max_workers=N_WORKERS) as executor:
            futures = [executor.submit(worker_setup, i) for i in range(N_WORKERS)]
            for f in as_completed(futures):
                f.result(timeout=5)

        assert len(worker_engines) == N_WORKERS

        # 每个 worker 的引擎应独立
        for wid_a, eng_a, op_a in worker_engines:
            assert eng_a._get_operator(op_a) is not None, f"worker_{wid_a} 引擎缺少操作符 {op_a}"
            for wid_b, eng_b, op_b in worker_engines:
                if wid_a != wid_b:
                    assert (
                        eng_b._get_operator(op_a) is None
                    ), f"worker_{wid_b} 引擎不应有 worker_{wid_a} 的操作符 {op_a}"


# ══════════════════════════════════════════════════════════
# 9. AssertItem 纯数据载体验证
# ══════════════════════════════════════════════════════════


class TestAssertItemPurity:
    """AssertItem 仅作为字段定义，不包含操作符映射逻辑"""

    def test_assert_item_is_dataclass(self):
        from dataclasses import is_dataclass

        assert is_dataclass(AssertItem)

    def test_assert_item_has_no_operator_mapping(self):
        """AssertItem 不应包含任何操作符映射属性"""
        item = AssertItem(path="test", expected=1)
        # 只包含数据字段
        expected_fields = {"path", "expected", "operator", "message", "ignore_case"}
        actual_fields = {f.name for f in item.__dataclass_fields__.values()}
        assert actual_fields == expected_fields
        # 没有 _operators 或类似字典
        for field_name in dir(item):
            assert (
                "operator" not in field_name.lower() or field_name == "operator"
            ), f"AssertItem 不应包含操作符映射属性，发现: {field_name}"


# ══════════════════════════════════════════════════════════
# 10. deepcopy 独立性验证
# ══════════════════════════════════════════════════════════


class TestDeepCopyIndependence:
    """验证实例操作符表是基于深拷贝的独立副本"""

    def test_modifying_instance_does_not_affect_default(self):
        engine = AssertionEngine()
        original_len = len(AssertionEngine.DEFAULT_OPERATORS)

        # 添加自定义操作符
        @engine.register_operator("extra_op")
        def extra_op(a, e):
            return True

        # 默认注册表不变
        assert len(AssertionEngine.DEFAULT_OPERATORS) == original_len
        assert "extra_op" not in AssertionEngine.DEFAULT_OPERATORS

    def test_deepcopy_creates_independent_dict(self):
        """验证 self._operators 是对字典的深拷贝，而非引用"""
        engine1 = AssertionEngine()
        engine2 = AssertionEngine()

        # 两个实例的 _operators 是不同的 dict 对象
        assert engine1._operators is not engine2._operators
        assert engine1._operators is not AssertionEngine.DEFAULT_OPERATORS

    def test_copy_deepcopy_used(self):
        """验证使用的是 copy.deepcopy 而非普通引用"""
        engine = AssertionEngine()
        # 验证 _operators 不是 MappingProxyType（即已被展开）
        assert not isinstance(engine._operators, MappingProxyType)
        assert isinstance(engine._operators, dict)

    def test_new_instance_has_all_defaults_eq_behavior(self):
        """新实例应有完整的默认操作符集合，且行为与默认一致"""
        engine = AssertionEngine()
        for op_name, default_func in AssertionEngine.DEFAULT_OPERATORS.items():
            instance_func = engine._get_operator(op_name)
            assert instance_func is not None
            # 函数引用可能不同（deepcopy），但名称一致
            assert instance_func.__name__ == default_func.__name__


# ══════════════════════════════════════════════════════════
# 11. AssertionReport 功能验证
# ══════════════════════════════════════════════════════════


class TestAssertionReport:
    def test_all_passed(self):
        results = [
            AssertResult(passed=True, path="a", expected=1, actual=1, operator="eq"),
            AssertResult(passed=True, path="b", expected=2, actual=2, operator="eq"),
        ]
        report = AssertionReport(results=results)
        assert report.passed is True
        assert report.pass_count == 2
        assert report.fail_count == 0

    def test_some_failed(self):
        results = [
            AssertResult(passed=True, path="a", expected=1, actual=1, operator="eq"),
            AssertResult(passed=False, path="b", expected=2, actual=3, operator="eq"),
        ]
        report = AssertionReport(results=results)
        assert report.passed is False
        assert report.pass_count == 1
        assert report.fail_count == 1

    def test_empty_results(self):
        report = AssertionReport(results=[])
        assert report.passed is True
        assert report.pass_count == 0
        assert report.fail_count == 0

    def test_summary_format(self):
        results = [
            AssertResult(passed=True, path="x", expected=1, actual=1, operator="eq"),
        ]
        report = AssertionReport(results=results)
        summary = report.summary()
        assert "断言" in summary
        assert "1 项" in summary
        assert "通过" in summary
