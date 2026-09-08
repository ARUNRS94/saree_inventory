from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    item_code: str = Field(min_length=1, max_length=50)
    item_name: str = Field(min_length=1, max_length=200)
    item_type: str = "FG"
    remarks: str | None = None
    color: str | None = None


class ItemUpdate(BaseModel):
    item_code: str | None = None
    item_name: str | None = None
    item_type: str | None = None
    remarks: str | None = None
    color: str | None = None


class ItemResponse(BaseModel):
    item_id: int
    item_code: str
    item_name: str
    item_type: str | None
    remarks: str | None
    color: str | None
    created_date: datetime | None

    model_config = {"from_attributes": True}


class ItemListResponse(BaseModel):
    items: list[ItemResponse]
    total: int
    page: int
    page_size: int
