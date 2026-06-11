"""邮件通知渠道单元测试 (T5-09)

测试覆盖：
- EmailChannel 初始化与 is_configured 校验
- send() 未配置时返回 False
- send() 发送成功场景（mock smtplib）
- send() 发送失败场景（SMTPException / OSError / TimeoutError）
- HTML 邮件正文生成（Markdown → HTML 转换）
- 标题/粗体/斜体/代码/列表/链接等 Markdown 元素
- SSL/TLS 连接模式
- 多收件人支持
"""

from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from framework.notifications.email_channel import (
    EmailChannel,
    _escape_html,
    _inline_md,
    _markdown_to_html,
)


# ── EmailChannel 基础测试 ────────────────────────────────


class TestEmailChannelInit:
    """初始化与配置校验."""

    def test_default_values(self) -> None:
        """默认值."""
        ch = EmailChannel()
        assert ch.name() == "email"
        assert ch._smtp_port == 587
        assert ch._use_tls is True
        assert ch._use_ssl is False
        assert ch._to_addrs == []

    def test_full_config(self) -> None:
        """完整配置."""
        ch = EmailChannel(
            smtp_host="smtp.example.com",
            smtp_port=465,
            username="user",
            password="pass",
            from_addr="from@test.com",
            to_addrs=["to@test.com"],
            use_tls=False,
            use_ssl=True,
        )
        assert ch._smtp_host == "smtp.example.com"
        assert ch._smtp_port == 465
        assert ch._use_ssl is True

    def test_is_configured_true(self) -> None:
        """所有必要参数已配置."""
        ch = EmailChannel(
            smtp_host="smtp.example.com",
            from_addr="from@test.com",
            to_addrs=["to@test.com"],
        )
        assert ch.is_configured() is True

    def test_is_configured_false_missing_host(self) -> None:
        """缺少 host."""
        ch = EmailChannel(from_addr="from@test.com", to_addrs=["to@test.com"])
        assert ch.is_configured() is False

    def test_is_configured_false_missing_from(self) -> None:
        """缺少 from_addr."""
        ch = EmailChannel(smtp_host="smtp.example.com", to_addrs=["to@test.com"])
        assert ch.is_configured() is False

    def test_is_configured_false_missing_to(self) -> None:
        """缺少 to_addrs."""
        ch = EmailChannel(smtp_host="smtp.example.com", from_addr="from@test.com")
        assert ch.is_configured() is False


# ── send() 测试（mock SMTP）─────────────────────────────


class TestEmailChannelSend:
    """send() 方法测试."""

    @pytest.fixture
    def channel(self) -> EmailChannel:
        return EmailChannel(
            smtp_host="smtp.test.local",
            smtp_port=587,
            username="user",
            password="pass",
            from_addr="from@test.com",
            to_addrs=["to1@test.com", "to2@test.com"],
        )

    @pytest.mark.asyncio
    async def test_send_not_configured_returns_false(self) -> None:
        """未配置时返回 False."""
        ch = EmailChannel()
        result = await ch.send("title", "content")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self, channel: EmailChannel) -> None:
        """发送成功返回 True."""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            mock_server.__enter__ = MagicMock(return_value=mock_server)
            mock_server.__exit__ = MagicMock(return_value=False)

            result = await channel.send("测试标题", "**测试内容**")
            assert result is True

    @pytest.mark.asyncio
    async def test_send_with_ssl(self) -> None:
        """SSL 模式（port 465）."""
        ch = EmailChannel(
            smtp_host="smtp.test.local",
            smtp_port=465,
            from_addr="from@test.com",
            to_addrs=["to@test.com"],
            use_ssl=True,
        )
        with patch("smtplib.SMTP_SSL") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            mock_server.__enter__ = MagicMock(return_value=mock_server)
            mock_server.__exit__ = MagicMock(return_value=False)

            result = await ch.send("SSL Test", "content")
            assert result is True
            mock_smtp.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_smtp_exception_returns_false(self, channel: EmailChannel) -> None:
        """SMTPException 时返回 False."""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = smtplib.SMTPException("Connection refused")

            result = await channel.send("title", "content")
            assert result is False

    @pytest.mark.asyncio
    async def test_send_oserror_returns_false(self, channel: EmailChannel) -> None:
        """OSError 时返回 False."""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = OSError("Network unreachable")

            result = await channel.send("title", "content")
            assert result is False

    @pytest.mark.asyncio
    async def test_send_timeout_returns_false(self, channel: EmailChannel) -> None:
        """TimeoutError 时返回 False."""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = TimeoutError("Connection timed out")

            result = await channel.send("title", "content")
            assert result is False

    @pytest.mark.asyncio
    async def test_send_unexpected_exception_returns_false(self, channel: EmailChannel) -> None:
        """未知异常时返回 False（不抛异常）."""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = RuntimeError("Unexpected")

            result = await channel.send("title", "content")
            assert result is False

    @pytest.mark.asyncio
    async def test_send_calls_starttls(self, channel: EmailChannel) -> None:
        """STARTTLS 被调用."""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            mock_server.__enter__ = MagicMock(return_value=mock_server)
            mock_server.__exit__ = MagicMock(return_value=False)

            await channel.send("title", "content")
            mock_server.starttls.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_calls_login(self, channel: EmailChannel) -> None:
        """SMTP 登录被调用."""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            mock_server.__enter__ = MagicMock(return_value=mock_server)
            mock_server.__exit__ = MagicMock(return_value=False)

            await channel.send("title", "content")
            mock_server.login.assert_called_once_with("user", "pass")

    @pytest.mark.asyncio
    async def test_send_without_auth(self) -> None:
        """无用户名密码时不调用 login."""
        ch = EmailChannel(
            smtp_host="smtp.test.local",
            from_addr="from@test.com",
            to_addrs=["to@test.com"],
            username="",
            password="",
        )
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            mock_server.__enter__ = MagicMock(return_value=mock_server)
            mock_server.__exit__ = MagicMock(return_value=False)

            await ch.send("title", "content")
            mock_server.login.assert_not_called()


# ── HTML 生成测试 ────────────────────────────────────────


class TestHtmlGeneration:
    """HTML 邮件正文生成测试."""

    def test_build_html_contains_title(self) -> None:
        """HTML 包含标题."""
        html = EmailChannel._build_html("测试报告", "内容")
        assert "测试报告" in html

    def test_build_html_contains_content(self) -> None:
        """HTML 包含正文."""
        html = EmailChannel._build_html("title", "hello world")
        assert "hello world" in html

    def test_build_html_has_structure(self) -> None:
        """HTML 有基本结构."""
        html = EmailChannel._build_html("t", "c")
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "<body" in html
        assert "</body>" in html

    def test_markdown_bold(self) -> None:
        """Markdown 粗体 → HTML."""
        result = _markdown_to_html("**bold text**")
        assert "<strong>bold text</strong>" in result

    def test_markdown_italic(self) -> None:
        """Markdown 斜体 → HTML."""
        result = _markdown_to_html("*italic*")
        assert "<em>italic</em>" in result

    def test_markdown_heading(self) -> None:
        """Markdown 标题 → HTML."""
        result = _markdown_to_html("## 二级标题")
        assert "<h2>二级标题</h2>" in result

        result = _markdown_to_html("### 三级标题")
        assert "<h3>三级标题</h3>" in result

    def test_markdown_unordered_list(self) -> None:
        """Markdown 无序列表 → HTML."""
        result = _markdown_to_html("- item1\n- item2")
        assert "<ul" in result
        assert "<li>item1</li>" in result
        assert "<li>item2</li>" in result
        assert "</ul>" in result

    def test_markdown_ordered_list(self) -> None:
        """Markdown 有序列表 → HTML."""
        result = _markdown_to_html("1. first\n2. second")
        assert "<ol" in result
        assert "<li>first</li>" in result
        assert "<li>second</li>" in result
        assert "</ol>" in result

    def test_markdown_inline_code(self) -> None:
        """Markdown 行内代码 → HTML."""
        result = _markdown_to_html("use `code()` function")
        assert "<code" in result
        assert "code()" in result

    def test_inline_md_combined(self) -> None:
        """组合行内标记."""
        result = _inline_md("**bold** and *italic* and `code`")
        assert "<strong>bold</strong>" in result
        assert "<em>italic</em>" in result
        assert "<code" in result

    def test_escape_html_chars(self) -> None:
        """HTML 特殊字符转义."""
        result = _escape_html("<script>alert('xss')</script>")
        assert "&lt;script&gt;" in result
        assert "<script>" not in result


# ── 集成场景测试 ──────────────────────────────────────────


class TestIntegrationScenarios:
    """集成场景测试."""

    @pytest.mark.asyncio
    async def test_send_with_report_content(self) -> None:
        """发送包含报告内容的邮件."""
        ch = EmailChannel(
            smtp_host="smtp.test.local",
            from_addr="autotest@test.com",
            to_addrs=["team@test.com"],
        )
        content = """## 测试报告

**环境**: dev
**时间**: 2026-06-11 12:00

### 结果概览

- 总计: 10
- 通过: 8
- 失败: 2

### 失败用例

1. test_login
2. test_checkout
"""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            mock_server.__enter__ = MagicMock(return_value=mock_server)
            mock_server.__exit__ = MagicMock(return_value=False)

            result = await ch.send("API 自动化测试报告 [dev]", content)
            assert result is True
            # 验证 send_message 被调用
            mock_server.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_recipients(self) -> None:
        """多收件人."""
        ch = EmailChannel(
            smtp_host="smtp.test.local",
            from_addr="from@test.com",
            to_addrs=["a@test.com", "b@test.com", "c@test.com"],
        )
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            mock_server.__enter__ = MagicMock(return_value=mock_server)
            mock_server.__exit__ = MagicMock(return_value=False)

            result = await ch.send("title", "content")
            assert result is True
