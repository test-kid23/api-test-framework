"""AutoTest Framework CLI — 命令行入口

基于 typer 构建，提供以下命令:
- autotest sync: YAML ↔ DB 双向同步
- autotest serve: (T2-1) 启动 API 服务
- autotest import: (T2-5) OpenAPI 导入

注册方式: pyproject.toml 中 [project.scripts] 注册
    autotest = "cli:app"

依赖: typer>=0.15.0
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

import typer

from framework.config import ConfigLoader
from framework.parser import YAMLParser
from framework.persistence.database import create_async_engine, create_async_session_factory
from framework.persistence.repositories.case_repo import CaseRepository
from framework.persistence.repositories.suite_repo import SuiteRepository
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
# sync 命令
# ═══════════════════════════════════════════════════════════════

_sync_app = typer.Typer(
    name="sync",
    help="YAML ↔ DB 双向同步",
)
app.add_typer(_sync_app)


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
    # 解析策略
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

        _print_result(result, f"YAML → DB 导入完成 [{directory}]")
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

        _print_result(result, f"DB → YAML 导出完成 [{target_dir}]")
        if result.has_errors:
            raise typer.Exit(code=1)

    asyncio.run(_run())


# ═══════════════════════════════════════════════════════════════
# serve 命令（T2-1，基础定义）
# ═══════════════════════════════════════════════════════════════


@app.command("serve")
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="监听地址"),
    port: int = typer.Option(8000, "--port", "-p", help="监听端口"),
    reload: bool = typer.Option(False, "--reload", "-r", help="开发模式自动重载"),
) -> None:
    """启动 API 服务（T2-1 FastAPI）。

    启动后可通过 http://{host}:{port}/docs 访问 Swagger UI。

    Examples:
        autotest serve
        autotest serve --port 8080
        autotest serve --reload
    """
    import uvicorn

    typer.echo(f"启动 API 服务: http://{host}:{port}")
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


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
