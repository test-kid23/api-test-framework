"""Mock 规则管理路由

接口：
- POST   /api/v1/mocks/rules       注册规则
- GET    /api/v1/mocks/rules       规则列表
- GET    /api/v1/mocks/rules/{id}  规则详情
- PUT    /api/v1/mocks/rules/{id}  更新规则
- DELETE /api/v1/mocks/rules/{id}  删除规则
- DELETE /api/v1/mocks/rules       清空规则

因为 Mock 规则采用内存存储（无需数据库持久化），
所有操作直接通过 MockRuleStore 完成，不依赖 AsyncSession。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.auth import CurrentUser, get_current_user, require_role
from framework.mock.rule_store import get_mock_store
from framework.utils.logger import Logger

router = APIRouter(prefix="/api/v1/mocks", tags=["mocks"])
_log = Logger.get("api.mocks")


# ── Helpers ───────────────────────────────────────────────


def _rule_to_dict(rule: Any) -> dict[str, Any]:
    """将 MockRule 转为字典"""
    return {
        "id": rule.id,
        "url_pattern": rule.url_pattern,
        "method": rule.method,
        "status_code": rule.status_code,
        "response_body": rule.response_body,
        "response_headers": rule.response_headers,
        "description": rule.description,
        "enabled": rule.enabled,
        "priority": rule.priority,
        "delay_ms": rule.delay_ms,
    }


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

    store = get_mock_store()
    rule = store.register(
        url_pattern=body["url_pattern"],
        method=body.get("method", "ANY"),
        status_code=body.get("status_code", 200),
        response_body=body.get("response_body"),
        response_headers=body.get("response_headers"),
        description=body.get("description", ""),
        priority=body.get("priority", 0),
        delay_ms=body.get("delay_ms", 0),
    )

    _log.info("mock_rule_created_via_api", rule_id=rule.id, url_pattern=rule.url_pattern)
    return {"success": True, "data": _rule_to_dict(rule)}


# ── POST /mocks/rules/batch ──────────────────────────────


@router.post(
    "/rules/batch",
    status_code=status.HTTP_201_CREATED,
    summary="批量注册 Mock 规则",
)
async def create_rules_batch(
    body: dict[str, Any],
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

    store = get_mock_store()
    created: list[dict[str, Any]] = []
    for rule_data in rules_data:
        if "url_pattern" not in rule_data:
            raise HTTPException(status_code=400, detail="每条规则必须包含 url_pattern")

        rule = store.register(
            url_pattern=rule_data["url_pattern"],
            method=rule_data.get("method", "ANY"),
            status_code=rule_data.get("status_code", 200),
            response_body=rule_data.get("response_body"),
            response_headers=rule_data.get("response_headers"),
            description=rule_data.get("description", ""),
            priority=rule_data.get("priority", 0),
            delay_ms=rule_data.get("delay_ms", 0),
        )
        created.append(_rule_to_dict(rule))

    _log.info("mock_rules_batch_created", count=len(created))
    return {"success": True, "data": created, "total": len(created)}


# ── GET /mocks/rules ─────────────────────────────────────


@router.get(
    "/rules",
    summary="查询 Mock 规则列表",
)
async def list_rules(
    url_pattern: str | None = Query(default=None, description="按 URL 模式筛选"),
    method: str | None = Query(default=None, description="按 HTTP 方法筛选"),
    current_user: CurrentUser = Depends(get_current_user),
):
    """查询所有已注册的 Mock 规则（按优先级降序）。"""
    store = get_mock_store()
    rules = store.list_all()

    if url_pattern:
        rules = [r for r in rules if url_pattern in r.url_pattern]
    if method:
        method_upper = method.upper()
        rules = [r for r in rules if r.method == "ANY" or r.method == method_upper]

    return {
        "success": True,
        "data": [_rule_to_dict(r) for r in rules],
        "total": len(rules),
    }


# ── GET /mocks/rules/{rule_id} ───────────────────────────


@router.get(
    "/rules/{rule_id}",
    summary="查询单条 Mock 规则",
)
async def get_rule(
    rule_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """根据 ID 获取单条 Mock 规则。"""
    store = get_mock_store()
    rule = store.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"规则不存在: {rule_id}")

    return {"success": True, "data": _rule_to_dict(rule)}


# ── PUT /mocks/rules/{rule_id} ───────────────────────────


@router.put(
    "/rules/{rule_id}",
    summary="更新 Mock 规则",
)
async def update_rule(
    rule_id: str,
    body: dict[str, Any],
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """更新 Mock 规则的部分字段。仅更新传入的非空字段。"""
    store = get_mock_store()
    rule = store.update(rule_id, **body)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"规则不存在: {rule_id}")

    _log.info("mock_rule_updated", rule_id=rule_id)
    return {"success": True, "data": _rule_to_dict(rule)}


# ── DELETE /mocks/rules/{rule_id} ────────────────────────


@router.delete(
    "/rules/{rule_id}",
    summary="删除 Mock 规则",
)
async def delete_rule(
    rule_id: str,
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """删除单条 Mock 规则。"""
    store = get_mock_store()
    deleted = store.delete(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"规则不存在: {rule_id}")

    _log.info("mock_rule_deleted", rule_id=rule_id)
    return {"success": True, "message": f"规则 {rule_id} 已删除"}


# ── DELETE /mocks/rules ──────────────────────────────────


@router.delete(
    "/rules",
    summary="清空所有 Mock 规则",
)
async def clear_rules(
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """清空所有已注册的 Mock 规则。"""
    store = get_mock_store()
    count = store.clear()
    _log.info("mock_rules_all_cleared", count=count)
    return {"success": True, "message": f"已清空 {count} 条规则"}


# ── GET /mocks/status ────────────────────────────────────


@router.get(
    "/status",
    summary="Mock 服务状态",
)
async def mock_status(
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取 Mock 服务的当前状态。"""
    store = get_mock_store()
    rules = store.list_all()
    return {
        "success": True,
        "data": {
            "status": "running",
            "total_rules": len(rules),
            "enabled_rules": sum(1 for r in rules if r.enabled),
            "rules": [_rule_to_dict(r) for r in rules],
        },
    }
