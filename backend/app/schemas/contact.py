from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ContactCreate(BaseModel):
    contact_name: str = Field(min_length=1, max_length=200)
    contact_person: str | None = None
    phone: str | None = None
    gst_no: str | None = None
    address: str | None = None
    contact_type: str = "Raw Material Vendor"


class ContactUpdate(BaseModel):
    contact_name: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    gst_no: str | None = None
    address: str | None = None
    contact_type: str | None = None
    is_active: bool | None = None


class ContactResponse(BaseModel):
    contact_id: int
    contact_name: str
    contact_person: str | None
    phone: str | None
    gst_no: str | None
    address: str | None
    contact_type: str
    is_active: bool
    created_date: datetime | None

    model_config = {"from_attributes": True}


class ContactListResponse(BaseModel):
    items: list[ContactResponse]
    total: int
    page: int
    page_size: int
