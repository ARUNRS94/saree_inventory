from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item
from app.models.contact import Contact
from app.models.vendor import Vendor
from app.models.vendor_process_type import VendorProcessType
from app.services.master_service import (
    CONTACT_TYPES, ITEM_TYPE_LABELS, MasterService, item_type_label,
    normalise_contact_type, normalise_item_type,
)

MAX_ROWS = 5000
EXPORT_LIMIT = 100_000


@dataclass
class EntitySpec:
    """CSV shape for one master. Column names follow the original desktop app."""

    columns: list[str]
    field_map: dict[str, str]
    required: list[str]
    key: str
    sample: list[str]
    # Older/alternate headers accepted on import, mapped onto the canonical ones.
    aliases: dict[str, str] = field(default_factory=dict)

    def canonical(self, header: str) -> str:
        header = header.strip().lower()
        return self.aliases.get(header, header)


ENTITY_SPECS: dict[str, EntitySpec] = {
    "items": EntitySpec(
        columns=["code", "name", "type", "remarks", "color"],
        field_map={
            "code": "item_code", "name": "item_name", "type": "item_type",
            "remarks": "remarks", "color": "color",
        },
        required=["code", "name"],
        key="code",
        sample=["RM001", "Cotton Grey Fabric", "Raw Material", "Plain weave", "White"],
        aliases={
            "item_code": "code", "item_name": "name", "item_type": "type",
            "saree_code": "code", "saree_name": "name", "fabric": "type", "design_name": "remarks",
        },
    ),
    "contacts": EntitySpec(
        columns=["name", "type", "contact_person", "phone", "gst_no", "address"],
        field_map={
            "name": "contact_name", "type": "contact_type", "contact_person": "contact_person",
            "phone": "phone", "gst_no": "gst_no", "address": "address",
        },
        required=["name", "type"],
        key="name",
        sample=["Acme Textiles", "Raw Material Vendor", "Ravi", "9876543210", "29ABCDE1234F1Z5", "Surat"],
        aliases={"contact_name": "name", "contact_type": "type", "supplier_name": "name"},
    ),
    "vendors": EntitySpec(
        columns=["name", "process_type", "contact_person", "phone", "gst_no", "address"],
        field_map={
            "name": "vendor_name", "process_type": "process_type", "contact_person": "contact_person",
            "phone": "phone", "gst_no": "gst_no", "address": "address",
        },
        required=["name", "process_type"],
        key="name",
        sample=["Sri Dyeing Works", "Dyeing", "Kumar", "9876543210", "29ABCDE1234F1Z5", "Erode"],
        aliases={"vendor_name": "name"},
    ),
    "process-types": EntitySpec(
        columns=["process_type"],
        field_map={"process_type": "process_type"},
        required=["process_type"],
        key="process_type",
        sample=["Dyeing"],
    ),
}


@dataclass
class ImportResult:
    imported: int = 0
    skipped: int = 0
    errors: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"imported": self.imported, "skipped": self.skipped, "errors": self.errors}


def build_template(entity: str) -> str:
    spec = ENTITY_SPECS[entity]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(spec.columns)
    writer.writerow(spec.sample)
    return buffer.getvalue()


async def export_csv(
    session: AsyncSession,
    entity: str,
    search: str = "",
    filter_value: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> str:
    """Export every row matching the caller's current filters, ignoring pagination."""
    spec = ENTITY_SPECS[entity]
    master = MasterService(session)

    if entity == "items":
        rows, _ = await master.search_items(search, filter_value, 1, EXPORT_LIMIT, sort_by, sort_dir)
    elif entity == "contacts":
        rows, _ = await master.search_contacts(search, filter_value, 1, EXPORT_LIMIT, sort_by, sort_dir)
    elif entity == "vendors":
        rows, _ = await master.search_vendors(search, filter_value, 1, EXPORT_LIMIT, sort_by, sort_dir)
    else:
        rows = await master.list_process_types(sort_by, sort_dir)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(spec.columns)
    for row in rows:
        values = []
        for column in spec.columns:
            value = getattr(row, spec.field_map[column], None)
            if column == "type" and entity == "items":
                value = item_type_label(value)
            values.append("" if value is None else value)
        writer.writerow(values)
    return buffer.getvalue()


class ImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.master = MasterService(session)

    async def _existing_keys(self, entity: str) -> set[str]:
        column = {
            "items": Item.item_code,
            "contacts": Contact.contact_name,
            "vendors": Vendor.vendor_name,
            "process-types": VendorProcessType.process_type,
        }[entity]
        result = await self.session.execute(select(func.lower(column)))
        return {value for value in result.scalars().all() if value}

    async def _create(self, entity: str, row: dict[str, str]) -> None:
        if entity == "items":
            raw_type = row.get("type")
            item_type = normalise_item_type(raw_type) if raw_type else "FG"
            if item_type is None:
                raise ValueError(f"type must be one of: {', '.join(ITEM_TYPE_LABELS.values())}")
            await self.master.create_item(
                row["code"], row["name"], item_type=item_type,
                remarks=row.get("remarks") or None, color=row.get("color") or None,
            )
        elif entity == "contacts":
            await self.master.create_contact(
                row["name"], row["type"],
                contact_person=row.get("contact_person") or None, phone=row.get("phone") or None,
                gst_no=row.get("gst_no") or None, address=row.get("address") or None,
            )
        elif entity == "vendors":
            await self.master.create_vendor(
                row["name"], row["process_type"],
                contact_person=row.get("contact_person") or None, phone=row.get("phone") or None,
                gst_no=row.get("gst_no") or None, address=row.get("address") or None,
            )
        else:
            await self.master.create_process_type(row["process_type"])

    async def import_csv(self, entity: str, content: bytes) -> ImportResult:
        if entity not in ENTITY_SPECS:
            raise ValueError(f"Unknown import type: {entity}")
        spec = ENTITY_SPECS[entity]

        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError("File must be UTF-8 encoded CSV.")

        reader = csv.DictReader(io.StringIO(text))
        headers = {spec.canonical(h) for h in (reader.fieldnames or []) if h}
        missing = [c for c in spec.required if c not in headers]
        if missing:
            raise ValueError(f"Missing required column(s): {', '.join(missing)}")

        result = ImportResult()
        existing = await self._existing_keys(entity)
        seen_in_file: set[str] = set()

        for line_no, raw in enumerate(reader, start=2):
            if result.imported + result.skipped + len(result.errors) >= MAX_ROWS:
                result.errors.append({"row": line_no, "value": "", "reason": f"Stopped at {MAX_ROWS} row limit."})
                break

            row = {spec.canonical(k): (v or "").strip() for k, v in raw.items() if k}
            if not any(row.values()):
                continue

            key_value = row.get(spec.key, "")
            if not key_value:
                result.errors.append({"row": line_no, "value": "", "reason": f"{spec.key} is required."})
                continue

            blank_required = [c for c in spec.required if not row.get(c)]
            if blank_required:
                result.errors.append({
                    "row": line_no, "value": key_value,
                    "reason": f"Missing value for: {', '.join(blank_required)}",
                })
                continue

            if entity == "contacts" and normalise_contact_type(row.get("type")) is None:
                result.errors.append({
                    "row": line_no, "value": key_value,
                    "reason": f"type must be one of: {', '.join(CONTACT_TYPES)}",
                })
                continue

            lookup = key_value.lower()
            if lookup in existing or lookup in seen_in_file:
                result.skipped += 1
                continue

            try:
                # Savepoint per row so one bad row cannot poison the transaction.
                async with self.session.begin_nested():
                    await self._create(entity, row)
            except ValueError as exc:
                result.errors.append({"row": line_no, "value": key_value, "reason": str(exc)})
                continue
            except Exception:
                result.errors.append({"row": line_no, "value": key_value, "reason": "Could not save this row."})
                continue

            seen_in_file.add(lookup)
            result.imported += 1

        return result
