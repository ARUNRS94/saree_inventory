from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class PurchaseLineCreate(BaseModel):
    saree_id: int
    quantity: int = Field(gt=0)
    rate: Decimal = Field(ge=0)
    stock_out_saree_id: int | None = None
    target_fg_saree_id: int | None = None


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    po_date: date | None = None
    expected_date: date | None = None
    remarks: str | None = None
    items: list[PurchaseLineCreate] = Field(min_length=1)


class PurchaseOrderStatusUpdate(BaseModel):
    status: str | None = None
    remarks: str | None = None


class POItemResponse(BaseModel):
    po_item_id: int
    saree_id: int
    saree_code: str | None = None
    saree_name: str | None = None
    stock_out_saree_id: int | None
    stock_out_saree_code: str | None = None
    target_fg_saree_id: int | None
    target_fg_saree_code: str | None = None
    target_fg_saree_name: str | None = None
    ordered_qty: int
    rate: Decimal
    amount: Decimal

    model_config = {"from_attributes": True}


class PurchaseOrderResponse(BaseModel):
    po_id: int
    po_number: str
    supplier_id: int
    supplier_name: str | None = None
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
