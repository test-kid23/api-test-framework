"""依赖注入 — 数据存储、配置、公共服务

当前 Phase 2 第一阶段使用内存存储（InMemoryStore）。
Phase 2 T2-2 完成后将替换为 SQLAlchemy AsyncSession。
"""

from __future__ import annotations

import threading
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from api.schemas.case import CaseResponse


# ==================== 内存数据存储 ====================


class InMemoryStore:
    """线程安全的内存数据存储

    用于 Phase 2 第一阶段的无 DB 开发阶段。
    T2-2 完成后替换为 SQLAlchemy Repository 实现。
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
