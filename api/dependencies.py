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


def create_runner(env_name: str = "dev") -> TestRunner:
    """创建 TestRunner 实例（含 AsyncHttpClient 支持）

    通过缓存复用 runner 实例（按环境隔离），避免每次执行都重新创建连接池。

    Args:
        env_name: 环境名称（dev/staging/production）

    Returns:
        已配置的 TestRunner 实例，同时包含同步 HttpClient 和异步 AsyncHttpClient
    """
    global _runner_cache

    with _runner_cache_lock:
        if env_name in _runner_cache:
            return _runner_cache[env_name]

        # 加载配置
        loader = ConfigLoader()
        project_config, env_config = loader.load(env_name)

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

        _runner_cache[env_name] = runner
        _log.info("runner_created", env=env_name)
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
