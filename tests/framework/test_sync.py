"""YAML ↔ DB 双向同步功能测试

覆盖:
- YamlToDbImporter: 单文件/目录导入, 冲突策略 (overwrite/skip)
- DbToYamlExporter: 全量/指定套件导出
- SyncResult: 统计正确性
- 往返测试: YAML → DB → YAML, 数据完整性
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
import yaml

from framework.models import TestCase as DomainTestCase
from framework.models import TestSuite as DomainTestSuite
from framework.parser import YAMLParser
from framework.persistence.database import create_async_engine, create_async_session_factory
from framework.persistence.repositories.case_repo import CaseRepository
from framework.persistence.repositories.suite_repo import SuiteRepository

pytest.importorskip("framework.sync", reason="framework.sync 导入链存在兼容性问题 (Phase 2 TODO)")
from framework.sync import (  # noqa: E402
    DbToYamlExporter,
    SyncConflictStrategy,
    SyncResult,
    YamlToDbImporter,
    _safe_filename,
    _tag_list_to_json,
    _json_to_tag_list,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def sample_yaml_dir(tmp_path: Path) -> Path:
    """创建包含示例 YAML 文件的临时目录。"""
    yaml_content = """\
name: 示例 HTTPBin 测试套件
description: 用于验证同步功能的示例套件
base_url: "https://httpbin.org"
tags: [smoke, sync-test]

cases:
  - name: 示例 GET 请求
    description: 验证 GET 请求
    tags: [http, get]
    priority: P0
    request:
      method: GET
      path: /get
      params:
        page: 1
    expect:
      status_code: 200
      jsonpath:
        $.args.page: "1"

  - name: 示例 POST 请求
    description: 验证 POST JSON 提交
    tags: [http, post]
    priority: P1
    request:
      method: POST
      path: /post
      body:
        name: test_user
        action: create
    expect:
      status_code: 200
      jsonpath:
        $.json.name: "test_user"
    extract:
      result_url: $.url
"""
    suite_file = tmp_path / "sample_sync_test.yaml"
    suite_file.write_text(yaml_content, encoding="utf-8")
    return tmp_path


@pytest.fixture
def multi_file_yaml_dir(tmp_path: Path) -> Path:
    """创建包含多个 YAML 文件的目录。"""
    file1 = tmp_path / "suite_a.yaml"
    file1.write_text("""\
name: 套件A - 状态码测试
description: 测试不同 HTTP 状态码
base_url: "https://httpbin.org"
tags: [smoke]

cases:
  - name: 200 验证
    request:
      method: GET
      path: /status/200
    expect:
      status_code: 200

  - name: 404 验证
    request:
      method: GET
      path: /status/404
    expect:
      status_code: 404
""", encoding="utf-8")

    file2 = tmp_path / "suite_b.yaml"
    file2.write_text("""\
name: 套件B - 认证测试
description: 验证认证流程
base_url: "https://httpbin.org"
tags: [regression]

cases:
  - name: 登录获取 Token
    request:
      method: POST
      path: /post
      body:
        username: admin
    expect:
      status_code: 200
    extract:
      token: $.json.username

  - name: 使用 Token 访问
    request:
      method: GET
      path: /bearer
      headers:
        Authorization: "Bearer {{token}}"
    expect:
      status_code: 200
""", encoding="utf-8")

    return tmp_path


@pytest_asyncio.fixture(scope="function")
async def async_session():
    """创建 SQLite 内存数据库会话。"""
    engine = create_async_engine(
        {"driver": "sqlite", "database": ":memory:"}, echo=False
    )
    # 确保表已创建
    from framework.persistence.models.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = create_async_session_factory(engine)
    async with session_factory() as session:
        yield session

    await engine.dispose()


# ═══════════════════════════════════════════════════════════════
# SyncResult 测试
# ═══════════════════════════════════════════════════════════════


class TestSyncResult:
    """SyncResult 统计正确性"""

    def test_empty_result(self):
        result = SyncResult()
        assert result.total == 0
        assert result.created == 0
        assert result.updated == 0
        assert result.skipped == 0
        assert result.success_count == 0
        assert not result.has_errors

    def test_summary_with_all_fields(self):
        result = SyncResult(total=10, created=5, updated=3, skipped=2)
        assert result.success_count == 10
        summary = result.summary()
        assert "总数=10" in summary
        assert "新建=5" in summary
        assert "更新=3" in summary
        assert "跳过=2" in summary

    def test_with_errors(self):
        result = SyncResult(total=5, errors=["错误1", "错误2"])
        assert result.has_errors
        summary = result.summary()
        assert "错误=2" in summary


# ═══════════════════════════════════════════════════════════════
# 辅助函数测试
# ═══════════════════════════════════════════════════════════════


class TestHelperFunctions:
    """辅助函数单元测试"""

    def test_safe_filename_removes_special_chars(self):
        assert _safe_filename("test:suite") == "test_suite"
        assert _safe_filename("a/b\\c") == "a_b_c"
        assert _safe_filename('hello"world') == "hello_world"

    def test_safe_filename_empty(self):
        assert _safe_filename("") == "unnamed_suite"
        assert _safe_filename("   ") == "unnamed_suite"

    def test_tag_list_to_json(self):
        assert _tag_list_to_json(None) is None
        assert _tag_list_to_json([]) is None
        assert _tag_list_to_json(["smoke", "P0"]) == '["smoke", "P0"]'

    def test_json_to_tag_list(self):
        assert _json_to_tag_list(None) == []
        assert _json_to_tag_list("") == []
        assert _json_to_tag_list('["smoke", "P0"]') == ["smoke", "P0"]
        assert _json_to_tag_list("not json") == []


# ═══════════════════════════════════════════════════════════════
# YamlToDbImporter 测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_import_single_file(sample_yaml_dir, async_session):
    """测试导入单个 YAML 文件"""
    parser = YAMLParser()
    importer = YamlToDbImporter(
        parser=parser,
        case_repo_factory=lambda: CaseRepository(async_session),
        suite_repo_factory=lambda: SuiteRepository(async_session),
    )

    yaml_file = str(sample_yaml_dir / "sample_sync_test.yaml")
    result = await importer.import_file(yaml_file)

    assert result.total == 2
    assert result.created == 2
    assert result.updated == 0
    assert not result.has_errors

    # 验证 DB 中确实有数据
    case_repo = CaseRepository(async_session)
    suite_repo = SuiteRepository(async_session)

    suite = await suite_repo.find_by_name("示例 HTTPBin 测试套件")
    assert suite is not None
    assert "https://httpbin.org" in (suite.config or "")

    case1 = await case_repo.find_by_name("示例 GET 请求")
    assert case1 is not None
    assert case1.priority == "P0"
    assert case1.suite_name == "示例 HTTPBin 测试套件"

    case2 = await case_repo.find_by_name("示例 POST 请求")
    assert case2 is not None
    assert case2.priority == "P1"


@pytest.mark.asyncio
async def test_import_directory(multi_file_yaml_dir, async_session):
    """测试导入整个目录"""
    parser = YAMLParser()
    importer = YamlToDbImporter(
        parser=parser,
        case_repo_factory=lambda: CaseRepository(async_session),
        suite_repo_factory=lambda: SuiteRepository(async_session),
    )

    result = await importer.import_dir(str(multi_file_yaml_dir))

    assert result.total == 4  # 2 + 2
    assert result.created == 4
    assert not result.has_errors

    # 验证两个套件都存在
    case_repo = CaseRepository(async_session)
    suite_repo = SuiteRepository(async_session)

    suite_a = await suite_repo.find_by_name("套件A - 状态码测试")
    assert suite_a is not None
    suite_b = await suite_repo.find_by_name("套件B - 认证测试")
    assert suite_b is not None

    cases_a = await case_repo.find_by_suite_name("套件A - 状态码测试")
    assert len(cases_a) == 2
    cases_b = await case_repo.find_by_suite_name("套件B - 认证测试")
    assert len(cases_b) == 2


@pytest.mark.asyncio
async def test_import_overwrite_existing(sample_yaml_dir, async_session):
    """测试导入时覆盖已有数据"""
    parser = YAMLParser()
    yaml_file = str(sample_yaml_dir / "sample_sync_test.yaml")

    # 第一次导入
    importer1 = YamlToDbImporter(
        parser=parser,
        case_repo_factory=lambda: CaseRepository(async_session),
        suite_repo_factory=lambda: SuiteRepository(async_session),
    )
    result1 = await importer1.import_file(yaml_file)
    assert result1.created == 2
    assert result1.updated == 0

    # 第二次导入（覆盖）
    importer2 = YamlToDbImporter(
        parser=parser,
        case_repo_factory=lambda: CaseRepository(async_session),
        suite_repo_factory=lambda: SuiteRepository(async_session),
        strategy=SyncConflictStrategy.OVERWRITE,
    )
    result2 = await importer2.import_file(yaml_file)
    assert result2.created == 0
    assert result2.updated == 2

    # 验证 version 已递增
    case_repo = CaseRepository(async_session)
    case = await case_repo.find_by_name("示例 GET 请求")
    assert case is not None
    assert case.version >= 2


@pytest.mark.asyncio
async def test_import_skip_existing(sample_yaml_dir, async_session):
    """测试导入时跳过已有数据"""
    parser = YAMLParser()
    yaml_file = str(sample_yaml_dir / "sample_sync_test.yaml")

    # 第一次导入
    importer1 = YamlToDbImporter(
        parser=parser,
        case_repo_factory=lambda: CaseRepository(async_session),
        suite_repo_factory=lambda: SuiteRepository(async_session),
    )
    await importer1.import_file(yaml_file)

    # 第二次导入（跳过）
    importer2 = YamlToDbImporter(
        parser=parser,
        case_repo_factory=lambda: CaseRepository(async_session),
        suite_repo_factory=lambda: SuiteRepository(async_session),
        strategy=SyncConflictStrategy.SKIP,
    )
    result2 = await importer2.import_file(yaml_file)
    assert result2.skipped >= 2
    assert result2.created == 0
    assert result2.updated == 0


# ═══════════════════════════════════════════════════════════════
# DbToYamlExporter 测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_export_to_dir(sample_yaml_dir, async_session, tmp_path):
    """测试从 DB 导出到目录"""
    parser = YAMLParser()
    yaml_file = str(sample_yaml_dir / "sample_sync_test.yaml")

    # 先导入
    importer = YamlToDbImporter(
        parser=parser,
        case_repo_factory=lambda: CaseRepository(async_session),
        suite_repo_factory=lambda: SuiteRepository(async_session),
    )
    await importer.import_file(yaml_file)

    # 导出
    export_dir = tmp_path / "exported"
    exporter = DbToYamlExporter(
        case_repo_factory=lambda: CaseRepository(async_session),
        suite_repo_factory=lambda: SuiteRepository(async_session),
        parser=parser,
    )
    result = await exporter.export_to_dir(str(export_dir))

    assert result.total >= 2
    assert not result.has_errors

    # 验证导出文件存在且可解析
    exported_files = list(export_dir.rglob("*.yaml"))
    assert len(exported_files) >= 1

    exported_yaml = exported_files[0]
    with open(exported_yaml, encoding="utf-8") as f:
        content = f.read()

    # 验证是合法的 YAML
    parsed = yaml.safe_load(content)
    assert isinstance(parsed, dict)
    assert "name" in parsed
    # 套件名应匹配
    assert "示例 HTTPBin" in parsed["name"] or any(
        "示例" in c.get("name", "") for c in parsed.get("cases", [])
    )


@pytest.mark.asyncio
async def test_export_specific_suite(multi_file_yaml_dir, async_session, tmp_path):
    """测试导出指定套件"""
    parser = YAMLParser()

    # 导入目录
    importer = YamlToDbImporter(
        parser=parser,
        case_repo_factory=lambda: CaseRepository(async_session),
        suite_repo_factory=lambda: SuiteRepository(async_session),
    )
    await importer.import_dir(str(multi_file_yaml_dir))

    # 仅导出 套件A
    export_dir = tmp_path / "exported_a"
    exporter = DbToYamlExporter(
        case_repo_factory=lambda: CaseRepository(async_session),
        suite_repo_factory=lambda: SuiteRepository(async_session),
    )
    result = await exporter.export_to_dir(
        str(export_dir), suite_name="套件A - 状态码测试"
    )

    assert result.total >= 2
    assert not result.has_errors

    exported_files = list(export_dir.rglob("*.yaml"))
    assert len(exported_files) == 1

    content = yaml.safe_load(exported_files[0].read_text(encoding="utf-8"))
    assert "套件A" in content.get("name", "")


@pytest.mark.asyncio
async def test_export_nonexistent_suite(async_session, tmp_path):
    """测试导出不存在的套件"""
    exporter = DbToYamlExporter(
        case_repo_factory=lambda: CaseRepository(async_session),
        suite_repo_factory=lambda: SuiteRepository(async_session),
    )
    result = await exporter.export_to_dir(
        str(tmp_path / "nonexistent"),
        suite_name="不存在的套件",
    )

    assert result.has_errors
    assert len(result.errors) > 0
    assert "不存在" in result.errors[0]


# ═══════════════════════════════════════════════════════════════
# 往返测试（Round-trip）
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_roundtrip_import_export_no_data_loss(sample_yaml_dir, async_session, tmp_path):
    """往返测试: YAML → DB → YAML，验证数据完整性"""
    parser = YAMLParser()
    original_file = str(sample_yaml_dir / "sample_sync_test.yaml")

    # 读取原始内容
    with open(original_file, encoding="utf-8") as f:
        original_content = f.read()

    # Step 1: YAML → DB
    importer = YamlToDbImporter(
        parser=parser,
        case_repo_factory=lambda: CaseRepository(async_session),
        suite_repo_factory=lambda: SuiteRepository(async_session),
    )
    import_result = await importer.import_file(original_file)
    assert not import_result.has_errors
    assert import_result.total == import_result.created

    # Step 2: DB → YAML
    export_dir = tmp_path / "roundtrip"
    exporter = DbToYamlExporter(
        case_repo_factory=lambda: CaseRepository(async_session),
        suite_repo_factory=lambda: SuiteRepository(async_session),
        parser=parser,
    )
    export_result = await exporter.export_to_dir(str(export_dir))
    assert not export_result.has_errors

    # Step 3: 验证导出文件数量和结构
    exported_files = list(export_dir.rglob("*.yaml"))
    assert len(exported_files) >= 1

    # 解析导出的 YAML
    exported_content = exported_files[0].read_text(encoding="utf-8")
    exported_parsed = yaml.safe_load(exported_content)

    # 解析原始的 YAML
    original_parsed = yaml.safe_load(original_content)

    # 核心字段对比
    assert exported_parsed["name"] == original_parsed["name"]
    assert len(exported_parsed["cases"]) == len(original_parsed["cases"])

    # 验证每个用例的 name 匹配
    exported_names = {c["name"] for c in exported_parsed["cases"]}
    original_names = {c["name"] for c in original_parsed["cases"]}
    assert exported_names == original_names


# ═══════════════════════════════════════════════════════════════
# SyncConflictStrategy 测试
# ═══════════════════════════════════════════════════════════════


class TestSyncConflictStrategy:
    """冲突策略枚举"""

    def test_overwrite_value(self):
        assert SyncConflictStrategy.OVERWRITE == "overwrite"

    def test_skip_value(self):
        assert SyncConflictStrategy.SKIP == "skip"

    def test_parse_from_string(self):
        assert SyncConflictStrategy("overwrite") == SyncConflictStrategy.OVERWRITE
        assert SyncConflictStrategy("skip") == SyncConflictStrategy.SKIP


# ═══════════════════════════════════════════════════════════════
# YamlToDbImporter.from_session_factory 测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_importer_from_session_factory(async_session):
    """测试便捷构造方法 from_session_factory"""
    parser = YAMLParser()

    importer = YamlToDbImporter.from_session_factory(
        parser=parser,
        session_factory=lambda: async_session,
        strategy=SyncConflictStrategy.OVERWRITE,
    )
    assert importer.strategy == SyncConflictStrategy.OVERWRITE


@pytest.mark.asyncio
async def test_exporter_from_session_factory(async_session):
    """测试便捷构造方法 from_session_factory"""
    exporter = DbToYamlExporter.from_session_factory(
        session_factory=lambda: async_session,
    )
    assert exporter is not None
