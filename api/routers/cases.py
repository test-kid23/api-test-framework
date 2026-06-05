"""用例 CRUD 路由

接口:
- POST   /api/v1/cases        创建用例
- GET    /api/v1/cases        列表查询（分页+过滤）
- GET    /api/v1/cases/{id}   查询单个用例
- PUT    /api/v1/cases/{id}   更新用例
- DELETE /api/v1/cases/{id}   删除用例
- GET    /api/v1/cases/{id}/versions  版本历史
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import InMemoryStore, get_store
from api.schemas.case import (
    CaseCreateRequest,
    CaseListItem,
    CaseQueryParams,
    CaseResponse,
    CaseUpdateRequest,
)
from api.schemas.common import (
    ErrorDetail,
    ErrorResponse,
    MessageResponse,
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


# ── Helpers ───────────────────────────────────────────────


def _case_to_response(record: dict) -> CaseResponse:
    return CaseResponse(**record)


def _case_to_list_item(record: dict) -> CaseListItem:
    return CaseListItem(
        id=record["id"],
        name=record["name"],
        description=record.get("description", ""),
        tags=record.get("tags", []),
        priority=record.get("priority", "P1"),
        timeout=record.get("timeout"),
        version=record.get("version", 1),
        created_at=record["created_at"],
        updated_at=record["updated_at"],
    )


# ── POST /cases ───────────────────────────────────────────


@router.post(
    "",
    response_model=SuccessResponse[CaseResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建用例",
    responses={
        201: {"description": "用例创建成功"},
        422: {"model": ErrorResponse, "description": "请求参数校验失败"},
    },
)
async def create_case(
    body: CaseCreateRequest,
    store: InMemoryStore = Depends(get_store),
):
    """创建新的测试用例，将 YAML 内容持久化到存储中。"""
    now = datetime.now(timezone.utc)
    record = {
        "id": uuid.uuid4().hex[:12],
        "name": body.name,
        "description": body.description,
        "tags": body.tags,
        "priority": body.priority,
        "yaml_content": body.yaml_content,
        "timeout": body.timeout,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    created = store.create_case(record)
    return SuccessResponse(data=_case_to_response(created))


# ── GET /cases ────────────────────────────────────────────


@router.get(
    "",
    response_model=SuccessResponse[PaginatedResponse[CaseListItem]],
    summary="查询用例列表",
)
async def list_cases(
    params: CaseQueryParams = Depends(),
    store: InMemoryStore = Depends(get_store),
):
    """分页查询用例列表，支持按标签、优先级过滤和关键词搜索。"""
    items, total = store.list_cases(
        page=params.page,
        page_size=params.page_size,
        tag=params.tag,
        priority=params.priority,
        search=params.search,
    )
    list_items = [_case_to_list_item(r) for r in items]
    meta = PaginationMeta(
        page=params.page,
        page_size=params.page_size,
        total=total,
        total_pages=max(1, (total + params.page_size - 1) // params.page_size),
    )
    return SuccessResponse(data=PaginatedResponse(items=list_items, pagination=meta))


# ── GET /cases/{case_id} ──────────────────────────────────


@router.get(
    "/{case_id}",
    response_model=SuccessResponse[CaseResponse],
    summary="查询单个用例",
    responses={
        200: {"description": "成功"},
        404: {"model": ErrorResponse, "description": "用例不存在"},
    },
)
async def get_case(
    case_id: str,
    store: InMemoryStore = Depends(get_store),
):
    """根据 ID 获取单个用例详情，包含完整 YAML 内容。"""
    record = store.get_case(case_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "用例不存在", "detail": [{"loc": ["case_id"], "msg": f"ID '{case_id}' 未找到", "type": "not_found"}]},
        )
    return SuccessResponse(data=_case_to_response(record))


# ── PUT /cases/{case_id} ──────────────────────────────────


@router.put(
    "/{case_id}",
    response_model=SuccessResponse[CaseResponse],
    summary="更新用例",
    responses={
        200: {"description": "更新成功"},
        404: {"model": ErrorResponse, "description": "用例不存在"},
    },
)
async def update_case(
    case_id: str,
    body: CaseUpdateRequest,
    store: InMemoryStore = Depends(get_store),
):
    """更新用例信息。仅更新传入的非 None 字段，版本号自动递增。"""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "无更新字段", "detail": [{"loc": ["body"], "msg": "至少提供一个要更新的字段", "type": "validation_error"}]},
        )
    record = store.update_case(case_id, update_data)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "用例不存在", "detail": [{"loc": ["case_id"], "msg": f"ID '{case_id}' 未找到", "type": "not_found"}]},
        )
    return SuccessResponse(data=_case_to_response(record))


# ── DELETE /cases/{case_id} ───────────────────────────────


@router.delete(
    "/{case_id}",
    response_model=MessageResponse,
    summary="删除用例",
    responses={
        200: {"description": "删除成功"},
        404: {"model": ErrorResponse, "description": "用例不存在"},
    },
)
async def delete_case(
    case_id: str,
    store: InMemoryStore = Depends(get_store),
):
    """删除指定用例及其版本历史。"""
    deleted = store.delete_case(case_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "用例不存在", "detail": [{"loc": ["case_id"], "msg": f"ID '{case_id}' 未找到", "type": "not_found"}]},
        )
    return MessageResponse(message=f"用例 {case_id} 已删除")


# ── GET /cases/{case_id}/versions ────────────────────────


@router.get(
    "/{case_id}/versions",
    response_model=SuccessResponse[List[CaseResponse]],
    summary="查询用例版本历史",
    responses={
        200: {"description": "成功"},
        404: {"model": ErrorResponse, "description": "用例不存在"},
    },
)
async def list_case_versions(
    case_id: str,
    store: InMemoryStore = Depends(get_store),
):
    """获取用例的全部历史版本（按时间倒序）。"""
    versions = store.list_case_versions(case_id)
    if not versions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "用例不存在", "detail": [{"loc": ["case_id"], "msg": f"ID '{case_id}' 不存在或无版本记录", "type": "not_found"}]},
        )
    return SuccessResponse(data=[_case_to_response(v) for v in reversed(versions)])
