"""钉钉机器人通知渠道

通过钉钉群机器人 Webhook 发送 Markdown 格式消息。

Webhook URL 格式:
    https://oapi.dingtalk.com/robot/send?access_token=xxxxx

支持加签安全模式（secret）。

参考文档: https://open.dingtalk.com/document/orgapp/custom-robot-access
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any
from urllib.parse import quote_plus

import httpx

from framework.notifications.webhook_channel import WebhookChannel


class DingTalkChannel(WebhookChannel):
    """钉钉群机器人 Webhook 通知渠道

    通过钉钉群机器人的 Webhook URL 发送 Markdown 格式通知消息。
    支持加签安全模式，自动在每次发送时计算签名并拼接到 URL。

    Attributes:
        _secret: 加签密钥（SEC 开头），为空字符串表示不使用加签。
    """

    def __init__(
        self,
        webhook_url: str,
        secret: str = "",
        timeout: float = 10.0,
    ) -> None:
        """
        Args:
            webhook_url: 钉钉机器人 Webhook URL。
            secret: 加签密钥（SEC 开头的字符串），为空则不使用加签。
            timeout: HTTP 请求超时秒数。
        """
        super().__init__(webhook_url, timeout)
        self._secret = secret

    def name(self) -> str:
        return "dingtalk"

    def _get_url(self, **kwargs: Any) -> str:
        """获取带签名时间戳的 Webhook URL

        钉钉加签规则：
        1. 将 timestamp + "\n" + secret 作为签名字符串
        2. 使用 HMAC-SHA256 算法计算签名
        3. 对签名结果进行 Base64 编码
        4. 对 URL 进行 URL 编码
        5. 拼接到原始 Webhook URL

        Returns:
            带签名的完整 Webhook URL。
        """
        if not self._secret:
            return self._webhook_url

        timestamp = str(round(time.time() * 1000))
        secret_enc = self._secret.encode("utf-8")
        string_to_sign = f"{timestamp}\n{self._secret}"
        string_to_sign_enc = string_to_sign.encode("utf-8")
        hmac_code = hmac.new(
            secret_enc, string_to_sign_enc, digestmod=hashlib.sha256
        ).digest()
        sign = quote_plus(base64.b64encode(hmac_code))
        return f"{self._webhook_url}&timestamp={timestamp}&sign={sign}"

    def _verify_response(self, response: httpx.Response) -> bool:
        """校验钉钉 API 响应

        除 HTTP 状态码外，还需检查 errcode 字段。

        Args:
            response: httpx 响应对象。

        Returns:
            True 表示发送成功，False 表示失败。
        """
        if not response.is_success:
            self._logger.warning(
                "notification_failed",
                channel=self.name(),
                status_code=response.status_code,
                response_body=response.text[:500],
            )
            return False

        try:
            body = response.json()
            if body.get("errcode") == 0:
                self._logger.info(
                    "notification_sent",
                    channel=self.name(),
                    status_code=response.status_code,
                )
                return True
            else:
                self._logger.warning(
                    "dingtalk_api_error",
                    errcode=body.get("errcode"),
                    errmsg=body.get("errmsg", ""),
                )
                return False
        except Exception:
            self._logger.warning(
                "dingtalk_response_parse_failed",
                body=response.text[:200],
            )
            return False

    def _build_payload(self, title: str, content: str, **kwargs: Any) -> dict[str, Any]:
        """构建钉钉机器人 Markdown 消息格式

        Args:
            title: 消息标题。
            content: Markdown 正文。
            **kwargs: 额外参数（is_at_all, at_mobiles）。

        Returns:
            钉钉 Webhook POST 的 JSON payload。
        """
        at_info: dict[str, Any] = {}
        if kwargs.get("is_at_all", False):
            at_info["isAtAll"] = True
        mobiles = kwargs.get("at_mobiles", [])
        if mobiles:
            at_info["atMobiles"] = mobiles  # type: ignore[assignment]

        payload: dict[str, Any] = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content,
            },
        }
        if at_info:
            payload["at"] = at_info  # type: ignore[assignment]

        return payload
