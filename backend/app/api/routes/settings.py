from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user, require_permission
from app.models.company_settings import CompanySettings
from app.models.user import User

router = APIRouter(prefix="/settings", tags=["Settings"])

require_settings = require_permission("settings")

ALLOWED_LOGO_SCHEMES = ("https://", "http://", "data:image/")


@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CompanySettings))
    rows = result.scalars().all()
    return {row.key: row.value for row in rows}


@router.put("")
async def update_settings(body: dict, db: AsyncSession = Depends(get_db), _user: User = Depends(require_settings)):
    logo = body.get("logo_url")
    if logo and not str(logo).startswith(ALLOWED_LOGO_SCHEMES):
        raise HTTPException(400, "logo_url must be an http(s) or data:image URL.")
    for key, value in body.items():
        existing = await db.scalar(select(CompanySettings).where(CompanySettings.key == key))
        if existing:
            existing.value = str(value)
        else:
            db.add(CompanySettings(key=key, value=str(value)))
    return {"message": "Settings updated."}
