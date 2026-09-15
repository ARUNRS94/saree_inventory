"""CSV import and export: templates, aliases, duplicates and per-row error handling."""
from __future__ import annotations

import csv
import io

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.import_service import (
    ENTITY_SPECS, ImportService, build_template, export_csv,
)
from app.services.master_service import MasterService


def _csv(rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    return buffer.getvalue().encode("utf-8")


# --- templates ---

@pytest.mark.parametrize("entity", sorted(ENTITY_SPECS))
def test_every_entity_has_a_usable_template(entity):
    rows = list(csv.reader(io.StringIO(build_template(entity))))
    header, sample = rows[0], rows[1]
    spec = ENTITY_SPECS[entity]

    assert header == spec.columns
    assert len(sample) == len(spec.columns)
    # Required columns must be filled in the sample, or the example itself would fail to import.
    for column in spec.required:
        assert sample[header.index(column)]


@pytest.mark.parametrize("entity", sorted(ENTITY_SPECS))
def test_template_required_columns_are_real_columns(entity):
    spec = ENTITY_SPECS[entity]
    assert set(spec.required) <= set(spec.columns)
    assert spec.key in spec.columns
    assert set(spec.field_map) == set(spec.columns)


def test_item_template_uses_the_human_readable_type():
    rows = list(csv.reader(io.StringIO(build_template("items"))))
    assert rows[1][rows[0].index("type")] == "Raw Material"


# --- importing ---

async def test_import_items_happy_path(db: AsyncSession):
    content = _csv([
        ["code", "name", "type", "remarks", "color"],
        ["RM001", "Grey Fabric", "Raw Material", "Plain", "White"],
        ["FG001", "Saree", "Finished Goods", "", "Red"],
    ])
    result = await ImportService(db).import_csv("items", content)
    assert (result.imported, result.skipped, result.errors) == (2, 0, [])

    rows, total = await MasterService(db).search_items()
    assert total == 2
    assert {r.item_code for r in rows} == {"RM001", "FG001"}
    assert {r.item_type for r in rows} == {"RM", "FG"}


async def test_import_accepts_the_generated_template(db: AsyncSession):
    result = await ImportService(db).import_csv("items", build_template("items").encode("utf-8"))
    assert result.imported == 1
    assert result.errors == []


async def test_import_accepts_legacy_headers(db: AsyncSession):
    """Files exported by the old desktop app still import."""
    content = _csv([
        ["saree_code", "saree_name", "fabric", "design_name"],
        ["OLD1", "Legacy Item", "RM", "From the old app"],
    ])
    result = await ImportService(db).import_csv("items", content)
    assert result.imported == 1
    rows, _ = await MasterService(db).search_items()
    assert rows[0].item_code == "OLD1"
    assert rows[0].remarks == "From the old app"


async def test_import_skips_rows_already_present(db: AsyncSession):
    master = MasterService(db)
    await master.create_item("RM001", "Existing", item_type="RM")
    await db.flush()

    content = _csv([
        ["code", "name", "type"],
        ["rm001", "Different name, same code", "Raw Material"],
        ["RM002", "Brand new", "Raw Material"],
    ])
    result = await ImportService(db).import_csv("items", content)
    assert result.imported == 1
    assert result.skipped == 1

    existing = next(r for r in (await master.search_items())[0] if r.item_code == "RM001")
    assert existing.item_name == "Existing", "an existing row must never be overwritten"


async def test_import_skips_duplicates_within_the_same_file(db: AsyncSession):
    content = _csv([
        ["code", "name", "type"],
        ["DUP1", "First", "Raw Material"],
        ["DUP1", "Second", "Raw Material"],
    ])
    result = await ImportService(db).import_csv("items", content)
    assert (result.imported, result.skipped) == (1, 1)


async def test_import_rejects_a_file_missing_required_columns(db: AsyncSession):
    content = _csv([["name", "type"], ["No code column", "Raw Material"]])
    with pytest.raises(ValueError, match="Missing required column"):
        await ImportService(db).import_csv("items", content)


async def test_import_rejects_unknown_entity(db: AsyncSession):
    with pytest.raises(ValueError, match="Unknown import type"):
        await ImportService(db).import_csv("widgets", _csv([["a"], ["b"]]))


async def test_import_rejects_non_utf8(db: AsyncSession):
    with pytest.raises(ValueError, match="UTF-8"):
        await ImportService(db).import_csv("items", b"\xff\xfe\x00code")


async def test_import_reports_bad_rows_without_losing_good_ones(db: AsyncSession):
    content = _csv([
        ["code", "name", "type"],
        ["GOOD1", "Fine", "Raw Material"],
        ["BAD1", "Bad type", "Nonsense"],
        ["", "Missing code", "Raw Material"],
        ["GOOD2", "Also fine", "Finished Goods"],
    ])
    result = await ImportService(db).import_csv("items", content)

    assert result.imported == 2
    assert len(result.errors) == 2
    assert {e["row"] for e in result.errors} == {3, 4}
    assert any("type must be one of" in e["reason"] for e in result.errors)
    assert any("required" in e["reason"] for e in result.errors)

    codes = {r.item_code for r in (await MasterService(db).search_items())[0]}
    assert codes == {"GOOD1", "GOOD2"}


async def test_import_ignores_completely_blank_rows(db: AsyncSession):
    content = _csv([
        ["code", "name", "type"],
        ["A1", "First", "Raw Material"],
        ["", "", ""],
        ["A2", "Second", "Raw Material"],
    ])
    result = await ImportService(db).import_csv("items", content)
    assert (result.imported, result.skipped, result.errors) == (2, 0, [])


async def test_import_contacts_validates_type(db: AsyncSession):
    content = _csv([
        ["name", "type", "phone"],
        ["Alpha Mills", "RM vendor", "111"],
        ["Beta Store", "Distributor", "222"],
    ])
    result = await ImportService(db).import_csv("contacts", content)
    assert result.imported == 1
    assert len(result.errors) == 1
    assert "type must be one of" in result.errors[0]["reason"]

    rows, _ = await MasterService(db).search_contacts()
    assert rows[0].contact_type == "Raw Material Vendor"


async def test_import_contacts_requires_type(db: AsyncSession):
    content = _csv([["name", "type"], ["No Type Co", ""]])
    result = await ImportService(db).import_csv("contacts", content)
    assert result.imported == 0
    assert "Missing value for: type" in result.errors[0]["reason"]


async def test_import_process_types_and_vendors(db: AsyncSession):
    pt_result = await ImportService(db).import_csv(
        "process-types", _csv([["process_type"], ["Dyeing"], ["Printing"], ["Dyeing"]]),
    )
    assert (pt_result.imported, pt_result.skipped) == (2, 1)

    vendor_result = await ImportService(db).import_csv(
        "vendors", _csv([["name", "process_type", "phone"], ["Sri Dyeing", "Dyeing", "999"]]),
    )
    assert vendor_result.imported == 1
    rows, _ = await MasterService(db).search_vendors()
    assert rows[0].vendor_name == "Sri Dyeing"


async def test_import_vendors_accepts_the_legacy_vendor_name_header(db: AsyncSession):
    result = await ImportService(db).import_csv(
        "vendors", _csv([["vendor_name", "process_type"], ["Legacy Vendor", "Dyeing"]]),
    )
    assert result.imported == 1


# --- exporting ---

async def test_export_round_trips_through_import(db: AsyncSession):
    master = MasterService(db)
    await master.create_item("RM001", "Grey Fabric", item_type="RM", color="White")
    await master.create_item("FG001", "Saree", item_type="FG")
    await db.flush()

    exported = await export_csv(db, "items")
    rows = list(csv.reader(io.StringIO(exported)))
    assert rows[0] == ENTITY_SPECS["items"].columns
    assert len(rows) == 3
    # Exports carry the label, and the importer understands it.
    assert "Raw Material" in exported

    fresh = ImportService(db)
    # Re-importing the same file changes nothing, because every key already exists.
    result = await fresh.import_csv("items", exported.encode("utf-8"))
    assert (result.imported, result.skipped) == (0, 2)


async def test_export_respects_search_and_filter(db: AsyncSession):
    master = MasterService(db)
    await master.create_item("RM001", "Grey Fabric", item_type="RM")
    await master.create_item("FG001", "Saree", item_type="FG")
    await db.flush()

    filtered = await export_csv(db, "items", filter_value="FG")
    rows = list(csv.reader(io.StringIO(filtered)))
    assert len(rows) == 2
    assert rows[1][0] == "FG001"

    searched = await export_csv(db, "items", search="Grey")
    assert len(list(csv.reader(io.StringIO(searched)))) == 2


async def test_export_respects_sorting(db: AsyncSession):
    master = MasterService(db)
    for code in ["B1", "A1", "C1"]:
        await master.create_item(code, code, item_type="RM")
    await db.flush()

    rows = list(csv.reader(io.StringIO(
        await export_csv(db, "items", sort_by="item_code", sort_dir="desc")
    )))
    assert [r[0] for r in rows[1:]] == ["C1", "B1", "A1"]


async def test_export_empty_table_still_has_a_header(db: AsyncSession):
    rows = list(csv.reader(io.StringIO(await export_csv(db, "contacts"))))
    assert rows == [ENTITY_SPECS["contacts"].columns]
