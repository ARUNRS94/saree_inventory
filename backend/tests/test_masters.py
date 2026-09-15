"""Master data: items, contacts, vendors and process types."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.master_service import (
    CONTACT_TYPES, ITEM_TYPES, MasterService, item_type_label,
    normalise_contact_type, normalise_item_type,
)


# --- type normalisation ---

@pytest.mark.parametrize("raw,expected", [
    ("RM", "RM"),
    ("rm", "RM"),
    ("Raw Material", "RM"),
    ("raw material", "RM"),
    ("FG", "FG"),
    ("Finished Goods", "FG"),
    ("Sub process", "Sub process"),
    ("Sub Process", "Sub process"),
    ("  fg  ", "FG"),
    ("nonsense", None),
    ("", None),
    (None, None),
])
def test_normalise_item_type(raw, expected):
    assert normalise_item_type(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("RM vendor", "Raw Material Vendor"),
    ("raw material vendor", "Raw Material Vendor"),
    ("Sub vendor", "Sub vendor"),
    ("CUSTOMER", "Customer"),
    ("  customer ", "Customer"),
    ("supplier", None),
    (None, None),
])
def test_normalise_contact_type(raw, expected):
    assert normalise_contact_type(raw) == expected


def test_item_type_label():
    assert item_type_label("RM") == "Raw Material"
    assert item_type_label("Sub process") == "Sub Process"
    assert item_type_label("FG") == "Finished Goods"
    # Unknown codes pass through rather than becoming blank.
    assert item_type_label("XX") == "XX"
    assert item_type_label(None) == ""


def test_catalogues_are_closed_sets():
    assert ITEM_TYPES == ["RM", "Sub process", "FG"]
    assert CONTACT_TYPES == ["Raw Material Vendor", "Sub vendor", "Customer"]


# --- items ---

async def test_item_code_is_upper_cased_and_trimmed(masters: MasterService):
    item = await masters.create_item("  rm-01  ", "  Grey Fabric  ", item_type="RM")
    assert item.item_code == "RM-01"
    assert item.item_name == "Grey Fabric"


async def test_item_defaults_to_finished_goods(masters: MasterService):
    item = await masters.create_item("X1", "No type given")
    assert item.item_type == "FG"


@pytest.mark.parametrize("code,name", [("", "Name"), ("   ", "Name"), ("C1", ""), ("C1", "  ")])
async def test_item_requires_code_and_name(masters: MasterService, code, name):
    with pytest.raises(ValueError, match="required"):
        await masters.create_item(code, name, item_type="RM")


async def test_item_type_must_be_a_stored_code_not_a_label(masters: MasterService):
    """create_item takes the stored code; labels must be normalised by the caller."""
    with pytest.raises(ValueError, match="valid item type"):
        await masters.create_item("X2", "Bad", item_type="Raw Material")


async def test_update_item_ignores_none_and_uppercases_code(masters: MasterService, db: AsyncSession):
    item = await masters.create_item("A1", "Original", item_type="RM", color="Red")
    updated = await masters.update_item(item.item_id, item_code="b2", item_name=None, color="Blue")
    assert updated.item_code == "B2"
    assert updated.item_name == "Original"
    assert updated.color == "Blue"


async def test_update_missing_item(masters: MasterService):
    with pytest.raises(ValueError, match="Item not found"):
        await masters.update_item(9999, item_name="Nope")


async def test_search_items_by_text_and_type(masters: MasterService, db: AsyncSession):
    await masters.create_item("RM1", "Cotton Grey", item_type="RM", color="White")
    await masters.create_item("FG1", "Cotton Saree", item_type="FG", color="Red")
    await masters.create_item("SP1", "Dyed Cloth", item_type="Sub process")
    await db.flush()

    all_rows, total = await masters.search_items()
    assert total == 3

    cotton, count = await masters.search_items("Cotton")
    assert count == 2

    rm_only, rm_count = await masters.search_items("", "RM")
    assert rm_count == 1
    assert rm_only[0].item_code == "RM1"

    by_colour, colour_count = await masters.search_items("Red")
    assert colour_count == 1


async def test_search_items_sorting_and_pagination(masters: MasterService, db: AsyncSession):
    for code in ["C", "A", "B"]:
        await masters.create_item(code, f"Item {code}", item_type="RM")
    await db.flush()

    asc, _ = await masters.search_items(sort_by="item_code", sort_dir="asc")
    assert [i.item_code for i in asc] == ["A", "B", "C"]

    desc, _ = await masters.search_items(sort_by="item_code", sort_dir="desc")
    assert [i.item_code for i in desc] == ["C", "B", "A"]

    # An unknown sort column must fall back to the default rather than raise.
    fallback, _ = await masters.search_items(sort_by="drop table", sort_dir="asc")
    assert [i.item_code for i in fallback] == ["A", "B", "C"]

    page1, total = await masters.search_items(page=1, page_size=2, sort_by="item_code")
    page2, _ = await masters.search_items(page=2, page_size=2, sort_by="item_code")
    assert total == 3
    assert [i.item_code for i in page1] == ["A", "B"]
    assert [i.item_code for i in page2] == ["C"]


# --- contacts ---

async def test_contact_requires_name_and_valid_type(masters: MasterService):
    with pytest.raises(ValueError, match="Contact name is required"):
        await masters.create_contact("   ", "Customer")
    with pytest.raises(ValueError, match="valid contact type"):
        await masters.create_contact("Someone", "Distributor")


async def test_search_contacts_filters_by_type(masters: MasterService, db: AsyncSession):
    await masters.create_contact("Alpha Mills", "Raw Material Vendor", phone="111")
    await masters.create_contact("Beta Dyers", "Sub vendor", phone="222")
    await masters.create_contact("Gamma Retail", "Customer", phone="333")
    await db.flush()

    customers, count = await masters.search_contacts("", "Customer")
    assert count == 1
    assert customers[0].contact_name == "Gamma Retail"

    by_phone, phone_count = await masters.search_contacts("222")
    assert phone_count == 1


async def test_inactive_contacts_are_excluded(masters: MasterService, db: AsyncSession):
    contact = await masters.create_contact("Retired Vendor", "Raw Material Vendor")
    await db.flush()
    _, before = await masters.search_contacts()
    await masters.update_contact(contact.contact_id, is_active=False)
    await db.flush()
    _, after = await masters.search_contacts()
    assert after == before - 1


# --- vendors and process types ---

async def test_vendor_requires_name_and_process_type(masters: MasterService):
    with pytest.raises(ValueError, match="required"):
        await masters.create_vendor("", "Dyeing")
    with pytest.raises(ValueError, match="required"):
        await masters.create_vendor("V", "   ")


async def test_duplicate_process_type_rejected(masters: MasterService):
    await masters.create_process_type("Dyeing")
    with pytest.raises(ValueError, match="already exists"):
        await masters.create_process_type("Dyeing")


async def test_blank_process_type_rejected(masters: MasterService):
    with pytest.raises(ValueError, match="required"):
        await masters.create_process_type("   ")


async def test_renaming_a_process_type_cascades_to_vendors(masters: MasterService, db: AsyncSession):
    pt = await masters.create_process_type("Dyeing")
    vendor = await masters.create_vendor("Sri Dyeing", "Dyeing")
    await db.flush()

    await masters.update_process_type(pt.process_type_id, process_type="Dyeing & Finishing")
    await db.refresh(vendor)
    assert vendor.process_type == "Dyeing & Finishing"


async def test_process_type_rename_clash_rejected(masters: MasterService, db: AsyncSession):
    first = await masters.create_process_type("Dyeing")
    await masters.create_process_type("Printing")
    await db.flush()
    with pytest.raises(ValueError, match="already exists"):
        await masters.update_process_type(first.process_type_id, process_type="Printing")


async def test_deactivated_process_type_is_hidden(masters: MasterService, db: AsyncSession):
    pt = await masters.create_process_type("Temporary")
    await db.flush()
    assert len(await masters.list_process_types()) == 1
    await masters.update_process_type(pt.process_type_id, is_active=False)
    await db.flush()
    assert await masters.list_process_types() == []
