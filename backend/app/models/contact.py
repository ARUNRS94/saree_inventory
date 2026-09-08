from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Contact(Base):
    __tablename__ = "contacts"

    contact_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    contact_person: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30))
    gst_no: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(Text)
    contact_type: Mapped[str] = mapped_column(String(50), default="Raw Material Vendor", server_default="Raw Material Vendor", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="contact")
