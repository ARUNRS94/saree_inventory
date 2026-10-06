from __future__ import annotations

from pydantic import BaseModel

from app.schemas.types import Money


class DashboardCardData(BaseModel):
    total_stock_qty: int
    stock_value: Money
    open_po_value: Money
    pending_po_qty: int
    vendor_wip_qty: int
    active_items: int
    active_vendors: int
    active_contacts: int


class PurchaseTrendItem(BaseModel):
    month: str
    value: Money


class StockMovementItem(BaseModel):
    month: str
    qty_in: int
    qty_out: int


class CategoryStockItem(BaseModel):
    category: str
    qty: int


class DashboardResponse(BaseModel):
    cards: DashboardCardData
    purchase_trend: list[PurchaseTrendItem]
    stock_movement: list[StockMovementItem]
    top_categories: list[CategoryStockItem]
