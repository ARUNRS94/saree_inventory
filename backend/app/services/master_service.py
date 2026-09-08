from __future__ import annotations

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item
from app.models.contact import Contact
from app.models.vendor import Vendor
from app.models.vendor_process_type import VendorProcessType

RM_VENDOR = "Raw Material Vendor"
SUB_VENDOR = "Sub vendor"
CUSTOMER = "Customer"

CONTACT_TYPES = [RM_VENDOR, SUB_VENDOR, CUSTOMER]

# Older data and CSV files use the previous spelling.
CONTACT_TYPE_ALIASES = {
    "rm vendor": RM_VENDOR,
    "raw material vendor": RM_VENDOR,
    "sub vendor": SUB_VENDOR,
    "customer": CUSTOMER,
}

ITEM_TYPES = ["RM", "Sub process", "FG"]

RAW_MATERIAL = "RM"
SUB_PROCESS = "Sub process"
FINISHED_GOODS = "FG"

# Codes are what we store; labels are what users see and what reports print.
ITEM_TYPE_LABELS = {"RM": "Raw Material", "Sub process": "Sub Process", "FG": "Finished Goods"}
ITEM_TYPE_ALIASES = {label.lower(): code for code, label in ITEM_TYPE_LABELS.items()}
ITEM_TYPE_ALIASES.update({code.lower(): code for code in ITEM_TYPES})


def item_type_label(code: str | None) -> str:
    return ITEM_TYPE_LABELS.get(code or "", code or "")


def normalise_item_type(value: str | None) -> str | None:
    """Map 'Raw Material' or 'rm' onto the stored 'RM' code."""
    if not value:
        return None
    return ITEM_TYPE_ALIASES.get(value.strip().lower())


def normalise_contact_type(value: str | None) -> str | None:
    if not value:
        return None
    return CONTACT_TYPE_ALIASES.get(value.strip().lower())


# Whitelisted sort columns, keyed by the value the client sends.
ITEM_SORTS = {
    "item_code": Item.item_code, "item_name": Item.item_name,
    "item_type": Item.item_type, "remarks": Item.remarks,
    "color": Item.color, "created_date": Item.created_date,
}
CONTACT_SORTS = {
    "contact_name": Contact.contact_name, "contact_person": Contact.contact_person,
    "phone": Contact.phone, "gst_no": Contact.gst_no,
    "contact_type": Contact.contact_type, "created_date": Contact.created_date,
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
    async def create_contact(self, name: str, contact_type: str, **values: object) -> Contact:
        if not name.strip():
            raise ValueError("Contact name is required.")
        resolved = normalise_contact_type(contact_type)
        if resolved is None:
            raise ValueError("Select a valid contact type.")
        contact = Contact(contact_name=name.strip(), contact_type=resolved, **values)
        self.session.add(contact)
        await self.session.flush()
        return contact

    async def update_contact(self, contact_id: int, **values: object) -> Contact:
        contact = await self.session.get(Contact, contact_id)
        if contact is None:
            raise ValueError("Contact not found.")
        for key, val in values.items():
            if val is not None:
                setattr(contact, key, val)
        await self.session.flush()
        return contact

    async def search_contacts(self, text: str = "", contact_type: str | None = None,
                              page: int = 1, page_size: int = 50,
                              sort_by: str | None = None, sort_dir: str | None = None) -> tuple[list[Contact], int]:
        stmt = select(Contact).where(Contact.is_active.is_(True))
        count_stmt = select(func.count()).select_from(Contact).where(Contact.is_active.is_(True))
        if contact_type:
            stmt = stmt.where(Contact.contact_type == contact_type)
            count_stmt = count_stmt.where(Contact.contact_type == contact_type)
        if text:
            like = f"%{text}%"
            text_filter = or_(
                Contact.contact_name.ilike(like),
                Contact.contact_person.ilike(like),
                Contact.phone.ilike(like),
                Contact.gst_no.ilike(like),
            )
            stmt = stmt.where(text_filter)
            count_stmt = count_stmt.where(text_filter)
        total = await self.session.scalar(count_stmt) or 0
        stmt = apply_sort(stmt, CONTACT_SORTS, sort_by, sort_dir, Contact.contact_name)
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

    # --- Items ---
    async def create_item(self, item_code: str, item_name: str, **values: object) -> Item:
        if not item_code.strip() or not item_name.strip():
            raise ValueError("Item code and name are required.")
        item_type = values.get("item_type") or "FG"
        if item_type not in ITEM_TYPES:
            raise ValueError("Select a valid item type.")
        item = Item(item_code=item_code.strip().upper(), item_name=item_name.strip(), **values)
        self.session.add(item)
        await self.session.flush()
        return item

    async def update_item(self, item_id: int, **values: object) -> Item:
        item = await self.session.get(Item, item_id)
        if item is None:
            raise ValueError("Item not found.")
        for key, val in values.items():
            if val is not None:
                if key == "item_code":
                    val = str(val).strip().upper()
                setattr(item, key, val)
        await self.session.flush()
        return item

    async def search_items(self, text: str = "", item_type: str | None = None,
                            page: int = 1, page_size: int = 50,
                            sort_by: str | None = None, sort_dir: str | None = None) -> tuple[list[Item], int]:
        stmt = select(Item)
        count_stmt = select(func.count()).select_from(Item)
        if item_type:
            stmt = stmt.where(Item.item_type == item_type)
            count_stmt = count_stmt.where(Item.item_type == item_type)
        if text:
            like = f"%{text}%"
            text_filter = or_(
                Item.item_code.ilike(like), Item.item_name.ilike(like),
                Item.remarks.ilike(like), Item.color.ilike(like),
                Item.item_type.ilike(like),
            )
            stmt = stmt.where(text_filter)
            count_stmt = count_stmt.where(text_filter)
        total = await self.session.scalar(count_stmt) or 0
        stmt = apply_sort(stmt, ITEM_SORTS, sort_by, sort_dir, Item.item_code)
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
