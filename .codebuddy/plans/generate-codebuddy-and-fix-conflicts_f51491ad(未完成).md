---
name: generate-codebuddy-and-fix-conflicts
overview: "生成极简 CODEBUDDY.md 文件，并根据用户审批的修复方案，执行立即修复项（#1 ExtractError → ExtractorError、#6 Optional→| None、#10 open→path.read_text），同时更新规范文档中 #3 #9 的豁免说明。"
todos:
  - id: generate-codebuddy-md
    content: 生成项目根目录 CODEBUDDY.md，从 docs/coding-standards.md 提取核心编码约束浓缩为极简卡片
    status: pending
  - id: fix-extract-error
    content: "修复 #1：删除 framework/extractor.py 中 ExtractError 类，替换为 framework/exceptions.py 的 ExtractorError，同步更新 tests/framework/test_extractor.py"
    status: pending
  - id: fix-optional-syntax
    content: "修复 #6：framework/config_schema.py 中 Optional[AnyHttpUrl] 替换为 AnyHttpUrl | None，移除 Optional import"
    status: pending
  - id: fix-open-to-read-text
    content: "修复 #10：framework/config.py 中 with open 改为 pathlib Path.read_text()"
    status: pending
  - id: update-standards-exemptions
    content: 更新 docs/coding-standards.md，在 Section 6.2 增加 DBExecutor 豁免条款，在 Section 8.1 增加 Logger 封装层保留说明
    status: pending
---

## 需求概述

1. 根据 `docs/coding-standards.md` 生成极简 `CODEBUDDY.md` 文件，供 AI 编码助手快速理解项目规范
2. 修复 3 项已审批的编码规范冲突：ExtractError 异常继承、Optional 类型替换、open 改 pathlib
3. 更新 `docs/coding-standards.md` 增加 2 项豁免条款

## 核心功能

- **CODEBUDDY.md**：从 coding-standards.md 提取核心编码约束，浓缩为约 150 行的极简参考卡片，覆盖 Python 版本、类型注解、docstring、路径处理、异步、异常、日志、命名等核心规则
- **冲突修复 #1**：删除 `framework/extractor.py` 中的 `ExtractError` 类，统一使用 `framework/exceptions.py` 中的 `ExtractorError`，同步更新测试文件中的引用和断言
- **冲突修复 #6**：`framework/config_schema.py` 中 `Optional[AnyHttpUrl]` 替换为 `AnyHttpUrl | None`，移除 `from typing import Optional`
- **冲突修复 #10**：`framework/config.py` 中 `with open(path)` 改为 `path.read_text(encoding="utf-8")` 后传给 `yaml.safe_load`
- **规范豁免**：coding-standards.md 中 DBExecutor raw SQL 增加豁免说明（测试引擎功能需求），Logger.get() 封装层增加保留说明

## 技术方案

### 实现策略

四个独立任务，无相互依赖，可并行执行：

1. **CODEBUDDY.md 生成**：从 coding-standards.md 中提取 12 个章节的核心约束，每条用一行浓缩表达，省略示例代码和长篇解释，保留"必须/禁止"级别的硬性规则
2. **ExtractError 替换**：两步走——先改源码（删除类定义 + 修改 raise + 新增 import），再改测试（更新 import、类引用、断言逻辑以适配 ExtractorError 签名）
3. **Optional 替换**：简单字符串替换，`Optional[AnyHttpUrl]` → `AnyHttpUrl | None`，移除 import 行中的 `Optional`
4. **open→read_text**：两行改动，`with open(path, encoding="utf-8") as f: data = yaml.safe_load(f)` → `data = yaml.safe_load(path.read_text(encoding="utf-8"))`

### 关键技术决策

- **ExtractError→ExtractorError 的参数适配**：原 `ExtractError(f"提取变量 '{item.var_name}' 失败: {e}")` 改为 `ExtractorError(f"提取变量 '{item.var_name}' 失败: {e}", var_name=item.var_name, source=item.source, source_type=item.source_type)`，充分利用 ExtractorError 的结构化字段
- **测试文件适配**：`TestExtractError` 类中 `issubclass(ExtractError, Exception)` 改为 `issubclass(ExtractorError, AutoTestException)`（验证规范继承链），`ExtractError("...")` 改为 `ExtractorError("...")`
- **CODEBUDDY.md 浓缩策略**：只保留"检查清单"级别的硬性约束，去除示例、原因解释、前后对比

### 影响范围

| 改动文件 | 改动类型 | 风险级别 |
| --- | --- | --- |
| `CODEBUDDY.md` | 新增 | 无风险 |
| `docs/coding-standards.md` | 追加 2 段豁免说明 | 无风险 |
| `framework/extractor.py` | 删除类 + 修改 raise + 新增 import | 低风险（ExtractorError 签名已稳定） |
| `tests/framework/test_extractor.py` | 更新 import 和测试断言 | 低风险 |
| `framework/config_schema.py` | 2 行修改 | 零风险 |
| `framework/config.py` | 2 行修改 | 零风险 |