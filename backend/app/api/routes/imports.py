from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_permission
from app.models.user import User
from app.services.import_service import ENTITY_SPECS, ImportService, build_template, export_csv

router = APIRouter(prefix="/imports", tags=["Imports"])
export_router = APIRouter(prefix="/exports", tags=["Exports"])

require_imports = require_permission("imports")

MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def _spec_or_404(entity: str):
    spec = ENTITY_SPECS.get(entity)
    if spec is None:
        raise HTTPException(404, f"Unknown import type: {entity}")
    return spec


@router.get("")
async def list_import_types(_user: User = Depends(require_imports)):
    return [
        {"entity": entity, "columns": spec.columns, "required": spec.required, "key": spec.key}
        for entity, spec in ENTITY_SPECS.items()
    ]


@router.get("/{entity}/template")
async def download_template(entity: str, _user: User = Depends(require_imports)):
    _spec_or_404(entity)
    return Response(
        content=build_template(entity),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={entity}_template.csv"},
    )


@router.post("/{entity}")
async def import_csv(
    entity: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_imports),
):
    _spec_or_404(entity)
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file.")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "File too large. Max 2MB.")
    if not content.strip():
        raise HTTPException(400, "The file is empty.")

    try:
        result = await ImportService(db).import_csv(entity, content)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return result.as_dict()


# Export is available to anyone who can already view the data on screen.
@export_router.get("/{entity}")
async def export_entity(
    entity: str,
    search: str = "",
    filter_value: str | None = None,
    sort_by: str | None = None,
    sort_dir: str = "asc",
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    _spec_or_404(entity)
    content = await export_csv(db, entity, search, filter_value, sort_by, sort_dir)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={entity}_export.csv"},
    )
