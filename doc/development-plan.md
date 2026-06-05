# AutoTest Framework 开发计划

> **计划版本**: 1.1（已根据评审反馈调整）  
> **制定日期**: 2026-06-03  
> **修订日期**: 2026-06-03  
> **关联文档**: [架构评审报告](./architecture-review.md)  
> **目标版本**: 1.0.0 → 3.0.0（分阶段交付）  
> **技术栈基线**: Python 3.12 | pytest 8.x | httpx 0.28.x | Pydantic 2.10.x

---

## 目录

1. [技术栈版本锁定](#0-技术栈版本锁定)
2. [总览与进度追踪](#1-总览与进度追踪)
3. [Phase 0a: 安全止血（1周）](#phase-0a-安全止血)
4. [Phase 0b: 工程化加固（1周）](#phase-0b-工程化加固)
5. [Phase 1: 架构解耦与核心重构（3-4周）](#phase-1-架构解耦与核心重构)
6. [Phase 2: 引擎服务化与持久化（4周）](#phase-2-引擎服务化与持久化)
7. [Phase 3: 平台化基础建设（4周）](#phase-3-平台化基础建设)
8. [Phase 4: 完整测试平台（6周）](#phase-4-完整测试平台)
9. [附录: 文件结构变更总览](#附录-文件结构变更总览)
10. [修订记录](#修订记录)

---

## 0. 技术栈版本锁定

### 运行时

| 组件 | 锁定版本 | 说明 |
|------|---------|------|
| **Python** | **3.12.3+** | 使用 3.12 新特性（`type` 语句、PEP 695 泛型语法等） |
| **pytest** | **8.3.x** | 核心测试框架，固定 8.x 大版本 |
| httpx | 0.28.1 | HTTP/2 支持，连接池复用 |
| PyYAML | 6.0.2 | YAML 解析（C 扩展加速） |
| Jinja2 | 3.1.4 | 模板引擎（修复 CVE 安全版本） |
| jsonpath-ng | 1.7.0 | JSONPath 表达式解析 |
| pydantic | 2.10.6 | 数据模型与配置校验 |

### 报告

| 组件 | 锁定版本 | 说明 |
|------|---------|------|
| allure-pytest | 2.13.5 | Allure 报告集成 |
| pytest-html | 4.1.1 | HTML 报告备选 |

### 执行增强

| 组件 | 锁定版本 | 说明 |
|------|---------|------|
| pytest-xdist | 3.6.1 | 多进程并行执行 |
| pytest-rerunfailures | 14.0 | 失败重试 |
| pytest-timeout | 2.3.1 | 用例级超时控制（新增） |

### 数据库（可选依赖 extra: db）

| 组件 | 锁定版本 | 说明 |
|------|---------|------|
| SQLAlchemy | 2.0.36 | ORM / Core |
| pymysql | 1.1.1 | MySQL 驱动 |
| psycopg2-binary | 2.9.10 | PostgreSQL 驱动 |
| aiosqlite | 0.20.0 | 异步 SQLite（新增，用于本地持久化） |

### WebSocket（可选依赖 extra: ws）

| 组件 | 锁定版本 | 说明 |
|------|---------|------|
| websockets | 13.1 | WebSocket 客户端 |

### 平台化新增（Phase 2+）

| 组件 | 锁定版本 | 用途 | 引入阶段 |
|------|---------|------|---------|
| fastapi | 0.115.x | REST API 服务 | Phase 2 |
| uvicorn | 0.34.0 | ASGI 服务器 | Phase 2 |
| celery | 5.4.0 | 分布式任务队列 | Phase 3 |
| redis | 5.2.0 | 消息代理 + 缓存 | Phase 3 |
| SQLAlchemy[asyncio] | 2.0.36 | 异步 ORM | Phase 2 |
| alembic | 1.14.0 | 数据库迁移版本管理 | Phase 2 |
| structlog | 24.4.0 | 结构化日志 | Phase 1 |

### 开发工具链（不进入生产依赖）

| 组件 | 锁定版本 | 用途 |
|------|---------|------|
| black | 24.10.0 | 代码格式化 |
| isort | 5.13.2 | import 排序 |
| mypy | 1.13.0 | 静态类型检查 |
| ruff | 0.8.0 | 快速 Linter（替代 flake8） |
| pre-commit | 4.0.1 | Git hooks 管理 |
| pytest-cov | 6.0.0 | 代码覆盖率 |
| safety | 3.2.x | 依赖安全扫描 |

---

## 1. 总览与进度追踪

### 版本路线图

```
v1.0.0 ──→ v1.0.1 ──→ v1.1.0 ──→ v1.2.0 ──→ v2.0.0 ──→ v2.1.0 ──→ v3.0.0
 (当前)  Phase 0a   Phase 0b   Phase 1    Phase 2    Phase 3    Phase 4
 6.93分  安全止血   工程化加固   架构解耦    引擎服务化  平台基础    完整平台
                             +核心重构    +持久化    分布式+调度  全功能
```

### 总进度看板

| 阶段 | 状态 | 开始日期 | 预计完成 | 实际完成 | 任务数 |
|------|------|---------|---------|---------|--------|
| Phase 0a | ⬜ 未开始 | — | — | — | 4 |
| Phase 0b | ⬜ 未开始 | — | — | — | 3 |
| Phase 1 | ⬜ 未开始 | — | — | — | 10 |
| Phase 2 | ⬜ 未开始 | — | — | — | 8 |
| Phase 3 | ⬜ 未开始 | — | — | — | 6 |
| Phase 4 | ⬜ 未开始 | — | — | — | 8 |
| **合计** | **0 / 39** | | | | 39 |

状态图例: ⬜ 未开始 | 🔄 进行中 | ✅ 已完成 | ❌ 已取消

---

## Phase 0a: 安全止血

**优先级**: 🔴 P0 - 紧急  
**预计工期**: 1 周  
**目标版本**: v1.0.1  
**评审依据**: [架构评审 §8 安全性评审]  
**设计原则**: 先止血，后加固。本阶段只处理有实际安全风险的 4 项，避免赶工遗漏。

> ⚠️ 本阶段完成后必须通过 `testcases/` 中现有用例的全量回归。

### 任务清单

#### T0a-1: Shell 注入安全加固
- **文件**: `framework/fixtures_loader.py`
- **问题**: `subprocess.run` 直接执行用户输入的命令
- **方案**: 
  1. 新增 `AllowedCommands` 白名单配置
  2. 对命令做参数解析 + 白名单校验
  3. 增加命令执行超时（默认 30s）
  4. 沙箱化执行（禁止网络操作、文件写入敏感路径）
- **验收**: Shell 动作无法执行未注册命令，超时可控

#### T0a-2: 日志敏感信息脱敏
- **文件**: `framework/utils/logger.py`, 新增 `framework/utils/masker.py`
- **问题**: 请求/响应原文包含 token、password 等敏感字段
- **方案**:
  1. 新增 `SensitiveDataMasker` 类
  2. 内置脱敏规则: `Authorization`, `password`, `token`, `secret`, `api_key`, `Cookie`
  3. 支持 `config.yaml` 中配置额外脱敏字段
  4. 请求日志和响应日志自动脱敏
  5. 脱敏逻辑独立成单独模块，便于单元测试
- **验收**: 日志中不再出现明文 token / password；`tests/framework/utils/test_masker.py` 覆盖全部内置规则

#### T0a-3: 断言操作符线程安全
- **文件**: `framework/assertion.py`
- **问题**: `CLASS_VAR` 全局注册表在多 worker 并发时非线程安全
- **方案**:
  1. 将 `OPERATORS` 从 `ClassVar` 改为实例属性 `self._operators`
  2. 构造函数中深拷贝默认注册表
  3. `register_operator` 改为支持实例级注册
  4. 保留类级别默认注册表作为 fallback
- **验收**: pytest-xdist 4 workers 并发执行无断言注册冲突

#### T0a-4: 配置 Schema 校验
- **文件**: `framework/config.py`, 新增 `framework/config_schema.py`
- **问题**: 配置错误在运行时才能发现
- **方案**:
  1. 使用 Pydantic v2 定义 `HttpConfig`, `LoggingConfig`, `ReportConfig`, `ExecutionConfig`, `DBConfig` 模型
  2. `ConfigLoader.load()` 返回时调用 `model_validate()`
  3. 配置错误时给出明确字段路径和期望类型
- **验收**: 错误配置在启动时报错而非运行时；`tests/framework/test_config.py` 覆盖常见配置错误场景

---

## Phase 0b: 工程化加固

**优先级**: 🟡 P1 - 高  
**预计工期**: 1 周  
**目标版本**: v1.1.0  
**评审依据**: [架构评审 §7 CI/CD 评审]  
**前置条件**: Phase 0a 全部完成并通过回归测试

### 任务清单

#### T0b-1: 工程化加固
- **文件**: 新增 `.pre-commit-config.yaml`, `pyproject.toml`（补充）, `.dockerignore`
- **内容**:
  1. 配置 pre-commit hooks: `ruff`, `black`, `isort`, `mypy`
  2. `pyproject.toml` 增加 `[tool.black]`, `[tool.isort]`, `[tool.mypy]`, `[tool.ruff]` 配置
  3. 新增 `.dockerignore`（排除 `__pycache__`, `.git`, `reports`, `logs`, `.venv`）
  4. Dockerfile 优化：先 `COPY requirements.txt` + `pip install`，再 `COPY . .`
- **验收**: `pre-commit run --all-files` 通过

#### T0b-2: GitHub Actions 安全扫描
- **文件**: `.github/workflows/test.yml`, 新增 `.github/dependabot.yml`
- **内容**:
  1. 增加 Dependabot 配置（pip 每周检查）
  2. CI 增加 `safety check` 步骤
  3. CI 增加 `bandit` 安全代码扫描
- **验收**: CI pipeline 包含安全扫描步骤，且全部通过

#### T0b-3: 容器化完善
- **文件**: `Dockerfile`, `docker-compose.test.yml`
- **内容**:
  1. Dockerfile 改用多阶段构建（builder + runtime）
  2. docker-compose 增加 db 服务（MySQL/PostgreSQL）和 mock 服务（可选）
  3. 增加健康检查 `HEALTHCHECK`
  4. 使用非 root 用户运行
- **验收**: `docker compose up` 一键启动完整测试环境

---

## Phase 1: 架构解耦与核心重构

**优先级**: 🟡 P1 - 高  
**预计工期**: 3-4 周（含回归测试缓冲）  
**目标版本**: v1.2.0  
**评审依据**: [架构评审 §5 解耦程度分析] + [§3.4 执行引擎] + [§3.11 报告模块] + [§3.12 插件系统]  
**前置条件**: Phase 0b 全部完成

> ⚠️ 本阶段涉及大量核心模块重构（执行引擎策略化、上下文改 contextvars、报告解耦），必须配合回归测试，确保不破坏已有功能。

### 测试基础设施（Phase 1 前置）

在开始重构前，先建立 `tests/` 目录结构：

```
tests/
├── __init__.py
├── conftest.py                    # 测试专用 fixtures
├── framework/
│   ├── __init__.py
│   ├── test_assertion.py          # 断言引擎单元测试
│   ├── test_extractor.py          # 提取器单元测试
│   ├── test_runner.py             # 执行引擎单元测试
│   ├── test_client.py             # HTTP 客户端单元测试
│   ├── test_config.py             # 配置加载器单元测试
│   ├── test_context.py            # 上下文管理单元测试
│   ├── test_parser.py             # 解析器单元测试
│   ├── utils/
│   │   ├── test_template.py
│   │   ├── test_masker.py
│   │   └── test_retry.py
│   └── plugins/
│       └── test_auth_manager.py
└── smoke/                         # 冒烟测试（每次重构后必跑）
    └── test_all_existing_cases.py # 运行现有 testcases/ 全量用例
```

### 任务清单

#### T1-1: 报告引擎抽象与解耦
- **文件**: `framework/report.py` → 重构为 `framework/report/`
- **方案**:
  ```
  framework/report/
  ├── __init__.py
  ├── base.py          # ReportAdapter 抽象基类
  ├── allure.py        # AllureAdapter 实现（从 report.py 迁移）
  ├── html_adapter.py  # 新增: pytest-html 适配器
  └── models.py        # 报告数据模型（统一数据结构）
  ```
- **关键接口**:
  ```python
  class ReportAdapter(ABC):
      @abstractmethod
      def attach_request(self, request: HttpRequest, url: str) -> None: ...
      @abstractmethod
      def attach_response(self, response: HttpResponse) -> None: ...
      @abstractmethod
      def attach_assertions(self, report: AssertionReport) -> None: ...
      @abstractmethod
      def attach_db_query(self, sql: str, result: Any, connection: str) -> None: ...
      @abstractmethod
      def set_environment(self, env: EnvConfig) -> None: ...
      @abstractmethod
      def set_case_labels(self, tags: list[str], priority: str) -> None: ...
  ```
- **验收**: runner 和 conftest 通过 `ReportAdapter` 接口调用，可替换实现

#### T1-2: 执行引擎协议分离（策略模式）
- **文件**: `framework/runner.py` → 拆分为 `framework/runner.py` + `framework/executors/`
- **方案**:
  ```
  framework/executors/
  ├── __init__.py
  ├── base.py           # StepExecutor 抽象基类
  ├── http_executor.py  # HTTP 步骤执行器
  └── ws_executor.py    # WebSocket 步骤执行器
  ```
- **关键接口**:
  ```python
  class StepExecutor(ABC):
      @abstractmethod
      def execute(self, case: TestCase, context: TestContext, variables: dict) -> CaseResult: ...
      @abstractmethod
      def supports(self, case: TestCase) -> bool: ...
  ```
- **runner.py 变更**: `_run_http_case` / `_run_ws_case` 逻辑迁移到对应 executor
- **验收**: 新增协议类型（gRPC）无需修改 `runner.py`

#### T1-3: 插件系统升级
- **文件**: `framework/plugins/base.py`
- **方案**:
  1. 新增钩子: `on_assertion`, `on_extract`, `on_setup`, `on_teardown`, `on_retry`, `on_db_query`
  2. 增加 `priority: int = 100` 优先级字段
  3. 增加 `PluginManager` 类：注册、排序、生命周期分发
  4. 插件自动发现：扫描 `framework/plugins/` 目录下 `PluginBase` 子类
  5. 支持插件间数据共享 `PluginContext`
- **新增文件**: `framework/plugins/manager.py`
- **验收**: 多个插件按优先级顺序执行，支持自定义钩子

#### T1-4: 上下文管理升级
- **文件**: `framework/context.py`
- **方案**:
  1. `threading.local` → `contextvars`（兼容 asyncio）
  2. 增加 step 级上下文快照（多步骤用例每步独立）
  3. 增加上下文序列化方法 `to_dict()` / `from_dict()`
  4. 增加变量作用域概念: `suite` → `case` → `step`
- **验收**: asyncio 协程环境正常工作，步骤间上下文隔离

#### T1-5: 日志结构化改造
- **文件**: `framework/utils/logger.py`
- **方案**:
  1. 引入 `structlog` 作为结构化日志引擎
  2. 每条日志自动附加 `trace_id`（基于 case 名称 + 时间戳）
  3. 支持 JSON 格式输出（配置项 `logging.format: json`）
  4. 兼容原有 `logging` 接口，渐进式迁移
  5. 移除未使用的 `loguru` 依赖，统一到 `structlog`
- **验收**: 日志可被 ELK/Loki 采集解析，trace_id 串联完整调用链

#### T1-6: 配置模块增强
- **文件**: `framework/config.py`
- **方案**:
  1. 配置监听文件变化（`watchdog`），支持运行时重载（可选）
  2. `_deep_merge` 支持 list 增量合并策略
  3. 增加 `ConfigValidationError` 自定义异常
- **验收**: 配置 schema 校验 + deep_merge list 策略

#### T1-7: conftest 与框架解耦
- **文件**: `conftest.py`
- **方案**:
  1. 抽取 `YamlFile` / `YamlItem` 到 `framework/collector.py`
  2. `_get_runner()` 改用 fixture 注入而非手动构造
  3. conftest 仅保留 `pytest_addoption` + fixture 注册 + YAML 收集入口
- **新增文件**: `framework/collector.py`
- **验收**: conftest 代码量减少 60%+，核心逻辑在 framework 内

#### T1-8: HTTP 客户端拦截器链
- **文件**: `framework/client.py`
- **方案**:
  1. 新增 `RequestInterceptor` 抽象基类
  2. `HttpClient` 支持 `add_interceptor()` 注册
  3. 请求前链式调用 `on_request`，响应后链式调用 `on_response`
  4. 内置拦截器：`AuthInterceptor`（迁移 auth_manager 逻辑）、`LoggingInterceptor`（日志分离）
- **新增文件**: `framework/interceptors/`
- **验收**: 新增签名/加密逻辑通过拦截器实现，无需修改 client 核心

#### T1-9: 模型与格式解耦
- **文件**: `framework/models.py`
- **方案**:
  1. 将 `_operator_registry` 从 `AssertItem` 中移除
  2. `TestCase` / `TestSuite` 不再暴露 YAML 特有字段（如 `source_file`, `line_number`, `data_driven`）
  3. 新增 `ParsedCase` 中间模型隔离解析格式
- **验收**: models.py 不依赖任何 YAML 特有概念

#### T1-10: 核心模块单元测试覆盖
- **新增目录**: `tests/`（详见上方测试基础设施结构）
- **方案**:
  1. 为每个重构模块编写单元测试（白盒 + 黑盒）
  2. **最低覆盖目标**（按 pytest-cov 统计）：
     - `assertion.py` ≥ 90%（16 种操作符 + 嵌套取值 + 边界条件）
     - `extractor.py` ≥ 85%（6 种提取类型 + 默认值回退）
     - `runner.py` ≥ 80%（HTTP/WS 主路径 + 异常路径）
     - `config.py` ≥ 85%（多环境合并 + 优先级 + schema 校验）
     - `context.py` ≥ 90%（线程安全 + contextvars + 序列化）
  3. 建立 `tests/smoke/test_all_existing_cases.py`：每次重构后运行现有 `testcases/` 全量用例
  4. CI 增加 `pytest --cov=framework --cov-report=term` 步骤
- **依赖**: `pytest-cov>=6.0.0`
- **验收**: 核心模块覆盖率达标；`tests/smoke/` 下冒烟测试通过

---

## Phase 2: 引擎服务化与持久化

**优先级**: 🟡 P1 - 高  
**预计工期**: 4 周  
**目标版本**: v2.0.0  
**评审依据**: [架构评审 §6 向测试平台演进可行性]  
**前置条件**: Phase 1 全部完成 + 核心模块测试覆盖率达标

> ⚠️ 本阶段产出的 FastAPI 服务是 Phase 3 分布式执行的基石。建议先通过同步线程池模式稳定运行一段时间，再在 Phase 3 接入 Celery。保留"单机执行模式"作为回退选项。

### 任务清单

#### T2-1: FastAPI REST 服务层
- **新增目录**: `api/`
- **结构**:
  ```
  api/
  ├── __init__.py
  ├── main.py              # FastAPI app 入口
  ├── dependencies.py      # 依赖注入（DB session, config）
  ├── routers/
  │   ├── __init__.py
  │   ├── cases.py         # 用例 CRUD
  │   ├── suites.py        # 套件 CRUD
  │   ├── executions.py    # 执行触发 + 结果查询
  │   └── reports.py       # 报告查询
  └── schemas/
      ├── __init__.py
      ├── case.py           # 用例请求/响应 Schema
      ├── execution.py      # 执行请求/响应 Schema
      └── report.py         # 报告 Schema
  ```
- **核心接口**:
  | 方法 | 路径 | 说明 |
  |------|------|------|
  | `POST` | `/api/v1/cases` | 创建用例 |
  | `GET` | `/api/v1/cases/{id}` | 查询用例 |
  | `PUT` | `/api/v1/cases/{id}` | 更新用例 |
  | `DELETE` | `/api/v1/cases/{id}` | 删除用例 |
  | `GET` | `/api/v1/cases` | 列表（分页+过滤） |
  | `POST` | `/api/v1/executions` | 触发执行 |
  | `GET` | `/api/v1/executions/{id}` | 查询执行结果 |
  | `GET` | `/api/v1/executions/{id}/report` | 执行报告详情 |
- **验收**: Swagger UI 可访问，CRUD 接口可用

#### T2-2: 数据持久化（SQLite → PostgreSQL）
- **新增目录**: `framework/persistence/`
- **结构**:
  ```
  framework/persistence/
  ├── __init__.py
  ├── database.py          # AsyncEngine 工厂
  ├── models/              # SQLAlchemy ORM 模型
  │   ├── __init__.py
  │   ├── test_case.py
  │   ├── test_suite.py
  │   ├── execution.py
  │   └── report.py
  └── repositories/        # Repository 模式
      ├── __init__.py
      ├── base.py
      ├── case_repo.py
      ├── suite_repo.py
      ├── execution_repo.py
      └── report_repo.py
  ```
- **数据库表**:
  | 表名 | 核心字段 |
  |------|---------|
  | `test_cases` | id, name, yaml_content, tags, priority, created_at, updated_at, version |
  | `test_suites` | id, name, description, config, created_at |
  | `executions` | id, suite_id, status, trigger, started_at, finished_at, env |
  | `execution_results` | id, execution_id, case_id, passed, error, request, response, elapsed_ms |
  | `reports` | id, execution_id, summary, detail_data |
- **迁移工具**: Alembic（`alembic/` 目录）
- **验收**: 用例持久化到 DB，支持版本历史查询

#### T2-3: 用例 YAML ↔ DB 双向同步
- **新增文件**: `framework/sync.py`
- **方案**:
  1. `YAML → DB`: 导入器，解析 `.yaml` 文件写入数据库
  2. `DB → YAML`: 导出器，从数据库生成 `.yaml` 文件
  3. CLI 命令: `autotest sync --from yaml --to db` / `autotest sync --from db --to yaml`
- **验收**: 用例可在文件系统和数据库间双向同步

#### T2-4: 报告数据持久化 + 历史查询
- **文件**: `framework/report/` 扩展
- **方案**:
  1. `ExecutionRepository` 存储每次执行结果
  2. `ReportService` 提供聚合查询：通过率趋势、平均响应时间趋势、Top 失败用例
  3. API 接口: `GET /api/v1/reports/trends?days=7`
- **验收**: 可查询历史 30 天测试趋势数据

#### T2-5: OpenAPI / Swagger 导入解析器
- **新增文件**: `framework/parser/openapi_parser.py`
- **方案**:
  1. 解析 OpenAPI 3.x JSON/YAML Spec
  2. 自动生成 TestCase 列表（每个 path + method 一个用例）
  3. 从 `responses` 和 `examples` 推断断言
  4. API: `POST /api/v1/cases/import` 接收 OpenAPI spec URL
- **依赖**: `openapi-spec-validator>=0.7.0`
- **验收**: 输入 Swagger URL，自动生成可执行用例

#### T2-6: CLI 工具
- **新增文件**: `cli.py`（项目根目录）
- **方案**:
  1. 基于 `click` 或 `typer` 构建
  2. 命令:
     ```bash
     autotest run --suite smoke --env dev
     autotest sync --from yaml --to db
     autotest import --source https://api.example.com/openapi.json
     autotest serve  # 启动 API 服务
     autotest report --execution-id <id>
     ```
  3. `pyproject.toml` 注册 `[project.scripts]`
- **依赖**: `typer>=0.15.0`
- **验收**: `autotest --help` 显示所有命令

#### T2-7: 异步执行支持
- **文件**: `framework/runner.py`, `framework/client.py`
- **方案**:
  1. `HttpClient` 增加 `AsyncHttpClient` 变体（基于 `httpx.AsyncClient`）
  2. `TestRunner` 增加 `arun_case()` 异步方法
  3. API 层通过 `asyncio` 调用异步 runner
- **验收**: API 触发执行不阻塞请求线程

#### T2-8: 依赖安全与版本锁定
- **文件**: `requirements.txt` → `pyproject.toml`（PEP 621 依赖声明）
- **方案**:
  1. 所有依赖迁移到 `pyproject.toml` 的 `[project]` + `[project.optional-dependencies]`
  2. 使用固定版本号（`==` 锁定，非 `>=`）
  3. 生成 `requirements.lock`（pip-tools 或 uv）
  4. `requirements.txt` 保留为 lock file 导出
- **验收**: `pip install -e ".[all]"` 安装全部依赖

---

## Phase 3: 平台化基础建设

**优先级**: 🟢 P2 - 中  
**预计工期**: 4 周  
**目标版本**: v2.1.0  
**评审依据**: [架构评审 §6.2 差距分析] + [§6.3 演进路径 Phase 2]  
**前置条件**: Phase 2 全部完成 + FastAPI 服务单机稳定运行

> ⚠️ 前端推迟到 Phase 4。Phase 3 用 Swagger UI（FastAPI 自带）作为过渡管理界面，专注后端分布式能力。
> ⚠️ Celery 分布式执行需保留**单机执行模式**作为回退选项（Phase 2 的同步线程池模式），通过配置项 `execution.mode: local|distributed` 切换。

### 任务清单

#### T3-1: 分布式执行（Master-Worker 架构，保留单机回退）
- **新增目录**: `worker/`
- **方案**:
  1. 基于 Celery + Redis 构建任务队列
  2. **Master**: API 服务接收执行请求 → 发布任务到 Celery
  3. **Worker**: Celery worker 拉取任务 → 调用 `TestRunner` → 上报结果
  4. **Broker**: Redis（消息队列）
  5. **Backend**: PostgreSQL（结果存储）
  6. **回退机制**: `execution.mode: local` 时走 Phase 2 的同步线程池，不依赖 Redis/Celery
- **依赖**: `celery>=5.4.0`, `redis>=5.2.0`
- **验收**: 多 Worker 并行执行不同套件；配置 `mode: local` 后不依赖 Redis 仍可执行

#### T3-2: 执行调度引擎
- **新增文件**: `framework/scheduler.py`, `api/routers/schedules.py`
- **方案**:
  1. 基于 APScheduler 构建
  2. 支持三种触发方式：Cron 定时 / Interval 间隔 / 手动触发
  3. API: `POST /api/v1/schedules` 创建定时任务
  4. 调度器状态持久化到 DB
- **依赖**: `apscheduler>=3.10.0`
- **验收**: 定时任务自动触发执行

#### T3-3: 环境管理服务
- **新增文件**: `api/routers/environments.py`, `framework/persistence/models/environment.py`
- **方案**:
  1. 环境配置从 YAML 文件迁移到 DB
  2. API: CRUD 环境（`POST/GET/PUT/DELETE /api/v1/environments`）
  3. 支持环境变量绑定（每个环境独立的 env var 集）
  4. 执行时动态选择环境
- **验收**: 在线管理环境配置，无需修改文件

#### T3-4: 告警通知服务
- **新增目录**: `framework/notifications/`
- **结构**:
  ```
  framework/notifications/
  ├── __init__.py
  ├── base.py            # NotificationChannel 抽象
  ├── email_channel.py
  ├── wecom_channel.py   # 企业微信
  ├── dingtalk_channel.py # 钉钉
  └── webhook_channel.py
  ```
- **方案**:
  1. 执行完成 / 失败率超过阈值时触发通知
  2. 通知规则可配置: 全部 / 仅失败 / 失败率 > N%
- **验收**: 测试失败后收到企业微信消息

#### T3-5: gRPC 协议支持（可选插件）
- **新增文件**: `framework/executors/grpc_executor.py`, `framework/models/grpc.py`
- **方案**:
  1. 基于 `grpcio` + `grpcio-reflection` 构建
  2. 支持 proto 文件解析或服务反射
  3. YAML 用例格式扩展:
     ```yaml
     grpc:
       service: "package.ServiceName"
       method: "MethodName"
       proto_file: "path/to/service.proto"
       body: { ... }
     ```
  4. **设计为可选 extra 依赖** `pip install autotest[grpc]`，不占用核心工期
  5. 仅实现 executor 扩展点，不做 proto 管理 UI
- **依赖**: `grpcio>=1.68.0`, `grpcio-reflection>=1.68.0`, `protobuf>=5.29.0`
- **验收**: 可执行 gRPC 接口测试；不安装 `[grpc]` extra 时不影响其他功能

#### T3-6: Docker Compose 全栈部署（不含前端）
- **文件**: `docker-compose.yml`（生产级）, `docker-compose.dev.yml`
- **服务编排**:
  ```yaml
  services:
    api:        # FastAPI 服务（含 Swagger UI 管理界面）
    worker:     # Celery Worker
    redis:      # 消息队列
    postgres:   # 主数据库
    nginx:      # 反向代理
  ```
- **验收**: `docker compose up -d` 启动完整平台后端；Swagger UI 可访问管理 API

---

## Phase 4: 完整测试平台

**优先级**: 🔵 P3 - 低  
**预计工期**: 6 周  
**目标版本**: v3.0.0  
**评审依据**: [架构评审 §6.3 演进路径 Phase 3]  
**前置条件**: Phase 3 全部完成

### 任务清单

#### T4-1: 基础 Web 前端
- **新增目录**: `frontend/`
- **方案**:
  1. 基于 Vue 3 + Vite + TDesign 构建
  2. 核心页面:
     - 用例列表（表格 + 搜索 + 标签过滤）
     - 用例编辑（YAML 编辑器 + 表单编辑）
     - 执行历史（时间线 + 结果列表）
     - 报告看板（通过率趋势图 + 饼图）
     - 环境管理
  3. SPA 打包后挂载到 FastAPI 静态文件
- **依赖**: Node.js 20 LTS, Vue 3.5+, TDesign Vue Next 1.13+
- **验收**: 浏览器访问 `/app` 显示管理界面

#### T4-2: Mock 服务引擎
- **新增目录**: `framework/mock/`
- **方案**:
  1. 基于 `WireMock`（Java）或自研轻量 Mock Server
  2. 支持静态配置和动态规则
  3. 与用例联动：用例执行前自动设置 Mock 规则
  4. fixture 类型扩展: `mock_setup` / `mock_teardown`
- **验收**: 可 Mock 下游接口，不依赖真实服务

#### T4-3: 流量录制与回放
- **新增目录**: `framework/recorder/`
- **方案**:
  1. 中间件模式录制真实流量（Go 或 Python sidecar）
  2. 录制格式: HAR / 自定义格式
  3. 回放引擎: 对比录制响应与实际响应
  4. 生成差异报告
- **验收**: 可录制线上流量并回放验证

#### T4-4: 智能断言与响应模型自动校验
- **新增文件**: `framework/assertion/smart.py`
- **方案**:
  1. 基于历史成功响应的 Schema 推断
  2. 自动生成字段类型、必填、格式断言
  3. 响应结构变更自动检测
- **验收**: 可自动生成基础断言，减少手写断言量

#### T4-5: 多租户与 RBAC
- **新增文件**: `api/routers/auth.py`, `framework/persistence/models/user.py`
- **方案**:
  1. JWT 认证
  2. 角色: admin / editor / viewer
  3. 权限: 项目级隔离
- **依赖**: `python-jose>=3.3.0`, `passlib>=1.7.4`
- **验收**: 不同角色用户看到不同功能和数据

#### T4-6: 报告聚合与高级分析
- **新增文件**: `api/routers/analytics.py`
- **方案**:
  1. 接口稳定性排行（Top N 不稳定接口）
  2. 响应时间分位数（P50/P95/P99）
  3. 失败原因分类统计
  4. 自动化测试 ROI 报表
- **验收**: 报表页面可视化展示分析数据

#### T4-7: 用例推荐与智能生成
- **新增文件**: `framework/generator.py`
- **方案**:
  1. 基于 OpenAPI spec 自动生成覆盖率报告
  2. 识别未覆盖的 API 端点
  3. 推荐补全用例
  4. 基于流量日志自动生成用例
- **验收**: 输入 spec 文件，输出覆盖率报告

#### T4-8: K8s 部署支持
- **新增目录**: `deploy/k8s/`
- **内容**:
  1. Deployment + Service + ConfigMap YAML
  2. HPA 自动扩缩容配置
  3. Ingress 配置
  4. Helm Chart
- **验收**: `kubectl apply -f deploy/k8s/` 部署成功

---

## 附录: 文件结构变更总览

### 当前结构 → 目标结构

```
当前 (v1.0.0)                          目标 (v3.0.0)
───────────────                        ───────────────
api-test-framework/                    api-test-framework/
├── assertions/                        ├── alembic/                 🆕
├── config/                            │   ├── versions/
│   ├── config.yaml                    │   └── env.py
│   ├── env.yaml                       ├── api/                     🆕
│   └── env.local.yaml                 │   ├── main.py
├── conftest.py                        │   ├── dependencies.py
├── framework/                         │   ├── routers/
│   ├── __init__.py                    │   └── schemas/
│   ├── assertion.py                   ├── assertions/
│   ├── client.py                      ├── cli.py                   🆕
│   ├── config.py                      ├── config/
│   ├── context.py                     ├── conftest.py              ♻️ 精简
│   ├── db.py                          ├── deploy/
│   ├── extractor.py                   │   └── k8s/                🆕 (Phase 4)
│   ├── fixtures_loader.py             ├── docker-compose.yml       ♻️
│   ├── models.py                      ├── docker-compose.dev.yml   🆕
│   ├── parser.py                      ├── Dockerfile               ♻️
│   ├── plugins/                       ├── framework/
│   │   ├── base.py                    │   ├── __init__.py
│   │   └── auth_manager.py            │   ├── assertion/           ♻️
│   ├── report.py                      │   ├── collector.py         🆕
│   ├── runner.py                      │   ├── client.py            ♻️
│   ├── utils/                         │   ├── config.py            ♻️
│   └── ws.py                          │   ├── config_schema.py     🆕
├── testcases/                         │   ├── context.py           ♻️
├── test_data/                         │   ├── db.py                ♻️
├── docker-compose.test.yml            │   ├── executors/           🆕
├── Dockerfile                         │   │   ├── base.py
├── Jenkinsfile                        │   │   ├── http_executor.py
├── Makefile                           │   │   ├── ws_executor.py
├── pyproject.toml                     │   │   └── grpc_executor.py 🆕 (Phase 3, optional extra)
├── requirements.txt                   │   ├── extractor.py
└── README.md                          │   ├── fixtures_loader.py   ♻️
                                       │   ├── generator.py         🆕 (Phase 4)
                                       │   ├── interceptors/        🆕
                                       │   ├── mock/                🆕 (Phase 4)
                                       │   ├── models.py            ♻️
                                       │   ├── notifications/       🆕 (Phase 3)
                                       │   ├── parser/
                                       │   │   ├── yaml_parser.py   ♻️
                                       │   │   └── openapi_parser.py🆕 (Phase 2)
                                       │   ├── persistence/         🆕 (Phase 2)
                                       │   ├── plugins/
                                       │   │   ├── base.py          ♻️
                                       │   │   ├── manager.py       🆕
                                       │   │   └── auth_manager.py
                                       │   ├── recorder/            🆕 (Phase 4)
                                       │   ├── report/              ♻️
                                       │   │   ├── base.py
                                       │   │   ├── allure.py
                                       │   │   └── html_adapter.py
                                       │   ├── runner.py            ♻️
                                       │   ├── scheduler.py         🆕 (Phase 3)
                                       │   ├── sync.py              🆕 (Phase 2)
                                       │   └── utils/
                                       │       ├── masker.py        🆕 (Phase 0a)
                                       │       └── ...
                                       ├── frontend/                🆕 (Phase 4)
                                       ├── tests/                   🆕 (Phase 1)
                                       │   ├── framework/
                                       │   └── smoke/
                                       ├── testcases/
                                       ├── test_data/
                                       ├── worker/                  🆕 (Phase 3)
                                       ├── .pre-commit-config.yaml  🆕 (Phase 0b)
                                       ├── .dockerignore            🆕 (Phase 0b)
                                       ├── pyproject.toml           ♻️
                                       └── README.md                ♻️
```

图例: ♻️ 重构 | 🆕 新增 | 标注了引入的阶段

---

> **使用说明**: 每次开始开发时，打开本文档确认当前阶段和任务进度。完成一个 task 后将状态从 `⬜` 改为 `🔄`（进行中）或 `✅`（已完成）。每个 Phase 完成后更新总进度看板。
>
> **下一步**: 从 Phase 0a - T0a-1 开始执行安全修复。

---

## 修订记录

| 版本 | 日期 | 修订内容 |
|------|------|---------|
| 1.0 | 2026-06-03 | 初始版本，基于架构评审报告制定 |
| 1.1 | 2026-06-03 | 根据评审反馈调整：<br>① Phase 0 拆分为 0a（安全止血 1周） + 0b（工程化加固 1周）<br>② Phase 1 增加 T1-10 核心模块单元测试覆盖 + `tests/` 目录<br>③ Phase 3 前端推迟至 Phase 4，gRPC 降级为可选插件<br>④ Phase 3 分布式执行增加单机回退模式<br>⑤ 总计 39 个任务，总工期 18-19 周
