"""测试执行调度引擎

基于 APScheduler AsyncIOScheduler 封装，支持:
- Cron 定时触发
- Interval 间隔触发
- 调度状态持久化到数据库（SQLAlchemyJobStore）
- 触发时通过 Celery Task 异步执行测试

用法:
    from framework.scheduler import get_scheduler

    scheduler = get_scheduler(session_factory, db_url)
    await scheduler.start()
    scheduler.add_schedule(schedule_model)
    await scheduler.stop()
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from framework.persistence.models.execution import ExecutionModel
from framework.persistence.models.schedule import ScheduleModel
from framework.persistence.models.test_case import TestCaseModel
from framework.persistence.models.test_suite import TestSuiteModel
from framework.persistence.repositories.schedule_repo import ScheduleRepository
from framework.utils.logger import Logger

_log = Logger.get("framework.scheduler")

# 全局调度器单例
_scheduler: TestScheduler | None = None


class TestScheduler:
    """APScheduler AsyncIOScheduler 封装，用于管理测试执行调度。

    Attributes:
        _apscheduler: APScheduler AsyncIOScheduler 实例。
        _session_factory: 异步会话工厂，用于回调中创建独立会话。
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        db_url: str,
    ) -> None:
        """初始化调度器。

        Args:
            session_factory: 异步会话工厂。
            db_url: 数据库连接 URL（同步引擎，供 APScheduler job store 使用）。
        """
        self._session_factory = session_factory

        # SQLAlchemyJobStore 使用同步 SQLAlchemy engine
        job_store = SQLAlchemyJobStore(url=db_url)
        job_store.jobs_tablename = "apscheduler_jobs"  # type: ignore[attr-defined]

        self._apscheduler = AsyncIOScheduler(jobstores={"default": job_store})

    # ── 生命周期 ──────────────────────────────────────────

    async def start(self) -> None:
        """启动调度器，从数据库加载所有启用的调度任务。

        从 schedules 表加载 enabled=True 的记录，逐一添加到 APScheduler。
        """
        async with self._session_factory() as session:
            repo = ScheduleRepository(session)
            enabled_schedules = await repo.find_enabled()

        for schedule_model in enabled_schedules:
            try:
                self.add_schedule(schedule_model)
            except ValueError as e:
                _log.warning(
                    "skip_invalid_schedule_on_start",
                    schedule_id=str(schedule_model.id),
                    name=schedule_model.name,
                    error=str(e),
                )

        self._apscheduler.start()
        _log.info(
            "scheduler_started",
            loaded_count=len(enabled_schedules),
        )

    async def stop(self) -> None:
        """停止调度器，等待所有运行中的作业完成。"""
        self._apscheduler.shutdown(wait=True)
        _log.info("scheduler_stopped")

    # ── 调度管理 ──────────────────────────────────────────

    def add_schedule(self, schedule: ScheduleModel) -> str:
        """将调度配置添加到 APScheduler。

        Args:
            schedule: 调度配置模型。

        Returns:
            添加的作业 ID。

        Raises:
            ValueError: trigger_type 不支持或必要参数缺失。
        """
        job_id = str(schedule.id)

        if schedule.trigger_type == "cron":
            if not schedule.cron_expression:
                raise ValueError(f"cron 类型调度 '{schedule.name}' 缺少 cron_expression")
            trigger: CronTrigger | IntervalTrigger = CronTrigger.from_crontab(
                schedule.cron_expression
            )
        elif schedule.trigger_type == "interval":
            if not schedule.interval_seconds:
                raise ValueError(
                    f"interval 类型调度 '{schedule.name}' 缺少 interval_seconds"
                )
            trigger = IntervalTrigger(seconds=schedule.interval_seconds)
        else:
            raise ValueError(f"不支持的 trigger_type: {schedule.trigger_type}")

        self._apscheduler.add_job(
            fire_schedule,
            trigger=trigger,
            id=job_id,
            name=schedule.name,
            kwargs={"schedule_id": job_id},
            replace_existing=True,
        )
        _log.info(
            "schedule_added",
            schedule_id=job_id,
            name=schedule.name,
            trigger_type=schedule.trigger_type,
        )
        return job_id

    def remove_schedule(self, schedule_id: str) -> None:
        """从 APScheduler 移除调度。

        Args:
            schedule_id: 调度 ID（字符串形式）。

        Raises:
            ValueError: 调度不存在时抛出。
        """
        job = self._apscheduler.get_job(schedule_id)
        if job is None:
            raise ValueError(f"调度不存在: {schedule_id}")
        self._apscheduler.remove_job(schedule_id)
        _log.info("schedule_removed", schedule_id=schedule_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        """列出所有 APScheduler 作业。

        Returns:
            作业信息列表，包含 id/name/next_run_time/trigger 信息。
        """
        jobs = self._apscheduler.get_jobs()
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": (
                    job.next_run_time.isoformat() if job.next_run_time else None
                ),
                "trigger": str(job.trigger),
            }
            for job in jobs
        ]

    def get_job(self, schedule_id: str) -> dict[str, Any] | None:
        """获取单个作业信息。

        Args:
            schedule_id: 调度 ID。

        Returns:
            作业信息字典，不存在返回 None。
        """
        job = self._apscheduler.get_job(schedule_id)
        if job is None:
            return None
        return {
            "id": job.id,
            "name": job.name,
            "next_run_time": (
                job.next_run_time.isoformat() if job.next_run_time else None
            ),
            "trigger": str(job.trigger),
        }


# ═══════════════════════════════════════════════════════════
# 调度触发回调（模块级，需可 pickle）
# ═══════════════════════════════════════════════════════════


async def fire_schedule(schedule_id: str) -> None:
    """APScheduler 调度触发时的回调函数。

    在独立的异步数据库会话中:
    1. 查询 ScheduleModel 获取 suite_id 和 env_name
    2. 查询关联套件下的所有用例 ID
    3. 创建 ExecutionModel 记录
    4. 发送 Celery 异步执行任务
    5. 更新调度上次运行时间

    Args:
        schedule_id: 调度 ID（UUID 字符串）。
    """
    scheduler = _scheduler
    if scheduler is None:
        _log.error("scheduler_not_initialized", schedule_id=schedule_id)
        return

    session: AsyncSession | None = None
    try:
        session_factory = scheduler._session_factory
        session = session_factory()
        repo = ScheduleRepository(session)

        schedule_uuid = uuid.UUID(schedule_id)
        schedule_model = await repo.get(schedule_uuid)
        if schedule_model is None or not schedule_model.enabled:
            _log.warning(
                "schedule_fire_skipped",
                schedule_id=schedule_id,
                reason="not_found_or_disabled",
            )
            return

        # 查询套件下的所有用例 ID
        suite_uuid = schedule_model.suite_id
        suite_result = await session.execute(
            select(TestSuiteModel.name).where(TestSuiteModel.id == suite_uuid)
        )
        suite_row = suite_result.first()
        if suite_row is None:
            _log.warning(
                "schedule_suite_not_found",
                schedule_id=schedule_id,
                suite_id=str(suite_uuid),
            )
            return
        suite_name = suite_row[0]

        case_result = await session.execute(
            select(TestCaseModel.id).where(TestCaseModel.suite_name == suite_name)
        )
        case_ids = [str(row[0]) for row in case_result.all()]

        if not case_ids:
            _log.warning(
                "schedule_no_cases",
                schedule_id=schedule_id,
                suite_id=str(suite_uuid),
            )
            return

        # 创建执行记录
        exec_id = uuid.uuid4()
        exec_model = ExecutionModel(
            id=exec_id,
            suite_id=suite_uuid,
            status="PENDING",
            trigger="scheduled",
            env=schedule_model.env_name,
        )
        session.add(exec_model)
        await session.flush()

        # 更新调度运行时间
        schedule_model.last_run_at = datetime.now(timezone.utc)
        await session.commit()

        # 发送 Celery 任务
        try:
            from worker.tasks import run_execution_task

            task = run_execution_task.delay(
                exec_id=str(exec_id),
                case_ids=case_ids,
                env_name=schedule_model.env_name,
            )

            # 更新 celery_task_id
            exec_model.celery_task_id = task.id
            session.add(exec_model)
            await session.commit()

            _log.info(
                "schedule_fired",
                schedule_id=schedule_id,
                name=schedule_model.name,
                exec_id=str(exec_id),
                celery_task_id=task.id,
                case_count=len(case_ids),
            )
        except Exception as e:
            _log.error(
                "schedule_celery_dispatch_failed",
                schedule_id=schedule_id,
                exec_id=str(exec_id),
                error=str(e),
            )
            # 标记执行为错误
            exec_model.status = "ERROR"
            exec_model.finished_at = datetime.now(timezone.utc)
            session.add(exec_model)
            await session.commit()

    except Exception as e:
        _log.error(
            "schedule_fire_callback_failed",
            schedule_id=schedule_id,
            error=str(e),
            exc_info=True,
        )
    finally:
        if session is not None:
            await session.close()


# ═══════════════════════════════════════════════════════════
# 全局单例管理
# ═══════════════════════════════════════════════════════════


def get_scheduler(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    db_url: str = "",
) -> TestScheduler:
    """获取全局 TestScheduler 单例。

    首次调用时需提供 session_factory 和 db_url。
    后续调用（调度器已初始化后）可不传参数直接获取已存在的实例。

    Args:
        session_factory: 异步会话工厂（首次初始化时必需）。
        db_url: 数据库连接 URL（首次初始化时必需）。

    Returns:
        TestScheduler 实例。

    Raises:
        RuntimeError: 调度器未初始化且未提供必要参数。
    """
    global _scheduler
    if _scheduler is None:
        if session_factory is None or not db_url:
            raise RuntimeError(
                "调度器未初始化，首次调用 get_scheduler() 需提供 session_factory 和 db_url"
            )
        _scheduler = TestScheduler(session_factory, db_url)
    return _scheduler


def has_scheduler() -> bool:
    """检查调度器是否已初始化。"""
    return _scheduler is not None
