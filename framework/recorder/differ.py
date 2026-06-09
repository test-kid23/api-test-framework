"""结构化差异计算引擎

对回放过程中的请求/响应对进行比较，生成三级差异报告：
- 状态码差异
- 响应头差异（对比指定或全部关键头）
- 响应体差异（结构化对比，支持 JSON）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DiffSeverity(str, Enum):
    """差异严重级别"""

    INFO = "info"        # 信息性差异（不阻塞）
    WARNING = "warning"  # 警告级差异
    ERROR = "error"      # 错误级差异（不匹配）


@dataclass
class DiffResult:
    """单条差异项

    Attributes:
        path: 差异定位路径（如 status、headers.content-type、body.id）。
        severity: 严重级别。
        recorded: 录制时的值。
        actual: 实际回放时的值。
        message: 差异描述。
    """

    path: str
    severity: DiffSeverity
    recorded: Any
    actual: Any
    message: str = ""

    @property
    def is_error(self) -> bool:
        return self.severity == DiffSeverity.ERROR

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "severity": self.severity.value,
            "recorded": _serialize_value(self.recorded),
            "actual": _serialize_value(self.actual),
            "message": self.message,
        }


@dataclass
class DiffReport:
    """完整差异报告

    Attributes:
        entry_index: HAR 条目在文件中的序号（0-based）。
        url: 请求 URL。
        method: HTTP 方法。
        matched: 是否完全匹配（无 ERROR 级差异）。
        diffs: 差异详情列表。
        summary: 人类可读的摘要文字。
    """

    entry_index: int = 0
    url: str = ""
    method: str = ""
    matched: bool = True
    diffs: list[DiffResult] = field(default_factory=list)
    summary: str = ""

    @property
    def diff_count(self) -> int:
        return len(self.diffs)

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.diffs if d.is_error)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_index": self.entry_index,
            "url": self.url,
            "method": self.method,
            "matched": self.matched,
            "summary": self.summary,
            "diff_count": self.diff_count,
            "error_count": self.error_count,
            "diffs": [d.to_dict() for d in self.diffs],
        }


class DiffEngine:
    """结构化差异计算引擎

    三级比较策略：
    1. 状态码: 精确匹配，不匹配为 ERROR
    2. 响应头: 对比指定的关键头列表，不匹配为 WARNING
    3. 响应体: JSON 结构深度对比（逐字段），不匹配为 ERROR

    Attributes:
        compare_headers: 需对比的响应头列表（为空则对比全部头）。
        ignore_headers: 忽略的响应头列表（如 date、server、x-request-id）。
        ignore_body_keys: 忽略的 JSON 响应体字段列表（如 timestamp、traceId）。
        strict_mode: 严格模式（逐字段精确匹配），False 时允许实际响应包含额外字段。
    """

    # 默认忽略的响应头（每次请求都会变化的值）
    DEFAULT_IGNORE_HEADERS: frozenset[str] = frozenset({
        "date",
        "server",
        "x-request-id",
        "x-trace-id",
        "x-amzn-requestid",
        "x-amzn-trace-id",
        "x-powered-by",
        "set-cookie",
        "etag",
        "last-modified",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "cf-ray",
        "x-cache",
        "via",
        "age",
        "connection",
    })

    def __init__(
        self,
        compare_headers: list[str] | None = None,
        ignore_headers: list[str] | None = None,
        ignore_body_keys: list[str] | None = None,
        strict_mode: bool = False,
    ) -> None:
        """初始化差异引擎。

        Args:
            compare_headers: 需要对比的响应头列表（为空则对比全部）。列表模式时仅对比指定的头。
            ignore_headers: 忽略的响应头列表。默认忽略 date/server/x-request-id 等时效性头。
            ignore_body_keys: 忽略的 JSON 响应体键列表。
            strict_mode: 严格模式，所有字段都必须匹配。
        """
        self.compare_headers = set(h.lower() for h in (compare_headers or []))
        self.ignore_headers = (
            set(h.lower() for h in ignore_headers)
            if ignore_headers is not None
            else set(h.lower() for h in self.DEFAULT_IGNORE_HEADERS)
        )
        self.ignore_body_keys = set(ignore_body_keys or [])
        self.strict_mode = strict_mode

    def compare(
        self,
        entry_index: int,
        url: str,
        method: str,
        recorded_status: int,
        actual_status: int,
        recorded_headers: dict[str, str],
        actual_headers: dict[str, str],
        recorded_body: Any,
        actual_body: Any,
    ) -> DiffReport:
        """对单次请求-响应执行完整差异比较。

        Args:
            entry_index: 条目序号。
            url: 请求 URL。
            method: HTTP 方法。
            recorded_status: 录制时的状态码。
            actual_status: 回放时的状态码。
            recorded_headers: 录制时的响应头。
            actual_headers: 回放时的响应头。
            recorded_body: 录制时的响应体。
            actual_body: 回放时的响应体。

        Returns:
            DiffReport 差异报告。
        """
        diffs: list[DiffResult] = []

        # Level 1: 状态码对比
        diffs.extend(self._compare_status(recorded_status, actual_status))

        # Level 2: 响应头对比
        diffs.extend(
            self._compare_headers(recorded_headers, actual_headers)
        )

        # Level 3: 响应体对比
        diffs.extend(
            self._compare_body(recorded_body, actual_body)
        )

        matched = all(
            d.severity != DiffSeverity.ERROR for d in diffs
        )

        # 生成摘要
        err_count = sum(1 for d in diffs if d.is_error)
        warn_count = sum(1 for d in diffs if d.severity == DiffSeverity.WARNING)

        parts: list[str] = []
        if matched:
            parts.append("✅ 完全匹配")
            if warn_count > 0:
                parts.append(f"({warn_count} 个警告)")
        else:
            parts.append(f"❌ 不匹配 - {err_count} 个错误")
            if warn_count > 0:
                parts.append(f", {warn_count} 个警告")

        return DiffReport(
            entry_index=entry_index,
            url=url,
            method=method,
            matched=matched,
            diffs=diffs,
            summary=" ".join(parts),
        )

    # ---------- 私有方法 ----------

    def _compare_status(
        self, recorded: int, actual: int
    ) -> list[DiffResult]:
        """比较状态码。"""
        if recorded != actual:
            return [
                DiffResult(
                    path="status_code",
                    severity=DiffSeverity.ERROR,
                    recorded=recorded,
                    actual=actual,
                    message=f"状态码不匹配: 录制 {recorded}, 实际 {actual}",
                )
            ]
        return []

    def _compare_headers(
        self,
        recorded: dict[str, str],
        actual: dict[str, str],
    ) -> list[DiffResult]:
        """比较响应头。"""
        diffs: list[DiffResult] = []

        # 规范化键
        recorded_normalized: dict[str, str] = {
            k.lower(): v for k, v in recorded.items()
        }
        actual_normalized: dict[str, str] = {
            k.lower(): v for k, v in actual.items()
        }

        # 确定要比较的头列表
        if self.compare_headers:
            keys_to_check = self.compare_headers
        else:
            all_keys = set(recorded_normalized.keys()) | set(actual_normalized.keys())
            keys_to_check = all_keys - self.ignore_headers

        for key in sorted(keys_to_check):
            rec_val = recorded_normalized.get(key)
            act_val = actual_normalized.get(key)

            if rec_val != act_val:
                severity = DiffSeverity.WARNING
                if key == "content-type":
                    severity = DiffSeverity.ERROR

                diffs.append(
                    DiffResult(
                        path=f"headers.{key}",
                        severity=severity,
                        recorded=rec_val,
                        actual=act_val,
                        message=f"响应头 '{key}' 不匹配",
                    )
                )

        return diffs

    def _compare_body(
        self, recorded: Any, actual: Any
    ) -> list[DiffResult]:
        """比较响应体。"""
        diffs: list[DiffResult] = []

        # 类型不一致
        if type(recorded) is not type(actual):
            return [
                DiffResult(
                    path="body",
                    severity=DiffSeverity.ERROR,
                    recorded=f"{type(recorded).__name__}: {_serialize_value(recorded)}",
                    actual=f"{type(actual).__name__}: {_serialize_value(actual)}",
                    message=f"响应体类型不匹配: {type(recorded).__name__} vs {type(actual).__name__}",
                )
            ]

        # 字符串直接比较
        if isinstance(recorded, str):
            if recorded != actual:
                diffs.append(
                    DiffResult(
                        path="body",
                        severity=DiffSeverity.ERROR,
                        recorded=recorded[:500],
                        actual=str(actual)[:500] if actual else "",
                        message="响应体文本不匹配",
                    )
                )
            return diffs

        # 字典（JSON）深度比较
        if isinstance(recorded, dict) and isinstance(actual, dict):
            return self._compare_dict(recorded, actual, "body")

        # 列表
        if isinstance(recorded, list) and isinstance(actual, list):
            if len(recorded) != len(actual):
                diffs.append(
                    DiffResult(
                        path="body",
                        severity=DiffSeverity.ERROR,
                        recorded=f"list(len={len(recorded)})",
                        actual=f"list(len={len(actual)})",
                        message=f"响应体数组长度不匹配: {len(recorded)} vs {len(actual)}",
                    )
                )
            for i in range(min(len(recorded), len(actual))):
                diffs.extend(
                    self._compare_body_element(
                        recorded[i], actual[i], f"body[{i}]"
                    )
                )
            return diffs

        # 其他类型直接比较
        if recorded != actual:
            diffs.append(
                DiffResult(
                    path="body",
                    severity=DiffSeverity.ERROR,
                    recorded=_serialize_value(recorded),
                    actual=_serialize_value(actual),
                    message="响应体值不匹配",
                )
            )

        return diffs

    def _compare_dict(
        self,
        recorded: dict[str, Any],
        actual: dict[str, Any],
        path_prefix: str,
    ) -> list[DiffResult]:
        """递归比较两个字典。"""
        diffs: list[DiffResult] = []

        rec_keys = set(recorded.keys())
        act_keys = set(actual.keys())

        # 在 strict 模式下报告缺少的键
        if self.strict_mode:
            missing_in_actual = rec_keys - act_keys
            for key in sorted(missing_in_actual):
                if key in self.ignore_body_keys:
                    continue
                diffs.append(
                    DiffResult(
                        path=f"{path_prefix}.{key}",
                        severity=DiffSeverity.ERROR,
                        recorded=recorded[key],
                        actual="<missing>",
                        message=f"键 '{key}' 在录制中存在但回放中缺失",
                    )
                )

        # 比较共有键
        common_keys = rec_keys & act_keys
        for key in sorted(common_keys):
            if key in self.ignore_body_keys:
                continue

            rec_val = recorded[key]
            act_val = actual[key]
            current_path = f"{path_prefix}.{key}"

            rec_type = type(rec_val)
            act_type = type(act_val)

            if rec_type is not act_type:
                diffs.append(
                    DiffResult(
                        path=current_path,
                        severity=DiffSeverity.ERROR,
                        recorded=_serialize_value(rec_val),
                        actual=_serialize_value(act_val),
                        message=f"字段 '{key}' 类型不匹配: {rec_type.__name__} vs {act_type.__name__}",
                    )
                )
            elif isinstance(rec_val, dict):
                diffs.extend(self._compare_dict(rec_val, act_val, current_path))
            elif isinstance(rec_val, list):
                diffs.extend(self._compare_list(rec_val, act_val, current_path))
            elif rec_val != act_val:
                diffs.append(
                    DiffResult(
                        path=current_path,
                        severity=DiffSeverity.ERROR,
                        recorded=_serialize_value(rec_val),
                        actual=_serialize_value(act_val),
                        message=f"字段 '{key}' 值不匹配",
                    )
                )

        return diffs

    def _compare_list(
        self,
        recorded: list[Any],
        actual: list[Any],
        path_prefix: str,
    ) -> list[DiffResult]:
        """比较两个列表。"""
        diffs: list[DiffResult] = []

        if len(recorded) != len(actual):
            diffs.append(
                DiffResult(
                    path=path_prefix,
                    severity=DiffSeverity.ERROR,
                    recorded=f"len={len(recorded)}",
                    actual=f"len={len(actual)}",
                    message=f"数组长度不匹配: {len(recorded)} vs {len(actual)}",
                )
            )

        for i in range(min(len(recorded), len(actual))):
            diffs.extend(
                self._compare_body_element(
                    recorded[i], actual[i], f"{path_prefix}[{i}]"
                )
            )

        return diffs

    def _compare_body_element(
        self, recorded: Any, actual: Any, path: str
    ) -> list[DiffResult]:
        """比较单个元素（列表项或嵌套值）。"""
        if isinstance(recorded, dict) and isinstance(actual, dict):
            return self._compare_dict(recorded, actual, path)
        if isinstance(recorded, list) and isinstance(actual, list):
            return self._compare_list(recorded, actual, path)
        if recorded != actual:
            return [
                DiffResult(
                    path=path,
                    severity=DiffSeverity.ERROR,
                    recorded=_serialize_value(recorded),
                    actual=_serialize_value(actual),
                    message=f"值不匹配",
                )
            ]
        return []


def _serialize_value(value: Any) -> Any:
    """安全序列化值（预处理复杂类型）。"""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, dict)):
        return value
    return str(value)
