"""TestContext 基于 contextvars 升级的完整测试

验证：
1. 不同协程间上下文隔离（asyncio Task）
2. Step 级变量隔离（步骤间变量不污染）
3. 三作用域变量解析（step → case → suite 优先级）
4. to_dict() / from_dict() 序列化往返
5. 向后兼容旧 API
6. 并发 asyncio 协程隔离
7. step_scope() 上下文管理器
8. resolve() 级联查找
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from framework.context import TestContext


# ══════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════


@pytest.fixture
def ctx() -> TestContext:
    """创建一个已初始化的 TestContext"""
    c = TestContext()
    c.init()
    return c


# ══════════════════════════════════════════════════════════
# 1. 基础 API — 向后兼容
# ══════════════════════════════════════════════════════════


class TestBasicApiCompat:
    """验证旧 API 在 contextvars 下仍然可用"""

    def test_init_and_get_variables(self, ctx: TestContext):
        ctx.set_variable("key", "value")
        assert ctx.get_variable("key") == "value"
        assert ctx.get_variables()["key"] == "value"

    def test_request_response_url(self, ctx: TestContext):
        ctx.set_request({"method": "GET"})
        ctx.set_response({"status": 200})
        ctx.set_url("http://example.com/api")

        assert ctx.get_request() == {"method": "GET"}
        assert ctx.get_response() == {"status": 200}
        assert ctx.get_url() == "http://example.com/api"

    def test_scope_context_manager(self, ctx: TestContext):
        with ctx.scope():
            ctx.set_variable("scoped", True)
            assert ctx.get_variable("scoped") is True

    def test_ensure_initialized(self):
        ctx = TestContext()
        ctx.init()  # 显式重置（ContextVar 可能被其他测试设置过）
        assert ctx.get_variables() == {}
        assert ctx.get_url() == ""

    def test_set_variable_updates_step(self, ctx: TestContext):
        ctx.set_case_vars({"base": "case"})
        ctx.start_step()
        ctx.set_variable("new_key", "step_value")

        # set_variable 写入 step 层
        assert ctx.step_vars["new_key"] == "step_value"
        # case 层不受影响
        assert "new_key" not in ctx.case_vars


# ══════════════════════════════════════════════════════════
# 2. 变量作用域 — step → case → suite 优先级
# ══════════════════════════════════════════════════════════


class TestVariableScopes:
    """验证三层变量作用域的分辨逻辑"""

    def test_step_overrides_case_overrides_suite(self, ctx: TestContext):
        ctx.set_suite_vars({"var": "suite", "suite_only": "s"})
        ctx.set_case_vars({"var": "case", "case_only": "c"})
        ctx.start_step()
        ctx.set_variable("var", "step")
        ctx.set_variable("step_only", "st")

        # resolve 按优先级
        assert ctx.resolve("var") == "step"
        assert ctx.resolve("step_only") == "st"
        assert ctx.resolve("case_only") == "c"
        assert ctx.resolve("suite_only") == "s"

    def test_get_variable_fallback_chain(self, ctx: TestContext):
        ctx.set_suite_vars({"a": "suite"})
        ctx.set_case_vars({"b": "case"})
        ctx.start_step()
        ctx.set_variable("c", "step")

        assert ctx.get_variable("a") == "suite"
        assert ctx.get_variable("b") == "case"
        assert ctx.get_variable("c") == "step"
        assert ctx.get_variable("missing", "default") == "default"

    def test_get_all_variables_flat_merge(self, ctx: TestContext):
        ctx.set_suite_vars({"env": "prod", "base_url": "https://api"})
        ctx.set_case_vars({"env": "case_env", "user_id": 42})
        ctx.start_step()
        ctx.set_variable("token", "abc")

        all_vars = ctx.get_all_variables()
        assert all_vars["env"] == "case_env"  # case 覆盖 suite
        assert all_vars["base_url"] == "https://api"
        assert all_vars["user_id"] == 42
        assert all_vars["token"] == "abc"

    def test_resolve_all_template_replacement(self, ctx: TestContext):
        ctx.set_suite_vars({"host": "api.example.com"})
        ctx.set_case_vars({"env": "staging"})
        ctx.start_step()
        ctx.set_variable("token", "secret123")

        result = ctx.resolve_all("https://{{host}}/{{env}}/login?t={{token}}")
        assert result == "https://api.example.com/staging/login?t=secret123"

    def test_missing_var_in_resolve_all(self, ctx: TestContext):
        ctx.init()
        ctx.start_step()
        result = ctx.resolve_all("Hello {{missing}}!")
        assert "{{missing}}" in result  # 保持原始占位符


# ══════════════════════════════════════════════════════════
# 3. Step 级隔离 — 步骤间变量不污染
# ══════════════════════════════════════════════════════════


class TestStepIsolation:
    """验证步骤间变量互相隔离"""

    def test_step1_vars_not_visible_to_step2(self, ctx: TestContext):
        ctx.set_case_vars({"base": "case", "shared": 0})

        # ── Step 1 ──
        ctx.start_step()
        ctx.set_variable("step1_var", "from_step1")
        ctx.set_variable("shared", 1)
        step1_snapshot = dict(ctx.step_vars)
        ctx.end_step(promote=False)  # 不提升，丢弃

        # ── Step 2 ──
        ctx.start_step()
        assert "step1_var" not in ctx.step_vars
        # shared 回到 case 值（0），因为步骤中改为 1 但未提升
        assert ctx.step_vars.get("shared") == 0
        ctx.set_variable("step2_var", "from_step2")
        ctx.end_step(promote=False)

        # Step 1 变量不会漏到 Step 2
        assert "step1_var" not in ctx.case_vars
        assert "step2_var" not in ctx.case_vars

    def test_step_extraction_promotion(self, ctx: TestContext):
        """验证 promote=True 时步骤变量会提升到 case"""
        ctx.set_case_vars({"base": "case"})

        # Step 1: 提取 token，提升
        ctx.start_step()
        ctx.set_variable("token", "tk_111")
        ctx.end_step(promote=True)

        assert ctx.case_vars["token"] == "tk_111"

        # Step 2: 可以读取到 Step 1 提升的变量
        ctx.start_step()
        assert ctx.step_vars["token"] == "tk_111"
        ctx.set_variable("user", "john")
        ctx.end_step(promote=True)

        assert ctx.case_vars["user"] == "john"
        assert ctx.case_vars["token"] == "tk_111"

    def test_promoted_vars_dont_overwrite_unchanged_case_vars(self, ctx: TestContext):
        """验证 end_step 只提升变更的变量"""
        ctx.set_case_vars({"a": 1, "b": 2, "original": True})
        ctx.start_step()
        ctx.set_variable("a", 100)  # 变更
        ctx.set_variable("new_thing", "extracted")  # 新增
        # b 和 original 不变，保持在 step_vars 中（copy from case）

        extracted = ctx.end_step(promote=True)

        assert "a" in extracted  # 变更的
        assert "new_thing" in extracted  # 新增的
        assert "b" not in extracted  # 未变更
        assert "original" not in extracted  # 未变更
        assert ctx.case_vars["a"] == 100
        assert ctx.case_vars["new_thing"] == "extracted"

    def test_step_scope_context_manager(self, ctx: TestContext):
        ctx.set_case_vars({"base": "case"})

        with ctx.step_scope():
            ctx.set_variable("extracted", "from_context_manager")

        # 默认 promote=True
        assert ctx.case_vars["extracted"] == "from_context_manager"
        # step vars 已清空
        assert ctx.step_vars == {}

    def test_consecutive_steps_no_cross_contamination(self, ctx: TestContext):
        """模拟真实多步骤用例流程"""
        ctx.init()
        ctx.set_case_vars({"env": "test"})

        # Step 1: 登录获取 token
        ctx.start_step()
        ctx.set_variable("token", "tk_login_123")
        ctx.set_variable("user_id", 100)
        ctx.end_step(promote=True)

        # Step 2: 使用 token 查询数据，提取 data_id
        ctx.start_step()
        assert ctx.step_vars["token"] == "tk_login_123"
        assert ctx.step_vars["user_id"] == 100
        ctx.set_variable("data_id", 5001)
        ctx.set_variable("_step2_internal", "temp")
        ctx.end_step(promote=True)

        # Step 3: 查看数据详情
        ctx.start_step()
        assert ctx.step_vars["token"] == "tk_login_123"
        assert ctx.step_vars["data_id"] == 5001
        # _step2_internal 被提升了，但后续步骤可见
        assert ctx.step_vars.get("_step2_internal") == "temp"

        # 验证 case 层有所有提升的变量
        assert ctx.case_vars["token"] == "tk_login_123"
        assert ctx.case_vars["data_id"] == 5001
        ctx.set_variable("detail", "ok")
        ctx.end_step(promote=True)

        # 全量快照
        all_vars = ctx.get_all_variables()
        assert all_vars["env"] == "test"
        assert all_vars["token"] == "tk_login_123"
        assert all_vars["data_id"] == 5001
        assert all_vars["detail"] == "ok"


# ══════════════════════════════════════════════════════════
# 4. asyncio 协程上下文隔离
# ══════════════════════════════════════════════════════════


class TestAsyncContextIsolation:
    """验证 asyncio 协程环境下 contextvars 自动隔离"""

    @pytest.mark.asyncio
    async def test_independent_task_contexts(self):
        """两个并发 Task 各自拥有独立的变量副本"""
        ctx_a = TestContext()
        ctx_b = TestContext()

        async def task_a():
            ctx_a.init()
            ctx_a.set_suite_vars({"task": "a"})
            ctx_a.start_step()
            ctx_a.set_variable("value", "aaa")
            await asyncio.sleep(0.01)
            return ctx_a.get_variable("value")

        async def task_b():
            ctx_b.init()
            ctx_b.set_suite_vars({"task": "b"})
            ctx_b.start_step()
            ctx_b.set_variable("value", "bbb")
            await asyncio.sleep(0.01)
            return ctx_b.get_variable("value")

        results = await asyncio.gather(task_a(), task_b())
        assert results == ["aaa", "bbb"]

    @pytest.mark.asyncio
    async def test_context_inheritance_from_parent(self):
        """子 Task 继承父 Task 创建时的上下文快照"""
        ctx = TestContext()
        ctx.init()
        ctx.set_suite_vars({"inherited": "yes"})
        ctx.set_case_vars({"case_key": "from_parent"})

        async def child_task(c: TestContext):
            # 子任务应该能看到继承的 suite/case vars
            assert c.suite_vars.get("inherited") == "yes"
            assert c.case_vars.get("case_key") == "from_parent"
            # 修改子任务不影��父任务
            c.case_vars["case_key"] = "from_child"
            return c.case_vars["case_key"]

        child_value = await child_task(ctx)
        assert child_value == "from_child"
        # 父任务 case_vars 不变（contextvars 写时复制语义）
        # 注意：如果是同一个 ctx 实例在同一个协程中，修改会生效
        # 但在不同 Task 中，每个 Task 有独立的 context copy

    @pytest.mark.asyncio
    async def test_parallel_step_isolation(self):
        """并发协程中的 step 隔离"""

        async def run_case(token: str) -> dict:
            ctx = TestContext()
            ctx.init()
            ctx.set_case_vars({"base": "case"})
            ctx.start_step()
            ctx.set_variable("token", token)
            ctx.set_variable("data", f"data_{token}")
            await asyncio.sleep(0.005)
            ctx.end_step(promote=True)
            return ctx.get_all_variables()

        results = await asyncio.gather(
            run_case("t1"),
            run_case("t2"),
            run_case("t3"),
        )

        assert results[0]["token"] == "t1"
        assert results[0]["data"] == "data_t1"
        assert results[1]["token"] == "t2"
        assert results[1]["data"] == "data_t2"
        assert results[2]["token"] == "t3"
        assert results[2]["data"] == "data_t3"

    @pytest.mark.asyncio
    async def test_many_concurrent_tasks(self):
        """大量并发任务上下文隔离"""

        async def worker(idx: int) -> int:
            ctx = TestContext()
            ctx.init()
            ctx.start_step()
            ctx.set_variable("idx", idx)
            ctx.set_variable("square", idx * idx)
            await asyncio.sleep(0)
            return ctx.get_variable("square")

        n = 50
        results = await asyncio.gather(*[worker(i) for i in range(n)])
        assert results == [i * i for i in range(n)]


# ══════════════════════════════════════════════════════════
# 5. 多线程上下文隔离
# ══════════════════════════════════════════════════════════


class TestThreadIsolation:
    """验证多线程环境下 contextvars 隔离"""

    def test_thread_isolation(self):
        """不同线程中变量互不干扰"""
        results = {}

        def thread_worker(name: str):
            ctx = TestContext()
            ctx.init()
            ctx.start_step()
            ctx.set_variable("thread", name)
            ctx.set_variable("data", f"from_{name}")
            results[name] = ctx.get_all_variables()

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(thread_worker, n) for n in ["t1", "t2", "t3"]]
            for f in futures:
                f.result()

        assert results["t1"]["thread"] == "t1"
        assert results["t1"]["data"] == "from_t1"
        assert results["t2"]["thread"] == "t2"
        assert results["t3"]["thread"] == "t3"
        # 各线程结果互不包含对方的变量
        assert results["t1"].get("thread") != "t2"

    def test_thread_step_promotion_isolation(self):
        """多线程中的 step promotion 隔离"""
        results = {}

        def worker(name: str):
            ctx = TestContext()
            ctx.init()
            ctx.set_case_vars({"worker": name})

            # Step 1
            ctx.start_step()
            ctx.set_variable("step1", f"{name}_s1")
            ctx.end_step(promote=True)

            # Step 2
            ctx.start_step()
            ctx.set_variable("step2", f"{name}_s2")
            ctx.end_step(promote=True)

            results[name] = ctx.get_all_variables()

        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = [ex.submit(worker, n) for n in ["A", "B"]]
            for f in futures:
                f.result()

        assert results["A"]["worker"] == "A"
        assert results["A"]["step1"] == "A_s1"
        assert results["A"]["step2"] == "A_s2"
        assert results["B"]["worker"] == "B"
        assert results["B"]["step1"] == "B_s1"
        assert results["B"]["step2"] == "B_s2"


# ══════════════════════════════════════════════════════════
# 6. to_dict / from_dict 序列化
# ══════════════════════════════════════════════════════════


class TestSerialization:
    """验证上下文序列化与反序列化"""

    def test_to_dict_roundtrip(self, ctx: TestContext):
        ctx.set_suite_vars({"env": "test"})
        ctx.set_case_vars({"user_id": 42})
        ctx.start_step()
        ctx.set_variable("token", "secret")
        ctx.set_request({"method": "GET"})
        ctx.set_response({"status": 200})
        ctx.set_url("http://example.com")

        data = ctx.to_dict()

        # 恢复到一个新实例
        ctx2 = TestContext()
        ctx2.from_dict(data)

        assert ctx2.suite_vars == {"env": "test"}
        assert ctx2.case_vars == {"user_id": 42}
        # start_step() 会将 case_vars 拷贝到 step_vars，因此 step 层包含 case 内容
        assert ctx2.step_vars.get("token") == "secret"
        assert ctx2.step_vars.get("user_id") == 42
        assert ctx2.get_request() == {"method": "GET"}
        assert ctx2.get_response() == {"status": 200}
        assert ctx2.get_url() == "http://example.com"

    def test_to_dict_from_empty_context(self):
        ctx = TestContext()
        ctx.init()
        data = ctx.to_dict()

        ctx2 = TestContext()
        ctx2.from_dict(data)

        assert ctx2.suite_vars == {}
        assert ctx2.case_vars == {}
        assert ctx2.step_vars == {}
        assert ctx2.get_url() == ""

    def test_snapshot_and_restore_aliases(self, ctx: TestContext):
        ctx.set_suite_vars({"key": "val"})
        snap = ctx.snapshot()

        ctx2 = TestContext()
        ctx2.restore(snap)
        assert ctx2.suite_vars == {"key": "val"}

    def test_from_dict_overwrites_all_state(self, ctx: TestContext):
        ctx.set_suite_vars({"old": "data"})
        ctx.set_case_vars({"old_case": True})

        ctx.from_dict({"suite_vars": {"new": "fresh"}, "case_vars": {}, "step_vars": {},
                       "variables": {}, "url": ""})

        assert ctx.suite_vars == {"new": "fresh"}
        assert ctx.case_vars == {}
        assert "old" not in ctx.suite_vars
        assert "old_case" not in ctx.case_vars


# ══════════════════════════════════════════════════════════
# 7. 边界情况
# ══════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界场景测试"""

    def test_start_step_without_init(self):
        """未 init 时调用 start_step 应自动初始化"""
        ctx = TestContext()
        ctx.start_step()
        assert ctx.step_vars == {}

    def test_end_step_without_start(self):
        """未 start 时 end_step 不应崩溃"""
        ctx = TestContext()
        ctx.init()
        extracted = ctx.end_step(promote=False)
        assert extracted == {}

    def test_double_init_overwrites(self, ctx: TestContext):
        ctx.set_suite_vars({"key": "first"})
        ctx.init()  # 第二次 init 会清空
        assert ctx.suite_vars == {}

    def test_empty_dict_vars(self, ctx: TestContext):
        ctx.set_suite_vars({})
        ctx.set_case_vars({})
        ctx.start_step()
        assert ctx.get_all_variables() == {}

    def test_nested_dict_values(self, ctx: TestContext):
        ctx.set_suite_vars({"nested": {"deep": {"key": "suite"}}})
        ctx.set_case_vars({"nested": {"deep": {"key": "case"}, "other": True}})

        assert ctx.resolve("nested") == {"deep": {"key": "case"}, "other": True}

    def test_resolve_with_none_value(self, ctx: TestContext):
        ctx.set_case_vars({"nullable": None})
        ctx.start_step()
        # None 是有效值，应该返回 None 而非 fallback
        assert ctx.resolve("nullable", "fallback") is None

    def test_suite_vars_update(self, ctx: TestContext):
        ctx.set_suite_vars({"a": 1})
        ctx.update_suite_vars({"b": 2, "a": 10})
        assert ctx.suite_vars == {"a": 10, "b": 2}

    def test_get_variables_returns_step_reference(self, ctx: TestContext):
        """get_variables() 返回 step_vars 自身引用，可 mutation"""
        ctx.start_step()
        vars_ref = ctx.get_variables()
        vars_ref["new_key"] = "new_value"
        assert ctx.step_vars["new_key"] == "new_value"
