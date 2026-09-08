from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("item_code", name="uq_item_code"),)

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    item_type: Mapped[str] = mapped_column(String(30), default="FG", server_default="FG", index=True)
    remarks: Mapped[str | None] = mapped_column(String(150))
    color: Mapped[str | None] = mapped_column(String(80))
    created_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
