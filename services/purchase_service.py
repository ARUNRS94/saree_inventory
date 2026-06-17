"""Purchase order, sub-vendor processing and GRN workflows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models.entities import GRN, GRNItem, PurchaseOrder, PurchaseOrderItem, Supplier
from services.inventory_service import InventoryService
from services.numbering import next_number


@dataclass(frozen=True)
class PurchaseLine:
    saree_id: int
    quantity: int
    rate: Decimal
    stock_out_saree_id: int | None = None


class PurchaseService:
    """Business rules for RM vendor purchase and sub-vendor process orders."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.inventory = InventoryService(session)

    def create_po(self, supplier_id: int, lines: list[PurchaseLine], po_date: date | None = None,
                  expected_date: date | None = None, remarks: str | None = None) -> PurchaseOrder:
        if not lines:
            raise ValueError("Purchase order requires at least one item line.")
        contact = self.session.get(Supplier, supplier_id)
        if contact is None:
            raise ValueError("Contact not found.")
        if contact.contact_type == "Customer":
            raise ValueError("Purchase orders can be created only for RM vendors or Sub vendors.")
        document_date = po_date or date.today()
        po = PurchaseOrder(
            po_number=next_number(self.session, PurchaseOrder, "po_number", "PO", document_date),
            supplier_id=supplier_id,
            po_date=document_date,
            expected_date=expected_date,
            remarks=remarks,
            status="OPEN",
        )
        for line in lines:
            if line.quantity <= 0 or line.rate < 0:
                raise ValueError("PO quantity must be positive and rate/process charges cannot be negative.")
            if contact.contact_type == "Sub vendor":
                if line.stock_out_saree_id is None:
                    raise ValueError("Select the RM stock-out item for Sub vendor process orders.")
                self.inventory.assert_available(line.stock_out_saree_id, line.quantity)
                self.inventory.post_ledger(
                    transaction_date=document_date,
                    transaction_type="SUB_VENDOR_ISSUE",
                    reference_no=po.po_number,
                    saree_id=line.stock_out_saree_id,
                    qty_out=line.quantity,
                    rate=line.rate,
                    remarks=remarks,
                )
            po.items.append(
                PurchaseOrderItem(
                    saree_id=line.saree_id,
                    stock_out_saree_id=line.stock_out_saree_id,
                    ordered_qty=line.quantity,
                    rate=line.rate,
                    amount=line.rate * line.quantity,
                )
            )
        self.session.add(po)
        return po

    def receive_grn(self, po_id: int, lines: list[tuple[int, int, int, Decimal]], grn_date: date | None = None,
                    remarks: str | None = None) -> GRN:
        po = self.session.get(PurchaseOrder, po_id)
        if po is None:
            raise ValueError("Purchase order not found.")
        if not lines:
            raise ValueError("GRN requires at least one received line.")

        document_date = grn_date or date.today()
        grn = GRN(
            grn_number=next_number(self.session, GRN, "grn_number", "GRN", document_date),
            po_id=po_id,
            grn_date=document_date,
            remarks=remarks,
        )
        transaction_type = "SUB_VENDOR_GRN" if po.supplier.contact_type == "Sub vendor" else "PURCHASE"
        for saree_id, received_qty, damaged_qty, rate in lines:
            total_receipt_qty = received_qty + damaged_qty
            if received_qty < 0 or damaged_qty < 0 or total_receipt_qty <= 0:
                raise ValueError("Received or damaged quantity is required.")
            pending = self.pending_po_qty(po_id, saree_id)
            if total_receipt_qty > pending:
                raise ValueError(f"Receipt quantity exceeds pending PO quantity. Pending: {pending}.")
            grn.items.append(GRNItem(saree_id=saree_id, received_qty=received_qty, damaged_qty=damaged_qty, rate=rate))
            if received_qty:
                self.inventory.post_ledger(
                    transaction_date=document_date,
                    transaction_type=transaction_type,
                    reference_no=grn.grn_number,
                    saree_id=saree_id,
                    qty_in=received_qty,
                    rate=rate,
                    remarks=remarks,
                )
        self.session.add(grn)
        self.session.flush()
        self._update_po_status(po)
        return grn

    def already_received_qty(self, po_id: int, saree_id: int) -> int:
        return int(
            self.session.scalar(
                select(func.coalesce(func.sum(GRNItem.received_qty + GRNItem.damaged_qty), 0))
                .join(GRN)
                .where(GRN.po_id == po_id, GRNItem.saree_id == saree_id)
            ) or 0
        )

    def pending_po_qty(self, po_id: int, saree_id: int) -> int:
        ordered = int(
            self.session.scalar(
                select(func.coalesce(func.sum(PurchaseOrderItem.ordered_qty), 0))
                .where(PurchaseOrderItem.po_id == po_id, PurchaseOrderItem.saree_id == saree_id)
            ) or 0
        )
        return max(ordered - self.already_received_qty(po_id, saree_id), 0)

    def _update_po_status(self, po: PurchaseOrder) -> None:
        ordered = sum(item.ordered_qty for item in po.items)
        received = int(
            self.session.scalar(
                select(func.coalesce(func.sum(GRNItem.received_qty + GRNItem.damaged_qty), 0))
                .join(GRN)
                .where(GRN.po_id == po.po_id)
            ) or 0
        )
        po.status = "CLOSED" if received >= ordered else "PARTIAL" if received > 0 else "OPEN"
