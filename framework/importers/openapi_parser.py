"""OpenAPI 3.x 规范解析器 — 从 OpenAPI/Swagger spec 自动生成测试用例

核心能力：
- 解析 JSON / YAML 格式的 OpenAPI 3.x 规范
- 为每个 path + method 生成 TestCase，含 URL、方法、请求体示例
- 从 responses / examples 推断初始断言（状态码、Content-Type）
- 递归解析 $ref 引用（本地引用和跨文件引用）
- 支持通过 URL 或本地文件路径加载 spec
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import yaml

from framework.models import (
    AssertItem,
    BodyType,
    HttpMethod,
    HttpRequest,
    TestCase,
    TestSuite,
)
from framework.utils.logger import Logger
from framework.utils.template import TemplateEngine

logger = Logger.get("openapi_parser")

# 内置 Schema 生成器支持的类型映射
_TYPE_MAP: dict[str, Any] = {
    "string": "string",
    "integer": 0,
    "number": 0.0,
    "boolean": False,
    "array": [],
    "object": {},
}


def _generate_example_from_schema(schema: dict[str, Any], ref_resolver: Any = None) -> Any:
    """从 JSON Schema 生成示例数据。

    优先使用 schema 中的 example / examples 字段，
    否则根据 type 递归生成合理的默认值。
    """
    if "example" in schema:
        return schema["example"]
    if "examples" in schema:
        examples = schema["examples"]
        if isinstance(examples, list) and examples:
            return examples[0]
        if isinstance(examples, dict):
            first = next(iter(examples.values()), None)
            if isinstance(first, dict):
                return first.get("value", first)

    schema_type = schema.get("type", "object")

    if schema_type == "string":
        if "enum" in schema:
            return schema["enum"][0]
        if "format" in schema:
            fmt = schema["format"]
            if fmt == "date":
                return "2025-01-01"
            if fmt == "date-time":
                return "2025-01-01T00:00:00Z"
            if fmt == "email":
                return "user@example.com"
            if fmt == "uri" or fmt == "url":
                return "https://example.com"
            if fmt == "uuid":
                return "00000000-0000-0000-0000-000000000000"
        return schema.get("default", "string")

    if schema_type == "integer":
        if "enum" in schema:
            return schema["enum"][0]
        return schema.get("default", schema.get("minimum", 0))

    if schema_type == "number":
        if "enum" in schema:
            return schema["enum"][0]
        return schema.get("default", schema.get("minimum", 0.0))

    if schema_type == "boolean":
        return schema.get("default", False)

    if schema_type == "array":
        items_schema = schema.get("items", {"type": "string"})
        item_example = _generate_example_from_schema(items_schema, ref_resolver)
        return [item_example]

    if schema_type == "object":
        result: dict[str, Any] = {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for prop_name, prop_schema in properties.items():
            if isinstance(prop_schema, dict):
                result[prop_name] = _generate_example_from_schema(prop_schema, ref_resolver)
        # 确保 required 字段都存在
        for prop_name in required:
            if prop_name not in result:
                result[prop_name] = None
        return result

    return None


class _RefResolver:
    """OpenAPI $ref 引用解析器。

    支持：
    - 本地引用: #/components/schemas/Pet
    - 同文件内部引用: #/paths/~1pets/get/responses/200
    - 远程引用: ./other.yaml#/components/schemas/Error（可选）
    """

    def __init__(self, document: dict[str, Any], source_url: str = "") -> None:
        self._doc = document
        self._source_url = source_url
        self._external_cache: dict[str, dict[str, Any]] = {}

    def resolve(self, ref: str) -> Any:
        """解析单个 $ref 引用"""
        if not ref:
            return None

        # 分离外部文件路径和内部路径
        parts = ref.split("#", 1)
        external_path = parts[0]
        fragment = parts[1] if len(parts) > 1 else ""

        if external_path:
            # 远程引用：加载外部文件
            doc = self._load_external(external_path)
            if fragment:
                return self._resolve_fragment(doc, fragment)
            return doc
        elif fragment:
            # 本地引用
            return self._resolve_fragment(self._doc, fragment)
        return None

    def resolve_all(self, obj: Any, max_depth: int = 20) -> Any:
        """递归解析对象中所有 $ref 引用"""
        if max_depth <= 0:
            return obj

        if isinstance(obj, dict):
            if "$ref" in obj and len(obj) == 1:
                resolved = self.resolve(obj["$ref"])
                if isinstance(resolved, dict) and "$ref" in resolved:
                    return self.resolve_all(resolved, max_depth - 1)
                return resolved
            return {k: self.resolve_all(v, max_depth - 1) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.resolve_all(item, max_depth - 1) for item in obj]
        return obj

    def _resolve_fragment(self, doc: dict[str, Any], fragment: str) -> Any:
        """根据 JSON Pointer 路径解析文档片段"""
        # JSON Pointer 格式: /components/schemas/Pet
        # 特殊字符: ~0 = ~, ~1 = /
        parts = fragment.split("/")
        current: Any = doc
        for part in parts:
            if not part:
                continue
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list):
                try:
                    idx = int(part)
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return None
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current

    def _load_external(self, path: str) -> dict[str, Any]:
        """加载外部引用的 spec 文件"""
        if path in self._external_cache:
            return self._external_cache[path]

        # 解析相对路径
        resolved_url = path
        if self._source_url:
            parsed = urlparse(self._source_url)
            if parsed.scheme in ("http", "https"):
                resolved_url = urljoin(self._source_url, path)
            else:
                resolved_url = str(Path(self._source_url).parent / path) if self._source_url else path

        content = _load_spec_content(resolved_url)
        doc = _parse_spec_content(content)
        self._external_cache[path] = doc
        return doc


def _load_spec_content(source: str) -> str:
    """加载 spec 内容（支持 URL 和本地文件路径）"""
    parsed = urlparse(source)

    if parsed.scheme in ("http", "https"):
        try:
            resp = httpx.get(source, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as e:
            raise ValueError(f"无法从 URL 加载 spec: {source}, 错误: {e}") from e

    # 本地文件路径
    path = Path(source).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Spec 文件不存在: {path}")
    return path.read_text(encoding="utf-8")


def _parse_spec_content(content: str) -> dict[str, Any]:
    """解析 spec 内容（自动检测 JSON 或 YAML 格式）"""
    content = content.strip()
    if content.startswith("{"):
        return json.loads(content)
    return yaml.safe_load(content)


# ==================== OpenAPI 解析器 ====================


class OpenAPICaseParser:
    """OpenAPI 3.x 规范解析器 — 从 spec 自动生成测试用例。

    用法::

        parser = OpenAPICaseParser()
        suite = parser.parse_from_url("https://petstore3.swagger.io/api/v3/openapi.json")
        # suite.cases 包含每个 path+method 的 TestCase

    或者直接处理 spec dict::

        suite = parser.parse_spec(spec_dict, base_url="https://api.example.com")
    """

    def __init__(self) -> None:
        self._base_url: str = ""

    # ── Public API ─────────────────────────────────────────

    def parse_from_url(self, url: str, suite_name: str | None = None) -> TestSuite:
        """从 URL 加载 OpenAPI spec 并生成测试套件。

        Args:
            url: OpenAPI spec 的 URL 或本地文件路径
            suite_name: 套件名称，不指定则从 spec info.title 推断

        Returns:
            包含所有 path+method 用例的 TestSuite
        """
        content = _load_spec_content(url)
        spec = _parse_spec_content(content)

        suite = self.parse_spec(spec, suite_name=suite_name, source_url=url)

        logger.info(
            "spec_parsed",
            url=url,
            case_count=len(suite.cases),
            title=spec.get("info", {}).get("title", "Unknown"),
        )
        return suite

    def parse_spec(
        self,
        spec: dict[str, Any],
        suite_name: str | None = None,
        base_url: str = "",
        source_url: str = "",
    ) -> TestSuite:
        """解析 OpenAPI spec 字典，生成 TestSuite。

        Args:
            spec: OpenAPI 3.x 规范字典
            suite_name: 套件名称
            base_url: 覆盖 spec 中 servers 的 base URL
            source_url: spec 来源 URL（用于解析 $ref 相对路径）

        Returns:
            生成的 TestSuite
        """
        version = spec.get("openapi", "")
        if not version.startswith("3."):
            raise ValueError(f"仅支持 OpenAPI 3.x 规范，当前版本: {version}")

        # 确定 base_url
        self._base_url = base_url
        if not self._base_url:
            servers = spec.get("servers", [])
            if servers:
                self._base_url = servers[0].get("url", "").rstrip("/")

        # 解析 title 和 description
        info = spec.get("info", {})
        title = suite_name or info.get("title", "OpenAPI Import")
        description = info.get("description", "")

        # 初始化 $ref 解析器
        resolver = _RefResolver(spec, source_url)

        suite = TestSuite(
            name=title,
            description=description,
            base_url=self._base_url,
            tags=["openapi", "auto-generated"],
        )

        # 遍历所有 paths
        paths = spec.get("paths", {})
        for path_pattern, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # 收集路径级参数
            path_params = path_item.get("parameters", [])

            for method_name in ("get", "post", "put", "delete", "patch", "head", "options"):
                operation = path_item.get(method_name)
                if not operation or not isinstance(operation, dict):
                    continue

                try:
                    case = self._build_case(
                        method_name.upper(),
                        path_pattern,
                        operation,
                        path_params,
                        resolver,
                    )
                    suite.cases.append(case)
                except Exception as exc:
                    logger.warning(
                        "case_build_error",
                        method=method_name.upper(),
                        path=path_pattern,
                        error=str(exc),
                    )

        logger.info(
            "spec_parsed_memory",
            suite=suite.name,
            total_cases=len(suite.cases),
        )
        return suite

    # ── Case Builder ──────────────────────────────────────

    def _build_case(
        self,
        method: str,
        path: str,
        operation: dict[str, Any],
        path_params: list[dict[str, Any]],
        resolver: _RefResolver,
    ) -> TestCase:
        """从单个 operation 构建 TestCase"""
        # 解析 $ref
        op = resolver.resolve_all(operation)

        # 合并路径级和操作级参数
        op_params = op.get("parameters", [])
        all_params = list(path_params) + list(op_params)

        # 分类参数为 headers, query, path
        query_params: dict[str, Any] = {}
        header_params: dict[str, str] = {}
        for param in all_params:
            param = resolver.resolve_all(param)
            param_in = param.get("in", "")
            name = param.get("name", "")
            if not name:
                continue
            example = self._get_param_example(param)
            if param_in == "query":
                if example is not None:
                    query_params[name] = example
            elif param_in == "header":
                if example is not None:
                    header_params[name] = str(example)

        # 构建请求体
        body: Any = None
        body_type: BodyType = BodyType.NONE
        content_type: str = ""

        request_body = op.get("requestBody", {})
        if request_body:
            body, body_type, content_type = self._build_body(request_body, resolver)

        # 构建请求 URL —— 将路径参数替换为示例值
        resolved_path = self._resolve_path_params(path, all_params, resolver)

        # 推断 Content-Type 默认 header
        if content_type and "Content-Type" not in header_params and "content-type" not in {k.lower() for k in header_params}:
            header_params["Content-Type"] = content_type

        http_request = HttpRequest(
            method=HttpMethod(method),
            path=resolved_path,
            headers=header_params if header_params else {},
            params=query_params if query_params else {},
            body=body,
            body_type=body_type,
        )

        # 构建断言
        assertions = self._build_assertions(op.get("responses", {}), resolver)

        # 构建 Tags
        op_tags = [t if isinstance(t, str) else t.get("name", str(t)) for t in op.get("tags", [])]

        # 用例名称
        case_name = (
            op.get("summary")
            or op.get("operationId")
            or f"{method} {path}"
        )

        return TestCase(
            name=str(case_name),
            description=op.get("description", "").strip() or f"{method} {path}",
            tags=list(set(["openapi", "auto-generated", method.lower()] + op_tags)),
            priority=self._infer_priority(op_tags),
            request=http_request,
            assertions=assertions,
        )

    def _resolve_path_params(
        self,
        path: str,
        all_params: list[dict[str, Any]],
        resolver: _RefResolver,
    ) -> str:
        """将路径中的 {param} 占位符替换为参数的示例值"""
        resolved = path
        # 收集路径参数及其示例值
        param_examples: dict[str, str] = {}
        for param in all_params:
            p = resolver.resolve_all(param)
            if p.get("in") == "path":
                name = p.get("name", "")
                example = self._get_param_example(p)
                if name and example is not None:
                    param_examples[name] = str(example)

        # 替换 {paramName} 模板
        for name, val in param_examples.items():
            resolved = resolved.replace(f"{{{name}}}", val)

        return resolved

    def _get_param_example(self, param: dict[str, Any]) -> Any:
        """从参数定义中提取示例值"""
        if "example" in param:
            return param["example"]
        if "examples" in param:
            examples = param["examples"]
            if isinstance(examples, dict):
                first = next(iter(examples.values()), None)
                if isinstance(first, dict):
                    return first.get("value")
                return first
            if isinstance(examples, list) and examples:
                return examples[0]

        schema = param.get("schema", {})
        if schema:
            return _generate_example_from_schema(schema)
        return None

    def _build_body(
        self, request_body: dict[str, Any], resolver: _RefResolver
    ) -> tuple[Any, BodyType, str]:
        """从 requestBody 构建请求体和 body_type"""
        rb = resolver.resolve_all(request_body)
        content = rb.get("content", {})

        # 优先级: json > form > multipart > raw > 第一个
        for mime_type, body_type in [
            ("application/json", BodyType.JSON),
            ("application/x-www-form-urlencoded", BodyType.FORM),
            ("multipart/form-data", BodyType.MULTIPART),
        ]:
            if mime_type in content:
                media = resolver.resolve_all(content[mime_type])
                schema = media.get("schema", {})
                example = self._get_media_example(media, schema, resolver)
                return example, body_type, mime_type

        # 回退：取第一个 content type
        if content:
            first_mime = next(iter(content.keys()))
            media = resolver.resolve_all(content[first_mime])
            schema = media.get("schema", {})
            example = self._get_media_example(media, schema, resolver)
            return example, BodyType.JSON, first_mime

        return None, BodyType.NONE, ""

    def _get_media_example(
        self,
        media: dict[str, Any],
        schema: dict[str, Any],
        resolver: _RefResolver,
    ) -> Any:
        """从 media type 对象中提取示例"""
        schema = resolver.resolve_all(schema)

        # 优先 example
        if "example" in media:
            return media["example"]

        # examples map
        examples = media.get("examples", {})
        if examples:
            first = next(iter(examples.values()), None)
            if isinstance(first, dict):
                return first.get("value", first)
            return first

        # 从 schema 生成
        if schema:
            return _generate_example_from_schema(schema)
        return {}

    def _build_assertions(
        self,
        responses: dict[str, Any],
        resolver: _RefResolver,
    ) -> list[AssertItem]:
        """从 responses 构建断言列表"""
        items: list[AssertItem] = []

        for status_str, response_obj in responses.items():
            if status_str == "default":
                continue

            try:
                status_code = int(status_str)
            except ValueError:
                continue

            response = resolver.resolve_all(response_obj)

            # 对 2xx 成功响应添加状态码断言
            if 200 <= status_code < 300:
                items.append(
                    AssertItem(
                        path="status_code",
                        expected=status_code,
                        operator="eq",
                    )
                )

                # 添加 Content-Type 断言
                content = response.get("content", {})
                if "application/json" in content:
                    items.append(
                        AssertItem(
                            path="headers.Content-Type",
                            expected="application/json",
                            operator="contains",
                        )
                    )
                elif "text/html" in content:
                    items.append(
                        AssertItem(
                            path="headers.Content-Type",
                            expected="text/html",
                            operator="contains",
                        )
                    )

        return items

    def _infer_priority(self, tags: list[str]) -> str:
        """从标签推断优先级，默认 P1"""
        tag_lower = [t.lower() for t in tags]
        if "p0" in tag_lower or "critical" in tag_lower:
            return "P0"
        if "p1" in tag_lower:
            return "P1"
        if "p2" in tag_lower:
            return "P2"
        if "p3" in tag_lower:
            return "P3"
        return "P1"


# ==================== TestCase → YAML 序列化 ====================


def testcase_to_yaml(case: TestCase, indent: int = 2) -> str:
    """将 TestCase 序列化为框架 YAML 格式。

    生成的 YAML 可直接被 framework.parser.YAMLParser 解析，
    也可存储到数据库的 yaml_content 字段中。

    Args:
        case: TestCase 实例
        indent: YAML 缩进空格数

    Returns:
        YAML 字符串
    """
    import io

    class _YamlWriter:
        """简单 YAML 写入器（避免 yaml.dump 格式问题）"""

        def __init__(self, stream: io.StringIO, indent: int = 2):
            self._s = stream
            self._indent = indent
            self._level = 0

        def write_line(self, text: str = "") -> None:
            if text:
                self._s.write(" " * (self._level * self._indent) + text)
            self._s.write("\n")

        def key_value(self, key: str, value: Any) -> None:
            if value is None or value == "":
                return
            if isinstance(value, bool):
                self.write_line(f"{key}: {'true' if value else 'false'}")
            elif isinstance(value, (int, float)):
                self.write_line(f"{key}: {value}")
            elif isinstance(value, list) and not value:
                self.write_line(f"{key}: []")
            elif isinstance(value, dict) and not value:
                self.write_line(f"{key}: {{}}")
            elif isinstance(value, list):
                self.write_line(f"{key}:")
                self._level += 1
                for item in value:
                    if isinstance(item, dict):
                        self.dict(item, inline_first=False)
                    else:
                        self.write_line(f"- {self._quote(item)}")
                self._level -= 1
            elif isinstance(value, dict):
                self.write_line(f"{key}:")
                self._level += 1
                self.dict(value)
                self._level -= 1
            else:
                self.write_line(f"{key}: {self._quote(str(value))}")

        def dict(self, d: dict[str, Any], inline_first: bool = False) -> None:
            """写入一个 dict 的所有键值对"""
            for k, v in d.items():
                self.key_value(k, v)

        def _quote(self, val: Any) -> str:
            """需要时添加引号"""
            s = str(val)
            if s in ("true", "false", "null", "yes", "no", "on", "off"):
                return f'"{s}"'
            if ":" in s or "#" in s or s.startswith("{") or s.startswith("["):
                return f'"{s}"'
            if any(c in s for c in ["\n", "\r", "\t"]):
                return f'"{s}"'
            return s

    buf = io.StringIO()
    w = _YamlWriter(buf, indent=indent)

    # --- request ---
    if case.request:
        req_dict: dict[str, Any] = {}
        req_dict["method"] = case.request.method.value
        req_dict["path"] = case.request.path
        if case.request.headers:
            req_dict["headers"] = case.request.headers
        if case.request.params:
            req_dict["params"] = case.request.params
        if case.request.body is not None:
            req_dict["body"] = case.request.body
            if case.request.body_type != BodyType.JSON:
                req_dict["body_type"] = case.request.body_type.value
        if case.request.timeout is not None:
            req_dict["timeout"] = case.request.timeout
        if case.request.verify_ssl is not None:
            req_dict["verify_ssl"] = case.request.verify_ssl
        w.key_value("request", req_dict)

    # --- expect ---
    if case.assertions:
        expect: dict[str, Any] = {}
        headers_expect: dict[str, str] = {}
        for a in case.assertions:
            if a.path == "status_code":
                expect["status_code"] = a.expected
            elif a.path.startswith("headers."):
                header_name = a.path[len("headers.") :]
                headers_expect[header_name] = a.expected
            elif a.path == "response_time":
                if a.operator == "lt":
                    expect["response_time"] = f"<{a.expected}"
                else:
                    expect["response_time"] = a.expected
            else:
                # JSONPath 类断言
                if "jsonpath" not in expect:
                    expect["jsonpath"] = {}
                expect["jsonpath"][a.path] = {
                    "value": a.expected,
                    "operator": a.operator,
                }
        if headers_expect:
            expect["headers"] = headers_expect
        w.key_value("expect", expect)

    return buf.getvalue()


def testcase_to_yaml_content(case: TestCase) -> str:
    """生成完整的 YAML 内容（可直接存储为 yaml_content）"""
    yaml_body = testcase_to_yaml(case)
    return f"# Auto-generated from OpenAPI spec\n# Name: {case.name}\n{yaml_body}"


def suite_to_yaml(suite: TestSuite) -> str:
    """将 TestSuite 序列化为框架 YAML 格式（含套件级元数据）。"""
    import io

    lines: list[str] = []
    lines.append(f'name: "{suite.name}"')
    if suite.description:
        lines.append(f'description: "{suite.description}"')
    if suite.base_url:
        lines.append(f'base_url: "{suite.base_url}"')
    if suite.tags:
        lines.append("tags: [" + ", ".join(suite.tags) + "]")

    lines.append("cases:")
    for case in suite.cases:
        case_yaml = testcase_to_yaml(case, indent=4)
        # 添加用例名和属性头
        lines.append(f'  - name: "{case.name}"')
        if case.description:
            lines.append(f'    description: "{case.description}"')
        if case.tags:
            lines.append(f"    tags: [{', '.join(case.tags)}]")
        lines.append(f"    priority: {case.priority}")
        # 追加 request/expect 内容（带 4 空格缩进）
        for line in case_yaml.strip().split("\n"):
            lines.append(f"    {line}")
        lines.append("")  # 用例间空行

    return "\n".join(lines)
