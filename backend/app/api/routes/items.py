from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.schemas.item import ItemCreate, ItemListResponse, ItemResponse, ItemUpdate
from app.services.master_service import MasterService

router = APIRouter(prefix="/items", tags=["Items"])


@router.get("", response_model=ItemListResponse)
async def list_items(
    search: str = "", item_type: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
    sort_by: str | None = None, sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    items, total = await MasterService(db).search_items(search, item_type, page, page_size, sort_by, sort_dir)
    return ItemListResponse(
        items=[ItemResponse.model_validate(s) for s in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    item = await db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    return ItemResponse.model_validate(item)


@router.post("", response_model=ItemResponse, status_code=201)
async def create_item(body: ItemCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        item = await MasterService(db).create_item(
            body.item_code, body.item_name,
            item_type=body.item_type,
            remarks=body.remarks, color=body.color,
        )
        return ItemResponse.model_validate(item)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/{item_id}", response_model=ItemResponse)
async def update_item(item_id: int, body: ItemUpdate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        item = await MasterService(db).update_item(item_id, **body.model_dump(exclude_unset=True))
        return ItemResponse.model_validate(item)
    except ValueError as e:
        raise HTTPException(400, str(e))


from app.models.item import Item
