"""数据模型定义 — 所有核心数据结构"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ==================== 枚举 ====================


class CaseStatus(str, Enum):
    """用例执行状态"""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


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
    """HTTP 请求数据模型

    Attributes:
        method: HTTP 方法 (GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS)。
        path: 请求路径（相对于 base_url）。
        headers: 请求头字典。
        params: URL 查询参数。
        body: 请求体内容。
        body_type: 请求体编码类型 (json/form/multipart/raw/none)。
        timeout: 单次请求超时秒数（为 None 时使用全局默认）。
        verify_ssl: 是否校验 SSL 证书。
        files: 文件上传路径映射。
        auth: 认证信息 (username/password)。
    """

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
    """HTTP 响应数据模型

    Attributes:
        status_code: HTTP 状态码。
        headers: 响应头字典。
        body: 解析后的响应体（JSON 自动解析为 dict/list，失败时保留原始文本）。
        elapsed_ms: 请求耗时（毫秒）。
        size_bytes: 响应体字节数。
        url: 实际请求 URL。
        request_body: 请求体快照（用于日志/报告）。
    """

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
    """WebSocket 消息模型

    Attributes:
        type: 消息方向 (send/receive/close)。
        data: 消息内容（文本或二进制）。
        opcode: WebSocket 操作码。
        timeout: 接收消息超时秒数。
        expect: 期望收到的消息字段及值。
    """

    type: str  # send / receive / close
    data: str | bytes = ""
    opcode: int = 1
    timeout: int | None = None
    expect: dict[str, Any] = field(default_factory=dict)


@dataclass
class WSConfig:
    """WebSocket 配置

    Attributes:
        url: WebSocket 服务端点 URL。
        headers: 连接请求头。
        timeout: 连接超时秒数。
        messages: 发送/接收的消息序列。
        close_after: 是否在所有消息完成后自动关闭连接。
    """

    url: str
    headers: dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    messages: list[WSMessage] = field(default_factory=list)
    close_after: bool = True


@dataclass
class WSResult:
    """WebSocket 执行结果

    Attributes:
        received_messages: 接收到的消息列表。
        errors: 执行过程中的错误列表。
        total_sent: 发送消息总数。
        total_received: 接收消息总数。
    """

    received_messages: list[str | bytes] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    total_sent: int = 0
    total_received: int = 0

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


# ==================== gRPC ====================


@dataclass
class GrpcConfig:
    """gRPC 调用配置

    Attributes:
        service: 完整的 gRPC 服务名（package.ServiceName）。
        method: 要调用的方法名。
        proto_file: proto 文件路径（用于动态加载服务定义）。
        proto_dir: proto 文件搜索目录（用于 import 解析，默认与 proto_file 同目录）。
        host: gRPC 服务地址（host:port），支持模板变量。
        body: 请求消息体（dict，键为字段名）。
        metadata: gRPC 元数据（key-value 对）。
        timeout: 调用超时秒数（为 None 时使用全局默认）。
        tls: 是否启用 TLS。
        tls_ca_cert: CA 证书路径（TLS 时可选）。
        reflection: 是否使用服务反射获取服务定义（优先于 proto_file）。
    """

    service: str
    method: str
    proto_file: str = ""
    proto_dir: str = ""
    host: str = "localhost:50051"
    body: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    timeout: int | None = None
    tls: bool = False
    tls_ca_cert: str = ""
    reflection: bool = False


@dataclass
class GrpcResult:
    """gRPC 调用结果

    Attributes:
        service: 调用的服务名。
        method: 调用的方法名。
        host: 实际连接地址。
        request_body: 发送的请求消息体。
        response_body: 收到的响应消息体（protobuf → dict）。
        elapsed_ms: 调用耗时（毫秒）。
        status_code: gRPC 状态码（grpc.StatusCode 的值）。
        status_detail: gRPC 状态详情。
        metadata: 响应元数据（trailing metadata）。
        success: 调用是否成功。
    """

    service: str
    method: str
    host: str
    request_body: dict[str, Any] = field(default_factory=dict)
    response_body: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0
    status_code: int = 0
    status_detail: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    success: bool = True


# ==================== 断言 ====================


@dataclass
class AssertItem:
    """单个断言项

    Attributes:
        path: 断言目标路径（status_code/response_time/body.xxx/headers.xxx/$.jsonpath）。
        expected: 期望值。
        operator: 断言操作符（eq/ne/gt/lt/contains/matches 等）。
        message: 自定义失败消息。
        ignore_case: 字符串比较时是否忽略大小写。
    """

    path: str
    expected: Any
    operator: str = "eq"
    message: str = ""
    ignore_case: bool = False


@dataclass
class CompositeAssertItem:
    """组合断言项 — 支持 AND/OR 嵌套组合多个子断言.

    Attributes:
        combinator: 组合逻辑（"all_of" 表示 AND，"any_of" 表示 OR）。
        children: 子断言项列表（可以是 AssertItem 或其他 CompositeAssertItem）。
        message: 自定义失败消息。

    Note:
        子断言可以是普通 AssertItem 或嵌套的 CompositeAssertItem，
        支持任意深度嵌套。
    """

    combinator: str  # "all_of" | "any_of"
    children: list[AssertItem | CompositeAssertItem] = field(default_factory=list)
    message: str = ""

    def __post_init__(self) -> None:
        if self.combinator not in ("all_of", "any_of"):
            raise ValueError(
                f"combinator 必须为 'all_of' 或 'any_of'，实际为 '{self.combinator}'"
            )


@dataclass
class AssertResult:
    """单个断言结果

    Attributes:
        passed: 断言是否通过。
        path: 断言目标路径。
        expected: 期望值。
        actual: 实际值。
        operator: 断言操作符。
        message: 失败时的错误消息。
    """

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
    """用例断言报告

    Attributes:
        results: 所有断言项的逐条结果（扁平化收集）。
    """

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
    """变量提取项

    Attributes:
        var_name: 提取结果存储的变量名。
        source: 提取表达式（JSONPath/header 名/正则等）。
        source_type: 提取源类型（jsonpath/header/body_regex/status_code/elapsed/sql_column/pipeline）。
        default: 提取失败时的默认值。
        pipeline: 可选的提取管道步骤列表（当 source_type="pipeline" 时使用）。
    """

    var_name: str
    source: str
    source_type: str = (
        "jsonpath"  # jsonpath / header / body_regex / status_code / elapsed / sql_column / pipeline
    )
    default: Any = None
    pipeline: list[dict[str, Any]] | None = None


# ==================== 数据库 ====================


@dataclass
class DBAction:
    """数据库操作

    Attributes:
        connection: 数据源名称。
        sql: SQL 语句（支持模板变量）。
        params: SQL 参数绑定。
        extract: 从结果中提取的变量列表。
        fetch_one: True 返回单行，False 返回多行。
    """

    connection: str
    sql: str
    params: dict[str, Any] = field(default_factory=dict)
    extract: list[ExtractItem] = field(default_factory=list)
    fetch_one: bool = False


@dataclass
class DBAssertItem:
    """数据库断言项

    Attributes:
        connection: 数据源名称。
        sql: 断言的 SQL 查询。
        expect: 期望的字段名→值映射。
        fetch_one: True 断言单行，False 断言多行。
    """

    connection: str
    sql: str
    expect: dict[str, Any] = field(default_factory=dict)
    fetch_one: bool = True


# ==================== Fixture ====================


@dataclass
class FixtureAction:
    """Fixture 中的单个动作

    Attributes:
        action_type: 动作类型（api_call/db_execute/wait/shell/mock_setup/mock_teardown）。
        config: 动作配置参数。
    """

    action_type: str  # api_call / db_execute / wait / shell / mock_setup / mock_teardown
    config: dict[str, Any] = field(default_factory=dict)


# ==================== 测试用例 ====================


@dataclass
class TestCase:
    """解析后的完整测试用例

    Attributes:
        name: 用例名称。
        description: 用例描述。
        tags: 标签列表（如 smoke, regression, P0）。
        priority: 优先级（P0/P1/P2/P3）。
        skip: 是否跳过。
        skip_if: 条件跳过表达式。
        variables: 用例级变量。
        request: HTTP 请求配置（与 ws_config 二选一）。
        ws_config: WebSocket 配置（与 request 二选一）。
        assertions: 断言项列表。
        extracts: 变量提取项列表。
        db_asserts: 数据库断言项列表。
        setup: 前置操作列表。
        teardown: 后置操作列表。
        timeout: 用例超时秒数（为 None 时使用全局默认）。
    """

    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    priority: str = "P1"
    skip: bool = False
    skip_if: str = ""

    variables: dict[str, Any] = field(default_factory=dict)

    request: HttpRequest | None = None
    ws_config: WSConfig | None = None
    grpc_config: GrpcConfig | None = None

    assertions: list[AssertItem | CompositeAssertItem] = field(default_factory=list)
    extracts: list[ExtractItem] = field(default_factory=list)
    db_asserts: list[DBAssertItem] = field(default_factory=list)

    setup: list[FixtureAction] = field(default_factory=list)
    teardown: list[FixtureAction] = field(default_factory=list)

    timeout: int | None = None


@dataclass
class TestSuite:
    """测试套件

    Attributes:
        name: 套件名称。
        description: 套件描述。
        base_url: 套件级基础 URL（覆盖全局默认）。
        tags: 套件标签。
        priority: 默认优先级（用例可单独覆盖）。
        variables: 套件级变量（用例可继承和覆盖）。
        setup: 套件级前置操作。
        teardown: 套件级后置操作。
        cases: 包含的测试用例列表。
        data_driven: 数据驱动参数列表，每个元素为一组变量覆盖。
    """

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
    """环境配置

    Attributes:
        name: 环境名称（dev/staging/production）。
        base_url: 被测服务的 HTTP 基础 URL。
        ws_url: WebSocket 服务 URL。
        variables: 环境级变量（全局可用）。
        http: HTTP 客户端配置（timeout/verify_ssl 等）。
        db: 数据库连接配置（数据源名称→连接参数）。
        ws: WebSocket 配置。
    """

    name: str
    base_url: str = ""
    ws_url: str = ""
    variables: dict[str, Any] = field(default_factory=dict)
    http: dict[str, Any] = field(default_factory=dict)
    db: dict[str, dict[str, Any]] = field(default_factory=dict)
    datasources: dict[str, Any] = field(default_factory=dict)
    ws: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectConfig:
    """项目全局配置

    Attributes:
        project_name: 项目名称。
        version: 版本号。
        http: HTTP 客户端全局默认配置。
        logging: 日志配置（level/format/console/file）。
        report: 报告配置（adapter 类型等）。
        assertion: 断言引擎配置。
        execution: 执行配置（并发度等）。
        db: 数据库连接配置。
        fixtures: Fixture 全局配置。
        notifications: 通知服务配置。
        persistence: 持久化开关与配置。
        settings: 通用设置（merge_strategy/hot_reload 等）。
        case_timeout: 全局用例超时秒数。
    """

    project_name: str = "API Test Suite"
    version: str = "1.0.0"
    http: dict[str, Any] = field(default_factory=dict)
    logging: dict[str, Any] = field(default_factory=dict)
    report: dict[str, Any] = field(default_factory=dict)
    assertion: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    db: dict[str, dict[str, Any]] = field(default_factory=dict)
    datasources: dict[str, Any] = field(default_factory=dict)
    fixtures: dict[str, Any] = field(default_factory=dict)
    notifications: dict[str, Any] = field(default_factory=dict)
    persistence: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    mock: dict[str, Any] = field(default_factory=dict)
    recorder: dict[str, Any] = field(default_factory=dict)
    case_timeout: int = 300
    jwt_secret: str = "autotest-default-secret-change-me"
    jwt_expire_minutes: int = 480


# ==================== 执行结果 ====================


@dataclass
class CaseResult:
    """单个用例执行结果

    Attributes:
        case_name: 用例名称。
        passed: 是否通过。
        status: 执行状态（PASS/FAIL/SKIP/TIMEOUT/ERROR）。
        assertion_report: 断言报告（如有）。
        error: 失败时的错误信息。
        request: 请求快照。
        response: 响应快照。
        url: 实际请求 URL。
        elapsed_ms: 执行耗时（毫秒）。
        extracted_vars: 提取的变量字典。
    """

    case_name: str
    passed: bool
    status: CaseStatus = CaseStatus.PASS
    assertion_report: AssertionReport | None = None
    error: str | None = None
    request: HttpRequest | None = None
    response: HttpResponse | None = None
    url: str = ""
    elapsed_ms: float = 0.0
    extracted_vars: dict[str, Any] = field(default_factory=dict)


@dataclass
class SuiteResult:
    """套件执行结果

    Attributes:
        suite_name: 套件名称。
        case_results: 套件内所有用例的执行结果。
        setup_error: 套件级 setup 失败信息。
        teardown_error: 套件级 teardown 失败信息。
    """

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
