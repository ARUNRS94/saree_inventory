from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VendorProcessType(Base):
    __tablename__ = "vendor_process_types"
    __table_args__ = (UniqueConstraint("process_type", name="uq_vendor_process_type"),)

    process_type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    process_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
