from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.schemas.supplier import SupplierCreate, SupplierListResponse, SupplierResponse, SupplierUpdate
from app.services.master_service import MasterService

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("", response_model=SupplierListResponse)
async def list_suppliers(
    search: str = "", contact_type: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    items, total = await MasterService(db).search_contacts(search, contact_type, page, page_size)
    return SupplierListResponse(
        items=[SupplierResponse.model_validate(s) for s in items],
        total=total, page=page, page_size=page_size,
    )


@router.post("", response_model=SupplierResponse, status_code=201)
async def create_supplier(body: SupplierCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        contact = await MasterService(db).create_contact(
            body.supplier_name, body.contact_type,
            contact_person=body.contact_person, phone=body.phone,
            gst_no=body.gst_no, address=body.address,
        )
        return SupplierResponse.model_validate(contact)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(supplier_id: int, body: SupplierUpdate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        contact = await MasterService(db).update_contact(supplier_id, **body.model_dump(exclude_unset=True))
        return SupplierResponse.model_validate(contact)
    except ValueError as e:
        raise HTTPException(400, str(e))
