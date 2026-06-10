# AutoTest Framework 开发计划（第五版）

> **计划版本**: 5.0  
> **制定日期**: 2026-06-11  
> **关联文档**: [架构评审报告 v5](./architecture-review.md)（评分 9.20/10）  
> **当前版本**: v2.3.0（Phase 0a/0b/1/2/3/4 全部完成）  
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
v1.0.0 ──→ v1.0.1 ──→ v1.1.0 ──→ v1.2.0 ──→ v2.0.0 ──→ v2.1.0 ──→ v2.2.0 ──→ v2.3.0 ──→ v3.0.0
 (起点)  Phase 0a   Phase 0b   Phase 1    Phase 2    Phase 3    Phase 4    Phase 4+   Phase 5
 6.93分  安全止血   工程化加固  架构解耦    引擎服务化  平台基础    完整平台    报告+K8s   平台完善
 ✅✅✅   ✅         ✅          ✅          +持久化     分布式+调度  前端+Mock   +推荐      生产化
                                                                  +录制+RBAC  9.20分
                                            ✅          ✅          ✅          ✅          ⬜
```

> **注**: Phase 4（完整测试平台）的任务已随 Phase 2-3 并行推进完成，不再作为独立阶段。

### 总进度看板

| 阶段 | 状态 | 开始日期 | 完成日期 | 任务数 | 已完成 |
|------|------|---------|---------|--------|--------|
| Phase 0a: 安全止血 | ✅ 已完成 | 2026-06-03 | 2026-06-04 | 4 | 4 |
| Phase 0b: 工程化加固 | ✅ 已完成 | 2026-06-04 | 2026-06-05 | 3 | 3 |
| Phase 1: 架构解耦与核心重构 | ✅ 已完成 | 2026-06-05 | 2026-06-05 | 10 | 10 |
| Phase 2: 引擎服务化与持久化 | ✅ 已完成 | 2026-06-05 | 2026-06-07 | 10 | 10 |
| Phase 3: 平台化基础建设 | ✅ 已完成 | 2026-06-07 | 2026-06-10 | 6 | 6 |
| Phase 4: 完整测试平台 | ✅ 已完成 | 2026-06-08 | 2026-06-10 | 11 | 11 |
| Phase 5: 平台完善与生产化 | ⬜ 未开始 | — | — | 3 | 0 |
| **合计** | | | | **47** | **47** |

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

### Phase 3: 平台化基础建设 ✅

**目标版本**: v2.1.0 | **状态**: 6/6 全部完成

| 任务 | 完成内容 | 关键产出 |
|------|---------|---------|
| T3-1: 分布式执行 (Master-Worker) | ✅ | `worker/`（celery_app.py + tasks.py）+ Celery + Redis + 自动降级本地模式 |
| T3-2: 执行调度引擎 | ✅ | `framework/scheduler.py` + `api/routers/schedules.py` + APScheduler + DB 持久化 |
| T3-3: 环境管理服务 | ✅ | `api/routers/environments.py` + `EnvironmentModel` + 三级加载策略 + Runner 缓存 |
| T3-4: 告警通知服务 | ✅ | `framework/notifications/`（企微/钉钉/Webhook/邮件骨架）+ 规则评估 + 并行分发 |
| T3-5: gRPC 协议支持 | ✅ | `framework/executors/grpc_executor.py`：GrpcStepExecutor 策略模式 + proto 编译/反射双模式 + YAML `grpc:` 字段 + `[grpc]` optional extra + 示例 gRPC 服务 + 单元测试 |
| T3-6: Docker Compose 全栈部署 | ✅ | 5 服务编排 + entrypoint.sh + 三套 compose + Nginx 反向代理 |

### Phase 4: 完整测试平台 ✅

**目标版本**: v2.2.0 | **状态**: 8/8 全部完成

| 任务 | 完成内容 | 关键产出 |
|------|---------|---------|
| T4-1: 基础 Web 前端 | ✅ | `frontend/`（114 文件）：React 18 + Vite + shadcn/ui + 16 页面 + 20 路由 |
| T4-2: Mock 服务引擎 | ✅ | `framework/mock/`（5 文件）：MockRuleStore + FastAPI 子应用 + MockPlugin + REST API + 前端 MockRulesPage |
| T4-3: 流量录制与回放 | ✅ | `framework/recorder/`（7 文件）：HAR 录制→回放→差异→用例生成 + 前端 RecorderPage |
| T4-4: 智能断言与 Schema 推断 | ✅ | `framework/assertion/smart.py`（27.54 KB）+ REST API + 前端 SmartAssertionPage |
| T4-5: 多租户与 RBAC | ✅ | JWT + bcrypt + admin/editor/viewer + RoleGuard + 用户管理 API + 前端 UsersPage |
| T4-6: 报告聚合与高级分析 | ✅ | 通过率趋势/响应时间分位数/失败分类统计 API + 前端 Dashboard 真实数据接入 |
| T4-7: 用例推荐与智能生成 | ✅ | 基于 OpenAPI 覆盖率报告 + 流量日志自动生成用例推荐 |
| T4-8: K8s 部署支持 | ✅ | `deploy/k8s/`：Deployment + Service + ConfigMap + HPA + Ingress + Helm Chart |

---

## Phase 5: 平台完善与生产化

**优先级**: 🔴🟡🟢 P0→P1→P2 分批推进  
**预计工期**: 8 周（分 3 个子阶段）  
**目标版本**: v3.0.0  
**评审依据**: [架构评审 v5 §10 遗留问题与改进建议]  
**前置条件**: Phase 4 全部完成 + T4-6/T4-7/T4-8 已交付（✅ 已满足）  
**架构评分目标**: 9.20 → **9.60+**  
**详细设计**: 参见 [`phase5-design.md`](./phase5-design.md)

> **Phase 5 定位**：项目已完成全部功能矩阵建设（47/47 任务），架构评分 9.20/10。Phase 5 不再新增功能模块，而是对现有 27 项遗留问题进行系统性修复和品质打磨。目标是让平台从"功能完整"进化到"生产就绪、长期可维护"。
>
> **核心原则**：
> 1. **不引入新概念** — 所有改动基于现有架构模式，不新增抽象层次
> 2. **不破坏兼容性** — YAML 格式、API 接口、DB Schema 变更必须向后兼容
> 3. **代码质量优先** — 每项改动必须有单元测试覆盖，完整类型注解和 docstring
> 4. **渐进式交付** — P0 → P1 → P2 分批推进，每批独立可验证、可发布

### 子阶段规划

```
Phase 5a (P0, 2周)          Phase 5b (P1, 3周)          Phase 5c (P2, 3周)
├── 执行编排统一             ├── 组合断言                  ├── 配置热加载
├── 上下文快照持久化         ├── 提取器管道                ├── 单接口超时覆盖
├── Worker 健康监控          ├── 插件配置化                ├── 签名计算函数
└── 调度失败告警             ├── 多数据源注册              ├── next_run_at 同步
                            ├── Email 通知完善            ├── 通知渠道配置化
                            ├── 环境变量加密存储           ├── 项目级 API 过滤
                            └── 报告聚合 API              ├── Token 刷新机制
                                                         ├── Mock 规则持久化
                                                         ├── 回放变量替换
                                                         ├── 密码强度策略
                                                         ├── 前端 E2E 测试
                                                         └── 国际化 (i18n)
```

### 任务清单

#### P0 级：生产稳定性（第 1-2 周）

| 编号 | 任务 | 工时 | 说明 |
|------|------|------|------|
| T5-01 | 执行编排统一 | 3d | 提取 `execution_orchestrator.py`，消除 Worker 与本地模式 80% 重复代码 |
| T5-02 | 上下文快照持久化 | 2d | 失败时自动快照三层变量状态到 DB，支持复现 |
| T5-03 | Worker 健康监控 | 2d | Redis 心跳 + 失联告警 + 健康检查 API |
| T5-04 | 调度失败告警 | 1d | 调度触发失败时通过通知渠道发送告警 |

#### P1 级：功能增强（第 3-5 周）

| 编号 | 任务 | 工时 | 说明 |
|------|------|------|------|
| T5-05 | 组合断言 (AND/OR) | 3d | AssertItem 新增 logic/children 字段，支持嵌套组合 |
| T5-06 | 提取器管道 | 2d | 新增 ExtractPipeline，支持 jsonpath→regex→base64_decode 链式处理 |
| T5-07 | 插件配置化 | 1d | config.yaml plugins.enabled/disabled 白名单/黑名单 |
| T5-08 | 多数据源注册 | 2d | DataSourceRegistry + 配置文件多数据源声明 |
| T5-09 | Email 通知完善 | 2d | aiosmtplib 异步 SMTP，支持 TLS/STARTTLS |
| T5-10 | 环境变量加密 | 2d | AES-256-GCM 加密敏感字段，API 查询脱敏返回 |
| T5-11 | 报告聚合 API | 3d | 通过率趋势/响应时间分位数/失败分类/不稳定接口排行 |
| T5-12 | 快照 Redis 缓存 | 1d | 每个 step 结束自动保存快照到 Redis（1h TTL） |

#### P2 级：工程化提升（第 6-8 周）

| 编号 | 任务 | 工时 | 说明 |
|------|------|------|------|
| T5-13 | 配置热加载 | 1d | watchdog 监听 config/ 目录，开发模式启用 |
| T5-14 | 单接口超时覆盖 | 0.5d | HttpRequest.timeout 字段，优先于全局配置 |
| T5-15 | 签名计算函数 | 1d | 模板引擎新增 hmac_sha256 / md5_sign 内置函数 |
| T5-16 | next_run_at 同步 | 0.5d | APScheduler 同步下次运行时间到 ScheduleModel |
| T5-17 | 通知渠道配置化 | 0.5d | channels.<name>.enabled 控制各渠道启停 |
| T5-18 | 项目级 API 隔离 | 2d | API 层按 project_id 过滤数据 |
| T5-19 | Token 刷新机制 | 2d | refresh_token + Axios 401 自动续期 |
| T5-20 | Mock 规则持久化 | 2d | MockRuleModel ORM + MockRuleStoreDB + Alembic 迁移 |
| T5-21 | 回放变量替换 | 1.5d | HAR 回放前自动识别动态字段并替换为模板变量 |
| T5-22 | 密码强度策略 | 1d | 密码复杂度校验 + 登录失败锁定 |
| T5-23 | 前端 E2E 测试 | 3d | Playwright 自动化测试（login/cases/execution/dashboard） |
| T5-24 | 国际化 i18n | 2d | react-i18next 中英文切换 |
| **合计** | **24 项** | **38d** | **12 新文件 + 25 文件改动** |

> **详细设计（接口签名、验收标准、代码约束）见 [`docs/phase5-design.md`](./phase5-design.md)**



---

## 附录: 文件结构变更总览

### 当前结构（v2.2.0 — Phase 4 全部完成后）

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
│   │   ├── ws_async_executor.py   # 🆕 Phase 4 — 纯异步 WS 执行器
│   │   └── grpc_executor.py       # 🆕 Phase 4 — gRPC 执行器（proto/反射）
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
│   └── grpc/                      # 🆕 Phase 4 — gRPC 示例（proto + server + 用例）
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
| 4.0 | 2026-06-10 | Phase 4 全部完成第四版：<br>① T3-5 gRPC 协议支持交付（GrpcStepExecutor + proto/反射双模式 + `[grpc]` extra）<br>② Phase 3 6/6 全部完成，Phase 4 8/8 全部完成<br>③ 总进度：44/44 任务完成（四个阶段全部完工）<br>④ Phase 5 任务从 4 个缩减为 3 个（移除 gRPC），遗留问题从 24 项缩减为 23 项<br>⑤ 架构评分升至 9.20/10<br>⑥ 版本号升至 v2.2.0<br>⑦ 更新文件结构总览反映 v2.2.0 实际目录 |
| 5.0 | 2026-06-11 | Phase 5 详设第五版：<br>① T4-6/T4-7/T4-8 标记已完成，Phase 4 完成数 8→11，总进度 47/47<br>② Phase 5 拆分为 3 个子阶段（5a/5b/5c），24 项任务，8 周工期<br>③ 详设内容独立为 `docs/phase5-design.md`，本文件保留追踪概览<br>④ 版本号升至 v2.3.0 |
