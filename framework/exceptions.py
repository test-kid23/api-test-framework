"""自定义异常体系 — 所有自定义异常的基类定义

所有框架异常必须继承自 AutoTestException，便于统一捕获和处理。
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError


class AutoTestException(Exception):  # noqa: N818
    """AutoTest Framework 异常基类

    所有自定义异常必须继承此类，支持以下功能：
    - 统一异常类型判断（catch AutoTestException 可捕获所有框架异常）
    - 携带上下文信息（如 trace_id、case_name）
    - 标准化的字符串表示

    Attributes:
        trace_id: 关联的 trace_id，用于日志串联。
    """

    def __init__(self, message: str = "", *, trace_id: str = "") -> None:
        super().__init__(message)
        self.trace_id = trace_id


# ==================== 配置异常 ====================


class ConfigError(AutoTestException):
    """配置相关异常基类"""

    pass


class ConfigNotFoundError(ConfigError):
    """配置文件不存在

    Attributes:
        file_path: 不存在的配置文件路径。
    """

    def __init__(self, file_path: str, *, trace_id: str = "") -> None:
        super().__init__(f"配置文件不存在: {file_path}", trace_id=trace_id)
        self.file_path = file_path


class ConfigValidationError(ConfigError):
    """配置 Schema 校验失败

    Attributes:
        errors: Pydantic 校验错误列表，每项含 loc / msg / type / input。
        field_path: (单字段模式) 校验失败的字段路径。
        expected: (单字段模式) 期望的类型或格式。
        actual: (单字段模式) 实际值。
    """

    def __init__(
        self,
        field_path_or_errors: str | list[dict[str, Any]],
        expected: str = "",
        actual: object = None,
        *,
        trace_id: str = "",
    ) -> None:
        if isinstance(field_path_or_errors, list):
            # 批量错误模式（from pydantic）
            self.errors: list[dict[str, Any]] = field_path_or_errors
            self.field_path = ""
            self.expected = ""
            self.actual = None
            lines = ["配置校验失败:"]
            for err in self.errors:
                loc = ".".join(str(p) for p in err.get("loc", []))
                msg = err.get("msg", "未知错误")
                expected_type = err.get("type", "")
                lines.append(f"  - {loc}: {msg} (type={expected_type})")
            super().__init__("\n".join(lines), trace_id=trace_id)
        else:
            # 单字段模式
            self.errors = []
            self.field_path = field_path_or_errors
            self.expected = expected
            self.actual = actual
            super().__init__(
                f"配置校验失败 [{self.field_path}]: 期望 {expected}, 实际 {actual!r}",
                trace_id=trace_id,
            )

    @classmethod
    def from_pydantic(cls, exc: ValidationError) -> ConfigValidationError:
        """从 Pydantic ValidationError 构造"""
        errors: list[dict[str, Any]] = []
        for e in exc.errors():
            errors.append(
                {
                    "loc": e.get("loc", []),
                    "msg": e.get("msg", ""),
                    "type": e.get("type", ""),
                    "input": e.get("input", None),
                }
            )
        return cls(errors)


# ==================== 执行异常 ====================


class ExecutionError(AutoTestException):
    """测试执行异常基类"""

    pass


class HTTPRequestError(ExecutionError):
    """HTTP 请求失败

    Attributes:
        method: HTTP 方法。
        url: 请求 URL。
        status_code: 响应状态码（如有）。
    """

    def __init__(
        self,
        message: str,
        *,
        method: str = "",
        url: str = "",
        status_code: int | None = None,
        trace_id: str = "",
    ) -> None:
        super().__init__(message, trace_id=trace_id)
        self.method = method
        self.url = url
        self.status_code = status_code


class WSConnectionError(ExecutionError):
    """WebSocket 连接异常"""

    def __init__(self, url: str, detail: str = "", *, trace_id: str = "") -> None:
        super().__init__(
            f"WebSocket 连接失败: {url}" + (f" — {detail}" if detail else ""), trace_id=trace_id
        )
        self.url = url
        self.detail = detail


class RetryExhaustedError(ExecutionError):
    """重试次数耗尽

    Attributes:
        max_retries: 最大重试次数。
        last_error: 最后一次失败的错误信息。
    """

    def __init__(self, max_retries: int, last_error: str = "", *, trace_id: str = "") -> None:
        super().__init__(
            f"重试 {max_retries} 次后仍失败" + (f": {last_error}" if last_error else ""),
            trace_id=trace_id,
        )
        self.max_retries = max_retries
        self.last_error = last_error


class NoExecutorFoundError(ExecutionError):
    """找不到匹配的 StepExecutor

    当 TestCase 既没有配置 request 也没有配置 ws_config 时抛出，
    或遍历所有 executor 均不匹配时抛出。

    Attributes:
        case_name: 触发异常的用例名称。
    """

    def __init__(self, case_name: str, *, trace_id: str = "") -> None:
        super().__init__(f"未找到匹配的 StepExecutor: {case_name}", trace_id=trace_id)
        self.case_name = case_name


class CaseTimeoutError(ExecutionError):
    """用例执行超时

    用例在设定的超时时间内未完成执行时抛出。
    用于 TestRunner.run_case() / arun_case() 超时控制。

    Attributes:
        case_name: 触发超时的用例名称。
        timeout_seconds: 超时阈值（秒）。
        current_step: 超时发生时正在执行的步骤描述。
    """

    def __init__(
        self,
        case_name: str,
        timeout_seconds: int,
        *,
        current_step: str = "",
        trace_id: str = "",
    ) -> None:
        msg = f"用例执行超时 [{case_name}]: 超过 {timeout_seconds}s 限制"
        if current_step:
            msg += f" (当前步骤: {current_step})"
        super().__init__(msg, trace_id=trace_id)
        self.case_name = case_name
        self.timeout_seconds = timeout_seconds
        self.current_step = current_step


# ==================== 断言异常 ====================


class CustomAssertionError(AutoTestException):
    """自定义断言执行异常

    Attributes:
        path: JSONPath 表达式。
        expected: 期望值。
        actual: 实际值。
        operator: 断言操作符。
    """

    def __init__(
        self,
        message: str,
        *,
        path: str = "",
        expected: object = None,
        actual: object = None,
        operator: str = "",
        trace_id: str = "",
    ) -> None:
        super().__init__(message, trace_id=trace_id)
        self.path = path
        self.expected = expected
        self.actual = actual
        self.operator = operator


# ==================== 提取异常 ====================


class ExtractionError(AutoTestException):
    """变量提取异常基类"""

    pass


class ExtractorError(ExtractionError):
    """变量提取失败

    Attributes:
        var_name: 提取失败的变量名。
        source: 提取表达式。
        source_type: 提取类型（jsonpath/header/body_regex 等）。
    """

    def __init__(
        self,
        message: str,
        *,
        var_name: str = "",
        source: str = "",
        source_type: str = "",
        trace_id: str = "",
    ) -> None:
        super().__init__(message, trace_id=trace_id)
        self.var_name = var_name
        self.source = source
        self.source_type = source_type


# ==================== 数据库异常 ====================


class DBError(AutoTestException):
    """数据库操作异常基类"""

    pass


class DBConnectionError(DBError):
    """数据库连接失败"""

    def __init__(self, connection: str, detail: str = "", *, trace_id: str = "") -> None:
        super().__init__(
            f"数据库连接失败 [{connection}]" + (f": {detail}" if detail else ""), trace_id=trace_id
        )
        self.connection = connection
        self.detail = detail


# ==================== 安全异常 ====================


class SecurityError(AutoTestException):
    """安全相关异常

    Attributes:
        command: 被拒绝的命令字符串。
    """

    def __init__(self, message: str, *, command: str = "", trace_id: str = "") -> None:
        super().__init__(message, trace_id=trace_id)
        self.command = command


# ==================== 插件异常 ====================


class PluginError(AutoTestException):
    """插件系统异常基类"""

    pass


class PluginLoadError(PluginError):
    """插件加载失败"""

    def __init__(self, plugin_name: str, detail: str = "", *, trace_id: str = "") -> None:
        super().__init__(
            f"插件加载失败: {plugin_name}" + (f" — {detail}" if detail else ""), trace_id=trace_id
        )
        self.plugin_name = plugin_name
        self.detail = detail
