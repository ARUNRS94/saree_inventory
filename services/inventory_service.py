"""Business logic for stock ledger and valuation."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from database.models.entities import StockLedger
from database.repositories.inventory import InventoryRepository


class InventoryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = InventoryRepository(session)

    def assert_available(self, saree_id: int, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        available = self.repo.current_stock(saree_id)
        if available < quantity:
            raise ValueError(f"Insufficient stock. Available: {available}, requested: {quantity}.")

    def post_ledger(self, *, transaction_date: date, transaction_type: str, reference_no: str, saree_id: int,
                    qty_in: int = 0, qty_out: int = 0, rate: Decimal = Decimal("0"), remarks: str | None = None) -> StockLedger:
        if qty_in < 0 or qty_out < 0 or (qty_in == 0 and qty_out == 0):
            raise ValueError("Ledger entry must contain a positive QtyIn or QtyOut.")
        entry = StockLedger(
            transaction_date=transaction_date,
            transaction_type=transaction_type,
            reference_no=reference_no,
            saree_id=saree_id,
            qty_in=qty_in,
            qty_out=qty_out,
            rate=rate,
            remarks=remarks,
        )
        self.session.add(entry)
        return entry

    def inventory_value(self) -> Decimal:
        """Calculate stock value as SUM(current stock × latest purchase rate) for every saree."""
        return self.repo.total_inventory_value()
