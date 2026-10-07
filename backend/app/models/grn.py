from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# Raw Material receipts are entered straight into a GRN; sub vendor receipts come off a voucher.
GRN_TYPE_RAW_MATERIAL = "RM"
GRN_TYPE_SUB_VENDOR = "SUB"


class GRN(Base):
    __tablename__ = "grns"

    grn_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grn_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    grn_type: Mapped[str] = mapped_column(String(10), default=GRN_TYPE_SUB_VENDOR, server_default=GRN_TYPE_SUB_VENDOR)
    po_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.po_id"))
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.contact_id"))
    grn_date: Mapped[date] = mapped_column(Date, nullable=False)
    vendor_voucher_number: Mapped[str | None] = mapped_column(String(50))
    remarks: Mapped[str | None] = mapped_column(Text)

    purchase_order: Mapped["PurchaseOrder | None"] = relationship()
    contact: Mapped["Contact | None"] = relationship()
    items: Mapped[list["GRNItem"]] = relationship(cascade="all, delete-orphan")


class GRNItem(Base):
    __tablename__ = "grn_items"

    grn_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grn_id: Mapped[int] = mapped_column(ForeignKey("grns.grn_id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.item_id"), nullable=False)
    received_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    damaged_qty: Mapped[int] = mapped_column(Integer, default=0)
    short_qty: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    lr_number: Mapped[str | None] = mapped_column(String(50))
    po_number: Mapped[str | None] = mapped_column(String(50))

    item: Mapped["Item"] = relationship()
