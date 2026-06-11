"""认证与授权核心模块 — JWT 令牌生成/验证 + 密码哈希 + 依赖注入

提供:
- create_access_token(): 生成 JWT。
- verify_password() / hash_password(): 密码哈希与验证。
- validate_password_strength(): 密码强度校验。
- get_current_user(): FastAPI 依赖，从 token 中解析当前用户。
- require_role(): FastAPI 依赖工厂，检查用户角色。
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session
from framework.persistence.repositories.user_repo import UserRepository

# ==================== JWT 配置 ====================


def _get_jwt_secret() -> str:
    """获取 JWT 签名密钥（环境变量优先，否则使用配置文件）。"""
    env_secret = os.environ.get("AUTOTEST_JWT_SECRET")
    if env_secret:
        return env_secret
    from framework.config import ConfigLoader

    loader = ConfigLoader()
    project_config, _ = loader.load()
    return getattr(project_config, "jwt_secret", "autotest-default-secret-change-me")


def _get_jwt_expire_minutes() -> int:
    """获取 JWT 过期时间（分钟）。"""
    env_expire = os.environ.get("AUTOTEST_JWT_EXPIRE_MINUTES")
    if env_expire:
        return int(env_expire)
    from framework.config import ConfigLoader

    loader = ConfigLoader()
    project_config, _ = loader.load()
    return getattr(project_config, "jwt_expire_minutes", 480)


def _get_refresh_token_expire_days() -> int:
    """获取 refresh token 过期时间（天）。"""
    env_expire = os.environ.get("AUTOTEST_REFRESH_TOKEN_EXPIRE_DAYS")
    if env_expire:
        return int(env_expire)
    from framework.config import ConfigLoader

    loader = ConfigLoader()
    project_config, _ = loader.load()
    return getattr(project_config, "refresh_token_expire_days", 7)


ALGORITHM = "HS256"

# HTTP Bearer 安全方案
_bearer_scheme = HTTPBearer(auto_error=False)


# ==================== 密码工具 ====================


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希密码是否匹配。

    Args:
        plain_password: 用户输入的明文密码。
        hashed_password: 数据库中存储的 bcrypt 哈希。

    Returns:
        是否匹配。
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def hash_password(password: str) -> str:
    """使用 bcrypt 哈希密码。

    Args:
        password: 明文密码。

    Returns:
        bcrypt 哈希字符串。
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


# ==================== 密码强度策略 ====================

# 登录失败锁定配置
_MAX_LOGIN_ATTEMPTS = 5
_LOCKOUT_MINUTES = 30
_LOGIN_FAILURES: dict[str, tuple[int, float]] = {}
"""内存中的登录失败计数器: {username: (failures, lockout_until_timestamp)}"""


def validate_password_strength(password: str) -> str | None:
    """校验密码强度，不符合要求时返回错误消息。

    要求:
    - 至少 8 个字符
    - 包含大写字母
    - 包含小写字母
    - 包含数字
    - 包含特殊字符 (!@#$%^&*()_+-=[]{}|;':\",./<>?)

    Args:
        password: 明文密码。

    Returns:
        校验通过返回 None，不通过返回错误描述字符串。
    """
    if len(password) < 8:
        return "密码长度至少为 8 个字符"

    if not any(c.isupper() for c in password):
        return "密码必须包含至少一个大写字母"

    if not any(c.islower() for c in password):
        return "密码必须包含至少一个小写字母"

    if not any(c.isdigit() for c in password):
        return "密码必须包含至少一个数字"

    specials = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
    if not any(c in specials for c in password):
        return "密码必须包含至少一个特殊字符 (!@#$%^&*()_+-=[]{}|;':\",./<>?)"

    return None


def check_login_lockout(username: str) -> str | None:
    """检查用户是否被登录锁定。

    Args:
        username: 用户名。

    Returns:
        未锁定返回 None，锁定中返回错误描述字符串。
    """
    if username not in _LOGIN_FAILURES:
        return None

    failures, lockout_until = _LOGIN_FAILURES[username]

    # 检查锁定是否已过期
    if lockout_until > 0 and time.time() > lockout_until:
        del _LOGIN_FAILURES[username]
        return None

    if failures >= _MAX_LOGIN_ATTEMPTS:
        remaining = max(0, int(lockout_until - time.time()))
        return f"账户已被锁定，请{remaining // 60}分{remaining % 60}秒后重试"

    return None


def record_login_failure(username: str) -> bool:
    """记录一次登录失败。

    Args:
        username: 用户名。

    Returns:
        True 表示用户已被锁定，False 表示仍可重试。
    """
    if username not in _LOGIN_FAILURES:
        _LOGIN_FAILURES[username] = (1, 0)
    else:
        failures, _ = _LOGIN_FAILURES[username]
        _LOGIN_FAILURES[username] = (failures + 1, 0)

    failures, _ = _LOGIN_FAILURES[username]

    if failures >= _MAX_LOGIN_ATTEMPTS:
        _LOGIN_FAILURES[username] = (
            failures,
            time.time() + _LOCKOUT_MINUTES * 60,
        )
        return True

    return False


def reset_login_failures(username: str) -> None:
    """登录成功后重置失败计数器。

    Args:
        username: 用户名。
    """
    _LOGIN_FAILURES.pop(username, None)


# ==================== JWT 令牌 ====================


def create_access_token(
    user_id: str,
    username: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """创建 JWT 访问令牌。

    Args:
        user_id: 用户 UUID 字符串。
        username: 用户名。
        role: 角色（admin/editor/viewer）。
        expires_delta: 自定义过期时长，None 则使用配置的默认值。

    Returns:
        JWT 字符串。
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=_get_jwt_expire_minutes())

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + expires_delta,
        "jti": uuid.uuid4().hex[:12],
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """解码并验证 JWT 令牌。

    Args:
        token: JWT 字符串。

    Returns:
        解码后的 payload 字典。

    Raises:
        HTTPException: token 无效或过期。
    """
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "令牌已过期，请重新登录", "code": "token_expired"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "无效的认证令牌", "code": "invalid_token"},
        )
    return payload


def create_refresh_token(user_id: str) -> str:
    """创建 JWT refresh token（仅包含 user_id，长过期时间）。

    Args:
        user_id: 用户 UUID 字符串。

    Returns:
        JWT refresh token 字符串。
    """
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(days=_get_refresh_token_expire_days())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + expires_delta,
        "jti": uuid.uuid4().hex[:12],
        "type": "refresh",
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=ALGORITHM)


def decode_refresh_token(token: str) -> dict:
    """解码并验证 refresh token。

    Args:
        token: JWT refresh token 字符串。

    Returns:
        解码后的 payload 字典。

    Raises:
        HTTPException: token 无效、过期或类型不正确。
    """
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "刷新令牌已过期，请重新登录", "code": "refresh_token_expired"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "无效的刷新令牌", "code": "invalid_refresh_token"},
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "令牌类型不正确", "code": "invalid_token_type"},
        )

    return payload


# ==================== 认证用户上下文 ====================


class CurrentUser:
    """当前认证用户上下文。

    Attributes:
        id: 用户 UUID 字符串。
        username: 用户名。
        role: 角色。
        project_ids: 用户所属项目的 ID 列表。
    """

    def __init__(
        self,
        id: str,
        username: str,
        role: str,
        project_ids: list[str],
    ) -> None:
        self.id = id
        self.username = username
        self.role = role
        self.project_ids = project_ids

    @property
    def primary_project_id(self) -> str | None:
        """返回用户的第一个项目 ID（如有关联）。"""
        return self.project_ids[0] if self.project_ids else None

    def is_admin(self) -> bool:
        return self.role == "admin"

    def has_role(self, *roles: str) -> bool:
        return self.role in roles


# ==================== FastAPI 依赖 ====================


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
    session: AsyncSession = Depends(get_db_session),
) -> CurrentUser:
    """FastAPI 依赖：从 Authorization header 中解析当前用户。

    Args:
        credentials: Bearer token 凭证（可选，未提供时返回 401）。
        session: 数据库会话。

    Returns:
        CurrentUser 实例。

    Raises:
        HTTPException 401: 未提供 token 或 token 无效。
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "请先登录", "code": "missing_token"},
        )

    payload = decode_access_token(credentials.credentials)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "令牌内容无效", "code": "invalid_payload"},
        )

    # 检查用户是否仍存在于数据库且处于激活状态
    repo = UserRepository(session)
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "无效的用户标识", "code": "invalid_user_id"},
        )

    user = await repo.get(uid)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "用户不存在或已禁用", "code": "user_inactive"},
        )

    # 获取用户项目
    project_ids = await repo.get_project_ids(uid)
    project_id_strs = [str(pid) for pid in project_ids]

    return CurrentUser(
        id=str(user.id),
        username=user.username,
        role=user.role,
        project_ids=project_id_strs,
    )


def require_role(*roles: str):
    """FastAPI 依赖工厂：要求用户具有指定角色之一。

    用法:
        @router.post("/cases")
        async def create_case(
            current_user: CurrentUser = Depends(require_role("admin", "editor")),
        ):
            ...

    Args:
        *roles: 允许的角色列表，如 "admin", "editor"。

    Returns:
        依赖函数，验证通过后返回 CurrentUser。
    """

    async def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not current_user.has_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "权限不足",
                    "required_roles": list(roles),
                    "actual_role": current_user.role,
                    "code": "forbidden",
                },
            )
        return current_user

    return _check


def check_project_access(
    resource_project_id: str | None,
    current_user: CurrentUser,
    resource_type: str = "资源",
) -> None:
    """检查用户是否有权访问指定项目下的资源。

    admin 角色可以访问任何项目，其他角色只能访问自己绑定的项目。
    资源无 project_id（null）时，所有用户均可访问（向后兼容）。

    Args:
        resource_project_id: 资源所属项目 ID（None 表示全局资源）。
        current_user: 当前认证用户。
        resource_type: 资源类型描述（用于错误消息）。

    Raises:
        HTTPException 403: 用户无权访问。
    """
    if resource_project_id is None:
        return  # 无项目关联的资源允许所有人访问

    if current_user.is_admin():
        return  # 管理员可访问所有项目

    if resource_project_id in current_user.project_ids:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": f"无权访问该项目下的{resource_type}",
            "code": "project_access_denied",
        },
    )
