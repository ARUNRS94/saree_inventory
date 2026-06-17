"""Inventory-specific read repositories."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from database.models.entities import GRN, GRNItem, PurchaseOrder, Saree, StockLedger


class InventoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def current_stock(self, saree_id: int | None = None) -> int:
        stmt: Select[tuple[int | None]] = select(func.coalesce(func.sum(StockLedger.qty_in - StockLedger.qty_out), 0))
        if saree_id is not None:
            stmt = stmt.where(StockLedger.saree_id == saree_id)
        return int(self.session.scalar(stmt) or 0)

    def latest_purchase_rate(self, saree_id: int) -> Decimal:
        """Return the newest purchase rate posted to stock, falling back to GRN item rate."""
        ledger_stmt = (
            select(StockLedger.rate)
            .where(StockLedger.saree_id == saree_id, StockLedger.transaction_type == "PURCHASE")
            .order_by(StockLedger.transaction_date.desc(), StockLedger.ledger_id.desc())
            .limit(1)
        )
        ledger_rate = self.session.scalar(ledger_stmt)
        if ledger_rate is not None:
            return Decimal(ledger_rate)
        grn_stmt = (
            select(GRNItem.rate)
            .join(GRN)
            .where(GRNItem.saree_id == saree_id)
            .order_by(GRN.grn_date.desc(), GRNItem.grn_item_id.desc())
            .limit(1)
        )
        return Decimal(self.session.scalar(grn_stmt) or 0)

    def inventory_valuation_rows(self) -> list[tuple[int, str, str, int, Decimal, Decimal]]:
        """Return saree-wise stock valuation based on current stock and latest purchase rate."""
        rows: list[tuple[int, str, str, int, Decimal, Decimal]] = []
        for saree in self.session.scalars(select(Saree).order_by(Saree.saree_code)):
            stock = self.current_stock(saree.saree_id)
            rate = self.latest_purchase_rate(saree.saree_id)
            rows.append((saree.saree_id, saree.saree_code, saree.saree_name, stock, rate, Decimal(stock) * rate))
        return rows

    def total_inventory_value(self) -> Decimal:
        """Return total inventory value from saree-wise valuation rows."""
        return sum((row[5] for row in self.inventory_valuation_rows()), Decimal("0"))

    def stock_report(self) -> list[tuple[str, str, int]]:
        balance = func.coalesce(func.sum(StockLedger.qty_in - StockLedger.qty_out), 0).label("current_stock")
        stmt = select(Saree.saree_code, Saree.saree_name, balance).outerjoin(StockLedger).group_by(Saree.saree_id)
        return [(code, name, int(stock or 0)) for code, name, stock in self.session.execute(stmt)]

    def pending_purchase_orders(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.status != "CLOSED")) or 0)
