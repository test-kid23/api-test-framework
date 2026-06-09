"""智能断言路由 — Schema 推断、变更检测、断言生成

接口：
- POST   /api/v1/smart-assertions/{case_id}/infer       触发 Schema 推断
- GET    /api/v1/smart-assertions/{case_id}/schema       获取已推断的 Schema
- GET    /api/v1/smart-assertions/{case_id}/assertions   获取生成的断言
- POST   /api/v1/smart-assertions/{case_id}/detect       检测响应结构变更
- DELETE /api/v1/smart-assertions/{case_id}/schema       清除已推断的 Schema
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser, get_current_user, require_role
from api.dependencies import get_db_session
from api.schemas.assertion import (
    AssertionItemResponse,
    ChangeDetectionResponse,
    FieldSchemaResponse,
    GenerateAssertionsRequest,
    InferSchemaRequest,
    InferredSchemaResponse,
    SmartAssertionResponse,
    StructureChangeResponse,
    ValidateResponseRequest,
)
from api.schemas.common import ErrorDetail, ErrorResponse, SuccessResponse
from framework.assertion.smart import (
    ChangeDetector,
    InferredSchema,
    SchemaInferrer,
)
from framework.persistence.repositories.execution_repo import (
    ExecutionResultRepository,
)
from framework.utils.logger import Logger

router = APIRouter(prefix="/api/v1/smart-assertions", tags=["smart-assertions"])
_log = Logger.get("api.smart_assertion")

# ==================== 内存缓存 ====================
# 推断的 Schema 缓存在内存中（按 case_id），避免重复数据库查询
# 生产环境可改为 Redis 或数据库表持久化
_schema_cache: dict[str, InferredSchema] = {}


def _field_to_response(fs: Any) -> FieldSchemaResponse:
    """将 FieldSchema 转为 API 响应模型"""
    return FieldSchemaResponse(
        path=fs.path,
        types=sorted(fs.types),
        dominant_type=fs.dominant_type,
        required=fs.required,
        occurrence_rate=round(fs.occurrence_rate, 2),
        null_rate=round(fs.null_rate, 2),
        sample_count=fs.sample_count,
        sample_values=fs.sample_values[:5],
        value_pattern=fs.value_pattern,
        min_value=fs.min_value,
        max_value=fs.max_value,
        min_length=fs.min_length,
        max_length=fs.max_length,
        distinct_count=fs.distinct_count,
        warnings=list(fs.warnings),
    )


def _schema_to_response(schema: InferredSchema) -> InferredSchemaResponse:
    """将 InferredSchema 转为 API 响应模型"""
    return InferredSchemaResponse(
        case_id=schema.case_id,
        case_name=schema.case_name,
        fields={
            path: _field_to_response(fs) for path, fs in schema.fields.items()
        },
        sample_count=schema.sample_count,
        response_count=schema.response_count,
        generated_at=schema.generated_at,
        top_level_type=schema.top_level_type,
    )


# ── POST /cases/{case_id}/smart/infer ──────────────────────


@router.post(
    "/{case_id}/infer",
    response_model=SuccessResponse[InferredSchemaResponse],
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="触发 Schema 推断",
    description="收集该用例的历史成功响应，推断字段的 Schema（类型、必填性、值范围等）。",
)
async def infer_schema(
    case_id: str,
    body: InferSchemaRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    sample_limit = body.sample_limit if body else 50
    case_name = body.case_name if body else ""

    # 验证 case_id 格式
    try:
        uid = uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="用例 ID 格式无效",
                detail=[ErrorDetail(msg=f"case_id={case_id} 不是有效 UUID", type="value_error")],
            ).model_dump(),
        )

    # 查询历史成功响应
    repo = ExecutionResultRepository(session)
    response_bodies = await repo.get_successful_responses_by_case_id(
        uid, limit=sample_limit
    )

    if not response_bodies:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="无可用数据",
                detail=[ErrorDetail(
                    msg=f"用例 {case_id} 没有成功的历史执行记录，无法推断 Schema",
                    type="not_found",
                )],
            ).model_dump(),
        )

    # 推断 Schema
    schema = SchemaInferrer.infer(
        response_bodies,
        case_id=case_id,
        case_name=case_name,
    )

    # 缓存
    _schema_cache[case_id] = schema

    return SuccessResponse(data=_schema_to_response(schema))


# ── GET /cases/{case_id}/smart/schema ───────────────────────


@router.get(
    "/{case_id}/schema",
    response_model=SuccessResponse[InferredSchemaResponse],
    responses={404: {"model": ErrorResponse}},
    summary="获取已推断的 Schema",
    description="获取该用例最近一次推断的字段 Schema。需先调用 infer 端点。",
)
async def get_schema(
    case_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    schema = _schema_cache.get(case_id)
    if schema is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="Schema 未推断",
                detail=[ErrorDetail(
                    msg=f"用例 {case_id} 的 Schema 尚未推断，请先调用 POST /smart-assertions/{case_id}/infer",
                    type="not_found",
                )],
            ).model_dump(),
        )

    return SuccessResponse(data=_schema_to_response(schema))


# ── GET /smart-assertions/{case_id}/assertions ──────────────────


@router.get(
    "/{case_id}/assertions",
    response_model=SuccessResponse[SmartAssertionResponse],
    responses={404: {"model": ErrorResponse}},
    summary="获取智能生成的断言",
    description="从已推断的 Schema 自动生成断言列表。需先调用 infer 端点。",
)
async def get_assertions(
    case_id: str,
    exclude_paths: list[str] = Query(
        default=[],
        description="要排除的字段路径（可多次传参）",
    ),
    include_only: list[str] = Query(
        default=[],
        description="仅包含的字段路径（可多次传参）",
    ),
    current_user: CurrentUser = Depends(get_current_user),
):
    schema = _schema_cache.get(case_id)
    if schema is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="Schema 未推断",
                detail=[ErrorDetail(
                    msg=f"用例 {case_id} 的 Schema 尚未推断，请先调用 POST /cases/{case_id}/smart/infer",
                    type="not_found",
                )],
            ).model_dump(),
        )

    exclude = exclude_paths if exclude_paths else None
    include = include_only if include_only else None

    assertions = SchemaInferrer.generate_assertions(
        schema,
        exclude_paths=exclude,
        include_only=include,
    )

    return SuccessResponse(
        data=SmartAssertionResponse(
            case_id=case_id,
            case_name=schema.case_name,
            schema=_schema_to_response(schema),
            assertions=[
                AssertionItemResponse(
                    path=a.path,
                    expected=a.expected,
                    operator=a.operator,
                    message=a.message,
                )
                for a in assertions
            ],
            sample_count=schema.sample_count,
        )
    )


# ── POST /cases/{case_id}/smart/detect ─────────────────────


@router.post(
    "/{case_id}/detect",
    response_model=SuccessResponse[ChangeDetectionResponse],
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="检测响应结构变更",
    description="对比最新响应与已推断的 Schema，检测新增字段、字段缺失、类型变更等。",
)
async def detect_changes(
    case_id: str,
    body: ValidateResponseRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    # 获取 Schema（优先使用内存缓存）
    schema = _schema_cache.get(case_id)

    # 获取响应体
    response_body: dict[str, Any] | None = None

    if body and body.response_body:
        # 手动传入响应体
        response_body = body.response_body
    else:
        # 从数据库中获取最新的一次响应
        try:
            uid = uuid.UUID(case_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error="用例 ID 格式无效",
                    detail=[ErrorDetail(msg=f"case_id={case_id} 不是有效 UUID", type="value_error")],
                ).model_dump(),
            )

        repo = ExecutionResultRepository(session)
        recent = await repo.get_recent_responses_by_case_id(uid, limit=1)
        if not recent:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error="无可用数据",
                    detail=[ErrorDetail(
                        msg=f"用例 {case_id} 没有历史执行记录",
                        type="not_found",
                    )],
                ).model_dump(),
            )
        _, response_body = recent[0]

    if response_body is None:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="响应体无效",
                detail=[ErrorDetail(
                    msg="无法解析响应体，请确保执行记录中有有效的 JSON 响应",
                    type="value_error",
                )],
            ).model_dump(),
        )

    # 如果没有 Schema，先用现有数据推断一个
    if schema is None:
        schema = SchemaInferrer.infer(
            [response_body],
            case_id=case_id,
            case_name="",
        )
        _schema_cache[case_id] = schema

    # 变更检测
    report = ChangeDetector.detect(schema, response_body, case_id=case_id)

    return SuccessResponse(
        data=ChangeDetectionResponse(
            case_id=report.case_id,
            case_name=report.case_name,
            changes=[
                StructureChangeResponse(
                    path=c.path,
                    change_type=c.change_type,
                    severity=c.severity,
                    expected=c.expected,
                    actual=c.actual,
                    message=c.message,
                )
                for c in report.changes
            ],
            has_warnings=report.has_warnings,
            has_errors=report.has_errors,
            summary=report.summary,
        )
    )


# ── DELETE /cases/{case_id}/smart/schema ────────────────────


@router.delete(
    "/{case_id}/schema",
    response_model=SuccessResponse[dict[str, str]],
    summary="清除推断的 Schema",
    description="清除该用例的缓存 Schema，下次需要重新推断。",
)
async def clear_schema(
    case_id: str,
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    existed = case_id in _schema_cache
    _schema_cache.pop(case_id, None)
    return SuccessResponse(
        data={
            "case_id": case_id,
            "status": "cleared" if existed else "not_found",
        }
    )
