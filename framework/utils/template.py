"""Jinja2 模板引擎 — 变量替换 + 内置函数"""

from __future__ import annotations

import base64
import hashlib
import os
import time
import uuid
from datetime import datetime
from typing import Any

import jinja2


class TemplateEngine:
    """基于 Jinja2 的变量替换引擎

    语法: {{variable_name}}
    支持嵌套: {{env.base_url}}
    支持函数: {{timestamp()}}, {{uuid4()}}
    """

    def __init__(self) -> None:
        self._env = jinja2.Environment(
            undefined=jinja2.Undefined,
            keep_trailing_newline=True,
        )
        self._env.globals.update(
            {
                "timestamp": self._timestamp,
                "timestamp_ms": self._timestamp_ms,
                "uuid4": self._uuid4,
                "random_int": self._random_int,
                "random_string": self._random_string,
                "base64_encode": self._base64_encode,
                "base64_decode": self._base64_decode,
                "md5": self._md5,
                "sha256": self._sha256,
                "now": self._now,
                "env_var": self._env_var,
            }
        )

    # ---------- 公共 API ----------

    def render(self, template_str: str, variables: dict[str, Any]) -> str:
        """替换字符串中的所有 {{变量}}"""
        if not isinstance(template_str, str):
            return str(template_str)
        if "{{" not in template_str:
            return template_str
        try:
            tpl = self._env.from_string(template_str)
            result: str = tpl.render(**variables)
            return result
        except jinja2.TemplateError:
            return template_str

    def render_dict(self, data: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
        """递归替换字典中所有字符串值"""
        result: dict[str, Any] = {}
        for key, value in data.items():
            new_key = self.render(key, variables) if isinstance(key, str) else key
            result[new_key] = self.render_value(value, variables)
        return result

    def render_value(self, value: Any, variables: dict[str, Any]) -> Any:
        """替换任意值（字符串替换，其他类型原样返回）"""
        if isinstance(value, str):
            return self.render(value, variables)
        if isinstance(value, dict):
            return self.render_dict(value, variables)
        if isinstance(value, list):
            return [self.render_value(item, variables) for item in value]
        return value

    # ---------- 内置函数 ----------

    @staticmethod
    def _timestamp() -> int:
        return int(time.time())

    @staticmethod
    def _timestamp_ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def _uuid4() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _random_int(min_val: int = 0, max_val: int = 999999) -> int:
        import random

        return random.randint(min_val, max_val)

    @staticmethod
    def _random_string(length: int = 10) -> str:
        import random
        import string

        return "".join(random.choices(string.ascii_letters, k=length))

    @staticmethod
    def _base64_encode(text: str) -> str:
        return base64.b64encode(text.encode()).decode()

    @staticmethod
    def _base64_decode(encoded: str) -> str:
        return base64.b64decode(encoded.encode()).decode()

    @staticmethod
    def _md5(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    @staticmethod
    def _sha256(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    @staticmethod
    def _now(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        return datetime.now().strftime(fmt)

    @staticmethod
    def _env_var(key: str, default: str = "") -> str:
        return os.environ.get(key, default)
