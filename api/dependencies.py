"""依赖注入 — 数据存储、配置、公共服务

当前 Phase 2 第一阶段使用内存存储（InMemoryStore）。
Phase 2 T2-2 完成后将替换为 SQLAlchemy AsyncSession。

报告模块（T2-4）已接入真实数据库，通过 get_db_session() 注入 AsyncSession。

T2-7 异步执行支持：
- create_runner(): 创建 TestRunner（含 AsyncHttpClient），供 executions 路由使用
- parse_yaml_case(): 将存储的 YAML 内容字符串解析为 TestCase 对象
"""

from __future__ import annotations

import os
import threading
from collections.abc import AsyncGenerator
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import yaml
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from api.schemas.case import CaseResponse
from framework.client import AsyncHttpClient, HttpClient
from framework.config import ConfigLoader
from framework.context import TestContext
from framework.db import DBConnectionManager
from framework.models import EnvConfig, ProjectConfig, TestCase, TestSuite
from framework.parser import YAMLParser
from framework.persistence.database import create_async_engine, create_async_session_factory
from framework.report.base import NoopReportAdapter
from framework.runner import TestRunner
from framework.utils.logger import Logger


# ==================== 内存数据存储（已废弃） ====================
#
# InMemoryStore 在路由层已被 SQLAlchemy Repository 替代。
# 保留类定义仅为测试兼容（部分测试可能仍引用 reset_store）。
# 新代码请使用 get_db_session() + 对应的 Repository 类。
#
# Deprecated since: Phase 2 T2-2 路由层切换到数据库。


class InMemoryStore:
    """[废弃] 线程安全的内存数据存储

    路由层已切换至 SQLAlchemy Repository 实现。
    保留此类仅用于测试场景，请勿在新路由中使用。
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cases: Dict[str, Dict[str, Any]] = {}
        self._suites: Dict[str, Dict[str, Any]] = {}
        self._executions: Dict[str, Dict[str, Any]] = {}
        self._reports: Dict[str, Dict[str, Any]] = {}
        self._case_versions: Dict[str, list[Dict[str, Any]]] = {}

    # ── Cases ──────────────────────────────────────────

    def create_case(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            record = deepcopy(data)
            case_id = record["id"]
            record["version"] = 1
            record["created_at"] = datetime.now(timezone.utc)
            record["updated_at"] = datetime.now(timezone.utc)
            self._cases[case_id] = record
            self._case_versions[case_id] = [deepcopy(record)]
            return deepcopy(record)

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return deepcopy(self._cases.get(case_id))

    def list_cases(
        self,
        page: int = 1,
        page_size: int = 20,
        tag: Optional[str] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[Dict[str, Any]], int]:
        with self._lock:
            cases = list(self._cases.values())

            if tag:
                cases = [c for c in cases if tag in c.get("tags", [])]
            if priority:
                cases = [c for c in cases if c.get("priority") == priority]
            if search:
                search_lower = search.lower()
                cases = [
                    c
                    for c in cases
                    if search_lower in c.get("name", "").lower()
                    or search_lower in c.get("description", "").lower()
                ]

            # 按更新时间倒序
            cases.sort(key=lambda c: c.get("updated_at", ""), reverse=True)

            total = len(cases)
            start = (page - 1) * page_size
            end = start + page_size
            return deepcopy(cases[start:end]), total

    def update_case(self, case_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self._lock:
            existing = self._cases.get(case_id)
            if existing is None:
                return None
            existing = deepcopy(existing)
            for key, value in data.items():
                if value is not None:
                    existing[key] = value
            existing["version"] += 1
            existing["updated_at"] = datetime.now(timezone.utc)
            self._cases[case_id] = existing
            if case_id not in self._case_versions:
                self._case_versions[case_id] = []
            self._case_versions[case_id].append(deepcopy(existing))
            return deepcopy(existing)

    def delete_case(self, case_id: str) -> bool:
        with self._lock:
            if case_id in self._cases:
                del self._cases[case_id]
                self._case_versions.pop(case_id, None)
                return True
            return False

    def list_case_versions(self, case_id: str) -> list[Dict[str, Any]]:
        with self._lock:
            return deepcopy(self._case_versions.get(case_id, []))

    # ── Suites ─────────────────────────────────────────

    def create_suite(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            record = deepcopy(data)
            record["created_at"] = datetime.now(timezone.utc)
            record["updated_at"] = datetime.now(timezone.utc)
            self._suites[record["id"]] = record
            return deepcopy(record)

    def get_suite(self, suite_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return deepcopy(self._suites.get(suite_id))

    def list_suites(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[Dict[str, Any]], int]:
        with self._lock:
            suites = sorted(
                self._suites.values(),
                key=lambda s: s.get("updated_at", ""),
                reverse=True,
            )
            total = len(suites)
            start = (page - 1) * page_size
            end = start + page_size
            return deepcopy(suites[start:end]), total

    def update_suite(self, suite_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self._lock:
            existing = self._suites.get(suite_id)
            if existing is None:
                return None
            existing = deepcopy(existing)
            for key, value in data.items():
                if value is not None:
                    existing[key] = value
            existing["updated_at"] = datetime.now(timezone.utc)
            self._suites[suite_id] = existing
            return deepcopy(existing)

    def delete_suite(self, suite_id: str) -> bool:
        with self._lock:
            if suite_id in self._suites:
                del self._suites[suite_id]
                return True
            return False

    # ── Executions ─────────────────────────────────────

    def create_execution(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            record = deepcopy(data)
            record["created_at"] = datetime.now(timezone.utc)
            self._executions[record["id"]] = record
            return deepcopy(record)

    def get_execution(self, exec_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return deepcopy(self._executions.get(exec_id))

    def update_execution(self, exec_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新执行记录的部分字段（线程安全）"""
        with self._lock:
            existing = self._executions.get(exec_id)
            if existing is None:
                return None
            existing.update(deepcopy(updates))
            return deepcopy(existing)

    def list_executions(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[Dict[str, Any]], int]:
        with self._lock:
            executions = sorted(
                self._executions.values(),
                key=lambda e: e.get("created_at", ""),
                reverse=True,
            )
            total = len(executions)
            start = (page - 1) * page_size
            end = start + page_size
            return deepcopy(executions[start:end]), total

    # ── Reports ────────────────────────────────────────

    def get_report(self, exec_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return deepcopy(self._reports.get(exec_id))

    def save_report(self, exec_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            record = deepcopy(data)
            self._reports[exec_id] = record
            return deepcopy(record)

    def list_reports(
        self, page: int = 1, page_size: int = 20, env: Optional[str] = None
    ) -> tuple[list[Dict[str, Any]], int]:
        with self._lock:
            reports = list(self._reports.values())
            if env:
                reports = [r for r in reports if r.get("env") == env]
            reports.sort(key=lambda r: r.get("created_at", ""), reverse=True)
            total = len(reports)
            start = (page - 1) * page_size
            end = start + page_size
            return deepcopy(reports[start:end]), total


# ==================== 全局单例 ====================

_store: InMemoryStore | None = None
_store_lock = threading.Lock()


def get_store() -> InMemoryStore:
    """获取全局 InMemoryStore 单例"""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = InMemoryStore()
    return _store


def reset_store() -> None:
    """重置存储（仅用于测试）"""
    global _store
    with _store_lock:
        _store = InMemoryStore()


# ==================== 数据库会话（报告模块） ====================

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_db_lock = threading.Lock()


def _init_db() -> None:
    """懒初始化数据库引擎与会话工厂。

    从配置文件和 AUTOTEST_DB_URL 环境变量读取数据库连接。
    线程安全的单次初始化。
    """
    global _engine, _session_factory

    dsn_override = os.environ.get("AUTOTEST_DB_URL")
    if dsn_override:
        # 使用环境变量覆盖的 DSN
        engine = create_async_engine(
            {"dsn": dsn_override, "driver": "auto"},
            echo=False,
        )
    else:
        loader = ConfigLoader()
        project_config, _ = loader.load()
        engine = create_async_engine(project_config.db, echo=False)

    _engine = engine
    _session_factory = create_async_session_factory(engine)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：为每个请求提供异步数据库会话。

    会话在请求结束时自动关闭，异常时自动回滚。
    """
    global _session_factory
    if _session_factory is None:
        with _db_lock:
            if _session_factory is None:
                _init_db()

    assert _session_factory is not None
    async with _session_factory() as session:
        try:
            yield session
        except Exception:  # 必须捕获任意异常以执行回滚（FastAPI 依赖安全模式）
            await session.rollback()
            raise
        finally:
            await session.close()


def create_independent_session() -> AsyncSession:
    """创建独立数据库会话（用于后台 asyncio.Task，非请求范围）。

    与 get_db_session 不同，此函数不使用 FastAPI 依赖注入模式。
    返回的 session 由调用方负责 commit / rollback / close。
    不会自动回滚或关闭 — 请确保在 try/finally 中处理。
    注意：此函数为同步函数（async_sessionmaker() 调用本身不需要 await），
    调用时无需 await。

    Usage:
        session = create_independent_session()
        try:
            # ... database operations ...
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    """
    global _session_factory
    if _session_factory is None:
        with _db_lock:
            if _session_factory is None:
                _init_db()

    assert _session_factory is not None
    return _session_factory()


# ==================== Runner 工厂（T2-7 异步执行支持） ====================

_runner_cache: dict[str, TestRunner] = {}
_runner_cache_lock = threading.Lock()
_log = Logger.get("api.dependencies")


def _run_async_query(coro: Any) -> Any:
    """在线程安全的前提下执行异步协程。

    自动检测当前是否在事件循环内，是则通过新线程执行，
    否则直接用 asyncio.run()。

    Args:
        coro: 待执行的协程对象。

    Returns:
        协程的返回值。
    """
    try:
        asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(asyncio.run, coro)
            return fut.result(timeout=10)
    except RuntimeError:
        return asyncio.run(coro)


async def _resolve_env_model(
    repo: Any,
    env_id: str | None,
    env_name: str | None,
) -> Any:
    """按 ID 或名称解析环境 ORM 模型。

    Args:
        repo: EnvironmentRepository 实例。
        env_id: 环境 ID 字符串。
        env_name: 环境名称。

    Returns:
        EnvironmentModel 或 None。
    """
    import uuid as _uuid

    if env_id:
        try:
            uid = _uuid.UUID(env_id)
            return await repo.get(uid)
        except ValueError:
            _log.warning("env_db_invalid_id", env_id=env_id)
            return None
    if env_name:
        return await repo.find_by_name(env_name)
    return None


def _try_load_env_from_db(
    env_id: str | None = None,
    env_name: str | None = None,
) -> EnvConfig | None:
    """从数据库加载环境配置，转换为 EnvConfig。

    优先按 env_id 精确查询，其次按 env_name 查询。
    线程安全，可在同步/异步任意上下文中调用。

    Args:
        env_id: 环境 UUID 字符串（可选，优先级高于 env_name）。
        env_name: 环境名称（可选）。

    Returns:
        EnvConfig 或 None（DB 未命中/连接失败时返回 None）。
    """
    async def _query() -> EnvConfig | None:
        session = create_independent_session()
        try:
            from framework.persistence.repositories.environment_repo import (
                EnvironmentRepository,
            )

            repo = EnvironmentRepository(session)
            model = await _resolve_env_model(repo, env_id, env_name)
            if model is None:
                return None

            _log.debug(
                "env_db_lookup",
                env_name=model.name,
                has_base_url=bool(model.base_url),
                var_count=len(model.variables) if model.variables else 0,
            )
            return EnvConfig(
                name=model.name,
                base_url=model.base_url or "",
                ws_url=model.ws_url or "",
                variables=model.variables or {},
                http=model.http_config or {},
            )
        except Exception as exc:
            _log.warning(
                "env_db_query_failed",
                error=str(exc),
                env_id=env_id,
                env_name=env_name,
            )
            return None
        finally:
            await session.close()

    return _run_async_query(_query())


def create_runner(
    env_name: str = "dev",
    environment_id: str | None = None,
) -> TestRunner:
    """创建 TestRunner 实例（含 AsyncHttpClient 支持）

    环境加载优先级（DB 优先、文件兜底）：
    1. 若传入 environment_id → 从 DB 查询环境 → 构建 EnvConfig
    2. 若传入 env_name → 先按名称查 DB → 命中则用 DB 数据，未命中回退 YAML
    3. 若都未传 → ConfigLoader 使用默认环境（YAML）

    通过缓存复用 runner 实例（按环境隔离），避免每次执行都重新创建连接池。

    Args:
        env_name: 环境名称（dev/staging/production 等），DB 命中时可作为回退名称。
        environment_id: 数据库中的环境 UUID，优先使用。

    Returns:
        已配置的 TestRunner 实例。
    """
    global _runner_cache

    # 缓存 key 优先用传入的环境 ID/名称
    cache_key = environment_id or env_name

    with _runner_cache_lock:
        if cache_key in _runner_cache:
            _log.debug("runner_cache_hit", cache_key=cache_key)
            return _runner_cache[cache_key]

        # ── DB 环境加载（优先） ──
        env_config: EnvConfig | None = None
        if environment_id or env_name:
            env_config = _try_load_env_from_db(
                env_id=environment_id,
                env_name=env_name if not environment_id else None,
            )
            if env_config:
                _log.info(
                    "env_loaded_from_db",
                    env_name=env_config.name,
                    cache_key=cache_key,
                )

        # ── YAML 环境加载（兜底） ──
        project_config: ProjectConfig
        if env_config is None:
            loader = ConfigLoader()
            project_config, env_config = loader.load(env_name)
            _log.info(
                "env_loaded_from_yaml",
                env_name=env_config.name,
                cache_key=cache_key,
            )
        else:
            # DB 命中后仍需从 YAML 加载 project_config（全局配置）
            loader = ConfigLoader()
            project_config, _ = loader.load(env_config.name or env_name)

        # 创建同步 HTTP 客户端
        http_client = HttpClient(
            config=project_config.http, base_url=env_config.base_url
        )

        # 创建异步 HTTP 客户端
        async_http_client = AsyncHttpClient(
            config=project_config.http, base_url=env_config.base_url
        )

        # 创建 DB 管理器（可选）
        db_manager = DBConnectionManager()

        # 创建 runner（注入异步客户端）
        runner = TestRunner(
            config=project_config,
            env=env_config,
            http_client=http_client,
            db_manager=db_manager,
            async_http_client=async_http_client,
            report_adapter=NoopReportAdapter(),
        )

        _runner_cache[cache_key] = runner
        _log.info(
            "runner_created",
            env=env_config.name,
            cache_key=cache_key,
            base_url=env_config.base_url,
        )
        return runner


def invalidate_runner_cache(env_name: str | None = None) -> None:
    """清除 runner 缓存（配置热加载时调用）

    Args:
        env_name: 指定环境名，为 None 时清除全部
    """
    global _runner_cache
    with _runner_cache_lock:
        if env_name is None:
            _runner_cache.clear()
        elif env_name in _runner_cache:
            # 关闭旧客户端释放连接
            runner = _runner_cache.pop(env_name)
            try:
                runner._http_client.close()
            except OSError:
                pass
            try:
                # AsyncHttpClient 的关闭需要在事件循环中执行，
                # 这里仅从缓存中移除，由下次 GC 处理
                pass
            except Exception:
                pass


def parse_yaml_case(yaml_content: str) -> TestCase:
    """将 YAML 内容字符串解析为 TestCase 对象

    支持两种格式：
    1. 完整套件格式（含 cases 列表）— 取第一个 case
    2. 单用例格式（直接是 case 定义）— 直接解析

    Args:
        yaml_content: YAML 格式的测试用例内容

    Returns:
        解析后的 TestCase 对象

    Raises:
        ValueError: 无法解析时抛出
    """
    raw = yaml.safe_load(yaml_content)
    if not isinstance(raw, dict):
        raise ValueError("YAML 内容格式错误（应为字典）")

    parser = YAMLParser()

    # 情况 1: 完整套件格式 — 取第一个 case
    if "cases" in raw:
        # 构建最小化 suite 结构
        from framework.parser_models import ParsedCase, ParsedSuite

        parsed_suite = ParsedSuite(
            name=raw.get("name", "API Execution"),
            base_url=raw.get("base_url", ""),
            variables=raw.get("variables", {}),
        )
        cases_raw = raw.get("cases", [])
        if not cases_raw:
            raise ValueError("套件中没有定义用例 (cases 为空)")
        first_case_raw = cases_raw[0]
        parsed_case = parser._to_parsed_case(first_case_raw, parsed_suite)
        return parser._convert_case(parsed_case, TestSuite(name=""))

    # 情况 2: 单用例格式
    from framework.parser_models import ParsedCase, ParsedSuite

    parsed_suite = ParsedSuite(name="Single Case Execution")
    parsed_case = parser._to_parsed_case(raw, parsed_suite)
    return parser._convert_case(parsed_case, TestSuite(name=""))
