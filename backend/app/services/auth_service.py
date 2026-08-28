from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.user import ROLES, User


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register(self, username: str, password: str, full_name: str, role: str = "viewer") -> User:
        existing = await self.session.scalar(select(User).where(User.username == username))
        if existing:
            raise ValueError("Username already exists.")
        if role not in ROLES:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(ROLES)}")
        user = User(username=username, password_hash=hash_password(password), full_name=full_name, role=role)
        self.session.add(user)
        await self.session.flush()
        return user

    async def login(self, username: str, password: str) -> tuple[str, str, User]:
        user = await self.session.scalar(select(User).where(User.username == username))
        if user is None or not verify_password(password, user.password_hash):
            raise ValueError("Invalid username or password.")
        if not user.is_active:
            raise ValueError("Account is inactive.")
        access = create_access_token({"sub": str(user.user_id)})
        refresh = create_refresh_token({"sub": str(user.user_id)})
        return access, refresh, user

    async def refresh_token(self, refresh_token: str) -> tuple[str, str]:
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token.")
        user_id = payload.get("sub")
        user = await self.session.get(User, int(user_id))
        if user is None or not user.is_active:
            raise ValueError("User not found or inactive.")
        access = create_access_token({"sub": str(user.user_id)})
        new_refresh = create_refresh_token({"sub": str(user.user_id)})
        return access, new_refresh

    async def list_users(self) -> tuple[list[User], int]:
        total = await self.session.scalar(select(func.count()).select_from(User)) or 0
        result = await self.session.execute(select(User).order_by(User.user_id))
        return list(result.scalars().all()), total

    async def update_user(self, user_id: int, **values: object) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise ValueError("User not found.")
        if "role" in values and values["role"] is not None:
            if values["role"] not in ROLES:
                raise ValueError(f"Invalid role. Must be one of: {', '.join(ROLES)}")
        for key, val in values.items():
            if val is not None:
                setattr(user, key, val)
        await self.session.flush()
        return user

    async def change_password(self, user_id: int, new_password: str) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise ValueError("User not found.")
        user.password_hash = hash_password(new_password)
        await self.session.flush()
        return user
        access = create_access_token({"sub": str(user.user_id)})
        new_refresh = create_refresh_token({"sub": str(user.user_id)})
        return access, new_refresh
