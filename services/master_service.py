"""Master-data services for contacts and inventory items."""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database.models.entities import Saree, Supplier, Vendor

CONTACT_TYPES = ["RM vendor", "Sub vendor", "Customer"]
ITEM_TYPES = ["RM", "Sub process", "FG"]


class MasterDataService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_supplier(self, supplier_name: str, **values: object) -> Supplier:
        return self.create_contact(supplier_name, values.pop("contact_type", "RM vendor"), **values)

    def create_contact(self, contact_name: str, contact_type: str, **values: object) -> Supplier:
        if not contact_name.strip():
            raise ValueError("Contact name is required.")
        if contact_type not in CONTACT_TYPES:
            raise ValueError("Select a valid contact type.")
        contact = Supplier(supplier_name=contact_name.strip(), contact_type=contact_type, **values)
        self.session.add(contact)
        return contact

    def search_suppliers(self, text: str = "", contact_type: str | None = None) -> list[Supplier]:
        return self.search_contacts(text=text, contact_type=contact_type)

    def search_contacts(self, text: str = "", contact_type: str | None = None) -> list[Supplier]:
        stmt = select(Supplier).where(Supplier.is_active.is_(True))
        if contact_type:
            stmt = stmt.where(Supplier.contact_type == contact_type)
        if text:
            stmt = stmt.where(Supplier.supplier_name.ilike(f"%{text}%"))
        return list(self.session.scalars(stmt.order_by(Supplier.supplier_name)))

    def create_vendor(self, vendor_name: str, process_type: str, **values: object) -> Vendor:
        if not vendor_name.strip() or not process_type.strip():
            raise ValueError("Vendor name and process type are required.")
        vendor = Vendor(vendor_name=vendor_name.strip(), process_type=process_type.strip(), **values)
        self.session.add(vendor)
        return vendor

    def create_saree(self, saree_code: str, saree_name: str, **values: object) -> Saree:
        if not saree_code.strip() or not saree_name.strip():
            raise ValueError("Item code and name are required.")
        item_type = values.get("fabric") or "FG"
        if item_type not in ITEM_TYPES:
            raise ValueError("Select a valid item type.")
        saree = Saree(saree_code=saree_code.strip().upper(), saree_name=saree_name.strip(), **values)
        self.session.add(saree)
        return saree

    def search_sarees(self, text: str = "", item_type: str | None = None) -> list[Saree]:
        stmt = select(Saree)
        if item_type:
            stmt = stmt.where(Saree.fabric == item_type)
        if text:
            like = f"%{text}%"
            stmt = stmt.where(or_(Saree.saree_code.ilike(like), Saree.saree_name.ilike(like), Saree.design_name.ilike(like)))
        return list(self.session.scalars(stmt.order_by(Saree.saree_code)))
