"""bill number on voucher lines

Revision ID: 004
Revises: 003
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('purchase_order_items', sa.Column('bill_number', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('purchase_order_items', 'bill_number')
