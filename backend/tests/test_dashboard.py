"""Dashboard cards, including the Vendor WIP definition."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.dashboard_service import DashboardService
from app.services.master_service import MasterService
from app.services.purchase_service import GRNLine, PurchaseLine, PurchaseService


async def test_empty_dashboard_returns_zeros(db: AsyncSession):
    cards = (await DashboardService(db).get_dashboard()).cards
    assert cards.total_stock_qty == 0
    assert cards.stock_value == Decimal("0")
    assert cards.vendor_wip_qty == 0
    assert cards.damaged_qty == 0
    assert cards.short_qty == 0
    assert cards.active_items == 0
    assert cards.active_contacts == 0


async def test_empty_dashboard_returns_no_panels(db: AsyncSession):
    board = await DashboardService(db).get_dashboard()
    assert board.sub_process_split == []
    assert board.vendor_pending == []
    assert board.recent_grns == []


async def test_damaged_and_short_are_totalled_across_grns(db: AsyncSession, masters: MasterService,
                                                          purchase: PurchaseService):
    contact = await masters.create_contact("V", "Raw Material Vendor")
    item = await masters.create_item(None, "RM", item_type="RM")
    await db.flush()
    po = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 10, Decimal("5"))])
    await purchase.receive_grn(po.po_id, [
        GRNLine(item_id=item.item_id, received_qty=6, damaged_qty=3, rate=Decimal("5"), short_qty=1),
    ])
    await db.flush()

    cards = (await DashboardService(db).get_dashboard()).cards
    assert (cards.damaged_qty, cards.short_qty) == (3, 1)


async def test_recent_grns_name_the_vendor_and_type(db: AsyncSession, masters: MasterService,
                                                    purchase: PurchaseService):
    vendor = await masters.create_contact("Acme", "Raw Material Vendor")
    item = await masters.create_item(None, "Grey", item_type="RM")
    await db.flush()
    await purchase.receive_direct_grn(vendor.contact_id, [
        GRNLine(item_id=item.item_id, received_qty=25, rate=Decimal("4"), po_number="PO-EXT-1"),
    ])
    await db.flush()

    recent = (await DashboardService(db).get_dashboard()).recent_grns
    assert len(recent) == 1
    assert recent[0].grn_type == "RM"
    assert recent[0].vendor_name == "Acme"
    assert recent[0].received_qty == 25


async def test_vendor_pending_lists_outstanding_sub_vendor_work(db: AsyncSession):
    master = MasterService(db)
    rm_vendor = await master.create_contact("RM Vendor", "Raw Material Vendor")
    sub_vendor = await master.create_contact("Dye House", "Sub vendor")
    rm = await master.create_item(None, "Grey", item_type="RM")
    wip = await master.create_item(None, "Dyeing", item_type="Sub process", category="Dying")
    fg = await master.create_item(None, "Dyed Saree", item_type="FG")
    await db.flush()

    svc = PurchaseService(db)
    rm_po = await svc.create_po(rm_vendor.contact_id, [PurchaseLine(rm.item_id, 100, Decimal("50"))])
    await svc.receive_grn(rm_po.po_id, [(rm.item_id, 100, 0, Decimal("50"))])
    sub_po = await svc.create_po(sub_vendor.contact_id, [
        PurchaseLine(wip.item_id, 40, Decimal("15"),
                     stock_out_item_id=rm.item_id, target_fg_item_id=fg.item_id),
    ])
    await db.flush()

    board = await DashboardService(db).get_dashboard()
    assert [(v.vendor_name, v.pending_qty, v.open_vouchers) for v in board.vendor_pending] == [("Dye House", 40, 1)]
    assert [(c.category, c.qty) for c in board.sub_process_split] == [("Dying", 40)]

    # Receiving part of it leaves the rest outstanding.
    await svc.receive_grn(sub_po.po_id, [(fg.item_id, 15, 0, Decimal("15"))])
    await db.flush()
    assert (await DashboardService(db).get_dashboard()).vendor_pending[0].pending_qty == 25


async def test_cards_count_active_masters(db: AsyncSession, masters: MasterService):
    await masters.create_item("RM1", "RM", item_type="RM")
    await masters.create_item("FG1", "FG", item_type="FG")
    await masters.create_contact("Vendor A", "Raw Material Vendor")
    await masters.create_process_type("Dyeing")
    await masters.create_vendor("Dye House", "Dyeing")
    await db.flush()

    cards = (await DashboardService(db).get_dashboard()).cards
    assert cards.active_items == 2
    assert cards.active_contacts == 1
    assert cards.active_vendors == 1


async def test_open_po_value_and_pending_quantity(db: AsyncSession, masters: MasterService,
                                                  purchase: PurchaseService):
    contact = await masters.create_contact("V", "Raw Material Vendor")
    item = await masters.create_item("RM1", "RM", item_type="RM")
    await db.flush()

    await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 10, Decimal("50"))])
    await db.flush()

    cards = (await DashboardService(db).get_dashboard()).cards
    assert cards.open_po_value == Decimal("500")
    assert cards.pending_po_qty == 10


async def test_stock_quantity_and_value_after_receipt(db: AsyncSession, stocked_rm):
    cards = (await DashboardService(db).get_dashboard()).cards
    assert cards.total_stock_qty == 100
    assert cards.stock_value == Decimal("5000")


async def test_vendor_wip_is_the_quantity_sitting_with_sub_vendors(db: AsyncSession):
    master = MasterService(db)
    rm_vendor = await master.create_contact("RM Vendor", "Raw Material Vendor")
    sub_vendor = await master.create_contact("Dye House", "Sub vendor")
    rm = await master.create_item("RM1", "Grey", item_type="RM")
    wip = await master.create_item("SP1", "Dyeing", item_type="Sub process")
    fg = await master.create_item("FG1", "Dyed Saree", item_type="FG")
    await db.flush()

    svc = PurchaseService(db)
    rm_po = await svc.create_po(rm_vendor.contact_id, [PurchaseLine(rm.item_id, 100, Decimal("50"))])
    await svc.receive_grn(rm_po.po_id, [(rm.item_id, 100, 0, Decimal("50"))])
    await db.flush()

    assert (await DashboardService(db).get_dashboard()).cards.vendor_wip_qty == 0

    # Issuing to the sub vendor parks 30 units in WIP.
    sub_po = await svc.create_po(sub_vendor.contact_id, [
        PurchaseLine(wip.item_id, 30, Decimal("15"),
                     stock_out_item_id=rm.item_id, target_fg_item_id=fg.item_id),
    ])
    await db.flush()
    assert (await DashboardService(db).get_dashboard()).cards.vendor_wip_qty == 30

    # Receiving finished goods clears it again.
    await svc.receive_grn(sub_po.po_id, [(fg.item_id, 30, 0, Decimal("15"))])
    await db.flush()
    assert (await DashboardService(db).get_dashboard()).cards.vendor_wip_qty == 0


async def test_cancelling_a_sub_vendor_po_clears_wip(db: AsyncSession):
    master = MasterService(db)
    rm_vendor = await master.create_contact("RM Vendor", "Raw Material Vendor")
    sub_vendor = await master.create_contact("Dye House", "Sub vendor")
    rm = await master.create_item("RM1", "Grey", item_type="RM")
    wip = await master.create_item("SP1", "Dyeing", item_type="Sub process")
    fg = await master.create_item("FG1", "Dyed Saree", item_type="FG")
    await db.flush()

    svc = PurchaseService(db)
    rm_po = await svc.create_po(rm_vendor.contact_id, [PurchaseLine(rm.item_id, 50, Decimal("10"))])
    await svc.receive_grn(rm_po.po_id, [(rm.item_id, 50, 0, Decimal("10"))])
    sub_po = await svc.create_po(sub_vendor.contact_id, [
        PurchaseLine(wip.item_id, 20, Decimal("5"),
                     stock_out_item_id=rm.item_id, target_fg_item_id=fg.item_id),
    ])
    await db.flush()
    assert (await DashboardService(db).get_dashboard()).cards.vendor_wip_qty == 20

    await svc.cancel_po(sub_po.po_id)
    await db.flush()
    assert (await DashboardService(db).get_dashboard()).cards.vendor_wip_qty == 0


async def test_dashboard_sections_are_present(db: AsyncSession, stocked_rm):
    result = await DashboardService(db).get_dashboard()
    assert isinstance(result.purchase_trend, list)
    assert isinstance(result.stock_movement, list)
    assert isinstance(result.top_categories, list)
