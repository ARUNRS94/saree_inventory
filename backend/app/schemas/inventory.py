from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class StockLedgerResponse(BaseModel):
    ledger_id: int
    transaction_date: date
    transaction_type: str
    reference_no: str
    item_id: int
    item_code: str | None = None
    item_name: str | None = None
    qty_in: int
    qty_out: int
    rate: Decimal
    remarks: str | None

    model_config = {"from_attributes": True}


class StockLedgerListResponse(BaseModel):
    items: list[StockLedgerResponse]
    total: int
    page: int
    page_size: int


class StockSummaryResponse(BaseModel):
    item_id: int
    item_code: str
    item_name: str
    item_type: str | None
    current_stock: int


class StockValuationResponse(BaseModel):
    item_id: int
    item_code: str
    item_name: str
    current_stock: int
    latest_rate: Decimal
    value: Decimal


class CustomerIssueCreate(BaseModel):
    customer_id: int
    item_id: int
    quantity: int = Field(gt=0)
    reference: str | None = None
    remarks: str | None = None
