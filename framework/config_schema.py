"""配置 Schema 校验 — Pydantic v2 模型定义

在 ConfigLoader.load() 合并配置后执行校验，实现启动时配置错误早发现。

设计原则：
- extra="ignore"：允许未知字段，保证向后兼容
- 关键字段有默认值，避免破坏现有配置
- 类型/范围约束在字段级别声明
"""

from __future__ import annotations

from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

# ConfigValidationError 统一由 framework.exceptions 提供（继承自 AutoTestException）
# 此处不再重复定义，仅做 re-export 以保持向后兼容
from framework.exceptions import ConfigValidationError  # noqa: F401

# ═══════════════════════════════════════════════════════════════
# 子配置模型
# ═══════════════════════════════════════════════════════════════


class HttpConfig(BaseModel):
    """HTTP 请求配置

    约束：
    - timeout: 1~300 秒
    - max_retries: 0~10 次
    - base_url: 可为空，若提供则必须是合法 HTTP/HTTPS URL
    """

    model_config = ConfigDict(extra="ignore")

    timeout: int = Field(default=30, ge=1, le=300, description="请求超时时间（秒），范围 1~300")
    verify_ssl: bool = Field(default=False, description="是否验证 SSL 证书")
    max_retries: int = Field(default=0, ge=0, le=10, description="最大重试次数，范围 0~10")
    base_url: AnyHttpUrl | None = Field(default=None, description="基础 URL，可选")


class LoggingConfig(BaseModel):
    """日志配置（基于 structlog 结构化日志）

    level: 日志级别，仅限 DEBUG/INFO/WARNING/ERROR
    format: 控制台输出格式，console（彩色）或 json（JSON 行）
            注：文件日志始终为 JSON 格式，不受此字段影响
    sensitive_fields: 需要脱敏的字段名列表
    """

    model_config = ConfigDict(extra="ignore")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="日志级别"
    )
    format: Literal["console", "json"] = Field(
        default="console", description="控制台日志输出格式；文件日志始终为 JSON"
    )
    sensitive_fields: list[str] = Field(default_factory=list, description="敏感字段脱敏列表")


class ReportConfig(BaseModel):
    """报告配置

    adapter: 报告适配器类型，allure 或 html
    output_dir: 报告输出目录
    """

    model_config = ConfigDict(extra="ignore")

    adapter: Literal["allure", "html"] = Field(default="allure", description="报告适配器")
    output_dir: str = Field(default="reports", description="报告输出目录")


class ExecutionConfig(BaseModel):
    """执行配置

    mode: 执行模式，local 或 distributed
    parallel_workers: 并行工作线程数，1~16
    """

    model_config = ConfigDict(extra="ignore")

    mode: Literal["local", "distributed"] = Field(default="local", description="执行模式")
    parallel_workers: int = Field(default=1, ge=1, le=16, description="并行工作线程数，范围 1~16")


class DBConfig(BaseModel):
    """数据库配置

    driver: 数据库驱动类型
    dsn: 数据源名称 / 连接字符串
    """

    model_config = ConfigDict(extra="ignore")

    driver: Literal["sqlite", "mysql", "postgresql"] = Field(
        default="sqlite", description="数据库驱动类型"
    )
    dsn: str = Field(default="", description="数据源连接字符串")


class PersistenceConfig(BaseModel):
    """持久化配置

    enabled: 是否启用持久化，关闭后测试执行不会写入数据库，适合本地调试。
    """

    model_config = ConfigDict(extra="ignore")

    enabled: bool = Field(default=True, description="是否启用测试结果自动持久化到数据库")


# ═══════════════════════════════════════════════════════════════
# 顶层配置模型
# ═══════════════════════════════════════════════════════════════


class AutotestConfig(BaseModel):
    """自动测试框架顶层配置

    包含所有子配置模块以及当前环境标识。
    校验在 load() 完成合并后调用，实现启动时错误早发现。
    """

    model_config = ConfigDict(extra="ignore")

    env: str = Field(default="dev", description="当前环境名称")
    http: HttpConfig = Field(default_factory=HttpConfig, description="HTTP 请求配置")
    logging: LoggingConfig = Field(default_factory=LoggingConfig, description="日志配置")
    report: ReportConfig = Field(default_factory=ReportConfig, description="报告配置")
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig, description="执行配置")
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig, description="持久化配置")
    db: DBConfig = Field(default_factory=DBConfig, description="数据库配置")
    case_timeout: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="全局默认用例超时时间（秒），范围 1~3600。单个用例可通过 TestCase.timeout 覆盖",
    )
