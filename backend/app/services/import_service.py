from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.saree import Saree
from app.models.supplier import Supplier
from app.models.vendor import Vendor
from app.models.vendor_process_type import VendorProcessType
from app.services.master_service import CONTACT_TYPES, ITEM_TYPES, MasterService

MAX_ROWS = 5000
EXPORT_LIMIT = 100_000


@dataclass
class EntitySpec:
    columns: list[str]
    required: list[str]
    key: str
    sample: list[str]


ENTITY_SPECS: dict[str, EntitySpec] = {
    "sarees": EntitySpec(
        columns=["saree_code", "saree_name", "fabric", "category", "design_name", "color", "unit"],
        required=["saree_code", "saree_name"],
        key="saree_code",
        sample=["RM001", "Cotton Grey Fabric", "RM", "Cotton", "Plain", "White", "PCS"],
    ),
    "suppliers": EntitySpec(
        columns=["supplier_name", "contact_type", "contact_person", "phone", "gst_no", "address"],
        required=["supplier_name", "contact_type"],
        key="supplier_name",
        sample=["Acme Textiles", "RM vendor", "Ravi", "9876543210", "29ABCDE1234F1Z5", "Surat"],
    ),
    "vendors": EntitySpec(
        columns=["vendor_name", "process_type", "contact_person", "phone", "gst_no", "address"],
        required=["vendor_name", "process_type"],
        key="vendor_name",
        sample=["Sri Dyeing Works", "Dyeing", "Kumar", "9876543210", "29ABCDE1234F1Z5", "Erode"],
    ),
    "process-types": EntitySpec(
        columns=["process_type"],
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

    if entity == "sarees":
        rows, _ = await master.search_sarees(search, filter_value, 1, EXPORT_LIMIT, sort_by, sort_dir)
    elif entity == "suppliers":
        rows, _ = await master.search_contacts(search, filter_value, 1, EXPORT_LIMIT, sort_by, sort_dir)
    elif entity == "vendors":
        rows, _ = await master.search_vendors(search, filter_value, 1, EXPORT_LIMIT, sort_by, sort_dir)
    else:
        rows = await master.list_process_types(sort_by, sort_dir)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(spec.columns)
    for row in rows:
        writer.writerow([getattr(row, column, "") if getattr(row, column, None) is not None else "" for column in spec.columns])
    return buffer.getvalue()


class ImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.master = MasterService(session)

    async def _existing_keys(self, entity: str) -> set[str]:
        column = {
            "sarees": Saree.saree_code,
            "suppliers": Supplier.supplier_name,
            "vendors": Vendor.vendor_name,
            "process-types": VendorProcessType.process_type,
        }[entity]
        result = await self.session.execute(select(func.lower(column)))
        return {value for value in result.scalars().all() if value}

    async def _create(self, entity: str, row: dict[str, str]) -> None:
        if entity == "sarees":
            item_type = row.get("fabric") or "FG"
            if item_type not in ITEM_TYPES:
                raise ValueError(f"fabric must be one of: {', '.join(ITEM_TYPES)}")
            await self.master.create_saree(
                row["saree_code"], row["saree_name"], fabric=item_type,
                category=row.get("category") or None, design_name=row.get("design_name") or None,
                color=row.get("color") or None, unit=row.get("unit") or "PCS",
            )
        elif entity == "suppliers":
            await self.master.create_contact(
                row["supplier_name"], row["contact_type"],
                contact_person=row.get("contact_person") or None, phone=row.get("phone") or None,
                gst_no=row.get("gst_no") or None, address=row.get("address") or None,
            )
        elif entity == "vendors":
            await self.master.create_vendor(
                row["vendor_name"], row["process_type"],
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
        headers = {(h or "").strip().lower() for h in (reader.fieldnames or [])}
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

            row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items() if k}
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

            if entity == "suppliers" and row.get("contact_type") not in CONTACT_TYPES:
                result.errors.append({
                    "row": line_no, "value": key_value,
                    "reason": f"contact_type must be one of: {', '.join(CONTACT_TYPES)}",
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
