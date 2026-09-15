"""Stock ledger, valuation and rate precedence."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.inventory_service import InventoryService
from app.services.master_service import MasterService
from app.services.purchase_service import PurchaseLine, PurchaseService


# --- ledger guards ---

async def test_ledger_entry_needs_a_quantity(db: AsyncSession, masters: MasterService):
    item = await masters.create_item("RM1", "RM", item_type="RM")
    await db.flush()
    inventory = InventoryService(db)
    with pytest.raises(ValueError, match="positive QtyIn or QtyOut"):
        await inventory.post_ledger(
            transaction_date=date.today(), transaction_type="ADJUST",
            reference_no="X", item_id=item.item_id,
        )


async def test_ledger_entry_rejects_negative_quantities(db: AsyncSession, masters: MasterService):
    item = await masters.create_item("RM1", "RM", item_type="RM")
    await db.flush()
    with pytest.raises(ValueError, match="positive QtyIn or QtyOut"):
        await InventoryService(db).post_ledger(
            transaction_date=date.today(), transaction_type="ADJUST",
            reference_no="X", item_id=item.item_id, qty_in=-5,
        )


async def test_assert_available(db: AsyncSession, stocked_rm):
    inventory = InventoryService(db)
    item_id = stocked_rm["item"].item_id

    await inventory.assert_available(item_id, 100)  # exactly the balance is fine
    with pytest.raises(ValueError, match="Insufficient stock"):
        await inventory.assert_available(item_id, 101)
    with pytest.raises(ValueError, match="greater than zero"):
        await inventory.assert_available(item_id, 0)


async def test_current_stock_across_all_items(db: AsyncSession, stocked_rm, masters: MasterService):
    other = await masters.create_item("RM2", "Other", item_type="RM")
    await db.flush()
    inventory = InventoryService(db)
    await inventory.post_ledger(
        transaction_date=date.today(), transaction_type="OPENING",
        reference_no="OPEN", item_id=other.item_id, qty_in=25, rate=Decimal("4"),
    )
    await db.flush()
    assert await inventory.current_stock() == 125


# --- valuation ---

async def test_valuation_uses_po_rate_in_preference_to_grn_rate(db: AsyncSession,
                                                               masters: MasterService,
                                                               purchase: PurchaseService):
    contact = await masters.create_contact("V", "Raw Material Vendor")
    item = await masters.create_item("RM1", "RM", item_type="RM")
    await db.flush()

    po = await purchase.create_po(contact.contact_id, [PurchaseLine(item.item_id, 10, Decimal("50"))])
    # The GRN is booked at a different rate; the PO rate is the contracted one and wins.
    await purchase.receive_grn(po.po_id, [(item.item_id, 10, 0, Decimal("55"))])
    await db.flush()

    rows = await InventoryService(db).inventory_valuation()
    row = next(r for r in rows if r["item_id"] == item.item_id)
    assert row["current_stock"] == 10
    assert row["latest_rate"] == Decimal("50")
    assert row["value"] == Decimal("500")


async def test_valuation_falls_back_to_the_ledger_rate(db: AsyncSession, masters: MasterService):
    item = await masters.create_item("RM9", "Opening only", item_type="RM")
    await db.flush()
    inventory = InventoryService(db)
    await inventory.post_ledger(
        transaction_date=date.today(), transaction_type="PURCHASE",
        reference_no="MANUAL", item_id=item.item_id, qty_in=7, rate=Decimal("12"),
    )
    await db.flush()

    rows = await inventory.inventory_valuation()
    row = next(r for r in rows if r["item_id"] == item.item_id)
    assert row["latest_rate"] == Decimal("12")
    assert row["value"] == Decimal("84")


async def test_items_without_movement_value_at_zero(db: AsyncSession, masters: MasterService):
    await masters.create_item("NEW1", "Never purchased", item_type="FG")
    await db.flush()
    rows = await InventoryService(db).inventory_valuation()
    row = next(r for r in rows if r["item_code"] == "NEW1")
    assert row["current_stock"] == 0
    assert row["latest_rate"] == Decimal("0")
    assert row["value"] == Decimal("0")


async def test_total_inventory_value_matches_the_sum_of_rows(db: AsyncSession, stocked_rm,
                                                             masters: MasterService,
                                                             purchase: PurchaseService):
    contact = stocked_rm["contact"]
    second = await masters.create_item("RM2", "Second", item_type="RM")
    await db.flush()
    po = await purchase.create_po(contact.contact_id, [PurchaseLine(second.item_id, 4, Decimal("25"))])
    await purchase.receive_grn(po.po_id, [(second.item_id, 4, 0, Decimal("25"))])
    await db.flush()

    inventory = InventoryService(db)
    rows = await inventory.inventory_valuation()
    assert await inventory.total_inventory_value() == sum(r["value"] for r in rows)
    # 100 x 50 + 4 x 25
    assert await inventory.total_inventory_value() == Decimal("5100")


async def test_valuation_is_ordered_by_item_code(db: AsyncSession, masters: MasterService):
    for code in ["ZZ", "AA", "MM"]:
        await masters.create_item(code, code, item_type="RM")
    await db.flush()
    rows = await InventoryService(db).inventory_valuation()
    assert [r["item_code"] for r in rows] == ["AA", "MM", "ZZ"]


async def test_latest_purchase_rate_matches_the_valuation_map(db: AsyncSession, stocked_rm):
    inventory = InventoryService(db)
    item_id = stocked_rm["item"].item_id
    rows = await inventory.inventory_valuation()
    row = next(r for r in rows if r["item_id"] == item_id)
    assert await inventory.latest_purchase_rate(item_id) == row["latest_rate"]


async def test_stock_report_lists_every_item_including_empty_ones(db: AsyncSession, stocked_rm,
                                                                  masters: MasterService):
    await masters.create_item("EMPTY1", "No movement", item_type="FG")
    await db.flush()
    report = await InventoryService(db).stock_report()
    by_code = {r["item_code"]: r for r in report}
    assert by_code["RM100"]["current_stock"] == 100
    assert by_code["EMPTY1"]["current_stock"] == 0
    assert by_code["EMPTY1"]["item_type"] == "FG"
