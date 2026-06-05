"""结构化日志 — 基于 structlog 的统一日志系统

==== 设计要点 ====
- 使用 structlog.stdlib.ProcessorFormatter 实现控制台/文件双渲染：
  - 控制台：彩色 ConsoleRenderer（开发调试）
  - 文件：JSONRenderer（便于 jq / 日志平台解析）
- 日志格式通过 config.yaml → logging.format 控制：
  - console：控制台彩色输出
  - json：全局 JSON 输出
- trace_id 通过 structlog.contextvars.bind_contextvars 自动附加，
  在用例边界调用 set_trace_id() / clear_trace_id() 切换。
- 完全移除 loguru 依赖，统一到 structlog + stdlib logging。
- 保持 Logger.setup() / Logger.get() / Logger.mask_sensitive() 接口兼容。

==== 使用示例 ====
    # 初始化
    Logger.setup({"level": "INFO", "format": "console"})

    # 获取 logger（兼容旧接口，返回 structlog BoundLogger）
    logger = Logger.get("runner")

    # 传统字符串日志（向后兼容）
    logger.info("套件开始执行")

    # 结构化日志（推荐）
    logger.info("suite_started", suite_name=name, case_count=10)

    # trace_id 管理
    set_trace_id("test_login")
    logger.info("case_started")  # 自动包含 trace_id
    clear_trace_id()
"""

from __future__ import annotations

import logging
import sys
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog
from structlog.stdlib import ProcessorFormatter

from framework.utils.masker import SensitiveDataMasker


# ═══════════════════════════════════════════════════════════════
# Trace ID 管理
# ═══════════════════════════════════════════════════════════════


def set_trace_id(case_name: str) -> str:
    """为当前上下文设置 trace_id，绑定到 structlog 上下文变量。

    应在每个用例开始时调用，用例结束后调用 clear_trace_id()。

    Args:
        case_name: 用例名称

    Returns:
        trace_id 字符串，格式为 {case_name}-{uuid_hex8}
    """
    trace_id = f"{case_name}-{uuid.uuid4().hex[:8]}"
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    return trace_id


def clear_trace_id() -> None:
    """清除当前 structlog 上下文的 trace_id。"""
    try:
        structlog.contextvars.unbind_contextvars("trace_id")
    except KeyError:
        pass


# ═══════════════════════════════════════════════════════════════
# Structlog 处理器
# ═══════════════════════════════════════════════════════════════


def _drop_colorama(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """从 event_dict 中移除 colorama（防止格式化器因 colorama 崩溃）"""
    event_dict.pop("colorama", None)
    return event_dict


def _ensure_trace_id(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """兜底：确保 event_dict 中至少有一个 trace_id。"""
    if "trace_id" not in event_dict:
        event_dict["trace_id"] = str(uuid.uuid4())[:8]
    return event_dict


def _json_fallback(obj: Any) -> Any:
    """JSON 序列化兜底：将不可序列化对象转为字符串。"""
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    try:
        return str(obj)
    except Exception:
        return f"<unserializable:{type(obj).__name__}>"


# ═══════════════════════════════════════════════════════════════
# Shared processor chain（structlog 入口处理器）
# ═══════════════════════════════════════════════════════════════

_SHARED_PROCESSORS: list[Any] = [
    # 合并 contextvars 中的上下文（trace_id 等）
    structlog.contextvars.merge_contextvars,
    # 添加日志级别
    structlog.stdlib.add_log_level,
    # 添加 logger 名称
    structlog.stdlib.add_logger_name,
    # 时间戳
    structlog.processors.TimeStamper(fmt="iso", utc=False),
    # 确保 trace_id
    _ensure_trace_id,
    # 移除 colorama（避免干扰）
    _drop_colorama,
    # 堆栈信息（仅 ERROR 及以上）
    structlog.processors.format_exc_info,
    # 委托给 ProcessorFormatter（支持按 handler 分别渲染）
    structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
]

# 供文件 handler 的 foreign_pre_chain 使用（非 structlog 日志的前处理）
_FOREIGN_PRE_CHAIN: list[Any] = [
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=False),
    _ensure_trace_id,
]


# ═══════════════════════════════════════════════════════════════
# Logger 类
# ═══════════════════════════════════════════════════════════════


class Logger:
    """日志管理器 — 基于 structlog 的结构化日志。

    特性：
    - 双输出：控制台彩色（开发）+ 文件 JSON（解析）
    - 每条日志自动附加 trace_id
    - 兼容原有 Logger.get() / Logger.setup() / Logger.mask_sensitive() 接口
    - 敏感数据脱敏（委托给 SensitiveDataMasker）

    通过 config.yaml 控制格式和级别：
        logging:
          level: INFO              # DEBUG|INFO|WARNING|ERROR
          format: console          # console|json
          console:
            enabled: true
            colorize: true
          file:
            enabled: true
            path: logs/test.log
    """

    _initialized = False
    _masker: SensitiveDataMasker | None = None
    _mask_enabled: bool = True

    @classmethod
    def setup(cls, config: dict[str, Any] | None = None) -> None:
        """初始化 structlog + stdlib logging 双引擎。

        幂等：多次调用仅首次生效。
        """
        if cls._initialized:
            return
        cls._initialized = True

        config = config or {}
        level_name: str = config.get("level", "INFO").upper()
        log_format: str = config.get("format", "console")
        cls._mask_enabled = config.get("mask_enabled", True)

        # ── 脱敏器 ──
        extra_fields: list[str] = config.get("sensitive_fields", [])
        if not isinstance(extra_fields, list):
            extra_fields = []
        cls._masker = SensitiveDataMasker(extra_fields=extra_fields)

        level = getattr(logging, level_name, logging.INFO)

        # ── 渲染器选择 ──
        if log_format == "json":
            console_processor: Any = structlog.processors.JSONRenderer(
                serializer=lambda obj, **kw: _json_handler(obj)
            )
        else:
            console_processor = structlog.dev.ConsoleRenderer(colors=True)

        file_processor: Any = structlog.processors.JSONRenderer(
            serializer=lambda obj, **kw: _json_handler(obj)
        )

        # ── 配置 structlog ──
        structlog.configure(
            processors=_SHARED_PROCESSORS,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            cache_logger_on_first_use=True,
        )

        # ── stdlib logging handlers ──
        root_logger = logging.getLogger("framework")
        root_logger.setLevel(level)
        root_logger.handlers.clear()

        # 控制台 handler
        console_cfg: dict[str, Any] = config.get("console", {})
        if console_cfg.get("enabled", True):
            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(level)
            ch.setFormatter(
                ProcessorFormatter(
                    processor=console_processor,
                )
            )
            root_logger.addHandler(ch)

        # 文件 handler（始终 JSON）
        file_cfg: dict[str, Any] = config.get("file", {})
        if file_cfg.get("enabled", True):
            log_path = Path(file_cfg.get("path", "logs/test.log"))
            log_path.parent.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(
                str(log_path),
                maxBytes=file_cfg.get("max_bytes", 10 * 1024 * 1024),
                backupCount=file_cfg.get("backup_count", 5),
                encoding="utf-8",
            )
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(
                ProcessorFormatter(
                    processor=file_processor,
                    foreign_pre_chain=_FOREIGN_PRE_CHAIN,
                )
            )
            root_logger.addHandler(fh)

        # 请求日志（独立文件，JSON 格式）
        req_cfg: dict[str, Any] = config.get("request_log", {})
        if req_cfg.get("enabled", True):
            req_path = Path(req_cfg.get("path", "logs/requests.log"))
            req_path.parent.mkdir(parents=True, exist_ok=True)
            rh = RotatingFileHandler(
                str(req_path),
                maxBytes=req_cfg.get("max_bytes", 10 * 1024 * 1024),
                backupCount=req_cfg.get("backup_count", 5),
                encoding="utf-8",
            )
            rh.setLevel(logging.DEBUG)
            rh.setFormatter(
                ProcessorFormatter(
                    processor=file_processor,
                    foreign_pre_chain=_FOREIGN_PRE_CHAIN,
                )
            )
            req_logger = logging.getLogger("framework.client")
            req_logger.handlers.clear()
            req_logger.propagate = False
            req_logger.addHandler(rh)

    @classmethod
    def get(cls, name: str) -> structlog.stdlib.BoundLogger:
        """获取 structlog BoundLogger。

        返回的 logger 支持两种调用方式：
        - 传统字符串: logger.info("hello")
        - 结构化: logger.info("event_name", key1=val1, key2=val2)
        """
        return structlog.get_logger(f"framework.{name}")

    @classmethod
    def is_debug_enabled(cls, name: str = "framework") -> bool:
        """检查 DEBUG 级别是否启用（替代原 isEnabledFor(10) 模式）。

        用于条件性地执行昂贵的日志数据准备。
        """
        return logging.getLogger(name).isEnabledFor(logging.DEBUG)

    # ── 敏感数据脱敏（与原有接口完全兼容）──

    @classmethod
    def mask_sensitive(cls, data: Any) -> Any:
        """对数据进行敏感信息脱敏。

        如果脱敏未初始化或已禁用，返回原始数据。
        支持 dict、list[dict]、str 类型。

        Args:
            data: 待脱敏的数据。

        Returns:
            脱敏后的数据。
        """
        if not cls._mask_enabled or cls._masker is None:
            return data
        return cls._masker.mask_dict(data)

    @classmethod
    def mask_sensitive_str(cls, text: str) -> str:
        """对文本进行敏感信息正则脱敏。

        如果脱敏未初始化或已禁用，返回原始文本。

        Args:
            text: 待脱敏的文本字符串。

        Returns:
            脱敏后的文本。
        """
        if not cls._mask_enabled or cls._masker is None:
            return text
        return cls._masker.mask_string(text)

    @classmethod
    def _get_masker(cls) -> SensitiveDataMasker | None:
        """获取当前脱敏器实例（供内部使用）"""
        return cls._masker


# ═══════════════════════════════════════════════════════════════
# JSON 序列化辅助
# ═══════════════════════════════════════════════════════════════

import json as _json


def _json_handler(obj: Any) -> str:
    """structlog JSONRenderer 的 serializer 回调。

    使用标准 json.dumps 并指定 default 兜底。
    """
    return _json.dumps(obj, default=_json_fallback, ensure_ascii=False)
