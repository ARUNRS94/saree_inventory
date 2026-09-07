from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import DEFAULT_ROLES, PERMISSION_CATALOGUE, Permission, Role
from app.models.user import User


async def seed_rbac(session: AsyncSession) -> None:
    """Create the permission catalogue and the built-in roles if missing."""
    existing_codes = set((await session.execute(select(Permission.code))).scalars().all())
    for code, name, description in PERMISSION_CATALOGUE:
        if code not in existing_codes:
            session.add(Permission(code=code, name=name, description=description))
    await session.flush()

    permissions = {p.code: p for p in (await session.execute(select(Permission))).scalars().all()}

    for role_name, (description, codes) in DEFAULT_ROLES.items():
        role = await session.scalar(select(Role).where(Role.role_name == role_name))
        if role is None:
            session.add(Role(
                role_name=role_name,
                description=description,
                is_system=True,
                permissions=[permissions[c] for c in sorted(codes)],
            ))
    await session.flush()


class RBACService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_permissions(self) -> list[Permission]:
        result = await self.session.execute(select(Permission).order_by(Permission.code))
        return list(result.scalars().all())

    async def list_roles(self) -> list[Role]:
        result = await self.session.execute(select(Role).order_by(Role.role_id))
        return list(result.scalars().all())

    async def get_role(self, role_id: int) -> Role:
        role = await self.session.get(Role, role_id)
        if role is None:
            raise ValueError("Role not found.")
        return role

    async def get_role_by_name(self, role_name: str) -> Role:
        role = await self.session.scalar(select(Role).where(Role.role_name == role_name))
        if role is None:
            raise ValueError(f"Unknown role: {role_name}")
        return role

    async def _resolve_permissions(self, codes: list[str]) -> list[Permission]:
        result = await self.session.execute(select(Permission).where(Permission.code.in_(codes)))
        found = {p.code: p for p in result.scalars().all()}
        unknown = sorted(set(codes) - set(found))
        if unknown:
            raise ValueError(f"Unknown permissions: {', '.join(unknown)}")
        return [found[c] for c in dict.fromkeys(codes)]

    async def create_role(self, role_name: str, description: str | None, permissions: list[str]) -> Role:
        role_name = role_name.strip().lower()
        if not role_name:
            raise ValueError("Role name is required.")
        if await self.session.scalar(select(Role).where(Role.role_name == role_name)):
            raise ValueError("Role already exists.")
        role = Role(
            role_name=role_name,
            description=description,
            permissions=await self._resolve_permissions(permissions),
        )
        self.session.add(role)
        await self.session.flush()
        return role

    async def update_role(
        self,
        role_id: int,
        role_name: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
        permissions: list[str] | None = None,
    ) -> Role:
        role = await self.get_role(role_id)
        if role.is_system and (role_name is not None or is_active is not None):
            raise ValueError("Built-in roles cannot be renamed or deactivated.")
        if role_name is not None:
            new_name = role_name.strip().lower()
            clash = await self.session.scalar(select(Role).where(Role.role_name == new_name, Role.role_id != role_id))
            if clash:
                raise ValueError("Role already exists.")
            role.role_name = new_name
        if description is not None:
            role.description = description
        if is_active is not None:
            role.is_active = is_active
        if permissions is not None:
            if role.role_name == "admin":
                raise ValueError("The admin role must keep all permissions.")
            role.permissions = await self._resolve_permissions(permissions)
        await self.session.flush()
        return role

    async def delete_role(self, role_id: int) -> None:
        role = await self.get_role(role_id)
        if role.is_system:
            raise ValueError("Built-in roles cannot be deleted.")
        assigned = await self.session.scalar(select(func.count()).select_from(User).where(User.role_id == role_id)) or 0
        if assigned:
            raise ValueError(f"Role is assigned to {assigned} user(s). Reassign them first.")
        await self.session.delete(role)
        await self.session.flush()
