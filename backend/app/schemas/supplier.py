from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SupplierCreate(BaseModel):
    supplier_name: str = Field(min_length=1, max_length=200)
    contact_person: str | None = None
    phone: str | None = None
    gst_no: str | None = None
    address: str | None = None
    contact_type: str = "RM vendor"


class SupplierUpdate(BaseModel):
    supplier_name: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    gst_no: str | None = None
    address: str | None = None
    contact_type: str | None = None
    is_active: bool | None = None


class SupplierResponse(BaseModel):
    supplier_id: int
    supplier_name: str
    contact_person: str | None
    phone: str | None
    gst_no: str | None
    address: str | None
    contact_type: str
    is_active: bool
    created_date: datetime | None

    model_config = {"from_attributes": True}


class SupplierListResponse(BaseModel):
    items: list[SupplierResponse]
    total: int
    page: int
    page_size: int
