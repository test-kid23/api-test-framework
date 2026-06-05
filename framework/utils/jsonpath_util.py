"""JSONPath 工具 — 基于 jsonpath-ng 的封装"""

from __future__ import annotations

from typing import Any

from jsonpath_ng import parse as jsonpath_parse
from jsonpath_ng.ext import parse as jsonpath_ext_parse


def extract_value(body: Any, path: str) -> Any:
    """从 JSON 对象中提取 JSONPath 路径对应的值

    支持扩展语法，如 $.data.list[0].id
    """
    try:
        expr = jsonpath_ext_parse(path)
        matches = expr.find(body)
        if matches:
            return matches[0].value
        return None
    except Exception:
        # 回退到基础语法
        try:
            expr = jsonpath_parse(path)
            matches = expr.find(body)
            if matches:
                return matches[0].value
        except Exception:
            pass
        return None


def extract_all(body: Any, path: str) -> list[Any]:
    """提取所有匹配的值"""
    try:
        expr = jsonpath_ext_parse(path)
        return [m.value for m in expr.find(body)]
    except Exception:
        return []
