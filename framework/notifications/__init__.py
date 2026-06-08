"""通知模块 — 多渠道告警通知

提供可扩展的通知渠道抽象和编排服务：
- NotificationService: 规则评估 + 消息格式化 + 渠道分发
- NotificationChannel: 渠道抽象基类
- WeComChannel: 企业微信群机器人
- DingTalkChannel: 钉钉群机器人
- EmailChannel: 邮件通知（骨架）

使用示例:
    from framework.notifications import NotificationService
    from framework.notifications import WeComChannel

    service = NotificationService.from_config(config["notifications"])
    await service.notify(suite_result)
"""

from __future__ import annotations

from framework.notifications.base import (
    NotificationChannel,
    NotificationConfig,
    NotificationRule,
)
from framework.notifications.dingtalk_channel import DingTalkChannel
from framework.notifications.email_channel import EmailChannel
from framework.notifications.service import NotificationService, ServiceConfig
from framework.notifications.webhook_channel import WebhookChannel
from framework.notifications.wecom_channel import WeComChannel

__all__ = [
    "NotificationChannel",
    "NotificationConfig",
    "NotificationRule",
    "NotificationService",
    "ServiceConfig",
    "WebhookChannel",
    "WeComChannel",
    "DingTalkChannel",
    "EmailChannel",
]
