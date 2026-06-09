"""HAR (HTTP Archive) 1.2 数据模型

基于 W3C HAR 1.2 规范 (http://www.softwareishard.com/blog/har-12-spec/)
将 HTTP 请求/响应序列化为标准的 JSON 格式，便于跨工具共享和分析。

HAR 结构::

    {
      "log": {
        "version": "1.2",
        "creator": {"name": "AutoTest", "version": "2.0.0"},
        "entries": [
          {
            "startedDateTime": "ISO8601",
            "request": { ... },
            "response": { ... },
            "timings": { ... },
            "time": 123,
            ...
          }
        ]
      }
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class HARNameValue:
    """HAR 通用键值对（headers / queryString / params）

    Attributes:
        name: 键名。
        value: 键值。
        comment: 可选注释。
    """

    name: str
    value: str
    comment: str = ""


@dataclass
class HARPostData:
    """HAR POST 请求体描述

    Attributes:
        mimeType: 内容类型。
        text: 请求体文本内容。
        params: 表单参数列表（用于 application/x-www-form-urlencoded）。
        comment: 可选注释。
    """

    mimeType: str = "application/json"
    text: str = ""
    params: list[HARNameValue] = field(default_factory=list)
    comment: str = ""


@dataclass
class HARRequest:
    """HAR 请求条目

    Attributes:
        method: HTTP 方法 (GET/POST/...).
        url: 完整的请求 URL.
        httpVersion: HTTP 协议版本.
        cookies: Cookie 列表.
        headers: 请求头列表.
        queryString: URL 查询参数列表.
        postData: POST 请求体（如有）.
        headersSize: 请求头字节数.
        bodySize: 请求体字节数.
        comment: 可选注释.
    """

    method: str
    url: str
    httpVersion: str = "HTTP/1.1"
    cookies: list[HARNameValue] = field(default_factory=list)
    headers: list[HARNameValue] = field(default_factory=list)
    queryString: list[HARNameValue] = field(default_factory=list)
    postData: HARPostData | None = None
    headersSize: int = -1
    bodySize: int = -1
    comment: str = ""


@dataclass
class HARResponse:
    """HAR 响应条目

    Attributes:
        status: HTTP 状态码.
        statusText: 状态文本.
        httpVersion: HTTP 协议版本.
        cookies: Cookie 列表.
        headers: 响应头列表.
        content: 响应体内容（含 mimeType/size/text）.
        redirectURL: 重定向 URL.
        headersSize: 响应头字节数.
        bodySize: 响应体字节数.
        comment: 可选注释.
    """

    status: int
    statusText: str = "OK"
    httpVersion: str = "HTTP/1.1"
    cookies: list[HARNameValue] = field(default_factory=list)
    headers: list[HARNameValue] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    redirectURL: str = ""
    headersSize: int = -1
    bodySize: int = -1
    comment: str = ""


@dataclass
class HARTimings:
    """HAR 时间指标（毫秒）

    Attributes:
        send: 发送请求耗时.
        wait: 等待响应耗时 (TTFB).
        receive: 接收响应耗时.
        blocked: 请求被阻塞的时间.
        dns: DNS 解析耗时.
        connect: TCP 连接耗时.
        ssl: SSL/TLS 握手耗时.
        comment: 可选注释.
    """

    send: float = 0.0
    wait: float = 0.0
    receive: float = 0.0
    blocked: float = -1.0
    dns: float = -1.0
    connect: float = -1.0
    ssl: float = -1.0
    comment: str = ""


@dataclass
class HARPageTimings:
    """HAR 页面加载时间指标

    Attributes:
        onContentLoad: DOMContentLoaded 事件时间（ms）.
        onLoad: onLoad 事件时间（ms）.
        comment: 可选注释.
    """

    onContentLoad: float = -1.0
    onLoad: float = -1.0
    comment: str = ""


@dataclass
class HAREntry:
    """HAR 条目 — 单次请求/响应的完整记录

    Attributes:
        startedDateTime: 请求开始时间（ISO 8601）.
        time: 请求总耗时（ms）.
        request: HTTP 请求快照.
        response: HTTP 响应快照.
        timings: 时间指标明细.
        pageref: 所属页面引用（用于页面级分析）.
        cache: 缓存命中信息（预留）.
        serverIPAddress: 服务器 IP.
        connection: TCP 连接 ID.
        comment: 可选注释.
    """

    startedDateTime: str = ""
    time: float = 0.0
    request: HARRequest | None = None
    response: HARResponse | None = None
    timings: HARTimings = field(default_factory=HARTimings)
    pageref: str = ""
    cache: dict[str, Any] = field(default_factory=dict)
    serverIPAddress: str = ""
    connection: str = ""
    comment: str = ""


@dataclass
class HARCreator:
    """HAR 创建者信息

    Attributes:
        name: 创建者名称.
        version: 创建者版本.
        comment: 可选注释.
    """

    name: str = "AutoTest Framework"
    version: str = "2.0.0"
    comment: str = ""


@dataclass
class HARLog:
    """HAR 日志容器

    Attributes:
        version: HAR 规范版本（固定 1.2）.
        creator: 创建者信息.
        entries: 请求/响应条目列表.
        pages: 页面列表（可选）.
        comment: 可选注释.
    """

    version: str = "1.2"
    creator: HARCreator = field(default_factory=HARCreator)
    entries: list[HAREntry] = field(default_factory=list)
    pages: list[dict[str, Any]] = field(default_factory=list)
    comment: str = ""


@dataclass
class HAR:
    """HAR 文件根结构

    完整的 HTTP Archive 文件顶层对象。

    Attributes:
        log: HAR 日志容器.
    """

    log: HARLog = field(default_factory=HARLog)

    @classmethod
    def create(cls, session_name: str = "Recording Session") -> HAR:
        """创建新的 HAR 实例。

        Args:
            session_name: 录制会话名称。

        Returns:
            初始化的 HAR 对象。
        """
        return cls(
            log=HARLog(
                version="1.2",
                creator=HARCreator(
                    name="AutoTest Framework", version="2.0.0", comment=session_name
                ),
                entries=[],
            )
        )

    def to_dict(self) -> dict[str, Any]:
        """将 HAR 对象序列化为字典（JSON 兼容）。

        Returns:
            HAR JSON 字典结构。
        """
        return {
            "log": {
                "version": self.log.version,
                "creator": {
                    "name": self.log.creator.name,
                    "version": self.log.creator.version,
                    "comment": self.log.creator.comment,
                },
                "entries": [_entry_to_dict(e) for e in self.log.entries],
                "pages": self.log.pages,
                "comment": self.log.comment,
            }
        }

    def add_entry(self, entry: HAREntry) -> None:
        """添加一条录制条目。

        Args:
            entry: HAR 条目。
        """
        self.log.entries.append(entry)


def _entry_to_dict(entry: HAREntry) -> dict[str, Any]:
    """将 HAREntry 序列化为字典。"""
    d: dict[str, Any] = {
        "startedDateTime": entry.startedDateTime,
        "time": entry.time,
        "pageref": entry.pageref,
        "cache": entry.cache,
        "serverIPAddress": entry.serverIPAddress,
        "connection": entry.connection,
        "comment": entry.comment,
    }

    if entry.request:
        d["request"] = _request_to_dict(entry.request)
    if entry.response:
        d["response"] = _response_to_dict(entry.response)
    if entry.timings:
        d["timings"] = {
            "send": entry.timings.send,
            "wait": entry.timings.wait,
            "receive": entry.timings.receive,
            "blocked": entry.timings.blocked,
            "dns": entry.timings.dns,
            "connect": entry.timings.connect,
            "ssl": entry.timings.ssl,
            "comment": entry.timings.comment,
        }

    return d


def _request_to_dict(req: HARRequest) -> dict[str, Any]:
    """将 HARRequest 序列化为字典。"""
    d: dict[str, Any] = {
        "method": req.method,
        "url": req.url,
        "httpVersion": req.httpVersion,
        "cookies": [_nv_to_dict(c) for c in req.cookies],
        "headers": [_nv_to_dict(h) for h in req.headers],
        "queryString": [_nv_to_dict(q) for q in req.queryString],
        "headersSize": req.headersSize,
        "bodySize": req.bodySize,
        "comment": req.comment,
    }
    if req.postData:
        d["postData"] = {
            "mimeType": req.postData.mimeType,
            "text": req.postData.text,
            "params": [_nv_to_dict(p) for p in req.postData.params],
            "comment": req.postData.comment,
        }
    return d


def _response_to_dict(resp: HARResponse) -> dict[str, Any]:
    """将 HARResponse 序列化为字典。"""
    return {
        "status": resp.status,
        "statusText": resp.statusText,
        "httpVersion": resp.httpVersion,
        "cookies": [_nv_to_dict(c) for c in resp.cookies],
        "headers": [_nv_to_dict(h) for h in resp.headers],
        "content": resp.content,
        "redirectURL": resp.redirectURL,
        "headersSize": resp.headersSize,
        "bodySize": resp.bodySize,
        "comment": resp.comment,
    }


def _nv_to_dict(nv: HARNameValue) -> dict[str, str]:
    """将 HARNameValue 序列化为字典。"""
    d: dict[str, str] = {"name": nv.name, "value": nv.value}
    if nv.comment:
        d["comment"] = nv.comment
    return d
