from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.google_oauth import GoogleProfile, verify_google_id_token
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.role import DEFAULT_SIGNUP_ROLE, Role
from app.models.user import AUTH_PROVIDER_GOOGLE, AUTH_PROVIDER_LOCAL, User
from app.models.user_identity import UserIdentity
from app.services.rbac_service import RBACService

_USERNAME_SAFE = re.compile(r"[^a-z0-9._-]+")


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- helpers ---

    async def _role_id(self, role_name: str) -> int:
        role = await RBACService(self.session).get_role_by_name(role_name)
        if not role.is_active:
            raise ValueError(f"Role '{role_name}' is inactive.")
        return role.role_id

    async def _unique_username(self, base: str) -> str:
        candidate = _USERNAME_SAFE.sub("", base.lower()) or "user"
        suffix = 0
        while await self.session.scalar(select(User.user_id).where(User.username == candidate)):
            suffix += 1
            candidate = f"{candidate.rstrip('0123456789')}{suffix}"
        return candidate

    def _issue_tokens(self, user: User) -> tuple[str, str]:
        return (
            create_access_token({"sub": str(user.user_id)}),
            create_refresh_token({"sub": str(user.user_id)}),
        )

    # --- local auth ---

    async def register(
        self,
        username: str,
        password: str,
        full_name: str,
        role: str = DEFAULT_SIGNUP_ROLE,
        email: str | None = None,
    ) -> User:
        existing = await self.session.scalar(select(User).where(User.username == username))
        if existing:
            raise ValueError("Username already exists.")
        email = email.lower().strip() if email else None
        if email and await self.session.scalar(select(User).where(User.email == email)):
            raise ValueError("Email already registered.")
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role_id=await self._role_id(role),
            auth_provider=AUTH_PROVIDER_LOCAL,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def login(self, username: str, password: str) -> tuple[str, str, User]:
        identifier = username.strip()
        user = await self.session.scalar(
            select(User).where(or_(User.username == identifier, User.email == identifier.lower()))
        )
        if user is None or not verify_password(password, user.password_hash):
            raise ValueError("Invalid username or password.")
        if not user.is_active:
            raise ValueError("Account is inactive.")
        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.session.flush()
        access, refresh = self._issue_tokens(user)
        return access, refresh, user

    # --- Google auth ---

    async def login_with_google(self, credential: str) -> tuple[str, str, User]:
        profile = await verify_google_id_token(credential)
        user = await self._find_or_create_google_user(profile)
        if not user.is_active:
            raise ValueError("Account is inactive. Contact your administrator.")
        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.session.flush()
        access, refresh = self._issue_tokens(user)
        return access, refresh, user

    async def _find_or_create_google_user(self, profile: GoogleProfile) -> User:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        identity = await self.session.scalar(
            select(UserIdentity).where(
                UserIdentity.provider == AUTH_PROVIDER_GOOGLE,
                UserIdentity.provider_user_id == profile.subject,
            )
        )
        if identity is not None:
            identity.last_login_at = now
            user = await self.session.get(User, identity.user_id)
            if user is None:
                raise ValueError("Linked account no longer exists.")
            return user

        # Link the Google identity to an existing account with the same email.
        user = await self.session.scalar(select(User).where(User.email == profile.email))
        if user is None:
            if not settings.GOOGLE_ALLOW_SIGNUP:
                raise ValueError("No account found for this Google address. Ask an administrator to invite you.")
            user = User(
                username=await self._unique_username(profile.email.split("@")[0]),
                email=profile.email,
                password_hash=None,
                full_name=profile.full_name,
                role_id=await self._role_id(settings.GOOGLE_SIGNUP_ROLE or DEFAULT_SIGNUP_ROLE),
                auth_provider=AUTH_PROVIDER_GOOGLE,
                avatar_url=profile.picture,
            )
            self.session.add(user)
            await self.session.flush()
        elif not user.avatar_url:
            user.avatar_url = profile.picture

        self.session.add(
            UserIdentity(
                user_id=user.user_id,
                provider=AUTH_PROVIDER_GOOGLE,
                provider_user_id=profile.subject,
                email=profile.email,
                last_login_at=now,
            )
        )
        await self.session.flush()
        await self.session.refresh(user)
        return user

    # --- tokens ---

    async def refresh_token(self, refresh_token: str) -> tuple[str, str]:
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token.")
        user_id = payload.get("sub")
        user = await self.session.get(User, int(user_id))
        if user is None or not user.is_active:
            raise ValueError("User not found or inactive.")
        return self._issue_tokens(user)

    # --- user administration ---

    async def list_users(self) -> tuple[list[User], int]:
        total = await self.session.scalar(select(func.count()).select_from(User)) or 0
        result = await self.session.execute(select(User).order_by(User.user_id))
        return list(result.scalars().all()), total

    async def update_user(self, user_id: int, **values: object) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise ValueError("User not found.")
        role_name = values.pop("role", None)
        if role_name is not None:
            user.role_id = await self._role_id(str(role_name))
        for key, val in values.items():
            if val is not None:
                setattr(user, key, val)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def change_password(self, user_id: int, new_password: str) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise ValueError("User not found.")
        user.password_hash = hash_password(new_password)
        if user.auth_provider == AUTH_PROVIDER_GOOGLE:
            user.auth_provider = AUTH_PROVIDER_LOCAL
        await self.session.flush()
        return user


async def ensure_default_admin(session: AsyncSession) -> None:
    """Create the bootstrap administrator when no users exist yet."""
    count = await session.scalar(select(func.count()).select_from(User)) or 0
    if count:
        return
    admin_role = await session.scalar(select(Role).where(Role.role_name == "admin"))
    session.add(
        User(
            username="admin",
            email="admin@example.com",
            password_hash=hash_password("admin123"),
            full_name="Administrator",
            role_id=admin_role.role_id if admin_role else None,
            auth_provider=AUTH_PROVIDER_LOCAL,
        )
    )
    await session.flush()
