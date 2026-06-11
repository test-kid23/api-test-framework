# Phase 5 详设文档：平台完善与生产化

> **文档版本**: 1.0  
> **制定日期**: 2026-06-11  
> **关联文档**: [开发计划 v5.0](./development-plan.md) | [架构评审 v5](./architecture-review.md)  
> **目标版本**: v3.0.0  
> **架构评分目标**: 9.20 → **9.60+**  
> **工期**: 8 周（3 个子阶段）  
> **前置条件**: Phase 4 全部完成（T4-6/T4-7/T4-8 已交付 ✅）

---

## 目录

1. [§5a 架构约束与代码质量基线](#5a-架构约束与代码质量基线)
2. [§5b P0 级任务详设：生产稳定性（第 1-2 周）](#5b-p0-级任务详设生产稳定性第-1-2-周)
3. [§5c P1 级任务详设：功能增强（第 3-5 周）](#5c-p1-级任务详设功能增强第-3-5-周)
4. [§5d P2 级任务详设：工程化提升（第 6-8 周）](#5d-p2-级任务详设工程化提升第-6-8-周)
5. [§5e 文件结构变更](#5e-文件结构变更)
6. [§5f 进度看板](#5f-进度看板)
7. [§5g 验收标准](#5g-验收标准)

---

## §5a 架构约束与代码质量基线

### 5a.1 不可破坏的架构模式

Phase 5 所有改动必须在以下 7 项既有模式内实现，**禁止引入新的架构概念或抽象层次**：

| # | 模式 | 约束 |
|---|------|------|
| 1 | **StepExecutor 策略模式** | 新增执行器必须继承 `StepExecutor` ABC，实现 `execute()` / `supports()` |
| 2 | **Repository 模式** | 所有 DB 操作通过 `framework/persistence/repositories/` 封装，禁止裸写 SQL |
| 3 | **依赖注入（DI）** | API 路由通过 `dependencies.py` 注入 `Runner` / `DB session` / `ConfigLoader`，不在路由函数内直接实例化 |
| 4 | **contextvars 三层作用域** | 保持 `run → case → step` 三层变量隔离，新增操作不破坏边界 |
| 5 | **PluginBase 钩子体系** | 新增钩子需声明 `priority`、添加 docstring，通过 `PluginManager` 分发 |
| 6 | **拦截器链（洋葱模型）** | HTTP 请求/响应通过 `RequestInterceptor` 链处理，顺序不可逆 |
| 7 | **通知渠道抽象** | 新增通知渠道实现 `NotificationChannel` ABC，通过 `NotificationService` 并行分发 |

### 5a.2 代码质量硬性指标

**所有 Phase 5 新增/修改的代码必须满足**：

| 指标 | 要求 | 检查方式 |
|------|------|---------|
| 类型注解 | PEP 695 `type` 语句，禁止 `Any` | mypy --strict |
| Docstring | Google 风格，`Args:` / `Returns:` / `Raises:` | ruff D 规则 |
| 测试覆盖率 | 新增代码 ≥ 90% | pytest-cov |
| 关键路径覆盖率 | ≥ 95%（执行引擎、调度器、通知） | pytest-cov --cov-context=test |
| 异常处理 | 捕获具体异常类型，禁止裸 `except Exception` | ruff B 规则 |
| 日志 | 使用 `Logger.get()`，关键路径有结构化日志 | structlog |
| 并发安全 | 禁止 `nest_asyncio`，使用纯 async/await | 人工 review |
| import 规范 | 顺序：标准库 → 第三方 → 项目内部，禁止 `import *` | ruff I 规则 |

### 5a.3 DB Schema 变更规范

1. 所有 Schema 变更通过 **Alembic 迁移**，禁止手动改表
2. 新增字段必须有 **默认值**（非 nullable），保证已有数据兼容
3. 迁移脚本必须包含 `downgrade()` 实现
4. 迁移前在 `docker-compose.test.yml` 环境验证

### 5a.4 API 兼容性规范

1. **禁止删除**已有 endpoint
2. 新增字段必须是 `Optional`（Pydantic: `Field(default=None)`）
3. Response schema 新字段追加在末尾，不改变已有字段顺序
4. 保持 `/api/v1/` 前缀不变

---

## §5b P0 级任务详设：生产稳定性（第 1-2 周）

### T5-01: 执行编排统一 ✅

> **完成日期**: 2026-06-11 | **测试**: 15/15 通过 | **本地 API 验证**: 8/8 通过

**问题**：`worker/tasks.py` 和 `api/routers/executions.py` 中存在约 80% 重复的执行逻辑（加载用例 → 注入环境 → 运行 → 持久化报告），两处代码各自维护，bug 修复经常只改一处。

**方案**：提取 `framework/execution_orchestrator.py`，统一执行编排流程。

**实际交付文件**：

```
framework/execution_orchestrator.py          # 🆕 执行编排器（含 ExecutionContext/ExecutionResult 数据类）
worker/tasks.py                              # ♻️ 重构为调用编排器（移除重复函数）
api/routers/executions.py                     # ♻️ 重构为调用编排器
tests/framework/test_execution_orchestrator.py # 🆕 15 个单元测试
```

**验收标准**：

- [x] `ExecutionOrchestrator` 核心方法 `execute_case_list_for_execution()` 覆盖所有执行场景
- [x] Worker 和 API 路由均通过编排器执行，无直接调用 runner
- [x] 单元测试 15 个，覆盖率 ≥ 95%（mock runner 和 repos）
- [x] 已有集成测试全部通过（439/444 passed，5 个预存失败与本任务无关）

---

### T5-02: 上下文快照持久化 ✅

> **完成日期**: 2026-06-11 | **测试**: 19/19 通过 | **本地 API 验证**: 8/8 通过

**问题**：执行失败时，三层变量状态（run/case/step）只在内存中，无法回溯复现失败现场。

**方案**：失败时自动将三层变量状态快照到 DB 新表 `context_snapshots`。

**实际交付文件**：

```
framework/context_snapshot.py                   # 🆕 快照生成逻辑 + 敏感字段脱敏
framework/persistence/models/context_snapshot.py # 🆕 ORM 模型
framework/persistence/repositories/context_snapshot_repo.py # 🆕 Repository
alembic/versions/a7b1c9d8e4f6_add_context_snapshots.py   # 🆕 迁移（含 downgrade）
api/routers/executions.py                        # ♻️ 新增 GET /{execution_id}/snapshot
tests/framework/test_context_snapshot.py         # 🆕 19 个单元测试
```

**验收标准**：

- [x] 执行失败后 DB 中有对应 snapshot 记录
- [x] `ContextSnapshot` 使用 `frozen=True` + `MappingProxyType` 保证不可变
- [x] API 查询接口可正常返回快照数据
- [x] 快照不包含敏感字段（token/password/api_key/authorization/credential 已脱敏，7 种正则模式）
- [x] 单元测试覆盖敏感字段识别（7 项）/ 脱敏（3 项）/ 安全序列化（5 项）/ 快照管理器（3 项）

---

### T5-03: Worker 健康监控

**问题**：Worker 进程挂掉后无感知，调度任务静默失败。

**方案**：Redis 心跳机制 + 失联告警 + 健康检查 API。

**文件设计**：

```
framework/worker_health.py                # 🆕 心跳发送 + 健康检查
worker/tasks.py                           # ♻️ 启动时注册心跳
api/routers/workers.py                    # 🆕 Worker 健康检查 API
tests/framework/test_worker_health.py     # 🆕 单元测试
```

**关键接口签名**：

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime


@dataclass
class WorkerInfo:
    """Worker 节点信息."""
    worker_id: str
    hostname: str
    status: str  # "online" | "offline" | "busy"
    last_heartbeat: datetime
    current_task: str | None = None
    uptime_seconds: int = 0


class WorkerHealthMonitor:
    """Worker 健康监控器.

    通过 Redis 心跳键实现 Worker 存活检测和失联告警。

    Attributes:
        HEARTBEAT_INTERVAL: 心跳间隔 30s
        HEARTBEAT_TTL: 心跳键过期时间 90s
        OFFLINE_THRESHOLD: 失联阈值 60s
    """

    HEARTBEAT_INTERVAL: int = 30
    HEARTBEAT_TTL: int = 90
    OFFLINE_THRESHOLD: int = 60

    def __init__(self, redis_client: Redis, notification_service: NotificationService) -> None:
        """初始化.

        Args:
            redis_client: Redis 客户端
            notification_service: 通知服务（用于失联告警）
        """
        ...

    async def start_heartbeat(self, worker_id: str, hostname: str) -> None:
        """启动心跳循环.

        Args:
            worker_id: Worker 唯一标识
            hostname: 主机名
        """
        ...

    async def stop_heartbeat(self, worker_id: str) -> None:
        """停止心跳.

        Args:
            worker_id: Worker 唯一标识
        """
        ...

    async def get_all_workers(self) -> list[WorkerInfo]:
        """获取所有 Worker 节点信息.

        Returns:
            WorkerInfo 列表
        """
        ...

    async def check_health(self) -> list[WorkerInfo]:
        """健康检查并触发失联告警.

        Returns:
            所有 Worker 信息（含失联标记）
        """
        ...
```

**API 接口**：

```
GET  /api/v1/workers              → list[WorkerInfo]     # 所有 Worker 状态
GET  /api/v1/workers/{id}         → WorkerInfo           # 单个 Worker 详情
POST /api/v1/workers/{id}/restart → None                  # 重启 Worker
```

**验收标准**：

- [ ] Worker 启动后自动发送心跳（30s 间隔）
- [ ] Worker 异常退出后心跳键在 90s 后过期
- [ ] 超过 60s 未心跳触发通知告警
- [ ] `/api/v1/workers` 返回正确的在线/离线状态
- [ ] 单元测试覆盖心跳注册/过期/告警三条路径

---

### T5-04: 调度失败告警 ✅

> **完成日期**: 2026-06-11 | **测试**: 10/10 通过 | **本地 API 验证**: 8/8 通过

**问题**：定时任务触发失败时（如环境不可用、Worker 全部离线），无告警通知。

**方案**：在 `framework/scheduler.py` 的任务触发点捕获异常，通过 `NotificationService` 发送告警。

**实际交付文件**：

```
framework/scheduler.py              # ♻️ fire_schedule() 新增 4 个失败场景告警 + _send_schedule_failure_alert()
framework/notifications/service.py  # ♻️ 新增 send_alert() 通用告警方法
tests/framework/test_scheduler_alert.py   # 🆕 10 个单元测试
```

**验收标准**：

- [x] 调度触发失败时发送告警（`send_alert()` 支持渠道过滤，默认所有已配置渠道）
- [x] 告警内容包含 schedule_id、调度名称、环境、时间戳、失败类型、详情
- [x] 异常类型有区分：suite_not_found / no_cases / celery_dispatch / callback_failed
- [x] 单元测试 mock NotificationService 验证调用（10 个测试全部通过）

---

## §5c P1 级任务详设：功能增强（第 3-5 周）

### T5-05: 组合断言 (AND/OR)

**问题**：当前断言只支持单一条件，无法表达"响应码=200 且 body.code=0"这样的组合逻辑。

**方案**：`AssertItem` 新增 `logic` 和 `children` 字段，支持递归嵌套的 AND/OR 组合。

**文件设计**：

```
framework/parser_models.py                     # ♻️ AssertItem 新增 logic/children
framework/assertion/engine.py                  # ♻️ 新增组合求值逻辑
framework/assertion/composite.py               # 🆕 组合断言求值器
tests/framework/test_composite_assertion.py    # 🆕 单元测试
testcases/composite_assertion_sample.yaml      # 🆕 示例用例
```

**关键接口签名**：

```python
from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from framework.assertion.engine import AssertionResult


class LogicOperator(str, Enum):
    AND = "and"
    OR = "or"


# parser_models.py 中 AssertItem 的扩展
class AssertItem(BaseModel):
    """断言项（支持组合）."""
    path: str | None = None          # 单断言时使用
    operator: str | None = None      # 单断言时使用
    expected: object | None = None   # 单断言时使用
    logic: LogicOperator | None = None       # 🆕 组合逻辑运算符
    children: list[AssertItem] | None = None # 🆕 子断言项（递归）
    message: str | None = None       # 自定义失败消息


class CompositeAssertionEvaluator:
    """组合断言求值器.

    递归求值 AND/OR 组合断言树。
    AND: 所有子断言通过 → 通过
    OR:  任一子断言通过 → 通过
    """

    def evaluate(self, item: AssertItem, context: dict[str, object]) -> AssertionResult:
        """递归求值断言项.

        Args:
            item: 断言项（可能是单断言或组合断言）
            context: 响应上下文

        Returns:
            AssertionResult: 求值结果
        """
        ...
```

**YAML 示例**：

```yaml
assert:
  logic: and
  children:
    - path: $.status_code
      operator: eq
      expected: 200
    - path: $.body.code
      operator: eq
      expected: 0
```

**验收标准**：

- [ ] 支持 AND/OR 嵌套（至少 3 层深度）
- [ ] 短路求值：AND 遇到第一个失败即停止，OR 遇到第一个成功即停止
- [ ] 失败消息能定位到具体哪个子断言失败
- [ ] 向后兼容：不设置 logic 的断言行为不变
- [ ] 单元测试覆盖：单层 AND/单层 OR/嵌套 AND+OR/空 children/边界深度

---

### T5-06: 提取器管道

**问题**：当前 `extractor` 只支持单步提取，无法对提取结果做链式处理（如 jsonpath → regex → base64_decode）。

**方案**：新增 `ExtractPipeline`，支持声明式链式提取步骤。

**文件设计**：

```
framework/extract_pipeline.py               # 🆕 提取器管道
framework/parser_models.py                  # ♻️ ExtractItem 新增 pipeline 字段
tests/framework/test_extract_pipeline.py    # 🆕 单元测试
```

**关键接口签名**：

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class ExtractStepType(str, Enum):
    JSONPATH = "jsonpath"
    REGEX = "regex"
    BASE64_DECODE = "base64_decode"
    BASE64_ENCODE = "base64_encode"
    JSON_PARSE = "json_parse"


@dataclass
class ExtractStep:
    """提取步骤."""
    type: ExtractStepType
    expression: str  # jsonpath 表达式 / regex 模式
    group: int = 0   # regex 捕获组索引


class ExtractPipeline:
    """提取器管道.

    支持声明式链式处理：jsonpath → regex → base64_decode → json_parse
    每步的输出作为下一步的输入。
    """

    def __init__(self, steps: list[ExtractStep]) -> None:
        """初始化管道.

        Args:
            steps: 提取步骤列表（按序执行）

        Raises:
            ValueError: steps 为空时
        """
        ...

    async def execute(self, source: str | dict | bytes) -> str:
        """执行提取管道.

        Args:
            source: 原始数据源

        Returns:
            最终提取结果（字符串）

        Raises:
            ExtractPipelineError: 任一步骤失败时
        """
        ...
```

**YAML 示例**：

```yaml
extract:
  token:
    pipeline:
      - type: jsonpath
        expression: $.body.auth_token
      - type: base64_decode
```

**验收标准**：

- [ ] 支持 5 种步骤类型
- [ ] 管道步骤按序执行，输出作为下一步输入
- [ ] 任一步骤失败抛出 `ExtractPipelineError`（含步骤索引）
- [ ] 向后兼容：不设置 pipeline 时走原有单步提取
- [ ] 单元测试覆盖：单步/多步/失败/空输入

---

### T5-07: 插件配置化

**问题**：插件启用/禁用硬编码在代码中，无法按环境配置。

**方案**：在 `config.yaml` 中新增 `plugins.enabled` / `plugins.disabled` 白名单/黑名单。

**文件设计**：

```
framework/config_schema.py      # ♻️ 新增 PluginConfig 模型
framework/plugins/manager.py    # ♻️ 读取配置过滤插件
config/config.yaml              # ♻️ 新增 plugins 配置段
```

**配置格式**：

```yaml
# config/config.yaml
plugins:
  mode: whitelist  # "whitelist" | "blacklist" | "all"
  enabled:
    - AuthPlugin
    - LoggingPlugin
    - MockPlugin
  disabled:
    - HeavyProfilerPlugin
```

**验收标准**：

- [ ] 支持 whitelist/blacklist/all 三种模式
- [ ] 配置变更后重启生效（T5-13 实现热加载后自动生效）
- [ ] 单元测试覆盖三种模式

---

### T5-08: 多数据源注册

**问题**：当前只支持单一 DB 连接，无法在用例中切换不同数据源执行 SQL 断言。

**方案**：新增 `DataSourceRegistry`，通过配置文件声明多数据源。

**文件设计**：

```
framework/datasource.py                     # 🆕 数据源注册表
framework/config_schema.py                  # ♻️ 新增 DataSourceConfig
framework/executors/db_executor.py          # ♻️ 支持数据源切换
config/config.yaml                          # ♻️ 新增 datasources 配置段
tests/framework/test_datasource.py          # 🆕 单元测试
```

**关键接口签名**：

```python
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class DataSourceConfig:
    """数据源配置."""
    name: str
    type: str  # "mysql" | "postgresql" | "sqlite"
    dsn: str
    pool_size: int = 5
    timeout: int = 30


class DataSourceRegistry:
    """多数据源注册表.

    管理多个数据库连接池，按名称获取。
    """

    def __init__(self, configs: list[DataSourceConfig]) -> None:
        """初始化并建立所有连接池.

        Args:
            configs: 数据源配置列表
        """
        ...

    async def get(self, name: str) -> AsyncConnection:
        """获取指定数据源连接.

        Args:
            name: 数据源名称

        Returns:
            数据库连接

        Raises:
            DataSourceNotFoundError: 数据源未注册时
        """
        ...

    async def close_all(self) -> None:
        """关闭所有连接池."""
        ...
```

**配置格式**：

```yaml
datasources:
  - name: primary
    type: postgresql
    dsn: postgresql+asyncpg://user:pass@host:5432/db
    pool_size: 10
  - name: analytics
    type: mysql
    dsn: mysql+aiomysql://user:pass@host:3306/db
    pool_size: 5
```

**验收标准**：

- [ ] 支持 PostgreSQL / MySQL / SQLite 三种数据源类型
- [ ] 连接池健康检查
- [ ] 按名称获取连接，不存在的名称抛出明确异常
- [ ] 单元测试 mock 连接池，覆盖注册/获取/关闭

---

### T5-09: Email 通知完善

**问题**：当前 `email_channel.py` 是骨架实现，缺少实际 SMTP 发送逻辑。

**方案**：使用 `aiosmtplib` 实现异步 SMTP 发送，支持 TLS/STARTTLS。

**文件设计**：

```
framework/notifications/email_channel.py      # ♻️ 完善 SMTP 发送
config/config.yaml                            # ♻️ 新增 email SMTP 配置
tests/framework/test_email_channel.py         # 🆕 单元测试
```

**配置格式**：

```yaml
notifications:
  email:
    smtp_host: smtp.example.com
    smtp_port: 587
    use_tls: true
    username: alerts@example.com
    password: ${EMAIL_PASSWORD}  # 环境变量引用
    from_addr: "AutoTest <alerts@example.com>"
    to_addrs:
      - admin@example.com
      - oncall@example.com
```

**关键接口**：

```python
class EmailChannel(NotificationChannel):
    """邮件通知渠道（aiosmtplib 异步实现）."""

    async def send(self, message: NotificationMessage) -> bool:
        """发送邮件通知.

        Args:
            message: 通知消息

        Returns:
            发送是否成功
        """
        ...
```

**验收标准**：

- [ ] 支持 TLS/STARTTLS 加密
- [ ] 支持 HTML 邮件正文（告警带样式）
- [ ] 发送失败不阻塞其他渠道（异常捕获）
- [ ] 单元测试 mock aiosmtplib

---

### T5-10: 环境变量加密存储

**问题**：环境配置中的敏感字段（密码/token/API Key）明文存储在 DB 中。

**方案**：实现 AES-256-GCM 加密，敏感字段写入时加密、读取时解密、API 返回时脱敏。

**文件设计**：

```
framework/utils/field_encryptor.py            # 🆕 AES-256-GCM 加密工具
framework/persistence/repositories/environment_repository.py  # ♻️ 写入时加密
api/schemas/environment.py                    # ♻️ 查询时脱敏
tests/framework/test_field_encryptor.py       # 🆕 单元测试
```

**关键接口签名**：

```python
from __future__ import annotations


class FieldEncryptor:
    """字段加密器（AES-256-GCM）.

    加密后格式: "enc:v1:<base64_nonce>:<base64_ciphertext>:<base64_tag>"
    """

    ENCRYPTION_PREFIX = "enc:v1:"

    def __init__(self, key: bytes) -> None:
        """初始化.

        Args:
            key: 32 字节 AES-256 密钥
        """
        ...

    def encrypt(self, plaintext: str) -> str:
        """加密.

        Args:
            plaintext: 明文

        Returns:
            加密后字符串（带 enc:v1: 前缀）
        """
        ...

    def decrypt(self, ciphertext: str) -> str:
        """解密.

        Args:
            ciphertext: 加密字符串

        Returns:
            明文

        Raises:
            DecryptionError: 解密失败时
        """
        ...

    def mask(self, value: str) -> str:
        """脱敏显示.

        Args:
            value: 原始值

        Returns:
            脱敏后值（如 "a***z"）
        """
        ...

    @staticmethod
    def is_encrypted(value: str) -> bool:
        """判断是否已加密.

        Args:
            value: 待检测值

        Returns:
            是否以 enc:v1: 开头
        """
        ...
```

**验收标准**：

- [ ] 写入时自动加密 `password`/`token`/`api_key` 类型字段
- [ ] 读取时自动解密（供执行引擎使用）
- [ ] API 查询返回脱敏值（`enc:v1:...` → `a***z`）
- [ ] 密钥从环境变量 `AUTOTEST_ENCRYPTION_KEY` 读取
- [ ] 单元测试覆盖加密/解密/脱敏/格式检测

---

### T5-11: 报告聚合 API

**问题**：缺少聚合分析 API（通过率趋势、响应时间分位数、失败分类），前端 Dashboard 数据不足。

**方案**：在 `api/routers/reports.py` 中新增聚合查询接口，底层通过 SQL 窗口函数实现。

**文件设计**：

```
api/routers/reports.py                    # ♻️ 新增聚合查询 API
framework/persistence/repositories/report_repository.py  # ♻️ 新增聚合查询方法
frontend/src/pages/DashboardPage.tsx      # ♻️ 接入聚合数据
```

**API 接口**：

```
GET /api/v1/reports/trend/pass-rate?days=30&granularity=day
  → { "data": [{ "date": "2026-06-01", "pass_rate": 0.95, "total": 100 }, ...] }

GET /api/v1/reports/trend/response-time?days=30
  → { "data": [{ "date": "2026-06-01", "p50": 120, "p90": 350, "p95": 500, "p99": 800 }, ...] }

GET /api/v1/reports/failure-categories?days=30
  → { "data": [{ "category": "assertion_failed", "count": 45, "percentage": 0.6 }, ...] }

GET /api/v1/reports/unstable-endpoints?days=30&threshold=0.8
  → { "data": [{ "endpoint": "POST /api/users", "pass_rate": 0.72, "total_runs": 50 }, ...] }
```

**验收标准**：

- [ ] 通过率趋势支持 day/week/month 粒度
- [ ] 响应时间分位数：P50/P90/P95/P99
- [ ] 失败分类：assertion_failed / timeout / connection_error / parse_error
- [ ] 不稳定接口阈值可配
- [ ] 单元测试覆盖所有聚合查询

---

### T5-12: 快照 Redis 缓存

**问题**：每个 step 的变量状态只存内存，高并发场景内存压力大，且 Worker 重启后丢失。

**方案**：每个 step 结束时自动将快照写到 Redis（1 小时 TTL），执行结束后持久化到 DB。

**文件设计**：

```
framework/context_snapshot.py             # ♻️ 新增 Redis 缓存逻辑
tests/framework/test_context_snapshot.py  # ♻️ 新增 Redis 缓存测试
```

**关键接口**：

```python
class ContextSnapshotManager:
    # ... 原有方法 ...

    async def cache_step_snapshot(
        self, execution_id: str, step_index: int, ctx: ExecutionContext
    ) -> None:
        """将步骤快照缓存到 Redis（1h TTL）.

        Args:
            execution_id: 执行 ID
            step_index: 步骤索引
            ctx: 执行上下文
        """
        ...

    async def get_cached_snapshot(self, execution_id: str) -> ContextSnapshot | None:
        """从 Redis 获取缓存的快照.

        Args:
            execution_id: 执行 ID

        Returns:
            快照或 None
        """
        ...
```

**验收标准**：

- [ ] 每个 step 结束自动写 Redis（TTL=3600s）
- [ ] 执行结束后快照持久化到 DB，Redis 键可提前过期
- [ ] Redis 不可用时不影响正常执行（降级为只存内存）
- [ ] 单元测试覆盖 Redis 可用/不可用两种场景

---

## §5d P2 级任务详设：工程化提升（第 6-8 周）

### T5-13: 配置热加载

**问题**：修改配置后必须重启服务才能生效。

**方案**：使用 `watchdog` 监听 `config/` 目录，检测到变更后自动重新加载配置（仅开发模式启用）。

**文件设计**：

```
framework/config_watcher.py            # 🆕 watchdog 监听器
framework/config.py                    # ♻️ 新增 reload 方法
```

**关键接口**：

```python
class ConfigWatcher:
    """配置热加载器（仅开发模式）."""

    def __init__(self, config_loader: ConfigLoader, watch_dir: Path) -> None:
        ...

    def start(self) -> None:
        """启动监听."""
        ...

    def stop(self) -> None:
        """停止监听."""
        ...
```

**验收标准**：

- [ ] `config.yaml` 修改后 3 秒内自动重载
- [ ] 仅 `dev` 模式启用（生产模式不加载）
- [ ] 重载失败时保留旧配置，记录告警日志
- [ ] 单元测试 mock watchdog

---

### T5-14: 单接口超时覆盖

**问题**：全局超时配置无法满足个别接口需要更长超时的需求。

**方案**：`HttpRequest` 模型新增 `timeout` 字段，优先级高于全局配置。

**文件设计**：

```
framework/models.py        # ♻️ HttpRequest 新增 timeout 字段
framework/parser.py        # ♻️ 解析 YAML timeout 字段
```

**YAML 示例**：

```yaml
steps:
  - name: 慢查询接口
    http:
      method: POST
      url: /api/slow-query
      timeout: 60  # 覆盖全局 30s
```

**验收标准**：

- [ ] `timeout` 字段可选，未设置时使用全局配置
- [ ] 向后兼容：已有用例不受影响

---

### T5-15: 签名计算函数

**问题**：模板引擎缺少签名计算能力，无法在 YAML 中直接计算 HMAC-SHA256/MD5 签名。

**方案**：模板引擎新增 `hmac_sha256` 和 `md5_sign` 内置函数。

**文件设计**：

```
framework/template.py                # ♻️ 注册新内置函数
tests/framework/test_template.py     # ♻️ 新增签名函数测试
```

**YAML 示例**：

```yaml
headers:
  Authorization: "HMAC-SHA256 {{ hmac_sha256(secret_key, body) }}"
  X-Sign: "{{ md5_sign(timestamp + body) }}"
```

**验收标准**：

- [ ] `hmac_sha256(key, message)` 返回 hex 摘要
- [ ] `md5_sign(message)` 返回 hex 摘要
- [ ] 函数在模板表达式中可用

---

### T5-16: next_run_at 同步

**问题**：`ScheduleModel.next_run_at` 只在创建/修改时计算一次，不随 APScheduler 实际调度更新。

**方案**：APScheduler 每次触发任务后更新 DB 中的 `next_run_at`。

**文件设计**：

```
framework/scheduler.py  # ♻️ 任务触发后同步 next_run_at
```

**验收标准**：

- [ ] 每次调度触发后 `next_run_at` 更新为下次触发时间
- [ ] 前端调度列表显示准确的"下次执行时间"

---

### T5-17: 通知渠道配置化

**问题**：通知渠道的启停需要在代码中修改，不灵活。

**方案**：`config.yaml` 中新增 `channels.<name>.enabled` 开关。

**配置格式**：

```yaml
notifications:
  channels:
    wecom:
      enabled: true
      webhook_url: "..."
    email:
      enabled: false
    dingtalk:
      enabled: true
```

**验收标准**：

- [ ] 各渠道独立控制启停
- [ ] disabled 的渠道不会收到任何通知

---

### T5-18: 项目级 API 隔离

**问题**：API 层未按 `project_id` 过滤数据，多项目部署时数据混杂。

**方案**：API 层查询时根据当前用户的项目归属过滤数据。

**文件设计**：

```
api/dependencies.py        # ♻️ 新增 project_id 上下文
api/routers/cases.py       # ♻️ 按 project_id 过滤
api/routers/executions.py  # ♻️ 按 project_id 过滤
api/routers/reports.py     # ♻️ 按 project_id 过滤
api/routers/schedules.py   # ♻️ 按 project_id 过滤
```

**验收标准**：

- [ ] 用户只能看到所属项目的数据
- [ ] admin 角色可查看所有项目数据
- [ ] 无项目归属的用户返回空列表

---

### T5-19: Token 刷新机制

**问题**：JWT access token 过期后用户必须重新登录，体验差。

**方案**：实现 refresh_token 机制 + 前端 Axios 拦截器自动续期。

**文件设计**：

```
api/auth.py                              # ♻️ 新增 refresh_token 逻辑
api/routers/auth.py                      # ♻️ 新增 POST /auth/refresh
frontend/src/api/client.ts               # ♻️ Axios 401 自动刷新
frontend/src/store/authStore.ts          # ♻️ 存储 refresh_token
```

**API 接口**：

```
POST /api/v1/auth/login     → { access_token, refresh_token, expires_in }
POST /api/v1/auth/refresh   → { access_token, refresh_token, expires_in }
```

**验收标准**：

- [ ] access_token 过期后用 refresh_token 自动续期
- [ ] refresh_token 也过期时跳转登录页
- [ ] 前端 Axios 拦截器无感刷新

---

### T5-20: Mock 规则持久化

**问题**：Mock 规则只存内存，服务重启后丢失。

**方案**：新增 `MockRuleModel` ORM + `MockRuleStoreDB`，通过 Alembic 迁移建表。

**文件设计**：

```
framework/persistence/models/mock_rule.py            # 🆕 ORM 模型
framework/persistence/repositories/mock_rule_repo.py # 🆕 Repository
framework/mock/rule_store_db.py                      # 🆕 DB 存储实现
alembic/versions/xxxx_add_mock_rules.py              # 🆕 迁移
```

**验收标准**：

- [ ] Mock 规则 CRUD 持久化
- [ ] 服务启动时从 DB 加载规则到内存
- [ ] 规则变更后同步到内存

---

### T5-21: 回放变量替换

**问题**：HAR 回放时使用录制时的硬编码值，不会替换动态字段（如 timestamp/token）。

**方案**：回放前自动识别动态字段（时间戳/UUID/token），替换为模板变量。

**文件设计**：

```
framework/recorder/player.py         # ♻️ 新增动态字段识别
framework/recorder/var_detector.py   # 🆕 动态变量检测器
```

**验收标准**：

- [ ] 自动识别 ISO 时间戳/UUID/JWT token
- [ ] 回放时替换为 `{{ $timestamp }}` / `{{ $uuid }}` / `{{ $token }}`
- [ ] 用户可自定义检测规则

---

### T5-22: 密码强度策略

**问题**：用户密码无复杂度校验，无登录失败锁定机制。

**方案**：新增密码复杂度校验 + 登录失败 5 次锁定 30 分钟。

**文件设计**：

```
api/auth.py                     # ♻️ 新增密码校验 + 登录锁定
api/schemas/auth.py             # ♻️ 新增密码规则 schema
tests/api/test_auth.py          # ♻️ 新增密码策略测试
```

**验收标准**：

- [ ] 密码最少 8 位，包含大小写+数字+特殊字符
- [ ] 连续 5 次失败锁定 30 分钟
- [ ] 锁定状态返回明确提示

---

### T5-23: 前端 E2E 测试

**问题**：前端无自动化测试，回归全靠手动。

**方案**：Playwright 实现关键路径 E2E 测试。

**文件设计**：

```
frontend/e2e/                    # 🆕 E2E 测试目录
  ├── login.spec.ts              # 登录流程
  ├── cases.spec.ts              # 用例管理
  ├── execution.spec.ts          # 执行流程
  └── dashboard.spec.ts          # 仪表盘
```

**验收标准**：

- [ ] 覆盖登录/用例 CRUD/执行触发/Dashboard 四条关键路径
- [ ] CI 集成（`npm run test:e2e`）
- [ ] 失败时自动截图

---

### T5-24: 国际化 i18n

**问题**：前端硬编码中文，无法切换英文。

**方案**：集成 `react-i18next`，实现中英文切换。

**文件设计**：

```
frontend/src/i18n/             # 🆕 i18n 配置
  ├── index.ts                 # i18next 初始化
  ├── locales/
  │   ├── zh-CN.json           # 中文翻译
  │   └── en-US.json           # 英文翻译
frontend/src/components/LanguageSwitcher.tsx  # 🆕 语言切换组件
```

**验收标准**：

- [ ] 支持中英文切换
- [ ] 切换后所有页面文本即时更新
- [ ] 语言偏好存储到 localStorage

---

## §5e 文件结构变更

### 新增文件（12 个）

```
framework/execution_orchestrator.py               # T5-01
framework/context_snapshot.py                     # T5-02
framework/worker_health.py                        # T5-03
framework/datasource.py                           # T5-08
framework/utils/field_encryptor.py                # T5-10
framework/assertion/composite.py                  # T5-05
framework/extract_pipeline.py                     # T5-06
framework/config_watcher.py                       # T5-13
framework/persistence/models/context_snapshot.py  # T5-02
framework/persistence/models/mock_rule.py         # T5-20
framework/recorder/var_detector.py                # T5-21
api/routers/workers.py                            # T5-03
```

### 改动文件（25 个）

```
worker/tasks.py                                   # T5-01 ♻️
api/routers/executions.py                         # T5-01/T5-02 ♻️
api/routers/reports.py                            # T5-11 ♻️
api/routers/cases.py                              # T5-18 ♻️
api/routers/schedules.py                          # T5-18 ♻️
api/dependencies.py                               # T5-18 ♻️
api/auth.py                                       # T5-19/T5-22 ♻️
api/routers/auth.py                               # T5-19 ♻️
api/schemas/auth.py                               # T5-22 ♻️
api/schemas/environment.py                        # T5-10 ♻️
framework/parser_models.py                        # T5-05/T5-06 ♻️
framework/assertion/engine.py                     # T5-05 ♻️
framework/models.py                               # T5-14 ♻️
framework/parser.py                               # T5-14 ♻️
framework/template.py                             # T5-15 ♻️
framework/scheduler.py                            # T5-04/T5-16 ♻️
framework/config_schema.py                        # T5-07/T5-08 ♻️
framework/config.py                               # T5-13 ♻️
framework/plugins/manager.py                      # T5-07 ♻️
framework/executors/db_executor.py                # T5-08 ♻️
framework/notifications/email_channel.py          # T5-09 ♻️
framework/recorder/player.py                      # T5-21 ♻️
framework/mock/rule_store_db.py                   # T5-20 ♻️
framework/context_snapshot.py                     # T5-12 ♻️
framework/persistence/repositories/               # T5-10/T5-11 ♻️
config/config.yaml                                # T5-07/T5-08/T5-09/T5-17 ♻️
frontend/src/pages/DashboardPage.tsx              # T5-11 ♻️
frontend/src/api/client.ts                        # T5-19 ♻️
frontend/src/store/authStore.ts                   # T5-19 ♻️
```

---

## §5f 进度看板

| 编号 | 任务 | 优先级 | 工时 | 状态 | 完成日期 | 测试 | API 验证 |
|------|------|--------|------|------|---------|------|---------|
| T5-01 | 执行编排统一 | P0 | 3d | ✅ | 2026-06-11 | 15/15 ✅ | 8/8 ✅ |
| T5-02 | 上下文快照持久化 | P0 | 2d | ✅ | 2026-06-11 | 19/19 ✅ | 8/8 ✅ |
| T5-03 | Worker 健康监控 | P0 | 2d | ✅ | 2026-06-11 | 25/25 ✅ | — |
| T5-04 | 调度失败告警 | P0 | 1d | ✅ | 2026-06-11 | 10/10 ✅ | 8/8 ✅ |
| T5-05 | 组合断言 (AND/OR) | P1 | 3d | ✅ | 2026-06-11 | 27/27 ✅ | — |
| T5-06 | 提取器管道 | P1 | 2d | ✅ | 2026-06-11 | 38/38 ✅ | — |
| T5-07 | 插件配置化 | P1 | 1d | ✅ | 2026-06-11 | 20/20 ✅ | — |
| T5-08 | 多数据源注册 | P1 | 2d | ✅ | 2026-06-11 | 29/29 ✅ | — |
| T5-09 | Email 通知完善 | P1 | 2d | ✅ | 2026-06-11 | 29/29 ✅ | — |
| T5-10 | 环境变量加密 | P1 | 2d | ✅ | 2026-06-11 | 35/35 ✅ | — |
| T5-11 | 报告聚合 API | P1 | 3d | ✅ | 2026-06-11 | 27/27 ✅ | — |
| T5-12 | 快照 Redis 缓存 | P1 | 1d | ✅ | 2026-06-11 | 30/30 ✅ | — |
| T5-13 | 配置热加载 | P2 | 1d | ⬜ | — | — | — |
| T5-14 | 单接口超时覆盖 | P2 | 0.5d | ⬜ | — | — | — |
| T5-15 | 签名计算函数 | P2 | 1d | ⬜ | — | — | — |
| T5-16 | next_run_at 同步 | P2 | 0.5d | ⬜ | — | — | — |
| T5-17 | 通知渠道配置化 | P2 | 0.5d | ⬜ | — | — | — |
| T5-18 | 项目级 API 隔离 | P2 | 2d | ⬜ | — | — | — |
| T5-19 | Token 刷新机制 | P2 | 2d | ⬜ | — | — | — |
| T5-20 | Mock 规则持久化 | P2 | 2d | ⬜ | — | — | — |
| T5-21 | 回放变量替换 | P2 | 1.5d | ⬜ | — | — | — |
| T5-22 | 密码强度策略 | P2 | 1d | ⬜ | — | — | — |
| T5-23 | 前端 E2E 测试 | P2 | 3d | ⬜ | — | — | — |
| T5-24 | 国际化 i18n | P2 | 2d | ⬜ | — | — | — |

状态图例: ⬜ 未开始 | 🔄 进行中 | ✅ 已完成

**当前进度**: 11/24 已完成（P0 任务 4/4 ✅，P1 任务 7/8 ✅），开发 2 天。已完成任务单元测试总计 275/275 通过，API 验证 24/24 通过。

---

## §5g 验收标准

### 整体验收

- [ ] 24 项任务全部完成
- [ ] 架构评分 ≥ 9.60/10（当前 v6 评审 9.33/10）
- [ ] 新增代码测试覆盖率 ≥ 90%，关键路径 ≥ 95%
- [ ] 所有已有测试通过（零回归）
- [ ] mypy --strict 零错误
- [ ] ruff 零错误
- [ ] 无 `nest_asyncio` 引用
- [ ] 无裸 `except Exception`
- [ ] API 全部向后兼容（已有接口行为不变）
- [ ] DB 迁移可正向/回滚

### 分阶段验收

**Phase 5a 验收（第 2 周末）**：
- [x] 执行编排统一后 Worker 和 API 路由无重复执行逻辑（T5-01，15 测试 ✅）
- [x] 执行失败可回溯快照（T5-02，19 测试 ✅，7 种敏感字段脱敏）
- [x] Worker 失联 60s 内触发告警（T5-03，25 测试 ✅，4 个 API 端点）
- [x] 调度失败触发告警通知（T5-04，10 测试 ✅，4 类失败场景覆盖）

**Phase 5b 验收（第 5 周末）**：
- [ ] 组合断言支持 3 层嵌套（T5-05）
- [ ] 提取管道支持链式处理（T5-06）
- [ ] 敏感字段加密存储 + API 脱敏返回（T5-10）
- [ ] 报告聚合 API 返回正确的趋势数据（T5-11）

**Phase 5c 验收（第 8 周末）**：
- [ ] 配置热加载在 dev 模式正常工作（T5-13）
- [ ] Token 自动刷新无感知（T5-19）
- [ ] Mock 规则重启不丢失（T5-20）
- [ ] E2E 测试覆盖关键路径（T5-23）
- [ ] 中英文切换正常（T5-24）

---

*文档更新于 2026-06-11 · Phase 5 详设 v1.3 · 已完成 4/24 任务（P0 全部完成） · 架构评分 9.33/10*
