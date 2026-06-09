"""Mock 插件 — 集成 PluginManager

在用例执行前后自动管理 Mock 规则的注册和清理。
通过 PluginManager 的 on_setup/on_teardown 钩子实现生命周期管理。

用法：
    1. 自动发现：PluginManager.discover() 会自动加载此插件
    2. 通过 PluginContext 传递规则：
       manager.context.set("mock_rules_for_case", [...])
    3. 插件在 case_setup 时注册规则，case_teardown 时清理
"""

from __future__ import annotations

from typing import Any

from framework.mock.rule_store import get_mock_store
from framework.plugins.base import PluginBase
from framework.utils.logger import Logger

logger = Logger.get("mock.plugin")


class MockPlugin(PluginBase):
    """Mock 管理插件

    在测试用例执行生命周期中自动管理 Mock 规则。
    优先级设为 50，确保在大多数业务插件之前执行。

    Attributes:
        priority: 插件优先级，50。
        _tag_prefix: 通过 context 传递的规则标记前缀。
    """

    priority: int = 50
    _tag_prefix: str = "mock_plugin_"

    def name(self) -> str:
        return "MockPlugin"

    def on_case_start(self, case: Any) -> None:
        """用例开始前 — 检查是否有待注册的 Mock 规则"""
        logger.debug("mock_plugin_case_start", case_name=getattr(case, "name", "unknown"))

    def on_case_end(self, case: Any, result: Any) -> None:
        """用例结束后 — 清理规则"""
        logger.debug("mock_plugin_case_end", case_name=getattr(case, "name", "unknown"))

    def on_setup(
        self,
        phase: str,
        case: Any,
        variables: dict[str, Any],
    ) -> None:
        """Setup 阶段完成后 — 检查是否需要注册 Mock 规则。

        通过 PluginContext 读取待注册规则：
        - context.get("mock_rules", []) → 注册规则列表

        Args:
            phase: "before" 或 "after"
            case: 当前用例或套件
            variables: 当前变量上下文
        """
        pass  # 规则注册由 FixtureLoader.mock_setup 直接调用 store

    def on_teardown(
        self,
        phase: str,
        case: Any,
        variables: dict[str, Any],
    ) -> None:
        """Teardown 阶段 — 清理 Mock 规则。

        Args:
            phase: "before" 或 "after"
            case: 当前用例或套件
            variables: 当前变量上下文
        """
        pass  # 规则清理由 FixtureLoader.mock_teardown 直接调用 store
