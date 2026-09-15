"""End-to-end checks against the shared `scenario` dataset.

The dataset is one small business mid-flight: goods received, one order part-delivered,
one still open, and a batch away at the dye house. These assert that the numbers the app
shows line up with that story.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.dashboard_service import DashboardService
from app.services.inventory_service import InventoryService
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseService


# --- masters ---

async def test_sample_masters_cover_every_type(db: AsyncSession, sample):
    master = MasterService(db)
    assert (await master.search_items("", "RM"))[1] == 2
    assert (await master.search_items("", "Sub process"))[1] == 2
    assert (await master.search_items("", "FG"))[1] == 2

    assert (await master.search_contacts("", "Raw Material Vendor"))[1] == 2
    assert (await master.search_contacts("", "Sub vendor"))[1] == 2
    assert (await master.search_contacts("", "Customer"))[1] == 1

    assert len(await master.list_process_types()) == 3
    assert (await master.search_vendors())[1] == 2


async def test_sample_masters_are_searchable(db: AsyncSession, sample):
    master = MasterService(db)
    rows, total = await master.search_items("Saree")
    assert total == 2
    assert {r.item_code for r in rows} == {"FG-SAR-01", "FG-SAR-02"}

    by_colour, colour_total = await master.search_items("Maroon")
    assert colour_total == 1
    assert by_colour[0].item_code == "FG-SAR-02"

    by_phone, phone_total = await master.search_contacts("9800000003")
    assert phone_total == 1
    assert by_phone[0].contact_name == "Sri Dyeing Works"


# --- stock ---

async def test_scenario_stock_balances(db: AsyncSession, scenario):
    inventory = InventoryService(db)
    data = scenario.data

    assert await inventory.current_stock(data.cotton.item_id) == 70   # 100 in, 30 to the dye house
    assert await inventory.current_stock(data.silk.item_id) == 25     # part-delivered
    assert await inventory.current_stock(data.dyeing.item_id) == 30   # sitting in WIP
    assert await inventory.current_stock(data.cotton_saree.item_id) == 0
    assert await inventory.current_stock() == 125


async def test_scenario_valuation(db: AsyncSession, scenario):
    inventory = InventoryService(db)
    rows = {r["item_code"]: r for r in await inventory.inventory_valuation()}

    assert rows["RM-COT-01"]["latest_rate"] == Decimal("50")
    assert rows["RM-COT-01"]["value"] == Decimal("3500")
    assert rows["RM-SLK-01"]["value"] == Decimal("3000")
    # WIP has no purchase rate of its own, so it carries no value.
    assert rows["SP-DYE-01"]["value"] == Decimal("0")
    assert await inventory.total_inventory_value() == Decimal("6500")


async def test_scenario_stock_report_lists_all_six_items(db: AsyncSession, scenario):
    report = await InventoryService(db).stock_report()
    assert len(report) == 6
    assert {r["item_code"] for r in report if r["current_stock"] > 0} == {
        "RM-COT-01", "RM-SLK-01", "SP-DYE-01",
    }


# --- purchase orders ---

async def test_scenario_po_statuses(db: AsyncSession, scenario):
    await db.refresh(scenario.closed_po)
    await db.refresh(scenario.partial_po)
    await db.refresh(scenario.open_po)

    assert scenario.closed_po.status == "CLOSED"
    assert scenario.partial_po.status == "PARTIAL"
    assert scenario.open_po.status == "OPEN"


async def test_scenario_pending_quantities(db: AsyncSession, scenario):
    svc = PurchaseService(db)
    assert await svc.pending_po_qty(scenario.closed_po.po_id) == 0
    assert await svc.pending_po_qty(scenario.partial_po.po_id) == 35   # 60 ordered, 25 received
    assert await svc.pending_po_qty(scenario.open_po.po_id) == 40


async def test_scenario_po_listing_and_filters(db: AsyncSession, scenario):
    svc = PurchaseService(db)
    _, total = await svc.list_pos()
    assert total == 4

    _, open_count = await svc.list_pos(status="OPEN")
    assert open_count == 2  # the RM order plus the sub vendor order

    _, alpha_count = await svc.list_pos(contact_id=scenario.data.alpha.contact_id)
    assert alpha_count == 2

    _, searched = await svc.list_pos(search="Bharat")
    assert searched == 1


# --- dashboard ---

async def test_scenario_dashboard_matches_the_ledger(db: AsyncSession, scenario):
    cards = (await DashboardService(db).get_dashboard()).cards
    assert cards.total_stock_qty == 125
    assert cards.stock_value == Decimal("6500")
    assert cards.vendor_wip_qty == 30
    assert cards.active_items == 6
    assert cards.active_contacts == 5
    assert cards.active_vendors == 2


async def test_scenario_completing_the_dye_run_moves_wip_into_finished_goods(db: AsyncSession, scenario):
    svc = PurchaseService(db)
    inventory = InventoryService(db)
    data = scenario.data

    await svc.receive_grn(scenario.sub_po.po_id, [(data.cotton_saree.item_id, 30, 0, Decimal("15"))])
    await db.flush()

    assert await inventory.current_stock(data.dyeing.item_id) == 0
    assert await inventory.current_stock(data.cotton_saree.item_id) == 30
    assert await inventory.current_stock(data.cotton.item_id) == 70   # unchanged by the receipt

    cards = (await DashboardService(db).get_dashboard()).cards
    assert cards.vendor_wip_qty == 0
    assert cards.total_stock_qty == 125  # 30 left WIP, 30 arrived as finished goods
