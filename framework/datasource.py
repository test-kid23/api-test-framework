"""数据源注册表 — 管理多数据源配置的注册、查询与验证

提供中心化的数据源管理能力：
- register(): 注册数据源配置
- get(): 获取指定数据源配置
- get_default(): 获取默认数据源
- list_all(): 列出所有数据源名称
- validate(): 启动时连接验证（SELECT 1）
"""

from __future__ import annotations

from typing import Any

from framework.config_schema import DataSourceConfig
from framework.utils.logger import Logger

logger = Logger.get("datasource")


class DataSourceRegistryError(Exception):
    """数据源注册表异常."""


class DataSourceRegistry:
    """数据源注册表.

    从配置中加载数据源定义，提供统一的数据源查询接口。

    Usage:
        registry = DataSourceRegistry()
        registry.register("main_db", DataSourceConfig(type="mysql", host="localhost", ...))
        config = registry.get("main_db")
    """

    def __init__(self) -> None:
        """初始化空注册表."""
        self._sources: dict[str, DataSourceConfig] = {}
        self._default_name: str = "main_db"

    # ── 注册 ──────────────────────────────────────────

    def register(self, name: str, config: DataSourceConfig) -> None:
        """注册数据源配置.

        Args:
            name: 数据源名称（如 "main_db"）。
            config: 数据源连接配置。

        Raises:
            DataSourceRegistryError: 名称已存在时。
        """
        if name in self._sources:
            raise DataSourceRegistryError(
                f"数据源 '{name}' 已注册，请使用不同的名称"
            )
        self._sources[name] = config
        logger.debug("datasource_registered", name=name, type=config.type)

    def register_or_update(self, name: str, config: DataSourceConfig) -> None:
        """注册或更新数据源配置.

        Args:
            name: 数据源名称。
            config: 数据源连接配置。
        """
        existed = name in self._sources
        self._sources[name] = config
        if existed:
            logger.debug("datasource_updated", name=name, type=config.type)
        else:
            logger.debug("datasource_registered", name=name, type=config.type)

    # ── 查询 ──────────────────────────────────────────

    def get(self, name: str) -> DataSourceConfig:
        """获取指定数据源配置.

        Args:
            name: 数据源名称。

        Returns:
            数据源配置。

        Raises:
            DataSourceRegistryError: 数据源未注册时。
        """
        if name not in self._sources:
            raise DataSourceRegistryError(
                f"数据源 '{name}' 未注册。已注册的数据源: {list(self._sources.keys())}"
            )
        return self._sources[name]

    def get_default(self) -> DataSourceConfig:
        """获取默认数据源配置.

        Returns:
            默认数据源配置。

        Raises:
            DataSourceRegistryError: 默认数据源未注册或注册表为空时。
        """
        if self._default_name not in self._sources:
            if self._sources:
                # 回退：返回第一个注册的数据源
                first = next(iter(self._sources.keys()))
                logger.warning(
                    "default_datasource_not_found",
                    expected=self._default_name,
                    fallback=first,
                )
                return self._sources[first]
            raise DataSourceRegistryError("没有注册任何数据源")
        return self._sources[self._default_name]

    def list_all(self) -> list[str]:
        """列出所有已注册的数据源名称.

        Returns:
            数据源名称列表。
        """
        return list(self._sources.keys())

    def set_default(self, name: str) -> None:
        """设置默认数据源.

        Args:
            name: 数据源名称（必须先注册）。

        Raises:
            DataSourceRegistryError: 数据源未注册时。
        """
        if name not in self._sources:
            raise DataSourceRegistryError(
                f"无法将默认数据源设置为 '{name}'：该数据源未注册"
            )
        self._default_name = name

    # ── 批量加载 ──────────────────────────────────────

    def load_from_config(self, datasources_config: dict[str, Any]) -> None:
        """从配置 dict 批量加载数据源.

        遍历 datasources 配置中的每个条目（排除 "default" 字段），
        将每个非 "default" 的 key-value 对注册为数据源。

        Args:
            datasources_config: 数据源配置字典，格式如:
                {"default": "main_db", "main_db": {...}, "secondary_db": {...}}
        """
        default_name = datasources_config.get("default", "main_db")
        if isinstance(default_name, str):
            self._default_name = default_name

        for name, raw in datasources_config.items():
            if name == "default":
                continue
            if isinstance(raw, dict):
                config = DataSourceConfig(**raw)
                self._sources[name] = config
                logger.info(
                    "datasource_loaded",
                    name=name,
                    type=config.type,
                    host=config.host,
                    database=config.database,
                )

    # ── 验证 ──────────────────────────────────────────

    def validate(self, name: str | None = None) -> dict[str, bool]:
        """验证数据源连接可用性（执行 SELECT 1）.

        Args:
            name: 要验证的数据源名称，为 None 时验证所有已注册数据源。

        Returns:
            {数据源名称: 是否可用} 字典。
        """
        results: dict[str, bool] = {}

        names = [name] if name else list(self._sources.keys())
        for ds_name in names:
            if ds_name not in self._sources:
                results[ds_name] = False
                continue
            try:
                config = self._sources[ds_name]
                conn_dict = config.to_connection_dict()
                ok = self._ping_connection(conn_dict)
                results[ds_name] = ok
                if ok:
                    logger.info("datasource_validated", name=ds_name, status="ok")
                else:
                    logger.error("datasource_validation_failed", name=ds_name)
            except Exception as e:
                logger.error("datasource_validation_error", name=ds_name, error=str(e))
                results[ds_name] = False

        return results

    @staticmethod
    def _ping_connection(conn_dict: dict[str, object]) -> bool:
        """执行 SELECT 1 验证连接.

        Args:
            conn_dict: DBConnectionManager 格式的连接配置。

        Returns:
            连接是否可用。
        """
        db_type = str(conn_dict.get("type", "mysql"))
        try:
            if db_type == "sqlite":
                import sqlite3

                database = str(conn_dict.get("database", ":memory:"))
                conn = sqlite3.connect(database, timeout=5)
                conn.execute("SELECT 1")
                conn.close()
                return True
            elif db_type == "postgresql":
                import psycopg2

                conn = psycopg2.connect(
                    host=str(conn_dict.get("host", "localhost")),
                    port=int(conn_dict.get("port", 5432)),
                    user=str(conn_dict.get("user", "postgres")),
                    password=str(conn_dict.get("password", "")),
                    dbname=str(conn_dict.get("database", "postgres")),
                    connect_timeout=5,
                )
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                conn.close()
                return True
            else:
                # mysql / default
                import pymysql

                conn = pymysql.connect(
                    host=str(conn_dict.get("host", "localhost")),
                    port=int(conn_dict.get("port", 3306)),
                    user=str(conn_dict.get("user", "root")),
                    password=str(conn_dict.get("password", "")),
                    database=str(conn_dict.get("database", "test")),
                    connect_timeout=5,
                )
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                conn.close()
                return True
        except Exception:
            return False

    # ── 工具 ──────────────────────────────────────────

    def to_connection_dicts(self) -> dict[str, dict[str, object]]:
        """将所有数据源配置转换为 DBExecutor 所需的格式.

        Returns:
            {数据源名称: 连接参数字典} 映射。
        """
        return {name: config.to_connection_dict() for name, config in self._sources.items()}

    def __len__(self) -> int:
        return len(self._sources)

    def __contains__(self, name: str) -> bool:
        return name in self._sources
