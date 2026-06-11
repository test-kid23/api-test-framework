"""Mock 规则管理路由

接口：
- POST   /api/v1/mocks/rules       注册规则
- GET    /api/v1/mocks/rules       规则列表
- GET    /api/v1/mocks/rules/{id}  规则详情
- PUT    /api/v1/mocks/rules/{id}  更新规则
- DELETE /api/v1/mocks/rules/{id}  删除规则
- DELETE /api/v1/mocks/rules       清空规则

Mock 规则通过 MockRuleRepository 持久化到数据库，同时同步到
MockRuleStore（内存）以支持运行时的低延迟匹配。
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser, get_current_user, require_role
from api.dependencies import get_db_session
from framework.mock.rule_store import get_mock_store
from framework.persistence.models.mock_rule import MockRuleModel
from framework.persistence.repositories.mock_rule_repo import MockRuleRepository
from framework.utils.logger import Logger

router = APIRouter(prefix="/api/v1/mocks", tags=["mocks"])
_log = Logger.get("api.mocks")


# ── Helpers ───────────────────────────────────────────────


def _model_to_dict(model: MockRuleModel) -> dict[str, Any]:
    """将 MockRuleModel 转为字典"""
    return {
        "id": str(model.id),
        "url_pattern": model.url_pattern,
        "method": model.method,
        "status_code": model.status_code,
        "response_body": model.response_body,
        "response_headers": model.response_headers,
        "description": model.description,
        "enabled": model.enabled,
        "priority": model.priority,
        "delay_ms": model.delay_ms,
    }


def _sync_to_memory(model: MockRuleModel) -> None:
    """将数据库规则同步到内存 MockRuleStore。"""
    store = get_mock_store()
    store.register(
        url_pattern=model.url_pattern,
        method=model.method,
        status_code=model.status_code,
        response_body=model.response_body,
        response_headers=model.response_headers,
        description=model.description,
        priority=model.priority,
        delay_ms=model.delay_ms,
        rule_id=str(model.id),
    )
    # 同步 enabled 状态
    if not model.enabled:
        rule = store.get(str(model.id))
        if rule:
            rule.enabled = False


# ── POST /mocks/rules ────────────────────────────────────


@router.post(
    "/rules",
    status_code=status.HTTP_201_CREATED,
    summary="注册 Mock 规则",
    responses={
        400: {"description": "参数校验失败"},
    },
)
async def create_rule(
    body: dict[str, Any],
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """注册一条 Mock 规则。

    请求体示例:
    ```json
    {
        "url_pattern": "/api/users/*",
        "method": "POST",
        "status_code": 201,
        "response_body": {"id": 1, "name": "test"},
        "response_headers": {"X-Custom": "value"},
        "description": "创建用户 Mock",
        "priority": 10,
        "delay_ms": 500
    }
    ```
    """
    if "url_pattern" not in body:
        raise HTTPException(status_code=400, detail="url_pattern 为必填字段")

    repo = MockRuleRepository(session)
    model = MockRuleModel(
        url_pattern=body["url_pattern"],
        method=body.get("method", "ANY"),
        status_code=body.get("status_code", 200),
        response_body=body.get("response_body"),
        response_headers=body.get("response_headers"),
        description=body.get("description", ""),
        priority=body.get("priority", 0),
        delay_ms=body.get("delay_ms", 0),
        project_id=uuid.UUID(current_user.primary_project_id) if current_user.primary_project_id else None,
    )
    created = await repo.create(model)
    await session.commit()

    # 同步到内存 store
    _sync_to_memory(created)

    _log.info("mock_rule_created_via_api", rule_id=str(created.id), url_pattern=created.url_pattern)
    return {"success": True, "data": _model_to_dict(created)}


# ── POST /mocks/rules/batch ──────────────────────────────


@router.post(
    "/rules/batch",
    status_code=status.HTTP_201_CREATED,
    summary="批量注册 Mock 规则",
)
async def create_rules_batch(
    body: dict[str, Any],
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """批量注册多条 Mock 规则。

    请求体示例:
    ```json
    {
        "rules": [
            {"url_pattern": "/api/users", "method": "GET", "status_code": 200, "response_body": []},
            {"url_pattern": "/api/users", "method": "POST", "status_code": 201, "response_body": {"id": 1}}
        ]
    }
    ```
    """
    rules_data = body.get("rules", [])
    if not rules_data:
        raise HTTPException(status_code=400, detail="rules 为必填且不能为空")

    repo = MockRuleRepository(session)
    project_id = uuid.UUID(current_user.primary_project_id) if current_user.primary_project_id else None
    created: list[dict[str, Any]] = []
    for rule_data in rules_data:
        if "url_pattern" not in rule_data:
            raise HTTPException(status_code=400, detail="每条规则必须包含 url_pattern")

        model = MockRuleModel(
            url_pattern=rule_data["url_pattern"],
            method=rule_data.get("method", "ANY"),
            status_code=rule_data.get("status_code", 200),
            response_body=rule_data.get("response_body"),
            response_headers=rule_data.get("response_headers"),
            description=rule_data.get("description", ""),
            priority=rule_data.get("priority", 0),
            delay_ms=rule_data.get("delay_ms", 0),
            project_id=project_id,
        )
        created_model = await repo.create(model)
        _sync_to_memory(created_model)
        created.append(_model_to_dict(created_model))

    await session.commit()
    _log.info("mock_rules_batch_created", count=len(created))
    return {"success": True, "data": created, "total": len(created)}


# ── GET /mocks/rules ─────────────────────────────────────


@router.get(
    "/rules",
    summary="查询 Mock 规则列表",
)
async def list_rules(
    session: AsyncSession = Depends(get_db_session),
    url_pattern: str | None = Query(default=None, description="按 URL 模式筛选"),
    method: str | None = Query(default=None, description="按 HTTP 方法筛选"),
    current_user: CurrentUser = Depends(get_current_user),
):
    """查询所有已注册的 Mock 规则（按优先级降序）。"""
    repo = MockRuleRepository(session)
    project_id = uuid.UUID(current_user.primary_project_id) if current_user.primary_project_id else None
    rules, total = await repo.list_by_project(
        project_id=project_id,
        url_pattern=url_pattern,
        method=method,
        limit=1000,
    )

    return {
        "success": True,
        "data": [_model_to_dict(r) for r in rules],
        "total": total,
    }


# ── GET /mocks/rules/{rule_id} ───────────────────────────


@router.get(
    "/rules/{rule_id}",
    summary="查询单条 Mock 规则",
)
async def get_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """根据 ID 获取单条 Mock 规则。"""
    try:
        uid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的规则 ID: {rule_id}")

    repo = MockRuleRepository(session)
    rule = await repo.get(uid)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"规则不存在: {rule_id}")

    return {"success": True, "data": _model_to_dict(rule)}


# ── PUT /mocks/rules/{rule_id} ───────────────────────────


@router.put(
    "/rules/{rule_id}",
    summary="更新 Mock 规则",
)
async def update_rule(
    rule_id: str,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """更新 Mock 规则的部分字段。仅更新传入的非空字段。"""
    try:
        uid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的规则 ID: {rule_id}")

    repo = MockRuleRepository(session)
    model = await repo.get(uid)
    if model is None:
        raise HTTPException(status_code=404, detail=f"规则不存在: {rule_id}")

    # 更新传入的字段
    updatable_fields = [
        "url_pattern", "method", "status_code", "response_body",
        "response_headers", "description", "priority", "delay_ms", "enabled",
    ]
    for key in updatable_fields:
        if key in body and body[key] is not None:
            setattr(model, key, body[key])

    await repo.update(model)
    await session.commit()

    # 同步到内存 store
    _sync_to_memory(model)

    _log.info("mock_rule_updated", rule_id=rule_id)
    return {"success": True, "data": _model_to_dict(model)}


# ── DELETE /mocks/rules/{rule_id} ────────────────────────


@router.delete(
    "/rules/{rule_id}",
    summary="删除 Mock 规则",
)
async def delete_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """删除单条 Mock 规则。"""
    try:
        uid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的规则 ID: {rule_id}")

    repo = MockRuleRepository(session)
    deleted = await repo.delete_by_id(uid)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"规则不存在: {rule_id}")
    await session.commit()

    # 从内存 store 中移除
    store = get_mock_store()
    store.delete(rule_id)

    _log.info("mock_rule_deleted", rule_id=rule_id)
    return {"success": True, "message": f"规则 {rule_id} 已删除"}


# ── DELETE /mocks/rules ──────────────────────────────────


@router.delete(
    "/rules",
    summary="清空所有 Mock 规则",
)
async def clear_rules(
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """清空当前项目下的所有 Mock 规则。"""
    repo = MockRuleRepository(session)
    project_id = uuid.UUID(current_user.primary_project_id) if current_user.primary_project_id else None

    if project_id:
        count = await repo.delete_all_by_project(project_id)
    else:
        # 无项目时清除所有全局规则
        rules, _ = await repo.list_by_project(project_id=None, limit=10000)
        count = 0
        for r in rules:
            await repo.delete(r)
            count += 1

    await session.commit()

    # 清空内存 store
    store = get_mock_store()
    store.clear()

    _log.info("mock_rules_all_cleared", count=count)
    return {"success": True, "message": f"已清空 {count} 条规则"}


# ── GET /mocks/status ────────────────────────────────────


@router.get(
    "/status",
    summary="Mock 服务状态",
)
async def mock_status(
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取 Mock 服务的当前状态。"""
    repo = MockRuleRepository(session)
    project_id = uuid.UUID(current_user.primary_project_id) if current_user.primary_project_id else None
    rules, total = await repo.list_by_project(project_id=project_id, limit=10000)

    return {
        "success": True,
        "data": {
            "status": "running",
            "total_rules": total,
            "enabled_rules": sum(1 for r in rules if r.enabled),
            "rules": [_model_to_dict(r) for r in rules],
        },
    }
