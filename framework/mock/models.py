"""Mock 规则数据模型

定义 Mock 规则的数据结构和 URL 匹配逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import fnmatch


@dataclass
class MockRule:
    """Mock 规则定义

    Attributes:
        id: 规则唯一标识符。
        url_pattern: URL 匹配模式（支持通配符 *，如 "/api/users/*"）。
        method: HTTP 方法（GET/POST/PUT/DELETE/PATCH/ANY）。
        status_code: 响应状态码，默认 200。
        response_body: 响应体（dict 或字符串）。
        response_headers: 额外的响应头。
        description: 规则描述。
        enabled: 是否启用，默认 True。
        priority: 优先级（数值越大越先匹配），默认 0。
        delay_ms: 模拟延迟（毫秒），默认 0。
    """

    id: str
    url_pattern: str
    method: str = "ANY"
    status_code: int = 200
    response_body: dict[str, Any] | str | None = None
    response_headers: dict[str, str] = field(default_factory=dict)
    description: str = ""
    enabled: bool = True
    priority: int = 0
    delay_ms: int = 0

    def matches(self, request_path: str, request_method: str) -> bool:
        """检查此规则是否匹配给定的请求。

        Args:
            request_path: 请求路径（如 "/api/users/123"）。
            request_method: 请求方法（如 "POST"）。

        Returns:
            是否匹配。
        """
        if not self.enabled:
            return False

        if self.method != "ANY" and self.method.upper() != request_method.upper():
            return False

        return fnmatch.fnmatch(request_path, self.url_pattern)
