# AutoTest Framework 开发计划（第二版）

> **计划版本**: 2.0  
> **制定日期**: 2026-06-05  
> **修订日期**: 2026-06-05  
> **关联文档**: [架构评审报告 v2](./architecture-review.md)  
> **当前版本**: v1.2.0（Phase 0a/0b/1 已完成）  
> **目标版本**: v1.2.0 → v3.0.0（分阶段交付）  
> **技术栈基线**: Python 3.12 | pytest 8.x | httpx 0.28.x | Pydantic 2.10.x | structlog 24.4.x

---

## 目录

1. [总览与进度追踪](#1-总览与进度追踪)
2. [已完成阶段回顾](#2-已完成阶段回顾)
3. [Phase 2: 引擎服务化与持久化（4周）](#phase-2-引擎服务化与持久化)
4. [Phase 3: 平台化基础建设（4周）](#phase-3-平台化基础建设)
5. [Phase 4: 完整测试平台（6周）](#phase-4-完整测试平台)
6. [附录: 文件结构变更总览](#附录-文件结构变更总览)
7. [修订记录](#修订记录)

---

## 1. 总览与进度追踪

### 版本路线图

```
v1.0.0 ──→ v1.0.1 ──→ v1.1.0 ──→ v1.2.0 ──→ v2.0.0 ──→ v2.1.0 ──→ v3.0.0
 (起点)  Phase 0a   Phase 0b   Phase 1    Phase 2    Phase 3    Phase 4
 6.93分  安全止血   工程化加固  架构解耦    引擎服务化  平台基础    完整平台
 ✅✅✅   ✅         ✅          ✅          +持久化     分布式+调度  全功能
                                                            8.22分→
```

### 总进度看板

| 阶段 | 状态 | 开始日期 | 完成日期 | 任务数 |
|------|------|---------|---------|--------|
| Phase 0a: 安全止血 | ✅ 已完成 | 2026-06-03 | 2026-06-04 | 4 |
| Phase 0b: 工程化加固 | ✅ 已完成 | 2026-06-04 | 2026-06-05 | 3 |
| Phase 1: 架构解耦与核心重构 | ✅ 已完成 | 2026-06-05 | 2026-06-05 | 10 |
| Phase 2: 引擎服务化与持久化 | ⬜ 未开始 | — | — | 8 |
| Phase 3: 平台化基础建设 | ⬜ 未开始 | — | — | 6 |
| Phase 4: 完整测试平台 | ⬜ 未开始 | — | — | 8 |
| **合计** | **17 / 39** | | | 39 |

状态图例: ⬜ 未开始 | 🔄 进行中 | ✅ 已完成 | ❌ 已取消

---

## 2. 已完成阶段回顾

### Phase 0a: 安全止血 ✅

**目标版本**: v1.0.1 | **状态**: 全部完成

| 任务 | 完成内容 | 关键产出 |
|------|---------|---------|
| T0a-1: Shell 注入安全加固 | ✅ | 白名单 + shlex + 沙箱 + 超时；`SecurityError` 异常 |
| T0a-2: 日志敏感信息脱敏 | ✅ | `SensitiveDataMasker` 类（10 字段 + 正则替换 + 可扩展） |
| T0a-3: 断言操作符线程安全 | ✅ | `MappingProxyType` 不可变默认表 + 实例 deepcopy |
| T0a-4: 配置 Schema 校验 | ✅ | `config_schema.py`（5 个 Pydantic 模型 + `ConfigValidationError`） |

### Phase 0b: 工程化加固 ✅

**目标版本**: v1.1.0 | **状态**: 全部完成

| 任务 | 完成内容 | 关键产出 |
|------|---------|---------|
| T0b-1: 工程化加固 | ✅ | `.pre-commit-config.yaml` + `pyproject.toml` 补充 + `.dockerignore` |
| T0b-2: GitHub Actions 安全扫描 | ✅ | Safety + Bandit + Dependabot 配置 |
| T0b-3: 容器化完善 | ✅ | Dockerfile 三层构建 + docker-compose 健康检查 + 非 root 用户 |

### Phase 1: 架构解耦与核心重构 ✅

**目标版本**: v1.2.0 | **状态**: 全部完成

| 任务 | 完成内容 | 关键产出 |
|------|---------|---------|
| T1-1: 报告引擎抽象与解耦 | ✅ | `ReportAdapter` + `AllureReportAdapter` + `HtmlReportAdapter` + `NoopReportAdapter` + 工厂函数 |
| T1-2: 执行引擎协议分离 | ✅ | `StepExecutor` ABC + `HttpStepExecutor` + `WsStepExecutor` |
| T1-3: 插件系统升级 | ✅ | 13 个钩子 + `priority` + `PluginManager`（自动发现/排序/分发）+ `PluginContext` |
| T1-4: 上下文管理升级 | ✅ | `contextvars` + 三层作用域 + `start_step()/end_step()` + 序列化 |
| T1-5: 日志结构化改造 | ✅ | structlog + JSON 文件 + trace_id + SensitiveDataMasker 管道 |
| T1-6: 配置模块增强 | ✅ | Pydantic Schema + `ConfigValidationError.from_pydantic()` |
| T1-7: conftest 与框架解耦 | ✅ | `framework/collector.py`（YamlCollector + YamlFunction(pytest.Function)） |
| T1-8: HTTP 客户端拦截器链 | ✅ | `RequestInterceptor` ABC + `AuthInterceptor` + `LoggingInterceptor` + 洋葱模型 |
| T1-9: 模型与格式解耦 | ✅ | 操作符注册表迁移至 `AssertionEngine` |
| T1-10: 核心模块单元测试 | ✅ | `tests/` 目录 + 覆盖率目标 |

---

## Phase 2: 引擎服务化与持久化

**优先级**: 🟡 P1 - 高  
**预计工期**: 4 周  
**目标版本**: v2.0.0  
**评审依据**: [架构评审 v2 §9 向测试平台演进可行性]  
**前置条件**: Phase 1 全部完成（✅ 已满足）

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
  1. 基于 `typer` 构建
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

#### T2-8: 引擎层能力补齐
- **文件**: `framework/runner.py`, `framework/assertion.py`, `framework/extractor.py`
- **方案**:
  1. **用例级超时管控**: runner 中对每个 case 设置超时（默认 300s），超时则标记 `TIMEOUT`
  2. **组合断言**: `AssertItem` 增加 `logic: str = "and"` 字段，支持 and/or 组合
  3. **提取管道**: 新增 `ExtractPipeline` 支持对提取结果二次加工（如 `base64_decode` / `json_parse` / `strip`）
  4. **失败快照**: 用例失败时自动调用 `context.snapshot()` 并附加到 `CaseResult`
  5. **多数据源**: `DataSourceRegistry` 支持动态注册多个数据库连接
- **验收**: 超时/组合断言/提取管道/失败快照/多数据源均有单元测试

---

## Phase 3: 平台化基础建设

**优先级**: 🟢 P2 - 中  
**预计工期**: 4 周  
**目标版本**: v2.1.0  
**评审依据**: [架构评审 v2 §9.2 差距分析]  
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
**评审依据**: [架构评审 v2 §9.2 差距分析]  
**前置条件**: Phase 3 全部完成

### 任务清单

#### T4-1: 基础 Web 前端
- **新增目录**: `frontend/`
- **方案**:
  1. 基于 Vue 3 + Vite + TDesign 构建
  2. 核心页面: 用例列表、用例编辑、执行历史、报告看板、环境管理
  3. SPA 打包后挂载到 FastAPI 静态文件
- **依赖**: Node.js 20 LTS, Vue 3.5+, TDesign Vue Next 1.13+
- **验收**: 浏览器访问 `/app` 显示管理界面

#### T4-2: Mock 服务引擎
- **新增目录**: `framework/mock/`
- **方案**:
  1. 基于轻量 Mock Server 自研
  2. 支持静态配置和动态规则
  3. 与用例联动：用例执行前自动设置 Mock 规则
  4. fixture 类型扩展: `mock_setup` / `mock_teardown`
- **验收**: 可 Mock 下游接口，不依赖真实服务

#### T4-3: 流量录制与回放
- **新增目录**: `framework/recorder/`
- **方案**:
  1. 中间件模式录制真实流量
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
当前 (v1.2.0)                          目标 (v3.0.0)
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
│   ├── collector.py                   ├── config/
│   ├── config.py                      ├── conftest.py
│   ├── config_schema.py              ├── deploy/
│   ├── context.py                     │   └── k8s/                🆕 (Phase 4)
│   ├── db.py                          ├── docker-compose.yml       ♻️
│   ├── exceptions.py                  ├── docker-compose.dev.yml   🆕
│   ├── executors/                     ├── Dockerfile
│   │   ├── __init__.py                ├── framework/
│   │   ├── base.py                    │   ├── assertion/           ♻️
│   │   ├── http_executor.py           │   ├── client.py
│   │   └── ws_executor.py             │   ├── collector.py
│   ├── extractor.py                   │   ├── config.py
│   ├── fixtures_loader.py             │   ├── config_schema.py
│   ├── interceptors/                  │   ├── context.py
│   │   ├── __init__.py                │   ├── db.py
│   │   ├── auth.py                    │   ├── exceptions.py
│   │   ├── base.py                    │   ├── executors/
│   │   └── logging.py                 │   │   ├── base.py
│   ├── models.py                      │   │   ├── http_executor.py
│   ├── parser.py                      │   │   ├── ws_executor.py
│   ├── plugins/                       │   │   └── grpc_executor.py 🆕 (Phase 3)
│   │   ├── __init__.py                │   ├── extractor.py
│   │   ├── auth_manager.py            │   ├── fixtures_loader.py
│   │   ├── base.py                    │   ├── generator.py         🆕 (Phase 4)
│   │   └── manager.py                 │   ├── interceptors/
│   ├── report/                        │   ├── mock/                🆕 (Phase 4)
│   │   ├── __init__.py                │   ├── models.py
│   │   ├── allure.py                  │   ├── notifications/       🆕 (Phase 3)
│   │   ├── base.py                    │   ├── parser/
│   │   ├── html_adapter.py            │   │   ├── yaml_parser.py   ♻️
│   │   └── models.py                  │   │   └── openapi_parser.py🆕 (Phase 2)
│   ├── runner.py                      │   ├── persistence/         🆕 (Phase 2)
│   └── utils/                         │   ├── plugins/
│       ├── __init__.py                │   │   ├── base.py
│       ├── logger.py                  │   │   ├── manager.py
│       ├── masker.py                  │   │   └── auth_manager.py
│       └── template.py                │   ├── recorder/            🆕 (Phase 4)
├── testcases/                         │   ├── report/
├── tests/                             │   │   ├── base.py
│   ├── framework/                     │   │   ├── allure.py
│   └── smoke/                         │   │   ├── html_adapter.py
├── docker-compose.test.yml            │   │   └── models.py
├── Dockerfile                         │   ├── runner.py
├── Jenkinsfile                        │   ├── scheduler.py         🆕 (Phase 3)
├── Makefile                           │   ├── sync.py              🆕 (Phase 2)
├── pyproject.toml                     │   └── utils/
├── requirements.txt                   │       ├── logger.py
└── README.md                          │       ├── masker.py
                                       │       └── template.py
                                       ├── frontend/                🆕 (Phase 4)
                                       ├── tests/
                                       │   ├── framework/
                                       │   └── smoke/
                                       ├── testcases/
                                       ├── worker/                  🆕 (Phase 3)
                                       ├── .pre-commit-config.yaml
                                       ├── .dockerignore
                                       ├── pyproject.toml
                                       └── README.md                ♻️
```

图例: ♻️ 重构 | 🆕 新增 | 标注了引入的阶段

---

> **使用说明**: 每次开始开发时，打开本文档确认当前阶段和任务进度。完成一个 task 后将状态从 `⬜` 改为 `🔄`（进行中）或 `✅`（已完成）。每个 Phase 完成后更新总进度看板。
>
> **下一步**: 从 Phase 2 - T2-1 开始执行 FastAPI REST 服务层开发。

---

## 修订记录

| 版本 | 日期 | 修订内容 |
|------|------|---------|
| 1.0 | 2026-06-03 | 初始版本，基于架构评审报告制定 |
| 1.1 | 2026-06-03 | Phase 0 拆分、T1-10 补充、前端推迟、gRPC 降级 |
| 2.0 | 2026-06-05 | Phase 0a/0b/1 全部完成后的第二版：<br>① 已完成阶段回顾（17/39 任务完成）<br>② Phase 2 增加 T2-8 引擎层能力补齐（超时/组合断言/提取管道/失败快照/多数据源）<br>③ 架构评分从 6.93 提升至 8.22<br>④ 文件结构更新反映 Phase 1 产出 |
