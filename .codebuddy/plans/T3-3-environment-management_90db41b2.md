---
name: T3-3-environment-management
overview: 实现环境配置在线管理服务：新增 ORM 模型、Repository、Pydantic Schema、FastAPI CRUD 路由，改造 create_runner 支持 DB 环境优先加载（DB > YAML），并创建 Alembic 迁移。
todos:
  - id: create-orm-model
    content: Use [skill:python-best-practices] and [skill:database-patterns] to create framework/persistence/models/environment.py ORM model
    status: completed
  - id: create-repository
    content: Use [skill:python-api-endpoint-creator] to create framework/persistence/repositories/environment_repo.py
    status: completed
    dependencies:
      - create-orm-model
  - id: create-schema
    content: Use [skill:python-api-endpoint-creator] to create api/schemas/environment.py Pydantic schemas
    status: completed
  - id: create-router
    content: Use [skill:python-api-endpoint-creator] to create api/routers/environments.py CRUD router
    status: completed
    dependencies:
      - create-schema
      - create-repository
  - id: create-migration
    content: Create alembic migration for environments table
    status: completed
    dependencies:
      - create-orm-model
  - id: register-modules
    content: Register EnvironmentModel, EnvironmentRepository, and environments router in __init__.py and main.py
    status: completed
    dependencies:
      - create-orm-model
      - create-repository
      - create-router
  - id: integrate-runner
    content: Modify api/dependencies.py create_runner to load env from DB with fallback to YAML
    status: completed
    dependencies:
      - create-orm-model
      - create-repository
---

## 用户需求

实现 T3-3 环境管理服务，将环境配置从 YAML 文件迁移到数据库，支持在线 CRUD 管理。

## 产品概述

在现有 AutoTest Framework REST API 中新增环境管理模块。管理员可通过 API 在线创建、查看、编辑和删除测试环境配置（如开发/预发布/生产环境），无需手动编辑 YAML 文件。执行测试时，Runner 优先从数据库加载环境变量，数据库未命中时回退到 YAML 文件。

## 核心功能

- **环境 CRUD**：提供 `POST/GET/PUT/DELETE /api/v1/environments` 接口，支持分页列表查询
- **数据模型**：id (UUID)、name、description、base_url、ws_url、variables (JSON)、http_config (JSON)、created_at、updated_at
- **执行集成**：`create_runner()` 新增 `environment_id` 参数，从 DB 查询环境配置并构建 EnvConfig；调度任务的 `env_name` 字段兼容按名称匹配 DB 环境
- **优先级策略**：执行时优先从 DB 加载（按 ID 或名称匹配），DB 未命中时回退到 config/env.yaml 文件
- **向后兼容**：保留 ConfigLoader 和 env.yaml 机制，已有的 `env_name` 参数继续有效

## 技术栈

- **后端框架**: FastAPI + Pydantic v2
- **ORM**: SQLAlchemy 2.0 异步
- **数据库迁移**: Alembic
- **日志**: structlog (Logger.get)
- **语言**: Python >=3.12

## 实现方案

### 1. 数据模型设计

**EnvironmentModel**（`framework/persistence/models/environment.py`）字段映射自 EnvConfig dataclass：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 主键 |
| name | String(100) | 环境名称（唯一键） |
| description | String(500) | 环境描述 |
| base_url | String(500) | 被测服务 HTTP 基础 URL |
| ws_url | String(500) | WebSocket 服务 URL |
| variables | JSON | 环境级变量字典 |
| http_config | JSON | HTTP 客户端覆盖配置（timeout/verify_ssl 等） |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |


- `name` 字段添加唯一约束，支持按名称查找（与 schedule.env_name 联动）
- `variables` 和 `http_config` 使用 JSON 列类型存储字典

### 2. "DB 优先、文件兜底"策略

修改 `api/dependencies.py` 的 `create_runner()` 方法：

```
优先级链：
1. 若传入 environment_id → 从 DB 查询 → 构建 EnvConfig
2. 若传入 env_name → 先按名称查 DB → 命中则用 DB 数据，未命中用 ConfigLoader 从 YAML 加载
3. 若都未传 → ConfigLoader.load() 使用默认环境
```

新增辅助函数 `_load_env_from_db(session, env_id_or_name)` 从数据库构建 EnvConfig，与 ConfigLoader 返回结构一致。

保持 `runner_cache` 的 key 为 `env_name` 不变，确保缓存复用。

### 3. Repository 层

`EnvironmentRepository` 继承 `BaseRepository[EnvironmentModel]`，额外提供：

- `find_by_name(name)` → 按名称查询环境
- `find_by_name_ignore_case(name)` → 忽略大小写匹配（兼容 name 唯一约束）

### 4. API 路由

完全遵循 `api/routers/schedules.py` 的模式：

- `POST /api/v1/environments` — 创建环境（校验 name 唯一性）
- `GET /api/v1/environments` — 分页列表（按创建时间倒序）
- `GET /api/v1/environments/{id}` — 环境详情
- `PUT /api/v1/environments/{id}` — 更新环境（仅更新传入字段）
- `DELETE /api/v1/environments/{id}` — 删除环境

### 5. 文件变更清单

| 操作 | 文件 | 说明 |
| --- | --- | --- |
| 新建 | `framework/persistence/models/environment.py` | ORM 模型 |
| 新建 | `framework/persistence/repositories/environment_repo.py` | Repository |
| 新建 | `api/schemas/environment.py` | Pydantic Schema |
| 新建 | `api/routers/environments.py` | CRUD 路由 |
| 新建 | `alembic/versions/xxxx_add_environments_table.py` | 数据库迁移 |
| 修改 | `framework/persistence/models/__init__.py` | 注册 EnvironmentModel |
| 修改 | `framework/persistence/repositories/__init__.py` | 注册 EnvironmentRepository |
| 修改 | `api/routers/__init__.py` | 注册 environments 模块 |
| 修改 | `api/main.py` | include_router + TAGS_METADATA |
| 修改 | `api/dependencies.py` | create_runner 新增 DB 环境加载逻辑 |


## 实现要点

### 性能考虑

- `create_runner` 中 DB 查询仅在新环境名首次缓存未命中时发生（走 runner_cache）
- 按名称索引查询使用唯一约束，单次查询 O(log n)
- `variables` 和 `http_config` JSON 列反序列化由 SQLAlchemy/Pydantic 自动处理

### 日志规范

- 路由层日志: `Logger.get("api.environments")`
- 依赖层日志: `Logger.get("api.dependencies")`（已有）
- 关键事件: `env_created`, `env_deleted`, `env_db_lookup`, `env_fallback_yaml`

### 向后兼容

- `create_runner(env_name="dev")` 签名不变，内部增加 DB 查表逻辑
- schedule 表的 `env_name` 字段不受影响，调度执行时自动尝试 DB 匹配
- `ConfigLoader` 不做任何修改，作为兜底方案保留

### 线程安全

- `_load_env_from_db` 接受 `AsyncSession` 参数，由调用方管理会话生命周期
- `runner_cache` 已有的 `threading.Lock` 机制不变

## Agent Extensions

### Skill

- **python-api-endpoint-creator**
- Purpose: 按 FastAPI 分层架构（Router → Service → Repository）生成环境管理 CRUD 端点代码
- Expected outcome: 生成符合现有 schedule 模式的环境路由、Schema 和 Repository 代码

- **python-best-practices**
- Purpose: 确保所有新代码遵循项目 Python 编码规范（类型注解、docstring、async/await、Pydantic v2 等）
- Expected outcome: 代码通过 CodeBuddy 编码检查清单全部规则

- **database-patterns**
- Purpose: 设计 environments 表 Schema 和 Alembic 迁移脚本
- Expected outcome: 生成符合 SQLAlchemy 2.0 异步风格的 ORM 模型和迁移文件