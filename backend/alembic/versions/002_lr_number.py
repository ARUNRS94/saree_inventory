"""add LR number to purchase order and GRN line items

Revision ID: 002
Revises: 001
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('purchase_order_items', sa.Column('lr_number', sa.String(length=50), nullable=True))
    op.add_column('grn_items', sa.Column('lr_number', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('grn_items', 'lr_number')
    op.drop_column('purchase_order_items', 'lr_number')
