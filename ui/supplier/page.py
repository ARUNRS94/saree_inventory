"""Supplier master UI with add/edit support."""
from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget, QTextEdit

from database.database import session_scope
from database.models.entities import Supplier
from services.master_service import MasterDataService
from ui.common import Page, fill_table


class SupplierPage(Page):
    def __init__(self) -> None:
        super().__init__("Supplier Master")
        self.selected_id: int | None = None
        form = QFormLayout()
        self.name = QLineEdit(); self.contact = QLineEdit(); self.phone = QLineEdit(); self.gst = QLineEdit(); self.address = QTextEdit()
        form.addRow("Supplier Name *", self.name); form.addRow("Contact Person", self.contact); form.addRow("Phone", self.phone); form.addRow("GST No", self.gst); form.addRow("Address", self.address)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("Add Supplier"); self.save_button.clicked.connect(self.save)
        clear = QPushButton("Clear"); clear.clicked.connect(self.clear_form)
        buttons.addWidget(self.save_button); buttons.addWidget(clear); form.addRow(buttons)
        self.layout.addLayout(form)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Contact", "Phone", "GST", "Address"])
        self.table.setColumnHidden(0, True); self.table.setSortingEnabled(True)
        self.table.cellDoubleClicked.connect(self.load_selected)
        self.layout.addWidget(self.table)
        self.refresh()

    def load_selected(self, row: int, _column: int) -> None:
        self.selected_id = int(self.table.item(row, 0).text())
        self.name.setText(self.table.item(row, 1).text()); self.contact.setText(self.table.item(row, 2).text()); self.phone.setText(self.table.item(row, 3).text()); self.gst.setText(self.table.item(row, 4).text()); self.address.setPlainText(self.table.item(row, 5).text())
        self.save_button.setText("Update Supplier")

    def clear_form(self) -> None:
        self.selected_id = None
        for widget in [self.name, self.contact, self.phone, self.gst]:
            widget.clear()
        self.address.clear(); self.save_button.setText("Add Supplier")

    def save(self) -> None:
        try:
            with session_scope() as session:
                if self.selected_id is None:
                    MasterDataService(session).create_supplier(self.name.text(), contact_person=self.contact.text(), phone=self.phone.text(), gst_no=self.gst.text(), address=self.address.toPlainText())
                    message = "Supplier added successfully."
                else:
                    supplier = session.get(Supplier, self.selected_id)
                    if supplier is None:
                        raise ValueError("Supplier not found.")
                    if not self.name.text().strip():
                        raise ValueError("Supplier name is required.")
                    supplier.supplier_name = self.name.text().strip(); supplier.contact_person = self.contact.text(); supplier.phone = self.phone.text(); supplier.gst_no = self.gst.text(); supplier.address = self.address.toPlainText()
                    message = "Supplier updated successfully."
            self.info(message); self.clear_form(); self.refresh()
        except Exception as exc:
            self.error(str(exc))

    def refresh(self) -> None:
        with session_scope() as session:
            rows = ([s.supplier_id, s.supplier_name, s.contact_person, s.phone, s.gst_no, s.address] for s in MasterDataService(session).search_suppliers())
            fill_table(self.table, rows)
