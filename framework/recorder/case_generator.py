"""测试用例生成器 — 将 HAR 录制文件转换为 YAML 测试用例

基于录制时的请求/响应自动生成可执行的 YAML 测试用例，
支持：
- 断言自动推断：从录制响应中提取关键字段作为断言
- 标签自动分类：根据 URL 路径和方法推断标签
- 优先级推断：基于状态码和响应类型设定优先级
- 数据驱动模板：支持生成数据驱动测试配置

使用方式::

    from framework.recorder import CaseGenerator

    generator = CaseGenerator()
    generator.generate(
        "recordings/session.har",
        output_dir="testcases/regression/",
        suite_name="回归测试-用户模块"
    )
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from framework.recorder.player import HARPlayer
from framework.utils.logger import Logger

logger = Logger.get("recorder.generator")


class _SafeDumper(yaml.Dumper):
    """安全 YAML Dumper，使用默认流样式。"""

    pass


class _IndentListDumper(_SafeDumper):
    """列表缩进增强 Dumper。"""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow, False)


@dataclass
class GenerateOptions:
    """用例生成选项

    Attributes:
        auto_assert: 是否自动生成断言（默认 True）。关闭时仅生成请求骨架。
        assert_status: 是否断言状态码。
        assert_headers: 需要断言验证的响应头列表。
        assert_body_fields: 需要断言验证的响应体字段（为空则自动选择前 N 个）。
        max_assert_fields: 自动断言时最多验证的字段数。
        strict_assert: 严格断言模式（operator 用 eq），关闭时使用 contains 等宽松运算符。
        include_extract: 是否包含变量提取配置。
        priority: 默认用例优先级。
        tags: 默认标签列表。
    """

    auto_assert: bool = True
    assert_status: bool = True
    assert_headers: list[str] = field(default_factory=list)
    assert_body_fields: list[str] = field(default_factory=list)
    max_assert_fields: int = 5
    strict_assert: bool = True
    include_extract: bool = False
    priority: str = "P1"
    tags: list[str] = field(default_factory=list)


@dataclass
class GenerateResult:
    """生成结果

    Attributes:
        output_file: 生成的 YAML 文件路径。
        case_count: 生成的用例数量。
        skipped_entries: 跳过的条目数（如无响应数据的请求）。
    """

    output_file: str = ""
    case_count: int = 0
    skipped_entries: int = 0
    errors: list[str] = field(default_factory=list)


class CaseGenerator:
    """测试用例生成器

    从 HAR 录制文件生成 YAML 测试用例。核心流程：
    1. 加载 HAR 文件
    2. 遍历每个请求/响应对
    3. 为每个条目生成一个测试用例（请求 + 自动推断的断言）
    4. 组装为测试套件并写入 YAML 文件

    Attributes:
        options: 生成选项配置。
    """

    def __init__(self, options: GenerateOptions | None = None) -> None:
        """初始化用例生成器。

        Args:
            options: 生成选项，为 None 时使用默认配置。
        """
        self.options = options or GenerateOptions()

    def generate(
        self,
        har_file: str,
        output_dir: str = "testcases/generated/",
        suite_name: str = "",
        options: GenerateOptions | None = None,
    ) -> GenerateResult:
        """从 HAR 文件生成 YAML 测试用例。

        Args:
            har_file: HAR 文件路径。
            output_dir: 用例输出目录。
            suite_name: 套件名称（为空时从 HAR 文件中提取）。
            options: 生成选项（覆盖实例默认配置）。

        Returns:
            GenerateResult 生成结果。
        """
        opts = options or self.options
        result = GenerateResult()
        errors: list[str] = []

        # 加载 HAR
        har_path = Path(har_file)
        if not har_path.exists():
            raise FileNotFoundError(f"HAR 文件不存在: {har_file}")

        har_data = json.loads(har_path.read_text(encoding="utf-8"))
        log = har_data.get("log", {})
        entries = log.get("entries", [])

        # 确定套件名称
        if not suite_name:
            creator = log.get("creator", {})
            suite_name = creator.get("comment", "") or har_path.stem

        # 构建用例列表
        cases: list[dict[str, Any]] = []
        tags = list(opts.tags)

        for i, entry in enumerate(entries):
            try:
                request = entry.get("request", {})
                response = entry.get("response", {})

                if not request or not response:
                    result.skipped_entries += 1
                    continue

                case = self._build_case(request, response, i, opts)
                cases.append(case)

                # 从 URL 路径收集标签
                url = request.get("url", "")
                path_tags = self._infer_tags_from_url(url, request.get("method", ""))
                for t in path_tags:
                    if t not in tags:
                        tags.append(t)

            except Exception as e:
                errors.append(f"条目 {i}: {str(e)}")
                result.skipped_entries += 1

        if not cases:
            if errors:
                logger.error("generation_no_cases", errors=errors)
            return result

        # 构建套件
        suite: dict[str, Any] = {
            "name": suite_name,
            "description": f"从 HAR 录制文件自动生成 — {har_path.name}",
            "tags": tags,
            "cases": cases,
        }

        # 写入 YAML 文件
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        safe_name = _safe_case_filename(suite_name)
        yaml_path = output_path / f"{safe_name}.yaml"

        # 使用自定义 YamlDumper 保持可读格式
        yaml_content = yaml.dump(
            suite,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            Dumper=_IndentListDumper,
        )

        # 改善 YAML 格式：添加空行分隔用例
        yaml_content = yaml_content.replace("\n- name:", "\n\n  - name:")

        yaml_path.write_text(yaml_content, encoding="utf-8")

        result.output_file = str(yaml_path)
        result.case_count = len(cases)
        result.errors = errors

        logger.info(
            "cases_generated",
            output_file=str(yaml_path),
            case_count=len(cases),
            skipped=result.skipped_entries,
        )

        return result

    # ---------- 私有方法 ----------

    def _build_case(
        self,
        request: dict[str, Any],
        response: dict[str, Any],
        index: int,
        opts: GenerateOptions,
    ) -> dict[str, Any]:
        """为单个 HAR 条目构建测试用例。

        Args:
            request: HAR 请求数据。
            response: HAR 响应数据。
            index: 条目序号。
            opts: 生成选项。

        Returns:
            测试用例字典。
        """
        method = request.get("method", "GET")
        url = request.get("url", "")

        # 用例名称
        name = self._generate_case_name(url, method, index)

        # 请求配置
        case_request = self._build_request(request)

        # 断言配置
        assertions = {}
        if opts.auto_assert:
            assertions = self._build_assertions(response, opts)

        case: dict[str, Any] = {
            "name": name,
            "description": f"自动生成的回归用例 — {method} {url}",
            "request": case_request,
        }

        if assertions:
            case["expect"] = assertions

        return case

    def _build_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """构建请求配置。"""
        method = request.get("method", "GET")
        url = request.get("url", "")

        # 从完整 URL 提取路径和查询参数
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(url)
        path = parsed.path or "/"

        req: dict[str, Any] = {
            "method": method,
            "path": path,
        }

        # 查询参数
        if parsed.query:
            params: dict[str, Any] = {}
            for k, v in parse_qs(parsed.query).items():
                params[k] = v[0] if len(v) == 1 else v
            if params:
                req["params"] = params

        # 请求头
        headers = request.get("headers", [])
        req_headers: dict[str, str] = {}
        for h in headers:
            name = h.get("name", "")
            # 跳过不需要的头
            if name.lower() in ("host", "accept-encoding", "connection"):
                continue
            req_headers[name] = h.get("value", "")
        if req_headers:
            req["headers"] = req_headers

        # 请求体
        post_data = request.get("postData")
        if post_data:
            text = post_data.get("text", "")
            mime = post_data.get("mimeType", "").lower()
            if text:
                if "json" in mime:
                    try:
                        body = json.loads(text)
                        req["body"] = body
                        req["body_type"] = "json"
                    except json.JSONDecodeError:
                        req["body"] = text
                        req["body_type"] = "raw"
                elif "form" in mime:
                    form_body: dict[str, str] = {}
                    for p in post_data.get("params", []):
                        form_body[p.get("name", "")] = p.get("value", "")
                    req["body"] = form_body
                    req["body_type"] = "form"
                else:
                    req["body"] = text
                    req["body_type"] = "raw"

        return req

    def _build_assertions(
        self,
        response: dict[str, Any],
        opts: GenerateOptions,
    ) -> dict[str, Any]:
        """自动推断断言配置。

        Args:
            response: HAR 响应数据。
            opts: 生成选项。

        Returns:
            断言配置字典。
        """
        assertions: dict[str, Any] = {}

        # 状态码断言
        if opts.assert_status:
            status = response.get("status", 0)
            assertions["status_code"] = status

        # 响应头断言
        if opts.assert_headers:
            resp_headers: dict[str, str] = {}
            for h in response.get("headers", []):
                name = h.get("name", "")
                if name.lower() in (h.lower() for h in opts.assert_headers):
                    resp_headers[name] = h.get("value", "")
            if resp_headers:
                assertions["headers"] = resp_headers

        # 响应体断言
        content = response.get("content", {})
        body_text = content.get("text", "")

        if body_text and opts.assert_body_fields:
            body = self._parse_response_body(body_text, content.get("mimeType", ""))
            if isinstance(body, dict):
                body_asserts = self._build_body_assert_dict(body, opts)
                if body_asserts:
                    assertions["body"] = body_asserts
            elif isinstance(body, list):
                if len(body) > 0 and isinstance(body[0], dict):
                    assertions["jsonpath"] = {
                        "$.length()": str(len(body))
                    }

        elif body_text:
            # 自动模式：尝试解析并提取关键字段
            body = self._parse_response_body(body_text, content.get("mimeType", ""))
            if isinstance(body, dict):
                body_asserts = self._build_body_assert_dict(body, opts)
                if body_asserts:
                    assertions["body"] = body_asserts
            elif isinstance(body, list) and len(body) > 0:
                assertions["body"] = _ListPlaceholder(len(body))

        return assertions

    @staticmethod
    def _parse_response_body(text: str, mime_type: str) -> Any:
        """解析响应体文本。"""
        if not text:
            return None
        if "json" in (mime_type or "").lower():
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        # 尝试 JSON 解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def _build_body_assert_dict(
        self, body: dict[str, Any], opts: GenerateOptions
    ) -> dict[str, Any]:
        """从字典响应体构建断言字典。"""
        asserts: dict[str, Any] = {}
        count = 0

        # 优先检查用户指定的字段
        for field in opts.assert_body_fields:
            if field in body:
                value = body[field]
                if isinstance(value, (str, int, float, bool, type(None))):
                    asserts[field] = value
                    count += 1

        # 自动选择字段（顶层简单类型）
        if count < opts.max_assert_fields:
            for key, value in body.items():
                if key in asserts or key in ("id", "created_at", "updated_at", "timestamp"):
                    # 跳过已在断言中或 ID/时间戳类字段
                    continue
                if isinstance(value, (str, int, float, bool, type(None))):
                    asserts[key] = value
                    count += 1
                    if count >= opts.max_assert_fields:
                        break

        return asserts

    @staticmethod
    def _generate_case_name(url: str, method: str, index: int) -> str:
        """生成用例名称。"""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        path = parsed.path.strip("/").replace("/", " ")

        if path:
            # 首字母大写
            parts = path.split(" ")
            path = " ".join(p.title() for p in parts)

        method_upper = method.upper()
        if path:
            return f"{method_upper} {path}"
        return f"{method_upper} Request #{index + 1}"

    @staticmethod
    def _infer_tags_from_url(url: str, method: str) -> list[str]:
        """从 URL 和 HTTP 方法推断测试标签。"""
        from urllib.parse import urlparse

        tags: list[str] = []
        parsed = urlparse(url)
        path = parsed.path.strip("/").lower()

        # 按路径段添加标签
        segments = path.split("/") if path else []
        if segments:
            # 第一个路径段通常代表资源或模块
            if segments[0]:
                tags.append(segments[0])

        # CRUD 标签
        method_upper = method.upper()
        if method_upper == "GET":
            tags.append("read")
        elif method_upper in ("POST", "PUT", "PATCH"):
            tags.append("write")
        elif method_upper == "DELETE":
            tags.append("delete")

        return tags


class _ListPlaceholder:
    """列表占位符 — 用于 YAML 序列化时保留空列表格式。"""

    def __init__(self, count: int = 0) -> None:
        self.count = count

    def __repr__(self) -> str:
        return str([self.count])


def _safe_case_filename(name: str) -> str:
    """将名称转换为安全的文件名。"""
    import re

    safe = re.sub(r"[^\w\s-]", "", name)
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe or "generated_cases"
