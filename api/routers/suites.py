"""测试套件 CRUD 路由

接口:
- POST   /api/v1/suites        创建套件
- GET    /api/v1/suites        列表查询
- GET    /api/v1/suites/{id}   查询单个套件
- PUT    /api/v1/suites/{id}   更新套件
- DELETE /api/v1/suites/{id}   删除套件

注意：TestSuiteModel 的 ORM 模型中无 tags/case_ids 列，响应中不返回这些字段。
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser, check_project_access, get_current_user, require_role
from api.dependencies import get_db_session
from api.schemas.common import (
    MessageResponse,
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)
from framework.persistence.models.test_suite import TestSuiteModel
from framework.persistence.repositories.suite_repo import SuiteRepository

router = APIRouter(prefix="/api/v1/suites", tags=["suites"])


# ==================== 内联 Schema ====================


class SuiteCreateRequest(BaseModel):
    """创建套件请求"""

    name: str = Field(..., min_length=1, max_length=255, description="套件名称")
    description: str = Field(default="", description="套件描述")
    tags: list[str] = Field(default_factory=list, description="标签")
    config: dict[str, Any] = Field(default_factory=dict, description="套件配置")
    case_ids: list[str] = Field(default_factory=list, description="包含的用例 ID 列表")


class SuiteUpdateRequest(BaseModel):
    """更新套件请求"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    config: Optional[dict[str, Any]] = None
    case_ids: Optional[list[str]] = None


class SuiteResponse(BaseModel):
    """套件响应"""

    id: str
    name: str
    description: str = ""
    created_at: str
    updated_at: str


class SuiteListItem(BaseModel):
    """套件列表项"""

    id: str
    name: str
    description: str = ""
    created_at: str
    updated_at: str


# ── Helpers ───────────────────────────────────────────────


def _orm_to_response(model: TestSuiteModel) -> SuiteResponse:
    """将 ORM 模型转换为 API 响应。"""
    return SuiteResponse(
        id=str(model.id),
        name=model.name,
        description=model.description or "",
        created_at=model.created_at.isoformat() if model.created_at else "",
        updated_at=model.updated_at.isoformat() if model.updated_at else "",
    )


def _orm_to_list_item(model: TestSuiteModel) -> SuiteListItem:
    """将 ORM 模型转换为列表项响应。"""
    return SuiteListItem(
        id=str(model.id),
        name=model.name,
        description=model.description or "",
        created_at=model.created_at.isoformat() if model.created_at else "",
        updated_at=model.updated_at.isoformat() if model.updated_at else "",
    )


# ── POST /suites ─────────────────────────────────────────


@router.post(
    "",
    response_model=SuccessResponse[SuiteResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建套件",
)
async def create_suite(
    body: SuiteCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    repo = SuiteRepository(session)
    model = TestSuiteModel(
        name=body.name,
        description=body.description,
        config=json.dumps(body.config, ensure_ascii=False) if body.config else None,
    )
    if current_user.primary_project_id:
        model.project_id = uuid.UUID(current_user.primary_project_id)
    created = await repo.create(model)
    await session.commit()
    return SuccessResponse(data=_orm_to_response(created))


# ── GET /suites ──────────────────────────────────────────


@router.get(
    "",
    response_model=SuccessResponse[PaginatedResponse[SuiteListItem]],
    summary="查询套件列表",
)
async def list_suites(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    stmt = select(TestSuiteModel)

    # 项目隔离：非 admin 用户只能看自己项目的套件
    if not current_user.is_admin():
        if current_user.project_ids:
            stmt = stmt.where(
                TestSuiteModel.project_id.in_([uuid.UUID(pid) for pid in current_user.project_ids])
                | TestSuiteModel.project_id.is_(None)
            )
        else:
            stmt = stmt.where(TestSuiteModel.project_id.is_(None))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    stmt = stmt.order_by(TestSuiteModel.updated_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(stmt)
    items = result.scalars().all()

    list_items = [_orm_to_list_item(m) for m in items]
    meta = PaginationMeta(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )
    return SuccessResponse(data=PaginatedResponse(items=list_items, pagination=meta))


# ── GET /suites/{suite_id} ───────────────────────────────


@router.get(
    "/{suite_id}",
    response_model=SuccessResponse[SuiteResponse],
    summary="查询单个套件",
)
async def get_suite(
    suite_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        uid = uuid.UUID(suite_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="套件不存在")

    repo = SuiteRepository(session)
    model = await repo.get(uid)
    if model is None:
        raise HTTPException(status_code=404, detail="套件不存在")
    check_project_access(str(model.project_id) if model.project_id else None, current_user, "套件")
    return SuccessResponse(data=_orm_to_response(model))


# ── PUT /suites/{suite_id} ───────────────────────────────


@router.put(
    "/{suite_id}",
    response_model=SuccessResponse[SuiteResponse],
    summary="更新套件",
)
async def update_suite(
    suite_id: str,
    body: SuiteUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="无更新字段")

    try:
        uid = uuid.UUID(suite_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="套件不存在")

    repo = SuiteRepository(session)
    model = await repo.get(uid)
    if model is None:
        raise HTTPException(status_code=404, detail="套件不存在")

    check_project_access(str(model.project_id) if model.project_id else None, current_user, "套件")

    if body.name is not None:
        model.name = body.name
    if body.description is not None:
        model.description = body.description
    if body.config is not None:
        model.config = json.dumps(body.config, ensure_ascii=False)

    # tags 和 case_ids 在 ORM 中不存在，忽略

    await repo.update(model)
    await session.commit()
    return SuccessResponse(data=_orm_to_response(model))


# ── DELETE /suites/{suite_id} ────────────────────────────


@router.delete(
    "/{suite_id}",
    response_model=MessageResponse,
    summary="删除套件",
)
async def delete_suite(
    suite_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    try:
        uid = uuid.UUID(suite_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="套件不存在")

    repo = SuiteRepository(session)
    model = await repo.get(uid)
    if model is None:
        raise HTTPException(status_code=404, detail="套件不存在")

    check_project_access(str(model.project_id) if model.project_id else None, current_user, "套件")

    deleted = await repo.delete_by_id(uid)
    await session.commit()
    return MessageResponse(message=f"套件 {suite_id} 已删除")
