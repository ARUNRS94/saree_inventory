"""bulk import permission

Revision ID: 004
Revises: 003
Create Date: 2026-09-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CODE = "imports"


def upgrade() -> None:
    conn = op.get_bind()
    # The app's own RBAC seeding may already have inserted this permission on boot.
    exists = conn.execute(sa.text("SELECT permission_id FROM permissions WHERE code = :c"), {"c": CODE}).first()
    if not exists:
        conn.execute(
            sa.text("INSERT INTO permissions (code, name, description) VALUES (:c, :n, :d)"),
            {"c": CODE, "n": "Bulk Import", "d": "Import master data from CSV files"},
        )
    # Granted to admin only; other roles opt in through Access Management.
    conn.execute(sa.text(
        "INSERT INTO role_permissions (role_id, permission_id) "
        "SELECT r.role_id, p.permission_id FROM roles r, permissions p "
        "WHERE r.role_name = 'admin' AND p.code = :c "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM role_permissions rp"
        "  WHERE rp.role_id = r.role_id AND rp.permission_id = p.permission_id"
        ")"
    ), {"c": CODE})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT permission_id FROM permissions WHERE code = :c)"
    ), {"c": CODE})
    conn.execute(sa.text("DELETE FROM permissions WHERE code = :c"), {"c": CODE})
