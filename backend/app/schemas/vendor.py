from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class VendorCreate(BaseModel):
    vendor_name: str = Field(min_length=1, max_length=200)
    process_type: str = Field(min_length=1, max_length=100)
    contact_person: str | None = None
    phone: str | None = None
    gst_no: str | None = None
    address: str | None = None


class VendorUpdate(BaseModel):
    vendor_name: str | None = None
    process_type: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    gst_no: str | None = None
    address: str | None = None
    is_active: bool | None = None


class VendorResponse(BaseModel):
    vendor_id: int
    vendor_name: str
    process_type: str
    contact_person: str | None
    phone: str | None
    gst_no: str | None
    address: str | None
    is_active: bool
    created_date: datetime | None

    model_config = {"from_attributes": True}


class VendorListResponse(BaseModel):
    items: list[VendorResponse]
    total: int
    page: int
    page_size: int


class VendorProcessTypeCreate(BaseModel):
    process_type: str = Field(min_length=1, max_length=100)


class VendorProcessTypeUpdate(BaseModel):
    process_type: str | None = None
    is_active: bool | None = None


class VendorProcessTypeResponse(BaseModel):
    process_type_id: int
    process_type: str
    is_active: bool
    created_date: datetime | None

    model_config = {"from_attributes": True}
