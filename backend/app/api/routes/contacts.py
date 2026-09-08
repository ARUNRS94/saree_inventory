from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.schemas.contact import ContactCreate, ContactListResponse, ContactResponse, ContactUpdate
from app.services.master_service import MasterService

router = APIRouter(prefix="/contacts", tags=["Contacts"])


@router.get("", response_model=ContactListResponse)
async def list_suppliers(
    search: str = "", contact_type: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
    sort_by: str | None = None, sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    items, total = await MasterService(db).search_contacts(search, contact_type, page, page_size, sort_by, sort_dir)
    return ContactListResponse(
        items=[ContactResponse.model_validate(s) for s in items],
        total=total, page=page, page_size=page_size,
    )


@router.post("", response_model=ContactResponse, status_code=201)
async def create_supplier(body: ContactCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        contact = await MasterService(db).create_contact(
            body.contact_name, body.contact_type,
            contact_person=body.contact_person, phone=body.phone,
            gst_no=body.gst_no, address=body.address,
        )
        return ContactResponse.model_validate(contact)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/{contact_id}", response_model=ContactResponse)
async def update_supplier(contact_id: int, body: ContactUpdate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        contact = await MasterService(db).update_contact(contact_id, **body.model_dump(exclude_unset=True))
        return ContactResponse.model_validate(contact)
    except ValueError as e:
        raise HTTPException(400, str(e))
