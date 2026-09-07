from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1)


class GoogleAuthRequest(BaseModel):
    """ID token issued by Google Identity Services."""

    credential: str = Field(min_length=1)


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=200)


class AuthProvidersResponse(BaseModel):
    google_enabled: bool
    google_client_id: str | None = None
    signup_enabled: bool


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    user_id: int
    username: str
    email: str | None = None
    full_name: str
    role: str
    role_id: int | None = None
    permissions: list[str] = []
    auth_provider: str = "local"
    avatar_url: str | None = None
    is_active: bool
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse | None = None


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr | None = None
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=200)
    role: str = "viewer"


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    is_active: bool | None = None


class PasswordChange(BaseModel):
    new_password: str = Field(min_length=8)


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int


# --- Access management ---

class PermissionResponse(BaseModel):
    permission_id: int
    code: str
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}


class RoleResponse(BaseModel):
    role_id: int
    role_name: str
    description: str | None = None
    is_system: bool
    is_active: bool
    permissions: list[str] = []

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    role_name: str = Field(min_length=2, max_length=50)
    description: str | None = None
    permissions: list[str] = []


class RoleUpdate(BaseModel):
    role_name: str | None = Field(default=None, min_length=2, max_length=50)
    description: str | None = None
    is_active: bool | None = None
    permissions: list[str] | None = None
