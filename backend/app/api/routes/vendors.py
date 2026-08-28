from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.schemas.vendor import (
    VendorCreate, VendorListResponse, VendorProcessTypeCreate,
    VendorProcessTypeResponse, VendorProcessTypeUpdate, VendorResponse, VendorUpdate,
)
from app.services.master_service import MasterService

router = APIRouter(prefix="/vendors", tags=["Vendors"])


@router.get("", response_model=VendorListResponse)
async def list_vendors(
    search: str = "", process_type: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    items, total = await MasterService(db).search_vendors(search, process_type, page, page_size)
    return VendorListResponse(
        items=[VendorResponse.model_validate(v) for v in items],
        total=total, page=page, page_size=page_size,
    )


@router.post("", response_model=VendorResponse, status_code=201)
async def create_vendor(body: VendorCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        vendor = await MasterService(db).create_vendor(
            body.vendor_name, body.process_type,
            contact_person=body.contact_person, phone=body.phone,
            gst_no=body.gst_no, address=body.address,
        )
        return VendorResponse.model_validate(vendor)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/{vendor_id}", response_model=VendorResponse)
async def update_vendor(vendor_id: int, body: VendorUpdate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        vendor = await MasterService(db).update_vendor(vendor_id, **body.model_dump(exclude_unset=True))
        return VendorResponse.model_validate(vendor)
    except ValueError as e:
        raise HTTPException(400, str(e))


# --- Process Types ---
@router.get("/process-types", response_model=list[VendorProcessTypeResponse])
async def list_process_types(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    return [VendorProcessTypeResponse.model_validate(pt) for pt in await MasterService(db).list_process_types()]


@router.post("/process-types", response_model=VendorProcessTypeResponse, status_code=201)
async def create_process_type(body: VendorProcessTypeCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        pt = await MasterService(db).create_process_type(body.process_type)
        return VendorProcessTypeResponse.model_validate(pt)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/process-types/{process_type_id}", response_model=VendorProcessTypeResponse)
async def update_process_type(process_type_id: int, body: VendorProcessTypeUpdate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        pt = await MasterService(db).update_process_type(process_type_id, **body.model_dump(exclude_unset=True))
        return VendorProcessTypeResponse.model_validate(pt)
    except ValueError as e:
        raise HTTPException(400, str(e))
