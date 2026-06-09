"""认证相关 Schema: 登录、注册、Token、用户信息"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ==================== 请求 ====================


class LoginRequest(BaseModel):
    """登录请求"""

    username: str = Field(..., min_length=1, max_length=128, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class RegisterRequest(BaseModel):
    """注册请求（公开注册，默认 viewer 角色，无权选择）"""

    username: str = Field(
        ..., min_length=3, max_length=128, description="用户名（3-128 字符）"
    )
    password: str = Field(
        ..., min_length=6, max_length=128, description="密码（最少 6 字符）"
    )

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("用户名只能包含字母、数字、下划线或连字符")
        return v


class AdminCreateUserRequest(BaseModel):
    """管理员创建用户请求（可指定角色）"""

    username: str = Field(
        ..., min_length=3, max_length=128, description="用户名（3-128 字符）"
    )
    password: str = Field(
        ..., min_length=6, max_length=128, description="初始密码（最少 6 字符）"
    )
    role: str = Field(
        default="viewer",
        pattern="^(admin|editor|viewer)$",
        description="角色: admin/editor/viewer",
    )
    is_active: bool = Field(default=True, description="是否启用")


class AdminUpdateUserRequest(BaseModel):
    """管理员更新用户请求"""

    role: str | None = Field(
        default=None,
        pattern="^(admin|editor|viewer)$",
        description="角色（可选）",
    )
    is_active: bool | None = Field(default=None, description="是否启用（可选）")
    new_password: str | None = Field(
        default=None, min_length=6, max_length=128, description="重置密码（可选）"
    )


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""

    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码")


# ==================== 响应 ====================


class TokenResponse(BaseModel):
    """JWT Token 响应"""

    access_token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")


class UserResponse(BaseModel):
    """用户信息响应"""

    id: str = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    role: str = Field(..., description="角色")
    is_active: bool = Field(default=True, description="是否启用")
    created_at: datetime = Field(..., description="创建时间")

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    """登录完整响应"""

    token: TokenResponse
    user: UserResponse
