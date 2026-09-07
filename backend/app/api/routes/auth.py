from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db, require_permission
from app.models.role import DEFAULT_SIGNUP_ROLE
from app.models.user import User
from app.schemas.auth import (
    AuthProvidersResponse, GoogleAuthRequest, LoginRequest, PasswordChange, RefreshRequest,
    RoleResponse, SignupRequest, TokenResponse, UserCreate, UserListResponse, UserResponse, UserUpdate,
)
from app.services.auth_service import AuthService
from app.services.rbac_service import RBACService

router = APIRouter(prefix="/auth", tags=["Authentication"])

require_users = require_permission("users")


@router.get("/providers", response_model=AuthProvidersResponse)
async def providers():
    return AuthProvidersResponse(
        google_enabled=settings.google_enabled,
        google_client_id=settings.GOOGLE_CLIENT_ID or None,
        signup_enabled=settings.GOOGLE_ALLOW_SIGNUP,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        access, refresh, user = await AuthService(db).login(body.username, body.password)
        return TokenResponse(access_token=access, refresh_token=refresh, user=UserResponse.model_validate(user))
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/google", response_model=TokenResponse)
async def google_login(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    if not settings.google_enabled:
        raise HTTPException(status_code=400, detail="Google sign-in is not configured.")
    try:
        access, refresh, user = await AuthService(db).login_with_google(body.credential)
        return TokenResponse(access_token=access, refresh_token=refresh, user=UserResponse.model_validate(user))
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    if not settings.GOOGLE_ALLOW_SIGNUP:
        raise HTTPException(status_code=403, detail="Self sign-up is disabled.")
    service = AuthService(db)
    try:
        await service.register(
            body.username, body.password, body.full_name,
            role=settings.GOOGLE_SIGNUP_ROLE or DEFAULT_SIGNUP_ROLE, email=body.email,
        )
        access, refresh, user = await service.login(body.username, body.password)
        return TokenResponse(access_token=access, refresh_token=refresh, user=UserResponse.model_validate(user))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        access, new_refresh = await AuthService(db).refresh_token(body.refresh_token)
        return TokenResponse(access_token=access, refresh_token=new_refresh)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    roles = await RBACService(db).list_roles()
    return [
        RoleResponse(
            role_id=r.role_id, role_name=r.role_name, description=r.description,
            is_system=r.is_system, is_active=r.is_active, permissions=sorted(r.permission_codes),
        )
        for r in roles
    ]


# --- User management (requires the "users" permission) ---

@router.get("/users", response_model=UserListResponse)
async def list_users(db: AsyncSession = Depends(get_db), _user: User = Depends(require_users)):
    users, total = await AuthService(db).list_users()
    return UserListResponse(items=[UserResponse.model_validate(u) for u in users], total=total)


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db), _user: User = Depends(require_users)):
    try:
        user = await AuthService(db).register(body.username, body.password, body.full_name, body.role, body.email)
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, body: UserUpdate, db: AsyncSession = Depends(get_db), _user: User = Depends(require_users)):
    try:
        user = await AuthService(db).update_user(user_id, **body.model_dump(exclude_unset=True))
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users/{user_id}/reset-password", response_model=UserResponse)
async def reset_password(user_id: int, body: PasswordChange, db: AsyncSession = Depends(get_db), _user: User = Depends(require_users)):
    try:
        user = await AuthService(db).change_password(user_id, body.new_password)
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
