"""数据源注册表与配置单元测试 (T5-08)

测试覆盖：
- DataSourceConfig 模型（字段默认值 / to_connection_dict / 校验）
- DataSourcesConfig 容器模型（default 字段 / extra=allow）
- DataSourceRegistry 注册表（register / get / get_default / list_all / set_default）
- 重复注册保护 / 未注册查询异常
- load_from_config 批量加载
- to_connection_dicts 格式转换
- validate 连接验证（mock）
- 默认数据源回退机制
"""

from __future__ import annotations

import pytest

from framework.config_schema import DataSourceConfig, DataSourcesConfig
from framework.datasource import DataSourceRegistry, DataSourceRegistryError


# ── DataSourceConfig 模型测试 ────────────────────────────


class TestDataSourceConfigModel:
    """DataSourceConfig Pydantic 模型测试."""

    def test_default_values(self) -> None:
        """默认值：type=mysql, host=localhost, port=3306, user=root."""
        config = DataSourceConfig()
        assert config.type == "mysql"
        assert config.host == "localhost"
        assert config.port == 3306
        assert config.user == "root"
        assert config.password == ""
        assert config.database == "test"
        assert config.pool_size == 5
        assert config.max_overflow == 10
        assert config.pool_recycle == 3600
        assert config.echo is False

    def test_postgresql_config(self) -> None:
        """PostgreSQL 配置."""
        config = DataSourceConfig(
            type="postgresql",
            host="pg.example.com",
            port=5432,
            user="pguser",
            password="secret",
            database="mydb",
            pool_size=10,
        )
        assert config.type == "postgresql"
        assert config.port == 5432

    def test_sqlite_config(self) -> None:
        """SQLite 配置."""
        config = DataSourceConfig(
            type="sqlite",
            database="/tmp/test.db",
            host="",
            port=0,
        )
        assert config.type == "sqlite"
        assert config.database == "/tmp/test.db"

    def test_port_range_validation(self) -> None:
        """port 范围 0-65535（0 用于 SQLite）."""
        # port=0 is valid (for SQLite)
        config = DataSourceConfig(port=0)
        assert config.port == 0
        # port > 65535 is invalid
        with pytest.raises(Exception):  # Pydantic ValidationError
            DataSourceConfig(port=99999)

    def test_pool_size_range_validation(self) -> None:
        """pool_size 范围 1-50."""
        with pytest.raises(Exception):
            DataSourceConfig(pool_size=0)
        with pytest.raises(Exception):
            DataSourceConfig(pool_size=100)

    def test_to_connection_dict(self) -> None:
        """to_connection_dict 返回 DBConnectionManager 所需的格式."""
        config = DataSourceConfig(
            type="mysql",
            host="db.internal",
            port=3307,
            user="app",
            password="pwd",
            database="prod",
            pool_size=8,
            max_overflow=15,
            pool_recycle=1800,
            echo=True,
        )
        result = config.to_connection_dict()
        assert result["type"] == "mysql"
        assert result["host"] == "db.internal"
        assert result["port"] == 3307
        assert result["user"] == "app"
        assert result["password"] == "pwd"
        assert result["database"] == "prod"
        assert result["pool_size"] == 8
        assert result["max_overflow"] == 15
        assert result["pool_recycle"] == 1800
        assert result["echo"] is True

    def test_extra_fields_ignored(self) -> None:
        """extra="ignore"：未知字段被忽略."""
        config = DataSourceConfig(**{"type": "mysql", "unknown_field": "should_be_ignored"})
        assert config.type == "mysql"
        assert not hasattr(config, "unknown_field")


# ── DataSourcesConfig 容器测试 ────────────────────────────


class TestDataSourcesConfig:
    """DataSourcesConfig 容器模型测试."""

    def test_default_value(self) -> None:
        """默认数据源名称为 main_db."""
        config = DataSourcesConfig()
        assert config.default == "main_db"

    def test_default_has_main_db(self) -> None:
        """默认包含 main_db DataSourceConfig."""
        config = DataSourcesConfig()
        assert isinstance(config.main_db, DataSourceConfig)

    def test_extra_allow_multiple_sources(self) -> None:
        """extra="allow" 支持任意数量的额外数据源."""
        config = DataSourcesConfig(
            default="main_db",
            main_db={"type": "mysql", "host": "db1", "database": "app1"},
            secondary_db={"type": "postgresql", "host": "db2", "database": "app2"},
            logs_db={"type": "sqlite", "database": "/tmp/logs.db"},
        )
        assert config.default == "main_db"
        assert config.main_db.database == "app1"
        # extra fields accessible via __pydantic_extra__
        extras = config.__pydantic_extra__ or {}
        assert "secondary_db" in extras
        assert "logs_db" in extras

    def test_custom_default(self) -> None:
        """自定义默认数据源."""
        config = DataSourcesConfig(default="secondary_db")
        assert config.default == "secondary_db"


# ── DataSourceRegistry 注册表测试 ────────────────────────


class TestDataSourceRegistry:
    """DataSourceRegistry 核心功能测试."""

    def test_register_and_get(self) -> None:
        """注册并获取数据源."""
        registry = DataSourceRegistry()
        config = DataSourceConfig(type="mysql", host="db1", database="app")
        registry.register("main_db", config)
        retrieved = registry.get("main_db")
        assert retrieved.host == "db1"
        assert retrieved.database == "app"

    def test_register_duplicate_raises(self) -> None:
        """重复注册抛出 DataSourceRegistryError."""
        registry = DataSourceRegistry()
        registry.register("main_db", DataSourceConfig())
        with pytest.raises(DataSourceRegistryError, match="已注册"):
            registry.register("main_db", DataSourceConfig())

    def test_register_or_update(self) -> None:
        """register_or_update 可以覆盖已有数据源."""
        registry = DataSourceRegistry()
        registry.register("main_db", DataSourceConfig(host="old"))
        registry.register_or_update("main_db", DataSourceConfig(host="new"))
        assert registry.get("main_db").host == "new"

    def test_get_unregistered_raises(self) -> None:
        """查询未注册数据源抛出异常."""
        registry = DataSourceRegistry()
        with pytest.raises(DataSourceRegistryError, match="未注册"):
            registry.get("nonexistent")

    def test_get_default(self) -> None:
        """获取默认数据源."""
        registry = DataSourceRegistry()
        registry.register("main_db", DataSourceConfig(database="main"))
        config = registry.get_default()
        assert config.database == "main"

    def test_get_default_fallback_to_first(self) -> None:
        """默认数据源不存在时回退到第一个注册的数据源."""
        registry = DataSourceRegistry()
        registry.register("custom_db", DataSourceConfig(database="custom"))
        config = registry.get_default()
        assert config.database == "custom"

    def test_get_default_empty_registry_raises(self) -> None:
        """空注册表获取默认抛出异常."""
        registry = DataSourceRegistry()
        with pytest.raises(DataSourceRegistryError, match="没有注册"):
            registry.get_default()

    def test_list_all(self) -> None:
        """列出所有数据源名称."""
        registry = DataSourceRegistry()
        registry.register("main_db", DataSourceConfig())
        registry.register("secondary_db", DataSourceConfig())
        names = registry.list_all()
        assert "main_db" in names
        assert "secondary_db" in names
        assert len(names) == 2

    def test_set_default(self) -> None:
        """设置默认数据源."""
        registry = DataSourceRegistry()
        registry.register("main_db", DataSourceConfig(database="main"))
        registry.register("secondary_db", DataSourceConfig(database="secondary"))
        registry.set_default("secondary_db")
        assert registry.get_default().database == "secondary"

    def test_set_default_unregistered_raises(self) -> None:
        """设置未注册的默认数据源抛出异常."""
        registry = DataSourceRegistry()
        with pytest.raises(DataSourceRegistryError, match="未注册"):
            registry.set_default("nonexistent")

    def test_len_and_contains(self) -> None:
        """__len__ 和 __contains__ 支持."""
        registry = DataSourceRegistry()
        registry.register("main_db", DataSourceConfig())
        assert len(registry) == 1
        assert "main_db" in registry
        assert "nonexistent" not in registry

    def test_to_connection_dicts(self) -> None:
        """to_connection_dicts 返回 DBExecutor 所需格式."""
        registry = DataSourceRegistry()
        registry.register("main_db", DataSourceConfig(type="mysql", host="h1", database="d1"))
        registry.register("aux_db", DataSourceConfig(type="postgresql", host="h2", database="d2"))
        result = registry.to_connection_dicts()
        assert result["main_db"]["host"] == "h1"
        assert result["main_db"]["database"] == "d1"
        assert result["aux_db"]["type"] == "postgresql"


# ── load_from_config 批量加载测试 ─────────────────────────


class TestLoadFromConfig:
    """load_from_config 批量加载测试."""

    def test_load_from_config_dict(self) -> None:
        """从配置 dict 批量加载."""
        registry = DataSourceRegistry()
        registry.load_from_config({
            "default": "main_db",
            "main_db": {"type": "mysql", "host": "db1", "database": "app"},
            "secondary_db": {"type": "postgresql", "host": "db2", "database": "logs"},
        })
        assert len(registry) == 2
        assert "main_db" in registry
        assert "secondary_db" in registry
        assert registry.get_default().database == "app"

    def test_load_from_config_respects_default(self) -> None:
        """load_from_config 正确设置默认数据源."""
        registry = DataSourceRegistry()
        registry.load_from_config({
            "default": "logs_db",
            "main_db": {"type": "mysql", "host": "db1", "database": "app"},
            "logs_db": {"type": "postgresql", "host": "db2", "database": "logs"},
        })
        assert registry.get_default().database == "logs"

    def test_load_from_config_no_default_field(self) -> None:
        """没有 default 字段时使用默认值 main_db."""
        registry = DataSourceRegistry()
        registry.load_from_config({
            "main_db": {"type": "mysql", "host": "db1", "database": "app"},
        })
        assert registry.get_default().database == "app"

    def test_load_from_config_skip_non_dict_values(self) -> None:
        """跳过非 dict 的配置值."""
        registry = DataSourceRegistry()
        registry.load_from_config({
            "default": "main_db",
            "main_db": {"type": "mysql", "host": "db1", "database": "app"},
            "some_string": "not_a_dict",
        })
        assert "main_db" in registry
        assert "some_string" not in registry


# ── 集成场景测试 ──────────────────────────────────────────


class TestIntegrationScenarios:
    """集成场景测试."""

    def test_full_workflow(self) -> None:
        """完整流程：加载配置 → 查询 → 验证（mock）."""
        registry = DataSourceRegistry()
        registry.load_from_config({
            "default": "main_db",
            "main_db": {
                "type": "sqlite",
                "database": ":memory:",
                "host": "",
                "port": 0,
            },
        })

        # 查询
        config = registry.get("main_db")
        assert config.type == "sqlite"

        # 连接字典
        conn_dicts = registry.to_connection_dicts()
        assert "main_db" in conn_dicts
        assert conn_dicts["main_db"]["type"] == "sqlite"

        # 验证（SQLite in-memory）
        results = registry.validate()
        assert "main_db" in results

    def test_multi_env_datasources(self) -> None:
        """多环境数据源场景：dev 和 staging 有不同数据源."""
        dev_registry = DataSourceRegistry()
        dev_registry.load_from_config({
            "default": "main_db",
            "main_db": {"type": "mysql", "host": "dev-db", "database": "dev_app"},
        })

        staging_registry = DataSourceRegistry()
        staging_registry.load_from_config({
            "default": "main_db",
            "main_db": {"type": "mysql", "host": "staging-db", "database": "staging_app"},
            "analytics_db": {"type": "postgresql", "host": "analytics-db", "database": "analytics"},
        })

        assert dev_registry.get_default().host == "dev-db"
        assert staging_registry.get_default().host == "staging-db"
        assert "analytics_db" in staging_registry
        assert "analytics_db" not in dev_registry
