"""通用 Webhook 通知渠道

基于 httpx 发送 HTTP POST 请求到 Webhook URL 的基类实现。
企业微信、钉钉等具体渠道可继承此类，重写 _build_payload() / _get_url() 适配不同格式。
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from framework.notifications.base import NotificationChannel
from framework.utils.logger import Logger


class WebhookChannel(NotificationChannel):
    """通用 Webhook 通知渠道

    通过 HTTP POST 将消息发送到指定的 Webhook URL。
    子类需实现 _build_payload() 来适配不同平台的消息格式。

    Attributes:
        _webhook_url: Webhook 回调地址。
        _timeout: HTTP 请求超时秒数。
        _logger: 结构化日志实例。
    """

    MAX_CONTENT_CHARS: int = 3500

    def __init__(self, webhook_url: str, timeout: float = 10.0) -> None:
        """
        Args:
            webhook_url: Webhook 回调地址。
            timeout: HTTP 请求超时秒数。
        """
        self._webhook_url = webhook_url
        self._timeout = timeout
        self._logger = Logger.get(f"notifications.{self.name()}")

    def is_configured(self) -> bool:
        """检查 Webhook URL 是否非空"""
        return bool(self._webhook_url)

    async def send(self, title: str, content: str, **kwargs: Any) -> bool:
        """发送 Webhook 消息

        Args:
            title: 消息标题。
            content: 消息正文。
            **kwargs: 传递给 _build_payload 的额外参数。

        Returns:
            True 表示发送成功，False 表示失败。
        """
        # 超长截断
        if len(content) > self.MAX_CONTENT_CHARS:
            content = content[: self.MAX_CONTENT_CHARS - 50] + "\n\n...\n> ⚠️ 内容过长已截断"

        payload = self._build_payload(title, content, **kwargs)
        target_url = self._get_url(**kwargs)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    target_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                return self._verify_response(response)
        except httpx.TimeoutException:
            self._logger.error(
                "notification_timeout",
                channel=self.name(),
                timeout=self._timeout,
            )
            return False
        except Exception as e:
            self._logger.error(
                "notification_error",
                channel=self.name(),
                error=str(e),
            )
            return False

    def _get_url(self, **kwargs: Any) -> str:
        """获取发送目标 URL（子类可覆盖以支持签名等）

        Args:
            **kwargs: 额外参数。

        Returns:
            完整的目标 URL。
        """
        return self._webhook_url

    def _verify_response(self, response: httpx.Response) -> bool:
        """校验 HTTP 响应（子类可覆盖以处理平台特有错误码）

        Args:
            response: httpx 响应对象。

        Returns:
            True 表示发送成功，False 表示失败。
        """
        if response.is_success:
            self._logger.info(
                "notification_sent",
                channel=self.name(),
                status_code=response.status_code,
            )
            return True
        else:
            self._logger.warning(
                "notification_failed",
                channel=self.name(),
                status_code=response.status_code,
                response_body=response.text[:500],
            )
            return False

    def _build_payload(self, title: str, content: str, **kwargs: Any) -> dict[str, Any]:
        """构建请求体（子类覆盖以适配不同平台格式）

        Args:
            title: 消息标题。
            content: 消息正文。
            **kwargs: 额外参数。

        Returns:
            POST 请求的 JSON payload 字典。
        """
        return {
            "title": title,
            "content": content,
        }
