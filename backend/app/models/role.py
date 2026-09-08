from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Catalogue of permission codes seeded into the `permissions` table.
PERMISSION_CATALOGUE: list[tuple[str, str, str]] = [
    ("users", "User Management", "Create, edit and deactivate users"),
    ("roles", "Access Management", "Create roles and assign permissions"),
    ("masters", "Masters", "Manage items, contacts and vendors"),
    ("imports", "Bulk Import", "Import master data from CSV files"),
    ("purchase", "Purchase", "Manage purchase orders"),
    ("grn", "GRN", "Manage goods receipt notes"),
    ("jobwork", "Job Work", "Manage job work issues and receipts"),
    ("inventory", "Inventory", "View and adjust stock"),
    ("reports", "Reports", "View and export reports"),
    ("settings", "Settings", "Manage company settings"),
]

# Default roles created on first boot, mapped to their permission codes.
DEFAULT_ROLES: dict[str, tuple[str, set[str]]] = {
    "admin": ("Full access to every module", {code for code, _, _ in PERMISSION_CATALOGUE}),
    "manager": ("Operations plus masters and reports", {"masters", "purchase", "grn", "jobwork", "inventory", "reports"}),
    "operator": ("Day-to-day transaction entry", {"purchase", "grn", "jobwork", "inventory"}),
    "viewer": ("Read-only access to stock and reports", {"inventory", "reports"}),
}

DEFAULT_SIGNUP_ROLE = "viewer"


class Permission(Base):
    __tablename__ = "permissions"

    permission_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    role_permission_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.role_id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.permission_id", ondelete="CASCADE"), nullable=False, index=True
    )


class Role(Base):
    __tablename__ = "roles"

    role_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    # System roles cannot be renamed or deleted.
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    permissions: Mapped[list[Permission]] = relationship(
        secondary=RolePermission.__table__, lazy="selectin", order_by=Permission.code
    )

    @property
    def permission_codes(self) -> set[str]:
        return {p.code for p in self.permissions}
