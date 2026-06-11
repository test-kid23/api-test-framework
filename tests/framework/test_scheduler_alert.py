"""调度失败告警单元测试

测试覆盖：
- _send_schedule_failure_alert 正常发送告警
- 通知未启用时跳过告警
- config.yaml 不存在时跳过
- 告警发送异常不抛出
- fire_schedule 中三个失败场景触发告警
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from framework.scheduler import _send_schedule_failure_alert, fire_schedule


class TestSendScheduleFailureAlert:
    """_send_schedule_failure_alert 辅助函数测试."""

    @pytest.fixture
    def notifications_config(self) -> dict:
        return {
            "enabled": True,
            "rule": "on_failure",
            "report_url": "",
            "channels": {
                "wecom": {
                    "enabled": True,
                    "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
                },
            },
        }

    @pytest.fixture
    def config_yaml_content(self, notifications_config: dict) -> str:
        return yaml.dump({"notifications": notifications_config, "project": {"name": "test"}})

    def _patch_notification_service(self) -> tuple[MagicMock, MagicMock]:
        """Helper: patch NotificationService.from_config and return (mock_cls, mock_service)."""
        mock_service = MagicMock()
        mock_service.send_alert = AsyncMock(return_value=True)
        patcher = patch(
            "framework.notifications.NotificationService.from_config",
            return_value=mock_service,
        )
        return patcher, mock_service

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.read_text")
    async def test_sends_alert_successfully(
        self,
        mock_read_text: MagicMock,
        mock_exists: MagicMock,
        config_yaml_content: str,
    ) -> None:
        """正常发送调度失败告警."""
        mock_read_text.return_value = config_yaml_content
        patcher, mock_service = self._patch_notification_service()

        with patcher:
            await _send_schedule_failure_alert(
                schedule_id="sched-123",
                schedule_name="每日回归测试",
                env_name="staging",
                failure_type="suite_not_found",
                detail="套件不存在",
            )

        mock_service.send_alert.assert_called_once()
        call_kwargs = mock_service.send_alert.call_args.kwargs
        assert call_kwargs["level"] == "error"
        assert "每日回归测试" in call_kwargs["title"]
        assert "suite_not_found" in call_kwargs["message"] or "套件不存在" in call_kwargs["message"]

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.read_text")
    async def test_skips_when_notifications_disabled(
        self,
        mock_read_text: MagicMock,
        mock_exists: MagicMock,
    ) -> None:
        """通知未启用时跳过告警."""
        disabled_config = yaml.dump(
            {"notifications": {"enabled": False}, "project": {"name": "test"}}
        )
        mock_read_text.return_value = disabled_config

        await _send_schedule_failure_alert(
            schedule_id="sched-123",
            schedule_name="test",
            env_name="dev",
            failure_type="no_cases",
            detail="无用例",
        )
        # 不应抛出异常，正常返回

    @patch("pathlib.Path.exists", return_value=False)
    async def test_skips_when_config_file_missing(
        self,
        mock_exists: MagicMock,
    ) -> None:
        """config.yaml 不存在时跳过告警."""
        await _send_schedule_failure_alert(
            schedule_id="sched-123",
            schedule_name="test",
            env_name="dev",
            failure_type="no_cases",
            detail="无用例",
        )
        # 不应抛出异常

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.read_text")
    async def test_handles_alert_exception_gracefully(
        self,
        mock_read_text: MagicMock,
        mock_exists: MagicMock,
        config_yaml_content: str,
    ) -> None:
        """告警发送异常不向上传播."""
        mock_read_text.return_value = config_yaml_content
        mock_service = MagicMock()
        mock_service.send_alert = AsyncMock(side_effect=RuntimeError("网络错误"))

        with patch(
            "framework.notifications.NotificationService.from_config",
            return_value=mock_service,
        ):
            # 不应抛出异常
            await _send_schedule_failure_alert(
                schedule_id="sched-123",
                schedule_name="test",
                env_name="dev",
                failure_type="celery_dispatch",
                detail="连接失败",
            )

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.read_text")
    async def test_includes_all_failure_info(
        self,
        mock_read_text: MagicMock,
        mock_exists: MagicMock,
        config_yaml_content: str,
    ) -> None:
        """告警内容包含 schedule_id、错误信息、时间戳."""
        mock_read_text.return_value = config_yaml_content
        mock_service = MagicMock()
        mock_service.send_alert = AsyncMock(return_value=True)

        with patch(
            "framework.notifications.NotificationService.from_config",
            return_value=mock_service,
        ):
            await _send_schedule_failure_alert(
                schedule_id="sched-456",
                schedule_name="冒烟测试",
                env_name="production",
                failure_type="callback_failed",
                detail="数据库连接超时",
            )

        mock_service.send_alert.assert_called_once()
        call_kwargs = mock_service.send_alert.call_args.kwargs
        message = call_kwargs["message"]
        assert "sched-456" in message
        assert "冒烟测试" in message
        assert "production" in message
        assert "数据库连接超时" in message

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.read_text")
    async def test_all_failure_types_have_labels(
        self,
        mock_read_text: MagicMock,
        mock_exists: MagicMock,
        config_yaml_content: str,
    ) -> None:
        """所有四种失败类型都有对应的中文标签."""
        mock_read_text.return_value = config_yaml_content
        mock_service = MagicMock()
        mock_service.send_alert = AsyncMock(return_value=True)

        expected_labels = {
            "suite_not_found": "套件不存在",
            "no_cases": "无用例可执行",
            "celery_dispatch": "Celery 分发失败",
            "callback_failed": "调度回调异常",
        }

        with patch(
            "framework.notifications.NotificationService.from_config",
            return_value=mock_service,
        ):
            for ftype, label in expected_labels.items():
                await _send_schedule_failure_alert(
                    schedule_id=f"sched-{ftype}",
                    schedule_name="test",
                    env_name="dev",
                    failure_type=ftype,
                    detail="测试详情",
                )
                call_args = mock_service.send_alert.call_args.kwargs
                assert label in call_args["message"], f"Missing label '{label}' for type '{ftype}'"


class TestFireScheduleAlerts:
    """fire_schedule 调度触发回调中的告警集成测试."""

    @pytest.fixture
    def mock_scheduler(self) -> MagicMock:
        from framework.scheduler import TestScheduler

        mock = MagicMock(spec=TestScheduler)
        mock._session_factory = MagicMock()
        return mock

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.close = AsyncMock()
        return session

    @patch("framework.scheduler._send_schedule_failure_alert")
    @patch("framework.scheduler._scheduler")
    async def test_alerts_on_suite_not_found(
        self,
        mock_global_scheduler: MagicMock,
        mock_alert: AsyncMock,
        mock_scheduler: MagicMock,
        mock_session: AsyncMock,
    ) -> None:
        """套件不存在时发送告警."""
        mock_global_scheduler.__bool__.return_value = True
        mock_global_scheduler._session_factory = MagicMock(return_value=mock_session)

        # Mock ScheduleRepository.get
        schedule_model = MagicMock()
        schedule_model.enabled = True
        schedule_model.name = "每日测试"
        schedule_model.env_name = "staging"
        schedule_model.suite_id = uuid.uuid4()

        # Mock 套件查询返回 None（套件不存在）
        suite_result = MagicMock()
        suite_result.first.return_value = None

        # 顺序: get schedule → query suite name
        mock_session.execute = AsyncMock(return_value=suite_result)

        with patch("framework.scheduler.ScheduleRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get = AsyncMock(return_value=schedule_model)
            mock_repo_cls.return_value = mock_repo

            await fire_schedule(str(uuid.uuid4()))

        mock_alert.assert_called_once()
        call_kwargs = mock_alert.call_args.kwargs
        assert call_kwargs["failure_type"] == "suite_not_found"

    @patch("framework.scheduler._send_schedule_failure_alert")
    @patch("framework.scheduler._scheduler")
    async def test_alerts_on_no_cases(
        self,
        mock_global_scheduler: MagicMock,
        mock_alert: AsyncMock,
        mock_scheduler: MagicMock,
        mock_session: AsyncMock,
    ) -> None:
        """套件下无测试用例时发送告警."""
        mock_global_scheduler.__bool__.return_value = True
        mock_global_scheduler._session_factory = MagicMock(return_value=mock_session)

        schedule_model = MagicMock()
        schedule_model.enabled = True
        schedule_model.name = "空套件测试"
        schedule_model.env_name = "dev"
        schedule_model.suite_id = uuid.uuid4()

        # Mock suite name 查询
        suite_row = MagicMock()
        suite_row.__getitem__ = MagicMock(return_value="empty_suite")

        suite_result = MagicMock()
        suite_result.first.return_value = suite_row

        # Mock case ids 查询返回空
        case_result = MagicMock()
        case_result.all.return_value = []

        mock_session.execute = AsyncMock(side_effect=[suite_result, case_result])

        with patch("framework.scheduler.ScheduleRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get = AsyncMock(return_value=schedule_model)
            mock_repo_cls.return_value = mock_repo

            await fire_schedule(str(uuid.uuid4()))

        mock_alert.assert_called_once()
        call_kwargs = mock_alert.call_args.kwargs
        assert call_kwargs["failure_type"] == "no_cases"

    @patch("framework.scheduler._send_schedule_failure_alert")
    @patch("framework.scheduler._scheduler")
    @patch("worker.tasks.run_execution_task")
    async def test_alerts_on_celery_dispatch_failure(
        self,
        mock_celery_task: MagicMock,
        mock_global_scheduler: MagicMock,
        mock_alert: AsyncMock,
        mock_scheduler: MagicMock,
        mock_session: AsyncMock,
    ) -> None:
        """Celery 任务分发失败时发送告警."""
        mock_global_scheduler.__bool__.return_value = True
        mock_global_scheduler._session_factory = MagicMock(return_value=mock_session)

        schedule_model = MagicMock()
        schedule_model.enabled = True
        schedule_model.name = "Celery 测试"
        schedule_model.env_name = "dev"
        schedule_model.suite_id = uuid.uuid4()

        # Mock suite name 查询
        suite_row = MagicMock()
        suite_row.__getitem__ = MagicMock(return_value="test_suite")

        suite_result = MagicMock()
        suite_result.first.return_value = suite_row

        # Mock case ids 查询
        case_row = MagicMock()
        case_row.__getitem__ = MagicMock(return_value=uuid.uuid4())

        case_result = MagicMock()
        case_result.all.return_value = [case_row]

        mock_session.execute = AsyncMock(side_effect=[suite_result, case_result])

        # Mock Celery dispatch 抛出异常
        mock_celery_task.delay.side_effect = RuntimeError("Celery broker 不可用")

        with patch("framework.scheduler.ScheduleRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get = AsyncMock(return_value=schedule_model)
            mock_repo_cls.return_value = mock_repo

            await fire_schedule(str(uuid.uuid4()))

        mock_alert.assert_called_once()
        call_kwargs = mock_alert.call_args.kwargs
        assert call_kwargs["failure_type"] == "celery_dispatch"
        assert "Celery" in call_kwargs["detail"]

    @patch("framework.scheduler._send_schedule_failure_alert")
    @patch("framework.scheduler._scheduler")
    async def test_skips_when_schedule_not_found(
        self,
        mock_global_scheduler: MagicMock,
        mock_alert: AsyncMock,
        mock_scheduler: MagicMock,
        mock_session: AsyncMock,
    ) -> None:
        """调度记录不存在时静默跳过（不发送告警）."""
        mock_global_scheduler.__bool__.return_value = True
        mock_global_scheduler._session_factory = MagicMock(return_value=mock_session)

        with patch("framework.scheduler.ScheduleRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo

            await fire_schedule(str(uuid.uuid4()))

        mock_alert.assert_not_called()
