"""用户管理路由（仅 admin 可见）— admin 后台管理用户

接口:
- GET    /api/v1/users              用户列表（分页）
- POST   /api/v1/users              创建用户（可指定角色）
- GET    /api/v1/users/{user_id}    用户详情
- PATCH  /api/v1/users/{user_id}    更新用户（角色/启用/重置密码）
- DELETE /api/v1/users/{user_id}    删除用户
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser, hash_password, require_role
from api.dependencies import get_db_session
from api.schemas.auth import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    UserResponse,
)
from api.schemas.common import (
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)
from framework.persistence.models.user import ProjectModel, UserModel
from framework.persistence.repositories.user_repo import (
    ProjectRepository,
    UserRepository,
)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _user_to_response(user: UserModel) -> UserResponse:
    """将 ORM 模型转换为 API 响应。"""
    from datetime import datetime, timezone

    return UserResponse(
        id=str(user.id),
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at if user.created_at else datetime.now(timezone.utc),
    )


# ── GET /users ──────────────────────────────────────────


@router.get(
    "",
    response_model=PaginatedResponse[UserResponse],
    summary="用户列表（admin）",
)
async def list_users(
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
    session: AsyncSession = Depends(get_db_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="按用户名模糊搜索"),
) -> PaginatedResponse[UserResponse]:
    """分页列出所有用户（仅 admin）。"""
    stmt = select(UserModel)
    if search:
        stmt = stmt.where(UserModel.username.ilike(f"%{search}%"))
    stmt = stmt.order_by(UserModel.created_at.desc())

    # 总数
    count_stmt = select(func.count()).select_from(UserModel)
    if search:
        count_stmt = count_stmt.where(UserModel.username.ilike(f"%{search}%"))
    total = (await session.execute(count_stmt)).scalar_one()

    # 分页
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    users = (await session.execute(stmt)).scalars().all()

    return PaginatedResponse(
        data=[_user_to_response(u) for u in users],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size if total else 0,
        ),
    )


# ── POST /users ──────────────────────────────────────────


@router.post(
    "",
    response_model=SuccessResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建用户（admin）",
)
async def create_user(
    body: AdminCreateUserRequest,
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
    session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[UserResponse]:
    """admin 在后台创建用户，可指定角色和初始密码。"""
    user_repo = UserRepository(session)
    if await user_repo.find_by_username(body.username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": f"用户名 '{body.username}' 已被注册",
                "code": "duplicate_username",
            },
        )

    user = UserModel(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=body.is_active,
    )
    created = await user_repo.create(user)

    # 自动创建同名个人项目并绑定
    project_repo = ProjectRepository(session)
    project = ProjectModel(
        name=f"{body.username}-project",
        description=f"{body.username} 的个人项目（由 {current_user.username} 创建）",
    )
    project = await project_repo.create(project)
    await project_repo.add_user(project.id, created.id)

    await session.commit()
    return SuccessResponse(data=_user_to_response(created))


# ── GET /users/{user_id} ────────────────────────────────


@router.get(
    "/{user_id}",
    response_model=SuccessResponse[UserResponse],
    summary="用户详情（admin）",
)
async def get_user(
    user_id: str,
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
    session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[UserResponse]:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "无效的用户 ID", "code": "invalid_id"},
        )

    user_repo = UserRepository(session)
    user = await user_repo.get(uid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "用户不存在", "code": "user_not_found"},
        )
    return SuccessResponse(data=_user_to_response(user))


# ── PATCH /users/{user_id} ──────────────────────────────


@router.patch(
    "/{user_id}",
    response_model=SuccessResponse[UserResponse],
    summary="更新用户（admin）",
)
async def update_user(
    user_id: str,
    body: AdminUpdateUserRequest,
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
    session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[UserResponse]:
    """更新用户角色、启用状态或重置密码（任一字段可选）。"""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "无效的用户 ID", "code": "invalid_id"},
        )

    user_repo = UserRepository(session)
    user = await user_repo.get(uid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "用户不存在", "code": "user_not_found"},
        )

    # 防止最后一个 admin 降级或停用自己
    if body.role is not None and body.role != "admin" and user.id == uuid.UUID(current_user.id):
        admin_count = (
            await session.execute(
                select(func.count()).select_from(UserModel).where(UserModel.role == "admin")
            )
        ).scalar_one()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "系统中只剩最后一个管理员，不能降级",
                    "code": "last_admin_protection",
                },
            )

    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        # 同样的保护
        if not body.is_active and user.id == uuid.UUID(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "不能停用自己",
                    "code": "self_deactivation_protection",
                },
            )
        user.is_active = body.is_active
    if body.new_password is not None:
        user.password_hash = hash_password(body.new_password)

    await user_repo.update(user)
    await session.commit()
    return SuccessResponse(data=_user_to_response(user))


# ── DELETE /users/{user_id} ─────────────────────────────


@router.delete(
    "/{user_id}",
    response_model=SuccessResponse[str],
    summary="删除用户（admin）",
)
async def delete_user(
    user_id: str,
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
    session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[str]:
    """删除用户（不可恢复）。保护：不能删除自己、最后一个 admin。"""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "无效的用户 ID", "code": "invalid_id"},
        )

    if uid == uuid.UUID(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "不能删除自己", "code": "self_delete_protection"},
        )

    user_repo = UserRepository(session)
    user = await user_repo.get(uid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "用户不存在", "code": "user_not_found"},
        )

    if user.role == "admin":
        admin_count = (
            await session.execute(
                select(func.count()).select_from(UserModel).where(UserModel.role == "admin")
            )
        ).scalar_one()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "系统中只剩最后一个管理员，不能删除",
                    "code": "last_admin_protection",
                },
            )

    await user_repo.delete_by_id(uid)
    await session.commit()
    return SuccessResponse(data=f"用户 {user.username} 已删除")
