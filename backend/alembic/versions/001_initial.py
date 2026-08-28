"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_date", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "sarees",
        sa.Column("saree_id", sa.Integer(), primary_key=True),
        sa.Column("saree_code", sa.String(50), nullable=False, index=True),
        sa.Column("saree_name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(100)),
        sa.Column("fabric", sa.String(100), server_default="FG"),
        sa.Column("design_name", sa.String(150)),
        sa.Column("color", sa.String(80)),
        sa.Column("unit", sa.String(20), server_default="PCS"),
        sa.Column("created_date", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("saree_code", name="uq_saree_code"),
    )

    op.create_table(
        "suppliers",
        sa.Column("supplier_id", sa.Integer(), primary_key=True),
        sa.Column("supplier_name", sa.String(200), nullable=False, index=True),
        sa.Column("contact_person", sa.String(150)),
        sa.Column("phone", sa.String(30)),
        sa.Column("gst_no", sa.String(30)),
        sa.Column("address", sa.Text()),
        sa.Column("contact_type", sa.String(30), server_default="RM vendor", index=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_date", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "vendors",
        sa.Column("vendor_id", sa.Integer(), primary_key=True),
        sa.Column("vendor_name", sa.String(200), nullable=False, index=True),
        sa.Column("process_type", sa.String(100), nullable=False),
        sa.Column("contact_person", sa.String(150)),
        sa.Column("phone", sa.String(30)),
        sa.Column("gst_no", sa.String(30)),
        sa.Column("address", sa.Text()),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_date", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "vendor_process_types",
        sa.Column("process_type_id", sa.Integer(), primary_key=True),
        sa.Column("process_type", sa.String(100), nullable=False, index=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_date", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("process_type", name="uq_vendor_process_type"),
    )

    op.create_table(
        "purchase_orders",
        sa.Column("po_id", sa.Integer(), primary_key=True),
        sa.Column("po_number", sa.String(30), unique=True, nullable=False, index=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.supplier_id"), nullable=False),
        sa.Column("po_date", sa.Date(), nullable=False),
        sa.Column("expected_date", sa.Date()),
        sa.Column("status", sa.String(20), default="OPEN"),
        sa.Column("remarks", sa.Text()),
    )

    op.create_table(
        "purchase_order_items",
        sa.Column("po_item_id", sa.Integer(), primary_key=True),
        sa.Column("po_id", sa.Integer(), sa.ForeignKey("purchase_orders.po_id"), nullable=False),
        sa.Column("saree_id", sa.Integer(), sa.ForeignKey("sarees.saree_id"), nullable=False),
        sa.Column("stock_out_saree_id", sa.Integer(), sa.ForeignKey("sarees.saree_id")),
        sa.Column("target_fg_saree_id", sa.Integer(), sa.ForeignKey("sarees.saree_id")),
        sa.Column("ordered_qty", sa.Integer(), nullable=False),
        sa.Column("rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
    )

    op.create_table(
        "grns",
        sa.Column("grn_id", sa.Integer(), primary_key=True),
        sa.Column("grn_number", sa.String(30), unique=True, nullable=False, index=True),
        sa.Column("po_id", sa.Integer(), sa.ForeignKey("purchase_orders.po_id"), nullable=False),
        sa.Column("grn_date", sa.Date(), nullable=False),
        sa.Column("remarks", sa.Text()),
    )

    op.create_table(
        "grn_items",
        sa.Column("grn_item_id", sa.Integer(), primary_key=True),
        sa.Column("grn_id", sa.Integer(), sa.ForeignKey("grns.grn_id"), nullable=False),
        sa.Column("saree_id", sa.Integer(), sa.ForeignKey("sarees.saree_id"), nullable=False),
        sa.Column("received_qty", sa.Integer(), nullable=False),
        sa.Column("damaged_qty", sa.Integer(), default=0),
        sa.Column("rate", sa.Numeric(12, 2), nullable=False),
    )

    op.create_table(
        "job_work_issues",
        sa.Column("issue_id", sa.Integer(), primary_key=True),
        sa.Column("issue_no", sa.String(30), unique=True, nullable=False, index=True),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("vendors.vendor_id"), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), default="OPEN"),
        sa.Column("remarks", sa.Text()),
    )

    op.create_table(
        "job_work_issue_items",
        sa.Column("issue_item_id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("job_work_issues.issue_id"), nullable=False),
        sa.Column("saree_id", sa.Integer(), sa.ForeignKey("sarees.saree_id"), nullable=False),
        sa.Column("issued_qty", sa.Integer(), nullable=False),
    )

    op.create_table(
        "job_work_receipts",
        sa.Column("receipt_id", sa.Integer(), primary_key=True),
        sa.Column("receipt_no", sa.String(30), unique=True, nullable=False, index=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("job_work_issues.issue_id"), nullable=False),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("vendors.vendor_id"), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
    )

    op.create_table(
        "job_work_receipt_items",
        sa.Column("receipt_item_id", sa.Integer(), primary_key=True),
        sa.Column("receipt_id", sa.Integer(), sa.ForeignKey("job_work_receipts.receipt_id"), nullable=False),
        sa.Column("saree_id", sa.Integer(), sa.ForeignKey("sarees.saree_id"), nullable=False),
        sa.Column("received_qty", sa.Integer(), nullable=False),
        sa.Column("rejected_qty", sa.Integer(), default=0),
        sa.Column("process_cost", sa.Numeric(12, 2), default=0),
    )

    op.create_table(
        "stock_ledger",
        sa.Column("ledger_id", sa.Integer(), primary_key=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("transaction_type", sa.String(40), nullable=False, index=True),
        sa.Column("reference_no", sa.String(50), nullable=False, index=True),
        sa.Column("saree_id", sa.Integer(), sa.ForeignKey("sarees.saree_id"), nullable=False),
        sa.Column("qty_in", sa.Integer(), default=0),
        sa.Column("qty_out", sa.Integer(), default=0),
        sa.Column("rate", sa.Numeric(12, 2), default=0),
        sa.Column("remarks", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("stock_ledger")
    op.drop_table("job_work_receipt_items")
    op.drop_table("job_work_receipts")
    op.drop_table("job_work_issue_items")
    op.drop_table("job_work_issues")
    op.drop_table("grn_items")
    op.drop_table("grns")
    op.drop_table("purchase_order_items")
    op.drop_table("purchase_orders")
    op.drop_table("vendor_process_types")
    op.drop_table("vendors")
    op.drop_table("suppliers")
    op.drop_table("sarees")
    op.drop_table("users")
