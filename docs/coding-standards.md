# AutoTest Framework 工程规范

> **适用版本**: v1.0.0+  
> **制定日期**: 2026-06-03  
> **技术栈基线**: Python 3.12+ | pytest 8.x | httpx 0.28.x | Pydantic 2.10.x  
> **关联文档**: [开发计划](./development-plan.md) | [架构评审](./architecture-review.md)

---

## 目录

1. [Python 版本与语言特性](#1-python-版本与语言特性)
2. [类型注解规范](#2-类型注解规范)
3. [文档字符串规范](#3-文档字符串规范)
4. [路径处理规范](#4-路径处理规范)
5. [异步编程规范](#5-异步编程规范)
6. [数据库操作规范](#6-数据库操作规范)
7. [配置管理规范](#7-配置管理规范)
8. [日志规范](#8-日志规范)
9. [测试规范](#9-测试规范)
10. [异常处理规范](#10-异常处理规范)
11. [代码风格与工具链](#11-代码风格与工具链)
12. [项目结构规范](#12-项目结构规范)
13. [前端规范（Phase 4+）](#13-前端规范phase-4)

---

## 1. Python 版本与语言特性

### 1.1 版本要求

项目最低要求 **Python 3.12.3+**，`pyproject.toml` 中声明：

```toml
[project]
requires-python = ">=3.12"
```

### 1.2 必须使用的 3.12 新特性

#### `type` 语句（PEP 695）

使用 `type` 语句声明类型别名，替代传统的 `TypeAlias`：

```python
# ✅ 正确 — PEP 695 type 语句
type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
type CaseNameMap = dict[str, TestCase]

# ❌ 错误 — 旧式 TypeAlias
from typing import TypeAlias
JsonValue: TypeAlias = str | int | float | bool | None | list[...] | dict[...]
```

#### PEP 695 泛型语法（`type` 语句含类型参数）

使用新式泛型语法，替代 `TypeVar`：

```python
# ✅ 正确 — PEP 695 泛型
type Response[T] = dict[str, T | list[T]]

class Repository[T]:
    def find_by_id(self, id: int) -> T | None: ...

# ❌ 错误 — 旧式 TypeVar
from typing import TypeVar
T = TypeVar("T")

class Repository(Generic[T]):
    def find_by_id(self, id: int) -> Optional[T]: ...
```

#### `|` 联合类型

替代 `Optional[X]` 和 `Union[X, Y]`：

```python
# ✅ 正确
def get_user(user_id: int) -> User | None: ...
def process(data: str | bytes) -> int: ...

# ❌ 错误
from typing import Optional, Union
def get_user(user_id: int) -> Optional[User]: ...
def process(data: Union[str, bytes]) -> int: ...
```

#### 其他推荐使用的 3.12 特性

| 特性 | 说明 |
|------|------|
| `@override` 装饰器 | 标记方法为重写，编译时检查 |
| `f-string` 增强 | 支持更复杂的表达式 |
| `pathlib.Path.walk()` | 目录遍历 |
| `itertools.batched()` | 批量迭代 |

---

## 2. 类型注解规范

### 2.1 强制要求

所有公共函数、方法、类属性 **必须有完整类型注解**：

```python
# ✅ 正确 — 完整类型注解
class HttpClient:
    def __init__(self, config: dict[str, Any], base_url: str) -> None: ...

    def request(
        self,
        method: HttpMethod,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        body: Any = None,
        timeout: int = 30,
    ) -> HttpResponse: ...

# ❌ 错误 — 缺少类型注解
class HttpClient:
    def __init__(self, config, base_url): ...

    def request(self, method, path, **kwargs):
        ...
```

### 2.2 私有方法

私有方法（单下划线前缀）也应有类型注解，但不强制完整 docstring：

```python
# ✅ 正确 — 私有方法有基本类型注解
def _build_url(self, base: str, path: str, params: dict[str, Any]) -> str:
    ...
```

### 2.3 `from __future__ import annotations`

所有文件顶部应包含此导入，确保类型注解延迟求值：

```python
from __future__ import annotations
```

### 2.4 built-in 容器泛型

优先使用 built-in 容器泛型，避免从 `typing` 导入：

```python
# ✅ 正确
def process(items: list[str], mapping: dict[str, int]) -> tuple[int, str]: ...

# ❌ 错误
from typing import List, Dict, Tuple
def process(items: List[str], mapping: Dict[str, int]) -> Tuple[int, str]: ...
```

---

## 3. 文档字符串规范

### 3.1 格式要求

使用 **Google 风格 docstring**，所有公共函数/方法/类必须有。

### 3.2 模块级 docstring

```python
"""模块简要说明 — 一行概述

详细说明可以多段，描述模块职责、设计决策、使用示例。
"""
```

### 3.3 函数/方法 docstring

```python
def load(self, env_name: str | None = None) -> tuple[ProjectConfig, EnvConfig]:
    """加载完整配置

    配置合并顺序（后覆盖前）：
    1. config.yaml（全局默认）
    2. env.yaml 中对应环境的配置
    3. env.local.yaml（本地覆盖）
    4. OS 环境变量覆盖

    Args:
        env_name: 环境名称，为 None 时使用 env.yaml 中的 default。

    Returns:
        (ProjectConfig, EnvConfig) 元组。

    Raises:
        ConfigNotFoundError: 配置文件不存在时抛出。
        ConfigValidationError: 配置内容不符合 Schema 时抛出。
    """
```

### 3.4 类 docstring

```python
class TestRunner:
    """测试执行引擎

    负责编排单个 TestCase 的执行流程，包括：
    - 模板变量渲染
    - HTTP/WS 请求发送
    - 断言执行
    - 变量提取

    Attributes:
        config: 项目全局配置。
        env: 当前环境配置。
        http_client: HTTP 客户端实例。
        db_manager: 数据库连接管理器。
        context: 测试上下文（线程安全）。

    Example:
        >>> runner = TestRunner(config, env, client, db, ctx)
        >>> result = runner.run_case(test_case, variables)
        >>> print(result.passed)
        True
    """
```

### 3.5 属性 docstring（dataclass）

```python
@dataclass
class HttpRequest:
    """HTTP 请求数据模型

    Attributes:
        method: HTTP 方法。
        path: 请求路径（相对于 base_url）。
        headers: 请求头字典。
        params: URL 查询参数。
        body: 请求体。
        body_type: 请求体编码类型。
        timeout: 超时时间（秒）。
        verify_ssl: 是否校验 SSL 证书。
        files: 文件上传路径映射。
        auth: 认证信息。
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
```

---

## 4. 路径处理规范

### 4.1 强制使用 pathlib

**禁止字符串拼接路径**，所有路径操作使用 `pathlib.Path`：

```python
# ✅ 正确 — pathlib
from pathlib import Path

config_dir = Path("config")
config_file = config_dir / "config.yaml"
log_path = Path("logs") / "test.log"
log_path.parent.mkdir(parents=True, exist_ok=True)

# ❌ 错误 — 字符串拼接
config_file = "config" + "/" + "config.yaml"
log_path = "logs\\test.log"
os.path.join("config", "config.yaml")  # 禁止
```

### 4.2 函数参数

接收路径参数的函数应接受 `str | Path`：

```python
from pathlib import Path
from typing import Any

def load_yaml(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {file_path}")
    ...
```

### 4.3 路径操作常用模式

| 操作 | 写法 |
|------|------|
| 拼接 | `base_dir / "sub" / "file.yaml"` |
| 创建目录 | `path.parent.mkdir(parents=True, exist_ok=True)` |
| 读取文件 | `path.read_text(encoding="utf-8")` |
| 写入文件 | `path.write_text(content, encoding="utf-8")` |
| 遍历文件 | `list(path.glob("*.yaml"))` 或 `path.walk()` |
| 相对路径 | `path.relative_to(base)` |

---

## 5. 异步编程规范

### 5.1 基本原则

- 异步代码使用 `async/await` 和 `asyncio`
- **禁止使用回调**（callback）
- 异步和同步代码明确分层

### 5.2 异步客户端

HTTP 客户端应提供异步变体：

```python
# ✅ 正确 — 异步客户端
import httpx

class AsyncHttpClient:
    def __init__(self, config: dict[str, Any], base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=config.get("timeout", 30),
        )

    async def request(
        self, method: str, path: str, *, body: Any = None
    ) -> dict[str, Any]:
        response = await self._client.request(method, path, json=body)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()

# ❌ 错误 — 使用回调
def request(method, path, callback):
    ...
```

### 5.3 Runner 异步方法

```python
class TestRunner:
    async def arun_case(
        self, case: TestCase, variables: dict[str, Any]
    ) -> CaseResult:
        """异步执行单个测试用例"""
        ctx = TestContext()
        ctx.init()

        # 使用异步客户端
        response = await self._async_client.request(
            method=case.request.method,
            path=case.request.path,
            body=case.request.body,
        )

        ...
        return result
```

### 5.4 FastAPI 路由

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])

@router.get("/{case_id}")
async def get_case(
    case_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> CaseResponse:
    repo = CaseRepository(session)
    case = await repo.find_by_id(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="用例不存在")
    return CaseResponse.model_validate(case)
```

### 5.5 事件循环管理

```python
import asyncio

# 在非异步环境中启动异步代码
# ✅ 正确
result = asyncio.run(main_async())

# ❌ 错误 — 不要手动管理事件循环
loop = asyncio.get_event_loop()
loop.run_until_complete(main_async())
```

---

## 6. 数据库操作规范

### 6.1 ORM

使用 **SQLAlchemy 2.0** 异步会话：

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
async_session = async_sessionmaker(engine, expire_on_commit=False)
```

### 6.2 Repository 模式

所有数据库操作通过 Repository 封装，不允许直接在业务代码中写 SQL：

```python
# ✅ 正确 — Repository 模式
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

class BaseRepository[T]:
    """Repository 基类

    定义通用 CRUD 操作，子类可按需扩展查询方法。

    Attributes:
        session: SQLAlchemy 异步会话。
        model: 对应的 ORM 模型类。
    """

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self._session = session
        self._model = model

    async def find_by_id(self, id: int) -> T | None:
        return await self._session.get(self._model, id)

    async def find_all(self, *, limit: int = 100, offset: int = 0) -> list[T]:
        stmt = select(self._model).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def save(self, entity: T) -> T:
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def delete(self, entity: T) -> None:
        await self._session.delete(entity)
        await self._session.flush()


class CaseRepository(BaseRepository):
    """测试用例仓储"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TestCaseModel)

    async def find_by_tag(self, tag: str) -> list[TestCaseModel]:
        stmt = select(TestCaseModel).where(TestCaseModel.tags.contains([tag]))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
```

```python
# ❌ 错误 — 直接在业务代码中写 SQL
async def get_case(case_id: int) -> dict:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT * FROM test_cases WHERE id = :id"),
            {"id": case_id},
        )
        return dict(result.mappings().first())
```

### 6.3 会话管理

使用 FastAPI 依赖注入管理会话生命周期：

```python
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
```

### 6.4 豁免：测试引擎 Raw SQL

**DBExecutor 的 raw SQL 执行不适用 Repository 模式。**

`framework/db.py` 中 `DBExecutor.execute()` 直接使用 `engine.connect()` 执行 raw SQL 是测试引擎的功能需求——用户在 YAML 测试用例中编写的 `sql_column` 提取本身就是自由 SQL，不属于"业务数据操作"。此类 raw SQL 执行作为例外，不强制走 Repository。

### 6.5 迁移

所有表结构变更通过 **Alembic** 管理，禁止手动修改数据库：

```bash
# 生成迁移
alembic revision --autogenerate -m "add test_cases table"

# 执行迁移
alembic upgrade head
```

---

## 7. 配置管理规范

### 7.1 配置加载

通过 `ConfigLoader` 单例获取配置，**禁止在模块内直接读取文件**：

```python
# ✅ 正确 — 通过 ConfigLoader
from framework.config import ConfigLoader

loader = ConfigLoader()
project_config, env_config = loader.load(env_name="dev")

# ❌ 错误 — 直接读取文件
import yaml
with open("config/config.yaml") as f:
    config = yaml.safe_load(f)
```

### 7.2 配置类设计

所有配置类使用 `@dataclass` 定义，属性有类型注解：

```python
@dataclass
class HttpConfig:
    """HTTP 客户端配置"""
    timeout: int = 30
    max_retries: int = 3
    verify_ssl: bool = True
    follow_redirects: bool = True
    headers: dict[str, str] = field(default_factory=dict)
```

### 7.3 配置验证

使用 Pydantic v2 在加载时校验：

```python
from pydantic import BaseModel, Field

class LoggingConfigModel(BaseModel):
    """日志配置 Schema"""
    level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = Field(default="text", pattern=r"^(text|json)$")
    console: ConsoleConfigModel = Field(default_factory=ConsoleConfigModel)
    file: FileConfigModel = Field(default_factory=FileConfigModel)
```

---

## 8. 日志规范

### 8.1 日志引擎

统一使用 **structlog** 作为结构化日志引擎（Phase 1 引入）：

```python
import structlog

logger = structlog.get_logger(__name__)
```

> **封装层保留说明**：项目当前使用 `Logger.get("xxx")`（`framework/utils/logger.py`）作为 structlog 的统一封装，底层已确保使用 structlog 引擎并自动绑定 trace_id。此封装层保留，不强制要求改为直接调用 `structlog.get_logger()`。

### 8.2 trace_id

每条日志 **必须** 附带 `trace_id`，用于串联完整调用链：

```python
import structlog
import uuid

logger = structlog.get_logger(__name__)

def process_case(case_name: str) -> None:
    trace_id = str(uuid.uuid4())
    log = logger.bind(trace_id=trace_id)

    log.info("开始执行用例", case_name=case_name)
    # ...
    log.info("用例执行完成", case_name=case_name, passed=True)
```

输出示例（JSON 格式）：

```json
{
  "event": "开始执行用例",
  "trace_id": "a1b2c3d4-...",
  "case_name": "test_login",
  "level": "info",
  "timestamp": "2026-06-03T13:36:00Z"
}
```

### 8.3 日志级别使用指南

| 级别 | 使用场景 |
|------|---------|
| `DEBUG` | 详细的调试信息，如请求/响应完整内容 |
| `INFO` | 关键流程节点，如配置加载完成、用例开始/结束 |
| `WARNING` | 非预期但可处理的情况，如重试、降级 |
| `ERROR` | 操作失败但系统可继续，如单个用例失败 |
| `CRITICAL` | 系统无法继续运行，如配置加载失败 |

### 8.4 敏感信息脱敏

请求/响应日志必须通过 `SensitiveDataMasker` 脱敏：

```python
from framework.utils.masker import SensitiveDataMasker

masker = SensitiveDataMasker()
safe_headers = masker.mask_dict(request.headers)
logger.debug("发送请求", url=url, headers=safe_headers)
```

---

## 9. 测试规范

### 9.1 测试框架

- 测试框架：**pytest 8.x**
- Mock 工具：**pytest-mock**（`mocker` fixture）
- 覆盖率：**pytest-cov**

### 9.2 覆盖率目标

| 模块 | 最低覆盖率 |
|------|-----------|
| `assertion.py` | ≥ 90% |
| `extractor.py` | ≥ 85% |
| `runner.py` | ≥ 80% |
| `config.py` | ≥ 85% |
| `context.py` | ≥ 90% |
| **核心模块整体** | **≥ 85%** |

### 9.3 测试目录结构

```
tests/
├── __init__.py
├── conftest.py                    # 测试专用 fixtures
├── framework/
│   ├── test_assertion.py
│   ├── test_extractor.py
│   ├── test_runner.py
│   ├── test_client.py
│   ├── test_config.py
│   ├── test_context.py
│   ├── utils/
│   │   ├── test_template.py
│   │   ├── test_masker.py
│   │   └── test_retry.py
│   └── ...
└── smoke/                        # 冒烟测试
    └── test_all_existing_cases.py
```

### 9.4 测试编写规范

```python
"""Tests for framework.extractor — 变量提取器单元测试"""

from __future__ import annotations

import pytest
from framework.extractor import Extractor
from framework.models import ExtractItem


class TestExtractor:
    """变量提取器测试"""

    def test_extract_jsonpath_basic(self) -> None:
        """基本 JSONPath 提取能正确返回值"""
        extractor = Extractor()
        item = ExtractItem(
            var_name="user_id",
            source="$.data.id",
            source_type="jsonpath",
        )
        response_data = {"data": {"id": 42, "name": "test"}}

        result = extractor.extract(item, response_data)

        assert result == 42
        assert isinstance(result, int)

    def test_extract_with_default_value(self) -> None:
        """JSONPath 不存在时返回默认值"""
        extractor = Extractor()
        item = ExtractItem(
            var_name="missing",
            source="$.data.missing_field",
            source_type="jsonpath",
            default="N/A",
        )
        response_data = {"data": {}}

        result = extractor.extract(item, response_data)

        assert result == "N/A"

    def test_extract_empty_response_raises(self) -> None:
        """空响应体应抛出 ExtractorError"""
        extractor = Extractor()
        item = ExtractItem(
            var_name="x", source="$.a", source_type="jsonpath"
        )

        with pytest.raises(ExtractorError):
            extractor.extract(item, None)
```

### 9.5 Mock 使用

```python
from pytest_mock import MockerFixture

def test_runner_with_mock_http(
    mocker: MockerFixture,
    runner: TestRunner,
    sample_case: TestCase,
) -> None:
    """Mock HTTP 响应，验证 runner 流程"""
    mock_response = HttpResponse(
        status_code=200,
        headers={},
        body={"status": "ok"},
        elapsed_ms=100.0,
        size_bytes=42,
        url="http://test/api",
    )

    mocker.patch.object(
        runner._http_client,
        "request",
        return_value=mock_response,
    )

    result = runner.run_case(sample_case, {})

    assert result.passed
    runner._http_client.request.assert_called_once()
```

### 9.6 运行命令

```bash
# 运行全部测试
pytest tests/ -v

# 带覆盖率
pytest tests/ -v --cov=framework --cov-report=term --cov-report=html

# 仅运行冒烟测试
pytest tests/smoke/ -v

# 仅运行特定模块
pytest tests/framework/test_assertion.py -v
```

---

## 10. 异常处理规范

### 10.1 异常基类

所有自定义异常 **必须** 继承自 `AutoTestException` 基类：

```python
# ✅ 正确 — 继承 AutoTestException
from framework.exceptions import AutoTestException


class ConfigValidationError(AutoTestException):
    """配置校验失败异常"""
    pass


class ExtractorError(AutoTestException):
    """变量提取异常

    Attributes:
        var_name: 提取失败的变量名。
        source: 提取表达式。
        source_type: 提取类型。
    """

    def __init__(
        self,
        message: str,
        var_name: str = "",
        source: str = "",
        source_type: str = "",
    ) -> None:
        super().__init__(message)
        self.var_name = var_name
        self.source = source
        self.source_type = source_type


class RetryExhaustedError(AutoTestException):
    """重试次数耗尽异常"""
    pass
```

```python
# ❌ 错误 — 直接继承 Exception
class MyError(Exception):
    pass
```

### 10.2 异常层次结构

```
AutoTestException
├── ConfigError
│   ├── ConfigNotFoundError
│   └── ConfigValidationError
├── ExecutionError
│   ├── HTTPRequestError
│   ├── WSConnectionError
│   └── RetryExhaustedError
├── AssertionError
│   └── CustomAssertionError
├── ExtractionError
│   └── ExtractorError
├── DBError
│   └── DBConnectionError
└── PluginError
    └── PluginLoadError
```

### 10.3 异常使用原则

1. 不要在 `except` 块中静默吞掉异常
2. 捕获具体异常类型，避免裸 `except Exception`
3. 异常信息应包含足够的上下文（哪个操作失败、关键参数值）
4. 框架层异常统一转换为 `AutoTestException` 子类

```python
# ✅ 正确 — 具体异常 + 上下文
try:
    response = self._client.request(method, path, json=body)
except httpx.TimeoutException:
    raise HTTPRequestError(
        f"请求超时: {method.value} {path} (timeout={timeout}s)"
    )
except httpx.HTTPStatusError as e:
    raise HTTPRequestError(
        f"请求失败: {method.value} {path} -> {e.response.status_code}"
    )

# ❌ 错误 — 裸 except
try:
    response = self._client.request(method, path, json=body)
except Exception:
    pass
```

---

## 11. 代码风格与工具链

### 11.1 格式化

| 工具 | 用途 | 配置 |
|------|------|------|
| **black** | 代码格式化 | 行长度 100 |
| **isort** | import 排序 | black 兼容模式 |
| **ruff** | Linter | 替代 flake8 |

### 11.2 静态检查

| 工具 | 用途 |
|------|------|
| **mypy** | 静态类型检查（strict 模式） |
| **ruff** | 代码质量检查 |

### 11.3 Pre-commit

所有代码提交前必须通过 pre-commit 钩子：

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black
  - repo: https://github.com/PyCQA/isort
    rev: 5.13.2
    hooks:
      - id: isort
```

### 11.4 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块/文件 | `snake_case` | `http_client.py` |
| 类名 | `PascalCase` | `HttpClient` |
| 函数/方法 | `snake_case` | `send_request()` |
| 变量 | `snake_case` | `base_url` |
| 常量 | `UPPER_SNAKE_CASE` | `DEFAULT_TIMEOUT` |
| 私有成员 | `_leading_underscore` | `_build_url()` |
| 模块私有 | `_leading_underscore` | `_internal.py` |

### 11.5 Import 规范

```python
# 1. 标准库
from __future__ import annotations

import asyncio
from pathlib import Path

# 2. 第三方库
import httpx
import structlog
from sqlalchemy import select

# 3. 项目内部
from framework.config import ConfigLoader
from framework.exceptions import AutoTestException
from framework.models import TestCase, CaseResult
```

- 使用 `isort` 自动排序，profile 设为 `black`
- 禁止 `import *`
- 禁止在模块顶层进行有副作用的导入

---

## 12. 项目结构规范

### 12.1 目录职责

```
api-test-framework/
├── api/                    # FastAPI REST 服务层 (Phase 2+)
├── assertions/             # 内置断言操作符扩展
├── config/                 # 配置文件目录
├── docs/                   # 项目文档
├── framework/              # 核心框架代码
│   ├── assertion/          # 断言引擎
│   ├── executors/          # 步骤执行器（策略模式）
│   ├── interceptors/       # HTTP 拦截器链
│   ├── persistence/        # 数据持久化层
│   │   ├── models/         # SQLAlchemy ORM 模型
│   │   └── repositories/   # Repository 实现
│   ├── plugins/            # 插件系统
│   ├── report/             # 报告引擎
│   └── utils/              # 工具模块
├── testcases/              # YAML 测试用例
├── test_data/              # 测试数据文件
├── tests/                  # 单元测试与冒烟测试 (Phase 1+)
└── frontend/               # Web 前端 (Phase 4+)
```

### 12.2 文件命名

- 每个模块对应一个 `__init__.py`，仅包含导出和版本信息
- 单一职责：一个文件只做一件事
- 单文件不超过 400 行（超出行数后拆分子模块）

### 12.3 依赖方向

```
api (REST 层)
  └── framework (核心框架)
       ├── persistence (数据层)
       └── utils (工具层)
```

- 上层依赖下层，下层不依赖上层
- 框架层不依赖 API 层
- 工具层不依赖业务层

---

## 13. 前端规范（Phase 4+）

### 13.1 技术栈

| 组件 | 版本 | 说明 |
|------|------|------|
| **React** | 18.x | UI 框架 |
| **TypeScript** | 5.x | 类型安全 |
| **Vite** | 5.x | 构建工具 |
| **Tailwind CSS** | 3.x | 原子化 CSS |
| **shadcn/ui** | latest | UI 组件库 |
| **Zustand** | 4.x | 状态管理 |

### 13.2 UI 组件库

使用 **shadcn/ui**（https://github.com/shadcn-ui/ui）作为主要组件库：

- 基于 Radix UI 原语 + Tailwind CSS 样式
- 通过 `npx shadcn-ui@latest add` 按需安装组件
- 组件源码属于项目自身，可完全定制
- 禁止引入其他重量级 UI 库（如 Ant Design、Element Plus）

### 13.3 目录结构

```
frontend/
├── src/
│   ├── components/         # 可复用组件
│   │   └── ui/             # shadcn/ui 组件
│   ├── pages/              # 页面组件
│   ├── hooks/              # 自定义 React Hooks
│   ├── lib/                # 工具函数
│   ├── stores/             # Zustand 状态管理
│   ├── types/              # TypeScript 类型定义
│   └── api/                # API 调用封装
├── public/
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.ts
```

---

## 附录

### A. 检查清单

CR（Code Review）时逐项检查：

- [ ] Python ≥ 3.12 特性使用正确（`type` 语句、`|` 联合类型）
- [ ] 所有公共函数/方法有完整类型注解
- [ ] Google 风格 docstring 完整
- [ ] 使用 `pathlib` 处理所有路径
- [ ] 异步代码使用 `async/await`，无回调
- [ ] 数据库操作通过 Repository，不裸写 SQL
- [ ] 配置通过 `ConfigLoader` 获取
- [ ] 日志使用 `structlog` 并附带 `trace_id`
- [ ] 单元测试覆盖率达标（核心模块 ≥ 85%）
- [ ] 自定义异常继承自 `AutoTestException`
- [ ] pre-commit 钩子全部通过

### B. 修订记录

| 版本 | 日期 | 修订内容 |
|------|------|---------|
| 1.0 | 2026-06-03 | 初始版本，制定全部工程规范 |
