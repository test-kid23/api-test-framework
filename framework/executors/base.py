"""StepExecutor 抽象基类 — 策略模式核心接口

所有协议执行器必须继承 StepExecutor 并实现 supports / execute。
新增协议（如 gRPC）只需新建一个子类文件并注册到 TestRunner 即可，
不需要修改 runner.py。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from framework.context import TestContext
from framework.models import CaseResult, TestCase


class StepExecutor(ABC):
    """协议执行器抽象基类

    职责：判断是否支持某个 TestCase，并执行该用例的核心协议逻辑。

    Usage:
        class GrpcStepExecutor(StepExecutor):
            def supports(self, case: TestCase) -> bool:
                return case.grpc_config is not None

            def execute(self, case: TestCase, context: TestContext, variables: dict) -> CaseResult:
                ...
    """

    @abstractmethod
    def execute(
        self,
        case: TestCase,
        context: TestContext,
        variables: dict[str, Any],
    ) -> CaseResult:
        """执行协议相关的用例逻辑

        Args:
            case: 当前测试用例。
            context: 线程安全的测试上下文（请求/响应/变量存储）。
            variables: 合并后的用例变量（环境 + 套件 + 用例 + setup 提取）。

        Returns:
            CaseResult: 执行结果，包含 passed / error / request / response 等信息。
        """
        ...

    @abstractmethod
    def supports(self, case: TestCase) -> bool:
        """判断当前 executor 是否支持该用例

        Args:
            case: 当前测试用例。

        Returns:
            True 表示本 executor 能处理该用例。
        """
        ...
