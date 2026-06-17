"""Goods receipt note UI."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QPushButton, QSpinBox
from sqlalchemy import select

from database.database import session_scope
from database.models.entities import PurchaseOrder, Saree
from services.purchase_service import PurchaseService
from ui.common import Page, populate_combo


class GrnPage(Page):
    def __init__(self) -> None:
        super().__init__("Goods Receipt Against PO")
        form = QFormLayout()
        self.po = QComboBox()
        self.saree = QComboBox()
        self.pending = QLabel("Pending: 0")
        self.received = QSpinBox(); self.received.setRange(0, 100000)
        self.damaged = QSpinBox(); self.damaged.setRange(0, 100000)
        self.rate = QDoubleSpinBox(); self.rate.setRange(0, 10000000); self.rate.setDecimals(2)
        form.addRow("PO", self.po)
        form.addRow("Saree", self.saree)
        form.addRow(self.pending)
        form.addRow("Received Qty", self.received)
        form.addRow("Damaged Qty", self.damaged)
        form.addRow("Rate", self.rate)
        save = QPushButton("Save GRN")
        save.clicked.connect(self.save)
        form.addRow(save)
        self.layout.addLayout(form)
        self.po.currentIndexChanged.connect(self.update_pending)
        self.saree.currentIndexChanged.connect(self.update_pending)
        self.refresh()

    def refresh(self) -> None:
        with session_scope() as session:
            populate_combo(self.po, [(p.po_id, p.po_number) for p in session.scalars(select(PurchaseOrder).where(PurchaseOrder.status != "CLOSED").order_by(PurchaseOrder.po_id.desc()))])
            populate_combo(self.saree, [(s.saree_id, f"{s.saree_code} - {s.saree_name}") for s in session.scalars(select(Saree).order_by(Saree.saree_code))])
        self.update_pending()

    def update_pending(self) -> None:
        if self.po.currentData() is None or self.saree.currentData() is None:
            self.pending.setText("Pending: 0")
            return
        with session_scope() as session:
            qty = PurchaseService(session).pending_po_qty(int(self.po.currentData()), int(self.saree.currentData()))
            self.pending.setText(f"Pending: {qty}")

    def save(self) -> None:
        try:
            if self.po.currentData() is None or self.saree.currentData() is None:
                raise ValueError("Create an open PO and saree before saving a GRN.")
            with session_scope() as session:
                grn = PurchaseService(session).receive_grn(
                    int(self.po.currentData()),
                    [(int(self.saree.currentData()), self.received.value(), self.damaged.value(), Decimal(str(self.rate.value())))],
                )
                grn_number = grn.grn_number
            self.info(f"GRN {grn_number} saved and stock updated.")
            self.refresh()
        except Exception as exc:
            self.error(str(exc))
