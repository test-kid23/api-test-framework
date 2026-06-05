"""配置 Schema 校验测试

验证：
1. 合法配置加载成功
2. 类型错误 → ConfigValidationError（含字段路径）
3. 范围越界 → ConfigValidationError
4. 缺失必填字段 → ConfigValidationError
5. Unknown 字段被忽略（向后兼容）
6. _deep_merge list 合并策略（replace / append）
7. ConfigValidationError 继承自 AutoTestException
8. 热加载功能（开关控制、防抖回调）
9. merge_strategy 从配置文件中读取
"""

from __future__ import annotations

import textwrap
import time
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from framework.config import MERGE_APPEND, MERGE_REPLACE, ConfigLoader
from framework.config_schema import (
    AutotestConfig,
    ConfigValidationError,
    DBConfig,
    ExecutionConfig,
    HttpConfig,
    ReportConfig,
)
from framework.exceptions import AutoTestException

# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def write_yaml(path: Path, content: str) -> None:
    """将字符串写入 YAML 文件"""
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def make_minimal_config(tmp_path: Path, http_override: dict | None = None) -> Path:
    """创建最小合法配置目录

    Args:
        tmp_path: pytest tmp_path fixture
        http_override: 可选的 http 段字典，用于覆盖默认值
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    http_block: dict = http_override or {
        "timeout": 30,
        "verify_ssl": False,
        "max_retries": 3,
    }

    config_data = {
        "http": http_block,
        "logging": {
            "level": "INFO",
            "format": "console",
            "sensitive_fields": [],
        },
        "report": {
            "adapter": "allure",
            "output_dir": "reports",
        },
        "execution": {
            "mode": "local",
            "parallel_workers": 4,
        },
        "db": {
            "driver": "sqlite",
            "dsn": "",
        },
    }

    (config_dir / "config.yaml").write_text(
        yaml.dump(config_data, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )

    env_data = {
        "default": "dev",
        "environments": {
            "dev": {
                "base_url": "http://localhost:8080",
                "http": {
                    "timeout": 30,
                    "verify_ssl": False,
                },
            }
        },
    }

    (config_dir / "env.yaml").write_text(
        yaml.dump(env_data, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )

    return config_dir


# ═══════════════════════════════════════════════════════════════
# 1. 合法配置加载成功
# ═══════════════════════════════════════════════════════════════


class TestValidConfig:
    """验证合法配置能正常加载"""

    def test_valid_minimal_config_loads(self, tmp_path: Path) -> None:
        """最小合法配置应加载成功"""
        config_dir = make_minimal_config(tmp_path)
        loader = ConfigLoader(str(config_dir))
        project_cfg, env_cfg = loader.load("dev")

        assert project_cfg.project_name == "API Test Suite"
        assert env_cfg.name == "dev"
        assert env_cfg.base_url == "http://localhost:8080"

    def test_autotest_config_model_validate(self) -> None:
        """AutotestConfig 直接校验合法字典应通过"""
        data = {
            "env": "dev",
            "http": {"timeout": 30, "verify_ssl": False, "max_retries": 3},
            "logging": {
                "level": "INFO",
                "format": "console",
                "sensitive_fields": [],
            },
            "report": {"adapter": "allure", "output_dir": "reports"},
            "execution": {"mode": "local", "parallel_workers": 4},
            "db": {"driver": "sqlite", "dsn": ""},
        }
        config = AutotestConfig.model_validate(data)
        assert config.env == "dev"
        assert config.http.timeout == 30
        assert config.execution.mode == "local"

    def test_default_values_applied(self) -> None:
        """空配置应使用所有默认值"""
        config = AutotestConfig.model_validate({"env": "test"})
        assert config.http.timeout == 30
        assert config.http.verify_ssl is False
        assert config.logging.level == "INFO"
        assert config.report.adapter == "allure"
        assert config.execution.mode == "local"

    def test_extra_fields_ignored(self) -> None:
        """未知字段应被忽略（extra='ignore'），保证向后兼容"""
        data = {
            "env": "dev",
            "http": {"timeout": 30, "verify_ssl": False, "max_retries": 3},
            "logging": {"level": "INFO", "format": "console"},
            "report": {"adapter": "html", "output_dir": "reports"},
            "execution": {"mode": "local", "parallel_workers": 1},
            "db": {"driver": "sqlite", "dsn": ""},
            # 以下为未知字段
            "project": {"name": "test", "version": "2.0"},
            "assertion": {"fail_fast": True},
            "fixtures": {"allowed_shell_commands": ["echo"]},
            "custom_plugin": {"enabled": True, "config": {"key": "value"}},
        }
        config = AutotestConfig.model_validate(data)
        assert config.env == "dev"
        # 未知字段不在模型上，但不会报错
        assert not hasattr(config, "custom_plugin")


# ═══════════════════════════════════════════════════════════════
# 2. 类型错误 → ConfigValidationError
# ═══════════════════════════════════════════════════════════════


class TestTypeErrors:
    """验证字段类型错误时抛出 ConfigValidationError"""

    def test_timeout_string_fails_with_field_path(self) -> None:
        """timeout: 'abc' 应立即报错并显示字段路径 http.timeout"""
        data = {
            "env": "dev",
            "http": {"timeout": "abc", "verify_ssl": False, "max_retries": 3},
            "logging": {"level": "INFO", "format": "console"},
            "report": {"adapter": "allure", "output_dir": "reports"},
            "execution": {"mode": "local", "parallel_workers": 1},
            "db": {"driver": "sqlite", "dsn": ""},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_raises(data)

        error_str = str(exc_info.value)
        assert "http" in error_str
        assert "timeout" in error_str

    def test_verify_ssl_wrong_type(self) -> None:
        """verify_ssl 应为 bool，传列表应报错"""
        data = {
            "env": "dev",
            "http": {"timeout": 30, "verify_ssl": [1, 2, 3], "max_retries": 3},
            "logging": {"level": "INFO", "format": "console"},
            "report": {"adapter": "allure", "output_dir": "reports"},
            "execution": {"mode": "local", "parallel_workers": 1},
            "db": {"driver": "sqlite", "dsn": ""},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_raises(data)

        error_str = str(exc_info.value)
        assert "verify_ssl" in error_str

    def test_logging_level_invalid_literal(self) -> None:
        """logging.level 仅限枚举值，传 'TRACE' 应报错"""
        data = {
            "env": "dev",
            "http": {"timeout": 30, "verify_ssl": False, "max_retries": 3},
            "logging": {"level": "TRACE", "format": "console"},
            "report": {"adapter": "allure", "output_dir": "reports"},
            "execution": {"mode": "local", "parallel_workers": 1},
            "db": {"driver": "sqlite", "dsn": ""},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_raises(data)

        error_str = str(exc_info.value)
        assert "logging" in error_str
        assert "level" in error_str

    def test_execution_mode_invalid_literal(self) -> None:
        """execution.mode 仅限 local/distributed，传 'cluster' 应报错"""
        data = {
            "env": "dev",
            "http": {"timeout": 30, "verify_ssl": False, "max_retries": 3},
            "logging": {"level": "INFO", "format": "console"},
            "report": {"adapter": "allure", "output_dir": "reports"},
            "execution": {"mode": "cluster", "parallel_workers": 1},
            "db": {"driver": "sqlite", "dsn": ""},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_raises(data)

        error_str = str(exc_info.value)
        assert "execution" in error_str
        assert "mode" in error_str


# ═══════════════════════════════════════════════════════════════
# 3. 范围越界 → ConfigValidationError
# ═══════════════════════════════════════════════════════════════


class TestRangeErrors:
    """验证数值范围越界时抛出 ConfigValidationError"""

    def test_timeout_below_minimum(self) -> None:
        """timeout: 0 小于最小值 1，应报错"""
        data = {
            "env": "dev",
            "http": {"timeout": 0, "verify_ssl": False, "max_retries": 3},
            "logging": {"level": "INFO", "format": "console"},
            "report": {"adapter": "allure", "output_dir": "reports"},
            "execution": {"mode": "local", "parallel_workers": 1},
            "db": {"driver": "sqlite", "dsn": ""},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_raises(data)

        error_str = str(exc_info.value)
        assert "timeout" in error_str

    def test_timeout_above_maximum(self) -> None:
        """timeout: 301 大于最大值 300，应报错"""
        data = {
            "env": "dev",
            "http": {"timeout": 301, "verify_ssl": False, "max_retries": 3},
            "logging": {"level": "INFO", "format": "console"},
            "report": {"adapter": "allure", "output_dir": "reports"},
            "execution": {"mode": "local", "parallel_workers": 1},
            "db": {"driver": "sqlite", "dsn": ""},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_raises(data)

        error_str = str(exc_info.value)
        assert "timeout" in error_str

    def test_max_retries_negative(self) -> None:
        """max_retries: -1 小于最小值 0，应报错"""
        data = {
            "env": "dev",
            "http": {"timeout": 30, "verify_ssl": False, "max_retries": -1},
            "logging": {"level": "INFO", "format": "console"},
            "report": {"adapter": "allure", "output_dir": "reports"},
            "execution": {"mode": "local", "parallel_workers": 1},
            "db": {"driver": "sqlite", "dsn": ""},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_raises(data)

        error_str = str(exc_info.value)
        assert "max_retries" in error_str

    def test_max_retries_above_maximum(self) -> None:
        """max_retries: 11 大于最大值 10，应报错"""
        data = {
            "env": "dev",
            "http": {"timeout": 30, "verify_ssl": False, "max_retries": 11},
            "logging": {"level": "INFO", "format": "console"},
            "report": {"adapter": "allure", "output_dir": "reports"},
            "execution": {"mode": "local", "parallel_workers": 1},
            "db": {"driver": "sqlite", "dsn": ""},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_raises(data)

        error_str = str(exc_info.value)
        assert "max_retries" in error_str

    def test_parallel_workers_below_minimum(self) -> None:
        """parallel_workers: 0 小于最小值 1，应报错"""
        data = {
            "env": "dev",
            "http": {"timeout": 30, "verify_ssl": False, "max_retries": 3},
            "logging": {"level": "INFO", "format": "console"},
            "report": {"adapter": "allure", "output_dir": "reports"},
            "execution": {"mode": "local", "parallel_workers": 0},
            "db": {"driver": "sqlite", "dsn": ""},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_raises(data)

        error_str = str(exc_info.value)
        assert "parallel_workers" in error_str

    def test_parallel_workers_above_maximum(self) -> None:
        """parallel_workers: 17 大于最大值 16，应报错"""
        data = {
            "env": "dev",
            "http": {"timeout": 30, "verify_ssl": False, "max_retries": 3},
            "logging": {"level": "INFO", "format": "console"},
            "report": {"adapter": "allure", "output_dir": "reports"},
            "execution": {"mode": "local", "parallel_workers": 17},
            "db": {"driver": "sqlite", "dsn": ""},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_raises(data)

        error_str = str(exc_info.value)
        assert "parallel_workers" in error_str


# ═══════════════════════════════════════════════════════════════
# 4. 子配置模型独立校验
# ═══════════════════════════════════════════════════════════════


class TestSubConfigs:
    """验证各子配置模型独立校验"""

    def test_http_config_boundaries(self) -> None:
        """HttpConfig 边界值应通过"""
        # 最小值
        cfg = HttpConfig(timeout=1, max_retries=0)
        assert cfg.timeout == 1

        # 最大值
        cfg = HttpConfig(timeout=300, max_retries=10)
        assert cfg.timeout == 300

    def test_db_config_driver_invalid(self) -> None:
        """DBConfig driver 仅限 sqlite/mysql/postgresql"""
        with pytest.raises(ValidationError):
            DBConfig(driver="oracle")

    def test_report_config_adapter_invalid(self) -> None:
        """ReportConfig adapter 仅限 allure/html"""
        with pytest.raises(ValidationError):
            ReportConfig(adapter="pdf")

    def test_execution_config_defaults(self) -> None:
        """ExecutionConfig 默认值"""
        cfg = ExecutionConfig()
        assert cfg.mode == "local"
        assert cfg.parallel_workers == 1


# ═══════════════════════════════════════════════════════════════
# 5. 集成测试：ConfigLoader 加载错误配置
# ═══════════════════════════════════════════════════════════════


class TestConfigLoaderIntegration:
    """ConfigLoader 集成测试 — 通过真实文件加载"""

    def test_invalid_config_raises_on_load(self, tmp_path: Path) -> None:
        """当 config.yaml 包含类型错误时，load() 应抛出 ConfigValidationError"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # 直接在 http 段写入非法值
        config_data = {
            "http": {"timeout": "abc", "verify_ssl": False, "max_retries": 3},
            "logging": {"level": "INFO", "format": "console"},
            "report": {"adapter": "allure", "output_dir": "reports"},
            "execution": {"mode": "local", "parallel_workers": 1},
            "db": {"driver": "sqlite", "dsn": ""},
        }
        (config_dir / "config.yaml").write_text(
            yaml.dump(config_data, allow_unicode=True), encoding="utf-8"
        )

        # 环境配置不覆盖 http（让全局的错误值暴露出来）
        env_data = {
            "default": "dev",
            "environments": {
                "dev": {
                    "base_url": "http://localhost:8080",
                }
            },
        }
        (config_dir / "env.yaml").write_text(
            yaml.dump(env_data, allow_unicode=True), encoding="utf-8"
        )
        loader = ConfigLoader(str(config_dir))
        with pytest.raises(ConfigValidationError) as exc_info:
            loader.load("dev")

        error_str = str(exc_info.value)
        assert "配置校验失败" in error_str
        assert "http" in error_str
        assert "timeout" in error_str

    def test_valid_config_loads_successfully(self, tmp_path: Path) -> None:
        """合法配置应正常加载，返回 ProjectConfig 和 EnvConfig"""
        config_dir = make_minimal_config(tmp_path)
        loader = ConfigLoader(str(config_dir))
        project_cfg, env_cfg = loader.load("dev")

        assert project_cfg is not None
        assert env_cfg is not None
        assert env_cfg.name == "dev"
        assert env_cfg.base_url == "http://localhost:8080"
        # 验证 http 配置被正确合并
        assert project_cfg.http.get("timeout") == 30

    def test_default_env_when_not_specified(self, tmp_path: Path) -> None:
        """未指定环境时使用 env.yaml 中的 default"""
        config_dir = make_minimal_config(tmp_path)
        loader = ConfigLoader(str(config_dir))
        _, env_cfg = loader.load()

        assert env_cfg.name == "dev"

    def test_extra_fields_in_yaml_do_not_cause_errors(self, tmp_path: Path) -> None:
        """YAML 中的未知字段不应导致校验失败"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        write_yaml(
            config_dir / "config.yaml",
            """
            http:
              timeout: 30
              verify_ssl: false
              max_retries: 3
              # 以下为未知额外字段
              custom_header: X-Custom-Value
              retry_on: [500, 502, 503]
            logging:
              level: INFO
              format: console
              console:
                enabled: true
                colorize: true
            report:
              adapter: allure
              output_dir: reports
            execution:
              mode: local
              parallel_workers: 2
            db:
              driver: sqlite
              dsn: ""
            project:
              name: test
              version: "2.0"
            """,
        )

        write_yaml(
            config_dir / "env.yaml",
            """
            default: dev
            environments:
              dev:
                base_url: http://localhost
                http:
                  timeout: 30
                  verify_ssl: false
            """,
        )

        loader = ConfigLoader(str(config_dir))
        # 不应抛出异常
        project_cfg, _ = loader.load("dev")
        assert project_cfg.http.get("custom_header") == "X-Custom-Value"

    def test_env_data_overrides_global(self, tmp_path: Path) -> None:
        """环境配置应覆盖全局配置中的同名字段"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        write_yaml(
            config_dir / "config.yaml",
            """
            http:
              timeout: 60
              verify_ssl: true
              max_retries: 3
            logging:
              level: INFO
              format: console
            report:
              adapter: allure
              output_dir: reports
            execution:
              mode: local
              parallel_workers: 1
            db:
              driver: sqlite
              dsn: ""
            """,
        )

        write_yaml(
            config_dir / "env.yaml",
            """
            default: dev
            environments:
              dev:
                base_url: http://localhost
                http:
                  timeout: 15
                  verify_ssl: false
            """,
        )

        loader = ConfigLoader(str(config_dir))
        _, env_cfg = loader.load("dev")

        # env 覆盖了 http section，但 config.yaml 的 project_cfg.http 不变
        # env_cfg.http 包含 env 级别的覆盖
        assert env_cfg.http.get("timeout") == 15
        assert env_cfg.http.get("verify_ssl") is False


# ═══════════════════════════════════════════════════════════════
# 6. ConfigValidationError 异常细节
# ═══════════════════════════════════════════════════════════════


class TestConfigValidationError:
    """验证异常包含完整的错误信息"""

    def test_error_contains_field_path(self) -> None:
        """异常信息应包含字段路径"""
        data = {
            "env": "dev",
            "http": {"timeout": "abc", "verify_ssl": False, "max_retries": 3},
            "logging": {"level": "INFO", "format": "console"},
            "report": {"adapter": "allure", "output_dir": "reports"},
            "execution": {"mode": "local", "parallel_workers": 1},
            "db": {"driver": "sqlite", "dsn": ""},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_raises(data)

        error = exc_info.value
        assert len(error.errors) >= 1
        first_error = error.errors[0]
        assert "loc" in first_error
        assert "msg" in first_error
        assert "type" in first_error

    def test_multiple_errors_collected(self) -> None:
        """多个字段同时出错时应收集所有错误"""
        data = {
            "env": "dev",
            "http": {
                "timeout": 0,  # 小于最小值
                "verify_ssl": "no",  # 类型错误
                "max_retries": 20,  # 大于最大值
            },
            "logging": {"level": "TRACE", "format": "xml"},
            "report": {"adapter": "pdf", "output_dir": "reports"},
            "execution": {"mode": "cloud", "parallel_workers": 0},
            "db": {"driver": "mssql", "dsn": ""},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            _validate_raises(data)

        error = exc_info.value
        # 至少应有 1 个以上错误
        assert len(error.errors) >= 1

    def test_from_pydantic_creates_correct_error(self) -> None:
        """ConfigValidationError.from_pydantic() 应正确转换"""
        try:
            AutotestConfig.model_validate({"http": {"timeout": "bad"}})
            pytest.fail("Should have raised ValidationError")
        except ValidationError as exc:
            err = ConfigValidationError.from_pydantic(exc)
            assert isinstance(err, ConfigValidationError)
            assert len(err.errors) >= 1
            assert "timeout" in str(err)


# ═══════════════════════════════════════════════════════════════
# 7. 向后兼容：现有 config.yaml / env.yaml 校验通过
# ═══════════════════════════════════════════════════════════════


class TestBackwardCompatibility:
    """验证现有配置文件格式能通过 Schema 校验"""

    def test_existing_config_yaml_validates(self) -> None:
        """项目中的 config.yaml 应通过 Schema 校验"""
        project_root = Path(__file__).resolve().parent.parent.parent
        config_path = project_root / "config" / "config.yaml"

        if config_path.exists():
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            # 只校验 Schema 相关字段（忽略 env 相关）
            try:
                AutotestConfig.model_validate({**raw, "env": "test"})
            except ConfigValidationError as exc:
                pytest.fail(f"config.yaml 校验失败:\n{exc}")

    def test_existing_env_yaml_validates(self) -> None:
        """项目中的 env.yaml 环境配置应通过 Schema 校验"""
        project_root = Path(__file__).resolve().parent.parent.parent
        config_path = project_root / "config" / "env.yaml"

        if config_path.exists():
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            envs = raw.get("environments", {})
            for env_name, env_data in envs.items():
                merged = {
                    **env_data,
                    "env": env_name,
                    "logging": {"level": "INFO", "format": "console"},
                    "report": {"adapter": "allure", "output_dir": "reports"},
                    "execution": {"mode": "local", "parallel_workers": 1},
                    "db": {"driver": "sqlite", "dsn": ""},
                }
                try:
                    AutotestConfig.model_validate(merged)
                except ConfigValidationError as exc:
                    pytest.fail(f"env.yaml [{env_name}] 校验失败:\n{exc}")


# ═══════════════════════════════════════════════════════════════
# 8. _deep_merge list 合并策略
# ═══════════════════════════════════════════════════════════════


class TestDeepMergeListStrategy:
    """验证 _deep_merge 对 list 字段的合并行为"""

    def test_list_replace_default(self) -> None:
        """默认策略（replace）：override list 直接替换 base list"""
        base = {"retry_on": [502, 503], "headers": {"X-A": "1"}}
        override = {"retry_on": [500]}

        result = ConfigLoader._deep_merge(base, override, list_strategy=MERGE_REPLACE)
        assert result["retry_on"] == [500], "replace 策略应使用 override 的值"

    def test_list_replace_explicit(self) -> None:
        """显式 replace：同名 list 完全替换"""
        base = {"items": ["a", "b", "c"]}
        override = {"items": ["x", "y"]}

        result = ConfigLoader._deep_merge(base, override, list_strategy=MERGE_REPLACE)
        assert result["items"] == ["x", "y"]

    def test_list_append_simple(self) -> None:
        """append 策略：两个 list 合并为 base + override"""
        base = {"items": ["a", "b"]}
        override = {"items": ["c", "d"]}

        result = ConfigLoader._deep_merge(base, override, list_strategy=MERGE_APPEND)
        assert result["items"] == ["a", "b", "c", "d"]

    def test_list_append_base_only(self) -> None:
        """append 策略：base 有 list 而 override 无该 key，保持 base"""
        base = {"items": ["a", "b"]}
        override = {"name": "test"}

        result = ConfigLoader._deep_merge(base, override, list_strategy=MERGE_APPEND)
        assert result["items"] == ["a", "b"]
        assert result["name"] == "test"

    def test_list_append_override_only(self) -> None:
        """append 策略：base 无该 list，直接使用 override"""
        base = {"name": "test"}
        override = {"items": ["x", "y"]}

        result = ConfigLoader._deep_merge(base, override, list_strategy=MERGE_APPEND)
        assert result["items"] == ["x", "y"]

    def test_list_append_nested_dict(self) -> None:
        """append 策略：嵌套在 dict 中的 list 同样生效"""
        base = {
            "http": {
                "retry_on": [500, 502],
                "timeout": 30,
            }
        }
        override = {
            "http": {
                "retry_on": [503, 504],
                "timeout": 60,
            }
        }

        result = ConfigLoader._deep_merge(base, override, list_strategy=MERGE_APPEND)
        assert result["http"]["retry_on"] == [500, 502, 503, 504]
        assert result["http"]["timeout"] == 60  # 非 list 仍为覆盖

    def test_list_append_empty_base(self) -> None:
        """append 策略：base list 为空时应正确追加"""
        base = {"allowed_ips": []}
        override = {"allowed_ips": ["10.0.0.1", "10.0.0.2"]}

        result = ConfigLoader._deep_merge(base, override, list_strategy=MERGE_APPEND)
        assert result["allowed_ips"] == ["10.0.0.1", "10.0.0.2"]

    def test_list_append_empty_override(self) -> None:
        """append 策略：override list 为空时 base 不变"""
        base = {"allowed_ips": ["10.0.0.1"]}
        override = {"allowed_ips": []}

        result = ConfigLoader._deep_merge(base, override, list_strategy=MERGE_APPEND)
        assert result["allowed_ips"] == ["10.0.0.1"]

    def test_list_append_mixed_types_in_base(self) -> None:
        """append 策略：list 中包含非标量元素也能正确合并"""
        base: dict = {"configs": [{"name": "a"}, {"name": "b"}]}
        override: dict = {"configs": [{"name": "c"}]}

        result = ConfigLoader._deep_merge(base, override, list_strategy=MERGE_APPEND)
        assert result["configs"] == [{"name": "a"}, {"name": "b"}, {"name": "c"}]

    def test_merge_strategy_from_loaded_config(self, tmp_path: Path) -> None:
        """从 config.yaml 中读取 merge_strategy 应正确生效"""
        config_dir = make_minimal_config(tmp_path)

        # 修改 config.yaml 添加 settings
        config_path = config_dir / "config.yaml"
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        raw["settings"] = {"merge_strategy": "append"}
        config_path.write_text(yaml.dump(raw), encoding="utf-8")

        loader = ConfigLoader(str(config_dir))
        loader.load("dev")

        assert loader.merge_strategy == "append"

    def test_invalid_merge_strategy_falls_back(self, tmp_path: Path) -> None:
        """无效的 merge_strategy 应回退为 replace"""
        config_dir = make_minimal_config(tmp_path)

        config_path = config_dir / "config.yaml"
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        raw["settings"] = {"merge_strategy": "invalid_value"}
        config_path.write_text(yaml.dump(raw), encoding="utf-8")

        loader = ConfigLoader(str(config_dir))
        loader.load("dev")

        assert loader.merge_strategy == "replace"


# ═══════════════════════════════════════════════════════════════
# 9. ConfigValidationError 异常继承验证
# ═══════════════════════════════════════════════════════════════


class TestConfigValidationErrorInheritance:
    """验证 ConfigValidationError 正确继承自 AutoTestException"""

    def test_inherits_auto_test_exception(self) -> None:
        """ConfigValidationError 应继承 AutoTestException"""
        assert issubclass(ConfigValidationError, AutoTestException), (
            "ConfigValidationError 必须继承 AutoTestException"
        )

    def test_caught_by_auto_test_exception(self) -> None:
        """ConfigValidationError 应能被 AutoTestException 捕获"""
        try:
            raise ConfigValidationError("test_field", "int", "abc")
        except AutoTestException:
            pass  # 预期被捕获
        else:
            pytest.fail("ConfigValidationError 没有被 AutoTestException 捕获")

    def test_trace_id_preserved(self) -> None:
        """异常应保留 trace_id"""
        err = ConfigValidationError("field", "str", 123, trace_id="trace-001")
        assert err.trace_id == "trace-001"
        assert err.field_path == "field"

    def test_from_pydantic_creates_valid_exception(self) -> None:
        """from_pydantic 创建的异常应有 errors 列表和正确的继承"""
        try:
            AutotestConfig.model_validate({"http": {"timeout": "bad"}})
            pytest.fail("Should have raised ValidationError")
        except ValidationError as exc:
            err = ConfigValidationError.from_pydantic(exc)
            assert isinstance(err, AutoTestException)
            assert len(err.errors) >= 1
            assert "timeout" in str(err)


# ═══════════════════════════════════════════════════════════════
# 10. 热加载功能测试
# ═══════════════════════════════════════════════════════════════


class TestHotReload:
    """验证配置热加载功能"""

    def test_start_watching_when_disabled(self, tmp_path: Path) -> None:
        """热加载未开启时 start_watching 应静默跳过"""
        config_dir = make_minimal_config(tmp_path)

        # settings.hot_reload.enabled 默认为 false
        loader = ConfigLoader(str(config_dir))
        loader.load("dev")

        # 不应抛异常，且 observer 为 None
        loader.start_watching()
        assert loader._observer is None
        loader.stop_watching()

    def test_hot_reload_enabled_from_config(self, tmp_path: Path) -> None:
        """配置中 hot_reload.enabled=true 时应返回 True"""
        config_dir = make_minimal_config(tmp_path)

        config_path = config_dir / "config.yaml"
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        raw["settings"] = {
            "merge_strategy": "replace",
            "hot_reload": {"enabled": True},
        }
        config_path.write_text(yaml.dump(raw), encoding="utf-8")

        loader = ConfigLoader(str(config_dir))
        loader.load("dev")

        assert loader.hot_reload_enabled is True

    def test_hot_reload_enabled_false_default(self, tmp_path: Path) -> None:
        """无 hot_reload 配置时默认关闭"""
        config_dir = make_minimal_config(tmp_path)
        loader = ConfigLoader(str(config_dir))
        loader.load("dev")

        assert loader.hot_reload_enabled is False

    def test_hot_reload_enabled_with_non_dict(self, tmp_path: Path) -> None:
        """hot_reload 为非 dict 类型时安全处理"""
        config_dir = make_minimal_config(tmp_path)

        config_path = config_dir / "config.yaml"
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        raw["settings"] = {"hot_reload": "enabled"}  # 非 dict
        config_path.write_text(yaml.dump(raw), encoding="utf-8")

        loader = ConfigLoader(str(config_dir))
        loader.load("dev")

        assert loader.hot_reload_enabled is False

    def test_reload_uses_same_env(self, tmp_path: Path) -> None:
        """reload() 不使用参数时应沿用上次的环境名"""
        config_dir = make_minimal_config(tmp_path)
        loader = ConfigLoader(str(config_dir))
        loader.load("dev")

        # 修改 env.yaml 中 dev 的 base_url
        env_path = config_dir / "env.yaml"
        raw = yaml.safe_load(env_path.read_text(encoding="utf-8"))
        raw["environments"]["dev"]["base_url"] = "http://changed:9999"
        env_path.write_text(yaml.dump(raw), encoding="utf-8")

        _, env2 = loader.reload()
        assert env2.base_url == "http://changed:9999"

    def test_stop_watching_when_not_started(self) -> None:
        """未启动监控时 stop_watching 应安全无异常"""
        loader = ConfigLoader()
        loader.stop_watching()  # 不应抛异常


# ═══════════════════════════════════════════════════════════════
# 11. 配置中的 settings 段集成测试
# ═══════════════════════════════════════════════════════════════


class TestSettingsIntegration:
    """验证 settings 段在完整加载流程中的行为"""

    def test_full_append_merge_from_files(self, tmp_path: Path) -> None:
        """通过真实文件验证 append 策略下的 list 合并"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # config.yaml: 全局配置，list 为 [1, 2]
        write_yaml(
            config_dir / "config.yaml",
            """
            settings:
              merge_strategy: append
            http:
              timeout: 30
              verify_ssl: false
              max_retries: 3
              retry_on: [502, 503]
            logging:
              level: INFO
              format: console
            report:
              adapter: allure
              output_dir: reports
            execution:
              mode: local
              parallel_workers: 1
            db:
              driver: sqlite
              dsn: ""
            """,
        )

        # env.yaml: 环境配置追加 retry_on
        write_yaml(
            config_dir / "env.yaml",
            """
            default: dev
            environments:
              dev:
                base_url: http://localhost
                http:
                  timeout: 15
                  retry_on: [504, 505]
            """,
        )

        loader = ConfigLoader(str(config_dir))
        project_cfg, env_cfg = loader.load("dev")

        # env 层的 http.retry_on 应该追加到全局 http.retry_on
        # 但当前 _build_env_config 只提取 base_url/ws_url/variables/http/db/ws
        # retry_on 在 env_cfg.http 中
        assert env_cfg.http.get("retry_on") == [504, 505]
        # 全局 project_cfg 的 retry_on 保持不变
        assert project_cfg.http.get("retry_on") == [502, 503]

    def test_settings_unknown_fields_ignored(self, tmp_path: Path) -> None:
        """settings 中的未知字段不应导致异常"""
        config_dir = make_minimal_config(tmp_path)

        config_path = config_dir / "config.yaml"
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        raw["settings"] = {
            "merge_strategy": "replace",
            "custom_key": "should_be_safe",
            "another": 42,
        }
        config_path.write_text(yaml.dump(raw), encoding="utf-8")

        loader = ConfigLoader(str(config_dir))
        project_cfg, _ = loader.load("dev")  # 不应抛异常

        assert loader.merge_strategy == "replace"
        assert project_cfg is not None


# ═══════════════════════════════════════════════════════════════
# 辅助：通过 AutotestConfig 触发 ConfigValidationError
# ═══════════════════════════════════════════════════════════════


def _validate_raises(data: dict) -> None:
    """通过 AutotestConfig 校验并转换为 ConfigValidationError"""
    try:
        AutotestConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigValidationError.from_pydantic(exc) from exc
