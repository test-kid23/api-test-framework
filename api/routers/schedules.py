"""调度管理路由

接口:
- POST   /api/v1/schedules        创建调度任务
- GET    /api/v1/schedules        调度列表
- GET    /api/v1/schedules/{id}   调度详情
- PUT    /api/v1/schedules/{id}   更新调度
- DELETE /api/v1/schedules/{id}   删除调度
- POST   /api/v1/schedules/{id}/run  手动触发执行
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session
from api.schemas.common import (
    MessageResponse,
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)
from api.schemas.schedule import ScheduleCreate, ScheduleResponse, ScheduleUpdate
from framework.persistence.models.execution import ExecutionModel
from framework.persistence.models.schedule import ScheduleModel
from framework.persistence.models.test_case import TestCaseModel
from framework.persistence.models.test_suite import TestSuiteModel
from framework.persistence.repositories.schedule_repo import ScheduleRepository
from framework.scheduler import fire_schedule, get_scheduler, has_scheduler
from framework.utils.logger import Logger

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])
_log = Logger.get("api.schedules")


# ── Helpers ───────────────────────────────────────────────


def _orm_to_response(model: ScheduleModel) -> ScheduleResponse:
    """将 ORM 模型转换为 API 响应。"""
    return ScheduleResponse(
        id=str(model.id),
        name=model.name,
        suite_id=str(model.suite_id),
        env_name=model.env_name,
        trigger_type=model.trigger_type,
        cron_expression=model.cron_expression,
        interval_seconds=model.interval_seconds,
        enabled=model.enabled,
        last_run_at=model.last_run_at,
        next_run_at=model.next_run_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


# ── POST /schedules ───────────────────────────────────────


@router.post(
    "",
    response_model=SuccessResponse[ScheduleResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建调度任务",
    responses={
        400: {"description": "参数校验失败"},
        404: {"description": "关联套件不存在"},
    },
)
async def create_schedule(
    body: ScheduleCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """创建定时/周期调度任务，关联测试套件和环境。

    支持两种触发类型:
    - **cron**: 需提供 cron_expression，如 `"0 8 * * *"` 表示每天 8:00
    - **interval**: 需提供 interval_seconds，如 `3600` 表示每小时执行
    """
    # 验证套件存在
    try:
        suite_uuid = uuid.UUID(body.suite_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"套件不存在: {body.suite_id}")

    suite_result = await session.execute(
        select(func.count(TestSuiteModel.id)).where(TestSuiteModel.id == suite_uuid)
    )
    if suite_result.scalar_one() == 0:
        raise HTTPException(status_code=404, detail=f"套件不存在: {body.suite_id}")

    # 参数校验
    if body.trigger_type.value == "cron" and not body.cron_expression:
        raise HTTPException(
            status_code=400,
            detail="cron 类型必须提供 cron_expression",
        )
    if body.trigger_type.value == "interval" and not body.interval_seconds:
        raise HTTPException(
            status_code=400,
            detail="interval 类型必须提供 interval_seconds",
        )

    # 创建调度记录
    model = ScheduleModel(
        name=body.name,
        suite_id=suite_uuid,
        env_name=body.env_name,
        trigger_type=body.trigger_type.value,
        cron_expression=body.cron_expression,
        interval_seconds=body.interval_seconds,
        enabled=body.enabled,
    )

    repo = ScheduleRepository(session)
    created = await repo.create(model)
    await session.commit()

    # 如果启用且调度器已启动，添加到 APScheduler
    if created.enabled and has_scheduler():
        scheduler = get_scheduler()
        try:
            scheduler.add_schedule(created)
        except ValueError as e:
            _log.warning(
                "schedule_add_to_apscheduler_failed",
                schedule_id=str(created.id),
                error=str(e),
            )

    _log.info(
        "schedule_created",
        schedule_id=str(created.id),
        name=created.name,
        trigger=created.trigger_type,
    )
    return SuccessResponse(data=_orm_to_response(created))


# ── GET /schedules ────────────────────────────────────────


@router.get(
    "",
    response_model=SuccessResponse[PaginatedResponse[ScheduleResponse]],
    summary="查询调度列表",
)
async def list_schedules(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    """分页查询所有调度任务（按创建时间倒序）。"""
    repo = ScheduleRepository(session)
    offset = (page - 1) * page_size
    items, total = await repo.list(
        offset=offset,
        limit=page_size,
        order_by=ScheduleModel.created_at.desc(),
    )

    schedule_items = [_orm_to_response(m) for m in items]
    meta = PaginationMeta(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )
    return SuccessResponse(data=PaginatedResponse(items=schedule_items, pagination=meta))


# ── GET /schedules/{schedule_id} ───────────────────────────


@router.get(
    "/{schedule_id}",
    response_model=SuccessResponse[ScheduleResponse],
    summary="查询调度详情",
)
async def get_schedule(
    schedule_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """根据 ID 获取单个调度任务详情。"""
    try:
        uid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="调度任务不存在")

    repo = ScheduleRepository(session)
    model = await repo.get(uid)
    if model is None:
        raise HTTPException(status_code=404, detail="调度任务不存在")

    return SuccessResponse(data=_orm_to_response(model))


# ── PUT /schedules/{schedule_id} ───────────────────────────


@router.put(
    "/{schedule_id}",
    response_model=SuccessResponse[ScheduleResponse],
    summary="更新调度任务",
)
async def update_schedule(
    schedule_id: str,
    body: ScheduleUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    """更新调度任务配置。修改后调度器中的作业也会同步更新。"""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="无更新字段")

    try:
        uid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="调度任务不存在")

    repo = ScheduleRepository(session)
    model = await repo.get(uid)
    if model is None:
        raise HTTPException(status_code=404, detail="调度任务不存在")

    # 更新字段
    if body.name is not None:
        model.name = body.name
    if body.env_name is not None:
        model.env_name = body.env_name
    if body.enabled is not None:
        model.enabled = body.enabled
    if body.cron_expression is not None:
        model.cron_expression = body.cron_expression
    if body.interval_seconds is not None:
        model.interval_seconds = body.interval_seconds

    await repo.update(model)
    await session.commit()

    # 同步 APScheduler 中的作业
    if has_scheduler():
        scheduler = get_scheduler()
        try:
            scheduler.remove_schedule(schedule_id)
        except (ValueError, KeyError):
            pass

        if model.enabled:
            try:
                scheduler.add_schedule(model)
            except ValueError as e:
                _log.warning(
                    "schedule_update_sync_failed",
                    schedule_id=schedule_id,
                    error=str(e),
                )

    _log.info("schedule_updated", schedule_id=schedule_id)
    return SuccessResponse(data=_orm_to_response(model))


# ── DELETE /schedules/{schedule_id} ────────────────────────


@router.delete(
    "/{schedule_id}",
    response_model=MessageResponse,
    summary="删除调度任务",
)
async def delete_schedule(
    schedule_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """删除调度任务，同时从调度器中移除作业。"""
    try:
        uid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="调度任务不存在")

    # 先从 APScheduler 移除
    if has_scheduler():
        scheduler = get_scheduler()
        try:
            scheduler.remove_schedule(schedule_id)
        except (ValueError, KeyError):
            pass

    repo = ScheduleRepository(session)
    deleted = await repo.delete_by_id(uid)
    if not deleted:
        raise HTTPException(status_code=404, detail="调度任务不存在")

    await session.commit()
    _log.info("schedule_deleted", schedule_id=schedule_id)
    return MessageResponse(message=f"调度任务 {schedule_id} 已删除")


# ── POST /schedules/{schedule_id}/run ──────────────────────


@router.post(
    "/{schedule_id}/run",
    response_model=SuccessResponse[dict],
    summary="手动触发调度执行",
    responses={
        200: {"description": "执行已触发"},
        404: {"description": "调度任务不存在"},
        400: {"description": "调度已禁用"},
    },
)
async def run_schedule(
    schedule_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """手动触发一次调度执行（不修改调度周期）。

    与定时触发行为一致：创建执行记录 → 通过 Celery task 异步执行套件用例。
    """
    try:
        uid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="调度任务不存在")

    repo = ScheduleRepository(session)
    model = await repo.get(uid)
    if model is None:
        raise HTTPException(status_code=404, detail="调度任务不存在")

    if not model.enabled:
        raise HTTPException(status_code=400, detail="调度任务已禁用，请先启用")

    # 查询套件下的用例
    suite_result = await session.execute(
        select(TestSuiteModel.name).where(TestSuiteModel.id == model.suite_id)
    )
    suite_row = suite_result.first()
    if suite_row is None:
        raise HTTPException(status_code=404, detail="关联套件不存在")

    suite_name = suite_row[0]
    case_result = await session.execute(
        select(TestCaseModel.id).where(TestCaseModel.suite_name == suite_name)
    )
    case_ids = [str(row[0]) for row in case_result.all()]

    if not case_ids:
        raise HTTPException(status_code=400, detail="套件下无用例")

    # 创建执行记录
    exec_id = uuid.uuid4()
    exec_model = ExecutionModel(
        id=exec_id,
        suite_id=model.suite_id,
        status="PENDING",
        trigger="scheduled",
        env=model.env_name,
    )
    session.add(exec_model)

    # 更新调度运行时间
    model.last_run_at = datetime.now(timezone.utc)
    await session.commit()

    # 发送 Celery 任务
    try:
        from worker.tasks import run_execution_task

        task = run_execution_task.delay(
            exec_id=str(exec_id),
            case_ids=case_ids,
            env_name=model.env_name,
        )

        exec_model.celery_task_id = task.id
        session.add(exec_model)
        await session.commit()

        _log.info(
            "schedule_manual_run",
            schedule_id=schedule_id,
            exec_id=str(exec_id),
            celery_task_id=task.id,
            case_count=len(case_ids),
        )
        return SuccessResponse(data={
            "execution_id": str(exec_id),
            "celery_task_id": task.id,
            "case_count": len(case_ids),
        })
    except Exception as e:
        _log.error(
            "schedule_manual_run_celery_failed",
            schedule_id=schedule_id,
            exec_id=str(exec_id),
            error=str(e),
        )
        exec_model.status = "ERROR"
        exec_model.finished_at = datetime.now(timezone.utc)
        session.add(exec_model)
        await session.commit()
        raise HTTPException(status_code=500, detail=f"Celery 调度失败: {str(e)}")
