from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grn import GRN, GRNItem
from app.models.purchase_order import PurchaseOrderItem
from app.models.saree import Saree
from app.models.stock_ledger import StockLedger


class InventoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def current_stock(self, saree_id: int | None = None) -> int:
        await self.session.flush()
        stmt = select(func.coalesce(func.sum(StockLedger.qty_in - StockLedger.qty_out), 0))
        if saree_id is not None:
            stmt = stmt.where(StockLedger.saree_id == saree_id)
        return int(await self.session.scalar(stmt) or 0)

    async def assert_available(self, saree_id: int, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        available = await self.current_stock(saree_id)
        if available < quantity:
            raise ValueError(f"Insufficient stock. Available: {available}, requested: {quantity}.")

    async def post_ledger(self, *, transaction_date: date, transaction_type: str, reference_no: str,
                          saree_id: int, qty_in: int = 0, qty_out: int = 0,
                          rate: Decimal = Decimal("0"), remarks: str | None = None) -> StockLedger:
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

    async def latest_purchase_rate(self, saree_id: int) -> Decimal:
        po_rate_stmt = (
            select(PurchaseOrderItem.rate)
            .join(GRN, GRN.po_id == PurchaseOrderItem.po_id)
            .join(GRNItem, (GRNItem.grn_id == GRN.grn_id) & (GRNItem.saree_id == PurchaseOrderItem.saree_id))
            .where(PurchaseOrderItem.saree_id == saree_id)
            .order_by(GRN.grn_date.desc(), GRNItem.grn_item_id.desc(), PurchaseOrderItem.po_item_id.desc())
            .limit(1)
        )
        po_rate = await self.session.scalar(po_rate_stmt)
        if po_rate is not None:
            return Decimal(po_rate)

        grn_stmt = (
            select(GRNItem.rate).join(GRN)
            .where(GRNItem.saree_id == saree_id)
            .order_by(GRN.grn_date.desc(), GRNItem.grn_item_id.desc())
            .limit(1)
        )
        grn_rate = await self.session.scalar(grn_stmt)
        if grn_rate is not None:
            return Decimal(grn_rate)

        ledger_stmt = (
            select(StockLedger.rate)
            .where(StockLedger.saree_id == saree_id, StockLedger.transaction_type == "PURCHASE")
            .order_by(StockLedger.transaction_date.desc(), StockLedger.ledger_id.desc())
            .limit(1)
        )
        return Decimal(await self.session.scalar(ledger_stmt) or 0)

    async def stock_report(self) -> list[dict]:
        balance = func.coalesce(func.sum(StockLedger.qty_in - StockLedger.qty_out), 0).label("current_stock")
        stmt = (
            select(Saree.saree_id, Saree.saree_code, Saree.saree_name, Saree.fabric, balance)
            .outerjoin(StockLedger)
            .group_by(Saree.saree_id)
        )
        result = await self.session.execute(stmt)
        return [
            {"saree_id": sid, "saree_code": code, "saree_name": name, "fabric": fabric or "FG", "current_stock": int(stock or 0)}
            for sid, code, name, fabric, stock in result
        ]

    async def _stock_map(self) -> dict[int, int]:
        stmt = (
            select(StockLedger.saree_id, func.coalesce(func.sum(StockLedger.qty_in - StockLedger.qty_out), 0))
            .group_by(StockLedger.saree_id)
        )
        result = await self.session.execute(stmt)
        return {saree_id: int(qty or 0) for saree_id, qty in result}

    async def _latest_rate_map(self) -> dict[int, Decimal]:
        """Latest rate per item, mirroring latest_purchase_rate's precedence in three set-based queries."""
        ledger_sub = (
            select(
                StockLedger.saree_id.label("saree_id"),
                StockLedger.rate.label("rate"),
                func.row_number().over(
                    partition_by=StockLedger.saree_id,
                    order_by=(StockLedger.transaction_date.desc(), StockLedger.ledger_id.desc()),
                ).label("rn"),
            )
            .where(StockLedger.transaction_type == "PURCHASE")
            .subquery()
        )
        grn_sub = (
            select(
                GRNItem.saree_id.label("saree_id"),
                GRNItem.rate.label("rate"),
                func.row_number().over(
                    partition_by=GRNItem.saree_id,
                    order_by=(GRN.grn_date.desc(), GRNItem.grn_item_id.desc()),
                ).label("rn"),
            )
            .join(GRN, GRN.grn_id == GRNItem.grn_id)
            .subquery()
        )
        po_sub = (
            select(
                PurchaseOrderItem.saree_id.label("saree_id"),
                PurchaseOrderItem.rate.label("rate"),
                func.row_number().over(
                    partition_by=PurchaseOrderItem.saree_id,
                    order_by=(
                        GRN.grn_date.desc(), GRNItem.grn_item_id.desc(), PurchaseOrderItem.po_item_id.desc(),
                    ),
                ).label("rn"),
            )
            .join(GRN, GRN.po_id == PurchaseOrderItem.po_id)
            .join(GRNItem, (GRNItem.grn_id == GRN.grn_id) & (GRNItem.saree_id == PurchaseOrderItem.saree_id))
            .subquery()
        )

        rates: dict[int, Decimal] = {}
        # Weakest source first so stronger ones overwrite it.
        for sub in (ledger_sub, grn_sub, po_sub):
            result = await self.session.execute(select(sub.c.saree_id, sub.c.rate).where(sub.c.rn == 1))
            for saree_id, rate in result:
                if rate is not None:
                    rates[saree_id] = Decimal(rate)
        return rates

    async def inventory_valuation(self) -> list[dict]:
        await self.session.flush()
        stock_by_id = await self._stock_map()
        rate_by_id = await self._latest_rate_map()
        sarees = (await self.session.execute(select(Saree).order_by(Saree.saree_code))).scalars().all()
        rows = []
        for saree in sarees:
            stock = stock_by_id.get(saree.saree_id, 0)
            rate = rate_by_id.get(saree.saree_id, Decimal("0"))
            rows.append({
                "saree_id": saree.saree_id,
                "saree_code": saree.saree_code,
                "saree_name": saree.saree_name,
                "current_stock": stock,
                "latest_rate": rate,
                "value": Decimal(stock) * rate,
            })
        return rows

    async def total_inventory_value(self) -> Decimal:
        await self.session.flush()
        stock_by_id = await self._stock_map()
        rate_by_id = await self._latest_rate_map()
        return sum(
            (Decimal(qty) * rate_by_id.get(saree_id, Decimal("0")) for saree_id, qty in stock_by_id.items()),
            Decimal("0"),
        )
