"""配置加载器 — 多环境配置合并 + 环境变量覆盖 + Schema 校验 + 热加载

支持:
- 多环境深度合并（config.yaml → env.yaml → env.local.yaml → OS 环境变量）
- list 合并策略（replace / append，由 settings.merge_strategy 控制）
- 基于 watchdog 的配置文件热加载（由 settings.hot_reload 控制）
- 配置 Schema 启动时校验
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Callable

import yaml
from pydantic import ValidationError

from framework.config_schema import AutotestConfig
from framework.exceptions import ConfigValidationError
from framework.models import EnvConfig, ProjectConfig
from framework.utils.logger import Logger

logger = Logger.get("config")

# watchdog 为可选依赖
try:
    from watchdog.events import FileSystemEventHandler  # type: ignore[import-untyped]
    from watchdog.observers import Observer  # type: ignore[import-untyped]

    _WATCHDOG_AVAILABLE = True
except ImportError:  # pragma: no cover
    _WATCHDOG_AVAILABLE = False

# 默认合并策略常量
MERGE_REPLACE = "replace"
MERGE_APPEND = "append"
_VALID_MERGE_STRATEGIES = (MERGE_REPLACE, MERGE_APPEND)


class ConfigLoader:
    """配置加载器

    加载顺序（后覆盖前）：
    1. config.yaml（全局默认）
    2. env.yaml 中对应环境的配置
    3. env.local.yaml（本地覆盖，gitignore）
    4. OS 环境变量覆盖

    list 合并策略：
    - settings.merge_strategy = "replace"（默认）：list 字段直接替换
    - settings.merge_strategy = "append"：list 字段增量追加

    热加载：
    - settings.hot_reload.enabled = true 开启
    - 调用 start_watching(callback) 开始监听配置文件变化
    """

    def __init__(self, config_dir: str = "config") -> None:
        self._config_dir = Path(config_dir)
        self._observer: Any = None
        self._watcher_lock = threading.Lock()

        # 缓存当前配置，用于热加载回调对比
        self._last_global_raw: dict[str, Any] = {}
        self._last_env_name: str | None = None

    # ---------- 公开 API ----------

    @property
    def merge_strategy(self) -> str:
        """获取当前生效的 list 合并策略

        优先从最新加载的全局配置中读取，未加载时返回默认值。
        """
        settings = self._last_global_raw.get("settings", {})
        strategy = settings.get("merge_strategy", MERGE_REPLACE)
        if strategy not in _VALID_MERGE_STRATEGIES:
            logger.warning(
                f"无效的 merge_strategy: '{strategy}'，回退为默认值 '{MERGE_REPLACE}'"
            )
            return MERGE_REPLACE
        return strategy

    @property
    def hot_reload_enabled(self) -> bool:
        """热加载是否已通过配置开启"""
        settings = self._last_global_raw.get("settings", {})
        hr = settings.get("hot_reload", {})
        if isinstance(hr, dict):
            return bool(hr.get("enabled", False))
        return False

    def load(self, env_name: str | None = None) -> tuple[ProjectConfig, EnvConfig]:
        """加载完整配置

        Args:
            env_name: 环境名称，为 None 时使用 env.yaml 中的 default

        Returns:
            (ProjectConfig, EnvConfig) 元组

        Raises:
            ConfigValidationError: 配置不满足 Schema 约束
        """
        # 1. 加载全局配置
        global_raw = self._load_yaml("config.yaml")
        self._last_global_raw = global_raw

        project_config = self._build_project_config(global_raw)

        # 2. 加载环境配置
        env_raw = self._load_yaml("env.yaml")
        if env_name is None:
            env_name = env_raw.get("default", "dev")

        self._last_env_name = env_name

        # 3. 加载本地覆盖
        local_raw = self._load_yaml("env.local.yaml")

        # 4. 合并环境配置（使用当前 merge_strategy）
        envs = env_raw.get("environments", {})
        env_data = envs.get(env_name, {})
        if not env_data:
            logger.warning(f"环境 '{env_name}' 未在 env.yaml 中定义，使用空配置")

        # 本地覆盖合并
        local_envs = local_raw.get("environments", {})
        if env_name in local_envs:
            env_data = self._deep_merge(env_data, local_envs[env_name], self.merge_strategy)

        # 5. Schema 校验 — 启动时配置错误早发现
        self._validate_merged_config(global_raw, env_data, env_name)

        env_config = self._build_env_config(env_name, env_data)

        # 6. OS 环境变量覆盖（AUTOTEST_ 前缀）
        self._apply_env_overrides(env_config)

        logger.info(f"配置加载完成: env={env_name}, base_url={env_config.base_url}")
        return project_config, env_config

    def reload(self, env_name: str | None = None) -> tuple[ProjectConfig, EnvConfig]:
        """重新加载配置（用于热加载回调）

        与 load() 相同，但会清除内部缓存后重新读取所有文件。

        Args:
            env_name: 环境名称，为 None 时使用上次加载的环境名

        Returns:
            (ProjectConfig, EnvConfig) 元组
        """
        target_env = env_name or self._last_env_name
        logger.info(f"配置热重载触发: env={target_env}")
        # 强制重读，不依赖 yaml.safe_load 可能存在的缓存
        return self.load(target_env)

    def start_watching(
        self,
        on_change: Callable[[tuple[ProjectConfig, EnvConfig]], None] | None = None,
    ) -> None:
        """启动配置文件热加载监控

        Args:
            on_change: 文件变化时的回调，参数为 (ProjectConfig, EnvConfig)。
                       若为 None，仅记录日志。

        Raises:
            ImportError: watchdog 未安装
            RuntimeError: 已启动监控

        Note:
            必须在 load() 之后调用，否则 merge_strategy 无法从配置中读取。
            热加载仅当 settings.hot_reload.enabled = true 时生效。
        """
        if not _WATCHDOG_AVAILABLE:
            raise ImportError(
                "watchdog 未安装，无法启用热加载。请运行: pip install watchdog"
            )

        with self._watcher_lock:
            if self._observer is not None:
                raise RuntimeError("热加载监控已启动，请先调用 stop_watching()")

            if not self.hot_reload_enabled:
                logger.info("热加载未在配置中开启 (settings.hot_reload.enabled=false)，跳过")
                return

            watched_files = self._get_watch_paths()

            handler = _ConfigFileHandler(self, on_change, watched_files)
            observer = Observer()
            observer.schedule(
                handler,
                str(self._config_dir),
                recursive=False,
            )
            observer.start()
            self._observer = observer

            logger.info(f"配置文件热加载已启动: 监控目录={self._config_dir}")

    def stop_watching(self) -> None:
        """停止配置文件热加载监控"""
        with self._watcher_lock:
            if self._observer is not None:
                self._observer.stop()
                self._observer.join(timeout=5)
                self._observer = None
                logger.info("配置文件热加载已停止")

    # ---------- 静态工具方法 ----------

    @staticmethod
    def _deep_merge(
        base: dict[str, Any],
        override: dict[str, Any],
        list_strategy: str = MERGE_REPLACE,
    ) -> dict[str, Any]:
        """深度合并两个字典

        合并规则：
        - 同为 dict → 递归合并
        - 同为 list：
            * list_strategy = "replace" → 直接替换（默认）
            * list_strategy = "append" → 增量追加
        - 其他 → override 覆盖 base

        Args:
            base: 基础字典
            override: 覆盖字典
            list_strategy: list 字段合并策略 ("replace"|"append")

        Returns:
            合并后的新字典
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigLoader._deep_merge(result[key], value, list_strategy)
            elif (
                key in result
                and isinstance(result[key], list)
                and isinstance(value, list)
                and list_strategy == MERGE_APPEND
            ):
                result[key] = result[key] + value
            else:
                result[key] = value
        return result

    # ---------- 私有方法 ----------

    def _validate_merged_config(
        self,
        global_raw: dict[str, Any],
        env_data: dict[str, Any],
        env_name: str,
    ) -> None:
        """对合并后的配置执行 Schema 校验"""
        merged = self._deep_merge(global_raw, env_data, self.merge_strategy)
        merged["env"] = env_name
        try:
            AutotestConfig.model_validate(merged)
        except ValidationError as exc:
            raise ConfigValidationError.from_pydantic(exc) from exc

        logger.debug(f"Schema 校验通过: env={env_name}")

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        """加载 YAML 文件"""
        path = self._config_dir / filename
        if not path.exists():
            logger.debug(f"配置文件不存在，跳过: {path}")
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def _build_project_config(self, raw: dict[str, Any]) -> ProjectConfig:
        """构建 ProjectConfig"""
        project = raw.get("project", {})
        auth = raw.get("auth", {})
        return ProjectConfig(
            project_name=project.get("name", "API Test Suite"),
            version=project.get("version", "1.0.0"),
            http=raw.get("http", {}),
            logging=raw.get("logging", {}),
            report=raw.get("report", {}),
            assertion=raw.get("assertion", {}),
            execution=raw.get("execution", {}),
            db=raw.get("db", {}),
            fixtures=raw.get("fixtures", {}),
            notifications=raw.get("notifications", {}),
            persistence=raw.get("persistence", {}),
            settings=raw.get("settings", {}),
            mock=raw.get("mock", {}),
            recorder=raw.get("recorder", {}),
            case_timeout=raw.get("case_timeout", 300),
            jwt_secret=auth.get("jwt_secret", "autotest-default-secret-change-me"),
            jwt_expire_minutes=auth.get("token_expire_minutes", 480),
        )

    def _build_env_config(self, name: str, raw: dict[str, Any]) -> EnvConfig:
        """构建 EnvConfig"""
        return EnvConfig(
            name=name,
            base_url=raw.get("base_url", ""),
            ws_url=raw.get("ws_url", ""),
            variables=raw.get("variables", {}),
            http=raw.get("http", {}),
            db=raw.get("db", {}),
            ws=raw.get("ws", {}),
        )

    def _apply_env_overrides(self, env_config: EnvConfig) -> None:
        """应用 OS 环境变量覆盖（AUTOTEST_ 前缀）"""
        prefix = "AUTOTEST_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                attr = key[len(prefix) :].lower()
                if attr == "base_url":
                    env_config.base_url = value
                elif attr == "ws_url":
                    env_config.ws_url = value
                else:
                    env_config.variables[attr] = value
                logger.debug(f"环境变量覆盖: {key} -> {attr}")

    def _get_watch_paths(self) -> set[Path]:
        """获取需要监控的配置文件路径集合"""
        paths: set[Path] = set()
        for name in ("config.yaml", "env.yaml", "env.local.yaml"):
            p = self._config_dir / name
            if p.exists():
                paths.add(p)
        return paths


class _ConfigFileHandler(FileSystemEventHandler if _WATCHDOG_AVAILABLE else object):
    """watchdog 文件系统事件处理器

    仅在配置文件实际内容变化时触发 reload，忽略非配置文件的变更。
    内置防抖：短时间内多次变动只触发一次。
    """

    def __init__(
        self,
        loader: ConfigLoader,
        callback: Callable[[tuple[ProjectConfig, EnvConfig]], None] | None,
        watched_paths: set[Path],
    ) -> None:
        if not _WATCHDOG_AVAILABLE:  # pragma: no cover
            raise ImportError("watchdog 不可用")
        super().__init__()  # type: ignore[no-untyped-call]
        self._loader = loader
        self._callback = callback
        self._watched_paths = watched_paths
        self._debounce_timer: threading.Timer | None = None
        self._debounce_lock = threading.Lock()
        self._debounce_seconds = 2.0  # 2 秒防抖

    def on_modified(self, event: Any) -> None:
        """文件修改事件"""
        if not event.is_directory and Path(event.src_path) in self._watched_paths:
            self._schedule_reload(Path(event.src_path))

    def on_created(self, event: Any) -> None:
        """文件创建事件"""
        if not event.is_directory and Path(event.src_path) in self._watched_paths:
            self._schedule_reload(Path(event.src_path))

    def _schedule_reload(self, changed_path: Path) -> None:
        """防抖调度重新加载"""
        with self._debounce_lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(
                self._debounce_seconds,
                self._do_reload,
                args=[changed_path],
            )
            self._debounce_timer.start()

    def _do_reload(self, changed_path: Path) -> None:
        """执行配置重载"""
        logger.info(f"检测到配置文件变化: {changed_path.name}")
        try:
            project_cfg, env_cfg = self._loader.reload()
            if self._callback:
                self._callback((project_cfg, env_cfg))
        except Exception as exc:
            logger.error(f"配置重载失败: {exc}")
