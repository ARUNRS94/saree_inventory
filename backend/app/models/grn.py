from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class GRN(Base):
    __tablename__ = "grns"

    grn_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grn_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.po_id"), nullable=False)
    grn_date: Mapped[date] = mapped_column(Date, nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text)

    purchase_order: Mapped["PurchaseOrder"] = relationship()
    items: Mapped[list["GRNItem"]] = relationship(cascade="all, delete-orphan")


class GRNItem(Base):
    __tablename__ = "grn_items"

    grn_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grn_id: Mapped[int] = mapped_column(ForeignKey("grns.grn_id"), nullable=False)
    saree_id: Mapped[int] = mapped_column(ForeignKey("sarees.saree_id"), nullable=False)
    received_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    damaged_qty: Mapped[int] = mapped_column(Integer, default=0)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    saree: Mapped["Saree"] = relationship()
