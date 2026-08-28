from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Saree(Base):
    __tablename__ = "sarees"
    __table_args__ = (UniqueConstraint("saree_code", name="uq_saree_code"),)

    saree_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    saree_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    saree_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    fabric: Mapped[str | None] = mapped_column(String(100), default="FG", server_default="FG")
    design_name: Mapped[str | None] = mapped_column(String(150))
    color: Mapped[str | None] = mapped_column(String(80))
    unit: Mapped[str] = mapped_column(String(20), default="PCS", server_default="PCS")
    created_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
