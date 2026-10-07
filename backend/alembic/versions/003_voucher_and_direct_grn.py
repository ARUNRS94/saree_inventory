"""voucher number, direct raw material GRN and sub process category

Revision ID: 003
Revises: 002
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('items', sa.Column('category', sa.String(length=50), nullable=True))

    op.add_column('purchase_orders', sa.Column('voucher_number', sa.String(length=50), nullable=True))
    op.create_index('ix_purchase_orders_voucher_number', 'purchase_orders', ['voucher_number'])

    op.add_column('grns', sa.Column('grn_type', sa.String(length=10), nullable=False, server_default='SUB'))
    op.add_column('grns', sa.Column('contact_id', sa.Integer(), nullable=True))
    op.add_column('grns', sa.Column('vendor_voucher_number', sa.String(length=50), nullable=True))
    op.create_foreign_key('fk_grns_contact_id', 'grns', 'contacts', ['contact_id'], ['contact_id'])
    # Raw Material receipts are entered without a purchase order.
    op.alter_column('grns', 'po_id', existing_type=sa.Integer(), nullable=True)

    op.add_column('grn_items', sa.Column('short_qty', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('grn_items', sa.Column('po_number', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('grn_items', 'po_number')
    op.drop_column('grn_items', 'short_qty')

    op.alter_column('grns', 'po_id', existing_type=sa.Integer(), nullable=False)
    op.drop_constraint('fk_grns_contact_id', 'grns', type_='foreignkey')
    op.drop_column('grns', 'vendor_voucher_number')
    op.drop_column('grns', 'contact_id')
    op.drop_column('grns', 'grn_type')

    op.drop_index('ix_purchase_orders_voucher_number', table_name='purchase_orders')
    op.drop_column('purchase_orders', 'voucher_number')

    op.drop_column('items', 'category')
