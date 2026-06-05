"""TestRunner 策略模式测试

验证：
1. HTTP TestCase 能正确路由到 HttpStepExecutor
2. WebSocket TestCase 能正确路由到 WsStepExecutor
3. 无匹配 executor 时抛出 NoExecutorFoundError
4. 默认 executor 列表包含 HTTP 和 WS 执行器
5. 自定义 executor 注册和优先级
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from framework.context import TestContext
from framework.exceptions import NoExecutorFoundError
from framework.executors.base import StepExecutor
from framework.executors.http_executor import HttpStepExecutor
from framework.executors.ws_async_executor import AsyncWsStepExecutor
from framework.models import (
    CaseResult,
    EnvConfig,
    HttpMethod,
    HttpRequest,
    ProjectConfig,
    TestCase,
    WSConfig,
)
from framework.runner import TestRunner

# ══════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════


@pytest.fixture
def project_config() -> ProjectConfig:
    return ProjectConfig(project_name="test")


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
# 辅助工厂函数
# ══════════════════════════════════════════════════════════


def make_http_case(**kwargs) -> TestCase:
    """创建标准 HTTP TestCase"""
    defaults = {
        "name": "test_http",
        "request": HttpRequest(method=HttpMethod.GET, path="/api/test"),
    }
    defaults.update(kwargs)
    return TestCase(**defaults)


def make_ws_case(**kwargs) -> TestCase:
    """创建 WebSocket TestCase"""
    defaults = {
        "name": "test_ws",
        "ws_config": WSConfig(url="ws://localhost/ws"),
    }
    defaults.update(kwargs)
    return TestCase(**defaults)


def make_empty_case(**kwargs) -> TestCase:
    """创建无 request/ws_config 的空 TestCase"""
    defaults = {"name": "test_empty"}
    defaults.update(kwargs)
    return TestCase(**defaults)


# ══════════════════════════════════════════════════════════
# 1. 默认 executor 列表
# ══════════════════════════════════════════════════════════


class TestDefaultExecutors:
    """验证 TestRunner 默认注册了 WS(Async) 和 HTTP 执行器"""

    def test_default_executors_include_ws_and_http(
        self, project_config, env_config, http_client, test_context
    ):
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
        )
        assert len(runner._executors) == 2
        assert isinstance(runner._executors[0], AsyncWsStepExecutor)
        assert isinstance(runner._executors[1], HttpStepExecutor)

    def test_ws_executor_has_priority_over_http(
        self, project_config, env_config, http_client, test_context
    ):
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
        )
        # WS executor 应在 HTTP executor 之前（优先级更高）
        assert isinstance(runner._executors[0], AsyncWsStepExecutor)
        assert isinstance(runner._executors[1], HttpStepExecutor)


# ══════════════════════════════════════════════════════════
# 2. HTTP 用例路由
# ══════════════════════════════════════════════════════════


class TestHttpRouting:
    """验证 HTTP TestCase 路由到 HttpStepExecutor"""

    def test_supports_http_case(self):
        http_exec = HttpStepExecutor(
            http_client=MagicMock(),
            template_engine=MagicMock(),
            assertion_engine=MagicMock(),
            extractor=MagicMock(),
            report_adapter=MagicMock(),
            env=EnvConfig(name="test"),
        )
        case = make_http_case()
        assert http_exec.supports(case) is True

    def test_does_not_support_ws_case(self):
        http_exec = HttpStepExecutor(
            http_client=MagicMock(),
            template_engine=MagicMock(),
            assertion_engine=MagicMock(),
            extractor=MagicMock(),
            report_adapter=MagicMock(),
            env=EnvConfig(name="test"),
        )
        case = make_ws_case()
        assert http_exec.supports(case) is False

    def test_does_not_support_empty_case(self):
        http_exec = HttpStepExecutor(
            http_client=MagicMock(),
            template_engine=MagicMock(),
            assertion_engine=MagicMock(),
            extractor=MagicMock(),
            report_adapter=MagicMock(),
            env=EnvConfig(name="test"),
        )
        case = make_empty_case()
        assert http_exec.supports(case) is False


# ══════════════════════════════════════════════════════════
# 3. WebSocket 用例路由
# ══════════════════════════════════════════════════════════


class TestWsRouting:
    """验证 WebSocket TestCase 路由到 AsyncWsStepExecutor"""

    def test_supports_ws_case(self):
        ws_exec = AsyncWsStepExecutor(template_engine=MagicMock())
        case = make_ws_case()
        assert ws_exec.supports(case) is True

    def test_does_not_support_http_case(self):
        ws_exec = AsyncWsStepExecutor(template_engine=MagicMock())
        case = make_http_case()
        assert ws_exec.supports(case) is False

    def test_does_not_support_empty_case(self):
        ws_exec = AsyncWsStepExecutor(template_engine=MagicMock())
        case = make_empty_case()
        assert ws_exec.supports(case) is False


# ══════════════════════════════════════════════════════════
# 4. NoExecutorFoundError 异常
# ══════════════════════════════════════════════════════════


class TestNoExecutorFound:
    """验证无匹配 executor 时抛出异常"""

    def test_raises_when_no_executor_matches(self, runner):
        case = make_empty_case()
        with pytest.raises(NoExecutorFoundError) as exc_info:
            runner.run_case(case, {})
        assert "test_empty" in str(exc_info.value)
        assert exc_info.value.case_name == "test_empty"

    def test_raises_with_custom_executors_empty_list(
        self, project_config, env_config, http_client, test_context
    ):
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[],
        )
        case = make_http_case()
        with pytest.raises(NoExecutorFoundError):
            runner.run_case(case, {})

    def test_exception_is_execution_error(self):
        """NoExecutorFoundError 应继承 ExecutionError"""
        from framework.exceptions import ExecutionError

        assert issubclass(NoExecutorFoundError, ExecutionError)


# ══════════════════════════════════════════════════════════
# 5. Mock executor 策略路由
# ══════════════════════════════════════════════════════════


class MockExecutor(StepExecutor):
    """测试用 Mock executor"""

    def __init__(self, supported: bool = True, result: CaseResult | None = None):
        self._supported = supported
        self._result = result or CaseResult(case_name="mock", passed=True)
        self.execute_called = False
        self.last_case = None

    def supports(self, case: TestCase) -> bool:
        return self._supported

    def execute(
        self,
        case: TestCase,
        context: TestContext,
        variables: dict,
    ) -> CaseResult:
        self.execute_called = True
        self.last_case = case
        return self._result


class TestStrategyRouting:
    """验证策略路由核心逻辑"""

    def test_routes_to_matching_executor(
        self, project_config, env_config, http_client, test_context
    ):
        """给定一个匹配的 mock executor，run_case 应调用其 execute"""
        mock = MockExecutor(supported=True)
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[mock],
        )
        case = make_http_case()
        result = runner.run_case(case, {})

        assert mock.execute_called is True
        assert mock.last_case is case
        assert result.passed is True

    def test_falls_back_to_no_executor(self, project_config, env_config, http_client, test_context):
        """多个不匹配的 executor 时，应抛出 NoExecutorFoundError"""
        mock1 = MockExecutor(supported=False)
        mock2 = MockExecutor(supported=False)
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[mock1, mock2],
        )
        case = make_http_case()

        with pytest.raises(NoExecutorFoundError):
            runner.run_case(case, {})

    def test_first_matching_executor_selected(
        self, project_config, env_config, http_client, test_context
    ):
        """多个 executor 都匹配时，应选择第一个"""
        mock1 = MockExecutor(supported=True, result=CaseResult(case_name="first", passed=True))
        mock2 = MockExecutor(supported=True, result=CaseResult(case_name="second", passed=False))
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[mock1, mock2],
        )
        case = make_http_case()
        result = runner.run_case(case, {})

        assert mock1.execute_called is True
        assert mock2.execute_called is False
        assert result.case_name == "first"

    def test_skipped_case_bypasses_executors(
        self, project_config, env_config, http_client, test_context
    ):
        """skip=True 的用例不应调用任何 executor"""
        mock = MockExecutor(supported=True)
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[mock],
        )
        case = make_http_case(skip=True)
        result = runner.run_case(case, {})

        assert mock.execute_called is False
        assert result.passed is True
        assert result.error == "SKIPPED"


# ══════════════════════════════════════════════════════════
# 6. 自定义 executor 扩展
# ══════════════════════════════════════════════════════════


class TestCustomExecutor:
    """验证自定义 executor 注册（模拟 gRPC 扩展场景）"""

    def test_custom_executor_injection(self, project_config, env_config, http_client, test_context):
        """注入自定义 executor 可通过 supports 匹配并执行"""
        custom = MockExecutor(supported=True, result=CaseResult(case_name="custom", passed=True))
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[custom],
        )
        case = make_empty_case()
        result = runner.run_case(case, {})

        assert custom.execute_called is True
        assert result.case_name == "custom"
        assert result.passed is True

    def test_custom_executor_combined_with_defaults(
        self, project_config, env_config, http_client, test_context
    ):
        """自定义 executor 可与默认 executor 共存"""
        custom = MockExecutor(supported=False)  # 不匹配，fallback 到默认
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[custom],  # 不提供默认 executor，只注入 custom
        )
        # 用例是空的，custom 不匹配，应抛出异常
        case = make_empty_case()
        with pytest.raises(NoExecutorFoundError):
            runner.run_case(case, {})

    def test_executor_order_determines_priority(
        self, project_config, env_config, http_client, test_context
    ):
        """executor 列表顺序决定匹配优先级"""
        mock_first = MockExecutor(supported=True, result=CaseResult(case_name="first", passed=True))
        mock_second = MockExecutor(
            supported=True, result=CaseResult(case_name="second", passed=True)
        )
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            context=test_context,
            executors=[mock_first, mock_second],
        )
        case = make_http_case()
        result = runner.run_case(case, {})

        assert mock_first.execute_called is True
        assert mock_second.execute_called is False
        assert result.case_name == "first"
