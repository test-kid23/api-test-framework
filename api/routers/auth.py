"""认证路由 — 用户登录、注册、Token 刷新

接口:
- POST /api/v1/auth/login     — 用户登录，返回 JWT token
- POST /api/v1/auth/register  — 注册新用户
- GET  /api/v1/auth/me        — 获取当前用户信息
- POST /api/v1/auth/change-password — 修改密码
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import (
    CurrentUser,
    check_login_lockout,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user,
    hash_password,
    record_login_failure,
    reset_login_failures,
    validate_password_strength,
    verify_password,
)
from api.dependencies import get_db_session
from api.schemas.auth import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
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
    """用户名 + 密码登录，返回 JWT 访问令牌。

    安全策略:
    - 连续 5 次失败锁定 30 分钟
    - 登录成功后重置失败计数器
    """
    # 检查登录锁定
    lockout_msg = check_login_lockout(body.username)
    if lockout_msg:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={"error": lockout_msg, "code": "account_locked"},
        )

    user_repo = UserRepository(session)
    # 登录仅需验证用户名+密码，不需要加载关联项目数据
    user = await user_repo.find_by_username(body.username)

    if user is None or not user.is_active:
        record_login_failure(body.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "用户名或密码错误", "code": "invalid_credentials"},
        )

    if not verify_password(body.password, user.password_hash):
        record_login_failure(body.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "用户名或密码错误", "code": "invalid_credentials"},
        )

    # 登录成功，重置失败计数器
    reset_login_failures(body.username)

    token = create_access_token(
        user_id=str(user.id),
        username=user.username,
        role=user.role,
    )
    refresh_token = create_refresh_token(user_id=str(user.id))

    token_response = TokenResponse(
        access_token=token,
        refresh_token=refresh_token,
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

    密码强度要求:
    - 至少 8 个字符
    - 包含大写字母、小写字母、数字、特殊字符
    """
    # 密码强度校验
    password_error = validate_password_strength(body.password)
    if password_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": password_error, "code": "weak_password"},
        )

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
    """修改当前登录用户的密码。

    密码强度要求与注册相同:
    - 至少 8 个字符
    - 包含大写字母、小写字母、数字、特殊字符
    """
    # 密码强度校验
    password_error = validate_password_strength(body.new_password)
    if password_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": password_error, "code": "weak_password"},
        )

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


# ── POST /auth/refresh ──────────────────────────────────────


@router.post(
    "/refresh",
    response_model=SuccessResponse[TokenResponse],
    summary="刷新 Token",
    responses={
        200: {"description": "刷新成功"},
        401: {"model": ErrorResponse, "description": "刷新令牌无效或过期"},
    },
)
async def refresh_token(
    body: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """使用 refresh token 获取新的 access token。

    前端在 access token 过期时自动调用此接口，无需用户重新登录。
    refresh token 有效期更长（默认 7 天），过期后需要重新登录。
    """
    payload = decode_refresh_token(body.refresh_token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "刷新令牌内容无效", "code": "invalid_refresh_payload"},
        )

    # 验证用户是否仍处于激活状态
    user_repo = UserRepository(session)
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "无效的用户标识", "code": "invalid_user_id"},
        )

    user = await user_repo.get(uid)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "用户不存在或已禁用", "code": "user_inactive"},
        )

    new_access_token = create_access_token(
        user_id=str(user.id),
        username=user.username,
        role=user.role,
    )

    return SuccessResponse(
        data=TokenResponse(
            access_token=new_access_token,
            token_type="bearer",
            expires_in=480 * 60,
        )
    )
