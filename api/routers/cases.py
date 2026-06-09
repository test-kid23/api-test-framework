"""用例 CRUD 路由

接口:
- POST   /api/v1/cases               创建用例
- GET    /api/v1/cases               列表查询（分页+过滤）
- GET    /api/v1/cases/{id}          查询单个用例
- PUT    /api/v1/cases/{id}          更新用例
- DELETE /api/v1/cases/{id}          删除用例
- GET    /api/v1/cases/{id}/versions 版本历史
- POST   /api/v1/cases/import        从 OpenAPI spec 导入用例
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser, check_project_access, get_current_user, require_role
from api.dependencies import get_db_session
from api.schemas.case import (
    CaseCreateRequest,
    CaseImportRequest,
    CaseImportResult,
    CaseListItem,
    CaseQueryParams,
    CaseResponse,
    CaseUpdateRequest,
)
from api.schemas.common import (
    ErrorResponse,
    MessageResponse,
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)
from framework.importers.openapi_parser import OpenAPICaseParser, testcase_to_yaml_content
from framework.persistence.models.test_case import TestCaseModel
from framework.persistence.repositories.case_repo import CaseRepository

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


# ── Helpers ───────────────────────────────────────────────


def _tags_to_json(tags: list[str] | None) -> str:
    """将标签列表序列化为 JSON 字符串（DB 存储格式）。"""
    return json.dumps(tags or [], ensure_ascii=False)


def _json_to_tags(tags_json: str | None) -> list[str]:
    """将 DB 中的 JSON 字符串反序列化为标签列表。"""
    if not tags_json:
        return []
    try:
        return json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []


def _orm_to_response(model: TestCaseModel) -> CaseResponse:
    """将 ORM 模型转换为 API 响应。"""
    return CaseResponse(
        id=str(model.id),
        name=model.name,
        description=model.description or "",
        tags=_json_to_tags(model.tags),
        priority=model.priority,
        yaml_content=model.yaml_content or "",
        timeout=None,  # TestCaseModel 无此字段
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _orm_to_list_item(model: TestCaseModel) -> CaseListItem:
    """将 ORM 模型转换为列表项响应。"""
    return CaseListItem(
        id=str(model.id),
        name=model.name,
        description=model.description or "",
        tags=_json_to_tags(model.tags),
        priority=model.priority,
        timeout=None,  # TestCaseModel 无此字段
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _not_found(case_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": "用例不存在",
            "detail": [
                {
                    "loc": ["case_id"],
                    "msg": f"ID '{case_id}' 未找到",
                    "type": "not_found",
                }
            ],
        },
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
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """创建新的测试用例，将 YAML 内容持久化到数据库中。"""
    repo = CaseRepository(session)
    model = TestCaseModel(
        name=body.name,
        description=body.description,
        tags=_tags_to_json(body.tags),
        priority=body.priority,
        yaml_content=body.yaml_content,
    )
    # 绑定到用户的第一个项目（如有关联）
    if current_user.primary_project_id:
        model.project_id = uuid.UUID(current_user.primary_project_id)
    created = await repo.create(model)
    await session.commit()
    return SuccessResponse(data=_orm_to_response(created))


# ── GET /cases ────────────────────────────────────────────


@router.get(
    "",
    response_model=SuccessResponse[PaginatedResponse[CaseListItem]],
    summary="查询用例列表",
)
async def list_cases(
    params: CaseQueryParams = Depends(),
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """分页查询用例列表，支持按标签、优先级过滤和关键词搜索。"""
    stmt = select(TestCaseModel)

    # 项目隔离：非 admin 用户只能看自己项目的用例
    if not current_user.is_admin() and current_user.project_ids:
        stmt = stmt.where(
            (TestCaseModel.project_id.in_([uuid.UUID(pid) for pid in current_user.project_ids]))
            | (TestCaseModel.project_id.is_(None))
        )
    elif not current_user.is_admin():
        # 无项目的用户只能看全局资源
        stmt = stmt.where(TestCaseModel.project_id.is_(None))

    # 标签过滤：tags 字段在 DB 中为 JSON 字符串，使用 contains 匹配
    if params.tag:
        stmt = stmt.where(TestCaseModel.tags.contains(params.tag))

    # 优先级过滤
    if params.priority:
        stmt = stmt.where(TestCaseModel.priority == params.priority)

    # 关键词搜索（名称/描述模糊匹配）
    if params.search:
        search_pattern = f"%{params.search}%"
        stmt = stmt.where(
            or_(
                TestCaseModel.name.ilike(search_pattern),
                TestCaseModel.description.ilike(search_pattern),
            )
        )

    # 计数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    # 分页 + 排序
    offset = (params.page - 1) * params.page_size
    stmt = stmt.order_by(TestCaseModel.updated_at.desc()).offset(offset).limit(params.page_size)
    result = await session.execute(stmt)
    items = result.scalars().all()

    list_items = [_orm_to_list_item(m) for m in items]
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
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """根据 ID 获取单个用例详情，包含完整 YAML 内容。"""
    try:
        uid = uuid.UUID(case_id)
    except ValueError:
        raise _not_found(case_id)

    repo = CaseRepository(session)
    model = await repo.get(uid)
    if model is None:
        raise _not_found(case_id)
    check_project_access(str(model.project_id) if model.project_id else None, current_user, "用例")
    return SuccessResponse(data=_orm_to_response(model))


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
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """更新用例信息。仅更新传入的非 None 字段，版本号自动递增。"""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "无更新字段",
                "detail": [
                    {
                        "loc": ["body"],
                        "msg": "至少提供一个要更新的字段",
                        "type": "validation_error",
                    }
                ],
            },
        )

    try:
        uid = uuid.UUID(case_id)
    except ValueError:
        raise _not_found(case_id)

    repo = CaseRepository(session)
    model = await repo.get(uid)
    if model is None:
        raise _not_found(case_id)

    check_project_access(str(model.project_id) if model.project_id else None, current_user, "用例")

    # 更新字段（仅更新传入的非 None 值）
    if body.name is not None:
        model.name = body.name
    if body.description is not None:
        model.description = body.description
    if body.tags is not None:
        model.tags = _tags_to_json(body.tags)
    if body.priority is not None:
        model.priority = body.priority
    if body.yaml_content is not None:
        model.yaml_content = body.yaml_content
    # timeout 字段在 ORM 中不存在，忽略

    # 版本号递增
    model.version += 1

    await repo.update(model)
    await session.commit()

    return SuccessResponse(data=_orm_to_response(model))


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
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """删除指定用例。"""
    try:
        uid = uuid.UUID(case_id)
    except ValueError:
        raise _not_found(case_id)

    repo = CaseRepository(session)
    model = await repo.get(uid)
    if model is None:
        raise _not_found(case_id)

    check_project_access(str(model.project_id) if model.project_id else None, current_user, "用例")

    deleted = await repo.delete_by_id(uid)
    if not deleted:
        raise _not_found(case_id)

    await session.commit()
    return MessageResponse(message=f"用例 {case_id} 已删除")


# ── GET /cases/{case_id}/versions ────────────────────────


@router.get(
    "/{case_id}/versions",
    response_model=SuccessResponse[list[CaseResponse]],
    summary="查询用例版本历史",
    responses={
        200: {"description": "成功"},
        404: {"model": ErrorResponse, "description": "用例不存在"},
    },
)
async def list_case_versions(
    case_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取用例的版本信息（当前 DB 中仅保留最新版本）。"""
    try:
        uid = uuid.UUID(case_id)
    except ValueError:
        raise _not_found(case_id)

    repo = CaseRepository(session)
    model = await repo.get(uid)
    if model is None:
        raise _not_found(case_id)

    check_project_access(str(model.project_id) if model.project_id else None, current_user, "用例")

    # DB 中无版本历史表，返回当前记录作为唯一版本
    return SuccessResponse(data=[_orm_to_response(model)])


# ── POST /cases/import ────────────────────────────────────


@router.post(
    "/import",
    response_model=SuccessResponse[CaseImportResult],
    status_code=status.HTTP_201_CREATED,
    summary="从 OpenAPI spec 导入用例",
    responses={
        201: {"description": "导入成功"},
        400: {"model": ErrorResponse, "description": "spec 无效或解析失败"},
    },
)
async def import_cases(
    body: CaseImportRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """从 OpenAPI 3.x / Swagger 规范 URL 或本地文件导入测试用例。

    解析 spec 中的每个 path + method 组合，自动生成包含请求示例、
    状态码断言和 Content-Type 断言的测试用例，并存储到数据库中。
    """
    parser = OpenAPICaseParser()

    try:
        suite = parser.parse_from_url(body.spec_url, suite_name=body.suite_name)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "spec 解析失败",
                "detail": [
                    {
                        "loc": ["spec_url"],
                        "msg": str(e),
                        "type": "parse_error",
                    }
                ],
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "导入过程异常",
                "detail": [
                    {"loc": ["spec_url"], "msg": str(e), "type": "internal_error"}
                ],
            },
        )

    repo = CaseRepository(session)
    imported_ids: list[str] = []
    errors: list[str] = []

    project_id = uuid.UUID(current_user.primary_project_id) if current_user.primary_project_id else None

    for case in suite.cases:
        try:
            yaml_content = testcase_to_yaml_content(case)
            model = TestCaseModel(
                name=case.name,
                description=case.description,
                tags=_tags_to_json(case.tags),
                priority=case.priority,
                yaml_content=yaml_content,
                suite_name=suite.name,
                project_id=project_id,
            )
            created = await repo.create(model)
            imported_ids.append(str(created.id))
        except Exception as e:
            errors.append(f"[{case.name}] {str(e)}")

    await session.commit()

    result = CaseImportResult(
        total_discovered=len(suite.cases),
        total_imported=len(imported_ids),
        total_skipped=len(suite.cases) - len(imported_ids),
        suite_name=suite.name,
        case_ids=imported_ids,
        errors=errors,
    )

    return SuccessResponse(data=result)
