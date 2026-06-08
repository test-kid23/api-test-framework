# AutoTest Framework · AI 编码速查卡

> 完整规范见 `docs/coding-standards.md`（v1.0），本文档为 AI 辅助编码的极简参考。

---

## 技术栈基线

- **Python**: `>=3.12` | **pytest**: `8.x` | **httpx**: `0.28.x` | **Pydantic**: `2.10.x`
- **ORM**: SQLAlchemy 2.0 异步 | **日志**: structlog | **路径**: pathlib
- **前端 (Phase 4+)**: React 18 + TypeScript 5 + Tailwind 3 + shadcn/ui + Zustand 4

---

## 快速检查清单

编写任何代码前，确保以下规则全部满足：

- [ ] `from __future__ import annotations` 在文件顶部
- [ ] 所有公共函数/方法有完整类型注解，用 `|` 联合类型（不用 `Optional`/`Union`）
- [ ] 公共类/函数/方法有 Google 风格 docstring（`Args:` / `Returns:` / `Raises:` / `Attributes:`）
- [ ] 新代码使用 PEP 695 `type` 语句声明类型别名和泛型（旧模块在 Phase 3 迁移）
- [ ] 所有路径用 `pathlib.Path`，禁止字符串拼接和 `os.path`
- [ ] 异步代码用 `async/await`，禁止回调；同步入口用 `asyncio.run()`
- [ ] 数据库操作通过 Repository 封装，禁止业务代码裸写 SQL。**豁免**：`DBExecutor` 的 raw SQL 执行是测试引擎功能需求
- [ ] **例外**：`conftest.py` 持久化逻辑逐步迁移到 Repository 模式
- [ ] 自定义异常继承 `AutoTestException`（`framework/exceptions.py`）
- [ ] 日志用 `Logger.get("xxx")` 获取（底层是 structlog），用例边界调用 `set_trace_id()` / `clear_trace_id()`
- [ ] 配置通过 `ConfigLoader` 单例获取，禁止模块内直接读文件
- [ ] 捕获具体异常类型，避免裸 `except Exception`（新模块严格禁止；旧模块 Phase 3 分批修复）
- [ ] 方法重写处添加 `@override` 装饰器（Phase 2 新模块推行）
- [ ] import 顺序：标准库 → 第三方 → 项目内部，禁止 `import *`

---

## 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块/文件 | `snake_case` | `http_client.py` |
| 类名 | `PascalCase` | `HttpClient` |
| 函数/方法/变量 | `snake_case` | `send_request()` |
| 常量 | `UPPER_SNAKE_CASE` | `DEFAULT_TIMEOUT` |
| 私有成员/模块 | `_leading_underscore` | `_build_url()` |

---

## 项目结构速查

```
framework/          # 核心测试引擎（不依赖 api/）
  assertion/        # 断言引擎
  executors/        # 步骤执行器（策略模式）
  interceptors/     # HTTP 拦截器链
  persistence/      # 数据持久化层
    models/         # SQLAlchemy ORM
    repositories/   # Repository 实现
  plugins/          # 插件系统
  report/           # 报告引擎
  utils/            # 工具模块
api/                # FastAPI REST 服务层（依赖 framework/）
  static/           #   前端构建产物（Vite 输出）
assertions/         # 自定义断言操作符扩展
config/             # YAML 配置文件
frontend/           # 管理前端（React 18 + Vite + shadcn/ui）
  src/
    api/            #   API 封装（Axios + TanStack Query）
    components/     #   UI 组件（shadcn/ui + 布局）
    hooks/          #   TanStack Query Hooks
    pages/          #   页面组件
    router/         #   React Router 6
    store/          #   Zustand 状态管理
    types/          #   TypeScript 类型
testcases/          # YAML 测试用例
tests/              # 单元测试与冒烟测试
```

**依赖方向**：`api → framework → persistence → utils`（上层依赖下层，不可反向）

---

## 常见模式速查

### 日志
```python
from framework.utils.logger import Logger, set_trace_id, clear_trace_id
logger = Logger.get("module_name")
logger.info("event_name", key1=val1, key2=val2)
```

### 配置
```python
from framework.config import ConfigLoader
loader = ConfigLoader()
project_config, env_config = loader.load(env_name="dev")
```

### 异常
```python
from framework.exceptions import AutoTestException
class MyError(AutoTestException): ...
```

### 路径
```python
from pathlib import Path
path = Path("config") / "config.yaml"
data = path.read_text(encoding="utf-8")
```

### 测试
```python
# 覆盖率目标：核心模块 ≥ 85%
# 运行：pytest tests/ -v --cov=framework
# 单模块：pytest tests/framework/test_runner.py -v
```

---

## 工具链

| 工具 | 用途 |
|------|------|
| black (line-length=100) | 格式化 |
| isort (profile=black) | import 排序 |
| ruff | Linter |
| mypy (strict) | 类型检查 |
| pytest + pytest-cov | 测试 + 覆盖率 |
| Alembic | 数据库迁移 |
