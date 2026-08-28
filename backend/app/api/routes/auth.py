from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_admin
from app.models.user import ROLES, ROLE_PERMISSIONS, User
from app.schemas.auth import (
    LoginRequest, PasswordChange, RefreshRequest, TokenResponse,
    UserCreate, UserListResponse, UserResponse, UserUpdate,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        access, refresh, user = await AuthService(db).login(body.username, body.password)
        return TokenResponse(access_token=access, refresh_token=refresh, user=UserResponse.model_validate(user))
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


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


@router.get("/roles")
async def list_roles(_user: User = Depends(get_current_user)):
    return [{"role": r, "permissions": sorted(ROLE_PERMISSIONS[r])} for r in ROLES]


# --- Admin: user management ---

@router.get("/users", response_model=UserListResponse)
async def list_users(db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    users, total = await AuthService(db).list_users()
    return UserListResponse(items=[UserResponse.model_validate(u) for u in users], total=total)


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    try:
        user = await AuthService(db).register(body.username, body.password, body.full_name, body.role)
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, body: UserUpdate, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    try:
        user = await AuthService(db).update_user(user_id, **body.model_dump(exclude_unset=True))
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users/{user_id}/reset-password", response_model=UserResponse)
async def reset_password(user_id: int, body: PasswordChange, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    try:
        user = await AuthService(db).change_password(user_id, body.new_password)
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
