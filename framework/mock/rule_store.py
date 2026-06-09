"""Mock 规则存储 — 线程安全的内存存储器

支持注册、查询、删除、匹配规则。所有操作线程安全。
"""

from __future__ import annotations

import threading
import uuid
from typing import Any

from framework.mock.models import MockRule
from framework.utils.logger import Logger

logger = Logger.get("mock.store")


class MockRuleStore:
    """Mock 规则存储器（线程安全）

    提供规则的 CRUD 操作和请求匹配功能。
    支持按优先级排序 — 高优先级规则（priority 值大）优先匹配。

    Usage:
        store = MockRuleStore()
        store.register(
            url_pattern="/api/users/*",
            method="POST",
            status_code=201,
            response_body={"id": 1, "name": "test"},
        )
        rule = store.match("/api/users/123", "POST")
    """

    def __init__(self) -> None:
        self._rules: dict[str, MockRule] = {}
        self._lock = threading.RLock()

    # ── CRUD ───────────────────────────────────────────

    def register(
        self,
        url_pattern: str,
        method: str = "ANY",
        status_code: int = 200,
        response_body: dict[str, Any] | str | None = None,
        response_headers: dict[str, str] | None = None,
        description: str = "",
        priority: int = 0,
        delay_ms: int = 0,
        rule_id: str | None = None,
    ) -> MockRule:
        """注册一条 Mock 规则。

        Args:
            url_pattern: URL 匹配模式。
            method: HTTP 方法。
            status_code: 响应状态码。
            response_body: 响应体。
            response_headers: 响应头。
            description: 描述。
            priority: 优先级。
            delay_ms: 延迟毫秒。
            rule_id: 规则 ID（不传自动生成 UUID）。

        Returns:
            注册的 MockRule 对象。
        """
        rule = MockRule(
            id=rule_id or str(uuid.uuid4()),
            url_pattern=url_pattern,
            method=method.upper(),
            status_code=status_code,
            response_body=response_body,
            response_headers=response_headers or {},
            description=description,
            enabled=True,
            priority=priority,
            delay_ms=delay_ms,
        )
        with self._lock:
            self._rules[rule.id] = rule
        logger.info(
            "mock_rule_registered",
            rule_id=rule.id,
            url_pattern=url_pattern,
            method=method,
        )
        return rule

    def get(self, rule_id: str) -> MockRule | None:
        """按 ID 获取规则。

        Args:
            rule_id: 规则 ID。

        Returns:
            MockRule 或 None。
        """
        with self._lock:
            return self._rules.get(rule_id)

    def list_all(self) -> list[MockRule]:
        """列出所有规则（按优先级降序）。

        Returns:
            规则列表。
        """
        with self._lock:
            rules = list(self._rules.values())
            rules.sort(key=lambda r: (-r.priority, r.url_pattern))
            return rules

    def update(self, rule_id: str, **kwargs: Any) -> MockRule | None:
        """更新规则的部分字段。

        Args:
            rule_id: 规则 ID。
            **kwargs: 要更新的字段。

        Returns:
            更新后的 MockRule 或 None。
        """
        with self._lock:
            rule = self._rules.get(rule_id)
            if rule is None:
                return None

            for key, value in kwargs.items():
                if hasattr(rule, key) and value is not None:
                    setattr(rule, key, value)
            return rule

    def delete(self, rule_id: str) -> bool:
        """删除一条规则。

        Args:
            rule_id: 规则 ID。

        Returns:
            是否删除成功。
        """
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                logger.info("mock_rule_deleted", rule_id=rule_id)
                return True
            return False

    def clear(self) -> int:
        """清空所有规则。

        Returns:
            清除的规则数量。
        """
        with self._lock:
            count = len(self._rules)
            self._rules.clear()
            if count > 0:
                logger.info("mock_rules_cleared", count=count)
            return count

    def delete_by_ids(self, rule_ids: list[str]) -> int:
        """按 ID 列表批量删除规则。

        Args:
            rule_ids: 要删除的规则 ID 列表。

        Returns:
            删除的规则数量。
        """
        with self._lock:
            count = 0
            for rid in rule_ids:
                if rid in self._rules:
                    del self._rules[rid]
                    count += 1
            logger.info("mock_rules_batch_deleted", requested=len(rule_ids), deleted=count)
            return count

    # ── 匹配 ───────────────────────────────────────────

    def match(self, request_path: str, request_method: str) -> MockRule | None:
        """根据请求路径和方法匹配规则。

        按优先级降序匹配，同等优先级时按模式特异性降序（更精确的模式优先）。
        返回第一个匹配的规则。

        Args:
            request_path: 请求路径。
            request_method: 请求方法。

        Returns:
            匹配的 MockRule 或 None。
        """
        with self._lock:
            rules = sorted(
                self._rules.values(),
                key=lambda r: (-r.priority, -MockRuleStore._specificity(r.url_pattern)),
            )
            for rule in rules:
                if rule.matches(request_path, request_method):
                    logger.debug(
                        "mock_rule_matched",
                        rule_id=rule.id,
                        path=request_path,
                        method=request_method,
                    )
                    return rule
        return None

    @staticmethod
    def _specificity(pattern: str) -> int:
        """计算模式特异性分数（越高越精确）。

        精确匹配 > 前缀通配 > 后缀通配 > 全通配。
        分数 = (非通配字符数 * 100) - (星号数量 * 10)

        Examples:
            /api/users/999  → 150  (精确)
            /api/users/*    → 110  (后缀通配)
            /api/*          → 40   (宽泛)
            /*              → 0    (全通配)
        """
        star_count = pattern.count("*")
        weight = len(pattern.replace("*", ""))
        return weight * 100 - star_count * 10

    @property
    def rule_count(self) -> int:
        """当前规则数量"""
        with self._lock:
            return len(self._rules)


# ── 全局单例 ───────────────────────────────────────

_store: MockRuleStore | None = None
_store_lock = threading.Lock()


def get_mock_store() -> MockRuleStore:
    """获取全局 MockRuleStore 单例。

    Returns:
        全局共享的 MockRuleStore 实例。
    """
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = MockRuleStore()
    return _store


def reset_mock_store() -> None:
    """重置全局 Mock 存储（仅用于测试）。"""
    global _store
    with _store_lock:
        _store = MockRuleStore()
