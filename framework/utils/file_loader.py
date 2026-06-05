"""文件加载工具 — 支持 @file: 语法"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from framework.utils.logger import Logger

logger = Logger.get("file_loader")


def load_file_ref(ref: str, base_dir: str = ".") -> Path:
    """解析 @file:path 语法，返回文件路径

    Args:
        ref: 文件引用，如 "@file:./test_data/sample.pdf"
        base_dir: 基准目录

    Returns:
        解析后的 Path 对象
    """
    if ref.startswith("@file:"):
        file_path = ref[6:]  # 去掉 @file: 前缀
    else:
        file_path = ref

    path = Path(base_dir) / file_path
    if not path.exists():
        logger.warning(f"文件不存在: {path}")
    return path


def is_file_ref(value: Any) -> bool:
    """判断是否为文件引用"""
    return isinstance(value, str) and value.startswith("@file:")


def load_file_content(file_path: Path) -> bytes:
    """读取文件内容为 bytes"""
    return file_path.read_bytes()
