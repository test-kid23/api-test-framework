"""覆盖率分析与用例推荐路由

接口:
- POST /api/v1/coverage/analyze      覆盖率分析
- POST /api/v1/coverage/generate     一键生成缺失用例
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser, check_project_access, get_current_user, require_role
from api.dependencies import get_db_session
from api.schemas.coverage import (
    CoverageAnalysisRequest,
    CoverageGapResponse,
    CoverageGenerateRequest,
    CoverageGroupResponse,
    CoverageReportResponse,
    EndpointInfoResponse,
    GenerateResultResponse,
    GeneratedCaseItem,
)
from api.schemas.common import ErrorResponse, SuccessResponse
from framework.generator import CoverageAnalyzer
from framework.persistence.models.test_case import TestCaseModel
from framework.persistence.repositories.case_repo import CaseRepository

router = APIRouter(prefix="/api/v1/coverage", tags=["coverage"])


# ── Helpers ───────────────────────────────────────────────


def _tags_to_json(tags: list[str] | None) -> str:
    return json.dumps(tags or [], ensure_ascii=False)


def _case_model_to_dict(model: TestCaseModel) -> dict:
    """将 ORM 模型转换为 CoverageAnalyzer 需要的 dict 格式。"""
    tags = []
    if model.tags:
        try:
            tags = json.loads(model.tags)
        except (json.JSONDecodeError, TypeError):
            pass

    # 从 yaml_content 中提取 method 和 path（简单解析）
    method = ""
    path = ""
    if model.yaml_content:
        import yaml

        try:
            parsed = yaml.safe_load(model.yaml_content)
            if isinstance(parsed, dict):
                # 处理套件格式
                cases = parsed.get("cases", [])
                if cases and isinstance(cases, list):
                    first = cases[0]
                    if isinstance(first, dict):
                        req = first.get("request", {})
                        if isinstance(req, dict):
                            method = req.get("method", "")
                            path = req.get("path", "")
                # 处理单用例格式
                else:
                    req = parsed.get("request", {})
                    if isinstance(req, dict):
                        method = req.get("method", "")
                        path = req.get("path", "")
        except Exception:
            pass

    return {
        "name": model.name,
        "method": method,
        "path": path,
        "tags": tags,
        "request": {"method": method, "path": path},
    }


def _build_report_response(report) -> CoverageReportResponse:
    """将 CoverageReport 转换为 API 响应。"""
    return CoverageReportResponse(
        spec_title=report.spec_title,
        spec_version=report.spec_version,
        total_endpoints=report.total_endpoints,
        covered_endpoints=report.covered_endpoints,
        uncovered_endpoints=report.uncovered_endpoints,
        coverage_rate=report.coverage_rate,
        coverage_percent=report.coverage_percent,
        by_tag=[
            CoverageGroupResponse(
                group_key=g.group_key,
                total=g.total,
                covered=g.covered,
                uncovered=g.uncovered,
                coverage_rate=g.coverage_rate,
            )
            for g in report.by_tag
        ],
        by_method=[
            CoverageGroupResponse(
                group_key=g.group_key,
                total=g.total,
                covered=g.covered,
                uncovered=g.uncovered,
                coverage_rate=g.coverage_rate,
            )
            for g in report.by_method
        ],
        by_priority=[
            CoverageGroupResponse(
                group_key=g.group_key,
                total=g.total,
                covered=g.covered,
                uncovered=g.uncovered,
                coverage_rate=g.coverage_rate,
            )
            for g in report.by_priority
        ],
        gaps=[
            CoverageGapResponse(
                endpoint=EndpointInfoResponse(
                    method=g.endpoint.method,
                    path=g.endpoint.path,
                    summary=g.endpoint.summary,
                    tags=g.endpoint.tags,
                    operation_id=g.endpoint.operation_id,
                    priority=g.endpoint.priority,
                ),
                has_similar=g.has_similar,
                similar_case_names=g.similar_case_names,
            )
            for g in report.gaps
        ],
        recommendations=[
            EndpointInfoResponse(
                method=r.method,
                path=r.path,
                summary=r.summary,
                tags=r.tags,
                operation_id=r.operation_id,
                priority=r.priority,
            )
            for r in report.recommendations
        ],
    )


# ── POST /coverage/analyze ─────────────────────────────────


@router.post(
    "/analyze",
    response_model=SuccessResponse[CoverageReportResponse],
    summary="分析 API 覆盖率",
    responses={
        200: {"description": "覆盖率分析成功"},
        400: {"model": ErrorResponse, "description": "spec 无效或解析失败"},
    },
)
async def analyze_coverage(
    body: CoverageAnalysisRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """分析 OpenAPI spec 的测试用例覆盖率。

    对比 spec 中定义的所有 endpoint 与数据库中的已有用例，
    计算总体覆盖率、按 tag/method/priority 分组统计，
    并返回未覆盖的 endpoint 列表和推荐生成的用例。
    """
    # 获取已有用例（项目隔离）
    stmt = select(TestCaseModel)
    if not current_user.is_admin() and current_user.project_ids:
        stmt = stmt.where(
            TestCaseModel.project_id.in_([uuid.UUID(pid) for pid in current_user.project_ids])
            | TestCaseModel.project_id.is_(None)
        )
    elif not current_user.is_admin():
        stmt = stmt.where(TestCaseModel.project_id.is_(None))

    result = await session.execute(stmt)
    models = result.scalars().all()

    existing_cases = [_case_model_to_dict(m) for m in models]

    # 执行覆盖率分析
    analyzer = CoverageAnalyzer()
    try:
        report = analyzer.analyze(
            spec_url=body.spec_url,
            existing_cases=existing_cases,
        )
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "spec 解析失败",
                "detail": [
                    {"loc": ["spec_url"], "msg": str(e), "type": "parse_error"}
                ],
            },
        )

    return SuccessResponse(data=_build_report_response(report))


# ── POST /coverage/generate ────────────────────────────────


@router.post(
    "/generate",
    response_model=SuccessResponse[GenerateResultResponse],
    status_code=status.HTTP_201_CREATED,
    summary="一键生成缺失用例",
    responses={
        201: {"description": "生成成功"},
        400: {"model": ErrorResponse, "description": "spec 无效或解析失败"},
    },
)
async def generate_cases(
    body: CoverageGenerateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """根据覆盖率缺口一键生成缺失的测试用例。

    若不指定 endpoints 列表，则自动分析覆盖率并生成所有未覆盖的用例。
    生成的用例可直接预览，也可选择性地持久化到数据库。

    生成策略：
    1. 若未提供 endpoints，先执行覆盖率分析，取推荐列表
    2. 解析 spec 中对应 endpoint 的定义，生成 TestCase
    3. 返回生成的 YAML 内容和元数据
    """
    analyzer = CoverageAnalyzer()

    # 确定要生成的 endpoint 列表
    endpoints_to_generate = body.endpoints

    if endpoints_to_generate is None:
        # 自动分析覆盖率获取推荐列表
        stmt = select(TestCaseModel)
        if not current_user.is_admin() and current_user.project_ids:
            stmt = stmt.where(
                TestCaseModel.project_id.in_([uuid.UUID(pid) for pid in current_user.project_ids])
                | TestCaseModel.project_id.is_(None)
            )
        elif not current_user.is_admin():
            stmt = stmt.where(TestCaseModel.project_id.is_(None))

        result = await session.execute(stmt)
        models = result.scalars().all()
        existing_cases = [_case_model_to_dict(m) for m in models]

        try:
            report = analyzer.analyze(
                spec_url=body.spec_url,
                existing_cases=existing_cases,
            )
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "spec 解析失败",
                    "detail": [
                        {"loc": ["spec_url"], "msg": str(e), "type": "parse_error"}
                    ],
                },
            )

        endpoints_to_generate = [
            {"method": ep.method, "path": ep.path}
            for ep in report.recommendations
        ]

    # 应用 limit
    if body.limit is not None and body.limit > 0:
        endpoints_to_generate = endpoints_to_generate[: body.limit]

    if not endpoints_to_generate:
        return SuccessResponse(data=GenerateResultResponse(
            total_generated=0,
            generated_cases=[],
            errors=["没有需要生成的用例：所有 endpoint 均已覆盖或 spec 为空"],
        ))

    # 生成用例
    try:
        gen_result = analyzer.generate_missing(
            spec_url=body.spec_url,
            endpoints=endpoints_to_generate,
        )
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "用例生成失败",
                "detail": [
                    {"loc": ["spec_url"], "msg": str(e), "type": "generate_error"}
                ],
            },
        )

    generated_cases = [
        GeneratedCaseItem(
            name=c["name"],
            method=c["method"],
            path=c["path"],
            description=c.get("description", ""),
            tags=c.get("tags", []),
            priority=c.get("priority", "P1"),
            yaml_content=c.get("yaml_content", ""),
        )
        for c in gen_result.generated_cases
    ]

    return SuccessResponse(data=GenerateResultResponse(
        total_generated=gen_result.total_generated,
        generated_cases=generated_cases,
        errors=gen_result.errors,
    ))


# ── POST /coverage/generate-and-save ───────────────────────


@router.post(
    "/generate-and-save",
    response_model=SuccessResponse[GenerateResultResponse],
    status_code=status.HTTP_201_CREATED,
    summary="一键生成并保存缺失用例",
    responses={
        201: {"description": "生成并保存成功"},
        400: {"model": ErrorResponse, "description": "spec 无效或解析失败"},
    },
)
async def generate_and_save_cases(
    body: CoverageGenerateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """一键生成缺失的测试用例并直接保存到数据库。

    与 /generate 的区别：生成后自动持久化到 test_cases 表，
    返回的每个用例包含数据库 ID。
    """
    analyzer = CoverageAnalyzer()

    # 确定要生成的 endpoint 列表
    endpoints_to_generate = body.endpoints

    if endpoints_to_generate is None:
        stmt = select(TestCaseModel)
        if not current_user.is_admin() and current_user.project_ids:
            stmt = stmt.where(
                TestCaseModel.project_id.in_([uuid.UUID(pid) for pid in current_user.project_ids])
                | TestCaseModel.project_id.is_(None)
            )
        elif not current_user.is_admin():
            stmt = stmt.where(TestCaseModel.project_id.is_(None))

        result = await session.execute(stmt)
        models = result.scalars().all()
        existing_cases = [_case_model_to_dict(m) for m in models]

        try:
            report = analyzer.analyze(
                spec_url=body.spec_url,
                existing_cases=existing_cases,
            )
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "spec 解析失败",
                    "detail": [
                        {"loc": ["spec_url"], "msg": str(e), "type": "parse_error"}
                    ],
                },
            )

        endpoints_to_generate = [
            {"method": ep.method, "path": ep.path}
            for ep in report.recommendations
        ]

    if body.limit is not None and body.limit > 0:
        endpoints_to_generate = endpoints_to_generate[: body.limit]

    if not endpoints_to_generate:
        return SuccessResponse(data=GenerateResultResponse(
            total_generated=0,
            generated_cases=[],
            errors=["没有需要生成的用例：所有 endpoint 均已覆盖或 spec 为空"],
        ))

    # 生成用例
    try:
        gen_result = analyzer.generate_missing(
            spec_url=body.spec_url,
            endpoints=endpoints_to_generate,
        )
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "用例生成失败",
                "detail": [
                    {"loc": ["spec_url"], "msg": str(e), "type": "generate_error"}
                ],
            },
        )

    # 持久化到数据库
    project_id = uuid.UUID(current_user.primary_project_id) if current_user.primary_project_id else None
    suite_name = body.suite_name or "auto-generated"
    repo = CaseRepository(session)

    saved_cases: list[GeneratedCaseItem] = []
    errors: list[str] = list(gen_result.errors)

    for c in gen_result.generated_cases:
        try:
            model = TestCaseModel(
                name=c["name"],
                description=c.get("description", ""),
                tags=_tags_to_json(c.get("tags", [])),
                priority=c.get("priority", "P1"),
                yaml_content=c.get("yaml_content", ""),
                suite_name=suite_name,
                project_id=project_id,
            )
            created = await repo.create(model)
            saved_cases.append(GeneratedCaseItem(
                name=c["name"],
                method=c["method"],
                path=c["path"],
                description=c.get("description", ""),
                tags=c.get("tags", []),
                priority=c.get("priority", "P1"),
                yaml_content=c.get("yaml_content", ""),
            ))
        except Exception as exc:
            errors.append(f"[{c.get('method', '')} {c.get('path', '')}] 保存失败: {exc}")

    await session.commit()

    return SuccessResponse(data=GenerateResultResponse(
        total_generated=len(saved_cases),
        generated_cases=saved_cases,
        errors=errors,
    ))
