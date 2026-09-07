from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_permission
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import PermissionResponse, RoleCreate, RoleResponse, RoleUpdate
from app.services.rbac_service import RBACService

router = APIRouter(prefix="/access", tags=["Access Management"])

require_roles = require_permission("roles")


def _to_response(role: Role) -> RoleResponse:
    return RoleResponse(
        role_id=role.role_id,
        role_name=role.role_name,
        description=role.description,
        is_system=role.is_system,
        is_active=role.is_active,
        permissions=sorted(role.permission_codes),
    )


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(db: AsyncSession = Depends(get_db), _user: User = Depends(require_roles)):
    return [PermissionResponse.model_validate(p) for p in await RBACService(db).list_permissions()]


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(db: AsyncSession = Depends(get_db), _user: User = Depends(require_roles)):
    return [_to_response(r) for r in await RBACService(db).list_roles()]


@router.post("/roles", response_model=RoleResponse, status_code=201)
async def create_role(body: RoleCreate, db: AsyncSession = Depends(get_db), _user: User = Depends(require_roles)):
    try:
        role = await RBACService(db).create_role(body.role_name, body.description, body.permissions)
        return _to_response(role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(role_id: int, body: RoleUpdate, db: AsyncSession = Depends(get_db), _user: User = Depends(require_roles)):
    try:
        role = await RBACService(db).update_role(role_id, **body.model_dump(exclude_unset=True))
        return _to_response(role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/roles/{role_id}")
async def delete_role(role_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require_roles)):
    try:
        await RBACService(db).delete_role(role_id)
        return {"message": "Role deleted."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
