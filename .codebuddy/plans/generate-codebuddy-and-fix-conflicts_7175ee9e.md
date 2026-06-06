---
name: generate-codebuddy-and-fix-conflicts
overview: 生成极简 CODEBUDDY.md，并分三个优先级（立即修复 / Phase 2 / Phase 3）执行全部 11 项编码规范冲突修复。立即修复项：CODEBUDDY.md、#1 ExtractError、#6 Optional、#10 open→read_text、规范豁免补充、#5 Dataclass docstring。Phase 2 项：#2 SQLAlchemy 异步、#3 持久化走 Repository、#7 @override。Phase 3 项：#4 PEP 695 旧模块迁移、#8 裸 except 分批修复、#11 文件重命名。
todos:
  - id: generate-codebuddy-md
    content: 【立即】生成项目根目录 CODEBUDDY.md，从 coding-standards.md 浓缩核心编码约束
    status: completed
  - id: fix-extract-error
    content: "【立即 #1】删除 extractor.py 中 ExtractError 类，统一用 ExtractorError，同步更新测试文件"
    status: completed
  - id: fix-dataclass-docstring
    content: "【立即 #5】framework/models.py 中所有 dataclass 补充 Attributes: Google 风格 docstring"
    status: completed
  - id: fix-optional-syntax
    content: "【立即 #6】config_schema.py 中 Optional[AnyHttpUrl] → AnyHttpUrl | None，移除 Optional import"
    status: completed
  - id: fix-open-to-read-text
    content: "【立即 #10】config.py 中 with open → pathlib Path.read_text()"
    status: completed
  - id: update-standards-exemptions
    content: "【立即 #3 #9】coding-standards.md 补充 DBExecutor 豁免 + Logger 封装层保留说明"
    status: completed
  - id: add-override-decorators
    content: "【Phase 2 #7】api/ 和 persistence/ 新增模块的方法重写处统一添加 @override 装饰器"
    status: completed
  - id: fix-conftest-repository
    content: "【Phase 2 #3】conftest.py 持久化逻辑改用 Repository 模式"
    status: completed
  - id: migrate-db-async
    content: "【Phase 2 #2】framework/db.py DBExecutor 迁移到异步 create_async_engine"
    status: completed
  - id: audit-bare-except-phase2
    content: "【Phase 2 #8】审查 api/ 和 persistence/ 目录中裸 except Exception，替换为具体异常类型"
    status: completed
---

