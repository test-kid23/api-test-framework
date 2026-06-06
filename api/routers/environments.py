"""环境管理路由

接口:
- POST   /api/v1/environments        创建环境
- GET    /api/v1/environments        环境列表
- GET    /api/v1/environments/{id}   环境详情
- PUT    /api/v1/environments/{id}   更新环境
- DELETE /api/v1/environments/{id}   删除环境
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session
from api.schemas.common import (
    MessageResponse,
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)
from api.schemas.environment import EnvironmentCreate, EnvironmentResponse, EnvironmentUpdate
from framework.persistence.models.environment import EnvironmentModel
from framework.persistence.repositories.environment_repo import EnvironmentRepository
from framework.utils.logger import Logger

router = APIRouter(prefix="/api/v1/environments", tags=["environments"])
_log = Logger.get("api.environments")


# ── Helpers ───────────────────────────────────────────────


def _orm_to_response(model: EnvironmentModel) -> EnvironmentResponse:
    """将 ORM 模型转换为 API 响应。"""
    return EnvironmentResponse(
        id=str(model.id),
        name=model.name,
        description=model.description,
        base_url=model.base_url,
        ws_url=model.ws_url,
        variables=model.variables,
        http_config=model.http_config,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


# ── POST /environments ───────────────────────────────────


@router.post(
    "",
    response_model=SuccessResponse[EnvironmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建环境",
    responses={
        400: {"description": "参数校验失败或名称已存在"},
    },
)
async def create_environment(
    body: EnvironmentCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """创建新的测试环境配置。

    环境名称必须全局唯一，否则返回 400 错误。
    """
    repo = EnvironmentRepository(session)

    # 检查名称唯一性
    if await repo.name_exists(body.name):
        raise HTTPException(
            status_code=400,
            detail=f"环境名称已存在: {body.name}",
        )

    model = EnvironmentModel(
        name=body.name,
        description=body.description,
        base_url=body.base_url,
        ws_url=body.ws_url,
        variables=body.variables,
        http_config=body.http_config,
    )

    created = await repo.create(model)
    await session.commit()

    _log.info(
        "env_created",
        env_id=str(created.id),
        name=created.name,
    )
    return SuccessResponse(data=_orm_to_response(created))


# ── GET /environments ────────────────────────────────────


@router.get(
    "",
    response_model=SuccessResponse[PaginatedResponse[EnvironmentResponse]],
    summary="查询环境列表",
)
async def list_environments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    """分页查询所有环境配置（按创建时间倒序）。"""
    repo = EnvironmentRepository(session)
    offset = (page - 1) * page_size
    items, total = await repo.list(
        offset=offset,
        limit=page_size,
        order_by=EnvironmentModel.created_at.desc(),
    )

    env_items = [_orm_to_response(m) for m in items]
    meta = PaginationMeta(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )
    return SuccessResponse(data=PaginatedResponse(items=env_items, pagination=meta))


# ── GET /environments/{env_id} ───────────────────────────


@router.get(
    "/{env_id}",
    response_model=SuccessResponse[EnvironmentResponse],
    summary="查询环境详情",
)
async def get_environment(
    env_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """根据 ID 获取单个环境配置详情。"""
    try:
        uid = uuid.UUID(env_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="环境不存在")

    repo = EnvironmentRepository(session)
    model = await repo.get(uid)
    if model is None:
        raise HTTPException(status_code=404, detail="环境不存在")

    return SuccessResponse(data=_orm_to_response(model))


# ── PUT /environments/{env_id} ───────────────────────────


@router.put(
    "/{env_id}",
    response_model=SuccessResponse[EnvironmentResponse],
    summary="更新环境",
)
async def update_environment(
    env_id: str,
    body: EnvironmentUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    """更新环境配置。仅更新传入的非空字段。"""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="无更新字段")

    try:
        uid = uuid.UUID(env_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="环境不存在")

    repo = EnvironmentRepository(session)
    model = await repo.get(uid)
    if model is None:
        raise HTTPException(status_code=404, detail="环境不存在")

    # 名称唯一性校验
    if body.name is not None and body.name != model.name:
        if await repo.name_exists(body.name, exclude_id=str(model.id)):
            raise HTTPException(
                status_code=400,
                detail=f"环境名称已存在: {body.name}",
            )

    # 更新字段
    if body.name is not None:
        model.name = body.name
    if body.description is not None:
        model.description = body.description
    if body.base_url is not None:
        model.base_url = body.base_url
    if body.ws_url is not None:
        model.ws_url = body.ws_url
    if body.variables is not None:
        model.variables = body.variables
    if body.http_config is not None:
        model.http_config = body.http_config

    await repo.update(model)
    await session.commit()

    _log.info("env_updated", env_id=env_id)
    return SuccessResponse(data=_orm_to_response(model))


# ── DELETE /environments/{env_id} ────────────────────────


@router.delete(
    "/{env_id}",
    response_model=MessageResponse,
    summary="删除环境",
)
async def delete_environment(
    env_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """删除环境配置。"""
    try:
        uid = uuid.UUID(env_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="环境不存在")

    repo = EnvironmentRepository(session)
    deleted = await repo.delete_by_id(uid)
    if not deleted:
        raise HTTPException(status_code=404, detail="环境不存在")

    await session.commit()
    _log.info("env_deleted", env_id=env_id)
    return MessageResponse(message=f"环境 {env_id} 已删除")
