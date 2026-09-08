from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grn import GRN, GRNItem
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.item import Item
from app.models.stock_ledger import StockLedger
from app.models.contact import Contact
from app.models.vendor import Vendor
from app.schemas.dashboard import (
    CategoryStockItem, DashboardCardData, DashboardResponse,
    PurchaseTrendItem, StockMovementItem,
)
from app.services.inventory_service import InventoryService
from app.services.master_service import SUB_PROCESS, item_type_label


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.inventory = InventoryService(session)

    async def get_dashboard(self) -> DashboardResponse:
        cards = await self._get_cards()
        purchase_trend = await self._purchase_trend()
        stock_movement = await self._stock_movement()
        top_categories = await self._top_categories()
        return DashboardResponse(
            cards=cards,
            purchase_trend=purchase_trend,
            stock_movement=stock_movement,
            top_categories=top_categories,
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

        return DashboardCardData(
            total_stock_qty=total_stock, stock_value=stock_value,
            open_po_value=Decimal(open_po_value or 0), pending_po_qty=int(pending_po_qty or 0),
            vendor_wip_qty=vendor_wip, active_items=int(active_items or 0),
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
