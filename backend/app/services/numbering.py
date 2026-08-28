from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def next_number(session: AsyncSession, model: type, field_name: str, prefix: str, on_date: date | None = None) -> str:
    year = (on_date or date.today()).year
    stem = f"{prefix}-{year}-"
    field = getattr(model, field_name)
    result = await session.scalar(select(func.count()).select_from(model).where(field.like(f"{stem}%")))
    count = result or 0
    return f"{stem}{int(count) + 1:04d}"
