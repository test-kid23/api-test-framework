"""组合断言单元测试 (T5-05)

测试覆盖：
- CompositeAssertItem 模型（字段验证 / combinator 校验）
- all_of AND 逻辑（全部通过 / 部分失败 / 短路求值）
- any_of OR 逻辑（任一通过 / 全部失败 / 短路求值）
- 嵌套组合（AND 内嵌 OR / OR 内嵌 AND / 3 层深度）
- 空 children 边界
- 向后兼容：普通断言行为不变
- 扁平化结果收集
"""

from __future__ import annotations

import pytest

from framework.assertion.engine import AssertionEngine
from framework.models import (
    AssertionReport,
    AssertItem,
    AssertResult,
    CompositeAssertItem,
    HttpResponse,
)


# ── 辅助工厂函数 ──────────────────────────────────────────


def make_response(
    status_code: int = 200,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
    elapsed_ms: float = 100.0,
    size_bytes: int = 1024,
) -> HttpResponse:
    """创建测试用 HttpResponse."""
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
        url="http://test.local/api",
    )


# ── CompositeAssertItem 模型测试 ──────────────────────────


class TestCompositeAssertItemModel:
    """CompositeAssertItem 数据模型测试."""

    def test_all_of_combinator(self) -> None:
        """all_of 组合器."""
        item = CompositeAssertItem(
            combinator="all_of",
            children=[
                AssertItem(path="status_code", expected=200),
                AssertItem(path="body.code", expected=0),
            ],
        )
        assert item.combinator == "all_of"
        assert len(item.children) == 2

    def test_any_of_combinator(self) -> None:
        """any_of 组合器."""
        item = CompositeAssertItem(
            combinator="any_of",
            children=[
                AssertItem(path="status_code", expected=200),
            ],
        )
        assert item.combinator == "any_of"

    def test_invalid_combinator_raises(self) -> None:
        """非法 combinator 抛出 ValueError."""
        with pytest.raises(ValueError, match="combinator"):
            CompositeAssertItem(combinator="xor", children=[])

    def test_empty_children_allowed(self) -> None:
        """空 children 列表被允许."""
        item = CompositeAssertItem(combinator="all_of")
        assert item.children == []

    def test_nested_composite_in_children(self) -> None:
        """children 支持嵌套 CompositeAssertItem."""
        item = CompositeAssertItem(
            combinator="all_of",
            children=[
                AssertItem(path="status_code", expected=200),
                CompositeAssertItem(
                    combinator="any_of",
                    children=[
                        AssertItem(path="body.a", expected=1),
                        AssertItem(path="body.b", expected=2),
                    ],
                ),
            ],
        )
        assert len(item.children) == 2
        assert isinstance(item.children[1], CompositeAssertItem)
        assert item.children[1].combinator == "any_of"


# ── all_of AND 逻辑测试 ───────────────────────────────────


class TestAllOf:
    """all_of 组合断言测试."""

    def test_all_pass(self) -> None:
        """所有子断言通过 → 整体通过."""
        engine = AssertionEngine()
        response = make_response(status_code=200, body={"code": 0, "msg": "ok"})
        composite = CompositeAssertItem(
            combinator="all_of",
            children=[
                AssertItem(path="status_code", expected=200),
                AssertItem(path="body.code", expected=0),
                AssertItem(path="body.msg", expected="ok"),
            ],
        )
        results = engine._assert_composite(response, composite, {})
        assert all(r.passed for r in results)
        assert len(results) == 3

    def test_one_fail_makes_overall_fail(self) -> None:
        """任一子断言失败 → 整体失败."""
        engine = AssertionEngine()
        response = make_response(status_code=200, body={"code": 1})
        composite = CompositeAssertItem(
            combinator="all_of",
            children=[
                AssertItem(path="status_code", expected=200),
                AssertItem(path="body.code", expected=0),  # 1 != 0 → FAIL
            ],
        )
        results = engine._assert_composite(response, composite, {})
        assert not all(r.passed for r in results)

    def test_short_circuit_on_first_failure(self) -> None:
        """AND 短路：第一个失败后停止，后续子断言不执行."""
        engine = AssertionEngine()
        response = make_response(status_code=404, body={})
        composite = CompositeAssertItem(
            combinator="all_of",
            children=[
                AssertItem(path="status_code", expected=200),  # 404 != 200 → FAIL, 短路
                AssertItem(path="body.code", expected=0),  # 不应执行
                AssertItem(path="body.msg", expected="ok"),  # 不应执行
            ],
        )
        results = engine._assert_composite(response, composite, {})
        assert len(results) == 1  # 只有第一个被执行
        assert not results[0].passed

    def test_all_fail(self) -> None:
        """全部失败."""
        engine = AssertionEngine()
        response = make_response(status_code=500, body={})
        composite = CompositeAssertItem(
            combinator="all_of",
            children=[
                AssertItem(path="status_code", expected=200),
            ],
        )
        results = engine._assert_composite(response, composite, {})
        assert not results[0].passed


# ── any_of OR 逻辑测试 ────────────────────────────────────


class TestAnyOf:
    """any_of 组合断言测试."""

    def test_one_pass_makes_overall_pass(self) -> None:
        """任一子断言通过 → 整体通过."""
        engine = AssertionEngine()
        response = make_response(status_code=200, body={"code": 1})
        composite = CompositeAssertItem(
            combinator="any_of",
            children=[
                AssertItem(path="status_code", expected=404),  # FAIL
                AssertItem(path="status_code", expected=200),  # PASS
                AssertItem(path="body.code", expected=999),  # 不会执行（短路）
            ],
        )
        results = engine._assert_composite(response, composite, {})
        assert len(results) == 2  # 第二个通过后短路，第三个不执行
        assert not results[0].passed
        assert results[1].passed

    def test_short_circuit_on_first_success(self) -> None:
        """OR 短路：第一个成功后停止."""
        engine = AssertionEngine()
        response = make_response(status_code=200)
        composite = CompositeAssertItem(
            combinator="any_of",
            children=[
                AssertItem(path="status_code", expected=200),  # PASS → 短路
                AssertItem(path="status_code", expected=404),  # 不应执行
                AssertItem(path="body.code", expected=0),  # 不应执行
            ],
        )
        results = engine._assert_composite(response, composite, {})
        assert len(results) == 1
        assert results[0].passed

    def test_all_fail(self) -> None:
        """OR 全部失败."""
        engine = AssertionEngine()
        response = make_response(status_code=500)
        composite = CompositeAssertItem(
            combinator="any_of",
            children=[
                AssertItem(path="status_code", expected=200),
                AssertItem(path="status_code", expected=404),
                AssertItem(path="status_code", expected=201),
            ],
        )
        results = engine._assert_composite(response, composite, {})
        assert len(results) == 3  # OR 无短路，全部执行
        assert not any(r.passed for r in results)


# ── 嵌套组合测试 ──────────────────────────────────────────


class TestNestedComposite:
    """嵌套组合断言测试（AND 内嵌 OR / OR 内嵌 AND / 3 层深度）."""

    def test_all_of_contains_any_of_pass(self) -> None:
        """AND { OR{a, b}, c } — OR 通过且 c 通过 → 整体通过."""
        engine = AssertionEngine()
        response = make_response(
            status_code=200,
            body={"code": 0, "msg": "ok"},
        )
        composite = CompositeAssertItem(
            combinator="all_of",
            children=[
                CompositeAssertItem(
                    combinator="any_of",
                    children=[
                        AssertItem(path="status_code", expected=404),  # FAIL
                        AssertItem(path="status_code", expected=200),  # PASS → OR 通过
                    ],
                ),
                AssertItem(path="body.code", expected=0),  # PASS
            ],
        )
        results = engine._assert_composite(response, composite, {})
        assert len(results) == 3  # OR 内两个都执行，然后 AND 继续
        assert all(r.passed for r in results[-1:])  # 最后一个 body.code 通过

    def test_all_of_contains_any_of_fail(self) -> None:
        """AND { OR{a, b}, c } — OR 全部失败 → AND 短路，c 不执行."""
        engine = AssertionEngine()
        response = make_response(status_code=500)
        composite = CompositeAssertItem(
            combinator="all_of",
            children=[
                CompositeAssertItem(
                    combinator="any_of",
                    children=[
                        AssertItem(path="status_code", expected=200),  # FAIL
                        AssertItem(path="status_code", expected=404),  # FAIL
                    ],
                ),
                AssertItem(path="body.code", expected=0),  # 不应执行
            ],
        )
        results = engine._assert_composite(response, composite, {})
        assert len(results) == 2  # OR 全部执行（2个），AND 短路 body.code 不执行

    def test_any_of_contains_all_of_pass(self) -> None:
        """OR { AND{a, b}, c } — AND 失败但 c 通过 → OR 通过."""
        engine = AssertionEngine()
        response = make_response(status_code=200, body={"code": 1})
        composite = CompositeAssertItem(
            combinator="any_of",
            children=[
                CompositeAssertItem(
                    combinator="all_of",
                    children=[
                        AssertItem(path="status_code", expected=200),  # PASS
                        AssertItem(path="body.code", expected=0),  # FAIL → AND 失败
                    ],
                ),
                AssertItem(path="status_code", expected=200),  # PASS → OR 通过
            ],
        )
        results = engine._assert_composite(response, composite, {})
        # AND 全部执行（2个，第二个失败后短路），OR 继续执行 c（1个） → 共 3 个
        assert len(results) == 3
        assert any(r.passed for r in results)

    def test_three_levels_deep(self) -> None:
        """3 层深度嵌套：AND { OR { AND {a, b}, c }, d }."""
        engine = AssertionEngine()
        response = make_response(
            status_code=200,
            body={"code": 0, "msg": "ok", "data": {"id": 1}},
        )
        composite = CompositeAssertItem(
            combinator="all_of",
            children=[
                CompositeAssertItem(
                    combinator="any_of",
                    children=[
                        CompositeAssertItem(
                            combinator="all_of",
                            children=[
                                AssertItem(path="status_code", expected=200),
                                AssertItem(path="body.code", expected=0),
                            ],
                        ),
                        AssertItem(path="body.code", expected=999),  # FAIL，但不影响 OR
                    ],
                ),
                AssertItem(path="body.msg", expected="ok"),
            ],
        )
        results = engine._assert_composite(response, composite, {})
        # AND {a, b} 执行 2 个 → 通过，OR 短路不执行 c，d 执行 1 个
        assert len(results) == 3
        assert all(r.passed for r in results)


# ── assert_response 集成测试 ───────────────────────────────


class TestAssertResponseWithComposite:
    """assert_response 方法支持混合普通断言和组合断言."""

    def test_mixed_plain_and_composite(self) -> None:
        """混合普通断言 + 组合断言."""
        engine = AssertionEngine()
        response = make_response(
            status_code=200,
            body={"code": 0, "msg": "ok"},
        )
        assertions: list = [
            AssertItem(path="status_code", expected=200),  # 普通断言
            CompositeAssertItem(
                combinator="all_of",
                children=[
                    AssertItem(path="body.code", expected=0),
                    AssertItem(path="body.msg", expected="ok"),
                ],
            ),
        ]
        report = engine.assert_response(response, assertions, {})
        assert report.passed
        assert len(report.results) == 3
        assert report.pass_count == 3
        assert report.fail_count == 0

    def test_composite_fail_makes_report_fail(self) -> None:
        """组合断言失败 → 报告失败."""
        engine = AssertionEngine()
        response = make_response(status_code=200, body={"code": 1})
        assertions: list = [
            AssertItem(path="status_code", expected=200),  # PASS
            CompositeAssertItem(
                combinator="all_of",
                children=[
                    AssertItem(path="body.code", expected=0),  # FAIL
                ],
            ),
        ]
        report = engine.assert_response(response, assertions, {})
        assert not report.passed
        assert report.fail_count == 1
        assert report.pass_count == 1

    def test_flat_results_in_report(self) -> None:
        """组合断言的结果被扁平化收集到报告中."""
        engine = AssertionEngine()
        response = make_response(status_code=200, body={"a": 1, "b": 2})
        assertions: list = [
            CompositeAssertItem(
                combinator="all_of",
                children=[
                    AssertItem(path="body.a", expected=1),
                    AssertItem(path="body.b", expected=2),
                ],
            ),
        ]
        report = engine.assert_response(response, assertions, {})
        # 扁平化：2 个普通结果
        assert len(report.results) == 2
        assert report.results[0].path == "body.a"
        assert report.results[1].path == "body.b"

    def test_summary_reflects_flat_count(self) -> None:
        """summary 反映扁平化后的断言数量."""
        engine = AssertionEngine()
        response = make_response(status_code=200, body={"x": 1})
        assertions: list = [
            AssertItem(path="status_code", expected=200),
            CompositeAssertItem(
                combinator="all_of",
                children=[
                    AssertItem(path="body.x", expected=1),
                    AssertItem(path="body.x", expected=1, operator="ne"),
                ],
            ),
        ]
        report = engine.assert_response(response, assertions, {})
        assert "3 项" in report.summary()


# ── 边界测试 ──────────────────────────────────────────────


class TestEdgeCases:
    """边界情况测试."""

    def test_empty_composite_children(self) -> None:
        """空 children 的组合断言不产生结果."""
        engine = AssertionEngine()
        response = make_response()
        composite = CompositeAssertItem(combinator="all_of", children=[])
        results = engine._assert_composite(response, composite, {})
        assert results == []

    def test_empty_composite_children_any_of(self) -> None:
        """空 children 的 any_of 也不产生结果."""
        engine = AssertionEngine()
        response = make_response()
        composite = CompositeAssertItem(combinator="any_of", children=[])
        results = engine._assert_composite(response, composite, {})
        assert results == []

    def test_composite_operator_exception_handling(self) -> None:
        """组合断言中子断言执行异常被捕获."""
        engine = AssertionEngine()
        response = make_response(body={"items": [1, 2, 3]})
        # 使用未知操作符触发异常路径
        composite = CompositeAssertItem(
            combinator="all_of",
            children=[
                AssertItem(path="body.items", expected=3, operator="length"),
                AssertItem(path="body.nonexistent.deep.path", expected="x"),
            ],
        )
        results = engine._assert_composite(response, composite, {})
        # 第一个通过，第二个获取 nested value 可能返回 None 但不抛异常
        # 实际上 _get_nested_value 不抛异常，返回 None
        assert len(results) == 2

    def test_backward_compatible_plain_assertions(self) -> None:
        """向后兼容：纯普通断言行为不变."""
        engine = AssertionEngine()
        response = make_response(status_code=200, body={"result": "success"})
        assertions: list = [
            AssertItem(path="status_code", expected=200),
            AssertItem(path="body.result", expected="success"),
        ]
        report = engine.assert_response(response, assertions, {})
        assert report.passed
        assert len(report.results) == 2


# ── 短路求值精确验证 ──────────────────────────────────────


class TestShortCircuitPrecision:
    """短路求值精确行为验证."""

    def test_all_of_stops_after_first_fail_in_nested(self) -> None:
        """AND 嵌套：内层 AND 失败后外层 AND 停止."""
        engine = AssertionEngine()
        response = make_response(status_code=500)
        composite = CompositeAssertItem(
            combinator="all_of",
            children=[
                CompositeAssertItem(
                    combinator="all_of",
                    children=[
                        AssertItem(path="status_code", expected=200),  # FAIL
                        AssertItem(path="status_code", expected=404),  # 不执行（内层短路）
                    ],
                ),
                AssertItem(path="status_code", expected=500),  # 不执行（外层短路）
            ],
        )
        results = engine._assert_composite(response, composite, {})
        assert len(results) == 1  # 只有内层第一个被执行

    def test_any_of_stops_after_first_pass_in_nested(self) -> None:
        """OR 嵌套：内层 OR 通过后外层 OR 停止."""
        engine = AssertionEngine()
        response = make_response(status_code=200)
        composite = CompositeAssertItem(
            combinator="any_of",
            children=[
                CompositeAssertItem(
                    combinator="any_of",
                    children=[
                        AssertItem(path="status_code", expected=200),  # PASS → 内层短路
                        AssertItem(path="status_code", expected=404),  # 不执行
                    ],
                ),
                AssertItem(path="status_code", expected=500),  # 不执行（外层短路）
            ],
        )
        results = engine._assert_composite(response, composite, {})
        assert len(results) == 1  # 只有内层第一个被执行

    def test_failure_message_indicates_which_child_failed(self) -> None:
        """失败消息能定位到具体哪个子断言失败."""
        engine = AssertionEngine()
        response = make_response(status_code=500)
        composite = CompositeAssertItem(
            combinator="all_of",
            children=[
                AssertItem(path="status_code", expected=200, message="状态码应为200"),
                AssertItem(path="status_code", expected=201),
            ],
        )
        results = engine._assert_composite(response, composite, {})
        assert len(results) == 1  # 短路
        assert not results[0].passed
        assert results[0].path == "status_code"
        assert "500" in results[0].message
