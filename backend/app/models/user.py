from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.role import Role

AUTH_PROVIDER_LOCAL = "local"
AUTH_PROVIDER_GOOGLE = "google"


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    # Null for accounts that can only sign in through an external provider.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.role_id", ondelete="SET NULL"), index=True)
    auth_provider: Mapped[str] = mapped_column(
        String(20), default=AUTH_PROVIDER_LOCAL, server_default=AUTH_PROVIDER_LOCAL
    )
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    role_ref: Mapped[Role | None] = relationship(lazy="selectin")

    @property
    def role(self) -> str:
        return self.role_ref.role_name if self.role_ref else ""

    @property
    def permissions(self) -> list[str]:
        if self.role_ref is None or not self.role_ref.is_active:
            return []
        return sorted(self.role_ref.permission_codes)
