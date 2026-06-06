---
name: fix-persistence-config-missing
overview: 修复 ProjectConfig 缺少 persistence 和 settings 字段导致的 pytest 运行报错，同时验证 parser→importers 模块改名的安全性。
todos:
  - id: fix-models
    content: 在 framework/models.py 中为 ProjectConfig 新增 persistence 和 settings 两个 dataclass 字段
    status: completed
  - id: fix-config-loader
    content: 在 framework/config.py 的 _build_project_config 方法中传递 persistence 和 settings 参数
    status: completed
    dependencies:
      - fix-models
  - id: verify-pytest
    content: 运行 python -m pytest testcases/local/test_user_api.yaml --env local -v 验证修复效果
    status: completed
    dependencies:
      - fix-config-loader
---

## 问题描述

执行 `python -m pytest testcases/local/test_user_api.yaml --env local -v` 报错：

```
conftest.py:142: in _persistence
    if not config.persistence.enabled:
E   AttributeError: 'ProjectConfig' object has no attribute 'persistence'
```

所有 8 个测试用例均在 setup 阶段因该错误而终止。

## 根因

`ProjectConfig` dataclass 定义和 `_build_project_config()` 构建方法均遗漏了 `persistence` 和 `settings` 两个字段，但：

- 配置文件 `config/config.yaml` 已有 `persistence.enabled: true`（第105行）和 `settings`（第11行）
- Pydantic Schema `AutotestConfig` 已定义 `persistence: PersistenceConfig`（`config_schema.py:134`）
- `conftest.py:142` 正确引用了 `config.persistence.enabled`

修复策略：纯增量补全缺失字段，不删除或重命名任何现有代码。

## 技术方案

### 修改范围

仅涉及 2 个文件，各 2 行纯增量代码：

| 文件 | 行号 | 修改内容 | 性质 |
| --- | --- | --- | --- |
| `framework/models.py` | 第 309 行后 | `ProjectConfig` 新增 `persistence` 和 `settings` 字段 | 纯增量 |
| `framework/config.py` | 第 295 行后 | `_build_project_config()` 传递 `persistence` 和 `settings` | 纯增量 |


### 数据流

```
config.yaml → ConfigLoader._load_yaml() → raw dict
    → _build_project_config(raw)  → ProjectConfig(persistence=raw.get("persistence", {}), settings=raw.get("settings", {}))
    → conftest.py: project_config.persistence.enabled  ✅
```

### 实现细节

**`framework/models.py`** — `ProjectConfig` dataclass（第309行后新增）：

```python
persistence: dict[str, Any] = field(default_factory=dict)
settings: dict[str, Any] = field(default_factory=dict)
```

- 类型与现有字段（`http`, `logging` 等）保持一致，均为 `dict[str, Any]`
- 默认值 `field(default_factory=dict)` 保证即使配置文件中不写也不会崩溃

**`framework/config.py`** — `_build_project_config()`（第295行后新增）：

```python
persistence=raw.get("persistence", {}),
settings=raw.get("settings", {}),
```

- 从原始 YAML dict 中按 key 获取，不存在时回退空 dict

### 防御性设计

- 两个字段均提供 `default_factory=dict`，即使 `config.yaml` 中删除 `persistence`/`settings` 节也不会导致 AttributeError
- `conftest.py:142` 的 `config.persistence.enabled` 在 YAML 不存在该配置节时为 `{}.get("enabled")` 即 `None`（falsy），行为等价于持久化关闭——安全降级