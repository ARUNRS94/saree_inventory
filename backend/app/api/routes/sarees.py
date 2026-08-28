from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.schemas.saree import SareeCreate, SareeListResponse, SareeResponse, SareeUpdate
from app.services.master_service import MasterService

router = APIRouter(prefix="/sarees", tags=["Sarees"])


@router.get("", response_model=SareeListResponse)
async def list_sarees(
    search: str = "", item_type: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    items, total = await MasterService(db).search_sarees(search, item_type, page, page_size)
    return SareeListResponse(
        items=[SareeResponse.model_validate(s) for s in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/{saree_id}", response_model=SareeResponse)
async def get_saree(saree_id: int, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    saree = await db.get(Saree, saree_id)
    if not saree:
        raise HTTPException(404, "Saree not found")
    return SareeResponse.model_validate(saree)


@router.post("", response_model=SareeResponse, status_code=201)
async def create_saree(body: SareeCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        saree = await MasterService(db).create_saree(
            body.saree_code, body.saree_name,
            category=body.category, fabric=body.fabric,
            design_name=body.design_name, color=body.color, unit=body.unit,
        )
        return SareeResponse.model_validate(saree)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/{saree_id}", response_model=SareeResponse)
async def update_saree(saree_id: int, body: SareeUpdate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        saree = await MasterService(db).update_saree(saree_id, **body.model_dump(exclude_unset=True))
        return SareeResponse.model_validate(saree)
    except ValueError as e:
        raise HTTPException(400, str(e))


from app.models.saree import Saree
