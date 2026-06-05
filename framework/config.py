"""配置加载器 — 多环境配置合并 + 环境变量覆盖 + Schema 校验"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from framework.config_schema import AutotestConfig, ConfigValidationError
from framework.models import EnvConfig, ProjectConfig
from framework.utils.logger import Logger

logger = Logger.get("config")


class ConfigLoader:
    """配置加载器

    加载顺序（后覆盖前）：
    1. config.yaml（全局默认）
    2. env.yaml 中对应环境的配置
    3. env.local.yaml（本地覆盖，gitignore）
    4. OS 环境变量覆盖
    """

    def __init__(self, config_dir: str = "config") -> None:
        self._config_dir = Path(config_dir)

    def load(self, env_name: str | None = None) -> tuple[ProjectConfig, EnvConfig]:
        """加载完整配置

        Args:
            env_name: 环境名称，为 None 时使用 env.yaml 中的 default

        Returns:
            (ProjectConfig, EnvConfig) 元组
        """
        # 1. 加载全局配置
        global_raw = self._load_yaml("config.yaml")
        project_config = self._build_project_config(global_raw)

        # 2. 加载环境配置
        env_raw = self._load_yaml("env.yaml")
        if env_name is None:
            env_name = env_raw.get("default", "dev")

        # 3. 加载本地覆盖
        local_raw = self._load_yaml("env.local.yaml")

        # 4. 合并环境配置
        envs = env_raw.get("environments", {})
        env_data = envs.get(env_name, {})
        if not env_data:
            logger.warning(f"环境 '{env_name}' 未在 env.yaml 中定义，使用空配置")

        # 本地覆盖合并
        local_envs = local_raw.get("environments", {})
        if env_name in local_envs:
            env_data = self._deep_merge(env_data, local_envs[env_name])

        # 5. Schema 校验 — 启动时配置错误早发现
        self._validate_merged_config(global_raw, env_data, env_name)

        env_config = self._build_env_config(env_name, env_data)

        # 6. OS 环境变量覆盖（AUTOTEST_ 前缀）
        self._apply_env_overrides(env_config)

        logger.info(f"配置加载完成: env={env_name}, base_url={env_config.base_url}")
        return project_config, env_config

    # ---------- 私有方法 ----------

    def _validate_merged_config(
        self,
        global_raw: dict[str, Any],
        env_data: dict[str, Any],
        env_name: str,
    ) -> None:
        """对合并后的配置执行 Schema 校验

        将 config.yaml 的全局配置与环境特定配置深度合并，
        通过 AutotestConfig Pydantic 模型进行类型和范围校验。

        Args:
            global_raw: config.yaml 的原始数据
            env_data: 合并后的环境特定数据
            env_name: 当前环境名称

        Raises:
            ConfigValidationError: 配置不满足 Schema 约束
        """
        merged = self._deep_merge(global_raw, env_data)
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
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}

    def _build_project_config(self, raw: dict[str, Any]) -> ProjectConfig:
        """构建 ProjectConfig"""
        project = raw.get("project", {})
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

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """深度合并两个字典"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigLoader._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
