from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class JobWorkIssueLineCreate(BaseModel):
    item_id: int
    issued_qty: int = Field(gt=0)


class JobWorkIssueCreate(BaseModel):
    vendor_id: int
    issue_date: date | None = None
    remarks: str | None = None
    items: list[JobWorkIssueLineCreate] = Field(min_length=1)


class JobWorkIssueItemResponse(BaseModel):
    issue_item_id: int
    item_id: int
    item_code: str | None = None
    item_name: str | None = None
    issued_qty: int

    model_config = {"from_attributes": True}


class JobWorkIssueResponse(BaseModel):
    issue_id: int
    issue_no: str
    vendor_id: int
    vendor_name: str | None = None
    issue_date: date
    status: str
    remarks: str | None
    items: list[JobWorkIssueItemResponse] = []

    model_config = {"from_attributes": True}


class JobWorkIssueListResponse(BaseModel):
    items: list[JobWorkIssueResponse]
    total: int
    page: int
    page_size: int


class JobWorkReceiptLineCreate(BaseModel):
    item_id: int
    received_qty: int = Field(ge=0)
    rejected_qty: int = Field(ge=0, default=0)
    process_cost: Decimal = Field(ge=0, default=0)


class JobWorkReceiptCreate(BaseModel):
    issue_id: int
    vendor_id: int
    receipt_date: date | None = None
    items: list[JobWorkReceiptLineCreate] = Field(min_length=1)


class JobWorkReceiptItemResponse(BaseModel):
    receipt_item_id: int
    item_id: int
    item_code: str | None = None
    item_name: str | None = None
    received_qty: int
    rejected_qty: int
    process_cost: Decimal

    model_config = {"from_attributes": True}


class JobWorkReceiptResponse(BaseModel):
    receipt_id: int
    receipt_no: str
    issue_id: int
    issue_no: str | None = None
    vendor_id: int
    vendor_name: str | None = None
    receipt_date: date
    items: list[JobWorkReceiptItemResponse] = []

    model_config = {"from_attributes": True}


class JobWorkReceiptListResponse(BaseModel):
    items: list[JobWorkReceiptResponse]
    total: int
    page: int
    page_size: int
