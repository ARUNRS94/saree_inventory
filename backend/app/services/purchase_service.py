from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.grn import GRN, GRNItem
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.item import Item
from app.models.contact import Contact
from app.services.inventory_service import InventoryService
from app.services.master_service import CUSTOMER, RM_VENDOR, SUB_VENDOR
from app.services.numbering import next_number


@dataclass(frozen=True)
class PurchaseLine:
    item_id: int
    quantity: int
    rate: Decimal
    stock_out_item_id: int | None = None
    target_fg_item_id: int | None = None


class PurchaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.inventory = InventoryService(session)

    async def create_po(self, contact_id: int, lines: list[PurchaseLine], po_date: date | None = None,
                        expected_date: date | None = None, remarks: str | None = None) -> PurchaseOrder:
        if not lines:
            raise ValueError("Purchase order requires at least one item line.")
        contact = await self.session.get(Contact, contact_id)
        if contact is None:
            raise ValueError("Contact not found.")
        if contact.contact_type == CUSTOMER:
            raise ValueError("Purchase orders can be created only for Raw Material Vendors or Sub vendors.")
        document_date = po_date or date.today()
        po = PurchaseOrder(
            po_number=await next_number(self.session, PurchaseOrder, "po_number", "PO", document_date),
            contact_id=contact_id,
            po_date=document_date,
            expected_date=expected_date,
            remarks=remarks,
            status="OPEN",
        )
        for line in lines:
            if line.quantity <= 0 or line.rate < 0:
                raise ValueError("PO quantity must be positive and rate/process charges cannot be negative.")
            stock_in_item = await self.session.get(Item, line.item_id)
            if stock_in_item is None:
                raise ValueError("Stock-in item not found.")
            if contact.contact_type == RM_VENDOR and stock_in_item.item_type != "RM":
                raise ValueError("Raw Material Vendor purchase orders can stock in only Raw Material items.")
            if contact.contact_type == SUB_VENDOR:
                if stock_in_item.item_type != "Sub process":
                    raise ValueError("Sub vendor purchase orders can stock in only Sub Process items.")
                if line.stock_out_item_id is None:
                    raise ValueError("Select the Raw Material or Finished Goods stock-out item for Sub vendor process orders.")
                target_fg_item = await self.session.get(Item, line.target_fg_item_id) if line.target_fg_item_id else None
                if target_fg_item is None or target_fg_item.item_type != "FG":
                    raise ValueError("Select the target Finished Goods item for Sub vendor process orders.")
                stock_out_item = await self.session.get(Item, line.stock_out_item_id)
                if stock_out_item is None or stock_out_item.item_type not in {"RM", "FG"}:
                    raise ValueError("Sub vendor stock-out item must be a Raw Material or Finished Goods item.")
                await self.inventory.assert_available(line.stock_out_item_id, line.quantity)
                await self.inventory.post_ledger(
                    transaction_date=document_date, transaction_type="SUB_VENDOR_ISSUE",
                    reference_no=po.po_number, item_id=line.stock_out_item_id,
                    qty_out=line.quantity, rate=line.rate, remarks=remarks,
                )
                await self.inventory.post_ledger(
                    transaction_date=document_date, transaction_type="WIP_STOCK_IN",
                    reference_no=po.po_number, item_id=line.item_id,
                    qty_in=line.quantity, rate=line.rate, remarks=remarks,
                )
            po.items.append(PurchaseOrderItem(
                item_id=line.item_id,
                stock_out_item_id=line.stock_out_item_id,
                target_fg_item_id=line.target_fg_item_id,
                ordered_qty=line.quantity,
                rate=line.rate,
                amount=line.rate * line.quantity,
            ))
        self.session.add(po)
        await self.session.flush()
        return po

    async def receive_grn(self, po_id: int, lines: list[tuple[int, int, int, Decimal]],
                          grn_date: date | None = None, remarks: str | None = None) -> GRN:
        po = await self.session.get(PurchaseOrder, po_id, populate_existing=True, options=[selectinload(PurchaseOrder.contact), selectinload(PurchaseOrder.items)])
        if po is None:
            raise ValueError("Purchase order not found.")
        if not lines:
            raise ValueError("GRN requires at least one received line.")

        document_date = grn_date or date.today()
        grn = GRN(
            grn_number=await next_number(self.session, GRN, "grn_number", "GRN", document_date),
            po_id=po_id,
            grn_date=document_date,
            remarks=remarks,
        )
        transaction_type = "SUB_VENDOR_GRN" if po.contact.contact_type == SUB_VENDOR else "PURCHASE"
        for item_id, received_qty, damaged_qty, rate in lines:
            total_receipt_qty = received_qty + damaged_qty
            if received_qty < 0 or damaged_qty < 0 or total_receipt_qty <= 0:
                raise ValueError("Received or damaged quantity is required.")
            if po.contact.contact_type == SUB_VENDOR:
                fg_item = await self.session.get(Item, item_id)
                allowed_fg_ids = {item.target_fg_item_id for item in po.items if item.target_fg_item_id is not None}
                if fg_item is None or fg_item.item_type != "FG":
                    raise ValueError("Sub vendor GRN stock-in item must be a Finished Goods item.")
                if allowed_fg_ids and item_id not in allowed_fg_ids:
                    raise ValueError("GRN stock-in item must match the Finished Goods item selected on the Sub vendor PO.")
                pending = await self.pending_po_qty(po_id)
            else:
                stock_in_item = await self.session.get(Item, item_id)
                if stock_in_item is None or stock_in_item.item_type != "RM":
                    raise ValueError("Raw Material Vendor GRN stock-in item must be a Raw Material item.")
                pending = await self.pending_po_qty(po_id, item_id)
            if total_receipt_qty > pending:
                raise ValueError(f"Receipt quantity exceeds pending PO quantity. Pending: {pending}.")
            grn.items.append(GRNItem(item_id=item_id, received_qty=received_qty, damaged_qty=damaged_qty, rate=rate))
            if po.contact.contact_type == SUB_VENDOR:
                await self._consume_wip(po, total_receipt_qty, document_date, grn.grn_number, rate, remarks)
            if received_qty:
                await self.inventory.post_ledger(
                    transaction_date=document_date, transaction_type=transaction_type,
                    reference_no=grn.grn_number, item_id=item_id,
                    qty_in=received_qty, rate=rate, remarks=remarks,
                )
        self.session.add(grn)
        await self.session.flush()
        await self._update_po_status(po)
        return grn

    async def pending_po_qty(self, po_id: int, item_id: int | None = None) -> int:
        stmt = select(func.coalesce(func.sum(PurchaseOrderItem.ordered_qty), 0)).where(PurchaseOrderItem.po_id == po_id)
        if item_id is not None:
            stmt = stmt.where(PurchaseOrderItem.item_id == item_id)
        ordered = int(await self.session.scalar(stmt) or 0)
        if item_id is None:
            received = int(await self.session.scalar(
                select(func.coalesce(func.sum(GRNItem.received_qty + GRNItem.damaged_qty), 0))
                .join(GRN).where(GRN.po_id == po_id)
            ) or 0)
        else:
            received = int(await self.session.scalar(
                select(func.coalesce(func.sum(GRNItem.received_qty + GRNItem.damaged_qty), 0))
                .join(GRN).where(GRN.po_id == po_id, GRNItem.item_id == item_id)
            ) or 0)
        return max(ordered - received, 0)

    async def _consume_wip(self, po: PurchaseOrder, quantity: int, document_date, reference_no, rate, remarks):
        remaining = quantity
        for item in po.items:
            if remaining <= 0:
                break
            available = await self.inventory.current_stock(item.item_id)
            consume_qty = min(remaining, item.ordered_qty, available)
            if consume_qty > 0:
                await self.inventory.post_ledger(
                    transaction_date=document_date, transaction_type="WIP_STOCK_OUT",
                    reference_no=reference_no, item_id=item.item_id,
                    qty_out=consume_qty, rate=rate, remarks=remarks,
                )
                remaining -= consume_qty
        if remaining > 0:
            raise ValueError("Insufficient WIP stock to complete the Sub vendor GRN.")

    async def cancel_po(self, po_id: int, cancel_date: date | None = None, remarks: str | None = None) -> PurchaseOrder:
        po = await self.session.get(PurchaseOrder, po_id, populate_existing=True, options=[selectinload(PurchaseOrder.contact), selectinload(PurchaseOrder.items)])
        if po is None:
            raise ValueError("Purchase order not found.")
        if po.status == "CANCELLED":
            raise ValueError("Purchase order is already cancelled.")
        received = int(await self.session.scalar(
            select(func.coalesce(func.sum(GRNItem.received_qty + GRNItem.damaged_qty), 0))
            .join(GRN).where(GRN.po_id == po.po_id)
        ) or 0)
        if received > 0:
            raise ValueError("Cannot cancel a PO after GRN quantity has been received.")
        document_date = cancel_date or date.today()
        if po.contact.contact_type == SUB_VENDOR:
            for item in po.items:
                if item.stock_out_item_id is not None:
                    await self.inventory.post_ledger(
                        transaction_date=document_date, transaction_type="SUB_VENDOR_ISSUE_CANCEL",
                        reference_no=po.po_number, item_id=item.stock_out_item_id,
                        qty_in=item.ordered_qty, rate=item.rate, remarks=remarks or po.remarks,
                    )
                await self.inventory.assert_available(item.item_id, item.ordered_qty)
                await self.inventory.post_ledger(
                    transaction_date=document_date, transaction_type="WIP_STOCK_CANCEL",
                    reference_no=po.po_number, item_id=item.item_id,
                    qty_out=item.ordered_qty, rate=item.rate, remarks=remarks or po.remarks,
                )
        po.status = "CANCELLED"
        if remarks:
            po.remarks = remarks
        return po

    async def _update_po_status(self, po: PurchaseOrder) -> None:
        ordered = sum(item.ordered_qty for item in po.items)
        received = int(await self.session.scalar(
            select(func.coalesce(func.sum(GRNItem.received_qty + GRNItem.damaged_qty), 0))
            .join(GRN).where(GRN.po_id == po.po_id)
        ) or 0)
        if po.status != "CANCELLED":
            po.status = "CLOSED" if received >= ordered else "PARTIAL" if received > 0 else "OPEN"

    async def list_pos(self, status: str | None = None, contact_id: int | None = None,
                       search: str = "", date_from: date | None = None, date_to: date | None = None,
                       page: int = 1, page_size: int = 50) -> tuple[list[PurchaseOrder], int]:
        stmt = select(PurchaseOrder).options(
            selectinload(PurchaseOrder.contact),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.item),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.stock_out_item),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.target_fg_item),
        )
        count_stmt = select(func.count()).select_from(PurchaseOrder)
        if status:
            stmt = stmt.where(PurchaseOrder.status == status)
            count_stmt = count_stmt.where(PurchaseOrder.status == status)
        if contact_id:
            stmt = stmt.where(PurchaseOrder.contact_id == contact_id)
            count_stmt = count_stmt.where(PurchaseOrder.contact_id == contact_id)
        if search:
            like = f"%{search}%"
            stmt = stmt.join(Contact).where(PurchaseOrder.po_number.ilike(like) | Contact.contact_name.ilike(like))
            count_stmt = count_stmt.join(Contact).where(PurchaseOrder.po_number.ilike(like) | Contact.contact_name.ilike(like))
        if date_from:
            stmt = stmt.where(PurchaseOrder.po_date >= date_from)
            count_stmt = count_stmt.where(PurchaseOrder.po_date >= date_from)
        if date_to:
            stmt = stmt.where(PurchaseOrder.po_date <= date_to)
            count_stmt = count_stmt.where(PurchaseOrder.po_date <= date_to)
        total = await self.session.scalar(count_stmt) or 0
        stmt = stmt.order_by(PurchaseOrder.po_id.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all()), total

    async def list_grns(self, po_id: int | None = None, search: str = "",
                        date_from: date | None = None, date_to: date | None = None,
                        page: int = 1, page_size: int = 50) -> tuple[list[GRN], int]:
        stmt = select(GRN).options(
            selectinload(GRN.purchase_order),
            selectinload(GRN.items).selectinload(GRNItem.item),
        )
        count_stmt = select(func.count()).select_from(GRN)
        if po_id:
            stmt = stmt.where(GRN.po_id == po_id)
            count_stmt = count_stmt.where(GRN.po_id == po_id)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(GRN.grn_number.ilike(like))
            count_stmt = count_stmt.where(GRN.grn_number.ilike(like))
        if date_from:
            stmt = stmt.where(GRN.grn_date >= date_from)
            count_stmt = count_stmt.where(GRN.grn_date >= date_from)
        if date_to:
            stmt = stmt.where(GRN.grn_date <= date_to)
            count_stmt = count_stmt.where(GRN.grn_date <= date_to)
        total = await self.session.scalar(count_stmt) or 0
        stmt = stmt.order_by(GRN.grn_id.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all()), total
