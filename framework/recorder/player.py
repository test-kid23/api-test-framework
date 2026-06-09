"""HAR 回放引擎

读取 HAR 录制文件，通过实际 HTTP 请求重放每个请求，
并与录制时的响应进行对比，生成差异报告。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from framework.models import BodyType, HttpMethod, HttpRequest
from framework.recorder.differ import DiffEngine, DiffReport
from framework.recorder.har_models import HAR, HAREntry
from framework.utils.logger import Logger

logger = Logger.get("recorder.player")


@dataclass
class PlaybackResult:
    """单条目回放结果

    Attributes:
        entry_index: 条目序号（0-based）。
        method: HTTP 方法。
        url: 请求 URL。
        recorded_status: 录制时的状态码。
        actual_status: 回放时的状态码。
        recorded_elapsed_ms: 录制时的响应耗时。
        actual_elapsed_ms: 回放时的响应耗时。
        response_body: 回放时的响应体。
        diff_report: 差异报告（如有差异）。
        error: 回放时发生的错误（如连接失败）。
    """

    entry_index: int = 0
    method: str = "GET"
    url: str = ""
    recorded_status: int = 0
    actual_status: int = 0
    recorded_elapsed_ms: float = 0.0
    actual_elapsed_ms: float = 0.0
    response_body: Any = None
    diff_report: DiffReport | None = None
    error: str = ""

    @property
    def matched(self) -> bool:
        if self.error:
            return False
        if self.diff_report:
            return self.diff_report.matched
        return self.recorded_status == self.actual_status

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_index": self.entry_index,
            "method": self.method,
            "url": self.url,
            "recorded_status": self.recorded_status,
            "actual_status": self.actual_status,
            "recorded_elapsed_ms": round(self.recorded_elapsed_ms, 2),
            "actual_elapsed_ms": round(self.actual_elapsed_ms, 2),
            "matched": self.matched,
            "diff_report": self.diff_report.to_dict() if self.diff_report else None,
            "error": self.error,
        }


@dataclass
class PlaybackReport:
    """完整回放报告

    Attributes:
        har_file: 回放的 HAR 文件路径。
        total_entries: 总条目数。
        matched_count: 匹配的条目数。
        failed_count: 不匹配的条目数。
        error_count: 回放执行错误的条目数。
        results: 每个条目的回放结果。
        duration_seconds: 回放总耗时。
        summary: 人类可读摘要。
    """

    har_file: str = ""
    total_entries: int = 0
    matched_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    results: list[PlaybackResult] = field(default_factory=list)
    duration_seconds: float = 0.0
    summary: str = ""

    @property
    def pass_rate(self) -> float:
        if self.total_entries == 0:
            return 100.0
        return round(self.matched_count / self.total_entries * 100, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "har_file": self.har_file,
            "total_entries": self.total_entries,
            "matched_count": self.matched_count,
            "failed_count": self.failed_count,
            "error_count": self.error_count,
            "pass_rate": self.pass_rate,
            "duration_seconds": round(self.duration_seconds, 2),
            "summary": self.summary,
            "results": [r.to_dict() for r in self.results],
        }


class HARPlayer:
    """HAR 回放引擎

    读取 HAR 文件，使用 HttpClient 重放每个请求，
    通过 DiffEngine 对比录制响应与实际响应。

    使用方式::

        from framework.recorder import HARPlayer
        from framework.client import HttpClient

        player = HARPlayer(client=http_client)
        report = player.replay("recordings/session.har")
        print(f"通过率: {report.pass_rate}%")

    Attributes:
        client: HttpClient 实例，用于发送回放请求。
        diff_engine: 差异引擎（可自定义配置）。
        base_url: 请求基础 URL（替换 HAR 中记录的 URL 前缀）。
    """

    def __init__(
        self,
        client: Any,
        diff_engine: DiffEngine | None = None,
        base_url: str = "",
    ) -> None:
        """初始化回放引擎。

        Args:
            client: HttpClient 实例。
            diff_engine: 差异引擎，为 None 时使用默认配置。
            base_url: 基础 URL，用于替换 HAR 中记录的 URL schema+host。
        """
        self._client = client
        self._diff_engine = diff_engine or DiffEngine()
        self._base_url = base_url

    def replay(
        self,
        har_file: str,
        filter_url: str | None = None,
        filter_method: str | None = None,
        max_entries: int | None = None,
    ) -> PlaybackReport:
        """回放 HAR 文件中的请求并生成差异报告。

        Args:
            har_file: HAR 文件路径。
            filter_url: 仅回放匹配 URL 的请求（支持子串匹配）。
            filter_method: 仅回放指定 HTTP 方法的请求。
            max_entries: 最大回放条目数。

        Returns:
            PlaybackReport 回放报告。
        """
        import time as _time

        start_time = _time.monotonic()

        # 加载 HAR 文件
        har = self._load_har(har_file)
        entries = har.log.entries

        logger.info(
            "playback_started",
            har_file=har_file,
            total_entries=len(entries),
        )

        # 过滤
        entries_to_replay = self._filter_entries(
            entries, filter_url, filter_method, max_entries
        )

        results: list[PlaybackResult] = []
        matched_count = 0
        failed_count = 0
        error_count = 0

        for i, entry in enumerate(entries_to_replay):
            try:
                result = self._replay_entry(i, entry)
                results.append(result)

                if result.matched:
                    matched_count += 1
                elif result.error:
                    error_count += 1
                else:
                    failed_count += 1

                logger.info(
                    "playback_entry",
                    index=i + 1,
                    url=result.url,
                    matched=result.matched,
                )
            except Exception as e:
                logger.error(
                    "playback_entry_error",
                    index=i + 1,
                    url=getattr(entry.request, "url", ""),
                    error=str(e),
                )
                # 创建错误结果
                entry_url = ""
                entry_method = "GET"
                if entry.request:
                    entry_url = entry.request.url
                    entry_method = entry.request.method

                results.append(
                    PlaybackResult(
                        entry_index=i,
                        method=entry_method,
                        url=entry_url,
                        recorded_status=(
                            entry.response.status if entry.response else 0
                        ),
                        actual_status=0,
                        recorded_elapsed_ms=entry.time,
                        diff_report=None,
                        error=f"回放异常: {str(e)}",
                    )
                )
                error_count += 1

        duration = _time.monotonic() - start_time

        total = len(results)
        summary_parts = []
        if total == 0:
            summary_parts.append("无条目")
        else:
            summary_parts.append(
                f"回放 {total} 条: {matched_count} 匹配, {failed_count} 失败, {error_count} 错误"
            )
            summary_parts.append(f"通过率 {round(matched_count / total * 100, 1)}%")

        report = PlaybackReport(
            har_file=har_file,
            total_entries=total,
            matched_count=matched_count,
            failed_count=failed_count,
            error_count=error_count,
            results=results,
            duration_seconds=round(duration, 2),
            summary=" | ".join(summary_parts),
        )

        logger.info(
            "playback_completed",
            total=total,
            matched=matched_count,
            failed=failed_count,
            errors=error_count,
            duration_seconds=round(duration, 2),
        )

        return report

    # ---------- 私有方法 ----------

    def _load_har(self, filepath: str) -> HAR:
        """加载 HAR 文件。"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"HAR 文件不存在: {filepath}")

        raw = json.loads(path.read_text(encoding="utf-8"))

        from framework.recorder.har_models import (
            HAREntry,
            HARLog,
            HARNameValue,
            HARPostData,
            HARRequest,
            HARResponse,
            HARTimings,
        )

        log_data = raw.get("log", {})
        entries: list[HAREntry] = []

        for e in log_data.get("entries", []):
            req_data = e.get("request", {})
            resp_data = e.get("response", {})
            timings_data = e.get("timings", {})

            # 解析 request
            har_request: HARRequest | None = None
            if req_data:
                post_data: HARPostData | None = None
                pd = req_data.get("postData")
                if pd:
                    post_data = HARPostData(
                        mimeType=pd.get("mimeType", ""),
                        text=pd.get("text", ""),
                        params=[
                            HARNameValue(
                                name=p.get("name", ""), value=p.get("value", "")
                            )
                            for p in pd.get("params", [])
                        ],
                    )

                har_request = HARRequest(
                    method=req_data.get("method", "GET"),
                    url=req_data.get("url", ""),
                    httpVersion=req_data.get("httpVersion", "HTTP/1.1"),
                    headers=[
                        HARNameValue(
                            name=h.get("name", ""), value=h.get("value", "")
                        )
                        for h in req_data.get("headers", [])
                    ],
                    queryString=[
                        HARNameValue(
                            name=q.get("name", ""), value=q.get("value", "")
                        )
                        for q in req_data.get("queryString", [])
                    ],
                    postData=post_data,
                    headersSize=req_data.get("headersSize", -1),
                    bodySize=req_data.get("bodySize", -1),
                )

            # 解析 response
            har_response: HARResponse | None = None
            if resp_data:
                har_response = HARResponse(
                    status=resp_data.get("status", 0),
                    statusText=resp_data.get("statusText", ""),
                    httpVersion=resp_data.get("httpVersion", "HTTP/1.1"),
                    headers=[
                        HARNameValue(
                            name=h.get("name", ""), value=h.get("value", "")
                        )
                        for h in resp_data.get("headers", [])
                    ],
                    content=resp_data.get("content", {}),
                    redirectURL=resp_data.get("redirectURL", ""),
                    headersSize=resp_data.get("headersSize", -1),
                    bodySize=resp_data.get("bodySize", -1),
                )

            entries.append(
                HAREntry(
                    startedDateTime=e.get("startedDateTime", ""),
                    time=e.get("time", 0.0),
                    request=har_request,
                    response=har_response,
                    timings=HARTimings(
                        send=timings_data.get("send", 0.0),
                        wait=timings_data.get("wait", 0.0),
                        receive=timings_data.get("receive", 0.0),
                        blocked=timings_data.get("blocked", -1.0),
                        dns=timings_data.get("dns", -1.0),
                        connect=timings_data.get("connect", -1.0),
                        ssl=timings_data.get("ssl", -1.0),
                    ),
                )
            )

        creator_data = log_data.get("creator", {})
        from framework.recorder.har_models import HARCreator

        return HAR(
            log=HARLog(
                version=log_data.get("version", "1.2"),
                creator=HARCreator(
                    name=creator_data.get("name", ""),
                    version=creator_data.get("version", ""),
                    comment=creator_data.get("comment", ""),
                ),
                entries=entries,
                pages=log_data.get("pages", []),
                comment=log_data.get("comment", ""),
            )
        )

    def _filter_entries(
        self,
        entries: list[HAREntry],
        filter_url: str | None,
        filter_method: str | None,
        max_entries: int | None,
    ) -> list[HAREntry]:
        """过滤 HAR 条目。"""
        result = list(entries)

        if filter_url:
            result = [
                e
                for e in result
                if e.request and filter_url in e.request.url
            ]

        if filter_method:
            method_upper = filter_method.upper()
            result = [
                e
                for e in result
                if e.request and e.request.method.upper() == method_upper
            ]

        if max_entries is not None and max_entries > 0:
            result = result[:max_entries]

        return result

    def _replay_entry(self, index: int, entry: HAREntry) -> PlaybackResult:
        """回放单个 HAR 条目。"""
        if entry.request is None:
            return PlaybackResult(
                entry_index=index,
                method="GET",
                url="<no request>",
                error="HAR 条目缺少请求数据",
            )

        har_req = entry.request
        har_resp = entry.response

        # 提取路径和查询参数
        url = har_req.url
        if self._base_url:
            # 替换基础 URL
            url = self._base_url.rstrip("/") + "/" + url.split("/", 3)[-1] if "/" in url else url

        try:
            # 构建 HttpRequest
            method_str = har_req.method.upper()
            try:
                method = HttpMethod(method_str)
            except ValueError:
                logger.warning("unknown_method_in_har", method=method_str)
                method = HttpMethod.GET

            # 提取头部
            headers: dict[str, str] = {}
            for h in har_req.headers:
                headers[h.name] = h.value

            # 提取查询参数
            params: dict[str, Any] = {}
            for q in har_req.queryString:
                params[q.name] = q.value

            # 提取请求体
            body = None
            body_type = BodyType.NONE
            if har_req.postData:
                text = har_req.postData.text
                mime = har_req.postData.mimeType.lower()
                if text:
                    if "json" in mime:
                        try:
                            body = json.loads(text)
                            body_type = BodyType.JSON
                        except json.JSONDecodeError:
                            body = text
                            body_type = BodyType.RAW
                    elif "form" in mime:
                        body = {}
                        for p in har_req.postData.params:
                            body[p.name] = p.value
                        body_type = BodyType.FORM
                    else:
                        body = text
                        body_type = BodyType.RAW

            # 从完整 URL 提取路径
            from urllib.parse import urlparse, parse_qs

            parsed = urlparse(url)
            request_path = parsed.path or url
            if parsed.query:
                request_path = f"{request_path}?{parsed.query}"

            http_req = HttpRequest(
                method=method,
                path=request_path,
                headers=headers,
                params=params,
                body=body,
                body_type=body_type,
            )

            # 发送请求
            response = self._client.request(http_req)

            # 加载录制的响应体
            recorded_body = None
            if har_resp and har_resp.content:
                text = har_resp.content.get("text", "")
                if text:
                    try:
                        recorded_body = json.loads(text)
                    except json.JSONDecodeError:
                        recorded_body = text

            # 差异比较
            recorded_status = har_resp.status if har_resp else 0
            recorded_headers: dict[str, str] = {}
            if har_resp:
                for h in har_resp.headers:
                    recorded_headers[h.name] = h.value

            diff_report = self._diff_engine.compare(
                entry_index=index,
                url=url,
                method=method_str,
                recorded_status=recorded_status,
                actual_status=response.status_code,
                recorded_headers=recorded_headers,
                actual_headers=response.headers,
                recorded_body=recorded_body,
                actual_body=response.body,
            )

            return PlaybackResult(
                entry_index=index,
                method=method_str,
                url=url,
                recorded_status=recorded_status,
                actual_status=response.status_code,
                recorded_elapsed_ms=entry.time,
                actual_elapsed_ms=response.elapsed_ms,
                response_body=response.body,
                diff_report=diff_report,
            )

        except Exception as e:
            logger.error(
                "playback_entry_request_error",
                index=index + 1,
                url=url,
                error=str(e),
            )
            return PlaybackResult(
                entry_index=index,
                method=har_req.method,
                url=url,
                recorded_status=har_resp.status if har_resp else 0,
                error=f"请求执行失败: {str(e)}",
            )
