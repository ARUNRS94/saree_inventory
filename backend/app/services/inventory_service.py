from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grn import GRN, GRNItem
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.contact import Contact
from app.models.item import Item
from app.models.stock_ledger import StockLedger

# Reports are rendered in one pass inside a serverless function, so the row count is bounded.
MOVEMENT_REPORT_LIMIT = 5_000


class InventoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def current_stock(self, item_id: int | None = None) -> int:
        await self.session.flush()
        stmt = select(func.coalesce(func.sum(StockLedger.qty_in - StockLedger.qty_out), 0))
        if item_id is not None:
            stmt = stmt.where(StockLedger.item_id == item_id)
        return int(await self.session.scalar(stmt) or 0)

    async def assert_available(self, item_id: int, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        available = await self.current_stock(item_id)
        if available < quantity:
            raise ValueError(f"Insufficient stock. Available: {available}, requested: {quantity}.")

    async def post_ledger(self, *, transaction_date: date, transaction_type: str, reference_no: str,
                          item_id: int, qty_in: int = 0, qty_out: int = 0,
                          rate: Decimal = Decimal("0"), remarks: str | None = None) -> StockLedger:
        if qty_in < 0 or qty_out < 0 or (qty_in == 0 and qty_out == 0):
            raise ValueError("Ledger entry must contain a positive QtyIn or QtyOut.")
        entry = StockLedger(
            transaction_date=transaction_date,
            transaction_type=transaction_type,
            reference_no=reference_no,
            item_id=item_id,
            qty_in=qty_in,
            qty_out=qty_out,
            rate=rate,
            remarks=remarks,
        )
        self.session.add(entry)
        return entry

    async def latest_purchase_rate(self, item_id: int) -> Decimal:
        po_rate_stmt = (
            select(PurchaseOrderItem.rate)
            .join(GRN, GRN.po_id == PurchaseOrderItem.po_id)
            .join(GRNItem, (GRNItem.grn_id == GRN.grn_id) & (GRNItem.item_id == PurchaseOrderItem.item_id))
            .where(PurchaseOrderItem.item_id == item_id)
            .order_by(GRN.grn_date.desc(), GRNItem.grn_item_id.desc(), PurchaseOrderItem.po_item_id.desc())
            .limit(1)
        )
        po_rate = await self.session.scalar(po_rate_stmt)
        if po_rate is not None:
            return Decimal(po_rate)

        grn_stmt = (
            select(GRNItem.rate).join(GRN)
            .where(GRNItem.item_id == item_id)
            .order_by(GRN.grn_date.desc(), GRNItem.grn_item_id.desc())
            .limit(1)
        )
        grn_rate = await self.session.scalar(grn_stmt)
        if grn_rate is not None:
            return Decimal(grn_rate)

        ledger_stmt = (
            select(StockLedger.rate)
            .where(StockLedger.item_id == item_id, StockLedger.transaction_type == "PURCHASE")
            .order_by(StockLedger.transaction_date.desc(), StockLedger.ledger_id.desc())
            .limit(1)
        )
        return Decimal(await self.session.scalar(ledger_stmt) or 0)

    async def vendor_map(self) -> dict[int, list[str]]:
        """Vendors an item has come in from, taken off its GRNs and vouchers."""
        vendors: dict[int, set[str]] = {}

        def record(item_id: int | None, name: str | None) -> None:
            if item_id and name:
                vendors.setdefault(item_id, set()).add(name)

        grn_stmt = (
            select(GRNItem.item_id, Contact.contact_name)
            .join(GRN, GRN.grn_id == GRNItem.grn_id)
            .outerjoin(PurchaseOrder, PurchaseOrder.po_id == GRN.po_id)
            .join(Contact, Contact.contact_id == func.coalesce(GRN.contact_id, PurchaseOrder.contact_id))
            .distinct()
        )
        for item_id, name in await self.session.execute(grn_stmt):
            record(item_id, name)

        po_stmt = (
            select(PurchaseOrderItem.item_id, PurchaseOrderItem.target_fg_item_id, Contact.contact_name)
            .join(PurchaseOrder, PurchaseOrder.po_id == PurchaseOrderItem.po_id)
            .join(Contact, Contact.contact_id == PurchaseOrder.contact_id)
            .distinct()
        )
        for item_id, target_fg_id, name in await self.session.execute(po_stmt):
            record(item_id, name)
            record(target_fg_id, name)

        return {item_id: sorted(names) for item_id, names in vendors.items()}

    async def voucher_maps(self) -> tuple[dict[int, list[str]], dict[int, list[str]]]:
        """GSS voucher numbers and sub vendor voucher numbers an item has appeared on."""
        gss: dict[int, set[str]] = {}
        vendor_voucher: dict[int, set[str]] = {}

        def record(bucket: dict[int, set[str]], item_id: int | None, number: str | None) -> None:
            if item_id and number:
                bucket.setdefault(item_id, set()).add(number)

        grn_stmt = (
            select(GRNItem.item_id, PurchaseOrder.voucher_number, GRN.vendor_voucher_number)
            .join(GRN, GRN.grn_id == GRNItem.grn_id)
            .outerjoin(PurchaseOrder, PurchaseOrder.po_id == GRN.po_id)
            .distinct()
        )
        for item_id, voucher_number, vendor_number in await self.session.execute(grn_stmt):
            record(gss, item_id, voucher_number)
            record(vendor_voucher, item_id, vendor_number)

        po_stmt = (
            select(PurchaseOrderItem.item_id, PurchaseOrderItem.target_fg_item_id,
                   PurchaseOrderItem.stock_out_item_id, PurchaseOrder.voucher_number)
            .join(PurchaseOrder, PurchaseOrder.po_id == PurchaseOrderItem.po_id)
            .distinct()
        )
        for item_id, target_fg_id, stock_out_id, voucher_number in await self.session.execute(po_stmt):
            record(gss, item_id, voucher_number)
            record(gss, target_fg_id, voucher_number)
            record(gss, stock_out_id, voucher_number)

        return (
            {item_id: sorted(values) for item_id, values in gss.items()},
            {item_id: sorted(values) for item_id, values in vendor_voucher.items()},
        )

    async def voucher_options(self) -> dict[str, list[str]]:
        """Distinct voucher numbers, for the report and GRN filter dropdowns."""
        gss = await self.session.scalars(
            select(PurchaseOrder.voucher_number)
            .where(PurchaseOrder.voucher_number.is_not(None))
            .distinct().order_by(PurchaseOrder.voucher_number)
        )
        vendor_vouchers = await self.session.scalars(
            select(GRN.vendor_voucher_number)
            .where(GRN.vendor_voucher_number.is_not(None))
            .distinct().order_by(GRN.vendor_voucher_number)
        )
        return {"voucher_numbers": list(gss), "vendor_voucher_numbers": list(vendor_vouchers)}

    @staticmethod
    def _matches_voucher(values: list[str], needle: str | None) -> bool:
        return not needle or any(needle.lower() in value.lower() for value in values)

    async def stock_report(self, search: str = "", item_type: str | None = None,
                           vendor: str | None = None, hide_zero: bool = False,
                           voucher_number: str | None = None,
                           vendor_voucher_number: str | None = None) -> list[dict]:
        balance = func.coalesce(func.sum(StockLedger.qty_in - StockLedger.qty_out), 0).label("current_stock")
        stmt = (
            select(Item.item_id, Item.item_code, Item.item_name, Item.item_type, Item.category, balance)
            .outerjoin(StockLedger)
            .group_by(Item.item_id)
            .order_by(Item.item_name)
        )
        if item_type:
            stmt = stmt.where(Item.item_type == item_type)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(Item.item_name.ilike(like) | Item.item_code.ilike(like) | Item.category.ilike(like))
        result = await self.session.execute(stmt)
        vendors = await self.vendor_map()
        gss_vouchers, vendor_vouchers = await self.voucher_maps()
        rows = [
            {
                "item_id": sid, "item_code": code, "item_name": name,
                "item_type": item_type_code or "FG", "category": category,
                "vendors": vendors.get(sid, []), "current_stock": int(stock or 0),
                "voucher_numbers": gss_vouchers.get(sid, []),
                "vendor_voucher_numbers": vendor_vouchers.get(sid, []),
            }
            for sid, code, name, item_type_code, category, stock in result
        ]
        if vendor:
            needle = vendor.lower()
            rows = [r for r in rows if any(needle in v.lower() for v in r["vendors"])]
        if voucher_number:
            rows = [r for r in rows if self._matches_voucher(r["voucher_numbers"], voucher_number)]
        if vendor_voucher_number:
            rows = [r for r in rows if self._matches_voucher(r["vendor_voucher_numbers"], vendor_voucher_number)]
        if hide_zero:
            rows = [r for r in rows if r["current_stock"] != 0]
        return rows

    async def _stock_map(self) -> dict[int, int]:
        stmt = (
            select(StockLedger.item_id, func.coalesce(func.sum(StockLedger.qty_in - StockLedger.qty_out), 0))
            .group_by(StockLedger.item_id)
        )
        result = await self.session.execute(stmt)
        return {item_id: int(qty or 0) for item_id, qty in result}

    async def _latest_rate_map(self) -> dict[int, Decimal]:
        """Latest rate per item, mirroring latest_purchase_rate's precedence in three set-based queries."""
        ledger_sub = (
            select(
                StockLedger.item_id.label("item_id"),
                StockLedger.rate.label("rate"),
                func.row_number().over(
                    partition_by=StockLedger.item_id,
                    order_by=(StockLedger.transaction_date.desc(), StockLedger.ledger_id.desc()),
                ).label("rn"),
            )
            .where(StockLedger.transaction_type == "PURCHASE")
            .subquery()
        )
        grn_sub = (
            select(
                GRNItem.item_id.label("item_id"),
                GRNItem.rate.label("rate"),
                func.row_number().over(
                    partition_by=GRNItem.item_id,
                    order_by=(GRN.grn_date.desc(), GRNItem.grn_item_id.desc()),
                ).label("rn"),
            )
            .join(GRN, GRN.grn_id == GRNItem.grn_id)
            .subquery()
        )
        po_sub = (
            select(
                PurchaseOrderItem.item_id.label("item_id"),
                PurchaseOrderItem.rate.label("rate"),
                func.row_number().over(
                    partition_by=PurchaseOrderItem.item_id,
                    order_by=(
                        GRN.grn_date.desc(), GRNItem.grn_item_id.desc(), PurchaseOrderItem.po_item_id.desc(),
                    ),
                ).label("rn"),
            )
            .join(GRN, GRN.po_id == PurchaseOrderItem.po_id)
            .join(GRNItem, (GRNItem.grn_id == GRN.grn_id) & (GRNItem.item_id == PurchaseOrderItem.item_id))
            .subquery()
        )

        rates: dict[int, Decimal] = {}
        # Weakest source first so stronger ones overwrite it.
        for sub in (ledger_sub, grn_sub, po_sub):
            result = await self.session.execute(select(sub.c.item_id, sub.c.rate).where(sub.c.rn == 1))
            for item_id, rate in result:
                if rate is not None:
                    rates[item_id] = Decimal(rate)
        return rates

    async def inventory_valuation(self, search: str = "", item_type: str | None = None,
                                  vendor: str | None = None, hide_zero: bool = False,
                                  voucher_number: str | None = None,
                                  vendor_voucher_number: str | None = None) -> list[dict]:
        await self.session.flush()
        stock_by_id = await self._stock_map()
        rate_by_id = await self._latest_rate_map()
        vendors = await self.vendor_map()
        gss_vouchers, vendor_vouchers = await self.voucher_maps()
        stmt = select(Item).order_by(Item.item_name)
        if item_type:
            stmt = stmt.where(Item.item_type == item_type)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(Item.item_name.ilike(like) | Item.item_code.ilike(like) | Item.category.ilike(like))
        items = (await self.session.execute(stmt)).scalars().all()
        rows = []
        for item in items:
            stock = stock_by_id.get(item.item_id, 0)
            rate = rate_by_id.get(item.item_id, Decimal("0"))
            item_vendors = vendors.get(item.item_id, [])
            item_gss = gss_vouchers.get(item.item_id, [])
            item_vendor_vouchers = vendor_vouchers.get(item.item_id, [])
            if vendor and not any(vendor.lower() in v.lower() for v in item_vendors):
                continue
            if not self._matches_voucher(item_gss, voucher_number):
                continue
            if not self._matches_voucher(item_vendor_vouchers, vendor_voucher_number):
                continue
            if hide_zero and stock == 0:
                continue
            rows.append({
                "item_id": item.item_id,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "item_type": item.item_type,
                "category": item.category,
                "vendors": item_vendors,
                "voucher_numbers": item_gss,
                "vendor_voucher_numbers": item_vendor_vouchers,
                "current_stock": stock,
                "latest_rate": rate,
                "value": Decimal(stock) * rate,
            })
        return rows

    def ledger_filters(self, search: str = "", transaction_type: str | None = None,
                       date_from: date | None = None, date_to: date | None = None) -> list:
        filters = []
        if transaction_type:
            filters.append(StockLedger.transaction_type == transaction_type)
        if date_from:
            filters.append(StockLedger.transaction_date >= date_from)
        if date_to:
            filters.append(StockLedger.transaction_date <= date_to)
        if search:
            like = f"%{search}%"
            filters.append(
                StockLedger.reference_no.ilike(like) | Item.item_code.ilike(like) | Item.item_name.ilike(like)
            )
        return filters

    async def movement_report(self, search: str = "", transaction_type: str | None = None,
                              date_from: date | None = None, date_to: date | None = None,
                              limit: int = MOVEMENT_REPORT_LIMIT) -> list[dict]:
        stmt = (
            select(StockLedger, Item.item_name, Item.item_type)
            .join(Item, Item.item_id == StockLedger.item_id)
        )
        for condition in self.ledger_filters(search, transaction_type, date_from, date_to):
            stmt = stmt.where(condition)
        stmt = stmt.order_by(StockLedger.transaction_date.desc(), StockLedger.ledger_id.desc())
        stmt = stmt.limit(min(limit, MOVEMENT_REPORT_LIMIT))
        result = await self.session.execute(stmt)
        return [
            {
                "transaction_date": entry.transaction_date,
                "transaction_type": entry.transaction_type,
                "reference_no": entry.reference_no,
                "item_name": name,
                "item_type": item_type,
                "qty_in": entry.qty_in,
                "qty_out": entry.qty_out,
                "rate": entry.rate,
                "remarks": entry.remarks or "",
            }
            for entry, name, item_type in result
        ]

    async def total_inventory_value(self) -> Decimal:
        await self.session.flush()
        stock_by_id = await self._stock_map()
        rate_by_id = await self._latest_rate_map()
        return sum(
            (Decimal(qty) * rate_by_id.get(item_id, Decimal("0")) for item_id, qty in stock_by_id.items()),
            Decimal("0"),
        )
