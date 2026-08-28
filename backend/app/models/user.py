from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


ROLES = ["admin", "manager", "operator", "viewer"]

ROLE_PERMISSIONS = {
    "admin": {"users", "masters", "purchase", "grn", "jobwork", "inventory", "reports", "settings"},
    "manager": {"masters", "purchase", "grn", "jobwork", "inventory", "reports"},
    "operator": {"purchase", "grn", "jobwork", "inventory"},
    "viewer": {"inventory", "reports"},
}


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="viewer", server_default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    @property
    def permissions(self) -> set[str]:
        return ROLE_PERMISSIONS.get(self.role, set())
