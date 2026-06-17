"""Purchase order UI."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget
from sqlalchemy import select

from database.database import session_scope
from database.models.entities import PurchaseOrder, Saree, Supplier
from services.purchase_service import PurchaseLine, PurchaseService
from ui.common import Page, fill_table, populate_combo


class PurchaseOrderPage(Page):
    def __init__(self) -> None:
        super().__init__("Create Purchase Order")
        form = QFormLayout()
        self.supplier = QComboBox()
        self.saree = QComboBox()
        self.quantity = QSpinBox(); self.quantity.setRange(1, 100000)
        self.rate = QDoubleSpinBox(); self.rate.setRange(0, 10000000); self.rate.setDecimals(2)
        self.amount = QLabel("0.00")
        self.remarks = QLineEdit()
        form.addRow("Supplier", self.supplier)
        form.addRow("Saree", self.saree)
        form.addRow("Quantity", self.quantity)
        form.addRow("Rate", self.rate)
        form.addRow("Amount", self.amount)
        form.addRow("Remarks", self.remarks)
        save = QPushButton("Create PO")
        save.clicked.connect(self.save)
        form.addRow(save)
        self.layout.addLayout(form)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["PO No", "Supplier Id", "Date", "Status"])
        self.layout.addWidget(self.table)
        self.quantity.valueChanged.connect(self.recalculate)
        self.rate.valueChanged.connect(self.recalculate)
        self.refresh()

    def refresh(self) -> None:
        with session_scope() as session:
            populate_combo(self.supplier, [(s.supplier_id, s.supplier_name) for s in session.scalars(select(Supplier).order_by(Supplier.supplier_name))])
            populate_combo(self.saree, [(s.saree_id, f"{s.saree_code} - {s.saree_name}") for s in session.scalars(select(Saree).order_by(Saree.saree_code))])
            pos = session.scalars(select(PurchaseOrder).order_by(PurchaseOrder.po_id.desc()))
            fill_table(self.table, ([p.po_number, p.supplier_id, p.po_date, p.status] for p in pos))
        self.recalculate()

    def recalculate(self) -> None:
        self.amount.setText(f"{self.quantity.value() * self.rate.value():,.2f}")

    def save(self) -> None:
        try:
            if self.supplier.currentData() is None or self.saree.currentData() is None:
                raise ValueError("Create a supplier and saree before creating a purchase order.")
            with session_scope() as session:
                po = PurchaseService(session).create_po(
                    int(self.supplier.currentData()),
                    [PurchaseLine(int(self.saree.currentData()), self.quantity.value(), Decimal(str(self.rate.value())))],
                    remarks=self.remarks.text(),
                )
                po_number = po.po_number
            self.info(f"Purchase Order {po_number} created.")
            self.refresh()
        except Exception as exc:
            self.error(str(exc))
