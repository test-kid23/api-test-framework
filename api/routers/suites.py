"""测试套件 CRUD 路由（预留）

接口:
- POST   /api/v1/suites        创建套件
- GET    /api/v1/suites        列表查询
- GET    /api/v1/suites/{id}   查询单个套件
- PUT    /api/v1/suites/{id}   更新套件
- DELETE /api/v1/suites/{id}   删除套件

当前 Phase 2 T2-1 阶段为占位实现，仅支持基础内存 CRUD。
完整的套件-Case 关联、data-driven 配置等将在 T2-3 后完善。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.dependencies import InMemoryStore, get_store
from api.schemas.common import (
    MessageResponse,
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)

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
    tags: list[str] = []
    config: dict[str, Any] = {}
    case_ids: list[str] = []
    created_at: datetime
    updated_at: datetime


class SuiteListItem(BaseModel):
    """套件列表项"""

    id: str
    name: str
    description: str = ""
    tags: list[str] = []
    case_count: int = 0
    created_at: datetime
    updated_at: datetime


# ── Helpers ───────────────────────────────────────────────


def _suite_to_response(record: dict) -> SuiteResponse:
    return SuiteResponse(**record)


def _suite_to_list_item(record: dict) -> SuiteListItem:
    return SuiteListItem(
        id=record["id"],
        name=record["name"],
        description=record.get("description", ""),
        tags=record.get("tags", []),
        case_count=len(record.get("case_ids", [])),
        created_at=record["created_at"],
        updated_at=record["updated_at"],
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
    store: InMemoryStore = Depends(get_store),
):
    now = datetime.now(timezone.utc)
    record = {
        "id": uuid.uuid4().hex[:12],
        "name": body.name,
        "description": body.description,
        "tags": body.tags,
        "config": body.config,
        "case_ids": body.case_ids,
        "created_at": now,
        "updated_at": now,
    }
    created = store.create_suite(record)
    return SuccessResponse(data=_suite_to_response(created))


# ── GET /suites ──────────────────────────────────────────


@router.get(
    "",
    response_model=SuccessResponse[PaginatedResponse[SuiteListItem]],
    summary="查询套件列表",
)
async def list_suites(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    store: InMemoryStore = Depends(get_store),
):
    items, total = store.list_suites(page=page, page_size=page_size)
    list_items = [_suite_to_list_item(r) for r in items]
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
    store: InMemoryStore = Depends(get_store),
):
    record = store.get_suite(suite_id)
    if record is None:
        raise HTTPException(status_code=404, detail="套件不存在")
    return SuccessResponse(data=_suite_to_response(record))


# ── PUT /suites/{suite_id} ───────────────────────────────


@router.put(
    "/{suite_id}",
    response_model=SuccessResponse[SuiteResponse],
    summary="更新套件",
)
async def update_suite(
    suite_id: str,
    body: SuiteUpdateRequest,
    store: InMemoryStore = Depends(get_store),
):
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="无更新字段")
    record = store.update_suite(suite_id, update_data)
    if record is None:
        raise HTTPException(status_code=404, detail="套件不存在")
    return SuccessResponse(data=_suite_to_response(record))


# ── DELETE /suites/{suite_id} ────────────────────────────


@router.delete(
    "/{suite_id}",
    response_model=MessageResponse,
    summary="删除套件",
)
async def delete_suite(
    suite_id: str,
    store: InMemoryStore = Depends(get_store),
):
    deleted = store.delete_suite(suite_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="套件不存在")
    return MessageResponse(message=f"套件 {suite_id} 已删除")
