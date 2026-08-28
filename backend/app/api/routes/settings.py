from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user, require_admin
from app.models.company_settings import CompanySettings
from app.models.user import User

router = APIRouter(prefix="/settings", tags=["Settings"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB


@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CompanySettings))
    rows = result.scalars().all()
    return {row.key: row.value for row in rows}


@router.put("")
async def update_settings(body: dict, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    for key, value in body.items():
        existing = await db.scalar(select(CompanySettings).where(CompanySettings.key == key))
        if existing:
            existing.value = str(value)
        else:
            db.add(CompanySettings(key=key, value=str(value)))
    return {"message": "Settings updated."}


@router.post("/logo")
async def upload_logo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if not file.filename:
        raise HTTPException(400, "No file provided.")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type {ext} not allowed. Use: {', '.join(ALLOWED_EXTENSIONS)}")
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large. Max 2MB.")

    filename = f"logo_{uuid.uuid4().hex[:8]}{ext}"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(content)

    # Remove old logo file
    old = await db.scalar(select(CompanySettings).where(CompanySettings.key == "logo_url"))
    if old and old.value:
        old_path = UPLOAD_DIR / Path(old.value).name
        if old_path.exists():
            old_path.unlink(missing_ok=True)
        old.value = f"/api/v1/settings/uploads/{filename}"
    else:
        db.add(CompanySettings(key="logo_url", value=f"/api/v1/settings/uploads/{filename}"))

    return {"logo_url": f"/api/v1/settings/uploads/{filename}"}


@router.delete("/logo")
async def delete_logo(db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    row = await db.scalar(select(CompanySettings).where(CompanySettings.key == "logo_url"))
    if row and row.value:
        old_path = UPLOAD_DIR / Path(row.value).name
        old_path.unlink(missing_ok=True)
        row.value = ""
    return {"message": "Logo removed."}


@router.get("/uploads/{filename}")
async def serve_upload(filename: str):
    filepath = UPLOAD_DIR / Path(filename).name
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(404, "File not found.")
    return FileResponse(filepath)
