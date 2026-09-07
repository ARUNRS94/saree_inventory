"""rbac tables and google sign-in

Revision ID: 002
Revises: 001
Create Date: 2026-09-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSIONS = [
    ("users", "User Management", "Create, edit and deactivate users"),
    ("roles", "Access Management", "Create roles and assign permissions"),
    ("masters", "Masters", "Manage sarees, suppliers and vendors"),
    ("purchase", "Purchase", "Manage purchase orders"),
    ("grn", "GRN", "Manage goods receipt notes"),
    ("jobwork", "Job Work", "Manage job work issues and receipts"),
    ("inventory", "Inventory", "View and adjust stock"),
    ("reports", "Reports", "View and export reports"),
    ("settings", "Settings", "Manage company settings"),
]

ROLES = {
    "admin": ("Full access to every module", [c for c, _, _ in PERMISSIONS]),
    "manager": ("Operations plus masters and reports", ["masters", "purchase", "grn", "jobwork", "inventory", "reports"]),
    "operator": ("Day-to-day transaction entry", ["purchase", "grn", "jobwork", "inventory"]),
    "viewer": ("Read-only access to stock and reports", ["inventory", "reports"]),
}


def upgrade() -> None:
    roles = op.create_table(
        "roles",
        sa.Column("role_id", sa.Integer(), primary_key=True),
        sa.Column("role_name", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("description", sa.Text()),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_date", sa.DateTime(), server_default=sa.func.now()),
    )

    permissions = op.create_table(
        "permissions",
        sa.Column("permission_id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_date", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_permission_id", sa.Integer(), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.role_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.permission_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    op.create_table(
        "user_identities",
        sa.Column("identity_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.String(30), nullable=False, index=True),
        sa.Column("provider_user_id", sa.String(255), nullable=False, index=True),
        sa.Column("email", sa.String(255)),
        sa.Column("created_date", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime()),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_provider_identity"),
    )

    op.bulk_insert(roles, [
        {"role_name": name, "description": desc, "is_system": True, "is_active": True}
        for name, (desc, _) in ROLES.items()
    ])
    op.bulk_insert(permissions, [
        {"code": code, "name": name, "description": desc} for code, name, desc in PERMISSIONS
    ])

    conn = op.get_bind()
    role_ids = dict(conn.execute(sa.text("SELECT role_name, role_id FROM roles")).all())
    permission_ids = dict(conn.execute(sa.text("SELECT code, permission_id FROM permissions")).all())
    conn.execute(
        sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :permission_id)"),
        [
            {"role_id": role_ids[role_name], "permission_id": permission_ids[code]}
            for role_name, (_, codes) in ROLES.items()
            for code in codes
        ],
    )

    had_role_column = "role" in {c["name"] for c in sa.inspect(conn).get_columns("users")}

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("email", sa.String(255)))
        batch.add_column(sa.Column("role_id", sa.Integer()))
        batch.add_column(sa.Column("auth_provider", sa.String(20), nullable=False, server_default="local"))
        batch.add_column(sa.Column("avatar_url", sa.String(500)))
        batch.add_column(sa.Column("last_login_at", sa.DateTime()))
        batch.alter_column("password_hash", existing_type=sa.String(255), nullable=True)
        batch.create_index("ix_users_email", ["email"], unique=True)
        batch.create_index("ix_users_role_id", ["role_id"])
        batch.create_foreign_key("fk_users_role_id", "roles", ["role_id"], ["role_id"], ondelete="SET NULL")

    # Migrate the legacy users.role string column onto the new roles table.
    if had_role_column:
        conn.execute(sa.text(
            "UPDATE users SET role_id = (SELECT role_id FROM roles WHERE roles.role_name = users.role)"
        ))
        with op.batch_alter_table("users") as batch:
            batch.drop_column("role")
    else:
        conn.execute(sa.text("UPDATE users SET role_id = :rid"), {"rid": role_ids["admin"]})


def downgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("role", sa.String(30), server_default="viewer"))
    conn.execute(sa.text(
        "UPDATE users SET role = COALESCE((SELECT role_name FROM roles WHERE roles.role_id = users.role_id), 'viewer')"
    ))
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_role_id", type_="foreignkey")
        batch.drop_index("ix_users_role_id")
        batch.drop_index("ix_users_email")
        for column in ("last_login_at", "avatar_url", "auth_provider", "role_id", "email"):
            batch.drop_column(column)
    op.drop_table("user_identities")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
