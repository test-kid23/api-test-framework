---
name: persistence-switch-and-todo
overview: 为持久化机制添加可配置开关（config.yaml），并为 report_service.py 的 text() SQL 添加技术债 TODO 注释。
todos:
  - id: add-persistence-config-schema
    content: 在 config_schema.py 新增 PersistenceConfig 模型并在 AutotestConfig 中添加 persistence 字段
    status: completed
  - id: add-persistence-config-yaml
    content: "在 config/config.yaml 新增 persistence.enabled: true 配置段"
    status: completed
  - id: add-persistence-toggle-conftest
    content: 在 conftest.py 的 _persistence fixture 中增加 enabled 开关早期退出逻辑
    status: completed
    dependencies:
      - add-persistence-config-schema
  - id: add-todo-comments-report-service
    content: 在 report_service.py 的 get_pass_rate_trend 和 get_avg_response_time_trend 两处 text() SQL 处添加 TODO 注释
    status: completed
---

## 用户需求

对之前持久化功能的修改做两项补充：

### 1. 持久化开关

在 conftest.py 的 `_persistence` fixture 中增加 config 开关，当 `config.persistence.enabled = false` 时跳过所有数据库操作。需要同步修改 config_schema.py（新增 `PersistenceConfig` 模型）和 config/config.yaml（新增 `persistence` 配置段）。默认 `enabled: true`，保持当前行为不变。

### 2. TODO 注释

在 report_service.py 的 `get_pass_rate_trend` 和 `get_avg_response_time_trend` 两个方法中，为 `text()` 原生 SQL 添加 TODO 注释，说明这是绕过 SQLAlchemy 2.0 异步编译器 `_isnull` bug 的临时方案，避免后续维护者误解。

## 修改范围

仅涉及 4 个文件，均为小范围增量修改，不影响已有功能。

### 1. config_schema.py — 新增 PersistenceConfig 模型

在 `DBConfig` 类定义之后、`AutotestConfig` 类定义之前插入：

```python
class PersistenceConfig(BaseModel):
    """持久化配置

    enabled: 是否启用持久化，关闭后测试执行不会写入数据库，适合本地调试。
    """

    model_config = ConfigDict(extra="ignore")

    enabled: bool = Field(default=True, description="是否启用持久化。关闭后不写入数据库")
```

然后在 `AutotestConfig` 的字段列表中新增一行：

```python
persistence: PersistenceConfig = Field(default_factory=PersistenceConfig, description="持久化配置")
```

位置：放在 `db: DBConfig` 之后或之前均可，建议放在 `db` 之前以保持配置文件的阅读顺序一致。

### 2. config/config.yaml — 新增 persistence 配置段

在 `db:` 配置段之前插入：

```
# ----------------------------------------------------------
# 持久化配置
# ----------------------------------------------------------
persistence:
  enabled: true                         # 是否启用持久化（默认开启，本地调试可关闭）
```

### 3. conftest.py — _persistence fixture 增加开关检查

在 `_persistence` fixture 中，`config, _ = loader.load(env_name)` 之后、`engine = create_async_engine(...)` 之前插入：

```python
    # 持久化开关：关闭时跳过所有数据库操作
    if not config.persistence.enabled:
        yield {}
        return
```

由于 `_persistence` 是 generator fixture，`yield {}` 后 `return` 会跳过后续所有 setup（建表、创建执行记录）和 teardown（更新状态、dispose engine）逻辑。

### 4. report_service.py — 两处 TODO 注释

- **第 92 行**（`get_pass_rate_trend`）：将现有注释 `# 使用 text() 原生 SQL 完全绕过 SQLAlchemy 编译器 func.date() _isnull bug` 替换为：

```python
        # TODO(T2-4): 用 ORM 重写。当前 text() 是为了绕过 SQLAlchemy 2.0 异步编译器
        # func.date() 的 _isnull AttributeError bug。
        # 已在 SQLite 3.45+ 验证通过。切 PostgreSQL 时需检查 DATE() 语法兼容性。
```

- **第 154 行之后**（`get_avg_response_time_trend`）：在 `start = _days_ago_utc(days)` 之前插入：

```python
        # TODO(T2-4): 同 get_pass_rate_trend。当前 text() 是为了绕过 SQLAlchemy 2.0
        # 异步编译器 func.date() 的 _isnull AttributeError bug。
        # 已在 SQLite 3.45+ 验证通过。切 PostgreSQL 时需检查 DATE() 语法兼容性。
```