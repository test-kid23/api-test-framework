"""YAML 解析中间模型 — 承载原始 YAML 结构，仅在 parser 内部使用

设计意图：
- 将 YAML 特有的数据结构（如 raw dict、source_file/line_number）隔离在此层。
- parser 内部使用 ParsedSuite / ParsedCase 描述 YAML 原始形态，
  再转换为 models.py 中干净的领域模型（TestCase / TestSuite）。
- 这些类型不对 parser 外部暴露。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedCase:
    """YAML 解析后的单个用例原始结构 — 仅在 parser 内部使用"""

    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    priority: str = "P1"
    skip: bool = False
    skip_if: str = ""
    variables: dict[str, Any] = field(default_factory=dict)
    request: dict[str, Any] | None = None
    ws_config: dict[str, Any] | None = None
    grpc: dict[str, Any] | None = None
    expect: dict[str, Any] = field(default_factory=dict)
    extract: dict[str, Any] = field(default_factory=dict)
    db_assert: list[dict[str, Any]] = field(default_factory=list)
    setup: list[dict[str, Any] | str] = field(default_factory=list)
    teardown: list[dict[str, Any] | str] = field(default_factory=list)
    # ── YAML 特有元信息 ──
    source_file: str = ""
    line_number: int = 0


@dataclass
class ParsedSuite:
    """YAML 解析后的套件原始结构 — 仅在 parser 内部使用"""

    name: str
    description: str = ""
    base_url: str = ""
    tags: list[str] = field(default_factory=list)
    priority: str = "P1"
    variables: dict[str, Any] = field(default_factory=dict)
    setup: list[dict[str, Any] | str] = field(default_factory=list)
    teardown: list[dict[str, Any] | str] = field(default_factory=list)
    cases: list[ParsedCase] = field(default_factory=list)
    data_driven: list[dict[str, Any]] = field(default_factory=list)
    # ── YAML 特有元信息 ──
    source_file: str = ""
