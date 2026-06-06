"""AutoTest Framework CLI — 命令行入口

基于 typer 构建，提供以下命令:
- autotest run:     执行测试套件（支持 --suite/--env/--parallel）
- autotest sync:    YAML <-> DB 双向同步（支持 --from/--to 或子命令）
- autotest import:  OpenAPI/Swagger 规范导入（--source）
- autotest serve:   启动 FastAPI API 服务
- autotest report:  查询执行报告（--execution-id）

注册方式: pyproject.toml 中 [project.scripts] 注册
    autotest = "cli:app"

依赖: typer>=0.15.0
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Optional, Sequence

import typer

from framework.client import HttpClient
from framework.config import ConfigLoader
from framework.db import DBConnectionManager
from framework.importers.openapi_parser import OpenAPICaseParser, suite_to_yaml, testcase_to_yaml_content
from framework.models import SuiteResult
from framework.parser import YAMLParser
from framework.persistence.database import create_async_engine, create_async_session_factory
from framework.persistence.repositories.case_repo import CaseRepository
from framework.persistence.repositories.execution_repo import ExecutionRepository, ExecutionResultRepository
from framework.persistence.repositories.suite_repo import SuiteRepository
from framework.persistence.services.report_service import ReportService
from framework.report import create_report_adapter
from framework.runner import TestRunner
from framework.sync import (
    DbToYamlExporter,
    SyncConflictStrategy,
    YamlToDbImporter,
)
from framework.utils.logger import Logger

app = typer.Typer(
    name="autotest",
    help="AutoTest Framework CLI — API 自动化测试框架命令行工具",
)

logger = Logger.get("cli")


# ═══════════════════════════════════════════════════════════════
# 异步会话工厂辅助
# ═══════════════════════════════════════════════════════════════


@asynccontextmanager
async def _create_db_session(
    config_dir: str = "config",
) -> AsyncGenerator:
    """创建数据库会话的上下文管理器。

    自动从配置加载数据库设置、创建引擎和会话。
    """
    loader = ConfigLoader(config_dir)
    project_config, _ = loader.load()

    engine = create_async_engine(project_config.db)
    session_factory = create_async_session_factory(engine)
    async with session_factory() as session:
        try:
            yield session
        finally:
            await engine.dispose()


# ═══════════════════════════════════════════════════════════════
# run 命令
# ═══════════════════════════════════════════════════════════════


@app.command("run")
def run_suites(
    suite: str = typer.Option(
        "testcases",
        "--suite",
        "-s",
        help="用例文件或目录路径",
    ),
    env: str = typer.Option(
        "dev",
        "--env",
        "-e",
        help="目标环境名称（对应 env.yaml 中的环境）",
    ),
    parallel: Optional[int] = typer.Option(
        None,
        "--parallel",
        "-p",
        help="并行执行（传入 worker 数，或 -p auto 自动检测）",
    ),
    config_dir: str = typer.Option(
        "config",
        "--config",
        "-c",
        help="配置文件目录",
    ),
    tags: Optional[str] = typer.Option(
        None,
        "--tags",
        "-t",
        help="按标签过滤用例（逗号分隔）",
    ),
    no_persist: bool = typer.Option(
        False,
        "--no-persist",
        help="禁用数据库持久化",
    ),
) -> None:
    """执行测试套件。

    读取 YAML 用例文件，加载环境和配置，执行测试并输出结果。

    Examples:
        autotest run
        autotest run --suite testcases/smoke
        autotest run --suite testcases/httpbin_cases.yaml --env staging
        autotest run --parallel auto
        autotest run --parallel 4 --tags smoke,regression
    """
    suite_path = Path(suite).expanduser().resolve()

    # ── 并行模式：委托给 pytest + xdist ──
    if parallel is not None:
        _run_parallel(suite_path, env, parallel, config_dir, tags, no_persist)
        return

    # ── 串行模式：直接使用 TestRunner ──
    _run_sequential(suite_path, env, config_dir, tags, no_persist)


def _run_sequential(
    suite_path: Path,
    env_name: str,
    config_dir: str,
    tags: Optional[str],
    no_persist: bool,
) -> None:
    """串行执行测试套件（直接使用 TestRunner）。"""
    # 加载配置
    loader = ConfigLoader(config_dir)
    project_config, env_config = loader.load(env_name)

    # 创建 HTTP 客户端
    http_client = HttpClient(
        config=project_config.http,
        base_url=env_config.base_url,
    )

    # 创建 DB 管理器
    db_manager = DBConnectionManager()

    # 创建报告适配器
    report_adapter = create_report_adapter(project_config)

    # 创建执行引擎
    runner = TestRunner(
        config=project_config,
        env=env_config,
        http_client=http_client,
        db_manager=db_manager,
        report_adapter=report_adapter,
    )

    # 解析标签过滤器
    tag_set: set[str] | None = None
    if tags:
        tag_set = {t.strip() for t in tags.split(",") if t.strip()}

    # 解析 YAML 用例
    parser = YAMLParser()
    suites = _load_suites(parser, suite_path)

    if not suites:
        typer.echo(f"未找到任何用例: {suite_path}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"\n{'='*60}")
    typer.echo(f"  AutoTest 执行开始")
    typer.echo(f"  环境: {env_name} | 目标: {env_config.base_url}")
    typer.echo(f"  用例源: {suite_path}")
    typer.echo(f"{'='*60}\n")

    total_passed = 0
    total_failed = 0
    total_cases = 0

    for s in suites:
        # 应用标签过滤
        if tag_set:
            filtered_cases = [c for c in s.cases if set(c.tags) & tag_set]
            if not filtered_cases:
                continue
            s.cases = filtered_cases

        typer.echo(f"[Suite] {s.name} ({len(s.cases)} 用例)")
        result: SuiteResult = runner.run_suite(s)

        for cr in result.case_results:
            total_cases += 1
            icon = "[PASS]" if cr.passed else "[FAIL]"
            elapsed = f"{cr.elapsed_ms:.0f}ms" if cr.elapsed_ms else "N/A"
            typer.echo(f"  {icon} {cr.case_name} [{cr.status.value}] ({elapsed})")
            if cr.error:
                typer.echo(f"    错误: {cr.error[:120]}")

        if result.passed:
            total_passed += 1
        else:
            total_failed += 1

    # ── 汇总 ──
    typer.echo(f"\n{'='*60}")
    typer.echo(f"  执行完成")
    typer.echo(f"  套件: {total_passed} 通过 / {total_failed} 失败")
    typer.echo(f"  用例: {total_cases} 个")
    typer.echo(f"{'='*60}\n")

    if total_failed > 0:
        raise typer.Exit(code=1)


def _run_parallel(
    suite_path: Path,
    env_name: str,
    parallel: Optional[int],
    config_dir: str,
    tags: Optional[str],
    no_persist: bool,
) -> None:
    """并行执行测试（委托给 pytest + xdist）。"""
    cmd: list[str] = [
        sys.executable, "-m", "pytest",
        str(suite_path),
        "-v",
        "--tb=short",
    ]

    # 传递环境参数
    cmd.extend(["--env", env_name])

    # 标签过滤
    if tags:
        cmd.extend(["--tags", tags])

    # 禁用持久化
    if no_persist:
        cmd.append("--no-persist")

    # xdist 并行
    if parallel is None or str(parallel).lower() == "auto":
        cmd.extend(["-n", "auto"])
    else:
        cmd.extend(["-n", str(parallel)])

    typer.echo(f">>> 并行执行: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=str(Path.cwd()))
    if result.returncode != 0:
        raise typer.Exit(code=result.returncode)


def _load_suites(parser: YAMLParser, path: Path) -> list:
    """加载 YAML 测试套件（文件或目录）。"""
    from framework.models import TestSuite

    if path.is_file():
        suite = parser.parse_file(str(path))
        return [suite]
    elif path.is_dir():
        return parser.parse_dir(str(path))
    else:
        typer.echo(f"路径不存在: {path}", err=True)
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════
# sync 命令（子命令 + --from/--to 双模式）
# ═══════════════════════════════════════════════════════════════

_sync_app = typer.Typer(
    name="sync",
    help="YAML <-> DB 双向同步",
    invoke_without_command=True,
)
app.add_typer(_sync_app)


@_sync_app.callback()
def sync_main(
    ctx: typer.Context,
    from_: str = typer.Option(
        "yaml",
        "--from",
        help="来源格式: yaml | db",
    ),
    to: str = typer.Option(
        "db",
        "--to",
        help="目标格式: yaml | db",
    ),
    directory: str = typer.Option(
        "testcases",
        "--dir",
        "-d",
        help="YAML 文件目录（yaml->db 时读取，db->yaml 时写入）",
    ),
    strategy: str = typer.Option(
        "overwrite",
        "--strategy",
        "-s",
        help="冲突策略: overwrite（覆盖） | skip（跳过）",
    ),
    config_dir: str = typer.Option(
        "config",
        "--config",
        "-c",
        help="配置文件目录",
    ),
) -> None:
    """YAML <-> DB 双向同步。

    支持两种调用方式:
      autotest sync --from yaml --to db          # YAML -> DB
      autotest sync --from db --to yaml          # DB -> YAML
      autotest sync yaml-to-db --dir testcases   # 等价子命令
      autotest sync db-to-yaml --target-dir out  # 等价子命令

    当 --from/--to 指定且无子命令时，自动路由到对应子命令。
    """
    if ctx.invoked_subcommand is not None:
        # 有子命令（如 yaml-to-db），由子命令处理
        return

    # 无子命令时，根据 --from/--to 路由
    f = from_.lower().strip()
    t = to.lower().strip()

    if f == "yaml" and t == "db":
        sync_yaml_to_db(directory=directory, strategy=strategy, config_dir=config_dir)
    elif f == "db" and t == "yaml":
        sync_db_to_yaml(target_dir=directory, suite=None, config_dir=config_dir)
    else:
        typer.echo(
            f"不支持的同步方向: --from {from_} --to {to}。支持: yaml->db, db->yaml",
            err=True,
        )
        raise typer.Exit(code=1)


@_sync_app.command("yaml-to-db")
def sync_yaml_to_db(
    directory: str = typer.Option(
        "testcases",
        "--dir",
        "-d",
        help="YAML 文件所在目录",
    ),
    strategy: str = typer.Option(
        "overwrite",
        "--strategy",
        "-s",
        help="冲突策略: overwrite（覆盖） 或 skip（跳过）",
    ),
    config_dir: str = typer.Option(
        "config",
        "--config",
        "-c",
        help="配置文件目录",
    ),
) -> None:
    """从 YAML 文件导入用例到数据库。

    Examples:
        autotest sync yaml-to-db
        autotest sync yaml-to-db --dir testcases/smoke
        autotest sync yaml-to-db --strategy skip
    """
    strategy_enum = _parse_strategy(strategy)

    async def _run() -> None:
        async with _create_db_session(config_dir) as session:
            parser = YAMLParser()
            importer = YamlToDbImporter(
                parser=parser,
                case_repo_factory=lambda: CaseRepository(session),
                suite_repo_factory=lambda: SuiteRepository(session),
                strategy=strategy_enum,
            )
            result = await importer.import_dir(directory)

        _print_result(result, f"YAML -> DB 导入完成 [{directory}]")
        if result.has_errors:
            raise typer.Exit(code=1)

    asyncio.run(_run())


@_sync_app.command("db-to-yaml")
def sync_db_to_yaml(
    target_dir: str = typer.Option(
        "testcases_exported",
        "--target-dir",
        "-t",
        help="YAML 输出目录",
    ),
    suite: Optional[str] = typer.Option(
        None,
        "--suite",
        help="仅导出指定套件（不指定则导出全部）",
    ),
    config_dir: str = typer.Option(
        "config",
        "--config",
        "-c",
        help="配置文件目录",
    ),
) -> None:
    """从数据库导出用例为 YAML 文件。

    Examples:
        autotest sync db-to-yaml
        autotest sync db-to-yaml --target-dir exported
        autotest sync db-to-yaml --suite "HTTPBin 基础接口测试"
    """
    async def _run() -> None:
        async with _create_db_session(config_dir) as session:
            parser = YAMLParser()
            exporter = DbToYamlExporter(
                case_repo_factory=lambda: CaseRepository(session),
                suite_repo_factory=lambda: SuiteRepository(session),
                parser=parser,
            )
            result = await exporter.export_to_dir(target_dir, suite_name=suite)

        _print_result(result, f"DB -> YAML 导出完成 [{target_dir}]")
        if result.has_errors:
            raise typer.Exit(code=1)

    asyncio.run(_run())


# ═══════════════════════════════════════════════════════════════
# import 命令（OpenAPI/Swagger）
# ═══════════════════════════════════════════════════════════════


@app.command("import")
def import_openapi(
    source: str = typer.Option(
        ...,
        "--source",
        "-s",
        help="OpenAPI/Swagger spec URL 或本地文件路径",
    ),
    output_dir: str = typer.Option(
        "testcases_imported",
        "--output-dir",
        "-o",
        help="生成 YAML 的输出目录",
    ),
    suite_name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="套件名称（不指定则从 spec info.title 推断）",
    ),
    import_to_db: bool = typer.Option(
        False,
        "--to-db",
        help="同时导入到数据库",
    ),
    config_dir: str = typer.Option(
        "config",
        "--config",
        "-c",
        help="配置文件目录",
    ),
) -> None:
    """从 OpenAPI/Swagger 规范导入用例。

    解析 OpenAPI 3.x 规范（JSON 或 YAML 格式），为每个 path+method
    自动生成 TestCase，输出为框架 YAML 格式。

    Examples:
        autotest import --source https://petstore3.swagger.io/api/v3/openapi.json
        autotest import --source ./openapi.yaml --name "用户服务"
        autotest import --source ./spec.json --to-db
    """
    typer.echo(f"[*] 解析 OpenAPI spec: {source}")

    try:
        parser = OpenAPICaseParser()
        suite = parser.parse_from_url(source, suite_name=suite_name)
    except FileNotFoundError as e:
        typer.echo(f"错误: {e}", err=True)
        raise typer.Exit(code=1) from e
    except ValueError as e:
        typer.echo(f"错误: {e}", err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.echo(f"解析失败: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo(f"[OK] 解析完成: {len(suite.cases)} 个用例生成")

    # 写入 YAML 文件
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    # 生成套件级 YAML（含 meta）
    suite_yaml = suite_to_yaml(suite)
    suite_file = output_path / f"{_safe_filename(suite.name)}.yaml"
    suite_file.write_text(suite_yaml, encoding="utf-8")
    typer.echo(f"[+] 套件: {suite_file}")

    # 逐用例生成独立 YAML
    for i, case in enumerate(suite.cases):
        case_yaml = testcase_to_yaml_content(case)
        case_name = f"{i+1:03d}_{_safe_filename(case.name)}.yaml"
        case_file = output_path / case_name
        case_file.write_text(case_yaml, encoding="utf-8")
        typer.echo(f"  + {case_file.name}")

    # 可选：导入到数据库
    if import_to_db:
        async def _import_to_db() -> None:
            async with _create_db_session(config_dir) as session:
                parser_adapter = YAMLParser()
                importer = YamlToDbImporter(
                    parser=parser_adapter,
                    case_repo_factory=lambda: CaseRepository(session),
                    suite_repo_factory=lambda: SuiteRepository(session),
                    strategy=SyncConflictStrategy.OVERWRITE,
                )
                result = await importer.import_dir(str(output_path))
            _print_result(result, f"已导入数据库 [{output_path}]")

        asyncio.run(_import_to_db())

    typer.echo(f"\n[OK] 导入完成，输出目录: {output_path}")


def _safe_filename(name: str) -> str:
    """将名称转为安全的文件名。"""
    import re
    safe = re.sub(r'[<>:"/\\|?*]', "_", name)
    safe = re.sub(r'\s+', "_", safe)
    return safe[:100]


# ═══════════════════════════════════════════════════════════════
# serve 命令
# ═══════════════════════════════════════════════════════════════


@app.command("serve")
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="监听地址"),
    port: int = typer.Option(8000, "--port", "-p", help="监听端口"),
    reload: bool = typer.Option(False, "--reload", "-r", help="开发模式自动重载"),
) -> None:
    """启动 API 服务（FastAPI）。

    启动后可通过 http://{host}:{port}/docs 访问 Swagger UI。

    Examples:
        autotest serve
        autotest serve --port 8080
        autotest serve --reload
    """
    import uvicorn

    typer.echo(f">>> 启动 API 服务: http://{host}:{port}")
    typer.echo(f"   Swagger UI: http://{host}:{port}/docs")
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


# ═══════════════════════════════════════════════════════════════
# report 命令
# ═══════════════════════════════════════════════════════════════


@app.command("report")
def report(
    execution_id: str = typer.Option(
        ...,
        "--execution-id",
        "-e",
        help="执行记录 ID（UUID）",
    ),
    output_format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="输出格式: table | json",
    ),
    config_dir: str = typer.Option(
        "config",
        "--config",
        "-c",
        help="配置文件目录",
    ),
) -> None:
    """查询测试执行报告。

    根据 execution_id 从数据库查询执行记录及每个用例的结果。

    Examples:
        autotest report --execution-id 550e8400-e29b-41d4-a716-446655440000
        autotest report --execution-id ... --format json
    """
    # 验证 UUID 格式
    try:
        exec_id = uuid.UUID(execution_id)
    except ValueError:
        typer.echo(f"无效的 execution-id 格式: {execution_id}", err=True)
        raise typer.Exit(code=1)

    async def _query() -> None:
        async with _create_db_session(config_dir) as session:
            # 查询执行记录
            exec_repo = ExecutionRepository(session)
            exec_record = await exec_repo.get_with_results(exec_id)

            if exec_record is None:
                typer.echo(f"未找到执行记录: {execution_id}", err=True)
                raise typer.Exit(code=1)

            # 查询详细结果
            result_repo = ExecutionResultRepository(session)
            results: Sequence = await result_repo.list_by_execution(exec_id)

            # 统计
            total = len(results)
            passed = sum(1 for r in results if r.passed)
            failed = total - passed
            pass_rate = (passed / total * 100) if total > 0 else 0

            # 输出
            if output_format == "json":
                _report_json(exec_record, results, total, passed, failed, pass_rate)
            else:
                _report_table(exec_record, results, total, passed, failed, pass_rate)

    asyncio.run(_query())


def _report_table(
    exec_record: Any,
    results: Sequence,
    total: int,
    passed: int,
    failed: int,
    pass_rate: float,
) -> None:
    """以表格形式输出报告。"""
    typer.echo(f"\n{'='*70}")
    typer.echo(f"  执行报告")
    typer.echo(f"{'='*70}")
    typer.echo(f"  执行 ID:   {exec_record.id}")
    typer.echo(f"  状态:      {exec_record.status}")
    typer.echo(f"  触发器:    {exec_record.trigger}")
    typer.echo(f"  环境:      {exec_record.env or 'N/A'}")
    if exec_record.started_at:
        typer.echo(f"  开始时间:  {exec_record.started_at.isoformat()}")
    if exec_record.finished_at:
        typer.echo(f"  结束时间:  {exec_record.finished_at.isoformat()}")
    typer.echo(f"{'='*70}")
    typer.echo(f"  用例总数:  {total}")
    typer.echo(f"  通过:      {passed}  [PASS]")
    typer.echo(f"  失败:      {failed}  [FAIL]")
    typer.echo(f"  通过率:    {pass_rate:.1f}%")
    typer.echo(f"{'='*70}\n")

    if results:
        typer.echo(f"{'状态':<8} {'用例名称':<40} {'耗时':>10} {'错误'}")
        typer.echo("-" * 70)
        for r in results:
            icon = "[PASS]" if r.passed else "[FAIL]"
            elapsed = f"{r.elapsed_ms:.0f}ms" if r.elapsed_ms else "-"
            error = (r.error or "")[:60]
            typer.echo(f"{icon} {r.status:<5} {r.case_name or '-':<38} {elapsed:>10} {error}")
        typer.echo()


def _report_json(
    exec_record: Any,
    results: Sequence,
    total: int,
    passed: int,
    failed: int,
    pass_rate: float,
) -> None:
    """以 JSON 格式输出报告。"""
    report_data: dict[str, Any] = {
        "execution_id": str(exec_record.id),
        "status": exec_record.status,
        "trigger": exec_record.trigger,
        "env": exec_record.env,
        "started_at": exec_record.started_at.isoformat() if exec_record.started_at else None,
        "finished_at": exec_record.finished_at.isoformat() if exec_record.finished_at else None,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(pass_rate, 2),
        },
        "results": [
            {
                "case_name": r.case_name,
                "status": r.status,
                "passed": r.passed,
                "elapsed_ms": r.elapsed_ms,
                "error": r.error,
            }
            for r in results
        ],
    }
    typer.echo(json.dumps(report_data, indent=2, ensure_ascii=False, default=str))


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _parse_strategy(strategy: str) -> SyncConflictStrategy:
    """解析冲突策略字符串。"""
    s = strategy.lower().strip()
    if s in ("overwrite", "覆盖"):
        return SyncConflictStrategy.OVERWRITE
    elif s in ("skip", "跳过"):
        return SyncConflictStrategy.SKIP
    else:
        typer.echo(f"警告: 未知策略 '{strategy}'，使用默认 'overwrite'", err=True)
        return SyncConflictStrategy.OVERWRITE


def _print_result(result: Any, title: str) -> None:
    """打印同步结果。"""
    typer.echo(f"\n{'='*60}")
    typer.echo(f"  {title}")
    typer.echo(f"{'='*60}")
    typer.echo(f"  总数:  {result.total}")
    typer.echo(f"  新建:  {result.created}")
    typer.echo(f"  更新:  {result.updated}")
    typer.echo(f"  跳过:  {result.skipped}")
    if result.errors:
        typer.echo(f"  错误:  {len(result.errors)}")
        for err in result.errors:
            typer.echo(f"    - {err}")
    typer.echo(f"{'='*60}\n")


if __name__ == "__main__":
    app()
