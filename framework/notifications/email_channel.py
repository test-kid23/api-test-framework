"""邮件通知渠道（骨架实现）

通过 SMTP 发送测试执行报告邮件。当前为骨架实现，
需要用户配置 SMTP 服务器参数后方可启用。

Usage:
    channel = EmailChannel(
        smtp_host="smtp.example.com",
        smtp_port=587,
        username="user@example.com",
        password="app-password",
        from_addr="autotest@example.com",
        to_addrs=["team@example.com"],
    )
"""

from __future__ import annotations

from typing import Any

from framework.notifications.base import NotificationChannel
from framework.utils.logger import Logger


class EmailChannel(NotificationChannel):
    """邮件通知渠道（骨架实现）

    通过 SMTP 发送测试报告邮件。
    当前仅提供框架，使用前需要配置 SMTP 参数。

    Attributes:
        _smtp_host: SMTP 服务器地址。
        _smtp_port: SMTP 端口。
        _username: SMTP 登录用户名。
        _password: SMTP 登录密码。
        _from_addr: 发件人地址。
        _to_addrs: 收件人地址列表。
        _use_tls: 是否使用 TLS。
    """

    def __init__(
        self,
        smtp_host: str = "",
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        from_addr: str = "",
        to_addrs: list[str] | None = None,
        use_tls: bool = True,
    ) -> None:
        """
        Args:
            smtp_host: SMTP 服务器地址。
            smtp_port: SMTP 端口，默认 587。
            username: SMTP 登录用户名。
            password: SMTP 登录密码。
            from_addr: 发件人邮箱。
            to_addrs: 收件人邮箱列表。
            use_tls: 是否使用 STARTTLS。
        """
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._username = username
        self._password = password
        self._from_addr = from_addr
        self._to_addrs = to_addrs or []
        self._use_tls = use_tls
        self._logger = Logger.get("notifications.email")

    def name(self) -> str:
        return "email"

    def is_configured(self) -> bool:
        """检查 SMTP 参数是否已配置"""
        return bool(self._smtp_host and self._from_addr and self._to_addrs)

    async def send(self, title: str, content: str, **kwargs: Any) -> bool:
        """发送邮件通知

        当前为骨架实现，返回 False 并记录未配置信息。

        Args:
            title: 邮件标题。
            content: 邮件正文（HTML）。
            **kwargs: 额外参数。

        Returns:
            True 表示发送成功，False 表示失败。
        """
        if not self.is_configured():
            self._logger.debug(
                "email_not_configured",
                reason="SMTP parameters missing",
            )
            return False

        # TODO: 实现 SMTP 发送逻辑
        # import smtplib
        # from email.mime.text import MIMEText
        # ...
        self._logger.warning("email_send_not_implemented")
        return False
