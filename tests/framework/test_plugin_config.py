"""插件配置化单元测试 (T5-07)

测试覆盖：
- PluginConfig Pydantic 模型（默认值 / 三种模式 / enabled/disabled 列表）
- PluginManager 无配置时加载所有插件
- PluginManager whitelist 模式仅加载指定插件
- PluginManager blacklist 模式排除指定插件
- PluginManager._should_load_plugin 各边界情况
- 未知模式降级为 all
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from framework.config_schema import PluginConfig
from framework.plugins.base import PluginBase
from framework.plugins.manager import PluginManager


# ── 测试用桩插件 ──────────────────────────────────────────


class _StubPluginA(PluginBase):
    """测试桩插件 A."""
    priority = 10

    def name(self) -> str:
        return "plugin_a"


class _StubPluginB(PluginBase):
    """测试桩插件 B."""
    priority = 20

    def name(self) -> str:
        return "plugin_b"


class _StubPluginC(PluginBase):
    """测试桩插件 C."""
    priority = 30

    def name(self) -> str:
        return "plugin_c"


# ── PluginConfig 模型测试 ──────────────────────────────────


class TestPluginConfig:
    """PluginConfig Pydantic 模型测试."""

    def test_default_values(self) -> None:
        """默认值：mode=all，enabled/disabled 为空."""
        cfg = PluginConfig()
        assert cfg.mode == "all"
        assert cfg.enabled == []
        assert cfg.disabled == []

    def test_whitelist_mode(self) -> None:
        """白名单模式."""
        cfg = PluginConfig(mode="whitelist", enabled=["plugin_a", "plugin_b"])
        assert cfg.mode == "whitelist"
        assert cfg.enabled == ["plugin_a", "plugin_b"]

    def test_blacklist_mode(self) -> None:
        """黑名单模式."""
        cfg = PluginConfig(mode="blacklist", disabled=["plugin_c"])
        assert cfg.mode == "blacklist"
        assert cfg.disabled == ["plugin_c"]

    def test_all_mode(self) -> None:
        """all 模式."""
        cfg = PluginConfig(mode="all")
        assert cfg.mode == "all"

    def test_extra_fields_ignored(self) -> None:
        """未知字段被忽略."""
        cfg = PluginConfig(mode="all", foo="bar")  # type: ignore[call-arg]
        assert cfg.mode == "all"

    def test_invalid_mode_raises(self) -> None:
        """非法 mode 值抛出 ValidationError."""
        with pytest.raises(Exception):
            PluginConfig(mode="invalid_mode")  # type: ignore[arg-type]


# ── _should_load_plugin 测试 ─────────────────────────────


class TestShouldLoadPlugin:
    """PluginManager._should_load_plugin 方法测试."""

    def test_all_mode_loads_everything(self) -> None:
        """all 模式加载所有插件."""
        mgr = PluginManager(plugin_config=PluginConfig(mode="all"))
        assert mgr._should_load_plugin("plugin_a") is True
        assert mgr._should_load_plugin("unknown_plugin") is True

    def test_whitelist_includes_only_listed(self) -> None:
        """whitelist 模式仅加载列表中的插件."""
        mgr = PluginManager(
            plugin_config=PluginConfig(
                mode="whitelist",
                enabled=["plugin_a", "plugin_b"],
            )
        )
        assert mgr._should_load_plugin("plugin_a") is True
        assert mgr._should_load_plugin("plugin_b") is True
        assert mgr._should_load_plugin("plugin_c") is False

    def test_blacklist_excludes_listed(self) -> None:
        """blacklist 模式排除列表中的插件."""
        mgr = PluginManager(
            plugin_config=PluginConfig(
                mode="blacklist",
                disabled=["plugin_c"],
            )
        )
        assert mgr._should_load_plugin("plugin_a") is True
        assert mgr._should_load_plugin("plugin_b") is True
        assert mgr._should_load_plugin("plugin_c") is False

    def test_whitelist_empty_loads_nothing(self) -> None:
        """空白名单不加载任何插件."""
        mgr = PluginManager(
            plugin_config=PluginConfig(
                mode="whitelist",
                enabled=[],
            )
        )
        assert mgr._should_load_plugin("plugin_a") is False

    def test_blacklist_empty_loads_all(self) -> None:
        """空黑名单加载所有插件."""
        mgr = PluginManager(
            plugin_config=PluginConfig(
                mode="blacklist",
                disabled=[],
            )
        )
        assert mgr._should_load_plugin("plugin_a") is True

    def test_no_config_loads_all(self) -> None:
        """无配置时加载所有插件."""
        mgr = PluginManager(plugin_config=None)
        assert mgr._should_load_plugin("any_plugin") is True

    def test_unknown_mode_falls_back_to_all(self) -> None:
        """未知模式降级为 all."""
        cfg = MagicMock()
        cfg.mode = "unknown_mode"
        cfg.enabled = []
        cfg.disabled = []
        mgr = PluginManager(plugin_config=cfg)
        assert mgr._should_load_plugin("plugin_a") is True


# ── PluginManager 集成测试 ────────────────────────────────


class TestPluginManagerWithConfig:
    """PluginManager 带配置的集成测试."""

    def _register_stubs(self, mgr: PluginManager) -> None:
        """注册三个桩插件."""
        mgr.register(_StubPluginA())
        mgr.register(_StubPluginB())
        mgr.register(_StubPluginC())

    def test_no_config_registers_all(self) -> None:
        """无配置时所有插件正常注册."""
        mgr = PluginManager()
        self._register_stubs(mgr)
        names = mgr.plugin_names
        assert "plugin_a" in names
        assert "plugin_b" in names
        assert "plugin_c" in names

    def test_whitelist_filters_on_discover(self) -> None:
        """whitelist 模式在 discover 时过滤插件."""
        mgr = PluginManager(
            plugin_config=PluginConfig(
                mode="whitelist",
                enabled=["plugin_a"],
            )
        )
        # 手动注册（模拟 discover 后的过滤）
        mgr.register(_StubPluginA())
        # plugin_b 和 plugin_c 被 _should_load_plugin 过滤
        assert mgr._should_load_plugin("plugin_a") is True
        assert mgr._should_load_plugin("plugin_b") is False
        assert mgr._should_load_plugin("plugin_c") is False

    def test_blacklist_filters_on_discover(self) -> None:
        """blacklist 模式在 discover 时过滤插件."""
        mgr = PluginManager(
            plugin_config=PluginConfig(
                mode="blacklist",
                disabled=["plugin_c"],
            )
        )
        assert mgr._should_load_plugin("plugin_a") is True
        assert mgr._should_load_plugin("plugin_b") is True
        assert mgr._should_load_plugin("plugin_c") is False

    def test_config_does_not_affect_dispatch(self) -> None:
        """配置不影响已注册插件的 dispatch 行为."""
        mgr = PluginManager(
            plugin_config=PluginConfig(mode="all")
        )
        self._register_stubs(mgr)

        # dispatch 仍正常工作（桩插件的 on_suite_start 继承自基类返回 None）
        results = mgr.dispatch("suite_start", suite="test")
        assert len(results) == 3

    def test_config_propagates_to_manager(self) -> None:
        """配置正确传递到 PluginManager."""
        cfg = PluginConfig(mode="whitelist", enabled=["plugin_a"])
        mgr = PluginManager(plugin_config=cfg)
        assert mgr._plugin_config is cfg
        assert mgr._plugin_config.mode == "whitelist"
        assert mgr._plugin_config.enabled == ["plugin_a"]


# ── 配置热加载场景 ────────────────────────────────────────


class TestConfigReloadScenario:
    """配置变更场景测试."""

    def test_switch_from_all_to_whitelist(self) -> None:
        """从 all 切换到 whitelist."""
        mgr_all = PluginManager(plugin_config=PluginConfig(mode="all"))
        assert mgr_all._should_load_plugin("plugin_c") is True

        mgr_whitelist = PluginManager(
            plugin_config=PluginConfig(
                mode="whitelist",
                enabled=["plugin_a"],
            )
        )
        assert mgr_whitelist._should_load_plugin("plugin_c") is False

    def test_switch_from_blacklist_to_all(self) -> None:
        """从 blacklist 切换到 all."""
        mgr_blacklist = PluginManager(
            plugin_config=PluginConfig(
                mode="blacklist",
                disabled=["plugin_b"],
            )
        )
        assert mgr_blacklist._should_load_plugin("plugin_b") is False

        mgr_all = PluginManager(plugin_config=PluginConfig(mode="all"))
        assert mgr_all._should_load_plugin("plugin_b") is True
