"""Purchase orders and goods receipts, including the Sub vendor process flow."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock_ledger import StockLedger
from app.services.inventory_service import InventoryService
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseLine, PurchaseService


async def _sub_vendor_setup(db: AsyncSession):
    """RM stock on hand, plus the three items a Sub vendor order needs."""
    master = MasterService(db)
    rm_vendor = await master.create_contact("RM Vendor", "Raw Material Vendor")
    sub_vendor = await master.create_contact("Dye House", "Sub vendor")
    rm = await master.create_item("RM1", "Grey Fabric", item_type="RM")
    wip = await master.create_item("SP1", "Dyeing", item_type="Sub process")
    fg = await master.create_item("FG1", "Dyed Saree", item_type="FG")
    await db.flush()

    svc = PurchaseService(db)
    po = await svc.create_po(rm_vendor.contact_id, [PurchaseLine(rm.item_id, 100, Decimal("50"))])
    await svc.receive_grn(po.po_id, [(rm.item_id, 100, 0, Decimal("50"))])
    await db.flush()
    return svc, sub_vendor, rm, wip, fg


# --- creation rules ---

async def test_po_requires_lines(db: AsyncSession, masters: MasterService, purchase: PurchaseService):
    contact = await masters.create_contact("V", "Raw Material Vendor")
    await db.flush()
    with pytest.raises(ValueError, match="at least one item line"):
        await purchase.create_po(contact.contact_id, [])


async def test_po_rejects_unknown_contact(purchase: PurchaseService):
    with pytest.raises(ValueError, match="Contact not found"):
        await purchase.create_po(9999, [PurchaseLine(1, 1, Decimal("1"))])


async def test_po_cannot_be_raised_against_a_customer(db: AsyncSession, masters: MasterService,
                                                     purchase: PurchaseService):
    customer = await masters.create_contact("Retail Buyer", "Customer")
    item = await masters.create_item("RM1", "RM", item_type="RM")
    await db.flush()
    with pytest.raises(ValueError, match="only for Raw Material Vendors or Sub vendors"):
        await purchase.create_po(customer.contact_id, [PurchaseLine(item.item_id, 1, Decimal("1"))])


@pytest.mark.parametrize("qty,rate", [(0, "10"), (-5, "10"), (5, "-1")])
async def test_po_rejects_bad_quantity_or_rate(db: AsyncSession, masters: MasterService,
                                               purchase: PurchaseService, qty, rate):
    contact = await masters.create_contact("V", "Raw Material Vendor")
    item = await masters.create_item("RM1", "RM", item_type="RM")
    await db.flush()
    with pytest.raises(ValueError, match="quantity must be positive"):
        await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, qty, Decimal(rate))])


@pytest.mark.parametrize("item_type", ["FG", "Sub process"])
async def test_rm_vendor_po_accepts_only_rm_items(db: AsyncSession, masters: MasterService,
                                                  purchase: PurchaseService, item_type):
    contact = await masters.create_contact("RM Vendor", "Raw Material Vendor")
    item = await masters.create_item("X1", "Wrong type", item_type=item_type)
    await db.flush()
    with pytest.raises(ValueError, match="only Raw Material items"):
        await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 5, Decimal("10"))])


async def test_sub_vendor_po_accepts_only_sub_process_items(db: AsyncSession):
    svc, sub_vendor, rm, wip, fg = await _sub_vendor_setup(db)
    with pytest.raises(ValueError, match="only Sub Process items"):
        await svc.create_po(sub_vendor.contact_id, [
            PurchaseLine(fg.item_id, 5, Decimal("10"), stock_out_item_id=rm.item_id, target_fg_item_id=fg.item_id),
        ])


async def test_sub_vendor_po_requires_stock_out_item(db: AsyncSession):
    svc, sub_vendor, rm, wip, fg = await _sub_vendor_setup(db)
    with pytest.raises(ValueError, match="stock-out item"):
        await svc.create_po(sub_vendor.contact_id, [PurchaseLine(wip.item_id, 5, Decimal("10"))])


async def test_sub_vendor_po_requires_target_fg_item(db: AsyncSession):
    svc, sub_vendor, rm, wip, fg = await _sub_vendor_setup(db)
    with pytest.raises(ValueError, match="target Finished Goods item"):
        await svc.create_po(sub_vendor.contact_id, [
            PurchaseLine(wip.item_id, 5, Decimal("10"), stock_out_item_id=rm.item_id),
        ])


async def test_sub_vendor_po_rejects_sub_process_as_stock_out(db: AsyncSession):
    svc, sub_vendor, rm, wip, fg = await _sub_vendor_setup(db)
    with pytest.raises(ValueError, match="Raw Material or Finished Goods"):
        await svc.create_po(sub_vendor.contact_id, [
            PurchaseLine(wip.item_id, 5, Decimal("10"),
                         stock_out_item_id=wip.item_id, target_fg_item_id=fg.item_id),
        ])


async def test_sub_vendor_po_requires_available_stock_out_quantity(db: AsyncSession):
    svc, sub_vendor, rm, wip, fg = await _sub_vendor_setup(db)
    with pytest.raises(ValueError, match="Insufficient stock"):
        await svc.create_po(sub_vendor.contact_id, [
            PurchaseLine(wip.item_id, 500, Decimal("10"),
                         stock_out_item_id=rm.item_id, target_fg_item_id=fg.item_id),
        ])


# --- the full Sub vendor cycle ---

async def test_sub_vendor_cycle_moves_stock_rm_to_wip_to_fg(db: AsyncSession):
    svc, sub_vendor, rm, wip, fg = await _sub_vendor_setup(db)
    inventory = InventoryService(db)

    po = await svc.create_po(sub_vendor.contact_id, [
        PurchaseLine(wip.item_id, 20, Decimal("15"),
                     stock_out_item_id=rm.item_id, target_fg_item_id=fg.item_id),
    ])
    await db.flush()

    # Issuing to the sub vendor takes RM out and parks the quantity in WIP.
    assert await inventory.current_stock(rm.item_id) == 80
    assert await inventory.current_stock(wip.item_id) == 20
    assert await inventory.current_stock(fg.item_id) == 0

    await svc.receive_grn(po.po_id, [(fg.item_id, 20, 0, Decimal("15"))])
    await db.flush()

    # Receiving clears WIP and brings in the finished goods.
    assert await inventory.current_stock(rm.item_id) == 80
    assert await inventory.current_stock(wip.item_id) == 0
    assert await inventory.current_stock(fg.item_id) == 20

    types = (await db.execute(select(StockLedger.transaction_type).order_by(StockLedger.ledger_id))).scalars().all()
    assert types == ["PURCHASE", "SUB_VENDOR_ISSUE", "WIP_STOCK_IN", "WIP_STOCK_OUT", "SUB_VENDOR_GRN"]


async def test_sub_vendor_grn_must_stock_in_the_declared_fg_item(db: AsyncSession):
    svc, sub_vendor, rm, wip, fg = await _sub_vendor_setup(db)
    other_fg = await MasterService(db).create_item("FG2", "Another FG", item_type="FG")
    await db.flush()

    po = await svc.create_po(sub_vendor.contact_id, [
        PurchaseLine(wip.item_id, 10, Decimal("5"),
                     stock_out_item_id=rm.item_id, target_fg_item_id=fg.item_id),
    ])
    with pytest.raises(ValueError, match="must match the Finished Goods item"):
        await svc.receive_grn(po.po_id, [(other_fg.item_id, 10, 0, Decimal("5"))])


async def test_sub_vendor_grn_rejects_non_fg_stock_in(db: AsyncSession):
    svc, sub_vendor, rm, wip, fg = await _sub_vendor_setup(db)
    po = await svc.create_po(sub_vendor.contact_id, [
        PurchaseLine(wip.item_id, 10, Decimal("5"),
                     stock_out_item_id=rm.item_id, target_fg_item_id=fg.item_id),
    ])
    with pytest.raises(ValueError, match="must be a Finished Goods item"):
        await svc.receive_grn(po.po_id, [(rm.item_id, 10, 0, Decimal("5"))])


async def test_cancelling_a_sub_vendor_po_returns_the_raw_material(db: AsyncSession):
    svc, sub_vendor, rm, wip, fg = await _sub_vendor_setup(db)
    inventory = InventoryService(db)

    po = await svc.create_po(sub_vendor.contact_id, [
        PurchaseLine(wip.item_id, 30, Decimal("15"),
                     stock_out_item_id=rm.item_id, target_fg_item_id=fg.item_id),
    ])
    await db.flush()
    assert await inventory.current_stock(rm.item_id) == 70

    await svc.cancel_po(po.po_id)
    await db.flush()

    assert po.status == "CANCELLED"
    assert await inventory.current_stock(rm.item_id) == 100
    assert await inventory.current_stock(wip.item_id) == 0


# --- GRN rules ---

async def test_grn_rejects_non_rm_stock_in_for_rm_vendor(db: AsyncSession, masters: MasterService,
                                                        purchase: PurchaseService):
    contact = await masters.create_contact("RM Vendor", "Raw Material Vendor")
    rm = await masters.create_item("RM1", "RM", item_type="RM")
    fg = await masters.create_item("FG1", "FG", item_type="FG")
    await db.flush()
    po = await purchase.create_po(contact.contact_id, [PurchaseLine(rm.item_id, 10, Decimal("5"))])
    with pytest.raises(ValueError, match="must be a Raw Material item"):
        await purchase.receive_grn(po.po_id, [(fg.item_id, 5, 0, Decimal("5"))])


async def test_grn_requires_lines_and_positive_quantity(db: AsyncSession, stocked_rm,
                                                       purchase: PurchaseService):
    po = stocked_rm["po"]
    with pytest.raises(ValueError, match="at least one received line"):
        await purchase.receive_grn(po.po_id, [])


async def test_grn_rejects_zero_and_negative_quantities(db: AsyncSession, masters: MasterService,
                                                       purchase: PurchaseService):
    contact = await masters.create_contact("V", "Raw Material Vendor")
    item = await masters.create_item("RM1", "RM", item_type="RM")
    await db.flush()
    po = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 10, Decimal("5"))])
    with pytest.raises(ValueError, match="Received or damaged quantity is required"):
        await purchase.receive_grn(po.po_id, [(item.item_id, 0, 0, Decimal("5"))])
    with pytest.raises(ValueError, match="Received or damaged quantity is required"):
        await purchase.receive_grn(po.po_id, [(item.item_id, -1, 0, Decimal("5"))])


async def test_damaged_quantity_counts_against_the_po_but_not_stock(db: AsyncSession,
                                                                   masters: MasterService,
                                                                   purchase: PurchaseService):
    contact = await masters.create_contact("V", "Raw Material Vendor")
    item = await masters.create_item("RM1", "RM", item_type="RM")
    await db.flush()

    po = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 10, Decimal("5"))])
    await purchase.receive_grn(po.po_id, [(item.item_id, 8, 2, Decimal("5"))])
    await db.flush()
    await db.refresh(po)

    assert po.status == "CLOSED"
    assert await purchase.pending_po_qty(po.po_id, item.item_id) == 0
    # Only the good units reach the ledger.
    assert await InventoryService(db).current_stock(item.item_id) == 8


async def test_grn_only_damaged_units_closes_po_without_stock(db: AsyncSession, masters: MasterService,
                                                             purchase: PurchaseService):
    contact = await masters.create_contact("V", "Raw Material Vendor")
    item = await masters.create_item("RM1", "RM", item_type="RM")
    await db.flush()

    po = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 4, Decimal("5"))])
    await purchase.receive_grn(po.po_id, [(item.item_id, 0, 4, Decimal("5"))])
    await db.flush()
    await db.refresh(po)

    assert po.status == "CLOSED"
    assert await InventoryService(db).current_stock(item.item_id) == 0


async def test_pending_qty_shrinks_across_partial_receipts(db: AsyncSession, masters: MasterService,
                                                          purchase: PurchaseService):
    contact = await masters.create_contact("V", "Raw Material Vendor")
    item = await masters.create_item("RM1", "RM", item_type="RM")
    await db.flush()

    po = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 30, Decimal("5"))])
    assert await purchase.pending_po_qty(po.po_id, item.item_id) == 30

    await purchase.receive_grn(po.po_id, [(item.item_id, 10, 0, Decimal("5"))])
    assert await purchase.pending_po_qty(po.po_id, item.item_id) == 20

    await purchase.receive_grn(po.po_id, [(item.item_id, 20, 0, Decimal("5"))])
    assert await purchase.pending_po_qty(po.po_id, item.item_id) == 0


# --- cancellation ---

async def test_cancel_twice_rejected(db: AsyncSession, masters: MasterService, purchase: PurchaseService):
    contact = await masters.create_contact("V", "Raw Material Vendor")
    item = await masters.create_item("RM1", "RM", item_type="RM")
    await db.flush()
    po = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 5, Decimal("5"))])
    await purchase.cancel_po(po.po_id)
    with pytest.raises(ValueError, match="already cancelled"):
        await purchase.cancel_po(po.po_id)


async def test_cancel_unknown_po(purchase: PurchaseService):
    with pytest.raises(ValueError, match="not found"):
        await purchase.cancel_po(4242)


# --- numbering ---

async def test_document_numbers_increment_within_the_year(db: AsyncSession, masters: MasterService,
                                                          purchase: PurchaseService):
    contact = await masters.create_contact("V", "Raw Material Vendor")
    item = await masters.create_item("RM1", "RM", item_type="RM")
    await db.flush()

    first = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 1, Decimal("1"))],
                                     po_date=date(2026, 1, 5))
    second = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 1, Decimal("1"))],
                                      po_date=date(2026, 6, 5))
    assert first.po_number == "PO-2026-0001"
    assert second.po_number == "PO-2026-0002"

    # A different year restarts the sequence.
    other_year = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 1, Decimal("1"))],
                                          po_date=date(2027, 1, 1))
    assert other_year.po_number == "PO-2027-0001"
