"""stock ledger lookup indexes

Revision ID: 003
Revises: 002
Create Date: 2026-09-08
"""
from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_stock_ledger_saree_id", "stock_ledger", ["saree_id"])
    # Serves the "latest purchase rate per item" lookup.
    op.create_index(
        "ix_stock_ledger_saree_date", "stock_ledger", ["saree_id", "transaction_date", "ledger_id"]
    )
    op.create_index("ix_grn_items_saree_id", "grn_items", ["saree_id"])
    op.create_index("ix_purchase_order_items_saree_id", "purchase_order_items", ["saree_id"])


def downgrade() -> None:
    op.drop_index("ix_purchase_order_items_saree_id", table_name="purchase_order_items")
    op.drop_index("ix_grn_items_saree_id", table_name="grn_items")
    op.drop_index("ix_stock_ledger_saree_date", table_name="stock_ledger")
    op.drop_index("ix_stock_ledger_saree_id", table_name="stock_ledger")
