"""插件管理器 — 自动发现、注册、排序、调度插件

设计要点：
- 自动发现：扫描 framework/plugins/ 目录，加载所有 PluginBase 子类。
- 按 priority 排序：数值越小越先执行。
- dispatch()：按优先级依次调用所有插件的对应钩子，并收集返回值。
- PluginContext：线程安全的插件间共享数据容器。
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import os
import threading
from typing import Any

from framework.plugins.base import PluginBase
from framework.utils.logger import Logger

logger = Logger.get("plugin.manager")


# ==================== PluginContext ====================


class PluginContext:
    """插件间共享数据容器（线程安全）

    支持按 key 存储/读取任意数据，用于插件间通信。
    例如：auth_manager 存入 token，report 插件读取 token 状态。

    Usage:
        ctx = PluginContext()
        ctx.set("token", "xxx")
        ctx.get("token")  # "xxx"
        ctx.get("missing", "default")  # "default"
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: Any) -> None:
        """存储数据"""
        with self._lock:
            self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """读取数据"""
        with self._lock:
            return self._data.get(key, default)

    def delete(self, key: str) -> Any:
        """删除并返回数据"""
        with self._lock:
            return self._data.pop(key, None)

    def has(self, key: str) -> bool:
        """检查 key 是否存在"""
        with self._lock:
            return key in self._data

    def snapshot(self) -> dict[str, Any]:
        """返回所有数据的快照（线程安全）"""
        with self._lock:
            return dict(self._data)

    def clear(self) -> None:
        """清空所有数据"""
        with self._lock:
            self._data.clear()


# ==================== PluginManager ====================

# 钩子方法到 dispatch 事件名的映射表
_HOOK_EVENTS: dict[str, str] = {
    "on_suite_start": "suite_start",
    "on_suite_end": "suite_end",
    "on_case_start": "case_start",
    "on_case_end": "case_end",
    "on_setup": "setup",
    "on_teardown": "teardown",
    "on_request": "request",
    "on_response": "response",
    "on_assertion": "assertion",
    "on_extract": "extract",
    "on_error": "error",
    "on_retry": "retry",
    "on_db_query": "db_query",
}

# 链式分发参数名映射：dispatch_chain 需要知道把 chain_value 传成什么参数名
_CHAIN_PARAM_MAP: dict[str, str] = {
    "request": "request",
    "response": "response",
}


class PluginManager:
    """插件管理器

    职责：
    1. 自动发现并加载 framework/plugins/ 下的插件
    2. 按 priority 排序
    3. 提供 dispatch(event, **kwargs) 分发钩子事件
    4. 管理 PluginContext 插件间共享数据

    Usage:
        manager = PluginManager()
        manager.discover()                # 自动发现插件
        manager.register(my_plugin)       # 手动注册额外插件
        manager.dispatch("case_start", case=test_case)

        插件间通信:
        manager.context.set("shared_key", value)
    """

    def __init__(
        self,
        context: PluginContext | None = None,
        plugin_dirs: list[str] | None = None,
    ) -> None:
        """
        Args:
            context: 共享上下文（不传则自动创建）。
            plugin_dirs: 额外扫描目录（默认扫描 framework/plugins/）。
        """
        self._plugins: list[PluginBase] = []
        self._plugin_map: dict[str, PluginBase] = {}
        self._context = context or PluginContext()

        # 默认扫描目录
        if plugin_dirs is None:
            framework_plugins = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "plugins"
            )
            self._plugin_dirs = [framework_plugins]
        else:
            self._plugin_dirs = plugin_dirs

    # ── 属性 ─────────────────────────────────────────

    @property
    def context(self) -> PluginContext:
        """插件间共享数据容器"""
        return self._context

    @property
    def plugins(self) -> list[PluginBase]:
        """已注册的插件列表（按 priority 排序）"""
        return list(self._plugins)

    @property
    def plugin_names(self) -> list[str]:
        """已注册的插件名称列表"""
        return [p.name() for p in self._plugins]

    def get_plugin(self, name: str) -> PluginBase | None:
        """按名称查找插件"""
        return self._plugin_map.get(name)

    # ── 注册 ─────────────────────────────────────────

    def register(self, plugin: PluginBase) -> None:
        """注册单个插件，按 priority 插入排序"""
        if plugin.name() in self._plugin_map:
            logger.warning(f"插件 '{plugin.name()}' 已存在，将被覆盖")
            self._plugins = [p for p in self._plugins if p.name() != plugin.name()]

        self._plugin_map[plugin.name()] = plugin

        # 按 priority 插入
        inserted = False
        for i, existing in enumerate(self._plugins):
            if plugin.priority < existing.priority:
                self._plugins.insert(i, plugin)
                inserted = True
                break
        if not inserted:
            self._plugins.append(plugin)

        logger.debug(
            f"注册插件: {plugin.name()} (priority={plugin.priority})"
        )

    def unregister(self, name: str) -> bool:
        """移除插件"""
        plugin = self._plugin_map.pop(name, None)
        if plugin:
            self._plugins = [p for p in self._plugins if p.name() != name]
            logger.debug(f"移除插件: {name}")
            return True
        return False

    # ── 自动发现 ────────────────────────────────────

    def discover(self, extra_dirs: list[str] | None = None) -> int:
        """自动扫描所有 plugin_dirs 并加载 PluginBase 子类

        扫描逻辑：
        1. 遍历 self._plugin_dirs + extra_dirs 中所有 .py 文件（排除 __init__ 和 base）
        2. 动态 import 模块
        3. 查找 PluginBase 的子类（排除 PluginBase 自身和已注册类）
        4. 实例化并注册

        Returns:
            新发现的插件数量
        """
        dirs = list(self._plugin_dirs)
        if extra_dirs:
            dirs.extend(extra_dirs)

        discovered = 0
        for directory in dirs:
            if not os.path.isdir(directory):
                logger.debug(f"插件目录不存在，跳过: {directory}")
                continue

            for filename in os.listdir(directory):
                if not self._is_plugin_file(filename):
                    continue

                module_name = filename[:-3]  # 去 .py
                try:
                    count = self._load_from_module(directory, module_name)
                    discovered += count
                except Exception as e:
                    logger.warning(f"加载插件模块失败 '{module_name}': {e}")

        if discovered > 0:
            logger.info(f"自动发现 {discovered} 个插件: {self.plugin_names}")
        else:
            logger.debug("未发现新插件")

        return discovered

    # ── 事件分发 ────────────────────────────────────

    def dispatch(self, event: str, **kwargs: Any) -> list[Any]:
        """按优先级分发事件到所有插件

        对于有返回值的钩子（on_request / on_response），
        前一个插件的返回值会传给下一个插件作为输入，
        最终返回所有插件的返回值列表。

        Args:
            event: 事件名（如 "case_start", "request" 等）
            **kwargs: 传递给钩子方法的参数

        Returns:
            所有插件的返回值列表（空钩子返回 None）

        Raises:
            ValueError: 未知事件名
        """
        method_name = self._event_to_method(event)
        results: list[Any] = []

        for plugin in self._plugins:
            hook = getattr(plugin, method_name, None)
            if hook is None:
                continue

            try:
                result = hook(**kwargs)
                results.append(result)
                logger.debug(f"插件 '{plugin.name()}' 处理事件 '{event}'")
            except Exception as e:
                logger.error(f"插件 '{plugin.name()}' 处理事件 '{event}' 异常: {e}")

        return results

    def dispatch_chain(self, event: str, chain_value: Any, **kwargs: Any) -> Any:
        """链式分发 — 适用于 on_request / on_response 等需要链式修改值的场景

        前一个插件的返回值作为下一个插件的输入，最终返回最后一个插件的输出。
        自动将 chain_value 映射为对应钩子方法的参数名（如 request → on_request 的 request 参数）。

        Args:
            event: 事件名
            chain_value: 链式传递的初始值
            **kwargs: 额外参数

        Returns:
            链式处理后的最终值
        """
        method_name = self._event_to_method(event)
        # 获取链式参数名（如 "request"、"response"）
        chain_param = _CHAIN_PARAM_MAP.get(event, "chain_value")
        current = chain_value

        for plugin in self._plugins:
            hook = getattr(plugin, method_name, None)
            if hook is None:
                continue

            try:
                all_kwargs = dict(kwargs)
                all_kwargs[chain_param] = current
                result = hook(**all_kwargs)
                if result is not None:
                    current = result
                logger.debug(f"插件 '{plugin.name()}' 链式处理事件 '{event}'")
            except Exception as e:
                logger.error(f"插件 '{plugin.name()}' 链式处理事件 '{event}' 异常: {e}")

        return current

    # ── 内部方法 ────────────────────────────────────

    @staticmethod
    def _is_plugin_file(filename: str) -> bool:
        """判断是否为可加载的插件文件"""
        return (
            filename.endswith(".py")
            and not filename.startswith("_")
            and filename != "base.py"
        )

    def _load_from_module(self, directory: str, module_name: str) -> int:
        """从指定目录动态加载模块并发现插件类"""
        # 构建完整模块路径
        # 例如 directory=/path/framework/plugins, module_name=auth_manager
        # -> framework.plugins.auth_manager
        filepath = os.path.join(directory, f"{module_name}.py")
        if not os.path.isfile(filepath):
            return 0

        spec = importlib.util.spec_from_file_location(
            f"framework.plugins.{module_name}", filepath
        )
        if spec is None or spec.loader is None:
            return 0

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        count = 0
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if not self._is_plugin_subclass(obj):
                continue
            # 跳过已注册的插件（按类名去重）
            if any(type(p) is obj for p in self._plugins):
                continue

            try:
                plugin_instance = obj()
                self.register(plugin_instance)
                count += 1
            except Exception as e:
                logger.warning(f"实例化插件 '{obj.__name__}' 失败: {e}")

        return count

    @staticmethod
    def _is_plugin_subclass(cls: type) -> bool:
        """判断是否为合法的插件子类"""
        return (
            issubclass(cls, PluginBase)
            and cls is not PluginBase
            and not inspect.isabstract(cls)
        )

    @staticmethod
    def _event_to_method(event: str) -> str:
        """将事件名映射为钩子方法名"""
        mapped = _HOOK_EVENTS.get(event)
        if mapped is None:
            # 反向查找
            reverse = {v: k for k, v in _HOOK_EVENTS.items()}
            if event in reverse:
                mapped = reverse[event]
            else:
                raise ValueError(
                    f"未知事件: '{event}'，支持的事件: {list(_HOOK_EVENTS.keys())} "
                    f"或 {list(set(_HOOK_EVENTS.values()))}"
                )
        return event if event in _HOOK_EVENTS else mapped
