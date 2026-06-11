"""提取器管道 — 支持声明式链式提取步骤

支持将多个提取步骤串联为一个管道，每步的输出作为下一步的输入：
    jsonpath → regex → base64_decode → json_parse

Usage:
    pipeline = ExtractPipeline(steps=[
        ExtractStep(type=ExtractStepType.JSONPATH, expression="$.data.token"),
        ExtractStep(type=ExtractStepType.BASE64_DECODE),
    ])
    result = pipeline.execute(response_body)
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from framework.exceptions import AutoTestException
from framework.utils.jsonpath_util import extract_value


class ExtractStepType(str, Enum):
    """提取步骤类型."""

    JSONPATH = "jsonpath"
    REGEX = "regex"
    BASE64_DECODE = "base64_decode"
    BASE64_ENCODE = "base64_encode"
    JSON_PARSE = "json_parse"


class ExtractPipelineError(AutoTestException):
    """提取管道执行异常.

    Attributes:
        step_index: 失败的步骤索引（从 0 开始）。
        step_type: 失败的步骤类型。
        expression: 失败的步骤表达式。
    """

    def __init__(
        self,
        message: str,
        step_index: int = -1,
        step_type: str = "",
        expression: str = "",
    ) -> None:
        super().__init__(message)
        self.step_index = step_index
        self.step_type = step_type
        self.expression = expression


@dataclass
class ExtractStep:
    """提取步骤.

    Attributes:
        type: 步骤类型。
        expression: jsonpath 表达式 / regex 模式。
        group: regex 捕获组索引（默认 1，即第一个捕获组）。
    """

    type: ExtractStepType
    expression: str = ""
    group: int = 1


class ExtractPipeline:
    """提取器管道.

    支持声明式链式处理：jsonpath → regex → base64_decode → json_parse
    每步的输出作为下一步的输入。

    Usage:
        pipeline = ExtractPipeline(steps=[
            ExtractStep(type=ExtractStepType.JSONPATH, expression="$.data.token"),
            ExtractStep(type=ExtractStepType.BASE64_DECODE),
        ])
        result = pipeline.execute({"data": {"token": "eyJ..."}})
    """

    def __init__(self, steps: list[ExtractStep]) -> None:
        """初始化管道.

        Args:
            steps: 提取步骤列表（按序执行）。

        Raises:
            ValueError: steps 为空时。
        """
        if not steps:
            raise ValueError("ExtractPipeline 的 steps 不能为空")
        self.steps = steps

    def execute(self, source: str | dict | bytes | list | Any) -> Any:
        """执行提取管道.

        Args:
            source: 原始数据源（可以是响应体 dict、字符串或 bytes）。

        Returns:
            最终提取结果。如果最后一步是 json_parse 则返回 dict/list，
            否则返回字符串。

        Raises:
            ExtractPipelineError: 任一步骤失败时。
        """
        current: Any = source

        for i, step in enumerate(self.steps):
            try:
                current = self._execute_step(current, step)
            except ExtractPipelineError as e:
                # 补充 step_index（如果步骤方法未设置）
                if e.step_index == -1:
                    e.step_index = i
                raise
            except Exception as e:
                raise ExtractPipelineError(
                    f"管道步骤 [{i}] {step.type.value} 执行失败: {e}",
                    step_index=i,
                    step_type=step.type.value,
                    expression=step.expression,
                ) from e

        # 最终结果处理：只有字符串/bytes 需要确保转为 str
        if isinstance(current, bytes):
            return current.decode("utf-8", errors="replace")
        return current

    def _execute_step(self, data: Any, step: ExtractStep) -> Any:
        """执行单个提取步骤.

        Args:
            data: 上一步的输出（或原始数据源）。
            step: 当前步骤定义。

        Returns:
            当前步骤的输出，作为下一步的输入。
        """
        if step.type == ExtractStepType.JSONPATH:
            return self._do_jsonpath(data, step.expression)

        elif step.type == ExtractStepType.REGEX:
            return self._do_regex(data, step.expression, step.group)

        elif step.type == ExtractStepType.BASE64_DECODE:
            return self._do_base64_decode(data)

        elif step.type == ExtractStepType.BASE64_ENCODE:
            return self._do_base64_encode(data)

        elif step.type == ExtractStepType.JSON_PARSE:
            return self._do_json_parse(data)

        else:
            raise ExtractPipelineError(
                f"未知的步骤类型: {step.type.value}",
                step_type=step.type.value,
            )

    # ── 步骤实现 ──────────────────────────────────────

    @staticmethod
    def _do_jsonpath(data: Any, expression: str) -> Any:
        """JSONPath 提取.

        Args:
            data: 数据源（dict/list）。
            expression: JSONPath 表达式。

        Returns:
            提取的值。

        Raises:
            ExtractPipelineError: 提取失败时。
        """
        result = extract_value(data, expression)
        if result is None:
            raise ExtractPipelineError(
                f"JSONPath '{expression}' 未匹配到任何值",
                step_type="jsonpath",
                expression=expression,
            )
        return result

    @staticmethod
    def _do_regex(data: Any, pattern: str, group: int = 1) -> str:
        """正则提取.

        Args:
            data: 输入字符串。
            pattern: 正则表达式模式。
            group: 捕获组索引（0 = 完整匹配，1+ = 对应捕获组）。

        Returns:
            匹配的字符串。

        Raises:
            ExtractPipelineError: 无匹配时。
        """
        text = str(data) if not isinstance(data, str) else data
        match = re.search(pattern, text)
        if not match:
            raise ExtractPipelineError(
                f"正则 '{pattern}' 未匹配到任何内容",
                step_type="regex",
                expression=pattern,
            )
        try:
            return match.group(group)
        except IndexError:
            # 如果指定捕获组不存在，返回完整匹配
            return match.group(0)

    @staticmethod
    def _do_base64_decode(data: Any) -> str:
        """Base64 解码.

        Args:
            data: Base64 编码的字符串或 bytes。

        Returns:
            解码后的字符串。

        Raises:
            ExtractPipelineError: 解码失败时。
        """
        if isinstance(data, bytes):
            raw = data
        else:
            raw = str(data).encode("utf-8")
        try:
            decoded = base64.b64decode(raw, validate=True)
            return decoded.decode("utf-8", errors="replace")
        except Exception as e:
            raise ExtractPipelineError(
                f"Base64 解码失败: {e}",
                step_type="base64_decode",
            ) from e

    @staticmethod
    def _do_base64_encode(data: Any) -> str:
        """Base64 编码.

        Args:
            data: 待编码的数据。

        Returns:
            Base64 编码后的字符串。
        """
        if isinstance(data, bytes):
            raw = data
        else:
            raw = str(data).encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    @staticmethod
    def _do_json_parse(data: Any) -> dict | list | str:
        """JSON 解析.

        如果 data 已经是 dict/list，直接返回；
        如果是字符串，尝试 JSON 解析。

        Args:
            data: JSON 字符串或已解析的对象。

        Returns:
            解析后的 dict/list。

        Raises:
            ExtractPipelineError: JSON 解析失败时。
        """
        if isinstance(data, (dict, list)):
            return data
        try:
            return json.loads(str(data))
        except json.JSONDecodeError as e:
            raise ExtractPipelineError(
                f"JSON 解析失败: {e}",
                step_type="json_parse",
            ) from e
