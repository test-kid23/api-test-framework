"""邮件通知渠道

通过 SMTP 发送测试执行报告邮件，支持 HTML 格式正文和 TLS/SSL 加密。

Usage:
    channel = EmailChannel(
        smtp_host="smtp.example.com",
        smtp_port=587,
        username="user@example.com",
        password="app-password",
        from_addr="autotest@example.com",
        to_addrs=["team@example.com"],
    )
    await channel.send("测试报告", "3/5 通过")
"""

from __future__ import annotations

import asyncio
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from framework.notifications.base import NotificationChannel
from framework.utils.logger import Logger


class EmailChannel(NotificationChannel):
    """邮件通知渠道

    通过 SMTP 发送测试报告邮件，支持：
    - STARTTLS（port 587）和 SSL（port 465）
    - HTML 邮件正文（自动从 Markdown 转换）
    - 异步发送（asyncio.to_thread）
    - 发送失败自动降级（返回 False，不抛异常）

    Attributes:
        _smtp_host: SMTP 服务器地址。
        _smtp_port: SMTP 端口（默认 587）。
        _username: SMTP 登录用户名。
        _password: SMTP 登录密码。
        _from_addr: 发件人地址。
        _to_addrs: 收件人地址列表。
        _use_tls: 是否使用 TLS（STARTTLS 或 SSL）。
        _use_ssl: 是否使用 SSL（port 465 直连加密）。
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
        use_ssl: bool = False,
    ) -> None:
        """
        Args:
            smtp_host: SMTP 服务器地址。
            smtp_port: SMTP 端口，默认 587（STARTTLS）。
            username: SMTP 登录用户名。
            password: SMTP 登录密码。
            from_addr: 发件人邮箱。
            to_addrs: 收件人邮箱列表。
            use_tls: 是否使用 STARTTLS。
            use_ssl: 是否使用 SSL 直连（port 465），优先级高于 use_tls。
        """
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._username = username
        self._password = password
        self._from_addr = from_addr
        self._to_addrs = to_addrs or []
        self._use_tls = use_tls
        self._use_ssl = use_ssl
        self._logger = Logger.get("notifications.email")

    def name(self) -> str:
        return "email"

    def is_configured(self) -> bool:
        """检查 SMTP 参数是否已配置."""
        return bool(self._smtp_host and self._from_addr and self._to_addrs)

    async def send(self, title: str, content: str, **kwargs: Any) -> bool:
        """发送邮件通知.

        Args:
            title: 邮件标题。
            content: 邮件正文（Markdown 格式，自动转换为 HTML）。
            **kwargs: 额外参数（保留兼容性）。

        Returns:
            True 表示发送成功，False 表示失败。
        """
        if not self.is_configured():
            self._logger.debug(
                "email_not_configured",
                reason="SMTP parameters missing",
            )
            return False

        html_body = self._build_html(title, content)

        try:
            await asyncio.to_thread(
                self._send_sync, title, html_body,
            )
            self._logger.info(
                "email_sent",
                to_count=len(self._to_addrs),
                title=title,
            )
            return True
        except (smtplib.SMTPException, OSError, TimeoutError) as e:
            self._logger.error(
                "email_send_failed",
                error=str(e),
                host=self._smtp_host,
                port=self._smtp_port,
            )
            return False
        except Exception as e:
            self._logger.error(
                "email_send_unexpected_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    # ── 内部方法 ──────────────────────────────────────

    def _send_sync(self, title: str, html_body: str) -> None:
        """同步 SMTP 发送（由 asyncio.to_thread 调用）.

        Args:
            title: 邮件标题。
            html_body: HTML 正文。

        Raises:
            smtplib.SMTPException: SMTP 协议错误。
            OSError: 网络错误。
            TimeoutError: 连接超时。
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = title
        msg["From"] = self._from_addr
        msg["To"] = ", ".join(self._to_addrs)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        if self._use_ssl:
            # SMTPS: 直接 SSL 连接（port 465）
            server = smtplib.SMTP_SSL(
                host=self._smtp_host,
                port=self._smtp_port,
                timeout=15,
            )
        else:
            server = smtplib.SMTP(
                host=self._smtp_host,
                port=self._smtp_port,
                timeout=15,
            )

        try:
            if not self._use_ssl and self._use_tls:
                server.starttls()

            if self._username and self._password:
                server.login(self._username, self._password)

            server.send_message(msg)
        finally:
            try:
                server.quit()
            except Exception:
                pass

    @staticmethod
    def _build_html(title: str, content: str) -> str:
        """将 Markdown 内容转换为 HTML 邮件正文.

        生成带内联样式的 HTML 邮件，在大多数邮件客户端中显示良好。

        Args:
            title: 邮件标题（用作 h1）。
            content: Markdown 格式的正文内容。

        Returns:
            完整的 HTML 文档字符串。
        """
        # 简单 Markdown → HTML 转换
        html_content = _markdown_to_html(content)

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
             max-width: 700px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 24px; border-radius: 8px 8px 0 0;">
        <h1 style="color: #fff; margin: 0; font-size: 20px;">{_escape_html(title)}</h1>
    </div>
    <div style="background: #fff; padding: 24px; border: 1px solid #e0e0e0;
                border-top: none; border-radius: 0 0 8px 8px; line-height: 1.6;">
        {html_content}
    </div>
    <div style="text-align: center; margin-top: 16px; color: #999; font-size: 12px;">
        AutoTest Framework · 自动发送
    </div>
</body>
</html>"""


# ── 简易 Markdown → HTML 转换 ─────────────────────────


def _markdown_to_html(md: str) -> str:
    """将 Markdown 文本转换为 HTML（轻量实现，无外部依赖）.

    支持：
    - **粗体** / *斜体*
    - # 标题（h2-h4）
    - - 无序列表
    - 1. 有序列表
    - `代码`
    - 换行 → <br>

    Args:
        md: Markdown 格式文本。

    Returns:
        HTML 字符串。
    """
    lines = md.split("\n")
    result: list[str] = []
    in_ul = False
    in_ol = False

    for line in lines:
        stripped = line.strip()

        # 空行：关闭列表
        if not stripped:
            if in_ul:
                result.append("</ul>")
                in_ul = False
            if in_ol:
                result.append("</ol>")
                in_ol = False
            result.append("<br>")
            continue

        # 标题
        if stripped.startswith("#### "):
            result.append(f"<h4>{_inline_md(stripped[5:])}</h4>")
            continue
        if stripped.startswith("### "):
            result.append(f"<h3>{_inline_md(stripped[4:])}</h3>")
            continue
        if stripped.startswith("## "):
            result.append(f"<h2>{_inline_md(stripped[3:])}</h2>")
            continue
        if stripped.startswith("# "):
            result.append(f"<h2>{_inline_md(stripped[2:])}</h2>")
            continue

        # 无序列表
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_ul:
                if in_ol:
                    result.append("</ol>")
                    in_ol = False
                result.append('<ul style="padding-left: 20px;">')
                in_ul = True
            result.append(f"<li>{_inline_md(stripped[2:])}</li>")
            continue

        # 有序列表
        ol_match = re.match(r"^(\d+)\.\s+(.+)", stripped)
        if ol_match:
            if not in_ol:
                if in_ul:
                    result.append("</ul>")
                    in_ul = False
                result.append('<ol style="padding-left: 20px;">')
                in_ol = True
            result.append(f"<li>{_inline_md(ol_match.group(2))}</li>")
            continue

        # 关闭列表
        if in_ul:
            result.append("</ul>")
            in_ul = False
        if in_ol:
            result.append("</ol>")
            in_ol = False

        # 普通段落
        result.append(f"<p>{_inline_md(stripped)}</p>")

    # 关闭未关闭的列表
    if in_ul:
        result.append("</ul>")
    if in_ol:
        result.append("</ol>")

    return "\n".join(result)


def _inline_md(text: str) -> str:
    """处理行内 Markdown 标记：粗体、斜体、代码、链接.

    Args:
        text: 行内文本。

    Returns:
        HTML 格式的文本。
    """
    # 粗体 **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # 斜体 *text*
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # 行内代码 `code`
    text = re.sub(
        r"`([^`]+)`",
        r'<code style="background:#f0f0f0;padding:2px 6px;border-radius:3px;font-family:monospace;">\1</code>',
        text,
    )
    return text


def _escape_html(text: str) -> str:
    """转义 HTML 特殊字符.

    Args:
        text: 原始文本。

    Returns:
        转义后的文本。
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
