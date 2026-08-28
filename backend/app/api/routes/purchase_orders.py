from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.schemas.purchase_order import (
    POItemResponse, PurchaseOrderCreate, PurchaseOrderListResponse,
    PurchaseOrderResponse, PurchaseOrderStatusUpdate,
)
from app.services.purchase_service import PurchaseLine, PurchaseService

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


def _po_to_response(po) -> PurchaseOrderResponse:
    items = []
    for item in po.items:
        items.append(POItemResponse(
            po_item_id=item.po_item_id,
            saree_id=item.saree_id,
            saree_code=item.saree.saree_code if item.saree else None,
            saree_name=item.saree.saree_name if item.saree else None,
            stock_out_saree_id=item.stock_out_saree_id,
            stock_out_saree_code=item.stock_out_saree.saree_code if item.stock_out_saree else None,
            target_fg_saree_id=item.target_fg_saree_id,
            target_fg_saree_code=item.target_fg_saree.saree_code if item.target_fg_saree else None,
            target_fg_saree_name=item.target_fg_saree.saree_name if item.target_fg_saree else None,
            ordered_qty=item.ordered_qty,
            rate=item.rate,
            amount=item.amount,
        ))
    return PurchaseOrderResponse(
        po_id=po.po_id, po_number=po.po_number, supplier_id=po.supplier_id,
        supplier_name=po.supplier.supplier_name if po.supplier else None,
        contact_type=po.supplier.contact_type if po.supplier else None,
        po_date=po.po_date, expected_date=po.expected_date,
        status=po.status, remarks=po.remarks, items=items,
    )


@router.get("", response_model=PurchaseOrderListResponse)
async def list_pos(
    status: str | None = None, supplier_id: int | None = None,
    search: str = "", date_from: date | None = None, date_to: date | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    pos, total = await PurchaseService(db).list_pos(status, supplier_id, search, date_from, date_to, page, page_size)
    return PurchaseOrderListResponse(
        items=[_po_to_response(po) for po in pos],
        total=total, page=page, page_size=page_size,
    )


@router.post("", response_model=PurchaseOrderResponse, status_code=201)
async def create_po(body: PurchaseOrderCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        lines = [PurchaseLine(
            saree_id=item.saree_id, quantity=item.quantity, rate=item.rate,
            stock_out_saree_id=item.stock_out_saree_id, target_fg_saree_id=item.target_fg_saree_id,
        ) for item in body.items]
        po = await PurchaseService(db).create_po(
            body.supplier_id, lines, body.po_date, body.expected_date, body.remarks,
        )
        # Reload with relationships
        from sqlalchemy.orm import selectinload
        from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
        po = await db.get(PurchaseOrder, po.po_id, options=[
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.saree),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.stock_out_saree),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.target_fg_saree),
        ])
        return _po_to_response(po)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/{po_id}/status", response_model=PurchaseOrderResponse)
async def update_po_status(po_id: int, body: PurchaseOrderStatusUpdate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
        from sqlalchemy.orm import selectinload
        po = await db.get(PurchaseOrder, po_id, options=[
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.saree),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.stock_out_saree),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.target_fg_saree),
        ])
        if po is None:
            raise HTTPException(404, "Purchase order not found")
        if body.status:
            po.status = body.status
        if body.remarks is not None:
            po.remarks = body.remarks
        return _po_to_response(po)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{po_id}/cancel", response_model=PurchaseOrderResponse)
async def cancel_po(po_id: int, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        po = await PurchaseService(db).cancel_po(po_id)
        from sqlalchemy.orm import selectinload
        from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
        po = await db.get(PurchaseOrder, po.po_id, options=[
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.saree),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.stock_out_saree),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.target_fg_saree),
        ])
        return _po_to_response(po)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{po_id}/pending-qty")
async def get_pending_qty(po_id: int, saree_id: int | None = None, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    qty = await PurchaseService(db).pending_po_qty(po_id, saree_id)
    return {"pending_qty": qty}
