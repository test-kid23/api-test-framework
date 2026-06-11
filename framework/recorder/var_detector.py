"""动态变量检测器 — 自动识别 HAR 请求中的动态字段

识别并标记 HAR 请求中的动态值（时间戳/UUID/token/signature 等），
供回放引擎在重放前替换为模板变量。

支持的检测模式：
- ISO 8601 时间戳（如 2024-01-15T10:30:00Z）
- UUID v4（如 550e8400-e29b-41d4-a716-446655440000）
- JWT token（三段 base64，以 eyJ 开头）
- Unix 时间戳（10-13 位数字）
- MD5/SHA 哈希（32/40/64 位 hex）
- 自定义正则模式（用户可配置）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ==================== 内置检测模式 ====================

# ISO 8601 时间戳
_ISO_TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)

# UUID v4
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)

# JWT token（三段 base64url，以 eyJ 开头）
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")

# Unix 时间戳（10 位秒级 或 13 位毫秒级，需在合理范围内）
_UNIX_TIMESTAMP_RE = re.compile(r"\b(?:1[3-9]\d{8}|[2-9]\d{9})(?:\d{3})?\b")

# MD5（32 位 hex）
_MD5_RE = re.compile(r"\b[a-fA-F0-9]{32}\b")

# SHA1（40 位 hex）
_SHA1_RE = re.compile(r"\b[a-fA-F0-9]{40}\b")

# SHA256（64 位 hex）
_SHA256_RE = re.compile(r"\b[a-fA-F0-9]{64}\b")

# 签名类参数名模式（key 匹配时值为动态）
_SIGNATURE_PARAM_NAMES = {
    "sign", "signature", "sig", "token", "access_token",
    "api_key", "apikey", "secret", "nonce", "timestamp",
    "ts", "t", "_t", "request_id", "trace_id", "traceid",
    "x-trace-id", "x-request-id",
}


# ==================== 数据结构 ====================


@dataclass
class DetectedVar:
    """检测到的动态变量。

    Attributes:
        original_value: 原始值。
        location: 位置类型（url_path / query_param / header / body）。
        key: 参数名或键名（如 query_param 的 name，header 的 name）。
        template: 推荐的模板变量名，如 {{ $timestamp }}。
        pattern_name: 匹配的检测模式名。
        start: 在原始字符串中的起始位置（-1 表示整个值）。
        end: 在原始字符串中的结束位置（-1 表示整个值）。
    """

    original_value: str
    location: str
    key: str = ""
    template: str = ""
    pattern_name: str = ""
    start: int = -1
    end: int = -1


# ==================== 检测器 ====================


class VarDetector:
    """动态变量检测器。

    对 HAR 请求的 URL、查询参数、请求头、请求体进行扫描，
    自动识别动态字段并生成模板变量替换建议。

    使用方式::

        detector = VarDetector()
        vars = detector.detect_url("https://api.example.com/users?ts=1715328000")
        for v in vars:
            print(f"{v.key} → {v.template}")

    可扩展：通过 add_pattern() 注册自定义检测规则。

    Attributes:
        custom_patterns: 用户自定义的检测模式列表。
    """

    def __init__(self) -> None:
        self.custom_patterns: list[tuple[str, re.Pattern[str], str]] = []
        """自定义模式列表: [(name, regex, template_name), ...]"""

    def add_pattern(self, name: str, regex: str, template: str) -> None:
        """注册自定义检测模式。

        Args:
            name: 模式名称（用于标识）。
            regex: 正则表达式字符串。
            template: 推荐的模板变量名，如 "{{ $custom_var }}"。

        Raises:
            re.error: 正则表达式无效。
        """
        compiled = re.compile(regex)
        self.custom_patterns.append((name, compiled, template))

    # ── 公共检测方法 ──────────────────────────────────

    def detect_url(self, url: str) -> list[DetectedVar]:
        """检测 URL 路径和查询参数中的动态值。

        Args:
            url: 完整 URL 字符串。

        Returns:
            检测到的动态变量列表。
        """
        from urllib.parse import parse_qs, urlparse

        results: list[DetectedVar] = []

        parsed = urlparse(url)

        # 检测查询参数
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            for key, values in params.items():
                for val in values:
                    detected = self._detect_value(val, location="query_param", key=key)
                    results.extend(detected)

                    # 签名类参数名检测
                    if key.lower() in _SIGNATURE_PARAM_NAMES:
                        results.append(
                            DetectedVar(
                                original_value=val,
                                location="query_param",
                                key=key,
                                template=f"{{{{ ${key} }}}}",
                                pattern_name="signature_param_name",
                            )
                        )

        return results

    def detect_headers(self, headers: dict[str, str]) -> list[DetectedVar]:
        """检测请求头中的动态值。

        Args:
            headers: 请求头字典。

        Returns:
            检测到的动态变量列表。
        """
        results: list[DetectedVar] = []

        # 需要检查动态值的头部名称
        dynamic_header_names = {
            "authorization", "x-api-key", "x-auth-token",
            "cookie", "set-cookie", "x-csrf-token", "x-xsrf-token",
        }

        for key, val in headers.items():
            if key.lower() in dynamic_header_names:
                # Authorization: Bearer <token>
                if key.lower() == "authorization" and val.lower().startswith("bearer "):
                    token = val[7:]
                    results.append(
                        DetectedVar(
                            original_value=token,
                            location="header",
                            key=key,
                            template="{{ $auth_token }}",
                            pattern_name="bearer_token",
                        )
                    )
                else:
                    results.append(
                        DetectedVar(
                            original_value=val,
                            location="header",
                            key=key,
                            template=f"{{{{ $header_{_sanitize_key(key)} }}}}",
                            pattern_name="dynamic_header_name",
                        )
                    )
                continue

            # 对头部值进行模式检测
            detected = self._detect_value(val, location="header", key=key)
            results.extend(detected)

        return results

    def detect_body(self, body: Any, path: str = "") -> list[DetectedVar]:
        """递归检测请求体中的动态值。

        支持 JSON dict/list/str 类型。

        Args:
            body: 请求体（dict / list / str / 其他）。
            path: 当前 JSON 路径（用于嵌套结构的 key 标识）。

        Returns:
            检测到的动态变量列表。
        """
        results: list[DetectedVar] = []

        if isinstance(body, dict):
            for key, val in body.items():
                child_path = f"{path}.{key}" if path else key
                if isinstance(val, str):
                    detected = self._detect_value(val, location="body", key=child_path)
                    results.extend(detected)

                    # 签名类 key 名检测
                    if key.lower() in _SIGNATURE_PARAM_NAMES:
                        results.append(
                            DetectedVar(
                                original_value=val,
                                location="body",
                                key=child_path,
                                template=f"{{{{ ${key} }}}}",
                                pattern_name="signature_param_name",
                            )
                        )
                elif isinstance(val, (dict, list)):
                    results.extend(self.detect_body(val, path=child_path))

        elif isinstance(body, list):
            for i, item in enumerate(body):
                child_path = f"{path}[{i}]"
                if isinstance(item, str):
                    detected = self._detect_value(item, location="body", key=child_path)
                    results.extend(detected)
                elif isinstance(item, (dict, list)):
                    results.extend(self.detect_body(item, path=child_path))

        elif isinstance(body, str):
            detected = self._detect_value(body, location="body", key=path)
            results.extend(detected)

        return results

    def detect_entry(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        query_params: dict[str, str] | None = None,
        body: Any = None,
    ) -> list[DetectedVar]:
        """对一个完整请求条目进行综合检测。

        Args:
            url: 请求 URL。
            headers: 请求头字典。
            query_params: 查询参数字典。
            body: 请求体。

        Returns:
            检测到的所有动态变量列表（去重）。
        """
        results: list[DetectedVar] = []

        results.extend(self.detect_url(url))

        if headers:
            results.extend(self.detect_headers(headers))

        if query_params:
            for key, val in query_params.items():
                detected = self._detect_value(str(val), location="query_param", key=key)
                results.extend(detected)

        if body is not None:
            results.extend(self.detect_body(body))

        # 去重（按 (location, key, original_value) 去重）
        seen: set[tuple[str, str, str]] = set()
        unique: list[DetectedVar] = []
        for v in results:
            sig = (v.location, v.key, v.original_value)
            if sig not in seen:
                seen.add(sig)
                unique.append(v)

        return unique

    # ── 私有方法 ──────────────────────────────────────

    def _detect_value(
        self, value: str, location: str, key: str = ""
    ) -> list[DetectedVar]:
        """对单个字符串值进行模式匹配。

        Args:
            value: 待检测的字符串值。
            location: 位置类型。
            key: 参数名。

        Returns:
            匹配到的动态变量列表。
        """
        if not value or not isinstance(value, str):
            return []

        results: list[DetectedVar] = []

        # 内置模式
        builtin_patterns: list[tuple[str, re.Pattern[str], str]] = [
            ("jwt_token", _JWT_RE, "{{ $token }}"),
            ("uuid_v4", _UUID_RE, "{{ $uuid }}"),
            ("iso_timestamp", _ISO_TIMESTAMP_RE, "{{ $timestamp }}"),
            ("sha256_hash", _SHA256_RE, "{{ $hash_sha256 }}"),
            ("sha1_hash", _SHA1_RE, "{{ $hash_sha1 }}"),
            ("md5_hash", _MD5_RE, "{{ $hash_md5 }}"),
        ]

        for pattern_name, pattern_re, template in builtin_patterns:
            for match in pattern_re.finditer(value):
                results.append(
                    DetectedVar(
                        original_value=match.group(0),
                        location=location,
                        key=key,
                        template=template,
                        pattern_name=pattern_name,
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # Unix 时间戳（需额外验证范围合理性）
        for match in _UNIX_TIMESTAMP_RE.finditer(value):
            ts_val = match.group(0)
            try:
                ts_int = int(ts_val)
                # 2000-01-01 ~ 2100-01-01 的合理范围
                if 946684800 <= (ts_int // 1000 if len(ts_val) == 13 else ts_int) <= 4102444800:
                    results.append(
                        DetectedVar(
                            original_value=ts_val,
                            location=location,
                            key=key,
                            template="{{ $unix_timestamp }}",
                            pattern_name="unix_timestamp",
                            start=match.start(),
                            end=match.end(),
                        )
                    )
            except (ValueError, OverflowError):
                pass

        # 自定义模式
        for pattern_name, pattern_re, template in self.custom_patterns:
            for match in pattern_re.finditer(value):
                results.append(
                    DetectedVar(
                        original_value=match.group(0),
                        location=location,
                        key=key,
                        template=template,
                        pattern_name=pattern_name,
                        start=match.start(),
                        end=match.end(),
                    )
                )

        return results

    def generate_replacements(
        self, detected_vars: list[DetectedVar]
    ) -> dict[str, str]:
        """根据检测结果生成替换映射。

        Args:
            detected_vars: detect_entry() 的返回结果。

        Returns:
            {原始值: 模板变量} 的映射字典。
        """
        replacements: dict[str, str] = {}
        for var in detected_vars:
            if var.original_value not in replacements:
                replacements[var.original_value] = var.template
        return replacements


# ==================== 工具函数 ====================


def _sanitize_key(key: str) -> str:
    """将 header/param 名称转为安全的变量名。

    Args:
        key: 原始键名。

    Returns:
        安全变量名（小写，连字符替换为下划线）。
    """
    return key.lower().replace("-", "_").replace(" ", "_")
