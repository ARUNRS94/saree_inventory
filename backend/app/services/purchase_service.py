from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.grn import GRN, GRNItem
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.saree import Saree
from app.models.supplier import Supplier
from app.services.inventory_service import InventoryService
from app.services.numbering import next_number


@dataclass(frozen=True)
class PurchaseLine:
    saree_id: int
    quantity: int
    rate: Decimal
    stock_out_saree_id: int | None = None
    target_fg_saree_id: int | None = None


class PurchaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.inventory = InventoryService(session)

    async def create_po(self, supplier_id: int, lines: list[PurchaseLine], po_date: date | None = None,
                        expected_date: date | None = None, remarks: str | None = None) -> PurchaseOrder:
        if not lines:
            raise ValueError("Purchase order requires at least one item line.")
        contact = await self.session.get(Supplier, supplier_id)
        if contact is None:
            raise ValueError("Contact not found.")
        if contact.contact_type == "Customer":
            raise ValueError("Purchase orders can be created only for RM vendors or Sub vendors.")
        document_date = po_date or date.today()
        po = PurchaseOrder(
            po_number=await next_number(self.session, PurchaseOrder, "po_number", "PO", document_date),
            supplier_id=supplier_id,
            po_date=document_date,
            expected_date=expected_date,
            remarks=remarks,
            status="OPEN",
        )
        for line in lines:
            if line.quantity <= 0 or line.rate < 0:
                raise ValueError("PO quantity must be positive and rate/process charges cannot be negative.")
            stock_in_item = await self.session.get(Saree, line.saree_id)
            if stock_in_item is None:
                raise ValueError("Stock-in item not found.")
            if contact.contact_type == "RM vendor" and stock_in_item.fabric != "RM":
                raise ValueError("RM vendor purchase orders can stock in only RM items.")
            if contact.contact_type == "Sub vendor":
                if stock_in_item.fabric != "Sub process":
                    raise ValueError("Sub vendor purchase orders can stock in only Sub process items.")
                if line.stock_out_saree_id is None:
                    raise ValueError("Select the RM or FG stock-out item for Sub vendor process orders.")
                target_fg_item = await self.session.get(Saree, line.target_fg_saree_id) if line.target_fg_saree_id else None
                if target_fg_item is None or target_fg_item.fabric != "FG":
                    raise ValueError("Select the target FG item for Sub vendor process orders.")
                stock_out_item = await self.session.get(Saree, line.stock_out_saree_id)
                if stock_out_item is None or stock_out_item.fabric not in {"RM", "FG"}:
                    raise ValueError("Sub vendor stock-out item must be an RM or FG item.")
                await self.inventory.assert_available(line.stock_out_saree_id, line.quantity)
                await self.inventory.post_ledger(
                    transaction_date=document_date, transaction_type="SUB_VENDOR_ISSUE",
                    reference_no=po.po_number, saree_id=line.stock_out_saree_id,
                    qty_out=line.quantity, rate=line.rate, remarks=remarks,
                )
                await self.inventory.post_ledger(
                    transaction_date=document_date, transaction_type="WIP_STOCK_IN",
                    reference_no=po.po_number, saree_id=line.saree_id,
                    qty_in=line.quantity, rate=line.rate, remarks=remarks,
                )
            po.items.append(PurchaseOrderItem(
                saree_id=line.saree_id,
                stock_out_saree_id=line.stock_out_saree_id,
                target_fg_saree_id=line.target_fg_saree_id,
                ordered_qty=line.quantity,
                rate=line.rate,
                amount=line.rate * line.quantity,
            ))
        self.session.add(po)
        await self.session.flush()
        return po

    async def receive_grn(self, po_id: int, lines: list[tuple[int, int, int, Decimal]],
                          grn_date: date | None = None, remarks: str | None = None) -> GRN:
        po = await self.session.get(PurchaseOrder, po_id, options=[selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.items)])
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
        transaction_type = "SUB_VENDOR_GRN" if po.supplier.contact_type == "Sub vendor" else "PURCHASE"
        for saree_id, received_qty, damaged_qty, rate in lines:
            total_receipt_qty = received_qty + damaged_qty
            if received_qty < 0 or damaged_qty < 0 or total_receipt_qty <= 0:
                raise ValueError("Received or damaged quantity is required.")
            if po.supplier.contact_type == "Sub vendor":
                fg_item = await self.session.get(Saree, saree_id)
                allowed_fg_ids = {item.target_fg_saree_id for item in po.items if item.target_fg_saree_id is not None}
                if fg_item is None or fg_item.fabric != "FG":
                    raise ValueError("Sub vendor GRN stock-in item must be an FG item.")
                if allowed_fg_ids and saree_id not in allowed_fg_ids:
                    raise ValueError("GRN stock-in FG must match the FG selected on the Sub vendor PO.")
                pending = await self.pending_po_qty(po_id)
            else:
                stock_in_item = await self.session.get(Saree, saree_id)
                if stock_in_item is None or stock_in_item.fabric != "RM":
                    raise ValueError("RM vendor GRN stock-in item must be an RM item.")
                pending = await self.pending_po_qty(po_id, saree_id)
            if total_receipt_qty > pending:
                raise ValueError(f"Receipt quantity exceeds pending PO quantity. Pending: {pending}.")
            grn.items.append(GRNItem(saree_id=saree_id, received_qty=received_qty, damaged_qty=damaged_qty, rate=rate))
            if po.supplier.contact_type == "Sub vendor":
                await self._consume_wip(po, total_receipt_qty, document_date, grn.grn_number, rate, remarks)
            if received_qty:
                await self.inventory.post_ledger(
                    transaction_date=document_date, transaction_type=transaction_type,
                    reference_no=grn.grn_number, saree_id=saree_id,
                    qty_in=received_qty, rate=rate, remarks=remarks,
                )
        self.session.add(grn)
        await self.session.flush()
        await self._update_po_status(po)
        return grn

    async def pending_po_qty(self, po_id: int, saree_id: int | None = None) -> int:
        stmt = select(func.coalesce(func.sum(PurchaseOrderItem.ordered_qty), 0)).where(PurchaseOrderItem.po_id == po_id)
        if saree_id is not None:
            stmt = stmt.where(PurchaseOrderItem.saree_id == saree_id)
        ordered = int(await self.session.scalar(stmt) or 0)
        if saree_id is None:
            received = int(await self.session.scalar(
                select(func.coalesce(func.sum(GRNItem.received_qty + GRNItem.damaged_qty), 0))
                .join(GRN).where(GRN.po_id == po_id)
            ) or 0)
        else:
            received = int(await self.session.scalar(
                select(func.coalesce(func.sum(GRNItem.received_qty + GRNItem.damaged_qty), 0))
                .join(GRN).where(GRN.po_id == po_id, GRNItem.saree_id == saree_id)
            ) or 0)
        return max(ordered - received, 0)

    async def _consume_wip(self, po: PurchaseOrder, quantity: int, document_date, reference_no, rate, remarks):
        remaining = quantity
        for item in po.items:
            if remaining <= 0:
                break
            available = await self.inventory.current_stock(item.saree_id)
            consume_qty = min(remaining, item.ordered_qty, available)
            if consume_qty > 0:
                await self.inventory.post_ledger(
                    transaction_date=document_date, transaction_type="WIP_STOCK_OUT",
                    reference_no=reference_no, saree_id=item.saree_id,
                    qty_out=consume_qty, rate=rate, remarks=remarks,
                )
                remaining -= consume_qty
        if remaining > 0:
            raise ValueError("Insufficient WIP stock to complete the Sub vendor GRN.")

    async def cancel_po(self, po_id: int, cancel_date: date | None = None, remarks: str | None = None) -> PurchaseOrder:
        po = await self.session.get(PurchaseOrder, po_id, options=[selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.items)])
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
        if po.supplier.contact_type == "Sub vendor":
            for item in po.items:
                if item.stock_out_saree_id is not None:
                    await self.inventory.post_ledger(
                        transaction_date=document_date, transaction_type="SUB_VENDOR_ISSUE_CANCEL",
                        reference_no=po.po_number, saree_id=item.stock_out_saree_id,
                        qty_in=item.ordered_qty, rate=item.rate, remarks=remarks or po.remarks,
                    )
                await self.inventory.assert_available(item.saree_id, item.ordered_qty)
                await self.inventory.post_ledger(
                    transaction_date=document_date, transaction_type="WIP_STOCK_CANCEL",
                    reference_no=po.po_number, saree_id=item.saree_id,
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

    async def list_pos(self, status: str | None = None, supplier_id: int | None = None,
                       search: str = "", date_from: date | None = None, date_to: date | None = None,
                       page: int = 1, page_size: int = 50) -> tuple[list[PurchaseOrder], int]:
        stmt = select(PurchaseOrder).options(
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.saree),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.stock_out_saree),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.target_fg_saree),
        )
        count_stmt = select(func.count()).select_from(PurchaseOrder)
        if status:
            stmt = stmt.where(PurchaseOrder.status == status)
            count_stmt = count_stmt.where(PurchaseOrder.status == status)
        if supplier_id:
            stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
            count_stmt = count_stmt.where(PurchaseOrder.supplier_id == supplier_id)
        if search:
            like = f"%{search}%"
            stmt = stmt.join(Supplier).where(PurchaseOrder.po_number.ilike(like) | Supplier.supplier_name.ilike(like))
            count_stmt = count_stmt.join(Supplier).where(PurchaseOrder.po_number.ilike(like) | Supplier.supplier_name.ilike(like))
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
            selectinload(GRN.items).selectinload(GRNItem.saree),
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
