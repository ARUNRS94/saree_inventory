"""Authentication: registration, login, tokens and password handling."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token, decode_token, hash_password, needs_rehash, verify_password,
)
from app.models.user import AUTH_PROVIDER_GOOGLE, AUTH_PROVIDER_LOCAL, User
from app.services.auth_service import AuthService, ensure_default_admin


# --- password hashing ---

def test_hashes_are_salted_and_verifiable():
    first, second = hash_password("correct horse"), hash_password("correct horse")
    assert first != second, "each hash must use a fresh salt"
    assert verify_password("correct horse", first)
    assert not verify_password("wrong", first)


def test_verify_password_handles_provider_only_accounts():
    """Google-only users have no password hash; verifying must fail, not explode."""
    assert verify_password("anything", None) is False
    assert verify_password("anything", "") is False


def test_needs_rehash_is_false_for_current_policy():
    assert needs_rehash(hash_password("x")) is False
    assert needs_rehash(None) is False
    assert needs_rehash("not-a-hash") is False


def test_needs_rehash_flags_a_heavier_legacy_hash():
    from argon2 import PasswordHasher

    legacy = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4).hash("x")
    assert needs_rehash(legacy) is True
    # Old hashes must still verify, or tuning the cost would lock everyone out.
    assert verify_password("x", legacy)


# --- tokens ---

def test_access_and_refresh_tokens_are_distinguishable():
    access = create_access_token({"sub": "1"})
    assert decode_token(access)["type"] == "access"
    assert decode_token(access)["sub"] == "1"


def test_decode_rejects_tampered_tokens():
    token = create_access_token({"sub": "1"})
    assert decode_token(token + "x") is None
    assert decode_token("garbage") is None


# --- registration ---

async def test_register_defaults_to_the_signup_role(db: AsyncSession):
    user = await AuthService(db).register("newbie", "password123", "New Bie")
    assert user.role == "viewer"
    assert user.permissions == ["inventory", "reports"]
    assert user.auth_provider == AUTH_PROVIDER_LOCAL


async def test_register_rejects_duplicate_username(db: AsyncSession):
    auth = AuthService(db)
    await auth.register("sameuser", "password123", "First")
    with pytest.raises(ValueError, match="Username already exists"):
        await auth.register("sameuser", "password123", "Second")


async def test_register_normalises_and_deduplicates_email(db: AsyncSession):
    auth = AuthService(db)
    user = await auth.register("user1", "password123", "One", email="  Mixed.Case@Example.COM ")
    assert user.email == "mixed.case@example.com"
    with pytest.raises(ValueError, match="Email already registered"):
        await auth.register("user2", "password123", "Two", email="MIXED.CASE@example.com")


async def test_register_rejects_an_unknown_role(db: AsyncSession):
    with pytest.raises(ValueError, match="Unknown role"):
        await AuthService(db).register("someone", "password123", "Some One", role="wizard")


async def test_password_is_never_stored_in_clear(db: AsyncSession):
    user = await AuthService(db).register("secure", "password123", "Secure")
    assert user.password_hash != "password123"
    assert user.password_hash.startswith("$argon2")


# --- login ---

async def test_login_by_username_or_email(db: AsyncSession):
    auth = AuthService(db)
    await auth.register("loginuser", "password123", "Login", email="login@example.com")

    _, _, by_username = await auth.login("loginuser", "password123")
    _, _, by_email = await auth.login("login@example.com", "password123")
    assert by_username.user_id == by_email.user_id


async def test_login_trims_whitespace_around_the_identifier(db: AsyncSession):
    auth = AuthService(db)
    await auth.register("trimmed", "password123", "Trim")
    access, _, _ = await auth.login("  trimmed  ", "password123")
    assert access


async def test_login_rejects_unknown_user(db: AsyncSession):
    with pytest.raises(ValueError, match="Invalid username or password"):
        await AuthService(db).login("ghost", "password123")


async def test_login_rejects_inactive_account(db: AsyncSession):
    auth = AuthService(db)
    user = await auth.register("dormant", "password123", "Dormant")
    await auth.update_user(user.user_id, is_active=False)
    with pytest.raises(ValueError, match="Account is inactive"):
        await auth.login("dormant", "password123")


async def test_login_records_last_login(db: AsyncSession):
    auth = AuthService(db)
    user = await auth.register("stamped", "password123", "Stamped")
    assert user.last_login_at is None
    _, _, logged_in = await auth.login("stamped", "password123")
    assert logged_in.last_login_at is not None


async def test_login_upgrades_a_legacy_hash_in_place(db: AsyncSession):
    from argon2 import PasswordHasher

    auth = AuthService(db)
    user = await auth.register("legacy", "password123", "Legacy")
    user.password_hash = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4).hash("password123")
    await db.flush()
    stale = user.password_hash

    _, _, logged_in = await auth.login("legacy", "password123")
    assert logged_in.password_hash != stale
    assert needs_rehash(logged_in.password_hash) is False


# --- refresh ---

async def test_refresh_issues_a_new_pair(db: AsyncSession):
    auth = AuthService(db)
    await auth.register("refresher", "password123", "Refresh")
    _, refresh, _ = await auth.login("refresher", "password123")

    access2, refresh2 = await auth.refresh_token(refresh)
    assert decode_token(access2)["type"] == "access"
    assert decode_token(refresh2)["type"] == "refresh"


async def test_refresh_rejects_an_access_token(db: AsyncSession):
    auth = AuthService(db)
    await auth.register("mixup", "password123", "Mix Up")
    access, _, _ = await auth.login("mixup", "password123")
    with pytest.raises(ValueError, match="Invalid refresh token"):
        await auth.refresh_token(access)


async def test_refresh_rejects_garbage(db: AsyncSession):
    with pytest.raises(ValueError, match="Invalid refresh token"):
        await AuthService(db).refresh_token("not.a.token")


async def test_refresh_rejects_a_deactivated_user(db: AsyncSession):
    auth = AuthService(db)
    user = await auth.register("switchedoff", "password123", "Off")
    _, refresh, _ = await auth.login("switchedoff", "password123")
    await auth.update_user(user.user_id, is_active=False)
    with pytest.raises(ValueError, match="not found or inactive"):
        await auth.refresh_token(refresh)


# --- administration ---

async def test_change_password_takes_effect(db: AsyncSession):
    auth = AuthService(db)
    user = await auth.register("changer", "oldpassword", "Changer")
    await auth.change_password(user.user_id, "newpassword")

    with pytest.raises(ValueError, match="Invalid"):
        await auth.login("changer", "oldpassword")
    assert await auth.login("changer", "newpassword")


async def test_setting_a_password_converts_a_google_account_to_local(db: AsyncSession):
    auth = AuthService(db)
    user = await auth.register("googler", "password123", "Googler")
    user.auth_provider = AUTH_PROVIDER_GOOGLE
    user.password_hash = None
    await db.flush()

    await auth.change_password(user.user_id, "localpassword")
    assert user.auth_provider == AUTH_PROVIDER_LOCAL
    assert await auth.login("googler", "localpassword")


async def test_update_user_changes_role_and_permissions(db: AsyncSession):
    auth = AuthService(db)
    user = await auth.register("promoted", "password123", "Promoted")
    assert user.permissions == ["inventory", "reports"]

    updated = await auth.update_user(user.user_id, role="manager")
    assert updated.role == "manager"
    assert "purchase" in updated.permissions


async def test_update_unknown_user(db: AsyncSession):
    with pytest.raises(ValueError, match="User not found"):
        await AuthService(db).update_user(9999, full_name="Nobody")


async def test_change_password_for_unknown_user(db: AsyncSession):
    with pytest.raises(ValueError, match="User not found"):
        await AuthService(db).change_password(9999, "whatever")


async def test_list_users(db: AsyncSession):
    auth = AuthService(db)
    await auth.register("u1", "password123", "One")
    await auth.register("u2", "password123", "Two")
    users, total = await auth.list_users()
    assert total == 2
    assert [u.username for u in users] == ["u1", "u2"]


# --- bootstrap admin ---

async def test_default_admin_is_created_once(db: AsyncSession):
    await ensure_default_admin(db)
    admin = await db.scalar(select(User).where(User.username == "admin"))
    assert admin is not None
    assert admin.role == "admin"
    assert len(admin.permissions) == 10

    await ensure_default_admin(db)
    assert await db.scalar(select(func.count()).select_from(User)) == 1


async def test_default_admin_is_skipped_when_users_exist(db: AsyncSession):
    await AuthService(db).register("first", "password123", "First")
    await ensure_default_admin(db)
    assert await db.scalar(select(User).where(User.username == "admin")) is None


async def test_default_admin_can_sign_in(db: AsyncSession):
    await ensure_default_admin(db)
    access, refresh, user = await AuthService(db).login("admin", "admin123")
    assert access and refresh
    assert user.role == "admin"
