from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


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

    saree: Mapped["Saree"] = relationship()
