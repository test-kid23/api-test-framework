"""协程安全的测试上下文 — 基于 contextvars 的三层作用域变量管理

升级要点：
- 从 threading.local 迁移到 contextvars.ContextVar
- 支持 asyncio 协程环境下的自动上下文隔离
- 三层变量作用域：suite → case → step（解析时 step 优先）
- Step 级上下文：每个步骤创建独立副本，步骤间变量不污染
- 支持序列化：to_dict() / from_dict()

变量作用域优先级（解析时）：
    step_vars > case_vars > suite_vars
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Any


class TestContext:
    """协程安全的测试上下文

    基于 contextvars 实现上下文隔离：
    - 每个 asyncio Task 或线程自动获得独立的变量副本
    - 变量按 suite / case / step 三层作用域组织
    - 步骤执行前后通过 start_step() / end_step() 管理隔离
    - 保持向后兼容旧版 get_variables / set_variable 等 API

    Usage::

        ctx = TestContext()
        ctx.init()
        ctx.set_suite_vars({"base_url": "https://api.example.com"})
        ctx.set_case_vars({"user_id": 123})
        ctx.start_step()
        ctx.set_variable("token", "abc")
        ctx.resolve("token")       # "abc"（来自 step）
        ctx.resolve("user_id")     # 123  （fallback 到 case）
        ctx.resolve("base_url")    # "..." （fallback 到 suite）
        ctx.end_step()
    """

    # ── ContextVar 定义（类级，每个执行上下文自动隔离）─────────

    _cv_variables: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
        "ctx_legacy_variables"
    )
    _cv_suite_vars: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
        "ctx_suite_vars"
    )
    _cv_case_vars: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
        "ctx_case_vars"
    )
    _cv_step_vars: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
        "ctx_step_vars"
    )
    _cv_request: contextvars.ContextVar[Any] = contextvars.ContextVar("ctx_request")
    _cv_response: contextvars.ContextVar[Any] = contextvars.ContextVar("ctx_response")
    _cv_assertion_report: contextvars.ContextVar[Any] = contextvars.ContextVar(
        "ctx_assertion_report"
    )
    _cv_url: contextvars.ContextVar[str] = contextvars.ContextVar("ctx_url")

    # ── 上下文生命周期 ──────────────────────────────────

    def init(self) -> None:
        """初始化当前执行上下文的全部变量槽位"""
        self._cv_variables.set({})
        self._cv_suite_vars.set({})
        self._cv_case_vars.set({})
        self._cv_step_vars.set({})
        self._cv_request.set(None)
        self._cv_response.set(None)
        self._cv_assertion_report.set(None)
        self._cv_url.set("")

    def ensure_initialized(self) -> None:
        """确保当前上下文已初始化（未初始化时自动 init）"""
        try:
            self._cv_variables.get()
        except LookupError:
            self.init()

    @contextmanager
    def scope(self):  # type: ignore[no-untyped-def]
        """创建新的上下文作用域（兼容旧 API）"""
        self.init()
        try:
            yield self
        finally:
            pass

    # ── 三层变量作用域 ─────────────────────────────────

    @property
    def suite_vars(self) -> dict[str, Any]:
        """套件级变量 — 跨用例共享，存 base_url / env 等全局配置"""
        self.ensure_initialized()
        return self._cv_suite_vars.get()

    def set_suite_vars(self, variables: dict[str, Any]) -> None:
        """批量设置套件级变量（覆盖已有）"""
        self.ensure_initialized()
        self._cv_suite_vars.set(dict(variables))

    def update_suite_vars(self, variables: dict[str, Any]) -> None:
        """增量更新套件级变量"""
        self.suite_vars.update(variables)

    @property
    def case_vars(self) -> dict[str, Any]:
        """用例级变量 — 跨步骤共享"""
        self.ensure_initialized()
        return self._cv_case_vars.get()

    def set_case_vars(self, variables: dict[str, Any]) -> None:
        """批量设置用例级变量"""
        self.ensure_initialized()
        self._cv_case_vars.set(dict(variables))

    @property
    def step_vars(self) -> dict[str, Any]:
        """步骤级变量 — 当前步骤独有（最高优先级）"""
        self.ensure_initialized()
        return self._cv_step_vars.get()

    # ── Step 生命周期管理 ──────────────────────────────

    def start_step(self) -> None:
        """开始新步骤：以当前 case_vars 为基准创建隔离副本

        调用后 step_vars 是 case_vars 的独立拷贝，步骤内写入不会
        直接污染 case_vars。
        """
        self.ensure_initialized()
        case = self._cv_case_vars.get()
        self._cv_step_vars.set(dict(case))

    def end_step(self, promote: bool = True) -> dict[str, Any]:
        """结束当前步骤

        Args:
            promote: True 时将步骤提取的新变量合并到 case_vars，
                     用于跨步骤传递；False 时丢弃步骤变量。

        Returns:
            步骤中新增/变更的变量字典。
        """
        self.ensure_initialized()
        step = self._cv_step_vars.get()
        case = dict(self._cv_case_vars.get())

        # 计算步骤引入的新增/变更变量
        extracted: dict[str, Any] = {}
        for k, v in step.items():
            if k not in case or case.get(k) != v:
                extracted[k] = v

        if promote:
            case.update(extracted)
            self._cv_case_vars.set(case)

        # 清空步骤作用域
        self._cv_step_vars.set({})
        return extracted

    @contextmanager
    def step_scope(self):  # type: ignore[no-untyped-def]
        """步骤上下文管理器 — 自动 start_step / end_step"""
        self.start_step()
        try:
            yield
        finally:
            self.end_step()

    # ── 变量读写 API（向后兼容）─────────────────────────

    def get_variables(self) -> dict[str, Any]:
        """返回步骤级变量字典（兼容旧版 API）

        注意：返回的是 step_vars 自身的引用，在步骤内对其调用
        .update() 或 [] 赋值会直接作用于 step 作用域，天然隔离。

        若需要读取完整合并视图，请使用 get_all_variables()。
        """
        self.ensure_initialized()
        return self._cv_step_vars.get()

    def get_all_variables(self) -> dict[str, Any]:
        """返回所有作用域合并后的变量快照（只读视角）

        合并顺序：suite → case → step（后者覆盖前者）
        """
        result: dict[str, Any] = {}
        result.update(self.suite_vars)
        result.update(self.case_vars)
        result.update(self.step_vars)
        return result

    def set_variable(self, key: str, value: Any) -> None:
        """设置变量到步骤层"""
        self.get_variables()[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        """按 step → case → suite 优先级查找变量"""
        step = self.step_vars
        if key in step:
            return step[key]
        case = self.case_vars
        if key in case:
            return case[key]
        suite = self.suite_vars
        if key in suite:
            return suite[key]
        return default

    def resolve(self, key: str, default: Any = None) -> Any:
        """别名：按 step → case → suite 优先级解析变量"""
        return self.get_variable(key, default)

    def resolve_all(self, template: str) -> str:
        """对模板字符串进行变量替换（简易版 {{var}} 语法）

        在当前作用域中查找变量并替换，支持级联查找。
        """
        import re

        def _replacer(match: re.Match[str]) -> str:
            var_name = match.group(1)
            return str(self.resolve(var_name, match.group(0)))

        return re.sub(r"\{\{(\w+)\}\}", _replacer, template)

    # ── 请求 / 响应 存取 ──────────────────────────────

    def set_request(self, request: Any) -> None:
        self.ensure_initialized()
        self._cv_request.set(request)

    def get_request(self) -> Any:
        self.ensure_initialized()
        return self._cv_request.get()

    def set_response(self, response: Any) -> None:
        self.ensure_initialized()
        self._cv_response.set(response)

    def get_response(self) -> Any:
        self.ensure_initialized()
        return self._cv_response.get()

    def set_url(self, url: str) -> None:
        self.ensure_initialized()
        self._cv_url.set(url)

    def get_url(self) -> str:
        self.ensure_initialized()
        return self._cv_url.get()  # type: ignore[no-any-return]

    def set_assertion_report(self, report: Any) -> None:
        self.ensure_initialized()
        self._cv_assertion_report.set(report)

    def get_assertion_report(self) -> Any:
        self.ensure_initialized()
        return self._cv_assertion_report.get()

    # ── 序列化 ───────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """将当前上下文序列化为可传输 / 持久化的字典"""
        self.ensure_initialized()
        return {
            "variables": dict(self._cv_variables.get()),
            "suite_vars": dict(self.suite_vars),
            "case_vars": dict(self.case_vars),
            "step_vars": dict(self.step_vars),
            "request": self._cv_request.get(),
            "response": self._cv_response.get(),
            "assertion_report": self._cv_assertion_report.get(),
            "url": self._cv_url.get(),
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """从字典恢复上下文状态"""
        self.init()
        self._cv_variables.set(dict(data.get("variables", {})))
        self._cv_suite_vars.set(dict(data.get("suite_vars", {})))
        self._cv_case_vars.set(dict(data.get("case_vars", {})))
        self._cv_step_vars.set(dict(data.get("step_vars", {})))
        self._cv_request.set(data.get("request"))
        self._cv_response.set(data.get("response"))
        self._cv_assertion_report.set(data.get("assertion_report"))
        self._cv_url.set(data.get("url", ""))

    # ── 上下文快照 ──────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """创建当前上下文的深拷贝快照（别名，等价于 to_dict）"""
        return self.to_dict()

    def restore(self, snapshot: dict[str, Any]) -> None:
        """从快照恢复上下文（别名，等价于 from_dict）"""
        self.from_dict(snapshot)
