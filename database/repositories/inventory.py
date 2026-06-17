"""Inventory-specific read repositories."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from database.models.entities import GRN, GRNItem, PurchaseOrder, PurchaseOrderItem, Saree, StockLedger


class InventoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def current_stock(self, saree_id: int | None = None) -> int:
        stmt: Select[tuple[int | None]] = select(func.coalesce(func.sum(StockLedger.qty_in - StockLedger.qty_out), 0))
        if saree_id is not None:
            stmt = stmt.where(StockLedger.saree_id == saree_id)
        return int(self.session.scalar(stmt) or 0)

    def latest_purchase_rate(self, saree_id: int) -> Decimal:
        """Return the newest PO unit rate for stock valuation.

        GRN/ledger rates can be mistyped as a line total or processing charge. For
        dashboard valuation, purchase order items are the source of truth because
        PO lines store a validated unit rate and amount separately.
        """
        po_rate_stmt = (
            select(PurchaseOrderItem.rate)
            .join(GRN, GRN.po_id == PurchaseOrderItem.po_id)
            .join(GRNItem, and_(GRNItem.grn_id == GRN.grn_id, GRNItem.saree_id == PurchaseOrderItem.saree_id))
            .where(PurchaseOrderItem.saree_id == saree_id)
            .order_by(GRN.grn_date.desc(), GRNItem.grn_item_id.desc(), PurchaseOrderItem.po_item_id.desc())
            .limit(1)
        )
        po_rate = self.session.scalar(po_rate_stmt)
        if po_rate is not None:
            return Decimal(po_rate)

        grn_stmt = (
            select(GRNItem.rate)
            .join(GRN)
            .where(GRNItem.saree_id == saree_id)
            .order_by(GRN.grn_date.desc(), GRNItem.grn_item_id.desc())
            .limit(1)
        )
        grn_rate = self.session.scalar(grn_stmt)
        if grn_rate is not None:
            return Decimal(grn_rate)

        ledger_stmt = (
            select(StockLedger.rate)
            .where(StockLedger.saree_id == saree_id, StockLedger.transaction_type == "PURCHASE")
            .order_by(StockLedger.transaction_date.desc(), StockLedger.ledger_id.desc())
            .limit(1)
        )
        return Decimal(self.session.scalar(ledger_stmt) or 0)

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
