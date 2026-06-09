# AutoTest Framework 开发计划（第三版）

> **计划版本**: 3.0  
> **制定日期**: 2026-06-09  
> **关联文档**: [架构评审报告 v4](./architecture-review.md)（评分 9.05/10）  
> **当前版本**: v2.1.0（Phase 0a/0b/1/2/3/4 大部分完成）  
> **目标版本**: v3.0.0（Phase 5 完成后）  
> **技术栈基线**: Python 3.12 | pytest 8.x | httpx 0.28.x | Pydantic 2.10.x | structlog 24.4.x

---

## 目录

1. [总览与进度追踪](#1-总览与进度追踪)
2. [已完成阶段回顾](#2-已完成阶段回顾)
3. [Phase 5: 平台完善与生产化（规划中）](#phase-5-平台完善与生产化)
4. [附录: 文件结构变更总览](#附录-文件结构变更总览)
5. [修订记录](#修订记录)

---

## 1. 总览与进度追踪

### 版本路线图

```
v1.0.0 ──→ v1.0.1 ──→ v1.1.0 ──→ v1.2.0 ──→ v2.0.0 ──→ v2.1.0 ──→ v3.0.0
 (起点)  Phase 0a   Phase 0b   Phase 1    Phase 2    Phase 3    Phase 5
 6.93分  安全止血   工程化加固  架构解耦    引擎服务化  平台基础    平台完善
 ✅✅✅   ✅         ✅          ✅          +持久化     分布式+调度  生产化
                                                                  9.05分
                                            ✅          ✅          ⬜
```

> **注**: Phase 4（完整测试平台）的大部分任务在实际开发中已随 Phase 2-3 并行推进完成，不再作为独立阶段。

### 总进度看板

| 阶段 | 状态 | 开始日期 | 完成日期 | 任务数 | 已完成 |
|------|------|---------|---------|--------|--------|
| Phase 0a: 安全止血 | ✅ 已完成 | 2026-06-03 | 2026-06-04 | 4 | 4 |
| Phase 0b: 工程化加固 | ✅ 已完成 | 2026-06-04 | 2026-06-05 | 3 | 3 |
| Phase 1: 架构解耦与核心重构 | ✅ 已完成 | 2026-06-05 | 2026-06-05 | 10 | 10 |
| Phase 2: 引擎服务化与持久化 | ✅ 已完成 | 2026-06-05 | 2026-06-07 | 10 | 10 |
| Phase 3: 平台化基础建设 | ✅ 大部分完成 | 2026-06-07 | 2026-06-08 | 6 | 5 |
| Phase 4: 完整测试平台 | ✅ 大部分完成 | 2026-06-08 | 2026-06-09 | 8 | 5 |
| Phase 5: 平台完善与生产化 | ⬜ 未开始 | — | — | 4 | 0 |
| **合计** | | | | **45** | **37** |

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

### Phase 2: 引擎服务化与持久化 ✅

**目标版本**: v2.0.0 | **状态**: 全部完成

| 任务 | 完成内容 | 关键产出 |
|------|---------|---------|
| T2-0: 用例超时管控 | ✅ | `asyncio.wait_for()` 用例级超时 + Worker `time-limit=1800s` 兜底 |
| T2-1: FastAPI REST 服务层 | ✅ | `api/` 目录（main.py + dependencies.py + routers/ + schemas/） |
| T2-2: 数据持久化 | ✅ | `framework/persistence/`（models/ + repositories/ + database.py）+ Alembic 迁移 |
| T2-3: 用例 YAML ↔ DB 双向同步 | ✅ | `framework/sync.py`（28.32 KB）+ `autotest sync` CLI 命令 |
| T2-4: 报告数据持久化 | ✅ | `ExecutionRepository` + `ReportRepository` + `report_service.py` |
| T2-5: OpenAPI 导入解析器 | ✅ | `framework/importers/openapi_parser.py`（26.84 KB）+ 前端 CaseImportPage |
| T2-6: CLI 工具 | ✅ | `framework/cli.py`（25.63 KB）：run/sync/import/serve/report 命令 |
| T2-7: 异步执行支持 | ✅ | `AsyncHttpClient` + `TestRunner.arun_case()` |
| T2-8: 引擎层能力补齐 | ✅ | 断言引擎重构为子包 `framework/assertion/` |
| T2-9: WebSocket asyncio 原生迁移 | ✅ | `framework/executors/ws_async_executor.py`（7.81 KB），消除 nest_asyncio |

### Phase 3: 平台化基础建设（大部分完成）✅

**目标版本**: v2.1.0 | **状态**: 5/6 完成（T3-5 延期）

| 任务 | 完成内容 | 关键产出 |
|------|---------|---------|
| T3-1: 分布式执行 (Master-Worker) | ✅ | `worker/`（celery_app.py + tasks.py）+ Celery + Redis + 自动降级本地模式 |
| T3-2: 执行调度引擎 | ✅ | `framework/scheduler.py` + `api/routers/schedules.py` + APScheduler + DB 持久化 |
| T3-3: 环境管理服务 | ✅ | `api/routers/environments.py` + `EnvironmentModel` + 三级加载策略 + Runner 缓存 |
| T3-4: 告警通知服务 | ✅ | `framework/notifications/`（企微/钉钉/Webhook/邮件骨架）+ 规则评估 + 并行分发 |
| T3-5: gRPC 协议支持 | ❌ 延期 | 留待 Phase 5 |
| T3-6: Docker Compose 全栈部署 | ✅ | 5 服务编排 + entrypoint.sh + 三套 compose + Nginx 反向代理 |

### Phase 4: 完整测试平台（大部分完成）✅

**目标版本**: v2.1.0 | **状态**: 5/8 完成

| 任务 | 完成内容 | 关键产出 |
|------|---------|---------|
| T4-1: 基础 Web 前端 | ✅ | `frontend/`（114 文件）：React 18 + Vite + shadcn/ui + 16 页面 + 20 路由 |
| T4-2: Mock 服务引擎 | ✅ | `framework/mock/`（5 文件）：MockRuleStore + FastAPI 子应用 + MockPlugin + REST API + 前端 MockRulesPage |
| T4-3: 流量录制与回放 | ✅ | `framework/recorder/`（7 文件）：HAR 录制→回放→差异→用例生成 + 前端 RecorderPage |
| T4-4: 智能断言与 Schema 推断 | ✅ | `framework/assertion/smart.py`（27.54 KB）+ REST API + 前端 SmartAssertionPage |
| T4-5: 多租户与 RBAC | ✅ | JWT + bcrypt + admin/editor/viewer + RoleGuard + 用户管理 API + 前端 UsersPage |
| T4-6: 报告聚合与高级分析 | ❌ 延期 | 留待 Phase 5 |
| T4-7: 用例推荐与智能生成 | ❌ 延期 | 留待 Phase 5 |
| T4-8: K8s 部署支持 | ❌ 延期 | 留待 Phase 5 |

---

## Phase 5: 平台完善与生产化

**优先级**: 🟢 P2 - 中  
**预计工期**: 4 周  
**目标版本**: v3.0.0  
**评审依据**: [架构评审 v4 §10 遗留问题与改进建议]  
**前置条件**: Phase 4 大部分完成（✅ 已满足）

> Phase 5 聚焦四个延期任务，以及架构评审 v4 中 P0/P1/P2 级遗留问题的批量修复（共 24 项）。目标是将平台从"功能完整"提升至"生产就绪"。

### 任务清单

#### T3-5（补）: gRPC 协议支持（可选插件）

- **新增文件**: `framework/executors/grpc_executor.py`, `framework/models/grpc.py`
- **优先级**: P2
- **方案**:
  1. 基于 `grpcio` + `grpcio-reflection` 构建 GrpcStepExecutor
  2. 支持 proto 文件解析或服务反射
  3. YAML 用例格式扩展 `grpc:` 字段
  4. 设计为可选 extra 依赖 `pip install autotest[grpc]`
- **依赖**: `grpcio>=1.68.0`, `grpcio-reflection>=1.68.0`, `protobuf>=5.29.0`
- **验收**: 可执行 gRPC 接口测试；不安装 `[grpc]` extra 时不影响其他功能

#### T4-6（补）: 报告聚合与高级分析

- **新增文件**: `api/routers/analytics.py`, 前端 Dashboard 数据接入
- **优先级**: P1
- **方案**:
  1. 接口稳定性排行（Top N 不稳定接口）
  2. 响应时间分位数（P50/P95/P99）
  3. 失败原因分类统计
  4. 通过率趋势图（日/周/月）
  5. 前端 Dashboard 替换静态 Mock 数据为真实 API
- **验收**: Dashboard 页面展示真实分析数据；可通过 API 查询趋势

#### T4-7（补）: 用例推荐与智能生成

- **新增文件**: `framework/generator.py`
- **优先级**: P2
- **方案**:
  1. 基于 OpenAPI spec 自动生成覆盖率报告
  2. 识别未覆盖的 API 端点
  3. 推荐补全用例
  4. 基于流量日志自动生成用例
- **验收**: 输入 spec 文件，输出覆盖率报告和推荐用例列表

#### T4-8（补）: K8s 部署支持

- **新增目录**: `deploy/k8s/`
- **优先级**: P2
- **内容**:
  1. Deployment + Service + ConfigMap YAML
  2. HPA 自动扩缩容配置
  3. Ingress 配置
  4. Helm Chart
- **验收**: `kubectl apply -f deploy/k8s/` 部署成功

#### Phase 5 批量修复（P0/P1/P2 遗留问题）

| 优先级 | 问题 | 建议 |
|--------|------|------|
| P0 | 执行失败无上下文快照 | 失败时自动调用 context.snapshot() 持久化，便于复现 |
| P0 | Worker 与本地模式执行逻辑重复 | 提取 `framework/execution_orchestrator.py` 统一编排 |
| P1 | 不支持组合断言（AND/OR） | AssertItem 增加 logic 字段 |
| P1 | 提取器不支持管道链式处理 | ExtractPipeline + Transformer 链 |
| P1 | 插件无配置化启用/禁用 | config.yaml → plugins.enabled 列表 |
| P1 | 数据库不支持多数据源 | DataSourceRegistry 注册表 |
| P1 | Email 通知仅骨架 | SMTP 实际发送实现 |
| P1 | 环境变量不支持加密存储 | 敏感字段 AES 加密 + 脱敏展示 |
| P1 | 调度器无失败告警 | 调度触发失败 → 通知渠道 |
| P2 | 配置热加载未实现 | watchdog 文件监听 + 重载 |
| P2 | 超时不支持单接口覆盖 | HttpRequest.timeout 字段 |
| P2 | 缺少签名计算函数 | HMAC-SHA256 / RSA 内置到模板 |
| P2 | `next_run_at` 未填充 | APScheduler 同步 next_run_time 到 ORM |
| P2 | 通知渠道无配置化开关 | YAML 配置段 channels.enabled 列表 |
| P2 | 前端 Dashboard 数据为静态 Mock | 接入后端报告聚合 API（依赖 T4-6） |
| P2 | 前端缺少 E2E 测试 | Playwright/Cypress 自动化测试 |
| P2 | 未实现国际化（i18n） | react-i18next 多语言支持 |
| P2 | 项目级隔离仅模型层，API 未强制过滤 | API 层按 project_id 过滤数据 |
| P2 | 缺少 Token 刷新机制 | refresh_token + 自动续期 |
| P2 | Mock 规则不支持持久化 | DB 持久化 Mock 规则，服务重启不丢失 |
| P2 | 回放引擎不支持变量替换 | HAR 回放时自动识别动态 token/timestamp 并替换 |
| P2 | 缺少密码强度策略和登录失败锁定 | 密码复杂度校验 + 失败次数限制 + 临时锁定 |
| P2 | 上下文快照无持久化（进程中断无法恢复） | 失败/异常时自动持久化 context snapshot 到 DB |
| P2 | Worker 健康监控不足 | Worker 心跳监控 + 执行超时告警 + 任务堆积阈值 |

---

## 附录: 文件结构变更总览

### 当前结构（v2.1.0 — Phase 4 大部分完成后）

```
api-test-framework/
├── alembic/                       # 🆕 Phase 2 — 数据库迁移
│   ├── env.py
│   └── versions/                  # 3 个迁移版本
├── api/                           # 🆕 Phase 2 — FastAPI REST 服务层
│   ├── main.py                    # FastAPI app 入口
│   ├── auth.py                    # JWT 认证 + bcrypt
│   ├── dependencies.py            # 依赖注入（Runner + DB session + 环境加载）
│   ├── routers/                   # 12 个路由模块
│   │   ├── assertions.py          # 🆕 Phase 4 — 智能断言 API
│   │   ├── auth.py                # 🆕 Phase 4 — 认证 API
│   │   ├── cases.py
│   │   ├── environments.py
│   │   ├── executions.py
│   │   ├── mocks.py               # 🆕 Phase 4 — Mock 规则 API
│   │   ├── recorder.py            # 🆕 Phase 4 — 录制回放 API
│   │   ├── reports.py
│   │   ├── schedules.py
│   │   ├── suites.py
│   │   └── users.py               # 🆕 Phase 4 — 用户管理 API
│   ├── schemas/                   # 9 个 Pydantic Schema 模块
│   └── static/                    # Vite 前端构建产物
├── assertions/
├── config/
├── conftest.py
├── docker/
│   └── entrypoint.sh
├── docs/
├── framework/
│   ├── assertion/                 # ♻️ Phase 4 — 断言引擎重构为子包
│   │   ├── engine.py              # 16 种操作符 + AssertionEngine
│   │   └── smart.py               # 🆕 Phase 4 — 智能断言（Schema 推断 + 变更检测）
│   ├── executors/
│   │   ├── base.py
│   │   ├── http_executor.py
│   │   ├── ws_executor.py         # @deprecated
│   │   └── ws_async_executor.py   # 🆕 Phase 4 — 纯异步 WS 执行器
│   ├── importers/                 # 🆕 Phase 2
│   │   └── openapi_parser.py      # OpenAPI 3.x Spec 解析 + 用例生成
│   ├── interceptors/
│   ├── mock/                      # 🆕 Phase 4 — Mock 服务
│   │   ├── models.py
│   │   ├── rule_store.py
│   │   ├── server.py
│   │   └── plugin.py
│   ├── notifications/             # 🆕 Phase 3 — 告警通知
│   │   ├── base.py
│   │   ├── service.py
│   │   ├── dingtalk_channel.py
│   │   ├── email_channel.py
│   │   ├── webhook_channel.py
│   │   └── wecom_channel.py
│   ├── persistence/               # 🆕 Phase 2 — 持久化层
│   │   ├── database.py
│   │   ├── bridge.py
│   │   ├── models/                # 8 个 ORM 模型
│   │   ├── repositories/          # 8 个 Repository
│   │   └── services/
│   ├── plugins/
│   ├── recorder/                  # 🆕 Phase 4 — 流量录制与回放
│   │   ├── har_models.py
│   │   ├── har_recorder.py
│   │   ├── recorder_manager.py
│   │   ├── player.py
│   │   ├── differ.py
│   │   └── case_generator.py
│   ├── report/
│   ├── utils/
│   ├── cli.py                     # 🆕 Phase 2 — CLI 工具
│   ├── client.py
│   ├── collector.py
│   ├── config.py
│   ├── config_schema.py
│   ├── context.py
│   ├── db.py
│   ├── exceptions.py
│   ├── extractor.py
│   ├── fixtures_loader.py
│   ├── models.py
│   ├── parser.py
│   ├── runner.py
│   ├── scheduler.py               # 🆕 Phase 3 — 调度引擎
│   └── sync.py                    # 🆕 Phase 2 — YAML ↔ DB 同步
├── frontend/                      # 🆕 Phase 4 — Web 管理前端（114 文件）
│   └── src/
│       ├── api/                   # 12 个 API 封装模块
│       ├── components/            # UI 组件 + shadcn/ui + auth 守卫
│       ├── hooks/                 # TanStack Query Hooks
│       ├── pages/                 # 16 个业务页面
│       ├── router/                # 20 条路由 + AuthGuard + RoleGuard
│       ├── store/                 # Zustand 状态管理
│       └── types/                 # TypeScript 类型
├── testcases/
├── tests/
├── worker/                        # 🆕 Phase 3 — Celery Worker
│   ├── celery_app.py
│   └── tasks.py
├── docker-compose.yml             # ♻️ 5 服务全栈编排
├── docker-compose.dev.yml         # 🆕 开发环境
├── docker-compose.test.yml        # 测试环境
├── Dockerfile
├── Dockerfile.api                 # 🆕 API 服务独立镜像
├── nginx.conf                     # 🆕 Nginx 反向代理配置
├── Makefile
├── pyproject.toml
├── requirements.txt
└── README.md
```

图例: ♻️ 重构 | 🆕 新增 | 标注了引入的阶段

---

## 修订记录

| 版本 | 日期 | 修订内容 |
|------|------|---------|
| 1.0 | 2026-06-03 | 初始版本，基于架构评审报告制定 |
| 1.1 | 2026-06-03 | Phase 0 拆分、T1-10 补充、前端推迟、gRPC 降级 |
| 2.0 | 2026-06-05 | Phase 0a/0b/1 全部完成后的第二版：已完成阶段回顾（17/39 任务完成）；Phase 2 增加 T2-8 引擎层能力补齐；架构评分 8.22 |
| 2.1 | 2026-06-05 | 结构性隐患专项处理：新增 T2-0 用例超时管控 + T2-9 WebSocket asyncio 原生迁移 |
| 3.0 | 2026-06-09 | Phase 2/3/4 完成后第三版：<br>① Phase 2 全部 10 任务完成（含 T2-0/T2-9 结构性隐患修复）<br>② Phase 3 5/6 任务完成（T3-5 gRPC 延期）<br>③ Phase 4 5/8 任务完成（T4-6/T4-7/T4-8 延期）<br>④ 新增 Phase 5 规划（4 个延期任务 + 24 项 P0/P1/P2 批量修复，对照架构评审 v4 §10 全覆盖）<br>⑤ 总进度：37/45 任务完成，架构评分 9.05/10<br>⑥ 更新文件结构总览反映 v2.1.0 实际目录 |
