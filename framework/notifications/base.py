"""通知渠道抽象基类与配置模型

定义了通知系统的核心抽象：
- NotificationChannel: 渠道抽象基类，所有具体渠道需实现此接口
- NotificationRule: 通知触发规则枚举
- NotificationConfig: 单渠道配置数据类
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NotificationRule(str, Enum):
    """通知触发规则

    Attributes:
        ALWAYS: 每次执行完成都发送通知（无论结果）。
        ON_FAILURE: 仅当存在失败用例时发送通知。
        FAILURE_RATE: 仅当失败率超过阈值时发送通知。
    """

    ALWAYS = "always"
    ON_FAILURE = "on_failure"
    FAILURE_RATE = "failure_rate"

    @classmethod
    def from_str(
        cls,
        value: str,
        default: NotificationRule | None = None,
    ) -> NotificationRule:
        """从字符串安全转换

        Args:
            value: 配置字符串值。
            default: 转换失败时的默认值，为 None 时使用 ON_FAILURE。

        Returns:
            对应的 NotificationRule 枚举值。
        """
        if default is None:
            default = cls.ON_FAILURE
        try:
            return cls(value.lower())
        except ValueError:
            return default


@dataclass
class NotificationConfig:
    """单渠道配置

    Attributes:
        enabled: 是否启用此渠道。
        name: 渠道名称（如 "wecom", "dingtalk"）。
        webhook_url: Webhook URL（企业微信/钉钉等）。
        channel_type: 渠道类型标识。
        extra: 渠道特定额外参数（如钉钉的 secret 签名密钥）。
    """

    enabled: bool = False
    name: str = ""
    webhook_url: str = ""
    channel_type: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class NotificationChannel(ABC):
    """通知渠道抽象基类

    所有具体通知渠道（企业微信、钉钉、邮件等）必须继承此类，
    实现 name() 和 send() 方法。

    设计参考 PluginBase 的抽象模式，但独立于插件系统，
    专注于消息发送而非生命周期钩子。

    Usage:
        class WeComChannel(NotificationChannel):
            def name(self) -> str:
                return "wecom"

            async def send(self, title: str, content: str, **kwargs) -> bool:
                # 发送企业微信机器人消息
                ...
    """

    @abstractmethod
    def name(self) -> str:
        """渠道唯一名称，用于配置查找和日志标识"""
        ...

    @abstractmethod
    async def send(self, title: str, content: str, **kwargs: Any) -> bool:
        """发送通知消息

        Args:
            title: 消息标题。
            content: 消息正文（Markdown 格式）。
            **kwargs: 渠道特定参数（如 msgtype）。

        Returns:
            True 表示发送成功，False 表示失败。
        """
        ...

    def is_configured(self) -> bool:
        """检查渠道是否已正确配置（如 webhook URL 是否非空）

        子类可覆盖以添加额外校验（如 API Key 是否存在等）。

        Returns:
            True 表示渠道配置有效，可以发送消息。
        """
        return True
