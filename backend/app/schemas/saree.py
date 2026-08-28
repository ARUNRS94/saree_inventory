from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SareeCreate(BaseModel):
    saree_code: str = Field(min_length=1, max_length=50)
    saree_name: str = Field(min_length=1, max_length=200)
    category: str | None = None
    fabric: str | None = "FG"
    design_name: str | None = None
    color: str | None = None
    unit: str = "PCS"


class SareeUpdate(BaseModel):
    saree_code: str | None = None
    saree_name: str | None = None
    category: str | None = None
    fabric: str | None = None
    design_name: str | None = None
    color: str | None = None
    unit: str | None = None


class SareeResponse(BaseModel):
    saree_id: int
    saree_code: str
    saree_name: str
    category: str | None
    fabric: str | None
    design_name: str | None
    color: str | None
    unit: str
    created_date: datetime | None

    model_config = {"from_attributes": True}


class SareeListResponse(BaseModel):
    items: list[SareeResponse]
    total: int
    page: int
    page_size: int
