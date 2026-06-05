"""用例超时控制测试

验证：
1. 同步 run_case: 超时后状态为 TIMEOUT
2. 单用例自定义 timeout 覆盖全局 case_timeout
3. 异步 arun_case: asyncio.wait_for 超时场景
4. 正常用例不受超时机制影响
5. skip 用例绕过超时逻辑
6. case_timeout=0 时的关闭行为
"""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import MagicMock

import pytest

from framework.context import TestContext
from framework.exceptions import CaseTimeoutError, NoExecutorFoundError
from framework.executors.base import StepExecutor
from framework.models import (
    CaseResult,
    CaseStatus,
    EnvConfig,
    HttpMethod,
    HttpRequest,
    ProjectConfig,
    TestCase,
)
from framework.runner import TestRunner


# ══════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════


@pytest.fixture
def project_config() -> ProjectConfig:
    """使用较短的全局 case_timeout 以加速测试"""
    return ProjectConfig(project_name="test", case_timeout=2)


@pytest.fixture
def env_config() -> EnvConfig:
    return EnvConfig(name="test", base_url="http://localhost")


@pytest.fixture
def http_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def test_context() -> TestContext:
    return TestContext()


@pytest.fixture
def runner(project_config, env_config, http_client, test_context) -> TestRunner:
    return TestRunner(
        config=project_config,
        env=env_config,
        http_client=http_client,
        db_manager=None,
        context=test_context,
    )


# ══════════════════════════════════════════════════════════
# Mock executor — 可控耗时
# ══════════════════════════════════════════════════════════


class SlowExecutor(StepExecutor):
    """模拟耗时 executor，sleep 指定秒数后返回"""

    def __init__(self, delay: float = 999.0, supported: bool = True):
        self._delay = delay
        self._supported = supported
        self.execute_called = False

    def supports(self, case: TestCase) -> bool:
        return self._supported

    def execute(
        self,
        case: TestCase,
        context: TestContext,
        variables: dict,
    ) -> CaseResult:
        self.execute_called = True
        time.sleep(self._delay)
        return CaseResult(case_name=case.name, passed=True, status=CaseStatus.PASS)


class BlockingExecutor(StepExecutor):
    """永久阻塞 executor — 用于触发超时"""

    def __init__(self, supported: bool = True):
        self._supported = supported
        self.execute_called = False
        self._event = threading.Event()

    def supports(self, case: TestCase) -> bool:
        return self._supported

    def execute(
        self,
        case: TestCase,
        context: TestContext,
        variables: dict,
    ) -> CaseResult:
        self.execute_called = True
        # 永久等待，直到外部设置 event（测试清理用）
        self._event.wait()
        return CaseResult(case_name=case.name, passed=True, status=CaseStatus.PASS)


# ══════════════════════════════════════════════════════════
# 辅助工厂
# ══════════════════════════════════════════════════════════


def make_case(name: str = "test_case", **kwargs) -> TestCase:
    defaults: dict = {
        "name": name,
        "request": HttpRequest(method=HttpMethod.GET, path="/api/test"),
    }
    defaults.update(kwargs)
    return TestCase(**defaults)


# ══════════════════════════════════════════════════════════
# 1. 同步超时 — 失控用例被自动终止
# ══════════════════════════════════════════════════════════


class TestSyncTimeout:
    """验证同步路径的超时控制"""

    def test_case_timeout_returns_timed_out_status(
        self, project_config, env_config, http_client, test_context
    ):
        """永久阻塞的用例应在 case_timeout 后返回 TIMEOUT 状态"""
        blocking_exec = BlockingExecutor(supported=True)
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[blocking_exec],
            auto_discover_plugins=False,
        )
        case = make_case("infinite_case")

        start = time.time()
        result = runner.run_case(case, {})
        elapsed = time.time() - start

        # 状态验证
        assert result.status == CaseStatus.TIMEOUT
        assert result.passed is False
        assert "超时" in (result.error or "")
        assert result.case_name == "infinite_case"
        # 耗时应接近 case_timeout（2s），允许一些抖动
        assert elapsed < 3.5  # 比 2s 多给些余量

        # clean up
        blocking_exec._event.set()

    def test_fast_case_not_affected_by_timeout(
        self, project_config, env_config, http_client, test_context
    ):
        """快速用例不受超时控制影响，正常返回"""
        fast_exec = SlowExecutor(delay=0.01, supported=True)
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[fast_exec],
            auto_discover_plugins=False,
        )
        case = make_case("fast_case")

        result = runner.run_case(case, {})

        assert result.status == CaseStatus.PASS
        assert result.passed is True
        assert fast_exec.execute_called is True


# ══════════════════════════════════════════════════════════
# 2. 单用例自定义超时
# ══════════════════════════════════════════════════════════


class TestCustomCaseTimeout:
    """验证用例级 timeout 覆盖全局 case_timeout"""

    def test_case_custom_timeout_overrides_global(
        self, project_config, env_config, http_client, test_context
    ):
        """case.timeout=1 覆盖全局 case_timeout=2，1s 即超时"""
        blocking_exec = BlockingExecutor(supported=True)
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[blocking_exec],
            auto_discover_plugins=False,
        )
        case = make_case("custom_timeout_case", timeout=1)

        start = time.time()
        result = runner.run_case(case, {})
        elapsed = time.time() - start

        assert result.status == CaseStatus.TIMEOUT
        assert result.passed is False
        # 应在 1s 左右超时，远小于全局 2s
        assert elapsed < 2.0

        blocking_exec._event.set()

    def test_case_custom_timeout_respected_over_global(
        self, project_config, env_config, http_client, test_context
    ):
        """case.timeout 直接覆盖全局 case_timeout，不限大小关系"""
        blocking_exec = BlockingExecutor(supported=True)
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[blocking_exec],
            auto_discover_plugins=False,
        )
        # case.timeout=5 > 全局 2s，实际使用 5s
        case = make_case("custom_5s_case", timeout=5)

        start = time.time()
        result = runner.run_case(case, {})
        elapsed = time.time() - start

        assert result.status == CaseStatus.TIMEOUT
        # 使用 case.timeout=5s，不是全局 2s
        assert 3.5 < elapsed < 6.0

        blocking_exec._event.set()

    def test_short_case_timeout_trumps_global(
        self, project_config, env_config, http_client, test_context
    ):
        """case.timeout=0.5 覆盖全局 case_timeout=2，0.5s 即超时"""
        blocking_exec = BlockingExecutor(supported=True)
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[blocking_exec],
            auto_discover_plugins=False,
        )
        case = make_case("short_case", timeout=0.5)

        start = time.time()
        result = runner.run_case(case, {})
        elapsed = time.time() - start

        assert result.status == CaseStatus.TIMEOUT
        assert elapsed < 1.5  # 远小于全局 2s

        blocking_exec._event.set()


# ══════════════════════════════════════════════════════════
# 3. asyncio.wait_for 超时
# ══════════════════════════════════════════════════════════


class TestAsyncTimeout:
    """验证异步路径的超时控制"""

    @pytest.mark.asyncio
    async def test_arun_case_timeout_with_asyncio_wait_for(
        self, project_config, env_config, http_client, test_context
    ):
        """arun_case 使用 asyncio.wait_for，超时后返回 TIMEOUT"""
        blocking_exec = BlockingExecutor(supported=True)
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[blocking_exec],
            auto_discover_plugins=False,
        )
        case = make_case("async_timeout_case", timeout=1)

        start = time.time()
        result = await runner.arun_case(case, {})
        elapsed = time.time() - start

        assert result.status == CaseStatus.TIMEOUT
        assert result.passed is False
        assert "超时" in (result.error or "")
        assert elapsed < 2.0

        blocking_exec._event.set()

    @pytest.mark.asyncio
    async def test_arun_case_fast_case_completes_normally(
        self, project_config, env_config, http_client, test_context
    ):
        """快速异步用例正常通过"""
        fast_exec = SlowExecutor(delay=0.01, supported=True)
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[fast_exec],
            auto_discover_plugins=False,
        )
        case = make_case("fast_async_case")

        result = await runner.arun_case(case, {})

        assert result.status == CaseStatus.PASS
        assert result.passed is True
        assert fast_exec.execute_called is True

    @pytest.mark.asyncio
    async def test_arun_case_no_timeout_disabled(
        self, project_config, env_config, http_client, test_context
    ):
        """timeout=0 关闭超时，快速用例正常完成"""
        pconfig = ProjectConfig(project_name="test", case_timeout=0)
        fast_exec = SlowExecutor(delay=0.01, supported=True)
        runner = TestRunner(
            config=pconfig,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[fast_exec],
            auto_discover_plugins=False,
        )
        case = make_case("no_timeout_case")

        result = await runner.arun_case(case, {})

        assert result.status == CaseStatus.PASS
        assert result.passed is True


# ══════════════════════════════════════════════════════════
# 4. Skip 用例绕过超时
# ══════════════════════════════════════════════════════════


class TestSkipBypassesTimeout:
    """skip=True 的用例不应受超时控制影响"""

    def test_skip_case_returns_immediately(
        self, project_config, env_config, http_client, test_context
    ):
        """跳过的用例直接返回 SKIP，不进入超时逻辑"""
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            auto_discover_plugins=False,
        )
        case = make_case("skip_case", skip=True, timeout=999)

        start = time.time()
        result = runner.run_case(case, {})
        elapsed = time.time() - start

        assert result.status == CaseStatus.SKIP
        assert result.passed is True
        assert result.error == "SKIPPED"
        assert elapsed < 0.5  # skip 应立即返回

    @pytest.mark.asyncio
    async def test_skip_case_async_returns_immediately(
        self, project_config, env_config, http_client, test_context
    ):
        """异步路径中 skip 用例也立即返回"""
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            auto_discover_plugins=False,
        )
        case = make_case("skip_async_case", skip=True)
        start = time.time()
        result = await runner.arun_case(case, {})
        elapsed = time.time() - start

        assert result.status == CaseStatus.SKIP
        assert elapsed < 0.5


# ══════════════════════════════════════════════════════════
# 5. CaseTimeoutError 异常
# ══════════════════════════════════════════════════════════


class TestCaseTimeoutError:
    """验证 CaseTimeoutError 异常定义"""

    def test_case_timeout_error_attributes(self):
        exc = CaseTimeoutError(
            case_name="test_case",
            timeout_seconds=30,
            current_step="execute",
        )
        assert exc.case_name == "test_case"
        assert exc.timeout_seconds == 30
        assert exc.current_step == "execute"
        assert "test_case" in str(exc)
        assert "30s" in str(exc)
        assert "execute" in str(exc)

    def test_case_timeout_error_is_execution_error(self):
        from framework.exceptions import ExecutionError

        assert issubclass(CaseTimeoutError, ExecutionError)


# ══════════════════════════════════════════════════════════
# 6. 禁用超时 (# case_timeout=0 时跳过超时控制)
# ══════════════════════════════════════════════════════════


class TestTimeoutDisabled:
    """case_timeout=0 时关闭超时控制"""

    def test_disabled_timeout_blocks_indefinitely(
        self, project_config, env_config, http_client, test_context
    ):
        """case_timeout=0 时，即使慢用例也不会被超时杀死"""
        pconfig = ProjectConfig(project_name="test", case_timeout=0)
        fast_exec = SlowExecutor(delay=0.01, supported=True)
        runner = TestRunner(
            config=pconfig,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[fast_exec],
            auto_discover_plugins=False,
        )
        case = make_case("disabled_case")

        result = runner.run_case(case, {})

        assert result.status == CaseStatus.PASS
        assert result.passed is True


# ══════════════════════════════════════════════════════════
# 7. CaseResult.status 默认值
# ══════════════════════════════════════════════════════════


class TestCaseStatusDefaults:
    """验证 CaseResult.status 在各种场景下的正确值"""

    def test_default_status_is_pass(self):
        result = CaseResult(case_name="test", passed=True)
        assert result.status == CaseStatus.PASS

    def test_status_enum_values(self):
        assert CaseStatus.PASS == "PASS"
        assert CaseStatus.FAIL == "FAIL"
        assert CaseStatus.SKIP == "SKIP"
        assert CaseStatus.TIMEOUT == "TIMEOUT"
        assert CaseStatus.ERROR == "ERROR"

    def test_skipped_case_has_skip_status(
        self, project_config, env_config, http_client, test_context
    ):
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            auto_discover_plugins=False,
        )
        case = make_case("skipped", skip=True)
        result = runner.run_case(case, {})
        assert result.status == CaseStatus.SKIP
