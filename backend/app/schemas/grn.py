from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class GRNLineCreate(BaseModel):
    saree_id: int
    received_qty: int = Field(ge=0)
    damaged_qty: int = Field(ge=0, default=0)
    rate: Decimal = Field(ge=0)


class GRNCreate(BaseModel):
    po_id: int
    grn_date: date | None = None
    remarks: str | None = None
    items: list[GRNLineCreate] = Field(min_length=1)


class GRNItemResponse(BaseModel):
    grn_item_id: int
    saree_id: int
    saree_code: str | None = None
    saree_name: str | None = None
    received_qty: int
    damaged_qty: int
    rate: Decimal

    model_config = {"from_attributes": True}


class GRNResponse(BaseModel):
    grn_id: int
    grn_number: str
    po_id: int
    po_number: str | None = None
    grn_date: date
    remarks: str | None
    items: list[GRNItemResponse] = []

    model_config = {"from_attributes": True}


class GRNListResponse(BaseModel):
    items: list[GRNResponse]
    total: int
    page: int
    page_size: int
