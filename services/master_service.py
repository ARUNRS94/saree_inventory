"""Master-data services for suppliers, vendors, and sarees."""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database.models.entities import Saree, Supplier, Vendor


class MasterDataService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_supplier(self, supplier_name: str, **values: object) -> Supplier:
        if not supplier_name.strip():
            raise ValueError("Supplier name is required.")
        supplier = Supplier(supplier_name=supplier_name.strip(), **values)
        self.session.add(supplier)
        return supplier

    def search_suppliers(self, text: str = "") -> list[Supplier]:
        stmt = select(Supplier).where(Supplier.is_active.is_(True))
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
            raise ValueError("Saree code and name are required.")
        saree = Saree(saree_code=saree_code.strip().upper(), saree_name=saree_name.strip(), **values)
        self.session.add(saree)
        return saree

    def search_sarees(self, text: str = "") -> list[Saree]:
        stmt = select(Saree)
        if text:
            like = f"%{text}%"
            stmt = stmt.where(or_(Saree.saree_code.ilike(like), Saree.saree_name.ilike(like), Saree.design_name.ilike(like)))
        return list(self.session.scalars(stmt.order_by(Saree.saree_code)))
