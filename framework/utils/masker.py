"""敏感数据脱敏工具 — 日志输出时自动遮蔽 token、password 等敏感字段

纯 Python 实现，无外部依赖。对外暴露 SensitiveDataMasker 类。
"""

from __future__ import annotations

import re
from typing import Any


class SensitiveDataMasker:
    """敏感数据脱敏器

    用于在日志输出前自动遮蔽敏感字段的值。
    支持字典递归遍历和文本正则替换两种模式。

    Attributes:
        DEFAULT_SENSITIVE_FIELDS: 内置默认脱敏字段（大小写不敏感）。
        _fields: 合并后的完整脱敏字段集合（小写形式）。
    """

    DEFAULT_SENSITIVE_FIELDS: list[str] = [
        "authorization",
        "password",
        "token",
        "secret",
        "api_key",
        "cookie",
        "set-cookie",
        "access_token",
        "refresh_token",
        "apikey",
    ]

    MASK_PLACEHOLDER: str = "******"

    def __init__(self, extra_fields: list[str] | None = None) -> None:
        """初始化脱敏器

        Args:
            extra_fields: 用户自定义的额外脱敏字段名列表。
                          与 DEFAULT_SENSITIVE_FIELDS 合并，大小写不敏感。
        """
        defaults = {f.lower() for f in self.DEFAULT_SENSITIVE_FIELDS}
        extras = {f.lower() for f in (extra_fields or [])}
        self._fields: set[str] = defaults | extras

    # ------------------------------------------------------------------
    # 公有方法
    # ------------------------------------------------------------------

    def mask_dict(self, data: Any) -> Any:
        """递归遮蔽字典中的敏感字段值

        遍历字典的所有层级，将 key 名匹配敏感字段的 value
        替换为 MASK_PLACEHOLDER。

        Args:
            data: 待脱敏的数据。支持 dict、list[dict]、以及其他类型。

        Returns:
            脱敏后的数据（结构不变，敏感值被替换）。

        Raises:
            不抛出异常：无法处理的类型原样返回。
        """
        if isinstance(data, dict):
            return self._mask_dict_inner(data)
        if isinstance(data, list):
            return [self.mask_dict(item) for item in data]
        return data

    def mask_string(self, text: str) -> str:
        """对文本中的敏感字段值进行正则替换

        匹配常见模式并替换为占位符：
         - ``Bearer <token>``   → ``Bearer ****``
         - ``Basic <cred>``    → ``Basic ****``
         - ``"key": "value"``  → ``"key": "******"``
         - ``key=value``       → ``key=******``
         - ``key: value``      → ``key: ******``

        Args:
            text: 待脱敏的文本字符串。

        Returns:
            脱敏后的文本。

        Raises:
            不抛出异常：非字符串类型原样返回。
        """
        if not isinstance(text, str):
            return text

        result = text

        # Authorization 有专用格式，从通用字段集中排除
        _auth_field = "authorization"
        non_auth_fields = sorted(
            (f for f in self._fields if f != _auth_field),
            key=len,
            reverse=True,
        )

        # 1) JSON 样式: "field": "value" 或 "field":"value"
        for field in non_auth_fields:
            field_escaped = re.escape(field)
            result = re.sub(
                rf'["\']?({field_escaped})["\']?\s*[:=]\s*["\'][^"\']*["\']',
                rf'"\1": "{self.MASK_PLACEHOLDER}"',
                result,
                flags=re.IGNORECASE,
            )

        # 2) key=value 或 key: value (不带引号的值)
        for field in non_auth_fields:
            field_escaped = re.escape(field)
            result = re.sub(
                rf'(?<![="\'])({field_escaped})(?:\s*[:=]\s*)(\S+)',
                rf"\1={self.MASK_PLACEHOLDER}",
                result,
                flags=re.IGNORECASE,
            )

        # 3) Authorization 头 (专用格式，独立处理)
        result = re.sub(
            r"(Authorization:\s*)(Bearer|Basic|Digest)\s+\S+",
            rf"\1\2 {self.MASK_PLACEHOLDER}",
            result,
            flags=re.IGNORECASE,
        )

        return result

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------

    @property
    def fields(self) -> set[str]:
        """返回当前生效的敏感字段集合（只读）"""
        return self._fields.copy()

    @property
    def placeholder(self) -> str:
        """返回当前占位符字符串"""
        return self.MASK_PLACEHOLDER

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _is_sensitive_key(self, key: Any) -> bool:
        """判断字典 key 是否为敏感字段（大小写不敏感）"""
        if not isinstance(key, str):
            return False
        return key.lower() in self._fields

    def _mask_dict_inner(self, data: dict[Any, Any]) -> dict[Any, Any]:
        """递归处理字典（内部实现）"""
        result: dict[Any, Any] = {}
        for key, value in data.items():
            if self._is_sensitive_key(key):
                # None 值视为无数据，保持原样
                result[key] = value if value is None else self.MASK_PLACEHOLDER
            elif isinstance(value, dict):
                result[key] = self._mask_dict_inner(value)
            elif isinstance(value, list):
                result[key] = [
                    self._mask_dict_inner(item) if isinstance(item, dict) else self.mask_dict(item)
                    for item in value
                ]
            else:
                result[key] = value
        return result
