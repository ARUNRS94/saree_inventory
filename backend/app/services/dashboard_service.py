from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grn import GRN, GRN_TYPE_RAW_MATERIAL, GRNItem
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.item import Item
from app.models.stock_ledger import StockLedger
from app.models.contact import Contact
from app.models.vendor import Vendor
from app.schemas.dashboard import (
    CategoryStockItem, DashboardCardData, DashboardResponse,
    PurchaseTrendItem, RecentGRNItem, StockMovementItem, VendorPendingItem,
)
from app.services.inventory_service import InventoryService
from app.services.master_service import SUB_PROCESS, SUB_VENDOR, item_type_label


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.inventory = InventoryService(session)

    async def get_dashboard(self) -> DashboardResponse:
        return DashboardResponse(
            cards=await self._get_cards(),
            purchase_trend=await self._purchase_trend(),
            stock_movement=await self._stock_movement(),
            top_categories=await self._top_categories(),
            sub_process_split=await self._sub_process_split(),
            vendor_pending=await self._vendor_pending(),
            recent_grns=await self._recent_grns(),
        )

    async def _get_cards(self) -> DashboardCardData:
        total_stock = await self.inventory.current_stock()
        stock_value = await self.inventory.total_inventory_value()

        # One round trip for both open-PO aggregates.
        open_po_value, pending_po_qty = (await self.session.execute(
            select(
                func.coalesce(func.sum(PurchaseOrderItem.amount), 0),
                func.coalesce(func.sum(PurchaseOrderItem.ordered_qty), 0),
            )
            .join(PurchaseOrder)
            .where(PurchaseOrder.status.in_(["OPEN", "PARTIAL"]))
        )).one()

        # Quantity sitting with Sub Vendors: the ledger balance of Sub Process items,
        # posted as WIP_STOCK_IN on the PO and cleared by WIP_STOCK_OUT/CANCEL.
        vendor_wip = int(await self.session.scalar(
            select(func.coalesce(func.sum(StockLedger.qty_in - StockLedger.qty_out), 0))
            .join(Item, Item.item_id == StockLedger.item_id)
            .where(Item.item_type == SUB_PROCESS)
        ) or 0)

        # Three master-data counts in a single round trip.
        active_items, active_vendors, active_contacts = (await self.session.execute(
            select(
                select(func.count()).select_from(Item).scalar_subquery(),
                select(func.count()).select_from(Vendor).where(Vendor.is_active.is_(True)).scalar_subquery(),
                select(func.count()).select_from(Contact).where(Contact.is_active.is_(True)).scalar_subquery(),
            )
        )).one()

        # Quantity the vendor was answerable for but never added to stock.
        damaged_qty, short_qty = (await self.session.execute(
            select(
                func.coalesce(func.sum(GRNItem.damaged_qty), 0),
                func.coalesce(func.sum(GRNItem.short_qty), 0),
            )
        )).one()

        return DashboardCardData(
            total_stock_qty=total_stock, stock_value=stock_value,
            open_po_value=Decimal(open_po_value or 0), pending_po_qty=int(pending_po_qty or 0),
            vendor_wip_qty=vendor_wip, damaged_qty=int(damaged_qty or 0), short_qty=int(short_qty or 0),
            active_items=int(active_items or 0),
            active_vendors=int(active_vendors or 0), active_contacts=int(active_contacts or 0),
        )

    async def _purchase_trend(self) -> list[PurchaseTrendItem]:
        stmt = (
            select(
                extract("year", PurchaseOrder.po_date).label("yr"),
                extract("month", PurchaseOrder.po_date).label("mn"),
                func.coalesce(func.sum(PurchaseOrderItem.amount), 0),
            )
            .join(PurchaseOrderItem)
            .where(PurchaseOrder.status != "CANCELLED")
            .group_by("yr", "mn")
            .order_by("yr", "mn")
            .limit(12)
        )
        result = await self.session.execute(stmt)
        return [PurchaseTrendItem(month=f"{int(yr)}-{int(mn):02d}", value=Decimal(val)) for yr, mn, val in result]

    async def _stock_movement(self) -> list[StockMovementItem]:
        stmt = (
            select(
                extract("year", StockLedger.transaction_date).label("yr"),
                extract("month", StockLedger.transaction_date).label("mn"),
                func.coalesce(func.sum(StockLedger.qty_in), 0),
                func.coalesce(func.sum(StockLedger.qty_out), 0),
            )
            .group_by("yr", "mn")
            .order_by("yr", "mn")
            .limit(12)
        )
        result = await self.session.execute(stmt)
        return [StockMovementItem(month=f"{int(yr)}-{int(mn):02d}", qty_in=int(qi), qty_out=int(qo)) for yr, mn, qi, qo in result]

    async def _top_categories(self) -> list[CategoryStockItem]:
        balance = func.coalesce(func.sum(StockLedger.qty_in - StockLedger.qty_out), 0)
        stmt = (
            select(func.coalesce(Item.item_type, "FG"), balance)
            .outerjoin(StockLedger)
            .group_by(Item.item_type)
            .order_by(balance.desc())
        )
        result = await self.session.execute(stmt)
        return [CategoryStockItem(category=item_type_label(cat) or "Finished Goods", qty=int(qty)) for cat, qty in result]

    async def _sub_process_split(self) -> list[CategoryStockItem]:
        """Work in progress split by the job the sub vendor is doing."""
        balance = func.coalesce(func.sum(StockLedger.qty_in - StockLedger.qty_out), 0)
        stmt = (
            select(func.coalesce(Item.category, "Uncategorised"), balance)
            .outerjoin(StockLedger)
            .where(Item.item_type == SUB_PROCESS)
            .group_by(Item.category)
            .order_by(balance.desc())
        )
        result = await self.session.execute(stmt)
        return [CategoryStockItem(category=cat, qty=int(qty)) for cat, qty in result if int(qty) != 0]

    async def _vendor_pending(self, limit: int = 8) -> list[VendorPendingItem]:
        """How much each sub vendor still owes across their open vouchers."""
        received = (
            select(
                GRN.po_id.label("po_id"),
                func.coalesce(func.sum(GRNItem.received_qty + GRNItem.damaged_qty + GRNItem.short_qty), 0).label("done"),
            )
            .join(GRNItem, GRNItem.grn_id == GRN.grn_id)
            .where(GRN.po_id.is_not(None))
            .group_by(GRN.po_id)
            .subquery()
        )
        ordered = (
            select(
                PurchaseOrderItem.po_id.label("po_id"),
                func.coalesce(func.sum(PurchaseOrderItem.ordered_qty), 0).label("ordered"),
            )
            .group_by(PurchaseOrderItem.po_id)
            .subquery()
        )
        outstanding = ordered.c.ordered - func.coalesce(received.c.done, 0)
        # CASE rather than GREATEST so the same query runs on SQLite and Postgres.
        pending_qty = func.coalesce(func.sum(case((outstanding > 0, outstanding), else_=0)), 0).label("pending_qty")
        stmt = (
            select(
                Contact.contact_name,
                pending_qty,
                func.count(PurchaseOrder.po_id).label("open_vouchers"),
            )
            .select_from(PurchaseOrder)
            .join(Contact, Contact.contact_id == PurchaseOrder.contact_id)
            .join(ordered, ordered.c.po_id == PurchaseOrder.po_id)
            .outerjoin(received, received.c.po_id == PurchaseOrder.po_id)
            .where(PurchaseOrder.status.in_(["OPEN", "PARTIAL"]), Contact.contact_type == SUB_VENDOR)
            .group_by(Contact.contact_name)
            .order_by(pending_qty.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [
            VendorPendingItem(vendor_name=name, pending_qty=int(qty or 0), open_vouchers=int(count or 0))
            for name, qty, count in result if int(qty or 0) > 0
        ]

    async def _recent_grns(self, limit: int = 8) -> list[RecentGRNItem]:
        totals = (
            select(
                GRNItem.grn_id.label("grn_id"),
                func.coalesce(func.sum(GRNItem.received_qty), 0).label("received"),
                func.coalesce(func.sum(GRNItem.damaged_qty), 0).label("damaged"),
                func.coalesce(func.sum(GRNItem.short_qty), 0).label("short"),
            )
            .group_by(GRNItem.grn_id)
            .subquery()
        )
        stmt = (
            select(
                GRN.grn_number, GRN.grn_type, GRN.grn_date, Contact.contact_name,
                totals.c.received, totals.c.damaged, totals.c.short,
            )
            .select_from(GRN)
            .outerjoin(PurchaseOrder, PurchaseOrder.po_id == GRN.po_id)
            .outerjoin(Contact, Contact.contact_id == func.coalesce(GRN.contact_id, PurchaseOrder.contact_id))
            .outerjoin(totals, totals.c.grn_id == GRN.grn_id)
            .order_by(GRN.grn_date.desc(), GRN.grn_id.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [
            RecentGRNItem(
                grn_number=number, grn_type=grn_type or GRN_TYPE_RAW_MATERIAL, grn_date=grn_date,
                vendor_name=vendor, received_qty=int(received or 0),
                damaged_qty=int(damaged or 0), short_qty=int(short or 0),
            )
            for number, grn_type, grn_date, vendor, received, damaged, short in result
        ]
