"""上下文快照管理器

在执行失败时自动捕获三层变量状态（run/case/step）并持久化到 DB。
支持脱敏处理，不存储敏感字段（token/password 等）。

T5-12: 新增 Redis 缓存层 — 每个 step 结束时自动缓存快照到 Redis（1h TTL），
执行结束后持久化到 DB。Redis 不可用时自动降级为仅存内存。

Attributes:
    ContextSnapshot: 不可变快照对象
    ContextSnapshotManager: 快照管理器
"""

from __future__ import annotations

import json
import re
import traceback as tb
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from framework.persistence.models.context_snapshot import ContextSnapshotModel
from framework.utils.logger import Logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from framework.context import TestContext
    from framework.persistence.repositories.context_snapshot_repo import (
        ContextSnapshotRepository,
    )

_log = Logger.get("context_snapshot")

# 需要脱敏的字段名模式（不区分大小写）
_SENSITIVE_KEY_PATTERNS: list[re.Pattern] = [
    re.compile(r".*token.*", re.IGNORECASE),
    re.compile(r".*password.*", re.IGNORECASE),
    re.compile(r".*secret.*", re.IGNORECASE),
    re.compile(r".*api_key.*", re.IGNORECASE),
    re.compile(r".*apikey.*", re.IGNORECASE),
    re.compile(r".*authorization.*", re.IGNORECASE),
    re.compile(r".*credential.*", re.IGNORECASE),
]

_MASKED_VALUE = "***REDACTED***"


@dataclass(frozen=True)
class ContextSnapshot:
    """不可变上下文快照.

    Attributes:
        execution_id: 关联执行 ID
        step_index: 失败步骤索引
        run_vars: 运行级变量（不可变映射）
        case_vars: 用例级变量（不可变映射）
        step_vars: 步骤级变量（不可变映射）
        error_message: 失败信息
        traceback: 完整堆栈
    """

    execution_id: str
    step_index: int
    run_vars: MappingProxyType[str, object]
    case_vars: MappingProxyType[str, object]
    step_vars: MappingProxyType[str, object]
    error_message: str
    traceback: str


def _is_sensitive_key(key: str) -> bool:
    """判断键名是否为敏感字段.

    Args:
        key: 字段名

    Returns:
        是否为敏感字段
    """
    return any(pattern.match(key) for pattern in _SENSITIVE_KEY_PATTERNS)


def _mask_sensitive_vars(vars_dict: dict[str, Any]) -> dict[str, Any]:
    """对变量字典中的敏感字段进行脱敏.

    Args:
        vars_dict: 原始变量字典

    Returns:
        脱敏后的变量字典（浅拷贝）
    """
    if not vars_dict:
        return {}
    return {
        k: _MASKED_VALUE if _is_sensitive_key(k) else _safe_serialize(v)
        for k, v in vars_dict.items()
    }


def _safe_serialize(value: Any) -> Any:
    """安全序列化值，处理不可 JSON 序列化的对象.

    Args:
        value: 任意值

    Returns:
        JSON 安全的表示
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_serialize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe_serialize(v) for k, v in value.items()}
    # 其他类型转为字符串
    try:
        return str(value)
    except Exception:
        return f"<{type(value).__name__}>"


class ContextSnapshotManager:
    """上下文快照管理器.

    在执行失败时自动捕获三层变量状态并持久化到 DB。
    支持 Redis 缓存层（T5-12）：每个 step 结束时缓存快照到 Redis，
    Redis 不可用时自动降级为仅存内存。

    Attributes:
        SENSITIVE_KEY_PATTERNS: 需要脱敏的字段名模式列表
        REDIS_CACHE_TTL: Redis 缓存过期时间（秒），默认 3600s（1h）
    """

    SENSITIVE_KEY_PATTERNS: list[re.Pattern] = _SENSITIVE_KEY_PATTERNS
    REDIS_CACHE_TTL: int = 3600
    _REDIS_KEY_PREFIX: str = "autotest:snapshot:"

    def __init__(
        self,
        repo: ContextSnapshotRepository,
        redis_client: Redis | None = None,
    ) -> None:
        """初始化.

        Args:
            repo: 快照 Repository
            redis_client: Redis 异步客户端（可选，用于缓存快照）。
                          为 None 时仅使用 DB 持久化。
        """
        self._repo = repo
        self._redis = redis_client
        self._redis_available: bool | None = None  # None = 未检测

    async def capture_on_failure(
        self,
        execution_id: uuid.UUID,
        step_index: int,
        test_context: TestContext,
        error: Exception,
    ) -> ContextSnapshot:
        """失败时捕获快照并持久化.

        从 TestContext 提取三层变量状态，脱敏处理后写入 DB。

        Args:
            execution_id: 执行 ID
            step_index: 失败步骤索引
            test_context: 测试上下文（含三层变量）
            error: 异常对象

        Returns:
            ContextSnapshot: 不可变快照对象
        """
        # 提取三层变量
        all_vars = test_context.get_all_variables() if hasattr(test_context, "get_all_variables") else {}
        run_vars_raw = test_context.get_suite_vars() if hasattr(test_context, "get_suite_vars") else {}
        case_vars_raw = test_context.get_case_vars() if hasattr(test_context, "get_case_vars") else {}
        step_vars_raw = test_context.get_step_vars() if hasattr(test_context, "get_step_vars") else {}

        # 脱敏
        run_vars_masked = _mask_sensitive_vars(run_vars_raw)
        case_vars_masked = _mask_sensitive_vars(case_vars_raw)
        step_vars_masked = _mask_sensitive_vars(step_vars_raw)

        error_msg = str(error)
        error_tb = "".join(tb.format_exception(type(error), error, error.__traceback__))

        # 持久化到 DB
        model = ContextSnapshotModel(
            execution_id=execution_id,
            step_index=step_index,
            run_vars=run_vars_masked,
            case_vars=case_vars_masked,
            step_vars=step_vars_masked,
            error_message=error_msg,
            traceback=error_tb,
        )
        self._repo._session.add(model)
        await self._repo._session.flush()

        _log.info(
            "snapshot_captured",
            execution_id=str(execution_id),
            step_index=step_index,
            error=error_msg[:200],
        )

        return ContextSnapshot(
            execution_id=str(execution_id),
            step_index=step_index,
            run_vars=MappingProxyType(run_vars_masked),
            case_vars=MappingProxyType(case_vars_masked),
            step_vars=MappingProxyType(step_vars_masked),
            error_message=error_msg,
            traceback=error_tb,
        )

    async def get_snapshot(self, execution_id: uuid.UUID) -> ContextSnapshot | None:
        """查询快照.

        优先从 Redis 缓存读取，未命中时回退 DB 查询。

        Args:
            execution_id: 执行 ID

        Returns:
            快照对象或 None
        """
        # 优先 Redis 缓存
        cached = await self.get_cached_snapshot(str(execution_id))
        if cached is not None:
            return cached

        # 回退 DB
        model = await self._repo.get_by_execution(execution_id)
        if model is None:
            return None

        return ContextSnapshot(
            execution_id=str(model.execution_id),
            step_index=model.step_index,
            run_vars=MappingProxyType(model.run_vars),
            case_vars=MappingProxyType(model.case_vars),
            step_vars=MappingProxyType(model.step_vars),
            error_message=model.error_message,
            traceback=model.traceback or "",
        )

    # ── Redis 缓存方法 (T5-12) ────────────────────────

    async def cache_step_snapshot(
        self,
        execution_id: str,
        step_index: int,
        run_vars: dict[str, Any],
        case_vars: dict[str, Any],
        step_vars: dict[str, Any],
    ) -> None:
        """将步骤快照缓存到 Redis（1h TTL）。

        每个 step 结束时自动调用，将当前三层变量状态写入 Redis。
        Redis 不可用时静默降级，不影响正常执行流程。

        Args:
            execution_id: 执行 ID 字符串。
            step_index: 步骤索引。
            run_vars: 运行级变量（原始）。
            case_vars: 用例级变量（原始）。
            step_vars: 步骤级变量（原始）。
        """
        if self._redis is None:
            return

        if not await self._ensure_redis_available():
            return

        try:
            # 脱敏后缓存
            snapshot_data = {
                "execution_id": execution_id,
                "step_index": step_index,
                "run_vars": _mask_sensitive_vars(run_vars),
                "case_vars": _mask_sensitive_vars(case_vars),
                "step_vars": _mask_sensitive_vars(step_vars),
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }

            key = f"{self._REDIS_KEY_PREFIX}{execution_id}"
            await self._redis.set(
                key,
                json.dumps(snapshot_data, default=str),
                ex=self.REDIS_CACHE_TTL,
            )

            _log.debug(
                "step_snapshot_cached",
                execution_id=execution_id,
                step_index=step_index,
            )
        except Exception as e:
            _log.debug(
                "step_snapshot_cache_failed",
                execution_id=execution_id,
                error=str(e),
            )

    async def get_cached_snapshot(self, execution_id: str) -> ContextSnapshot | None:
        """从 Redis 获取缓存的快照。

        Args:
            execution_id: 执行 ID 字符串。

        Returns:
            快照或 None（缓存未命中/Redis 不可用）。
        """
        if self._redis is None:
            return None

        if not await self._ensure_redis_available():
            return None

        try:
            key = f"{self._REDIS_KEY_PREFIX}{execution_id}"
            raw = await self._redis.get(key)
            if raw is None:
                return None

            data = json.loads(raw)
            return ContextSnapshot(
                execution_id=data["execution_id"],
                step_index=data["step_index"],
                run_vars=MappingProxyType(data.get("run_vars", {})),
                case_vars=MappingProxyType(data.get("case_vars", {})),
                step_vars=MappingProxyType(data.get("step_vars", {})),
                error_message="",
                traceback="",
            )
        except Exception as e:
            _log.debug(
                "cached_snapshot_read_failed",
                execution_id=execution_id,
                error=str(e),
            )
            return None

    async def _ensure_redis_available(self) -> bool:
        """检查 Redis 是否可用（带缓存检测结果）。

        Returns:
            True 表示 Redis 可用。
        """
        if self._redis is None:
            return False

        if self._redis_available is not None:
            return self._redis_available

        try:
            await self._redis.ping()
            self._redis_available = True
            return True
        except Exception as e:
            _log.warning(
                "redis_unavailable_snapshot_degraded",
                error=str(e),
            )
            self._redis_available = False
            return False
