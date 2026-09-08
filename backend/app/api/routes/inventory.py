from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.item import Item
from app.models.stock_ledger import StockLedger
from app.schemas.inventory import CustomerIssueCreate, StockLedgerListResponse, StockLedgerResponse, StockSummaryResponse, StockValuationResponse
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("/stock", response_model=list[StockSummaryResponse])
async def get_stock(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    service = InventoryService(db)
    rows = await service.stock_report()
    return [StockSummaryResponse(**r) for r in rows]


@router.get("/stock/{item_id}")
async def get_stock_qty(item_id: int, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    qty = await InventoryService(db).current_stock(item_id)
    return {"item_id": item_id, "current_stock": qty}


@router.get("/valuation", response_model=list[StockValuationResponse])
async def get_valuation(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    rows = await InventoryService(db).inventory_valuation()
    return [StockValuationResponse(**r) for r in rows]


@router.get("/ledger", response_model=StockLedgerListResponse)
async def get_ledger(
    search: str = "", transaction_type: str | None = None,
    date_from: date | None = None, date_to: date | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    base_filter = []
    if transaction_type:
        base_filter.append(StockLedger.transaction_type == transaction_type)
    if date_from:
        base_filter.append(StockLedger.transaction_date >= date_from)
    if date_to:
        base_filter.append(StockLedger.transaction_date <= date_to)
    if search:
        like = f"%{search}%"
        base_filter.append(
            StockLedger.reference_no.ilike(like) | Item.item_code.ilike(like) | Item.item_name.ilike(like)
        )

    count_stmt = select(func.count()).select_from(StockLedger).join(Item, Item.item_id == StockLedger.item_id)
    for f in base_filter:
        count_stmt = count_stmt.where(f)
    total = await db.scalar(count_stmt) or 0

    stmt = (
        select(StockLedger, Item.item_code, Item.item_name)
        .join(Item, Item.item_id == StockLedger.item_id)
    )
    for f in base_filter:
        stmt = stmt.where(f)
    stmt = stmt.order_by(StockLedger.transaction_date.desc(), StockLedger.ledger_id.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = []
    for entry, code, name in result:
        items.append(StockLedgerResponse(
            ledger_id=entry.ledger_id, transaction_date=entry.transaction_date,
            transaction_type=entry.transaction_type, reference_no=entry.reference_no,
            item_id=entry.item_id, item_code=code, item_name=name,
            qty_in=entry.qty_in, qty_out=entry.qty_out, rate=entry.rate, remarks=entry.remarks,
        ))
    return StockLedgerListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/customer-issue", status_code=201)
async def customer_issue(body: CustomerIssueCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        service = InventoryService(db)
        await service.assert_available(body.item_id, body.quantity)
        reference = body.reference or f"CUST-{date.today():%Y%m%d}"
        await service.post_ledger(
            transaction_date=date.today(), transaction_type="CUSTOMER_ISSUE",
            reference_no=reference, item_id=body.item_id,
            qty_out=body.quantity, remarks=body.remarks,
        )
        return {"message": "Customer issue saved and FG stock reduced."}
    except ValueError as e:
        raise HTTPException(400, str(e))
