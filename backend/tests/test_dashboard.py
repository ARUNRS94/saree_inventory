"""Dashboard cards, including the Vendor WIP definition."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.dashboard_service import DashboardService
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseLine, PurchaseService


async def test_empty_dashboard_returns_zeros(db: AsyncSession):
    cards = (await DashboardService(db).get_dashboard()).cards
    assert cards.total_stock_qty == 0
    assert cards.stock_value == Decimal("0")
    assert cards.vendor_wip_qty == 0
    assert cards.active_items == 0
    assert cards.active_contacts == 0


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
