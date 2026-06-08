"""企业微信机器人通知渠道

通过企业微信群机器人 Webhook 发送 Markdown 格式消息。

Webhook URL 格式:
    https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx

参考文档: https://developer.work.weixin.qq.com/document/path/91770
"""

from __future__ import annotations

from typing import Any

from framework.notifications.webhook_channel import WebhookChannel


class WeComChannel(WebhookChannel):
    """企业微信群机器人 Webhook 通知渠道

    通过企业微信群机器人的 Webhook URL 发送 Markdown 格式通知消息。
    支持 @所有人 和内容长度限制（Markdown 最长 4096 字节）。

    Usage:
        channel = WeComChannel(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
        )
        await channel.send(
            title="测试报告",
            content="## 执行摘要\\n> 通过: 8\\n> 失败: 2",
        )
    """

    def name(self) -> str:
        return "wecom"

    def _build_payload(self, title: str, content: str, **kwargs: Any) -> dict[str, Any]:
        """构建企业微信机器人 Markdown 消息格式

        Args:
            title: 消息标题。
            content: Markdown 正文。
            **kwargs: 额外参数（mentioned_list, mentioned_mobile_list）。

        Returns:
            企业微信 Webhook POST 的 JSON payload。
        """
        payload: dict[str, Any] = {
            "msgtype": "markdown",
            "markdown": {
                "content": content,
            },
        }
        if "mentioned_list" in kwargs and kwargs["mentioned_list"]:
            payload["markdown"]["mentioned_list"] = kwargs["mentioned_list"]
        if "mentioned_mobile_list" in kwargs and kwargs["mentioned_mobile_list"]:
            payload["markdown"]["mentioned_mobile_list"] = kwargs["mentioned_mobile_list"]
        return payload
