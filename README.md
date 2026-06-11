# AutoTest Framework — 企业级 API 自动化测试框架

> **v2.4.0** | Python 3.12+ | pytest 8.x | httpx 0.28.x | YAML 驱动 | 结构化日志 | 策略模式引擎

## 目录

- [特性总览](#特性总览)
- [快速开始](#快速开始)
- [API 服务](#api-服务)
- [CLI 工具](#cli-工具)
- [项目结构](#项目结构)
- [用例编写指南](#用例编写指南)
- [执行与运行](#执行与运行)
- [变量系统](#变量系统)
- [断言引擎](#断言引擎)
- [变量提取](#变量提取)
- [Fixture 与 Setup/Teardown](#fixture-与-setupteardown)
- [数据库集成](#数据库集成)
- [WebSocket 测试](#websocket-测试)
- [gRPC 测试](#grpc-测试)
- [Mock 服务](#mock-服务)
- [流量录制与回放](#流量录制与回放)
- [智能断言与 Schema 推断](#智能断言与-schema-推断)
- [调度引擎](#调度引擎)
- [告警通知](#告警通知)
- [分布式执行](#分布式执行)
- [插件系统与钩子](#插件系统与钩子)
- [自定义插件开发](#自定义插件开发)
- [拦截器链](#拦截器链)
- [报告系统](#报告系统)
- [日志系统](#日志系统)
- [配置管理](#配置管理)
- [多租户与 RBAC](#多租户与-rbac)
- [前端管理界面](#前端管理界面)
- [CI/CD 集成](#cicd-集成)
- [命令速查](#命令速查)
- [架构设计](#架构设计)
- [开发计划](#开发计划)
- [License](#license)

---

## 特性总览

| 特性 | 说明 |
|------|------|
| **YAML 驱动** | 测试人员写 YAML，零代码完成用例编写 |
| **变量系统** | 三层作用域（suite → case → step），11 个内置函数，模板渲染 |
| **断言引擎** | 16 种操作符，支持 JSONPath、正则、嵌套校验，可扩展自定义操作符 |
| **变量提取** | 6 种提取类型（jsonpath/header/body_regex/status_code/elapsed/sql_column） |
| **Fixture 系统** | setup/teardown 支持 api_call / db_execute / wait / shell 四种动作 |
| **数据库集成** | setup/teardown 中执行 SQL，从查询结果提取变量，支持 MySQL/PostgreSQL/SQLite |
| **WebSocket 支持** | 纯异步 WS 执行器，收发消息、断言验证 |
| **gRPC 支持** | proto 编译 + 反射双模式服务发现，可选 `[grpc]` extra 依赖，零侵入集成 |
| **多环境切换** | `--env=staging` 一行命令切换环境 |
| **插件系统** | 13 个生命周期钩子，优先级排序，自动发现，插件间通信 |
| **拦截器链** | 洋葱模型请求/响应拦截，内置认证与日志拦截器 |
| **报告多引擎** | Allure / HTML / 自定义，通过 ReportAdapter 接口解耦 |
| **结构化日志** | structlog + JSON + trace_id + 敏感数据脱敏 |
| **安全加固** | Shell 白名单、日志脱敏、线程安全操作符、配置 Schema 校验 |
| **并行执行** | pytest-xdist 多进程并发 |
| **数据持久化** | SQLAlchemy 2.0 异步 ORM + Alembic 迁移 + Repository 模式 |
| **REST API 服务** | FastAPI 全功能 API 层（12 个路由模块 + JWT 认证 + RBAC） |
| **CLI 工具** | `autotest run/sync/import/serve/report` 命令行工具 |
| **OpenAPI 导入** | 解析 OpenAPI 3.x Spec 自动生成测试用例 |
| **YAML ↔ DB 同步** | 用例在 YAML 文件与数据库之间双向同步 |
| **分布式执行** | Celery + Redis Master-Worker 架构，自动降级本地模式 |
| **调度引擎** | APScheduler 定时/周期执行，DB 持久化调度配置 |
| **告警通知** | 企微/钉钉/Webhook/邮件多渠道通知，规则评估 + 并行分发 |
| **Mock 服务** | 内置 Mock 引擎，规则匹配 + 动态响应，支持前端管理 |
| **流量录制与回放** | HAR 格式录制→回放→差异对比→自动生成用例 |
| **智能断言** | Schema 推断 + 变更检测 + 自动生成断言规则 |
| **多租户与 RBAC** | JWT + bcrypt + admin/editor/viewer 三级角色 |
| **Web 管理前端** | React 18 + Vite + shadcn/ui，16 页面 + 20 路由 + TanStack Query |
| **CI/CD 就绪** | GitHub Actions / Jenkins / GitLab CI / Docker Compose 全栈部署 |
| **执行编排统一** | ExecutionOrchestrator 统一 Worker/本地执行逻辑，消除 80% 重复代码 |
| **上下文快照** | 失败时自动持久化三层变量状态，敏感字段脱敏，支持失败现场复现 |
| **调度失败告警** | 4 类失败场景自动告警，通过通知渠道实时推送 |
| **K8s 部署支持** | Helm Chart + Deployment/Service/ConfigMap/HPA/Ingress 生产级编排 |

---

## 快速开始

### 前置条件

| 工具 | 最低版本 | 说明 |
|------|----------|------|
| **Python** | **>= 3.12** | 框架使用 PEP 695 `type` 语句等 3.12+ 特性 |
| **pip** | >= 23.0 | 随 Python 3.12 自带 |
| **Node.js** | >= 18 | 前端开发（可选，仅需管理前端时安装） |

> **换电脑/CI 环境首次克隆后**：虚拟环境和依赖不会随仓库分发（已通过 `.gitignore` 排除），需要重新创建环境并安装依赖。

### 1. 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 2. 安装依赖

```bash
# 一键安装全部依赖（含 API 服务、数据库、WebSocket、分布式执行、调度器、JWT 认证等）
pip install -r requirements.txt

# 开发工具链（可选）
pip install black isort ruff mypy pre-commit pytest-cov
pre-commit install
```

> **注意**：`requirements.txt` 已包含 `fastapi`、`uvicorn`、`structlog`、`SQLAlchemy`、`apscheduler`、`PyJWT`、`bcrypt` 等全部运行时依赖，**不需要**再单独安装。README 旧版拆分安装的命令已废弃。

### 2. 编写第一个用例

创建 `testcases/smoke/test_api.yaml`：

```yaml
name: 用户接口冒烟测试
base_url: "{{env.base_url}}"
tags: [smoke]

variables:
  default_page: 1

cases:
  - name: 获取用户列表
    request:
      method: GET
      path: /api/users
      params:
        page: "{{default_page}}"
    expect:
      status_code: 200
      jsonpath:
        $.data.list: "not_null"
        $.data.total: ">0"
    extract:
      first_user_id: $.data.list[0].id

  - name: 获取单个用户
    request:
      method: GET
      path: /api/users/{{first_user_id}}
    expect:
      status_code: 200
```

### 3. 运行测试

```bash
# 冒烟测试
pytest testcases/smoke/ --env=dev -v

# 使用 Makefile
make smoke

# 并行执行
pytest -n 4 testcases/

# 生成 Allure 报告
make report
```

### 5. 启动 API 服务

```bash
# 确保在项目根目录执行（数据库文件、配置文件路径依赖工作目录）
cd /path/to/apitestframework

# 开发模式（热重载，代码变更自动重启）
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式（多 worker，不支持 --reload）
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4

# 验证
curl http://localhost:8000/health
# 访问 Swagger UI: http://localhost:8000/docs
```

### 后端启动常见问题

| 现象 | 原因 | 解决 |
|------|------|------|
| `ModuleNotFoundError: No module named 'structlog'` | 依赖未完整安装 | 执行 `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'apscheduler'` | 同上 | 同上 |
| `unable to open database file` | 未从项目根目录启动，SQLite 路径解析失败 | `cd` 到项目根目录再启动 |
| `SchedulerNotRunningError` | SQLite DB 初始化失败导致调度器未启动（不影响 API 核心功能） | 检查工作目录是否正确，确保 `data/` 目录存在 |
| `Python 3.11` 语法报错 | 框架要求 Python >= 3.12（使用了 PEP 695 等新语法） | 升级到 Python 3.12+ |
| 全局 pip 环境依赖冲突 | 多个项目共享同一 Python 环境 | **强烈建议用虚拟环境**（见步骤 1） |

---

## API 服务

框架提供基于 FastAPI 的全功能 REST API 服务层，涵盖用例管理、执行调度、报告查询、Mock 规则、流量录制、智能断言、用户管理等。

### API 接口总览

| 资源 | 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|------|
| 健康检查 | `GET` | `/health` | 服务健康检查 | ✅ |
| 认证 | `POST` | `/api/v1/auth/login` | 用户登录获取 JWT | ✅ |
| 认证 | `POST` | `/api/v1/auth/register` | 用户注册 | ✅ |
| 用例 | `POST` `GET` `PUT` `DELETE` | `/api/v1/cases` | 用例 CRUD + 版本历史 | ✅ |
| 套件 | `POST` `GET` `PUT` `DELETE` | `/api/v1/suites` | 套件 CRUD | ✅ |
| 执行 | `POST` `GET` | `/api/v1/executions` | 触发执行 + 历史查询 + 快照查询 | ✅ |
| 报告 | `GET` | `/api/v1/reports` | 报告查询 + 趋势分析 | ✅ |
| 环境 | `POST` `GET` `PUT` `DELETE` | `/api/v1/environments` | 环境配置管理 | ✅ |
| 调度 | `POST` `GET` `PUT` `DELETE` | `/api/v1/schedules` | 定时任务管理 | ✅ |
| Mock 规则 | `POST` `GET` `PUT` `DELETE` | `/api/v1/mocks` | Mock 规则 CRUD | ✅ |
| 录制回放 | `POST` `GET` | `/api/v1/recorder` | 流量录制/回放/差异对比 | ✅ |
| 智能断言 | `POST` | `/api/v1/assertions` | Schema 推断 + 变更检测 | ✅ |
| 用户管理 | `POST` `GET` `PUT` `DELETE` | `/api/v1/users` | 用户 CRUD（admin 专属） | ✅ |

### 服务目录结构

```
api/
├── main.py               # FastAPI app 入口（CORS、路由、异常处理）
├── auth.py                # JWT 认证 + bcrypt 密码哈希
├── dependencies.py        # 依赖注入（Runner + DB session + 环境加载）
├── routers/
│   ├── assertions.py      # 智能断言 API
│   ├── auth.py            # 认证 API（login/register）
│   ├── cases.py           # 用例 CRUD（完整实现 + 版本管理）
│   ├── environments.py    # 环境配置管理
│   ├── executions.py      # 执行触发/结果查询
│   ├── mocks.py           # Mock 规则管理
│   ├── recorder.py        # 流量录制与回放
│   ├── reports.py         # 报告查询/趋势分析
│   ├── schedules.py       # 定时调度管理
│   ├── suites.py          # 套件 CRUD
│   └── users.py           # 用户管理（admin）
└── schemas/               # 9 个 Pydantic Schema 模块
```

### 手工测试 API（curl）

```bash
# 用户登录获取 Token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 创建用例（需 Bearer Token）
curl -X POST http://localhost:8000/api/v1/cases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"name":"登录测试","tags":["smoke"],"priority":"P0","yaml_content":"name: test"}'

# 查看列表
curl http://localhost:8000/api/v1/cases \
  -H "Authorization: Bearer <token>"

# 按标签过滤
curl "http://localhost:8000/api/v1/cases?tags=smoke&priority=P0" \
  -H "Authorization: Bearer <token>"

# 触发执行
curl -X POST http://localhost:8000/api/v1/executions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"case_ids": ["<id1>", "<id2>"], "env_name": "dev"}'

# Swagger UI
# http://localhost:8000/docs
```

---

## CLI 工具

框架提供 `autotest` 命令行工具，支持以下子命令：

```bash
# 运行测试
autotest run --env dev --tags smoke testcases/

# YAML ↔ DB 双向同步
autotest sync --direction yaml-to-db
autotest sync --direction db-to-yaml

# 导入 OpenAPI Spec 生成用例
autotest import --file openapi.yaml --output testcases/generated/

# 启动 API 服务
autotest serve --host 0.0.0.0 --port 8000

# 查看执行报告
autotest report --execution-id <id>
```

---

## 项目结构

```
api-test-framework/
├── config/                       # 配置目录
│   ├── config.yaml               # 全局配置（HTTP/日志/报告/数据库等）
│   └── env.yaml                  # 多环境配置（dev/staging/production/local）
├── api/                          # FastAPI REST 服务层
│   ├── main.py                   #   FastAPI app 入口（CORS、路由、异常处理）
│   ├── auth.py                   #   JWT 认证 + bcrypt 密码哈希
│   ├── dependencies.py           #   依赖注入（Runner + DB session + 环境加载）
│   ├── routers/                  #   12 个路由模块
│   │   ├── assertions.py         #     智能断言 API
│   │   ├── auth.py               #     认证 API
│   │   ├── cases.py              #     用例 CRUD + 版本管理
│   │   ├── environments.py       #     环境配置管理
│   │   ├── executions.py         #     执行触发/结果查询
│   │   ├── mocks.py              #     Mock 规则管理
│   │   ├── recorder.py           #     流量录制与回放
│   │   ├── reports.py            #     报告查询/趋势分析
│   │   ├── schedules.py          #     定时调度管理
│   │   ├── suites.py             #     套件 CRUD
│   │   └── users.py              #     用户管理（admin）
│   ├── schemas/                  #   9 个 Pydantic Schema 模块
│   └── static/                   #   Vite 前端构建产物
├── framework/                    # 框架核心代码
│   ├── runner.py                 # 测试执行引擎（策略路由 + 插件调度）
│   ├── execution_orchestrator.py # 统一执行编排器（Worker/本地共用）
│   ├── context_snapshot.py       # 上下文快照管理器（失败现场复现）
│   ├── client.py                 # HTTP 客户端（httpx + 拦截器链）
│   ├── collector.py              # pytest 用例收集器（YamlCollector）
│   ├── context.py                # 协程安全上下文（contextvars 三层作用域）
│   ├── config.py                 # 配置加载器（多源合并）
│   ├── config_schema.py          # 配置 Schema 校验（Pydantic v2）
│   ├── models.py                 # 数据模型（Pydantic v2）
│   ├── parser.py                 # YAML 解析器
│   ├── extractor.py              # 变量提取器（6 种提取类型）
│   ├── fixtures_loader.py        # Fixture 加载器（安全加固版）
│   ├── exceptions.py             # 自定义异常体系
│   ├── db.py                     # 数据库模块（SQLAlchemy 2.0）
│   ├── cli.py                    # CLI 工具（run/sync/import/serve/report）
│   ├── sync.py                   # YAML ↔ DB 双向同步
│   ├── scheduler.py              # 调度引擎（APScheduler + 失败告警）
│   ├── assertion/                # 断言引擎子包
│   │   ├── engine.py             #   16 种操作符 + AssertionEngine
│   │   └── smart.py              #   智能断言（Schema 推断 + 变更检测）
│   ├── executors/                # 协议执行器（策略模式，3 个实现）
│   │   ├── base.py               #   StepExecutor 抽象基类
│   │   ├── http_executor.py      #   HTTP 步骤执行器
│   │   ├── ws_async_executor.py  #   纯异步 WebSocket 执行器
│   │   └── grpc_executor.py      #   gRPC 步骤执行器（proto/反射）
│   ├── importers/                # 外部格式导入
│   │   └── openapi_parser.py     #   OpenAPI 3.x Spec 解析 + 用例生成
│   ├── interceptors/             # 请求拦截器链
│   │   ├── base.py               #   RequestInterceptor 抽象基类
│   │   ├── auth.py               #   AuthInterceptor 认证拦截器
│   │   └── logging.py            #   LoggingInterceptor 日志拦截器
│   ├── mock/                     # Mock 服务引擎
│   │   ├── models.py             #   Mock 数据模型
│   │   ├── rule_store.py         #   规则存储与匹配
│   │   ├── server.py             #   FastAPI 子应用
│   │   └── plugin.py             #   Mock 插件
│   ├── notifications/            # 告警通知服务
│   │   ├── base.py               #   通知渠道抽象基类
│   │   ├── service.py            #   通知服务（规则评估 + 并行分发）
│   │   ├── dingtalk_channel.py   #   钉钉通知
│   │   ├── email_channel.py      #   邮件通知
│   │   ├── webhook_channel.py    #   Webhook 通知
│   │   └── wecom_channel.py      #   企业微信通知
│   ├── persistence/              # 数据持久化层
│   │   ├── database.py           #   数据库连接管理
│   │   ├── bridge.py             #   ORM ↔ Pydantic 桥接
│   │   ├── models/               #   9 个 SQLAlchemy ORM 模型
│   │   ├── repositories/         #   9 个 Repository 实现
│   │   └── services/             #   业务服务层
│   ├── plugins/                  # 插件系统
│   │   ├── base.py               #   PluginBase（13 个生命周期钩子）
│   │   ├── manager.py            #   PluginManager（自动发现/排序/分发）
│   │   └── auth_manager.py       #   AuthManager 认证管理插件
│   ├── recorder/                 # 流量录制与回放
│   │   ├── har_models.py         #   HAR 数据模型
│   │   ├── har_recorder.py       #   HAR 录制器
│   │   ├── recorder_manager.py   #   录制管理器
│   │   ├── player.py             #   回放引擎
│   │   ├── differ.py             #   差异对比器
│   │   └── case_generator.py     #   用例生成器
│   ├── report/                   # 报告模块（多引擎适配）
│   │   ├── base.py               #   ReportAdapter 抽象基类
│   │   ├── allure.py             #   Allure 适配器
│   │   ├── html_adapter.py       #   HTML 适配器
│   │   └── models.py             #   报告数据模型
│   └── utils/                    # 工具模块
│       ├── logger.py             #   structlog 结构化日志 + trace_id
│       ├── masker.py             #   SensitiveDataMasker 敏感数据脱敏
│       └── template.py           #   Jinja2 模板引擎
├── frontend/                     # Web 管理前端（React 18 + Vite + shadcn/ui）
│   └── src/
│       ├── api/                  #   12 个 API 封装模块（Axios + TanStack Query）
│       ├── components/           #   UI 组件 + shadcn/ui + AuthGuard + RoleGuard
│       ├── hooks/                #   TanStack Query Hooks
│       ├── pages/                #   16 个业务页面
│       ├── router/               #   20 条路由
│       ├── store/                #   Zustand 状态管理
│       └── types/                #   TypeScript 类型定义
├── worker/                       # Celery 分布式 Worker
│   ├── celery_app.py             #   Celery 应用配置
│   └── tasks.py                  #   异步任务定义
├── testcases/                    # YAML 测试用例
│   ├── local/                    #   本地环境用例
│   ├── smoke/                    #   冒烟测试
│   ├── regression/               #   回归测试
│   └── grpc/                     #   gRPC 示例（proto + server + 用例）
├── assertions/                   # 自定义断言函数
│   └── custom_checks.py
├── tests/                        # 框架单元测试
│   ├── framework/                #   核心模块测试
│   └── smoke/                    #   冒烟测试
├── alembic/                      # 数据库迁移
│   ├── env.py
│   └── versions/                 # 迁移版本文件
├── docker/                       # Docker 辅助脚本
│   └── entrypoint.sh
├── conftest.py                   # pytest 全局配置
├── Makefile                      # 常用命令
├── Dockerfile                    # 三层构建优化
├── Dockerfile.api                # API 服务独立镜像
├── docker-compose.yml            # 5 服务全栈编排
├── docker-compose.dev.yml        # 开发环境编排
├── docker-compose.test.yml       # 测试环境编排
├── nginx.conf                    # Nginx 反向代理配置
├── pyproject.toml                # 项目配置 + 工具链
├── requirements.txt              # 依赖
├── requirements.lock             # 锁定依赖版本
├── .pre-commit-config.yaml       # Git 提交前检查
├── .dockerignore                 # Docker 构建排除
└── docs/                         # 文档
    ├── architecture-review.md    #   架构评审报告
    ├── development-plan.md       #   开发计划
    └── coding-standards.md       #   编码规范
```

---

## 用例编写指南

### 用例文件结构

一个 YAML 用例文件代表一个 **TestSuite**，包含多个 **TestCase**：

```yaml
name: 套件名称                    # 必填：套件名称
description: 套件描述             # 可选：描述信息
base_url: "{{env.base_url}}"     # 必填：基础 URL（支持模板变量）
tags: [smoke, crud]              # 可选：套件级标签

variables:                        # 可选：套件级变量
  key1: value1
  key2: value2

setup:                            # 可选：套件级前置动作
  - action_type: api_call
    config:
      method: POST
      path: /api/setup
      extract:
        setup_token: $.token

teardown:                         # 可选：套件级后置动作
  - action_type: api_call
    config:
      method: DELETE
      path: /api/cleanup

cases:                            # 必填：用例列表
  - name: 用例名称
    # ... 详见下方
```

### 单个用例完整示例

```yaml
- name: 登录获取 JWT Token
  description: 调用 /api/login 获取 access_token   # 可选
  tags: [auth, login, P0]                           # 可选：用例级标签
  priority: P0                                      # 可选：优先级

  # ── 变量 ──
  variables:                                        # 可选：用例级变量
    username: "admin"

  # ── 前置/后置 ──
  setup:                                            # 可选：用例级前置
    - action_type: wait
      config:
        seconds: 1
  teardown:                                         # 可选：用例级后置
    - action_type: api_call
      config:
        method: DELETE
        path: /api/session

  # ── 请求 ──
  request:
    method: POST                                    # GET/POST/PUT/DELETE/PATCH
    path: /api/login                                # 接口路径
    headers:                                        # 可选：请求头
      Content-Type: application/json
    params:                                         # 可选：URL 查询参数
      redirect: "true"
    body:                                           # 可选：请求体
      username: "{{username}}"
      password: "{{env.admin_pass}}"
    auth:                                           # 可选：认证信息
      type: bearer
      token: "{{access_token}}"
    timeout: 10                                     # 可选：单请求超时（秒）

  # ── 断言 ──
  expect:
    status_code: 200                                # 状态码断言
    jsonpath:                                       # JSONPath 断言
      $.code:
        operator: eq
        value: 200
      $.msg: "登录成功"                              # 简写：默认 eq 操作符
      $.data.access_token:
        operator: matches
        value: ".+"
      $.data.token_type: "Bearer"
    headers:                                        # 可选：响应头断言
      Content-Type:
        operator: contains
        value: "application/json"

  # ── 提取 ──
  extract:                                          # 可选：变量提取
    access_token: $.data.access_token               # JSONPath 提取
    token_type: $.data.token_type

  # ── 数据库断言 ──
  db_assert:                                        # 可选：数据库断言
    - connection: main_db
      sql: "SELECT count(*) as cnt FROM users WHERE username='{{username}}'"
      assertions:
        - column: cnt
          operator: gt
          value: 0

  # ── 跳过条件 ──
  skip:                                             # 可选：跳过条件
    if: "{{env_name}} == 'production'"              # 条件表达式
    reason: "生产环境跳过此用例"
```

### 数据驱动

通过 `data_driven` 字段实现参数化：

```yaml
name: 用户查询参数化测试
base_url: "{{env.base_url}}"

data_driven:
  parameters:
    - user_id: 1
      expected_name: "张三"
    - user_id: 2
      expected_name: "李四"
    - user_id: 3
      expected_name: "王五"

cases:
  - name: "查询用户 ID={{user_id}}"
    request:
      method: GET
      path: /api/users/{{user_id}}
    expect:
      status_code: 200
      jsonpath:
        $.data.name: "{{expected_name}}"
```

每个 `parameters` 中的字典会与套件变量合并，用例名称中的 `{{变量}}` 会被渲染。

---

## 执行与运行

### 基本执行

```bash
# 执行指定目录/文件
pytest testcases/smoke/ -v
pytest testcases/local/test_user_api.yaml -v

# 指定环境
pytest testcases/ --env=staging -v
pytest testcases/ --env=local -v

# 指定标签过滤
pytest testcases/ --tags=smoke -v
pytest testcases/ --tags=auth,login -v

# 同时指定环境和标签
pytest testcases/ --env=staging --tags=P0 -v

# 跳过持久化（不写数据库）
pytest testcases/ --no-persist -v
```

### 并行执行

```bash
# 4 进程并行
pytest -n 4 testcases/

# 8 进程并行 + 失败重试
pytest -n 8 --reruns 2 testcases/
```

### 调试模式

```bash
# 详细日志（DEBUG 级别）
pytest testcases/ -v --log-cli-level=DEBUG

# 仅收集不执行
pytest testcases/ --collect-only

# 执行失败时进入 pdb
pytest testcases/ --pdb -v

# 使用 Makefile
make debug
```

### 使用 Makefile

```bash
make install      # 安装依赖
make smoke        # 冒烟测试（--env=dev --tags=smoke）
make regression   # 回归测试
make parallel     # 并行执行（4 workers）
make report       # 生成 Allure 报告
make report-html  # 生成 HTML 报告
make collect      # 只列出用例不执行
make debug        # 调试模式（DEBUG 日志）
make clean        # 清理报告和日志
```

### Docker 执行

```bash
# 构建镜像
docker build -t autotest .

# 运行测试
docker run --rm \
  -v $(pwd)/reports:/app/reports \
  -e ENV=staging \
  autotest

# Docker Compose 全栈部署（API + Worker + DB + Redis + Nginx）
docker compose up -d

# 开发环境（热重载）
docker compose -f docker-compose.dev.yml up

# 测试环境（含数据库服务）
docker compose -f docker-compose.test.yml up
```

---

## 变量系统

### 变量作用域（优先级从低到高）

```
内置函数 → 全局配置变量 → 环境变量(env.yaml) → 套件变量 → 用例变量 → extract 提取变量
```

解析时 step_vars > case_vars > suite_vars，后者覆盖前者。

### 变量引用语法

使用 Jinja2 `{{ }}` 语法在 YAML 中引用变量：

```yaml
# 引用环境变量
base_url: "{{env.base_url}}"

# 引用套件/用例变量
path: /api/users/{{user_id}}

# 引用 extract 提取的变量
headers:
  Authorization: "Bearer {{access_token}}"

# 使用内置函数
body:
  request_id: "{{uuid4()}}"
  timestamp: "{{timestamp()}}"
```

### 内置函数

| 函数 | 用法 | 说明 |
|------|------|------|
| `timestamp()` | `{{timestamp()}}` | Unix 时间戳（秒） |
| `timestamp_ms()` | `{{timestamp_ms()}}` | Unix 时间戳（毫秒） |
| `uuid4()` | `{{uuid4()}}` | 随机 UUID |
| `random_int(min, max)` | `{{random_int(1, 100)}}` | 随机整数 |
| `random_string(length)` | `{{random_string(10)}}` | 随机字符串 |
| `now(format)` | `{{now('%Y-%m-%d')}}` | 当前时间 |
| `base64_encode(str)` | `{{base64_encode('hello')}}` | Base64 编码 |
| `base64_decode(str)` | `{{base64_decode('aGVsbG8=')}}` | Base64 解码 |
| `md5(str)` | `{{md5('test')}}` | MD5 哈希 |
| `sha256(str)` | `{{sha256('test')}}` | SHA256 哈希 |
| `env_var(key)` | `{{env_var('API_KEY')}}` | 读取环境变量 |

### 环境变量覆盖

支持 `AUTOTEST_` 前缀的操作系统环境变量自动覆盖配置：

```bash
# AUTOTEST_HTTP__TIMEOUT=60 等价于 config.yaml 中 http.timeout: 60
export AUTOTEST_HTTP__TIMEOUT=60
pytest testcases/ --env=dev
```

---

## 断言引擎

### 简写语法

最常用的 `eq` 操作符可省略：

```yaml
expect:
  status_code: 200                    # 等价于 status_code: {operator: eq, value: 200}
  jsonpath:
    $.data.name: "张三"               # 等价于 {operator: eq, value: "张三"}
    $.data.total: ">0"               # 等价于 {operator: gt, value: 0}
    $.data.id: "not_null"            # 等价于 {operator: not_null}
```

### 完整语法

```yaml
expect:
  jsonpath:
    $.data.price:
      operator: between
      value: [1, 100]
```

### 全部操作符

| 操作符 | 说明 | 示例 |
|--------|------|------|
| `eq` | 等于 | `value: 200` |
| `ne` | 不等于 | `operator: ne, value: 0` |
| `gt` / `gte` | 大于 / 大于等于 | `operator: gt, value: 0` |
| `lt` / `lte` | 小于 / 小于等于 | `operator: lt, value: 100` |
| `contains` | 包含 | `operator: contains, value: "success"` |
| `not_contains` | 不包含 | `operator: not_contains, value: "error"` |
| `matches` | 正则匹配 | `operator: matches, value: "^[a-z]+$"` |
| `in` | 在列表中 | `operator: in, value: [1, 2, 3]` |
| `not_in` | 不在列表中 | `operator: not_in, value: [0, -1]` |
| `not_null` | 非空 | `operator: not_null` |
| `is_null` | 为空 | `operator: is_null` |
| `type` | 类型检查 | `operator: type, value: "list"` |
| `length` | 长度检查 | `operator: length, value: ">0"` |
| `between` | 范围检查 | `operator: between, value: [1, 100]` |

### 数值比较简写

在简写语法中，以 `>`、`<`、`>=`、`<=`、`!=` 开头的值会自动识别为数值比较：

```yaml
$.data.total: ">0"         # operator: gt, value: 0
$.data.price: "<100"       # operator: lt, value: 100
$.data.count: ">=1"        # operator: gte, value: 1
```

### 自定义断言操作符

```python
# assertions/custom_checks.py
from framework.assertion import AssertionEngine

engine = AssertionEngine()

@engine.register_operator("is_even")
def op_is_even(actual, expected):
    """检查数值是否为偶数"""
    if not isinstance(actual, (int, float)) or actual % 2 != 0:
        raise AssertionError(f"Expected even number, got {actual}")

@engine.register_operator("starts_with")
def op_starts_with(actual, expected):
    """检查字符串是否以指定前缀开头"""
    if not str(actual).startswith(str(expected)):
        raise AssertionError(f"Expected '{actual}' to start with '{expected}'")
```

在 YAML 中使用：

```yaml
expect:
  jsonpath:
    $.data.count:
      operator: is_even
    $.data.name:
      operator: starts_with
      value: "user_"
```

### 断言路径类型

| 路径前缀 | 说明 | 示例 |
|----------|------|------|
| `$.` | JSONPath 表达式 | `$.data.list[0].id` |
| `status_code` | HTTP 状态码 | `status_code: 200` |
| `response_time` | 响应时间（ms） | `response_time: {operator: lt, value: 5000}` |
| `body_size` | 响应体大小（bytes） | `body_size: {operator: lt, value: 1024}` |
| `headers.` | 响应头 | `headers.Content-Type: {operator: contains, value: "json"}` |
| `body.` | 响应体字段（点号路径） | `body.data.name: "test"` |

---

## 变量提取

### 提取类型

| 类型 | 语法 | 说明 |
|------|------|------|
| JSONPath | `var_name: $.data.id` | 从 JSON 响应中提取（默认） |
| Header | `var_name: header:X-Request-Id` | 从响应头提取 |
| 正则 | `var_name: regex:<pattern>` | 从响应体正则提取 |
| 状态码 | `var_name: status_code` | 提取 HTTP 状态码 |
| 耗时 | `var_name: elapsed` | 提取响应耗时（ms） |
| SQL 列 | 在 db_assert 中使用 | 从数据库查询结果提取 |

### 提取示例

```yaml
cases:
  - name: 登录
    request:
      method: POST
      path: /api/login
      body: { username: "admin", password: "123456" }
    extract:
      # JSONPath 提取（最常用）
      access_token: $.data.access_token
      user_id: $.data.user.id
      # 响应头提取
      request_id: header:X-Request-Id
      # 状态码提取
      login_status: status_code
      # 耗时提取
      response_time: elapsed
    # 提取的变量可在后续用例中使用
  - name: 查询用户
    request:
      method: GET
      path: /api/users/{{user_id}}
      headers:
        Authorization: "Bearer {{access_token}}"
```

### 数据库提取

在 `db_assert` 中结合 `extract` 使用：

```yaml
db_assert:
  - connection: main_db
    sql: "SELECT username, email FROM users WHERE id={{user_id}}"
    assertions:
      - column: username
        operator: eq
        value: "admin"
    extract:
      user_email: email      # 提取 email 列的值
```

---

## Fixture 与 Setup/Teardown

### 支持的动作类型

| 动作类型 | 说明 | 配置字段 |
|----------|------|---------|
| `api_call` | 发送 HTTP 请求 | method, path, headers, body, extract |
| `db_execute` | 执行 SQL | connection, sql, params, extract |
| `wait` | 等待指定秒数 | seconds |
| `shell` | 执行 Shell 命令（安全加固） | command, timeout |

### 套件级 Setup/Teardown

```yaml
name: 订单流程测试
base_url: "{{env.base_url}}"

setup:
  - action_type: api_call
    config:
      method: POST
      path: /api/test-data/init
      extract:
        test_order_id: $.data.order_id
  - action_type: db_execute
    config:
      connection: main_db
      sql: "INSERT INTO test_flags (key, value) VALUES ('test_run', '1')"
  - action_type: wait
    config:
      seconds: 2

teardown:
  - action_type: api_call
    config:
      method: DELETE
      path: /api/test-data/cleanup
  - action_type: db_execute
    config:
      connection: main_db
      sql: "DELETE FROM test_flags WHERE key='test_run'"
```

### 用例级 Setup/Teardown

每个用例也可以独立配置 setup/teardown：

```yaml
cases:
  - name: 创建用户
    setup:
      - action_type: wait
        config:
          seconds: 1
    request:
      method: POST
      path: /api/users
      body: { name: "test" }
    expect:
      status_code: 200
    teardown:
      - action_type: db_execute
        config:
          connection: main_db
          sql: "DELETE FROM users WHERE name='test'"
```

### Shell 动作安全策略

Shell 动作经过安全加固，必须在 `config.yaml` 中配置白名单：

```yaml
# config.yaml
fixtures:
  allowed_shell_commands:    # 命令白名单，空列表禁止所有 shell 命令
    - echo
    - curl
    - date
  shell_sandbox: true        # 启用沙箱模式（检查敏感路径引用）
```

```yaml
# 用例中使用
setup:
  - action_type: shell
    config:
      command: "echo hello"
      timeout: 10    # 可选，默认 30 秒
```

安全检查流程：
1. 从配置读取白名单（空列表 = 拒绝所有）
2. `shlex.split()` 安全解析命令参数
3. 检查命令名是否在白名单中（支持全路径和 basename 匹配）
4. 沙箱模式下检查参数是否引用敏感路径
5. `subprocess.run` 执行，默认超时 30 秒

---

## 数据库集成

### 配置数据库连接

在 `config/env.yaml` 中配置：

```yaml
environments:
  dev:
    db:
      driver: mysql
      dsn: "mysql://root@localhost:3306/test_db"
      main_db:
        type: mysql
        host: localhost
        port: 3306
        user: root
        password: "${DB_PASSWORD}"
        database: test_db
        pool_size: 5
```

### 数据库断言

```yaml
cases:
  - name: 创建用户后验证数据库
    request:
      method: POST
      path: /api/users
      body: { name: "test_user", age: 25 }
    expect:
      status_code: 200
    db_assert:
      - connection: main_db
        sql: "SELECT count(*) as cnt FROM users WHERE name='test_user'"
        assertions:
          - column: cnt
            operator: gt
            value: 0
      - connection: main_db
        sql: "SELECT age FROM users WHERE name='test_user'"
        assertions:
          - column: age
            operator: eq
            value: 25
        extract:
          user_age: age
```

### 数据库断言操作符

支持与 HTTP 断言相同的操作符：`eq`、`ne`、`gt`、`lt`、`gte`、`lte`、`contains`、`matches` 等。

简写语法：`">0"` 自动识别为 `operator: gt, value: 0`。

---

## WebSocket 测试

### WebSocket 用例示例

```yaml
name: WebSocket 聊天测试
base_url: "{{env.base_url}}"

cases:
  - name: 发送和接收消息
    ws_config:
      url: "{{env.ws_url}}/chat"
      headers:
        Authorization: "Bearer {{access_token}}"
      messages:
        - action: send
          data: '{"type": "hello", "content": "Hi"}'
        - action: receive
          timeout: 5
          expect:
            jsonpath:
              $.type: "hello_response"
        - action: send
          data: '{"type": "bye"}'
      close_timeout: 3
```

---

## gRPC 测试

框架通过 `GrpcStepExecutor` 支持 gRPC 接口测试，采用与 HTTP/WS 相同的策略模式实现。

### 安装 gRPC 依赖

gRPC 依赖设计为 optional extra，不影响框架核心功能：

```bash
# 安装 gRPC 支持
pip install -e ".[grpc]"

# 或安装全部 extras
pip install -e ".[all]"
```

### gRPC 服务发现方式

支持两种方式获取 gRPC 服务定义：

| 方式 | 说明 | 适用场景 |
|------|------|---------|
| **Proto 文件编译** | 通过 `proto_file` + `proto_dir` 指定 `.proto` 文件，执行时自动编译为 Python pb2 模块 | 有 proto 源码的开发/测试环境 |
| **服务反射** | 设置 `reflection: true`，运行时通过 gRPC Reflection API 自动查询服务描述符 | 无 proto 源码的生产环境 |

### gRPC 用例示例

```yaml
name: gRPC Greeter 服务测试
base_url: "http://localhost:50051"

cases:
  # ── Proto 文件模式 ──
  - name: SayHello - proto 模式
    grpc:
      service: Greeter
      method: SayHello
      proto_file: greet.proto
      proto_dir: testcases/grpc
      host: localhost:50051
      body:
        name: "World"
    expect:
      status_code: 0          # gRPC 状态码，0 表示 OK
      jsonpath:
        $.message: "not_null"

  # ── 服务反射模式 ──
  - name: HealthCheck - 反射模式
    grpc:
      service: Greeter
      method: HealthCheck
      host: localhost:50051
      reflection: true
      body:
        service_name: "greeter"
    expect:
      status_code: 0
      jsonpath:
        $.status: "SERVING"

  # ── 带模板变量 ──
  - name: GetUser
    grpc:
      service: Greeter
      method: GetUser
      proto_file: greet.proto
      proto_dir: testcases/grpc
      host: "{{grpc_host}}"
      body:
        user_id: "{{user_id}}"
    expect:
      status_code: 0
      jsonpath:
        $.name: "not_null"
    extract:
      user_email: $.email
```

### gRPC 配置字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `service` | string | ✅ | gRPC 服务名（proto 中定义的服务名） |
| `method` | string | ✅ | gRPC 方法名 |
| `host` | string | ✅ | gRPC 服务地址，格式 `host:port` |
| `proto_file` | string | 条件必填 | proto 文件名（非反射模式必填） |
| `proto_dir` | string | 条件必填 | proto 文件所在目录（非反射模式必填） |
| `reflection` | bool | 否 | 是否使用 gRPC 反射，默认 `false` |
| `body` | dict | 否 | 请求消息体（自动映射到 protobuf 字段） |
| `metadata` | dict | 否 | gRPC metadata（如认证 token） |
| `timeout` | int | 否 | 请求超时秒数，默认 30 |
| `tls` | bool | 否 | 是否启用 TLS，默认 `false` |
| `tls_ca_cert` | string | 否 | TLS CA 证书路径 |

### 断言说明

gRPC 执行器通过 `_to_assertable()` 适配器将 `GrpcResult` 转换为 HTTP-like 对象，复用现有断言引擎：

- **`status_code`**: gRPC 状态码（0=OK, 14=UNAVAILABLE, 等）
- **`jsonpath`**: 对响应消息体使用 JSONPath 断言（响应已序列化为 JSON）
- **`elapsed_ms`**: 请求耗时（毫秒）

### 启动示例 gRPC 服务

```bash
# 编译 proto 文件
python testcases/grpc/compile_proto.py

# 启动示例服务
python testcases/grpc/server.py

# 运行 gRPC 测试
pytest testcases/grpc/grpc_test.yaml -v
```

### 策略模式集成

gRPC 执行器自动注册到 `TestRunner` 的 executor 链中（在 WS 和 HTTP 之前），通过 `supports()` 方法识别 `grpc_config is not None` 的用例：

```
StepExecutor 路由链:
  GrpcStepExecutor  → WS 用例
  WsStepExecutor     → HTTP 用例
  HttpStepExecutor   → 默认兜底
```

未安装 `[grpc]` 依赖时，`GrpcStepExecutor` 自动返回 `None`，不影响其他协议的执行。

---

## Mock 服务

框架内置 Mock 服务引擎，可在测试中模拟外部依赖。

### Mock 规则配置

```yaml
# 通过 API 或 YAML 定义 Mock 规则
rules:
  - name: "模拟用户服务"
    method: GET
    path_pattern: "/api/users/*"
    response:
      status_code: 200
      headers:
        Content-Type: "application/json"
      body:
        code: 200
        data:
          id: 1
          name: "mock_user"
    delay_ms: 100    # 模拟延迟
```

### 启动 Mock 服务

```bash
# Mock 服务随 API 服务自动启动
# 访问 http://localhost:8000/mock/

# 前端管理：Mock Rules 页面
# 路由：/mocks
```

---

## 流量录制与回放

录制真实 API 流量为 HAR 格式，支持回放、差异对比和自动生成测试用例。

### 录制模式

```bash
# 启动录制（通过 API）
curl -X POST http://localhost:8000/api/v1/recorder/start \
  -H "Authorization: Bearer <token>" \
  -d '{"name": "用户模块录制", "filter_path": "/api/users/*"}'

# 停止录制
curl -X POST http://localhost:8000/api/v1/recorder/stop

# 回放并对比差异
curl -X POST http://localhost:8000/api/v1/recorder/play \
  -H "Authorization: Bearer <token>" \
  -d '{"recording_id": "<id>"}'

# 生成测试用例
curl -X POST http://localhost:8000/api/v1/recorder/generate-cases \
  -H "Authorization: Bearer <token>" \
  -d '{"recording_id": "<id>"}'
```

### 差异对比

回放时自动对比：
- 状态码变化
- 响应头差异
- JSON Body 字段增删改

---

## 智能断言与 Schema 推断

基于历史响应数据自动推断 JSON Schema 并生成断言规则。

### Schema 推断

```bash
# 提交样本响应进行 Schema 推断
curl -X POST http://localhost:8000/api/v1/assertions/infer-schema \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"samples": [{"id": 1, "name": "test"}, {"id": 2, "name": "demo"}]}'
```

### 变更检测

对比新旧 Schema 检测字段变更：
- 新增字段
- 删除字段
- 类型变化
- 必填/可选变化

---

## 调度引擎

支持定时和周期执行测试用例，调度配置持久化到数据库。

```bash
# 创建每日定时执行
curl -X POST http://localhost:8000/api/v1/schedules \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "每日冒烟测试",
    "cron_expression": "0 8 * * *",
    "case_ids": ["<id1>", "<id2>"],
    "env_name": "dev",
    "enabled": true
  }'

# 查看调度列表
curl http://localhost:8000/api/v1/schedules \
  -H "Authorization: Bearer <token>"
```

---

## 告警通知

执行失败或异常时自动通过多渠道发送告警通知。

### 支持的通知渠道

| 渠道 | 说明 |
|------|------|
| 企业微信 | 机器人 Webhook 消息 |
| 钉钉 | 机器人 Webhook 消息 |
| Webhook | 自定义 HTTP 回调 |
| 邮件 | SMTP 邮件通知 |

### 告警规则

```yaml
notifications:
  channels:
    wecom:
      enabled: true
      webhook_url: "https://qyapi.weixin.qq.com/..."
  rules:
    - name: "P0 用例失败告警"
      condition: "priority == 'P0' and status == 'failed'"
      channels: ["wecom", "email"]
```

---

## 分布式执行

基于 Celery + Redis 的 Master-Worker 分布式架构，支持自动降级为本地模式。

```bash
# 启动 Worker
celery -A worker.celery_app worker --loglevel=info

# 启动 Beat（定时调度）
celery -A worker.celery_app beat --loglevel=info

# 触发分布式执行（通过 API）
curl -X POST http://localhost:8000/api/v1/executions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"case_ids": ["<id>"], "env_name": "dev", "mode": "distributed"}'
```

> Redis 不可用时自动降级为本地同步执行模式，无需人工干预。

---

## 插件系统与钩子

### 生命周期钩子一览

框架提供 13 个生命周期钩子，覆盖测试执行全流程：

| 钩子方法 | 触发时机 | 参数 |
|----------|---------|------|
| `on_suite_start` | 套件开始前 | `suite` |
| `on_suite_end` | 套件结束后 | `suite`, `result` |
| `on_case_start` | 用例开始前 | `case` |
| `on_case_end` | 用例结束后 | `case`, `result` |
| `on_setup` | setup 执行前后 | `phase`("before"/"after"), `case`, `variables` |
| `on_teardown` | teardown 执行前后 | `phase`("before"/"after"), `case`, `variables` |
| `on_request` | 请求发送前（可修改请求） | `request` → 返回修改后的 request |
| `on_response` | 响应接收后（可修改响应） | `response` → 返回修改后的 response |
| `on_assertion` | 断言执行后 | `case`, `report` |
| `on_extract` | 变量提取后 | `case`, `extracted` |
| `on_error` | 发生错误时 | `error`, `case` |
| `on_retry` | 重试发生时 | `case`, `attempt`, `max_retries`, `reason` |
| `on_db_query` | 数据库查询前后 | `phase`("before"/"after"), `case`, `sql`, `result` |

### 钩子执行顺序

```
on_suite_start
  ├── on_case_start
  │     ├── on_setup(phase="before")
  │     ├── [setup 执行]
  │     ├── on_setup(phase="after")
  │     ├── on_request → [HTTP请求] → on_response
  │     ├── on_assertion
  │     ├── on_extract
  │     ├── on_teardown(phase="before")
  │     ├── [teardown 执行]
  │     └── on_teardown(phase="after")
  ├── on_case_end
  └── on_suite_end
```

### 内置插件

#### AuthManager（认证管理）

自动管理 Bearer Token 的注入与刷新：

```python
from framework.plugins.auth_manager import AuthManager

auth = AuthManager()
auth.set_token("your-jwt-token", expires_in=3600)
auth.set_refresh_callback(lambda: fetch_new_token())  # 可选：Token 过期自动刷新

# 注册到 PluginManager
plugin_manager.register(auth)
```

- `priority = 10`（确保最先执行，在请求发送前注入 `Authorization` 头）
- Token 过期自动调用刷新回调
- 刷新失败时通过 `on_error` 钩子记录日志

---

## 自定义插件开发

### 最简插件

```python
# framework/plugins/my_plugin.py
from framework.plugins.base import PluginBase

class MyPlugin(PluginBase):
    priority = 100  # 数值越小越先执行，默认 100

    def name(self) -> str:
        return "my_plugin"

    def on_case_start(self, case):
        print(f"用例开始: {case.name}")

    def on_case_end(self, case, result):
        print(f"用例结束: {case.name}, 结果: {'通过' if result.passed else '失败'}")
```

### 插件自动发现

放在 `framework/plugins/` 目录下的 `PluginBase` 子类会被 `PluginManager.discover()` 自动发现并注册。

命名规则：文件名不能以 `_` 开头，不能是 `base.py` 或 `__init__.py`。

### 请求修改插件

通过 `on_request` / `on_response` 钩子修改请求和响应（链式传递）：

```python
class SigningPlugin(PluginBase):
    """请求签名插件 — 为每个请求自动添加 HMAC 签名"""

    priority = 50  # 在 AuthManager 之后执行

    def name(self) -> str:
        return "signing"

    def on_request(self, request):
        import hashlib, hmac, time
        timestamp = str(int(time.time()))
        sign_str = f"{request.method.value}{request.path}{timestamp}"
        signature = hmac.new(b"secret_key", sign_str.encode(), hashlib.sha256).hexdigest()
        request.headers["X-Signature"] = signature
        request.headers["X-Timestamp"] = timestamp
        return request
```

### 插件间通信

通过 `PluginContext` 在插件间共享数据：

```python
class TokenCollectorPlugin(PluginBase):
    """收集 Token 供其他插件使用"""

    priority = 5  # 最先执行

    def name(self) -> str:
        return "token_collector"

    def on_response(self, response):
        # 将 token 存入共享上下文
        if hasattr(response, 'json_data') and 'token' in response.json_data:
            self.context.set("latest_token", response.json_data['token'])
        return response

class TokenValidatorPlugin(PluginBase):
    """从共享上下文读取 Token 进行验证"""

    priority = 50

    def name(self) -> str:
        return "token_validator"

    def on_case_end(self, case, result):
        token = self.context.get("latest_token")
        if token:
            # 验证 token 有效性
            pass
```

### 手动注册插件

```python
from framework.plugins.manager import PluginManager, PluginContext
from framework.plugins.base import PluginBase

# 创建 PluginManager
pm = PluginManager(context=PluginContext())

# 自动发现 framework/plugins/ 下的插件
pm.discover()

# 手动注册额外插件
pm.register(MyPlugin())

# 查看已注册插件
print(pm.plugin_names)

# 分发事件
pm.dispatch("case_start", case=test_case)

# 链式分发（on_request/on_response）
modified_request = pm.dispatch_chain("request", chain_value=http_request)
```

---

## 拦截器链

### 工作原理（洋葱模型）

```
请求流（外→内）：
  AuthInterceptor.on_request → LoggingInterceptor.on_request → 发送 HTTP 请求

响应流（内→外）：
  ← LoggingInterceptor.on_response ← AuthInterceptor.on_response
```

- `on_request`：按注册顺序执行
- `on_response`：按注册逆序执行
- 拦截器间通过 `context` 字典传递状态

### 内置拦截器

| 拦截器 | 职责 |
|--------|------|
| `AuthInterceptor` | 检查 `request.auth` 字段，自动注入 Bearer/Basic 认证 |
| `LoggingInterceptor` | 记录请求/响应结构化日志，自动脱敏敏感数据 |

### 自定义拦截器

```python
# framework/interceptors/my_interceptor.py
from framework.interceptors.base import RequestInterceptor
from framework.models import HttpRequest, HttpResponse

class CacheInterceptor(RequestInterceptor):
    """响应缓存拦截器"""

    def __init__(self):
        self._cache = {}

    def on_request(self, request: HttpRequest, context: dict) -> HttpRequest:
        cache_key = f"{request.method.value}:{request.path}"
        if cache_key in self._cache:
            context["cached_response"] = self._cache[cache_key]
        return request

    def on_response(self, response: HttpResponse, context: dict) -> HttpResponse:
        if "cached_response" not in context:
            cache_key = f"{response.status_code}"  # 简化示例
            self._cache[cache_key] = response
        return response

# 注册
client.add_interceptor(CacheInterceptor())
```

---

## 报告系统

### 支持的报告引擎

| 引擎 | 配置值 | 说明 |
|------|--------|------|
| Allure | `allure` | 默认，功能最完整 |
| HTML | `html` | pytest-html 轻量报告 |
| Noop | `noop` | 无报告输出（CI 内部使用） |

### 配置报告引擎

```yaml
# config.yaml
report:
  adapter: allure     # allure | html
  output_dir: reports
  allure:
    enabled: true
    results_dir: reports/allure-results
```

### 生成报告

```bash
# Allure 报告
pytest testcases/ --alluredir=reports/allure-results
allure serve reports/allure-results    # 在线查看
allure generate reports/allure-results -o reports/allure-report  # 静态生成

# 使用 Makefile
make report

# HTML 报告
pytest testcases/ --html=reports/report.html --self-contained-html
```

### 报告内容

Allure 报告自动附加以下信息：
- 请求详情（方法、URL、Headers、Body）
- 响应详情（状态码、耗时、Headers、Body）
- 断言结果（每个断言的 pass/fail、期望值、实际值）
- 数据库查询（SQL 语句、查询结果）
- 环境信息（环境名、base_url）

---

## 日志系统

### 结构化日志

框架使用 **structlog** 实现结构化日志，每条日志自动附加 `trace_id`：

```
2026-06-05T10:30:00.123456 [info     ] suite_started trace_id=login_test-a1b2c3d4 suite_name=用户接口测试 case_count=8
2026-06-05T10:30:00.234567 [info     ] request_started trace_id=login_test-a1b2c3d4 method=POST url=/api/login
2026-06-05T10:30:00.345678 [info     ] request_completed trace_id=login_test-a1b2c3d4 status_code=200 elapsed_ms=45
```

### 日志配置

```yaml
# config.yaml
logging:
  level: INFO                  # DEBUG|INFO|WARNING|ERROR
  format: console              # console(彩色)|json(JSON行)
                               # 注：文件日志始终为 JSON，不受此字段影响
  console:
    enabled: true
    colorize: true
  file:
    enabled: true
    path: logs/test.log
    max_bytes: 10485760        # 10MB
    backup_count: 5
  request_log:
    enabled: true
    path: logs/requests.log    # 独立的请求日志文件
    max_bytes: 10485760
    backup_count: 5
  sensitive_fields: []         # 用户自定义额外脱敏字段
  mask_enabled: true           # 是否启用脱敏
```

### trace_id

每个用例执行时自动生成 `trace_id`（格式: `{case_name}-{uuid8}`），串联该用例的所有日志：

```
trace_id=login_test-a1b2c3d4
  ├── suite_started
  ├── request_started
  ├── request_completed
  ├── assertion_completed
  └── case_ended
```

通过 trace_id 可以在日志文件中快速过滤单个用例的完整链路：

```bash
grep "login_test-a1b2c3d4" logs/test.log
```

### 敏感数据脱敏

日志输出自动脱敏以下字段：

- `Authorization` → `Bearer ****`
- `password` → `******`
- `token` → `******`
- `secret` → `******`
- `api_key` → `******`
- `Cookie` / `Set-Cookie` → `******`
- `access_token` / `refresh_token` → `******`

自定义脱敏字段：

```yaml
logging:
  sensitive_fields:
    - "x-api-key"
    - "private_token"
    - "credit_card"
```

### JSON 日志模式

设置 `format: json` 后，控制台也输出 JSON 格式，便于日志采集系统（ELK/Loki）解析：

```bash
# 启动时设置
pytest testcases/ --env=dev -v

# 或修改配置
# config.yaml → logging.format: json
```

---

## 配置管理

### 配置加载优先级（从低到高）

```
config.yaml → env.yaml → env.local.yaml → AUTOTEST_ 前缀环境变量
```

### 多环境配置

```yaml
# config/env.yaml
default: dev

environments:
  dev:
    base_url: https://httpbin.org
    variables:
      admin_user: dev_admin
      admin_pass: dev123
    http:
      timeout: 30
      verify_ssl: false

  staging:
    base_url: https://staging-api.example.com
    http:
      timeout: 15
      verify_ssl: true

  production:
    base_url: https://api.example.com
    http:
      timeout: 10
      verify_ssl: true

  local:
    base_url: http://127.0.0.1:8011
    http:
      timeout: 10
      verify_ssl: false
```

### 本地覆盖

创建 `config/env.local.yaml` 覆盖敏感配置（已 `.gitignore`）：

```yaml
environments:
  dev:
    db:
      main_db:
        password: "my_real_password"
```

### 配置 Schema 校验

框架使用 Pydantic v2 对配置进行校验，启动时即可发现配置错误：

| 配置项 | 类型 | 约束 |
|--------|------|------|
| `http.timeout` | int | 1~300 |
| `http.max_retries` | int | 0~10 |
| `logging.level` | enum | DEBUG/INFO/WARNING/ERROR |
| `logging.format` | enum | console/json |
| `report.adapter` | enum | allure/html |
| `execution.mode` | enum | local/distributed |
| `execution.parallel_workers` | int | 1~16 |
| `db.driver` | enum | sqlite/mysql/postgresql |

配置校验失败时，错误信息包含字段路径和期望类型：

```
配置校验失败:
  - http.timeout: Input should be greater than or equal to 1 (type=greater_than_equal)
```

---

## CI/CD 集成

### GitHub Actions

自动在 push/PR/定时 时运行测试，包含安全扫描步骤：

```yaml
# .github/workflows/test.yml 已配置
# - Python 3.11/3.12 矩阵测试
# - 单元测试 + Coverage
# - 集成测试 + Allure
# - Safety 依赖漏洞扫描
# - Bandit 代码安全扫描
# - Allure 报告部署到 GitHub Pages
```

### Jenkins

```groovy
// Jenkinsfile 已内置，直接在 Pipeline 中使用
// 支持参数化构建 + 邮件通知
```

### GitLab CI

```yaml
# .gitlab-ci.yml 已配置
# - unit-test 阶段
# - api-test 阶段
# - allure-report 阶段
```

### Docker

```bash
# 构建镜像（三层构建优化，依赖缓存）
docker build -t autotest .

# 运行测试
docker run --rm \
  -v $(pwd)/reports:/app/reports \
  -v $(pwd)/config:/app/config \
  -e ENV=staging \
  -e DB_PASSWORD=secret \
  autotest

# Docker Compose 全栈部署（API + Worker + DB + Redis + Nginx）
docker compose up -d

# 开发环境（热重载）
docker compose -f docker-compose.dev.yml up

# 测试环境（含数据库）
docker compose -f docker-compose.test.yml up
```

---

## 命令速查

| 命令 | 说明 |
|------|------|
| `make install` | 安装依赖 |
| `make smoke` | 运行冒烟测试（dev + smoke 标签） |
| `make regression` | 运行回归测试 |
| `make parallel` | 并行执行（4 workers） |
| `make report` | 生成 Allure 报告 |
| `make report-html` | 生成 HTML 报告 |
| `make collect` | 只列出用例不执行 |
| `make debug` | 调试模式（DEBUG 日志） |
| `make clean` | 清理报告和日志 |
| `make up` | 启动 Docker Compose 全栈服务 |
| `make down` | 停止 Docker Compose 服务 |
| `pytest --env=staging` | 指定环境运行 |
| `pytest --tags=smoke,P0` | 指定标签过滤 |
| `pytest --no-persist` | 跳过持久化，不写入数据库 |
| `pytest -n 4` | 4 进程并行 |
| `pytest --reruns 2` | 失败重试 2 次 |
| `pytest --collect-only` | 仅收集用例 |
| `pytest --pdb` | 失败进入调试器 |
| `autotest run --env dev --tags smoke testcases/` | CLI 运行测试 |
| `autotest sync --direction yaml-to-db` | YAML → DB 同步 |
| `autotest import --file openapi.yaml` | OpenAPI 导入 |
| `autotest serve --port 8000` | 启动 API 服务 |
| `pre-commit run --all-files` | 手动运行代码检查 |
| `uvicorn api.main:app --reload` | 启动 API 服务（开发模式） |
| `uvicorn api.main:app --workers 4` | 启动 API 服务（生产模式） |

---

## 架构设计

### 核心设计模式

| 模式 | 应用场景 | 说明 |
|------|---------|------|
| 策略模式 | `StepExecutor` | 协议执行器可插拔（HTTP/WS/gRPC），新增协议无需改 Runner |
| 工厂模式 | `create_report_adapter()` | 根据配置创建报告适配器 |
| 观察者模式 | `PluginBase` + `PluginManager` | 13 个生命周期钩子，按优先级分发 |
| 洋葱模型 | `RequestInterceptor` | 请求/响应拦截器链式处理 |
| 模板方法 | `StepExecutor.execute()` | 执行流程固定，通过插件/拦截器扩展 |

### 执行流程

```
YAML 文件 → YamlCollector 收集 → YamlFunction(pytest.Function) → runner fixture 注入
  → TestRunner.run_case()
    → 绑定 trace_id
    → 合并变量（suite + case + step）
    → PluginManager.dispatch("setup", phase="before")
    → FixtureLoader.run_setup()
    → PluginManager.dispatch("setup", phase="after")
    → StepExecutor 策略路由（GrpcStepExecutor / WsStepExecutor / HttpStepExecutor）
      → 模板渲染请求
      → PluginManager.dispatch_chain("request")  ← 拦截器链
      → 发送 HTTP 请求
      → PluginManager.dispatch_chain("response")  ← 拦截器链（逆序）
      → AssertionEngine.assert_response()
      → PluginManager.dispatch("assertion")
      → Extractor.extract()
      → PluginManager.dispatch("extract")
    → DBAsserter（可选）
    → PluginManager.dispatch("teardown", phase="before")
    → FixtureLoader.run_teardown()
    → PluginManager.dispatch("teardown", phase="after")
    → 变量提升（step → case）
```

## 多租户与 RBAC

框架内置基于 JWT 的用户认证与三级角色权限控制。

### 角色权限

| 角色 | 权限 |
|------|------|
| **admin** | 全部权限：用户管理、系统配置、所有 CRUD 操作 |
| **editor** | 用例/套件/环境/调度/Mock 的 CRUD，执行触发，报告查看 |
| **viewer** | 只读：查看用例、执行历史、报告 |

### 使用方式

```bash
# 注册用户
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"editor1","password":"pass123","role":"editor"}'

# 登录获取 Token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"editor1","password":"pass123"}'

# 后续请求携带 Token
# Authorization: Bearer <access_token>
```

> 前端内置 `AuthGuard` 和 `RoleGuard` 组件，自动拦截未授权访问。

---

## 前端管理界面

> 基于 React 18 + Vite + shadcn/ui + TanStack Query + Zustand 构建。

### 前置条件

- **Node.js >= 18**（推荐 20 LTS）
- **npm >= 9**（随 Node.js 自带）

> 换电脑/CI 环境首次克隆后，`node_modules/` 不在仓库中（已通过 `.gitignore` 排除），需重新安装依赖。

### 启动开发服务器

```bash
# 进入前端目录
cd frontend

# 安装依赖（首次/换环境后）
# 推荐 npm ci：按 lockfile 精确安装，确保多环境一致
npm ci

# 开发模式（默认 http://localhost:5173）
npm run dev

# 构建到 api/static/（供 Docker/生产环境使用）
npm run build
```

### 前端启动常见问题

| 现象 | 原因 | 解决 |
|------|------|------|
| `'vite' 不是内部或外部命令` | `node_modules` 未安装 | 执行 `npm ci` |
| `npm ci` 报错 | `package-lock.json` 与 `node_modules` 不一致 | 删掉 `node_modules` 后重试 |
| 端口 5173 被占用 | 已有 Vite 实例运行 | 关掉其他终端或修改 `vite.config.ts` 端口 |
| API 请求 404 | 后端未启动或端口不对 | 确保 `uvicorn api.main:app --port 8000` 已启动 |

### Docker 注意事项

- 前端**不参与 Docker 构建**（Dockerfile 仅处理 Python 后端）。
- 前端构建产物通过 `npm run build` 输出到 `api/static/`，由 FastAPI 托管静态文件。
- 如果前端代码更新了，需在构建 Docker 镜像**之前**先执行 `npm run build`。
- `docker-compose.yml` 中的 nginx 将 `/` 路由直接转发到 FastAPI（含静态文件），前端页面通过 `http://localhost/` 访问。

### 页面一览

| 页面 | 路由 | 功能 |
|------|------|------|
| 登录 | `/login` | 用户登录 |
| 注册 | `/register` | 用户注册 |
| 仪表盘 | `/dashboard` | 通过率趋势图、失败分类饼图、Top5 不稳定接口 |
| 用例列表 | `/cases` | 分页表格、搜索/筛选、编辑/删除操作 |
| 用例编辑 | `/cases/new`, `/cases/:id/edit` | 创建/编辑表单、YAML 编辑、标签/优先级 |
| 用例导入 | `/cases/import` | OpenAPI Spec 导入 |
| 套件管理 | `/suites` | 套件 CRUD |
| 执行历史 | `/executions` | 时间线列表、状态筛选 |
| 执行详情 | `/executions/:id` | 通过率、耗时、用例结果明细 |
| 报告中心 | `/reports` | 报告列表、趋势分析 |
| 环境管理 | `/environments` | 环境 CRUD、变量管理 |
| 调度管理 | `/schedules` | 定时任务 CRUD |
| Mock 规则 | `/mocks` | Mock 规则管理 |
| 录制回放 | `/recorder` | 流量录制/回放/差异对比 |
| 智能断言 | `/assertions` | Schema 推断 + 变更检测 |
| 用户管理 | `/users` | 用户 CRUD（admin 专属） |

---

## 开发计划

当前版本 **v2.4.0**，架构评分 **9.33/10**，50/71 任务已完成（Phase 0a-5a）。

| 阶段 | 状态 | 目标版本 |
|------|------|---------|
| Phase 0a: 安全止血 | ✅ 已完成 | v1.0.1 |
| Phase 0b: 工程化加固 | ✅ 已完成 | v1.1.0 |
| Phase 1: 架构解耦与核心重构 | ✅ 已完成 | v1.2.0 |
| Phase 2: 引擎服务化与持久化 | ✅ 已完成 | v2.0.0 |
| Phase 3: 平台化基础建设 | ✅ 已完成 | v2.1.0 |
| Phase 4: 完整测试平台 | ✅ 已完成 | v2.2.0 |
| Phase 4+: 报告+K8s+推荐 | ✅ 已完成 | v2.3.0 |
| Phase 5a: 生产稳定性 | 🔄 进行中 (3/4) | v2.4.0 |
| Phase 5: 平台完善与生产化 | 🔄 进行中 | v3.0.0 |

> 详细计划见 [`docs/development-plan.md`](docs/development-plan.md)

---

## License

MIT
