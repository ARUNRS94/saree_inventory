"""SQLAlchemy ORM models for the saree inventory domain."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base


class TimestampMixin:
    created_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=func.now())


class Supplier(TimestampMixin, Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    contact_person: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30))
    gst_no: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(Text)
    contact_type: Mapped[str] = mapped_column(String(30), default="RM vendor", server_default="RM vendor", index=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="supplier")


class VendorProcessType(TimestampMixin, Base):
    __tablename__ = "vendor_process_types"
    __table_args__ = (UniqueConstraint("process_type", name="uq_vendor_process_type"),)

    process_type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    process_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class Vendor(TimestampMixin, Base):
    __tablename__ = "vendors"

    vendor_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    process_type: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30))
    gst_no: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)


class Saree(TimestampMixin, Base):
    __tablename__ = "sarees"
    __table_args__ = (UniqueConstraint("saree_code", name="uq_saree_code"),)

    saree_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    saree_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    saree_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    fabric: Mapped[str | None] = mapped_column(String(100), default="FG", server_default="FG")
    design_name: Mapped[str | None] = mapped_column(String(150))
    color: Mapped[str | None] = mapped_column(String(80))
    unit: Mapped[str] = mapped_column(String(20), default="PCS")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    po_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.supplier_id"), nullable=False)
    po_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    remarks: Mapped[str | None] = mapped_column(Text)

    supplier: Mapped[Supplier] = relationship(back_populates="purchase_orders")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    po_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.po_id"), nullable=False)
    saree_id: Mapped[int] = mapped_column(ForeignKey("sarees.saree_id"), nullable=False)
    stock_out_saree_id: Mapped[int | None] = mapped_column(ForeignKey("sarees.saree_id"))
    target_fg_saree_id: Mapped[int | None] = mapped_column(ForeignKey("sarees.saree_id"))
    ordered_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")
    saree: Mapped[Saree] = relationship(foreign_keys=[saree_id])
    stock_out_saree: Mapped[Saree | None] = relationship(foreign_keys=[stock_out_saree_id])
    target_fg_saree: Mapped[Saree | None] = relationship(foreign_keys=[target_fg_saree_id])


class GRN(Base):
    __tablename__ = "grns"

    grn_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grn_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.po_id"), nullable=False)
    grn_date: Mapped[date] = mapped_column(Date, nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text)
    items: Mapped[list["GRNItem"]] = relationship(cascade="all, delete-orphan")


class GRNItem(Base):
    __tablename__ = "grn_items"

    grn_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grn_id: Mapped[int] = mapped_column(ForeignKey("grns.grn_id"), nullable=False)
    saree_id: Mapped[int] = mapped_column(ForeignKey("sarees.saree_id"), nullable=False)
    received_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    damaged_qty: Mapped[int] = mapped_column(Integer, default=0)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class JobWorkIssue(Base):
    __tablename__ = "job_work_issues"

    issue_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.vendor_id"), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    remarks: Mapped[str | None] = mapped_column(Text)
    items: Mapped[list["JobWorkIssueItem"]] = relationship(cascade="all, delete-orphan")


class JobWorkIssueItem(Base):
    __tablename__ = "job_work_issue_items"

    issue_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("job_work_issues.issue_id"), nullable=False)
    saree_id: Mapped[int] = mapped_column(ForeignKey("sarees.saree_id"), nullable=False)
    issued_qty: Mapped[int] = mapped_column(Integer, nullable=False)


class JobWorkReceipt(Base):
    __tablename__ = "job_work_receipts"

    receipt_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("job_work_issues.issue_id"), nullable=False)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.vendor_id"), nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    items: Mapped[list["JobWorkReceiptItem"]] = relationship(cascade="all, delete-orphan")


class JobWorkReceiptItem(Base):
    __tablename__ = "job_work_receipt_items"

    receipt_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("job_work_receipts.receipt_id"), nullable=False)
    saree_id: Mapped[int] = mapped_column(ForeignKey("sarees.saree_id"), nullable=False)
    received_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_qty: Mapped[int] = mapped_column(Integer, default=0)
    process_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)


class StockLedger(Base):
    __tablename__ = "stock_ledger"

    ledger_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    reference_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    saree_id: Mapped[int] = mapped_column(ForeignKey("sarees.saree_id"), nullable=False)
    qty_in: Mapped[int] = mapped_column(Integer, default=0)
    qty_out: Mapped[int] = mapped_column(Integer, default=0)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    remarks: Mapped[str | None] = mapped_column(Text)
