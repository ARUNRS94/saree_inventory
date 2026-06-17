"""Purchase order UI for RM vendor purchases and Sub vendor process orders."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.database import session_scope
from database.models.entities import PurchaseOrder, PurchaseOrderItem, Saree, Supplier
from services.purchase_service import PurchaseLine, PurchaseService
from ui.common import Page, fill_table, populate_combo


class PurchaseOrderPage(Page):
    def __init__(self) -> None:
        super().__init__("Purchase Orders")
        self.selected_po_id: int | None = None
        form = QFormLayout(); self.supplier = QComboBox(); self.stock_out_item = QComboBox(); self.saree = QComboBox(); self.quantity = QSpinBox(); self.quantity.setRange(1, 100000); self.rate = QDoubleSpinBox(); self.rate.setRange(0, 10000000); self.rate.setDecimals(2); self.amount = QLabel("0.00"); self.status = QComboBox(); self.status.addItems(["OPEN", "PARTIAL", "CLOSED"]); self.remarks = QLineEdit()
        form.addRow("RM/Sub Vendor", self.supplier); form.addRow("Stock Out Item (RM, for Sub vendor)", self.stock_out_item); form.addRow("Stock In Item", self.saree); form.addRow("Quantity", self.quantity); form.addRow("Rate / Process Charges", self.rate); form.addRow("Amount", self.amount); form.addRow("Status", self.status); form.addRow("Remarks", self.remarks)
        buttons = QHBoxLayout(); self.save_button = QPushButton("Create PO"); self.save_button.clicked.connect(self.save); clear = QPushButton("Clear"); clear.clicked.connect(self.clear_form); buttons.addWidget(self.save_button); buttons.addWidget(clear); form.addRow(buttons)
        self.layout.addLayout(form)
        self.table = QTableWidget(0, 14)
        self.table.setHorizontalHeaderLabels(["PO ID", "PO No", "Contact", "Type", "PO Date", "Expected", "Stock Out", "Stock In Code", "Stock In Name", "Ordered Qty", "Rate/Charges", "Amount", "Remarks", "Status"])
        self.table.setColumnHidden(0, True); self.table.setSortingEnabled(True); self.table.cellDoubleClicked.connect(self.load_selected); self.layout.addWidget(self.table)
        self.quantity.valueChanged.connect(self.recalculate); self.rate.valueChanged.connect(self.recalculate); self.supplier.currentIndexChanged.connect(self.update_contact_mode); self.refresh()

    def refresh(self) -> None:
        with session_scope() as session:
            contacts = session.scalars(select(Supplier).where(Supplier.contact_type.in_(["RM vendor", "Sub vendor"])).order_by(Supplier.supplier_name))
            populate_combo(self.supplier, [(s.supplier_id, f"{s.supplier_name} ({s.contact_type})") for s in contacts])
            populate_combo(self.stock_out_item, [(s.saree_id, f"{s.saree_code} - {s.saree_name}") for s in session.scalars(select(Saree).where(Saree.fabric == "RM").order_by(Saree.saree_code))])
            populate_combo(self.saree, [(s.saree_id, f"{s.saree_code} - {s.saree_name} ({s.fabric})") for s in session.scalars(select(Saree).order_by(Saree.saree_code))])
            pos = session.scalars(select(PurchaseOrder).options(selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.saree), selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.stock_out_saree), selectinload(PurchaseOrder.supplier)).order_by(PurchaseOrder.po_id.desc()))
            rows = []
            for po in pos:
                for item in po.items:
                    stock_out = f"{item.stock_out_saree.saree_code} - {item.stock_out_saree.saree_name}" if item.stock_out_saree else ""
                    rows.append([po.po_id, po.po_number, po.supplier.supplier_name, po.supplier.contact_type, po.po_date, po.expected_date, stock_out, item.saree.saree_code, item.saree.saree_name, item.ordered_qty, item.rate, item.amount, po.remarks, po.status])
                if not po.items:
                    rows.append([po.po_id, po.po_number, po.supplier.supplier_name, po.supplier.contact_type, po.po_date, po.expected_date, "", "", "", "", "", "", po.remarks, po.status])
            fill_table(self.table, rows)
        self.update_contact_mode(); self.recalculate()

    def selected_contact_type(self) -> str:
        text = self.supplier.currentText()
        return "Sub vendor" if "(Sub vendor)" in text else "RM vendor"

    def update_contact_mode(self) -> None:
        is_sub_vendor = self.selected_contact_type() == "Sub vendor"
        self.stock_out_item.setEnabled(is_sub_vendor)

    def recalculate(self) -> None:
        self.amount.setText(f"{self.quantity.value() * self.rate.value():,.2f}")

    def load_selected(self, row: int, _column: int) -> None:
        self.selected_po_id = int(self.table.item(row, 0).text()); self.remarks.setText(self.table.item(row, 12).text()); self.status.setCurrentText(self.table.item(row, 13).text()); self.save_button.setText("Update PO Status")

    def clear_form(self) -> None:
        self.selected_po_id = None; self.remarks.clear(); self.status.setCurrentText("OPEN"); self.save_button.setText("Create PO")

    def save(self) -> None:
        try:
            with session_scope() as session:
                if self.selected_po_id is None:
                    if self.supplier.currentData() is None or self.saree.currentData() is None: raise ValueError("Create contacts and items before creating a purchase order.")
                    stock_out_id = int(self.stock_out_item.currentData()) if self.selected_contact_type() == "Sub vendor" and self.stock_out_item.currentData() is not None else None
                    po = PurchaseService(session).create_po(int(self.supplier.currentData()), [PurchaseLine(int(self.saree.currentData()), self.quantity.value(), Decimal(str(self.rate.value())), stock_out_id)], remarks=self.remarks.text())
                    message = f"Purchase Order {po.po_number} created."
                else:
                    po = session.get(PurchaseOrder, self.selected_po_id)
                    if po is None: raise ValueError("Purchase order not found.")
                    po.status = self.status.currentText(); po.remarks = self.remarks.text() or po.remarks; message = f"Purchase Order {po.po_number} updated."
            self.info(message); self.clear_form(); self.refresh()
        except Exception as exc:
            self.error(str(exc))
