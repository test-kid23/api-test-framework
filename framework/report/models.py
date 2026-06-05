"""报告数据模型 — 统一报告接口所需的数据结构

本模块定义报告适配器使用的标准化数据模型。
AssertionReport / AssertResult / HttpRequest / HttpResponse 等
核心模型复用 framework.models 中的定义，此处仅做重导出和补充。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# 从 framework.models 重导出核心模型，作为报告层的统一入口
from framework.models import (
    AssertionReport,
    AssertResult,
    EnvConfig,
    HttpMethod,
    HttpRequest,
    HttpResponse,
)


# ==================== 报告专用枚举 ====================


class ReportAdapterType(str, Enum):
    """报告适配器类型枚举"""

    ALLURE = "allure"
    HTML = "html"
    NOOP = "noop"


# ==================== 报告步骤模型（rich report） ====================


@dataclass
class ReportStep:
    """报告中的一个步骤 / 附件条目"""

    name: str
    content: str
    attachment_type: str = "text"  # text | json | html

    def __str__(self) -> str:
        return f"[{self.attachment_type}] {self.name}: {self.content[:80]}..."


@dataclass
class ReportContext:
    """报告级别的上下文信息"""

    environment: str = ""
    base_url: str = ""
    tags: list[str] = field(default_factory=list)
    priority: str = "P1"
    steps: list[ReportStep] = field(default_factory=list)

    def add_step(self, step: ReportStep) -> None:
        self.steps.append(step)

    def clear(self) -> None:
        self.steps.clear()


__all__ = [
    "AssertionReport",
    "AssertResult",
    "EnvConfig",
    "HttpMethod",
    "HttpRequest",
    "HttpResponse",
    "ReportAdapterType",
    "ReportContext",
    "ReportStep",
]
