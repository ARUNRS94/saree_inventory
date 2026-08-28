from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.schemas.grn import GRNCreate, GRNItemResponse, GRNListResponse, GRNResponse
from app.services.purchase_service import PurchaseService

router = APIRouter(prefix="/grns", tags=["GRN"])


def _grn_to_response(grn) -> GRNResponse:
    items = [GRNItemResponse(
        grn_item_id=item.grn_item_id, saree_id=item.saree_id,
        saree_code=item.saree.saree_code if item.saree else None,
        saree_name=item.saree.saree_name if item.saree else None,
        received_qty=item.received_qty, damaged_qty=item.damaged_qty, rate=item.rate,
    ) for item in grn.items]
    return GRNResponse(
        grn_id=grn.grn_id, grn_number=grn.grn_number, po_id=grn.po_id,
        po_number=grn.purchase_order.po_number if grn.purchase_order else None,
        grn_date=grn.grn_date, remarks=grn.remarks, items=items,
    )


@router.get("", response_model=GRNListResponse)
async def list_grns(
    po_id: int | None = None, search: str = "",
    date_from: date | None = None, date_to: date | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    grns, total = await PurchaseService(db).list_grns(po_id, search, date_from, date_to, page, page_size)
    return GRNListResponse(
        items=[_grn_to_response(g) for g in grns],
        total=total, page=page, page_size=page_size,
    )


@router.post("", response_model=GRNResponse, status_code=201)
async def create_grn(body: GRNCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        lines = [(item.saree_id, item.received_qty, item.damaged_qty, item.rate) for item in body.items]
        grn = await PurchaseService(db).receive_grn(body.po_id, lines, body.grn_date, body.remarks)
        from sqlalchemy.orm import selectinload
        from app.models.grn import GRN, GRNItem
        grn = await db.get(GRN, grn.grn_id, options=[
            selectinload(GRN.purchase_order),
            selectinload(GRN.items).selectinload(GRNItem.saree),
        ])
        return _grn_to_response(grn)
    except ValueError as e:
        raise HTTPException(400, str(e))
