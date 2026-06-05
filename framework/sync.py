"""YAML ↔ DB 双向同步模块

提供:
- YamlToDbImporter: 扫描 YAML 文件 → 解析 → 写入数据库
- DbToYamlExporter: 从数据库读取用例 → 生成 YAML 文件
- SyncConflictStrategy: 冲突处理策略（覆盖 / 跳过）
- SyncResult: 同步结果统计

设计原则:
- 导入时按 (name, source_file) 对匹配已有记录
- 导出时按 suite_name 分组重建 YAML 文件
- 导出时优先使用 DB 中存储的 yaml_content 作为源内容
- 所有数据库操作通过 Repository 层，保持分层架构
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import yaml

from framework.models import TestCase, TestSuite
from framework.parser import YAMLParser
from framework.persistence.models.test_case import TestCaseModel
from framework.persistence.models.test_suite import TestSuiteModel
from framework.persistence.repositories.case_repo import CaseRepository
from framework.persistence.repositories.suite_repo import SuiteRepository
from framework.utils.logger import Logger

logger = Logger.get("sync")


# ═══════════════════════════════════════════════════════════════
# 枚举 & 数据类
# ═══════════════════════════════════════════════════════════════


class SyncConflictStrategy(str, Enum):
    """同步冲突处理策略"""

    OVERWRITE = "overwrite"  # 存在则更新
    SKIP = "skip"  # 存在则跳过


@dataclass
class SyncResult:
    """同步操作结果统计"""

    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return self.created + self.updated + self.skipped

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def summary(self) -> str:
        parts = [f"总数={self.total}", f"新建={self.created}", f"更新={self.updated}"]
        if self.skipped > 0:
            parts.append(f"跳过={self.skipped}")
        if self.errors:
            parts.append(f"错误={len(self.errors)}")
        return ", ".join(parts)


# ═══════════════════════════════════════════════════════════════
# 辅助: 序列化 / 反序列化
# ═══════════════════════════════════════════════════════════════


def _normalize_path(file_path: str | Path) -> str:
    """将文件路径规范化为相对于项目根的路径（使用正斜杠）。"""
    p = Path(file_path).resolve()
    try:
        cwd = Path.cwd()
        p = p.relative_to(cwd)
    except ValueError:
        pass
    return p.as_posix()


def _tag_list_to_json(tags: list[str] | None) -> str | None:
    """将标签列表序列化为 JSON 字符串。"""
    if not tags:
        return None
    return json.dumps(tags, ensure_ascii=False)


def _json_to_tag_list(json_str: str | None) -> list[str]:
    """将 JSON 字符串反序列化为标签列表。"""
    if not json_str:
        return []
    try:
        parsed = json.loads(json_str)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _case_to_yaml_dict(case: TestCase) -> dict[str, Any]:
    """将 TestCase 领域模型转换为 YAML 友好的字典结构。

    仅保留 YAML 用例定义中需要的字段，排除内部运行状态。
    """

    result: dict[str, Any] = {"name": case.name}

    if case.description:
        result["description"] = case.description
    if case.tags:
        result["tags"] = case.tags
    if case.priority:
        result["priority"] = case.priority
    if case.skip:
        result["skip"] = True
    if case.skip_if:
        result["skip_if"] = case.skip_if
    if case.variables:
        result["variables"] = case.variables
    if case.timeout is not None:
        result["timeout"] = case.timeout

    # HTTP 请求
    if case.request:
        req: dict[str, Any] = {
            "method": case.request.method.value,
            "path": case.request.path,
        }
        if case.request.headers:
            req["headers"] = case.request.headers
        if case.request.params:
            req["params"] = case.request.params
        if case.request.body is not None:
            req["body"] = case.request.body
        if case.request.body_type.value != "json":
            req["body_type"] = case.request.body_type.value
        if case.request.timeout is not None:
            req["timeout"] = case.request.timeout
        if case.request.verify_ssl is not None:
            req["verify_ssl"] = case.request.verify_ssl
        if case.request.files:
            req["files"] = case.request.files
        if case.request.auth:
            req["auth"] = case.request.auth
        result["request"] = req

    # WebSocket 配置
    if case.ws_config:
        ws: dict[str, Any] = {
            "url": case.ws_config.url,
            "headers": case.ws_config.headers,
            "timeout": case.ws_config.timeout,
            "close_after": case.ws_config.close_after,
        }
        if case.ws_config.messages:
            msgs = []
            for m in case.ws_config.messages:
                msg: dict[str, Any] = {"type": m.type}
                if m.data:
                    msg["data"] = m.data
                if m.timeout is not None:
                    msg["timeout"] = m.timeout
                if m.expect:
                    msg["expect"] = m.expect
                msgs.append(msg)
            ws["messages"] = msgs
        result["ws_config"] = ws

    # 断言
    if case.assertions:
        expect: dict[str, Any] = {}
        body_expect: dict[str, Any] = {}
        jsonpath_expect: dict[str, Any] = {}
        header_expect: dict[str, Any] = {}

        for a in case.assertions:
            if a.path == "status_code":
                expect["status_code"] = a.expected
            elif a.path == "response_time":
                expect["response_time"] = f"<{a.expected}"
            elif a.path.startswith("body."):
                key = a.path[5:]
                # 检查大括号嵌套（如 body.data.id）
                parts = key.split(".")
                target = body_expect
                for part in parts[:-1]:
                    if part not in target:
                        target[part] = {}
                    target = target[part]
                target[parts[-1]] = _format_assert_value(a)
            elif a.path.startswith("headers."):
                header_expect[a.path[8:]] = _format_assert_value(a)
            else:
                jsonpath_expect[a.path] = _format_assert_value(a)

        if body_expect:
            expect["body"] = body_expect
        if jsonpath_expect:
            expect["jsonpath"] = jsonpath_expect
        if header_expect:
            expect["headers"] = header_expect

        if expect:
            result["expect"] = expect

    # 提取
    if case.extracts:
        extract: dict[str, Any] = {}
        for e in case.extracts:
            source = e.source
            if e.source_type == "header":
                source = f"header.{e.source}"
            elif e.source_type == "body_regex":
                source = f"regex:{e.source}"
            extract[e.var_name] = source
        result["extract"] = extract

    # 数据库断言
    if case.db_asserts:
        result["db_assert"] = [
            {
                "connection": da.connection,
                "sql": da.sql,
                "expect": da.expect,
                "fetch_one": da.fetch_one,
            }
            for da in case.db_asserts
        ]

    # Setup / Teardown
    if case.setup:
        result["setup"] = [
            {"action_type": fa.action_type, "config": fa.config} for fa in case.setup
        ]
    if case.teardown:
        result["teardown"] = [
            {"action_type": fa.action_type, "config": fa.config} for fa in case.teardown
        ]

    return result


def _format_assert_value(item: Any) -> Any:
    """格式化断言项的值为 YAML 友好形式。"""
    from framework.models import AssertItem

    if hasattr(item, "operator") and hasattr(item, "expected"):
        # 这是一个 AssertItem
        if item.operator == "eq":
            return item.expected
        return {
            "operator": item.operator,
            "value": item.expected,
        }
    return item


# ═══════════════════════════════════════════════════════════════
# YamlToDbImporter
# ═══════════════════════════════════════════════════════════════


class YamlToDbImporter:
    """YAML → DB 导入器

    扫描指定目录中的 .yaml / .yml 文件，解析为 TestSuite / TestCase，
    通过 Repository 层存入数据库。

    Attributes:
        parser: YAML 解析器实例。
        strategy: 冲突处理策略。
    """

    def __init__(
        self,
        parser: YAMLParser,
        case_repo_factory: Callable[[], CaseRepository],
        suite_repo_factory: Callable[[], SuiteRepository],
        strategy: SyncConflictStrategy = SyncConflictStrategy.OVERWRITE,
    ) -> None:
        self._parser = parser
        self._case_repo_factory = case_repo_factory
        self._suite_repo_factory = suite_repo_factory
        self.strategy = strategy

    @staticmethod
    def from_session_factory(
        parser: YAMLParser,
        session_factory: Callable[[], Any],
        strategy: SyncConflictStrategy = SyncConflictStrategy.OVERWRITE,
    ) -> YamlToDbImporter:
        """通过 session 工厂构造导入器（便捷方法）。

        Args:
            parser: YAML 解析器。
            session_factory: 返回 AsyncSession 的可调用对象。
            strategy: 冲突策略。

        Returns:
            YamlToDbImporter 实例。
        """
        return YamlToDbImporter(
            parser=parser,
            case_repo_factory=lambda: CaseRepository(session_factory()),
            suite_repo_factory=lambda: SuiteRepository(session_factory()),
            strategy=strategy,
        )

    async def import_dir(self, dir_path: str) -> SyncResult:
        """扫描目录，导入所有 YAML 文件。

        Args:
            dir_path: 包含 .yaml/.yml 文件的目录路径。

        Returns:
            SyncResult 统计结果。
        """
        path = Path(dir_path)
        if not path.is_dir():
            raise NotADirectoryError(f"目录不存在: {dir_path}")

        result = SyncResult()

        # 收集所有 YAML 文件
        yaml_files: list[Path] = []
        for pattern in ("*.yaml", "*.yml"):
            yaml_files.extend(sorted(path.rglob(pattern)))

        # 去重（同一文件 .yaml 和 .yml 都匹配时）
        seen: set[str] = set()
        unique_files: list[Path] = []
        for f in yaml_files:
            key = f.with_suffix("").name
            if key not in seen:
                seen.add(key)
                unique_files.append(f)

        for yaml_file in unique_files:
            try:
                file_result = await self.import_file(str(yaml_file))
                result.total += file_result.total
                result.created += file_result.created
                result.updated += file_result.updated
                result.skipped += file_result.skipped
                result.errors.extend(file_result.errors)
            except Exception as e:
                msg = f"导入文件失败 [{yaml_file}]: {e}"
                result.errors.append(msg)
                logger.error("import_file_error", file=str(yaml_file), error=str(e))

        logger.info(
            "import_dir_completed",
            dir=dir_path,
            result=result.summary(),
        )
        return result

    async def import_file(self, file_path: str) -> SyncResult:
        """导入单个 YAML 文件。

        Args:
            file_path: YAML 文件路径。

        Returns:
            SyncResult 统计结果。
        """
        result = SyncResult()

        # 1. 解析 YAML → TestSuite
        suite = self._parser.parse_file(file_path)

        # 2. 读取原始 YAML 文件内容
        raw_yaml = self._read_raw_yaml(file_path)
        normalized_path = _normalize_path(file_path)

        # 3. 处理 TestSuite
        suite_repo = self._suite_repo_factory()
        await self._upsert_suite(suite_repo, suite, normalized_path)

        # 4. 处理每个 TestCase
        case_repo = self._case_repo_factory()

        for case in suite.cases:
            result.total += 1
            try:
                action = await self._upsert_case(
                    case_repo,
                    case,
                    suite.name,
                    normalized_path,
                    raw_yaml,
                )
                if action == "created":
                    result.created += 1
                elif action == "updated":
                    result.updated += 1
                elif action == "skipped":
                    result.skipped += 1
            except Exception as e:
                msg = f"用例 [{case.name}] 导入失败: {e}"
                result.errors.append(msg)
                logger.error("case_import_error", case=case.name, error=str(e))

        logger.info(
            "import_file_completed",
            file=normalized_path,
            result=result.summary(),
        )
        return result

    # ── 私有方法 ──────────────────────────────────────────

    async def _upsert_suite(
        self,
        repo: SuiteRepository,
        suite: TestSuite,
        source_file: str,
    ) -> TestSuiteModel:
        """创建或更新套件记录。

        Returns:
            已持久化的 TestSuiteModel。
        """
        existing = await repo.find_by_name(suite.name)

        if existing is not None:
            if self.strategy == SyncConflictStrategy.SKIP:
                return existing
            # OVERWRITE: 更新字段
            existing.description = suite.description or existing.description
            existing.config = json.dumps(
                {
                    "base_url": suite.base_url,
                    "tags": suite.tags,
                    "priority": suite.priority,
                    "source_file": source_file,
                },
                ensure_ascii=False,
            )
            await repo.update(existing)
            logger.debug("suite_updated", name=suite.name)
            return existing

        model = TestSuiteModel(
            name=suite.name,
            description=suite.description,
            config=json.dumps(
                {
                    "base_url": suite.base_url,
                    "tags": suite.tags,
                    "priority": suite.priority,
                    "source_file": source_file,
                },
                ensure_ascii=False,
            ),
        )
        await repo.create(model)
        logger.debug("suite_created", name=suite.name)
        return model

    async def _upsert_case(
        self,
        repo: CaseRepository,
        case: TestCase,
        suite_name: str,
        source_file: str,
        yaml_content: str = "",
    ) -> str:
        """创建或更新用例记录。

        Returns:
            操作类型: "created" / "updated" / "skipped"
        """
        existing = await repo.find_by_name(case.name)

        if existing is not None:
            if self.strategy == SyncConflictStrategy.SKIP:
                logger.debug("case_skipped", name=case.name)
                return "skipped"
            # OVERWRITE: 更新字段
            existing.description = case.description or existing.description
            existing.tags = _tag_list_to_json(case.tags)
            existing.priority = case.priority
            existing.source_file = source_file
            existing.suite_name = suite_name
            existing.yaml_content = yaml_content or existing.yaml_content
            existing.version = (existing.version or 0) + 1
            await repo.update(existing)
            logger.debug("case_updated", name=case.name)
            return "updated"

        # 新建
        model = TestCaseModel(
            name=case.name,
            description=case.description,
            tags=_tag_list_to_json(case.tags),
            priority=case.priority,
            source_file=source_file,
            suite_name=suite_name,
            yaml_content=yaml_content,
        )
        await repo.create(model)
        logger.debug("case_created", name=case.name)
        return "created"

    @staticmethod
    def _read_raw_yaml(file_path: str) -> str:
        """读取原始 YAML 文件内容（用于存入 yaml_content）。"""
        with open(file_path, encoding="utf-8") as f:
            return f.read()


# ═══════════════════════════════════════════════════════════════
# DbToYamlExporter
# ═══════════════════════════════════════════════════════════════


class DbToYamlExporter:
    """DB → YAML 导出器

    从数据库读取用例和套件，按 suite_name 分组重建 YAML 文件，
    写入目标目录。

    Attributes:
        case_repo_factory: CaseRepository 工厂。
        suite_repo_factory: SuiteRepository 工厂。
        parser: YAML 解析器（用于校验导出的内容）。
    """

    def __init__(
        self,
        case_repo_factory: Callable[[], CaseRepository],
        suite_repo_factory: Callable[[], SuiteRepository],
        parser: YAMLParser | None = None,
    ) -> None:
        self._case_repo_factory = case_repo_factory
        self._suite_repo_factory = suite_repo_factory
        self._parser = parser or YAMLParser()

    @staticmethod
    def from_session_factory(
        session_factory: Callable[[], Any],
        parser: YAMLParser | None = None,
    ) -> DbToYamlExporter:
        """通过 session 工厂构造导出器（便捷方法）。

        Args:
            session_factory: 返回 AsyncSession 的可调用对象。
            parser: 可选的 YAML 解析器。

        Returns:
            DbToYamlExporter 实例。
        """
        return DbToYamlExporter(
            case_repo_factory=lambda: CaseRepository(session_factory()),
            suite_repo_factory=lambda: SuiteRepository(session_factory()),
            parser=parser,
        )

    async def export_to_dir(
        self,
        target_dir: str,
        suite_name: str | None = None,
    ) -> SyncResult:
        """导出所有（或指定套件的）用例到目标目录。

        Args:
            target_dir: 目标目录路径。
            suite_name: 可选，仅导出指定套件。

        Returns:
            SyncResult 统计结果。
        """
        result = SyncResult()
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)

        case_repo = self._case_repo_factory()
        suite_repo = self._suite_repo_factory()

        # 获取套件名列表
        if suite_name:
            suite_names = [suite_name]
            # 验证套件存在
            if await suite_repo.find_by_name(suite_name) is None:
                msg = f"套件 '{suite_name}' 不存在于数据库中"
                result.errors.append(msg)
                logger.error("suite_not_found", suite_name=suite_name)
                return result
        else:
            suite_names = await case_repo.list_all_suite_names()

        if not suite_names:
            logger.warning("no_suites_to_export")
            return result

        for sname in suite_names:
            try:
                file_result = await self._export_suite(
                    case_repo, suite_repo, sname, target_path
                )
                result.total += file_result.total
                result.created += file_result.created
                result.updated += file_result.updated
                result.skipped += file_result.skipped
                result.errors.extend(file_result.errors)
            except Exception as e:
                msg = f"导出套件 [{sname}] 失败: {e}"
                result.errors.append(msg)
                logger.error("export_suite_error", suite=sname, error=str(e))

        logger.info(
            "export_dir_completed",
            dir=target_dir,
            result=result.summary(),
        )
        return result

    # ── 私有方法 ──────────────────────────────────────────

    async def _export_suite(
        self,
        case_repo: CaseRepository,
        suite_repo: SuiteRepository,
        suite_name: str,
        target_dir: Path,
    ) -> SyncResult:
        """导出单个套件为 YAML 文件。

        Returns:
            SyncResult 统计结果。
        """
        result = SyncResult()

        # 查询套件信息
        suite_model = await suite_repo.find_by_name(suite_name)

        # 查询该套件下所有用例
        case_models = await case_repo.find_by_suite_name(suite_name)
        if not case_models:
            logger.warning("no_cases_for_suite", suite_name=suite_name)
            return result

        result.total = len(case_models)

        # 优先使用套件的 source_file 作为输出文件名
        safe_name = _safe_filename(suite_name)
        output_file = target_dir / f"{safe_name}.yaml"

        # 检查是否有原始 YAML 内容可以直接复用
        if suite_model and suite_model.config:
            try:
                config = json.loads(suite_model.config)
            except (json.JSONDecodeError, TypeError):
                config = {}

            # 构建完整的 YAML 结构
            suite_dict = self._build_suite_dict(
                suite_name=suite_name,
                description=suite_model.description or "",
                config=config,
                case_models=case_models,
            )
        else:
            suite_dict = self._build_suite_dict(
                suite_name=suite_name,
                description="",
                config={},
                case_models=case_models,
            )

        # 检查冲突
        if output_file.exists():
            # 存在同名文件 → 始终覆盖（导出方向由调用方决定策略）
            result.updated += 1
        else:
            result.created += 1

        # 写入文件（通过线程池避免阻塞事件循环）

        def _write_file() -> None:
            with open(output_file, "w", encoding="utf-8") as f:
                # 写入注释头
                f.write("# 由 autotest sync 导出生成\n")
                f.write(f"# 套件: {suite_name}\n")
                f.write(f"# 用例数: {len(case_models)}\n\n")
                yaml.dump(
                    suite_dict,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                    indent=2,
                    width=120,
                )

        await asyncio.to_thread(_write_file)

        logger.info(
            "suite_exported",
            suite=suite_name,
            file=str(output_file),
            case_count=len(case_models),
        )
        return result

    def _build_suite_dict(
        self,
        suite_name: str,
        description: str,
        config: dict[str, Any],
        case_models: list[TestCaseModel],
    ) -> dict[str, Any]:
        """从 DB 数据构建套件级 YAML 字典。

        Args:
            suite_name: 套件名称。
            description: 套件描述。
            config: 套件配置字典。
            case_models: 该套件的用例模型列表。

        Returns:
            YAML 友好的字典结构。
        """
        suite_dict: dict[str, Any] = {
            "name": suite_name,
        }
        if description:
            suite_dict["description"] = description

        base_url = config.get("base_url", "")
        if base_url:
            suite_dict["base_url"] = base_url

        tags = config.get("tags", [])
        if tags:
            suite_dict["tags"] = tags

        priority = config.get("priority", "P1")
        if priority:
            suite_dict["priority"] = priority

        # 构建 cases 列表
        cases_list: list[dict[str, Any]] = []
        for cm in case_models:
            case_dict = self._build_case_dict(cm)
            cases_list.append(case_dict)

        if cases_list:
            suite_dict["cases"] = cases_list

        return suite_dict

    def _build_case_dict(self, model: TestCaseModel) -> dict[str, Any]:
        """从 TestCaseModel 构建单个用例的 YAML 字典。

        优先使用 yaml_content 中的原始内容；若不可用则从模型字段重建。
        """
        # 尝试从 yaml_content 中提取用例级内容
        if model.yaml_content:
            try:
                parsed = yaml.safe_load(model.yaml_content)
                if isinstance(parsed, dict):
                    # yaml_content 存的是完整文件内容，提取匹配的 case
                    file_cases = parsed.get("cases", [])
                    if isinstance(file_cases, list):
                        for c in file_cases:
                            if isinstance(c, dict) and c.get("name") == model.name:
                                return c

                    # 如果 yaml_content 就是单个 case 定义
                    if parsed.get("name") == model.name:
                        return parsed
            except yaml.YAMLError:
                pass

        # 从模型字段重建最小用例定义
        case_dict: dict[str, Any] = {
            "name": model.name,
        }
        if model.description:
            case_dict["description"] = model.description
        if model.tags:
            case_dict["tags"] = _json_to_tag_list(model.tags)
        case_dict["priority"] = model.priority

        # 如果无法重建更多细节，添加注释说明
        if not model.yaml_content:
            case_dict["#_note"] = "此用例由数据库重建，可能不完整。建议通过解析器重新生成完整结构。"

        return case_dict


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _safe_filename(name: str) -> str:
    """将套件名称转换为安全的文件名。

    Args:
        name: 原始名称。

    Returns:
        安全的文件名（不含特殊字符）。
    """
    # 替换非法文件名字符
    safe = name.strip()
    for char in r'<>:"/\|?*':
        safe = safe.replace(char, "_")
    # 压缩连续下划线
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe or "unnamed_suite"
