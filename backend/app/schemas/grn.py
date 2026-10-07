from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.types import Money


class GRNLineCreate(BaseModel):
    item_id: int
    received_qty: int = Field(ge=0)
    damaged_qty: int = Field(ge=0, default=0)
    short_qty: int = Field(ge=0, default=0)
    rate: Decimal = Field(ge=0, default=Decimal("0"))
    lr_number: str | None = Field(default=None, max_length=50)
    po_number: str | None = Field(default=None, max_length=50)


class GRNCreate(BaseModel):
    """A sub vendor GRN draws on a voucher; a Raw Material GRN is entered directly."""

    grn_type: str = "SUB"
    po_id: int | None = None
    contact_id: int | None = None
    grn_date: date | None = None
    vendor_voucher_number: str | None = Field(default=None, max_length=50)
    remarks: str | None = None
    items: list[GRNLineCreate] = Field(min_length=1)


class GRNItemResponse(BaseModel):
    grn_item_id: int
    item_id: int
    item_code: str | None = None
    item_name: str | None = None
    received_qty: int
    damaged_qty: int
    short_qty: int = 0
    rate: Money
    lr_number: str | None = None
    po_number: str | None = None

    model_config = {"from_attributes": True}


class GRNResponse(BaseModel):
    grn_id: int
    grn_number: str
    grn_type: str = "SUB"
    po_id: int | None = None
    po_number: str | None = None
    voucher_number: str | None = None
    contact_id: int | None = None
    contact_name: str | None = None
    grn_date: date
    vendor_voucher_number: str | None = None
    remarks: str | None
    items: list[GRNItemResponse] = []

    model_config = {"from_attributes": True}


class GRNListResponse(BaseModel):
    items: list[GRNResponse]
    total: int
    page: int
    page_size: int
