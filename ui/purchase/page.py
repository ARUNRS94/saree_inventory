"""Purchase order UI for RM vendor purchases and Sub vendor process orders."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget
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
        form = QFormLayout(); self.supplier = QComboBox(); self.stock_out_item = QComboBox(); self.saree = QComboBox(); self.target_fg = QComboBox(); self.quantity = QSpinBox(); self.quantity.setRange(1, 100000); self.rate = QDoubleSpinBox(); self.rate.setRange(0, 10000000); self.rate.setDecimals(2); self.amount = QLabel("0.00"); self.status = QComboBox(); self.status.addItems(["OPEN", "PARTIAL", "CLOSED"]); self.remarks = QLineEdit()
        form.addRow("RM/Sub Vendor", self.supplier); form.addRow("Stock Out Item (RM/FG, for Sub vendor)", self.stock_out_item); form.addRow("Stock In Item", self.saree); form.addRow("Target FG (for Sub vendor GRN)", self.target_fg); form.addRow("Quantity", self.quantity); form.addRow("Rate / Process Charges", self.rate); form.addRow("Amount", self.amount); form.addRow("Status", self.status); form.addRow("Remarks", self.remarks)
        buttons = QHBoxLayout(); self.save_button = QPushButton("Create PO"); self.save_button.clicked.connect(self.save); self.cancel_button = QPushButton("Cancel PO"); self.cancel_button.clicked.connect(self.cancel_po); self.cancel_button.setEnabled(False); clear = QPushButton("Clear"); clear.clicked.connect(self.clear_form); buttons.addWidget(self.save_button); buttons.addWidget(self.cancel_button); buttons.addWidget(clear); form.addRow(buttons)
        self.layout.addLayout(form)
        self.table = QTableWidget(0, 16)
        self.table.setHorizontalHeaderLabels(["PO ID", "PO No", "Contact", "Type", "PO Date", "Expected", "Stock Out", "Stock In Code", "Stock In Name", "Target FG Code", "Target FG Name", "Ordered Qty", "Rate/Charges", "Amount", "Remarks", "Status"])
        self.table.setColumnHidden(0, True); self.table.setSortingEnabled(True); self.table.cellDoubleClicked.connect(self.load_selected); self.layout.addWidget(self.table)
        self.quantity.valueChanged.connect(self.recalculate); self.rate.valueChanged.connect(self.recalculate); self.supplier.currentIndexChanged.connect(self.update_contact_mode); self.refresh()

    def refresh(self) -> None:
        with session_scope() as session:
            contacts = session.scalars(select(Supplier).where(Supplier.contact_type.in_(["RM vendor", "Sub vendor"])).order_by(Supplier.supplier_name))
            populate_combo(self.supplier, [(s.supplier_id, f"{s.supplier_name} ({s.contact_type})") for s in contacts])
            populate_combo(self.stock_out_item, [(s.saree_id, f"{s.saree_code} - {s.saree_name} ({s.fabric})") for s in session.scalars(select(Saree).where(Saree.fabric.in_(["RM", "FG"])).order_by(Saree.fabric, Saree.saree_code))])
            populate_combo(self.target_fg, [(s.saree_id, f"{s.saree_code} - {s.saree_name}") for s in session.scalars(select(Saree).where(Saree.fabric == "FG").order_by(Saree.saree_code))])
            self._populate_stock_in_items(session)
            pos = session.scalars(select(PurchaseOrder).options(selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.saree), selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.stock_out_saree), selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.target_fg_saree), selectinload(PurchaseOrder.supplier)).order_by(PurchaseOrder.po_id.desc()))
            rows = []
            for po in pos:
                for item in po.items:
                    stock_out = f"{item.stock_out_saree.saree_code} - {item.stock_out_saree.saree_name}" if item.stock_out_saree else ""
                    target_fg_code = item.target_fg_saree.saree_code if item.target_fg_saree else ""
                    target_fg_name = item.target_fg_saree.saree_name if item.target_fg_saree else ""
                    rows.append([po.po_id, po.po_number, po.supplier.supplier_name, po.supplier.contact_type, po.po_date, po.expected_date, stock_out, item.saree.saree_code, item.saree.saree_name, target_fg_code, target_fg_name, item.ordered_qty, item.rate, item.amount, po.remarks, po.status])
                if not po.items:
                    rows.append([po.po_id, po.po_number, po.supplier.supplier_name, po.supplier.contact_type, po.po_date, po.expected_date, "", "", "", "", "", "", "", "", po.remarks, po.status])
            fill_table(self.table, rows)
        self.update_contact_mode(); self.recalculate()

    def selected_contact_type(self) -> str:
        text = self.supplier.currentText()
        return "Sub vendor" if "(Sub vendor)" in text else "RM vendor"

    def _populate_stock_in_items(self, session) -> None:
        item_type = "Sub process" if self.selected_contact_type() == "Sub vendor" else "RM"
        populate_combo(self.saree, [(s.saree_id, f"{s.saree_code} - {s.saree_name} ({s.fabric})") for s in session.scalars(select(Saree).where(Saree.fabric == item_type).order_by(Saree.saree_code))])

    def update_contact_mode(self) -> None:
        is_sub_vendor = self.selected_contact_type() == "Sub vendor"
        self.stock_out_item.setEnabled(is_sub_vendor)
        self.target_fg.setEnabled(is_sub_vendor)
        with session_scope() as session:
            self._populate_stock_in_items(session)

    def recalculate(self) -> None:
        self.amount.setText(f"{self.quantity.value() * self.rate.value():,.2f}")

    def load_selected(self, row: int, _column: int) -> None:
        status = self.table.item(row, 15).text(); self.selected_po_id = int(self.table.item(row, 0).text()); self.remarks.setText(self.table.item(row, 14).text()); self.status.setCurrentText(status); self.save_button.setText("Update PO Status"); self.save_button.setEnabled(status != "CANCELLED"); self.cancel_button.setEnabled(status not in ["CLOSED", "CANCELLED"])

    def clear_form(self) -> None:
        self.selected_po_id = None; self.remarks.clear(); self.status.setCurrentText("OPEN"); self.save_button.setText("Create PO"); self.save_button.setEnabled(True); self.cancel_button.setEnabled(False)

    def save(self) -> None:
        try:
            with session_scope() as session:
                if self.selected_po_id is None:
                    if self.supplier.currentData() is None or self.saree.currentData() is None: raise ValueError("Create contacts and items before creating a purchase order.")
                    if not self.confirm("Create Purchase Order", "Create this purchase order and post stock movements?"):
                        return
                    is_sub_vendor = self.selected_contact_type() == "Sub vendor"
                    stock_out_id = int(self.stock_out_item.currentData()) if is_sub_vendor and self.stock_out_item.currentData() is not None else None
                    target_fg_id = int(self.target_fg.currentData()) if is_sub_vendor and self.target_fg.currentData() is not None else None
                    po = PurchaseService(session).create_po(int(self.supplier.currentData()), [PurchaseLine(int(self.saree.currentData()), self.quantity.value(), Decimal(str(self.rate.value())), stock_out_id, target_fg_id)], remarks=self.remarks.text())
                    message = f"Purchase Order {po.po_number} created."
                else:
                    po = session.get(PurchaseOrder, self.selected_po_id)
                    if po is None: raise ValueError("Purchase order not found.")
                    po.status = self.status.currentText(); po.remarks = self.remarks.text() or po.remarks; message = f"Purchase Order {po.po_number} updated."
            self.info(message); self.clear_form(); self.refresh()
        except Exception as exc:
            self.error(str(exc))

    def confirm(self, title: str, message: str) -> bool:
        return QMessageBox.question(self, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def cancel_po(self) -> None:
        try:
            if self.selected_po_id is None:
                raise ValueError("Select a purchase order to cancel.")
            if not self.confirm("Cancel Purchase Order", "Cancel this PO and reverse any Sub vendor WIP/stock issue movements?"):
                return
            with session_scope() as session:
                po = PurchaseService(session).cancel_po(self.selected_po_id, remarks=self.remarks.text())
                message = f"Purchase Order {po.po_number} cancelled."
            self.info(message); self.clear_form(); self.refresh()
        except Exception as exc:
            self.error(str(exc))
