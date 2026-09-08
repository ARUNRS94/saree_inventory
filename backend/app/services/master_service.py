from __future__ import annotations

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.saree import Saree
from app.models.supplier import Supplier
from app.models.vendor import Vendor
from app.models.vendor_process_type import VendorProcessType

CONTACT_TYPES = ["RM vendor", "Sub vendor", "Customer"]
ITEM_TYPES = ["RM", "Sub process", "FG"]

# Whitelisted sort columns, keyed by the value the client sends.
SAREE_SORTS = {
    "saree_code": Saree.saree_code, "saree_name": Saree.saree_name,
    "category": Saree.category, "fabric": Saree.fabric,
    "design_name": Saree.design_name, "color": Saree.color,
    "created_date": Saree.created_date,
}
SUPPLIER_SORTS = {
    "supplier_name": Supplier.supplier_name, "contact_person": Supplier.contact_person,
    "phone": Supplier.phone, "gst_no": Supplier.gst_no,
    "contact_type": Supplier.contact_type, "created_date": Supplier.created_date,
}
VENDOR_SORTS = {
    "vendor_name": Vendor.vendor_name, "process_type": Vendor.process_type,
    "contact_person": Vendor.contact_person, "phone": Vendor.phone,
    "gst_no": Vendor.gst_no, "created_date": Vendor.created_date,
}
PROCESS_TYPE_SORTS = {
    "process_type": VendorProcessType.process_type,
    "created_date": VendorProcessType.created_date,
}


def apply_sort(stmt, allowed: dict, sort_by: str | None, sort_dir: str | None, default):
    """Order by a whitelisted column; unknown names fall back to the default."""
    column = allowed.get(sort_by or "", default)
    return stmt.order_by(column.desc() if (sort_dir or "").lower() == "desc" else column.asc())


class MasterService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Contacts ---
    async def create_contact(self, name: str, contact_type: str, **values: object) -> Supplier:
        if not name.strip():
            raise ValueError("Contact name is required.")
        if contact_type not in CONTACT_TYPES:
            raise ValueError("Select a valid contact type.")
        contact = Supplier(supplier_name=name.strip(), contact_type=contact_type, **values)
        self.session.add(contact)
        await self.session.flush()
        return contact

    async def update_contact(self, supplier_id: int, **values: object) -> Supplier:
        contact = await self.session.get(Supplier, supplier_id)
        if contact is None:
            raise ValueError("Contact not found.")
        for key, val in values.items():
            if val is not None:
                setattr(contact, key, val)
        await self.session.flush()
        return contact

    async def search_contacts(self, text: str = "", contact_type: str | None = None,
                              page: int = 1, page_size: int = 50,
                              sort_by: str | None = None, sort_dir: str | None = None) -> tuple[list[Supplier], int]:
        stmt = select(Supplier).where(Supplier.is_active.is_(True))
        count_stmt = select(func.count()).select_from(Supplier).where(Supplier.is_active.is_(True))
        if contact_type:
            stmt = stmt.where(Supplier.contact_type == contact_type)
            count_stmt = count_stmt.where(Supplier.contact_type == contact_type)
        if text:
            like = f"%{text}%"
            text_filter = or_(
                Supplier.supplier_name.ilike(like),
                Supplier.contact_person.ilike(like),
                Supplier.phone.ilike(like),
                Supplier.gst_no.ilike(like),
            )
            stmt = stmt.where(text_filter)
            count_stmt = count_stmt.where(text_filter)
        total = await self.session.scalar(count_stmt) or 0
        stmt = apply_sort(stmt, SUPPLIER_SORTS, sort_by, sort_dir, Supplier.supplier_name)
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    # --- Vendors ---
    async def create_vendor(self, vendor_name: str, process_type: str, **values: object) -> Vendor:
        if not vendor_name.strip() or not process_type.strip():
            raise ValueError("Vendor name and process type are required.")
        vendor = Vendor(vendor_name=vendor_name.strip(), process_type=process_type.strip(), **values)
        self.session.add(vendor)
        await self.session.flush()
        return vendor

    async def update_vendor(self, vendor_id: int, **values: object) -> Vendor:
        vendor = await self.session.get(Vendor, vendor_id)
        if vendor is None:
            raise ValueError("Vendor not found.")
        for key, val in values.items():
            if val is not None:
                setattr(vendor, key, val)
        await self.session.flush()
        return vendor

    async def search_vendors(self, text: str = "", process_type: str | None = None,
                             page: int = 1, page_size: int = 50,
                             sort_by: str | None = None, sort_dir: str | None = None) -> tuple[list[Vendor], int]:
        stmt = select(Vendor).where(Vendor.is_active.is_(True))
        count_stmt = select(func.count()).select_from(Vendor).where(Vendor.is_active.is_(True))
        if process_type:
            stmt = stmt.where(Vendor.process_type == process_type)
            count_stmt = count_stmt.where(Vendor.process_type == process_type)
        if text:
            like = f"%{text}%"
            text_filter = or_(
                Vendor.vendor_name.ilike(like),
                Vendor.contact_person.ilike(like),
                Vendor.phone.ilike(like),
            )
            stmt = stmt.where(text_filter)
            count_stmt = count_stmt.where(text_filter)
        total = await self.session.scalar(count_stmt) or 0
        stmt = apply_sort(stmt, VENDOR_SORTS, sort_by, sort_dir, Vendor.vendor_name)
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    # --- Sarees ---
    async def create_saree(self, saree_code: str, saree_name: str, **values: object) -> Saree:
        if not saree_code.strip() or not saree_name.strip():
            raise ValueError("Item code and name are required.")
        item_type = values.get("fabric") or "FG"
        if item_type not in ITEM_TYPES:
            raise ValueError("Select a valid item type.")
        saree = Saree(saree_code=saree_code.strip().upper(), saree_name=saree_name.strip(), **values)
        self.session.add(saree)
        await self.session.flush()
        return saree

    async def update_saree(self, saree_id: int, **values: object) -> Saree:
        saree = await self.session.get(Saree, saree_id)
        if saree is None:
            raise ValueError("Item not found.")
        for key, val in values.items():
            if val is not None:
                if key == "saree_code":
                    val = str(val).strip().upper()
                setattr(saree, key, val)
        await self.session.flush()
        return saree

    async def search_sarees(self, text: str = "", item_type: str | None = None,
                            page: int = 1, page_size: int = 50,
                            sort_by: str | None = None, sort_dir: str | None = None) -> tuple[list[Saree], int]:
        stmt = select(Saree)
        count_stmt = select(func.count()).select_from(Saree)
        if item_type:
            stmt = stmt.where(Saree.fabric == item_type)
            count_stmt = count_stmt.where(Saree.fabric == item_type)
        if text:
            like = f"%{text}%"
            text_filter = or_(
                Saree.saree_code.ilike(like), Saree.saree_name.ilike(like),
                Saree.design_name.ilike(like), Saree.color.ilike(like),
                Saree.category.ilike(like), Saree.fabric.ilike(like),
            )
            stmt = stmt.where(text_filter)
            count_stmt = count_stmt.where(text_filter)
        total = await self.session.scalar(count_stmt) or 0
        stmt = apply_sort(stmt, SAREE_SORTS, sort_by, sort_dir, Saree.saree_code)
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    # --- Process Types ---
    async def list_process_types(self, sort_by: str | None = None,
                                 sort_dir: str | None = None) -> list[VendorProcessType]:
        stmt = select(VendorProcessType).where(VendorProcessType.is_active.is_(True))
        stmt = apply_sort(stmt, PROCESS_TYPE_SORTS, sort_by, sort_dir, VendorProcessType.process_type)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_process_type(self, process_type: str) -> VendorProcessType:
        if not process_type.strip():
            raise ValueError("Process type is required.")
        existing = await self.session.scalar(select(VendorProcessType).where(VendorProcessType.process_type == process_type.strip()))
        if existing:
            raise ValueError("Process type already exists.")
        pt = VendorProcessType(process_type=process_type.strip())
        self.session.add(pt)
        await self.session.flush()
        return pt

    async def update_process_type(self, process_type_id: int, **values: object) -> VendorProcessType:
        pt = await self.session.get(VendorProcessType, process_type_id)
        if pt is None:
            raise ValueError("Process type not found.")
        new_name = values.get("process_type")
        if new_name:
            dup = await self.session.scalar(
                select(VendorProcessType).where(
                    VendorProcessType.process_type == str(new_name).strip(),
                    VendorProcessType.process_type_id != process_type_id,
                )
            )
            if dup:
                raise ValueError("Process type already exists.")
            old_name = pt.process_type
            pt.process_type = str(new_name).strip()
            result = await self.session.execute(select(Vendor).where(Vendor.process_type == old_name))
            for vendor in result.scalars():
                vendor.process_type = pt.process_type
        if "is_active" in values and values["is_active"] is not None:
            pt.is_active = bool(values["is_active"])
        await self.session.flush()
        return pt
