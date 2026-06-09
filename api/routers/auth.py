"""认证路由 — 用户登录、注册、Token 刷新

接口:
- POST /api/v1/auth/login     — 用户登录，返回 JWT token
- POST /api/v1/auth/register  — 注册新用户
- GET  /api/v1/auth/me        — 获取当前用户信息
- POST /api/v1/auth/change-password — 修改密码
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import (
    CurrentUser,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from api.dependencies import get_db_session
from api.schemas.auth import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from api.schemas.common import ErrorResponse, SuccessResponse
from framework.persistence.models.user import ProjectModel, UserModel, UserProjectModel
from framework.persistence.repositories.user_repo import ProjectRepository, UserRepository

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _user_to_response(user: UserModel) -> UserResponse:
    """将 ORM 模型转换为 API 响应。"""
    return UserResponse(
        id=str(user.id),
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at if user.created_at else datetime.now(timezone.utc),
    )


# ── POST /auth/login ───────────────────────────────────────


@router.post(
    "/login",
    response_model=SuccessResponse[LoginResponse],
    summary="用户登录",
    responses={
        200: {"description": "登录成功"},
        401: {"model": ErrorResponse, "description": "用户名或密码错误"},
    },
)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """用户名 + 密码登录，返回 JWT 访问令牌。"""
    user_repo = UserRepository(session)
    user = await user_repo.find_by_username_with_projects(body.username)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "用户名或密码错误", "code": "invalid_credentials"},
        )

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "用户名或密码错误", "code": "invalid_credentials"},
        )

    token = create_access_token(
        user_id=str(user.id),
        username=user.username,
        role=user.role,
    )

    token_response = TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=480 * 60,  # 秒
    )

    return SuccessResponse(
        data=LoginResponse(
            token=token_response,
            user=_user_to_response(user),
        )
    )


# ── POST /auth/register ────────────────────────────────────


@router.post(
    "/register",
    response_model=SuccessResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="注册新用户",
    responses={
        201: {"description": "注册成功"},
        409: {"model": ErrorResponse, "description": "用户名已存在"},
    },
)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """注册新用户（公开注册，硬编码为 viewer 角色，防止提权）。

    安全设计：客户端不能通过注册请求提权，所有公开注册的用户都是 viewer。
    需要提升权限（editor/admin）必须由 admin 在后台管理界面创建或修改。
    """
    user_repo = UserRepository(session)

    # 检查用户名是否已存在
    existing = await user_repo.find_by_username(body.username)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": f"用户名 '{body.username}' 已被注册", "code": "duplicate_username"},
        )

    user = UserModel(
        username=body.username,
        password_hash=hash_password(body.password),
        role="viewer",  # 硬编码 viewer，禁止注册时指定角色
        is_active=True,
    )
    created = await user_repo.create(user)

    # 自动创建同名个人项目并绑定
    project_repo = ProjectRepository(session)
    project = ProjectModel(
        name=f"{body.username}-project",
        description=f"{body.username} 的个人项目",
    )
    project = await project_repo.create(project)
    await project_repo.add_user(project.id, created.id)

    await session.commit()

    return SuccessResponse(data=_user_to_response(created))


# ── GET /auth/me ────────────────────────────────────────────


@router.get(
    "/me",
    response_model=SuccessResponse[UserResponse],
    summary="获取当前用户信息",
    responses={
        200: {"description": "成功"},
        401: {"model": ErrorResponse, "description": "未登录或 token 无效"},
    },
)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """返回当前登录用户的详细信息。"""
    user_repo = UserRepository(session)
    from uuid import UUID

    user = await user_repo.get(UUID(current_user.id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "用户不存在", "code": "user_not_found"},
        )
    return SuccessResponse(data=_user_to_response(user))


# ── POST /auth/change-password ──────────────────────────────


@router.post(
    "/change-password",
    response_model=SuccessResponse[str],
    summary="修改密码",
    responses={
        200: {"description": "修改成功"},
        400: {"model": ErrorResponse, "description": "旧密码错误"},
        401: {"model": ErrorResponse, "description": "未登录"},
    },
)
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """修改当前登录用户的密码。"""
    user_repo = UserRepository(session)
    from uuid import UUID

    user = await user_repo.get(UUID(current_user.id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "用户不存在", "code": "user_not_found"},
        )

    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "旧密码错误", "code": "wrong_password"},
        )

    user.password_hash = hash_password(body.new_password)
    await user_repo.update(user)
    await session.commit()

    return SuccessResponse(data="密码修改成功")
