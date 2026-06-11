"""变量提取器 — 从 HTTP 响应和数据库结果中提取变量"""

from __future__ import annotations

import json
import re
from typing import Any

from framework.exceptions import ExtractorError
from framework.extract_pipeline import (
    ExtractPipeline,
    ExtractPipelineError,
    ExtractStep,
    ExtractStepType,
)
from framework.models import ExtractItem, HttpResponse
from framework.utils.jsonpath_util import extract_value
from framework.utils.logger import Logger

logger = Logger.get("extractor")


class Extractor:
    """变量提取器

    支持的 source_type:
    - jsonpath:     $.data.token
    - header:       Content-Type
    - body_regex:   "token\":\"([^\"]+)"
    - status_code:  (直接取状态码)
    - elapsed:      (取响应时间 ms)
    - sql_column:   column_name (从 DB 查询结果提取)
    - pipeline:     链式提取管道（jsonpath → regex → base64_decode → json_parse）
    """

    def extract(
        self,
        response: HttpResponse,
        extracts: list[ExtractItem],
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行提取，返回 {var_name: value} 字典"""
        results: dict[str, Any] = {}

        for item in extracts:
            try:
                value = self._extract_single(response, item)
                if value is not None:
                    results[item.var_name] = value
                    logger.debug("variable_extracted", var_name=item.var_name, source=item.source)
                elif item.default is not None:
                    results[item.var_name] = item.default
                    logger.debug("variable_extracted_default", var_name=item.var_name, default=item.default)
                else:
                    logger.warning("variable_extract_failed", var_name=item.var_name, reason="value is None with no default")
            except ExtractorError:
                raise
            except ExtractPipelineError as e:
                if item.default is not None:
                    results[item.var_name] = item.default
                    logger.debug("pipeline_extract_fallback", var_name=item.var_name, default=item.default, error=str(e))
                else:
                    logger.error("pipeline_extract_error", var_name=item.var_name, error=str(e))
                    raise ExtractorError(
                        f"管道提取变量 '{item.var_name}' 失败: {e}",
                        var_name=item.var_name,
                        source=item.source,
                        source_type=item.source_type,
                    ) from e
            except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
                if item.default is not None:
                    results[item.var_name] = item.default
                    logger.debug("variable_extracted_fallback", var_name=item.var_name, default=item.default)
                else:
                    logger.error("variable_extract_error", var_name=item.var_name, error=str(e))
                    raise ExtractorError(
                        f"提取变量 '{item.var_name}' 失败: {e}",
                        var_name=item.var_name,
                        source=item.source,
                        source_type=item.source_type,
                    ) from e

        return results

    def extract_from_db(
        self,
        rows: list[dict[str, Any]] | dict[str, Any] | None,
        extracts: list[ExtractItem],
    ) -> dict[str, Any]:
        """从数据库查询结果中提取变量"""
        results: dict[str, Any] = {}

        if rows is None:
            return results

        for item in extracts:
            try:
                value = self._extract_from_db_result(rows, item)
                if value is not None:
                    results[item.var_name] = value
                elif item.default is not None:
                    results[item.var_name] = item.default
            except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
                if item.default is not None:
                    results[item.var_name] = item.default
                else:
                    logger.error("db_variable_extract_error", var_name=item.var_name, error=str(e))

        return results

    def _extract_single(self, response: HttpResponse, item: ExtractItem) -> Any:
        """从 HTTP 响应中提取单个变量"""
        source_type = item.source_type

        if source_type == "pipeline":
            return self._extract_with_pipeline(response.body, item)

        if source_type == "jsonpath":
            return self._extract_from_jsonpath(response.body, item.source)

        elif source_type == "header":
            return self._extract_from_header(response.headers, item.source)

        elif source_type == "body_regex":
            return self._extract_from_regex(
                str(response.body) if not isinstance(response.body, str) else response.body,
                item.source,
            )

        elif source_type == "status_code":
            return response.status_code

        elif source_type == "elapsed":
            return response.elapsed_ms

        else:
            # 尝试自动推断
            if item.source.startswith("$."):
                return self._extract_from_jsonpath(response.body, item.source)
            elif item.source.startswith("header."):
                return self._extract_from_header(response.headers, item.source[7:])
            else:
                return self._extract_from_jsonpath(response.body, item.source)

    @staticmethod
    def _extract_with_pipeline(body: Any, item: ExtractItem) -> Any:
        """使用提取管道执行链式提取.

        Args:
            body: 响应体。
            item: 包含 pipeline 定义的 ExtractItem。

        Returns:
            管道最终输出字符串。

        Raises:
            ExtractPipelineError: 管道执行失败时。
        """
        if not item.pipeline:
            raise ExtractPipelineError(
                "pipeline 配置为空",
                step_type="pipeline",
            )
        steps = [
            ExtractStep(
                type=ExtractStepType(s["type"]),
                expression=s.get("expression", ""),
                group=s.get("group", 1),
            )
            for s in item.pipeline
        ]
        pipeline = ExtractPipeline(steps=steps)
        return pipeline.execute(body)

    @staticmethod
    def _extract_from_jsonpath(body: Any, path: str) -> Any:
        """JSONPath 提取"""
        return extract_value(body, path)

    @staticmethod
    def _extract_from_header(headers: dict[str, str], name: str) -> str | None:
        """响应头提取（不区分大小写）"""
        name_lower = name.lower()
        for key, value in headers.items():
            if key.lower() == name_lower:
                return value
        return None

    @staticmethod
    def _extract_from_regex(body: str, pattern: str) -> str | None:
        """正则提取"""
        match = re.search(pattern, body)
        if match:
            # 如果有捕获组，返回第一个组
            if match.groups():
                return match.group(1)
            return match.group(0)
        return None

    @staticmethod
    def _extract_from_db_result(
        rows: list[dict[str, Any]] | dict[str, Any],
        item: ExtractItem,
    ) -> Any:
        """从数据库查询结果中提取变量"""
        if isinstance(rows, dict):
            # fetch_one 结果
            return rows.get(item.source)
        elif isinstance(rows, list) and len(rows) > 0:
            # fetchall 结果，取第一行
            return rows[0].get(item.source)
        return None
