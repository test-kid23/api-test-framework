"""数据模型定义 — 所有核心数据结构"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ==================== 枚举 ====================


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class AssertOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    MATCHES = "matches"
    IN = "in"
    NOT_IN = "not_in"
    NOT_NULL = "not_null"
    IS_NULL = "is_null"
    TYPE = "type"
    LENGTH = "length"
    BETWEEN = "between"


class BodyType(str, Enum):
    JSON = "json"
    FORM = "form"
    MULTIPART = "multipart"
    RAW = "raw"
    NONE = "none"


# ==================== HTTP ====================


@dataclass
class HttpRequest:
    """HTTP 请求数据模型"""

    method: HttpMethod
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    body: Any = None
    body_type: BodyType = BodyType.JSON
    timeout: int | None = None
    verify_ssl: bool | None = None
    files: dict[str, str] = field(default_factory=dict)
    auth: dict[str, str] | None = None


@dataclass
class HttpResponse:
    """HTTP 响应数据模型"""

    status_code: int
    headers: dict[str, str]
    body: Any
    elapsed_ms: float
    size_bytes: int
    url: str
    request_body: Any = None


# ==================== WebSocket ====================


@dataclass
class WSMessage:
    """WebSocket 消息模型"""

    type: str  # send / receive / close
    data: str | bytes = ""
    opcode: int = 1
    timeout: int | None = None
    expect: dict[str, Any] = field(default_factory=dict)


@dataclass
class WSConfig:
    """WebSocket 配置"""

    url: str
    headers: dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    messages: list[WSMessage] = field(default_factory=list)
    close_after: bool = True


@dataclass
class WSResult:
    """WebSocket 执行结果"""

    received_messages: list[str | bytes] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    total_sent: int = 0
    total_received: int = 0

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


# ==================== 断言 ====================


@dataclass
class AssertItem:
    """单个断言项"""

    path: str
    expected: Any
    operator: str = "eq"
    message: str = ""
    ignore_case: bool = False


@dataclass
class AssertResult:
    """单个断言结果"""

    passed: bool
    path: str
    expected: Any
    actual: Any
    operator: str
    message: str = ""

    def __str__(self) -> str:
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return (
            f"{status} | {self.path} | {self.operator}"
            f" | expected={self.expected} | actual={self.actual}"
        )


@dataclass
class AssertionReport:
    """用例断言报告"""

    results: list[AssertResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    def summary(self) -> str:
        return f"断言 {len(self.results)} 项: {self.pass_count} 通过, {self.fail_count} 失败"


# ==================== 提取 ====================


@dataclass
class ExtractItem:
    """变量提取项"""

    var_name: str
    source: str
    source_type: str = (
        "jsonpath"  # jsonpath / header / body_regex / status_code / elapsed / sql_column
    )
    default: Any = None


# ==================== 数据库 ====================


@dataclass
class DBAction:
    """数据库操作"""

    connection: str
    sql: str
    params: dict[str, Any] = field(default_factory=dict)
    extract: list[ExtractItem] = field(default_factory=list)
    fetch_one: bool = False


@dataclass
class DBAssertItem:
    """数据库断言项"""

    connection: str
    sql: str
    expect: dict[str, Any] = field(default_factory=dict)
    fetch_one: bool = True


# ==================== Fixture ====================


@dataclass
class FixtureAction:
    """Fixture 中的单个动作"""

    action_type: str  # api_call / db_execute / wait / shell
    config: dict[str, Any] = field(default_factory=dict)


# ==================== 测试用例 ====================


@dataclass
class TestCase:
    """解析后的完整测试用例"""

    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    priority: str = "P1"
    skip: bool = False
    skip_if: str = ""

    variables: dict[str, Any] = field(default_factory=dict)

    request: HttpRequest | None = None
    ws_config: WSConfig | None = None

    assertions: list[AssertItem] = field(default_factory=list)
    extracts: list[ExtractItem] = field(default_factory=list)
    db_asserts: list[DBAssertItem] = field(default_factory=list)

    setup: list[FixtureAction] = field(default_factory=list)
    teardown: list[FixtureAction] = field(default_factory=list)

    timeout: int | None = None


@dataclass
class TestSuite:
    """测试套件"""

    name: str
    description: str = ""
    base_url: str = ""
    tags: list[str] = field(default_factory=list)
    priority: str = "P1"
    variables: dict[str, Any] = field(default_factory=dict)
    setup: list[FixtureAction] = field(default_factory=list)
    teardown: list[FixtureAction] = field(default_factory=list)
    cases: list[TestCase] = field(default_factory=list)
    data_driven: list[dict[str, Any]] = field(default_factory=list)


# ==================== 配置 ====================


@dataclass
class EnvConfig:
    """环境配置"""

    name: str
    base_url: str = ""
    ws_url: str = ""
    variables: dict[str, Any] = field(default_factory=dict)
    http: dict[str, Any] = field(default_factory=dict)
    db: dict[str, dict[str, Any]] = field(default_factory=dict)
    ws: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectConfig:
    """项目全局配置"""

    project_name: str = "API Test Suite"
    version: str = "1.0.0"
    http: dict[str, Any] = field(default_factory=dict)
    logging: dict[str, Any] = field(default_factory=dict)
    report: dict[str, Any] = field(default_factory=dict)
    assertion: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    db: dict[str, dict[str, Any]] = field(default_factory=dict)
    fixtures: dict[str, Any] = field(default_factory=dict)


# ==================== 执行结果 ====================


@dataclass
class CaseResult:
    """单个用例执行结果"""

    case_name: str
    passed: bool
    assertion_report: AssertionReport | None = None
    error: str | None = None
    request: HttpRequest | None = None
    response: HttpResponse | None = None
    url: str = ""
    elapsed_ms: float = 0.0
    extracted_vars: dict[str, Any] = field(default_factory=dict)


@dataclass
class SuiteResult:
    """套件执行结果"""

    suite_name: str
    case_results: list[CaseResult] = field(default_factory=list)
    setup_error: str | None = None
    teardown_error: str | None = None

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.case_results) and not self.setup_error

    @property
    def total(self) -> int:
        return len(self.case_results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.case_results if r.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.case_results if not r.passed)
