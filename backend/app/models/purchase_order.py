from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    po_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.contact_id"), nullable=False)
    po_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    remarks: Mapped[str | None] = mapped_column(Text)

    contact: Mapped["Contact"] = relationship(back_populates="purchase_orders")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    po_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.po_id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.item_id"), nullable=False)
    stock_out_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.item_id"))
    target_fg_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.item_id"))
    ordered_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")
    item: Mapped["Item"] = relationship(foreign_keys=[item_id])
    stock_out_item: Mapped["Item | None"] = relationship(foreign_keys=[stock_out_item_id])
    target_fg_item: Mapped["Item | None"] = relationship(foreign_keys=[target_fg_item_id])
