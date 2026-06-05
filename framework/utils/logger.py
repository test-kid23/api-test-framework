"""日志工具 — 分级日志 + 文件轮转 + 彩色控制台 + 敏感数据脱敏"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from framework.utils.masker import SensitiveDataMasker

try:
    from loguru import logger as loguru_logger  # noqa: F401

    HAS_LOGURU = True
except ImportError:
    HAS_LOGURU = False


# 彩色日志颜色表
COLORS = {
    "DEBUG": "\033[36m",  # cyan
    "INFO": "\033[32m",  # green
    "WARNING": "\033[33m",  # yellow
    "ERROR": "\033[31m",  # red
    "CRITICAL": "\033[35m",  # magenta
}
RESET = "\033[0m"


class ColoredFormatter(logging.Formatter):
    """彩色控制台日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        levelname = record.levelname
        if levelname in COLORS:
            record.levelname = f"{COLORS[levelname]}{levelname:<8}{RESET}"
        return super().format(record)


class Logger:
    """日志管理器

    集成 SensitiveDataMasker，在日志输出前自动脱敏敏感字段。
    客户端代码可通过 Logger.mask_sensitive() 对数据进行脱敏后再写入日志。
    """

    _initialized = False
    _masker: SensitiveDataMasker | None = None
    _mask_enabled: bool = True

    @classmethod
    def setup(cls, config: dict[str, Any] | None = None) -> None:
        """初始化日志系统

        同时根据配置初始化敏感数据脱敏器。
        """
        if cls._initialized:
            return
        cls._initialized = True

        config = config or {}
        level = config.get("level", "INFO").upper()

        # --- 初始化脱敏器 ---
        cls._mask_enabled = config.get("mask_enabled", True)
        extra_fields: list[str] = config.get("sensitive_fields", [])
        if not isinstance(extra_fields, list):
            extra_fields = []
        cls._masker = SensitiveDataMasker(extra_fields=extra_fields)

        root_logger = logging.getLogger("framework")
        root_logger.setLevel(getattr(logging, level, logging.INFO))
        root_logger.handlers.clear()

        # 控制台处理器
        console_cfg = config.get("console", {})
        if console_cfg.get("enabled", True):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, level, logging.INFO))
            fmt = console_cfg.get("format", "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s")
            datefmt = console_cfg.get("datefmt", "%Y-%m-%d %H:%M:%S")
            if console_cfg.get("colorize", True):
                console_handler.setFormatter(ColoredFormatter(fmt, datefmt=datefmt))
            else:
                console_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
            root_logger.addHandler(console_handler)

        # 文件处理器
        file_cfg = config.get("file", {})
        if file_cfg.get("enabled", True):
            log_path = Path(file_cfg.get("path", "logs/test.log"))
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                str(log_path),
                maxBytes=file_cfg.get("max_bytes", 10 * 1024 * 1024),
                backupCount=file_cfg.get("backup_count", 5),
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            fmt = file_cfg.get(
                "format",
                "%(asctime)s [%(levelname)-8s] %(name)s [%(filename)s:%(lineno)d]: %(message)s",
            )
            file_handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
            root_logger.addHandler(file_handler)

        # 请求日志文件（独立）
        req_cfg = config.get("request_log", {})
        if req_cfg.get("enabled", True):
            req_path = Path(req_cfg.get("path", "logs/requests.log"))
            req_path.parent.mkdir(parents=True, exist_ok=True)
            req_handler = RotatingFileHandler(
                str(req_path),
                maxBytes=req_cfg.get("max_bytes", 10 * 1024 * 1024),
                backupCount=req_cfg.get("backup_count", 5),
                encoding="utf-8",
            )
            req_handler.setLevel(logging.DEBUG)
            req_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            req_logger = logging.getLogger("framework.client")
            req_logger.addHandler(req_handler)

    @classmethod
    def get(cls, name: str) -> logging.Logger:
        """获取指定名称的 logger"""
        return logging.getLogger(f"framework.{name}")

    @classmethod
    def mask_sensitive(cls, data: Any) -> Any:
        """对数据进行敏感信息脱敏

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
        """对文本进行敏感信息正则脱敏

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
