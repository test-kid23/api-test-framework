"""通知服务 — 规则评估、消息格式化、渠道分发

NotificationService 是通知模块的编排层，负责：
1. 根据 SuiteResult 评估通知规则（ALWAYS / ON_FAILURE / FAILURE_RATE）
2. 构建标准化的 Markdown 格式执行摘要消息
3. 异步分发到所有已启用的通知渠道
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from framework.models import CaseResult, SuiteResult
from framework.notifications.base import (
    NotificationChannel,
    NotificationConfig,
    NotificationRule,
)
from framework.utils.logger import Logger

logger = Logger.get("notifications.service")


@dataclass
class ServiceConfig:
    """通知服务全局配置

    Attributes:
        enabled: 是否启用通知。
        rule: 通知触发规则。
        failure_threshold: 失败率阈值（0.0~1.0），仅在 rule 为 FAILURE_RATE 时生效。
        report_url: 报告链接，将嵌入通知消息中。
        env_name: 当前环境名称。
    """

    enabled: bool = False
    rule: NotificationRule = NotificationRule.ON_FAILURE
    failure_threshold: float = 0.0
    report_url: str = ""
    env_name: str = ""


class NotificationService:
    """通知服务 — 编排通知规则评估与多渠道分发

    使用方式：
        service = NotificationService(
            config=ServiceConfig(enabled=True, rule=NotificationRule.ON_FAILURE),
            channels=[wecom_channel, dingtalk_channel],
        )
        await service.notify(suite_result)

    与 TestRunner 集成：
        在 run_suite() 完成后调用 service.notify(suite_result) 即可。
    """

    def __init__(
        self,
        config: ServiceConfig | None = None,
        channels: list[NotificationChannel] | None = None,
    ) -> None:
        """
        Args:
            config: 服务全局配置。
            channels: 已初始化的通知渠道列表。
        """
        self._config = config or ServiceConfig()
        self._channels: list[NotificationChannel] = channels or []

    # ── 公共方法 ────────────────────────────────────────

    def add_channel(self, channel: NotificationChannel) -> None:
        """注册通知渠道

        Args:
            channel: 通知渠道实例。
        """
        self._channels.append(channel)
        logger.debug("channel_added", name=channel.name())

    async def notify(self, suite_result: SuiteResult) -> bool:
        """评估通知规则并发送通知

        Args:
            suite_result: 测试套件执行结果。

        Returns:
            True 表示通知已发送或被正确跳过，False 表示全部渠道发送失败。
        """
        if not self._config.enabled:
            logger.debug("notifications_disabled")
            return False

        if not self._should_notify(suite_result):
            logger.debug("notification_skipped_by_rule", rule=self._config.rule.value)
            return False

        active_channels = [ch for ch in self._channels if ch.is_configured()]
        if not active_channels:
            logger.warning("no_active_notification_channels")
            return False

        title = self._build_title(suite_result)
        content = self._build_content(suite_result)

        send_tasks = [channel.send(title, content) for channel in active_channels]
        results = await asyncio.gather(*send_tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        logger.info(
            "notification_dispatch_complete",
            total=len(active_channels),
            success=success_count,
            failed=len(active_channels) - success_count,
        )
        return success_count > 0

    async def notify_result(
        self,
        suite_name: str,
        total: int,
        passed: int,
        failed: int,
        failed_cases: list[dict[str, str]] | None = None,
    ) -> bool:
        """无需 SuiteResult 对象，直接传结果数据触发通知

        适用于 conftest 等没有完整 SuiteResult 的场景。

        Args:
            suite_name: 套件名称。
            total: 总用例数。
            passed: 通过数。
            failed: 失败数。
            failed_cases: 失败用例列表，每项含 "name" 和 "error" 键。

        Returns:
            True 表示通知已发送。
        """
        if not self._config.enabled:
            return False

        # 快速规则校验
        if total == 0:
            return False

        failure_rate = failed / total if total > 0 else 0.0
        rule = self._config.rule

        if rule == NotificationRule.ON_FAILURE and failed == 0:
            return False
        if rule == NotificationRule.FAILURE_RATE and failure_rate <= self._config.failure_threshold:
            return False

        active_channels = [ch for ch in self._channels if ch.is_configured()]
        if not active_channels:
            return False

        content = self._build_content_from_raw(
            suite_name=suite_name,
            total=total,
            passed=passed,
            failed=failed,
            failed_cases=failed_cases or [],
        )

        title = f"测试执行报告 - {suite_name}"
        send_tasks = [channel.send(title, content) for channel in active_channels]
        results = await asyncio.gather(*send_tasks, return_exceptions=True)

        return any(r is True for r in results)

    # ── 通用告警 ────────────────────────────────────────

    async def send_alert(
        self,
        title: str,
        level: str,
        message: str,
        channels: list[str] | None = None,
    ) -> bool:
        """发送通用告警通知（不依赖 SuiteResult）

        适用于调度失败、Worker 宕机等非执行结果的告警场景。

        Args:
            title: 告警标题。
            level: 告警级别（info / warning / error / critical）。
            message: 告警消息正文（Markdown 格式）。
            channels: 目标渠道名称列表（如 ["wecom", "email"]），
                      为 None 时发送到所有已配置的渠道。

        Returns:
            True 表示至少有一个渠道发送成功。
        """
        if not self._config.enabled:
            logger.debug("alert_disabled")
            return False

        active_channels = [ch for ch in self._channels if ch.is_configured()]
        if not active_channels:
            logger.warning("no_active_alert_channels")
            return False

        # 渠道过滤
        if channels:
            active_channels = [
                ch for ch in active_channels if ch.name() in channels
            ]
            if not active_channels:
                logger.warning(
                    "alert_no_matching_channels",
                    requested=channels,
                )
                return False

        level_icon = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🔥"}.get(
            level, "📢"
        )
        full_title = f"{level_icon} {title}"
        full_content = f"## {level.upper()}: {title}\n\n{message}"

        send_tasks = [channel.send(full_title, full_content) for channel in active_channels]
        results = await asyncio.gather(*send_tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        logger.info(
            "alert_dispatch_complete",
            title=title,
            level=level,
            total=len(active_channels),
            success=success_count,
        )
        return success_count > 0

    # ── 工厂方法 ────────────────────────────────────────

    @classmethod
    def from_config(
        cls,
        notifications_config: dict[str, Any],
        env_name: str = "",
    ) -> NotificationService:
        """从配置字典构建 NotificationService

        Args:
            notifications_config: YAML 配置中的 notifications 节点。
            env_name: 当前环境名称。

        Returns:
            已配置的 NotificationService 实例。
        """
        service_config = cls._parse_service_config(notifications_config, env_name)
        channels = cls._build_channels(notifications_config)

        return cls(config=service_config, channels=channels)

    # ── 规则评估 ────────────────────────────────────────

    def _should_notify(self, result: SuiteResult) -> bool:
        """评估是否应发送通知

        Args:
            result: 套件执行结果。

        Returns:
            True 表示应发送通知。
        """
        rule = self._config.rule

        if rule == NotificationRule.ALWAYS:
            return True

        if rule == NotificationRule.ON_FAILURE:
            return result.failed_count > 0

        if rule == NotificationRule.FAILURE_RATE:
            if result.total == 0:
                return False
            failure_rate = result.failed_count / result.total
            return failure_rate > self._config.failure_threshold

        return False

    # ── 消息构建 ────────────────────────────────────────

    def _build_title(self, result: SuiteResult) -> str:
        """构建通知标题

        Args:
            result: 套件执行结果。

        Returns:
            通知消息标题。
        """
        status_icon = "✅" if result.passed else "❌"
        return f"{status_icon} 测试执行报告 - {result.suite_name}"

    def _build_content(self, result: SuiteResult) -> str:
        """构建 Markdown 格式的执行摘要消息

        Args:
            result: 套件执行结果。

        Returns:
            Markdown 格式的完整通知消息。
        """
        return self._build_content_from_raw(
            suite_name=result.suite_name,
            total=result.total,
            passed=result.passed_count,
            failed=result.failed_count,
            failed_cases=[
                {"name": r.case_name, "error": r.error or "未知错误"}
                for r in result.case_results
                if not r.passed
            ],
        )

    def _build_content_from_raw(
        self,
        suite_name: str,
        total: int,
        passed: int,
        failed: int,
        failed_cases: list[dict[str, str]],
    ) -> str:
        """从原始数据构建 Markdown 格式消息

        Args:
            suite_name: 套件名称。
            total: 总用例数。
            passed: 通过数。
            failed: 失败数。
            failed_cases: 失败用例列表。

        Returns:
            Markdown 格式的完整通知消息。
        """
        pass_rate = (passed / total * 100) if total > 0 else 0.0
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # 构建消息
        lines: list[str] = []

        # ── 执行摘要 ──
        lines.append("# 测试执行报告")
        lines.append(f"> 套件: **{suite_name}**")
        lines.append(f"> 环境: **{self._config.env_name}**")
        lines.append(f"> 时间: {timestamp}")
        lines.append("")
        lines.append(f"## 总体状态: {'✅ 全部通过' if failed == 0 else '❌ 存在失败'}")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 总计 | {total} |")
        lines.append(f"| 通过 | {passed} |")
        lines.append(f"| 失败 | {failed} |")
        lines.append(f"| 通过率 | {pass_rate:.1f}% |")

        # ── 失败用例 ──
        if failed_cases:
            lines.append("")
            lines.append("## ❌ 失败用例")
            # 最多展示 10 个失败用例，避免消息过长
            display_count = min(len(failed_cases), 10)
            for i, case in enumerate(failed_cases[:display_count]):
                case_name = case.get("name", "未知")
                error = case.get("error", "").replace("\n", " ")
                # 截断过长错误信息
                if len(error) > 120:
                    error = error[:120] + "..."
                lines.append(f"{i + 1}. **{case_name}**")
                lines.append(f"   > {error}")
                lines.append("")

            if len(failed_cases) > display_count:
                lines.append(f"> ... 还有 {len(failed_cases) - display_count} 个失败用例")

        # ── Setup/Teardown 错误 ──
        # 这里没法从 raw 数据获取，由 _build_content 添加
        # （两个方法的调用场景不同）

        # ── 报告链接 ──
        if self._config.report_url:
            lines.append("")
            lines.append(f"[📊 查看完整报告]({self._config.report_url})")

        return "\n".join(lines)

    # ── 配置解析 ────────────────────────────────────────

    @staticmethod
    def _parse_service_config(
        raw: dict[str, Any],
        env_name: str,
    ) -> ServiceConfig:
        """从原始配置字典解析 ServiceConfig

        Args:
            raw: notifications 配置节点。
            env_name: 环境名称。

        Returns:
            ServiceConfig 实例。
        """
        rule_str = raw.get("rule", "on_failure")
        return ServiceConfig(
            enabled=raw.get("enabled", False),
            rule=NotificationRule.from_str(rule_str),
            failure_threshold=float(raw.get("failure_threshold", 0.0)),
            report_url=str(raw.get("report_url", "")),
            env_name=env_name,
        )

    @staticmethod
    def _build_channels(raw: dict[str, Any]) -> list[NotificationChannel]:
        """从配置字典构建渠道实例

        Args:
            raw: notifications 配置节点。

        Returns:
            已初始化的渠道实例列表。
        """
        channels: list[NotificationChannel] = []
        channel_configs = raw.get("channels", {})

        # ── 企业微信 ──
        wecom_cfg = channel_configs.get("wecom", {})
        if wecom_cfg.get("enabled", False) and wecom_cfg.get("webhook_url"):
            from framework.notifications.wecom_channel import WeComChannel

            channels.append(WeComChannel(webhook_url=wecom_cfg["webhook_url"]))
            logger.info("channel_loaded", name="wecom")

        # ── 钉钉 ──
        dingtalk_cfg = channel_configs.get("dingtalk", {})
        if dingtalk_cfg.get("enabled", False) and dingtalk_cfg.get("webhook_url"):
            from framework.notifications.dingtalk_channel import DingTalkChannel

            channels.append(
                DingTalkChannel(
                    webhook_url=dingtalk_cfg["webhook_url"],
                    secret=dingtalk_cfg.get("secret", ""),
                )
            )
            logger.info("channel_loaded", name="dingtalk")

        # ── 邮件（仅当完整配置时才启用） ──
        email_cfg = channel_configs.get("email", {})
        if (
            email_cfg.get("enabled", False)
            and email_cfg.get("smtp_host")
            and email_cfg.get("from_addr")
            and email_cfg.get("to_addrs")
        ):
            from framework.notifications.email_channel import EmailChannel

            channels.append(
                EmailChannel(
                    smtp_host=email_cfg["smtp_host"],
                    smtp_port=email_cfg.get("smtp_port", 587),
                    username=email_cfg.get("username", ""),
                    password=email_cfg.get("password", ""),
                    from_addr=email_cfg["from_addr"],
                    to_addrs=email_cfg.get("to_addrs", []),
                    use_tls=email_cfg.get("use_tls", True),
                )
            )
            logger.info("channel_loaded", name="email")

        return channels
