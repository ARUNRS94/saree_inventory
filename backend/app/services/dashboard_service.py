from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grn import GRN, GRNItem
from app.models.job_work import JobWorkIssue, JobWorkIssueItem, JobWorkReceipt, JobWorkReceiptItem
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.saree import Saree
from app.models.stock_ledger import StockLedger
from app.models.supplier import Supplier
from app.models.vendor import Vendor
from app.schemas.dashboard import (
    CategoryStockItem, DashboardCardData, DashboardResponse,
    PurchaseTrendItem, StockMovementItem,
)
from app.services.inventory_service import InventoryService


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

        # Vendor WIP: issued qty on open job work, minus what has come back.
        issued_qty = int(await self.session.scalar(
            select(func.coalesce(func.sum(JobWorkIssueItem.issued_qty), 0))
            .join(JobWorkIssue)
            .where(JobWorkIssue.status.in_(["OPEN", "PARTIAL"]))
        ) or 0)
        received_qty = int(await self.session.scalar(
            select(func.coalesce(func.sum(JobWorkReceiptItem.received_qty + JobWorkReceiptItem.rejected_qty), 0))
            .join(JobWorkReceipt)
            .join(JobWorkIssue, JobWorkIssue.issue_id == JobWorkReceipt.issue_id)
            .where(JobWorkIssue.status.in_(["OPEN", "PARTIAL"]))
        ) or 0)
        vendor_wip = max(issued_qty - received_qty, 0)

        # Three master-data counts in a single round trip.
        active_sarees, active_vendors, active_suppliers = (await self.session.execute(
            select(
                select(func.count()).select_from(Saree).scalar_subquery(),
                select(func.count()).select_from(Vendor).where(Vendor.is_active.is_(True)).scalar_subquery(),
                select(func.count()).select_from(Supplier).where(Supplier.is_active.is_(True)).scalar_subquery(),
            )
        )).one()

        return DashboardCardData(
            total_stock_qty=total_stock, stock_value=stock_value,
            open_po_value=Decimal(open_po_value or 0), pending_po_qty=int(pending_po_qty or 0),
            vendor_wip_qty=vendor_wip, active_sarees=int(active_sarees or 0),
            active_vendors=int(active_vendors or 0), active_suppliers=int(active_suppliers or 0),
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
            select(func.coalesce(Saree.fabric, "FG"), balance)
            .outerjoin(StockLedger)
            .group_by(Saree.fabric)
            .order_by(balance.desc())
        )
        result = await self.session.execute(stmt)
        return [CategoryStockItem(category=cat or "FG", qty=int(qty)) for cat, qty in result]
