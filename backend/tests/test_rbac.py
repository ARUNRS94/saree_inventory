"""Roles and permissions."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import DEFAULT_ROLES, PERMISSION_CATALOGUE, Permission, Role
from app.services.auth_service import AuthService
from app.services.rbac_service import RBACService, seed_rbac


async def test_seeding_creates_the_whole_catalogue(db: AsyncSession):
    rbac = RBACService(db)
    assert len(await rbac.list_permissions()) == len(PERMISSION_CATALOGUE)
    assert {r.role_name for r in await rbac.list_roles()} == set(DEFAULT_ROLES)


async def test_seeding_is_idempotent(db: AsyncSession):
    before = await db.scalar(select(func.count()).select_from(Permission))
    await seed_rbac(db)
    await seed_rbac(db)
    assert await db.scalar(select(func.count()).select_from(Permission)) == before


async def test_admin_holds_every_permission(db: AsyncSession):
    admin = await RBACService(db).get_role_by_name("admin")
    assert admin.permission_codes == {code for code, _, _ in PERMISSION_CATALOGUE}


async def test_reseeding_grants_new_permissions_to_admin(db: AsyncSession):
    """A permission added to the catalogue later must reach the existing admin role."""
    db.add(Permission(code="exports", name="Exports", description="Added later"))
    await db.flush()

    await seed_rbac(db)
    admin = await RBACService(db).get_role_by_name("admin")
    assert "exports" in admin.permission_codes


async def test_built_in_roles_carry_their_documented_permissions(db: AsyncSession):
    rbac = RBACService(db)
    for name, (_, codes) in DEFAULT_ROLES.items():
        role = await rbac.get_role_by_name(name)
        assert role.permission_codes == codes
        assert role.is_system is True


async def test_unknown_role_lookup(db: AsyncSession):
    with pytest.raises(ValueError, match="Unknown role"):
        await RBACService(db).get_role_by_name("wizard")


async def test_missing_role_by_id(db: AsyncSession):
    with pytest.raises(ValueError, match="Role not found"):
        await RBACService(db).get_role(9999)


# --- custom roles ---

async def test_create_custom_role(db: AsyncSession):
    role = await RBACService(db).create_role("auditor", "Read-only reviewer", ["reports", "inventory"])
    assert role.role_name == "auditor"
    assert role.is_system is False
    assert role.permission_codes == {"reports", "inventory"}


async def test_role_names_are_lower_cased(db: AsyncSession):
    role = await RBACService(db).create_role("  AuDiToR  ", None, ["reports"])
    assert role.role_name == "auditor"


async def test_create_role_requires_a_name(db: AsyncSession):
    with pytest.raises(ValueError, match="Role name is required"):
        await RBACService(db).create_role("   ", None, ["reports"])


async def test_duplicate_role_rejected(db: AsyncSession):
    rbac = RBACService(db)
    await rbac.create_role("auditor", None, ["reports"])
    with pytest.raises(ValueError, match="Role already exists"):
        await rbac.create_role("auditor", None, ["reports"])


async def test_creating_a_role_with_an_unknown_permission(db: AsyncSession):
    with pytest.raises(ValueError, match="Unknown permissions: teleport"):
        await RBACService(db).create_role("wizard", None, ["reports", "teleport"])


async def test_update_role_permissions(db: AsyncSession):
    rbac = RBACService(db)
    role = await rbac.create_role("auditor", None, ["reports"])
    updated = await rbac.update_role(role.role_id, permissions=["reports", "inventory", "purchase"])
    assert updated.permission_codes == {"reports", "inventory", "purchase"}


async def test_rename_role_clash_rejected(db: AsyncSession):
    rbac = RBACService(db)
    await rbac.create_role("auditor", None, ["reports"])
    other = await rbac.create_role("reviewer", None, ["reports"])
    with pytest.raises(ValueError, match="Role already exists"):
        await rbac.update_role(other.role_id, role_name="auditor")


async def test_built_in_roles_cannot_be_renamed_or_disabled(db: AsyncSession):
    rbac = RBACService(db)
    manager = await rbac.get_role_by_name("manager")
    with pytest.raises(ValueError, match="cannot be renamed or deactivated"):
        await rbac.update_role(manager.role_id, role_name="supervisor")
    with pytest.raises(ValueError, match="cannot be renamed or deactivated"):
        await rbac.update_role(manager.role_id, is_active=False)


async def test_admin_permissions_cannot_be_reduced(db: AsyncSession):
    rbac = RBACService(db)
    admin = await rbac.get_role_by_name("admin")
    with pytest.raises(ValueError, match="must keep all permissions"):
        await rbac.update_role(admin.role_id, permissions=["reports"])


async def test_built_in_role_description_can_still_be_edited(db: AsyncSession):
    rbac = RBACService(db)
    manager = await rbac.get_role_by_name("manager")
    updated = await rbac.update_role(manager.role_id, description="Updated wording")
    assert updated.description == "Updated wording"


async def test_built_in_roles_cannot_be_deleted(db: AsyncSession):
    rbac = RBACService(db)
    viewer = await rbac.get_role_by_name("viewer")
    with pytest.raises(ValueError, match="cannot be deleted"):
        await rbac.delete_role(viewer.role_id)


async def test_delete_custom_role(db: AsyncSession):
    rbac = RBACService(db)
    role = await rbac.create_role("temporary", None, ["reports"])
    await rbac.delete_role(role.role_id)
    assert await db.scalar(select(Role).where(Role.role_name == "temporary")) is None


async def test_role_in_use_cannot_be_deleted(db: AsyncSession):
    rbac = RBACService(db)
    role = await rbac.create_role("auditor", None, ["reports"])
    await AuthService(db).register("aud1", "password123", "Auditor", role="auditor")
    with pytest.raises(ValueError, match="assigned to 1 user"):
        await rbac.delete_role(role.role_id)


async def test_inactive_role_grants_no_permissions(db: AsyncSession):
    rbac = RBACService(db)
    role = await rbac.create_role("suspended", None, ["reports", "inventory"])
    user = await AuthService(db).register("susp", "password123", "Susp", role="suspended")
    assert user.permissions == ["inventory", "reports"]

    await rbac.update_role(role.role_id, is_active=False)
    await db.refresh(user)
    assert user.permissions == []


async def test_registering_into_an_inactive_role_is_refused(db: AsyncSession):
    rbac = RBACService(db)
    role = await rbac.create_role("frozen", None, ["reports"])
    await rbac.update_role(role.role_id, is_active=False)
    with pytest.raises(ValueError, match="is inactive"):
        await AuthService(db).register("nope", "password123", "Nope", role="frozen")
