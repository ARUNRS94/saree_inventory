from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.types import Money


class PurchaseLineCreate(BaseModel):
    item_id: int
    quantity: int = Field(gt=0)
    rate: Decimal = Field(ge=0, default=Decimal("0"))
    stock_out_item_id: int | None = None
    target_fg_item_id: int | None = None
    lr_number: str | None = Field(default=None, max_length=50)


class PurchaseOrderCreate(BaseModel):
    contact_id: int
    voucher_number: str = Field(min_length=1, max_length=50)
    po_date: date | None = None
    expected_date: date | None = None
    remarks: str | None = None
    items: list[PurchaseLineCreate] = Field(min_length=1)


class PurchaseOrderStatusUpdate(BaseModel):
    status: str | None = None
    remarks: str | None = None


class POItemResponse(BaseModel):
    po_item_id: int
    item_id: int
    item_code: str | None = None
    item_name: str | None = None
    stock_out_item_id: int | None
    stock_out_item_code: str | None = None
    target_fg_item_id: int | None
    target_fg_item_code: str | None = None
    target_fg_item_name: str | None = None
    ordered_qty: int
    rate: Money
    amount: Money
    lr_number: str | None = None

    model_config = {"from_attributes": True}


class PurchaseOrderResponse(BaseModel):
    po_id: int
    po_number: str
    voucher_number: str | None = None
    contact_id: int
    contact_name: str | None = None
    contact_type: str | None = None
    po_date: date
    expected_date: date | None
    status: str
    remarks: str | None
    items: list[POItemResponse] = []

    model_config = {"from_attributes": True}


class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderResponse]
    total: int
    page: int
    page_size: int
