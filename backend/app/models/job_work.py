from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class JobWorkIssue(Base):
    __tablename__ = "job_work_issues"

    issue_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.vendor_id"), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    remarks: Mapped[str | None] = mapped_column(Text)

    vendor: Mapped["Vendor"] = relationship()
    items: Mapped[list["JobWorkIssueItem"]] = relationship(cascade="all, delete-orphan")


class JobWorkIssueItem(Base):
    __tablename__ = "job_work_issue_items"

    issue_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("job_work_issues.issue_id"), nullable=False)
    saree_id: Mapped[int] = mapped_column(ForeignKey("sarees.saree_id"), nullable=False)
    issued_qty: Mapped[int] = mapped_column(Integer, nullable=False)

    saree: Mapped["Saree"] = relationship()


class JobWorkReceipt(Base):
    __tablename__ = "job_work_receipts"

    receipt_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("job_work_issues.issue_id"), nullable=False)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.vendor_id"), nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)

    issue: Mapped[JobWorkIssue] = relationship()
    vendor: Mapped["Vendor"] = relationship()
    items: Mapped[list["JobWorkReceiptItem"]] = relationship(cascade="all, delete-orphan")


class JobWorkReceiptItem(Base):
    __tablename__ = "job_work_receipt_items"

    receipt_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("job_work_receipts.receipt_id"), nullable=False)
    saree_id: Mapped[int] = mapped_column(ForeignKey("sarees.saree_id"), nullable=False)
    received_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_qty: Mapped[int] = mapped_column(Integer, default=0)
    process_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    saree: Mapped["Saree"] = relationship()
