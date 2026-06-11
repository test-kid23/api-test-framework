"""上下文快照管理器

在执行失败时自动捕获三层变量状态（run/case/step）并持久化到 DB。
支持脱敏处理，不存储敏感字段（token/password 等）。

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

    Attributes:
        SENSITIVE_KEY_PATTERNS: 需要脱敏的字段名模式列表
    """

    SENSITIVE_KEY_PATTERNS: list[re.Pattern] = _SENSITIVE_KEY_PATTERNS

    def __init__(self, repo: ContextSnapshotRepository) -> None:
        """初始化.

        Args:
            repo: 快照 Repository
        """
        self._repo = repo

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

        Args:
            execution_id: 执行 ID

        Returns:
            快照对象或 None
        """
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
