from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.grn import GRN_TYPE_RAW_MATERIAL
from app.schemas.grn import GRNCreate, GRNItemResponse, GRNListResponse, GRNResponse
from app.services.purchase_service import GRNLine, PurchaseService

router = APIRouter(prefix="/grns", tags=["GRN"])


def _grn_to_response(grn) -> GRNResponse:
    items = [GRNItemResponse(
        grn_item_id=item.grn_item_id, item_id=item.item_id,
        item_code=item.item.item_code if item.item else None,
        item_name=item.item.item_name if item.item else None,
        received_qty=item.received_qty, damaged_qty=item.damaged_qty,
        short_qty=item.short_qty or 0, rate=item.rate,
        lr_number=item.lr_number, po_number=item.po_number,
    ) for item in grn.items]
    contact = grn.contact or (grn.purchase_order.contact if grn.purchase_order else None)
    return GRNResponse(
        grn_id=grn.grn_id, grn_number=grn.grn_number, grn_type=grn.grn_type or "SUB",
        po_id=grn.po_id,
        po_number=grn.purchase_order.po_number if grn.purchase_order else None,
        voucher_number=grn.purchase_order.voucher_number if grn.purchase_order else None,
        contact_id=grn.contact_id,
        contact_name=contact.contact_name if contact else None,
        grn_date=grn.grn_date, vendor_voucher_number=grn.vendor_voucher_number,
        remarks=grn.remarks, items=items,
    )


@router.get("", response_model=GRNListResponse)
async def list_grns(
    po_id: int | None = None, search: str = "", grn_type: str | None = None,
    date_from: date | None = None, date_to: date | None = None,
    voucher_number: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    grns, total = await PurchaseService(db).list_grns(po_id, search, date_from, date_to, page, page_size,
                                                      grn_type, voucher_number)
    return GRNListResponse(
        items=[_grn_to_response(g) for g in grns],
        total=total, page=page, page_size=page_size,
    )


@router.post("", response_model=GRNResponse, status_code=201)
async def create_grn(body: GRNCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        lines = [GRNLine(
            item_id=item.item_id, received_qty=item.received_qty, damaged_qty=item.damaged_qty,
            rate=item.rate, lr_number=item.lr_number, short_qty=item.short_qty, po_number=item.po_number,
        ) for item in body.items]
        service = PurchaseService(db)
        if body.grn_type == GRN_TYPE_RAW_MATERIAL:
            grn = await service.receive_direct_grn(body.contact_id, lines, body.grn_date, body.remarks)
        else:
            if body.po_id is None:
                raise ValueError("Select the voucher this sub vendor receipt belongs to.")
            grn = await service.receive_grn(
                body.po_id, lines, body.grn_date, body.remarks, body.vendor_voucher_number,
            )
        from sqlalchemy.orm import selectinload
        from app.models.grn import GRN, GRNItem
        from app.models.purchase_order import PurchaseOrder
        grn = await db.get(GRN, grn.grn_id, populate_existing=True, options=[
            selectinload(GRN.purchase_order).selectinload(PurchaseOrder.contact),
            selectinload(GRN.contact),
            selectinload(GRN.items).selectinload(GRNItem.item),
        ])
        return _grn_to_response(grn)
    except ValueError as e:
        raise HTTPException(400, str(e))
