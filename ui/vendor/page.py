"""Vendor master UI with add/edit support."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget
from sqlalchemy import select

from database.database import session_scope
from database.models.entities import Vendor
from services.master_service import MasterDataService
from ui.common import Page, fill_table


class VendorPage(Page):
    def __init__(self) -> None:
        super().__init__("Vendor Master")
        self.selected_id: int | None = None
        form = QFormLayout(); self.name = QLineEdit(); self.process = QComboBox(); self.process.addItems(["Dyeing", "Stoning", "Finishing", "Printing", "Other"]); self.phone = QLineEdit()
        form.addRow("Vendor Name *", self.name); form.addRow("Process Type *", self.process); form.addRow("Phone", self.phone)
        buttons = QHBoxLayout(); self.save_button = QPushButton("Add Vendor"); self.save_button.clicked.connect(self.save); clear = QPushButton("Clear"); clear.clicked.connect(self.clear_form); buttons.addWidget(self.save_button); buttons.addWidget(clear); form.addRow(buttons)
        self.layout.addLayout(form)
        self.table = QTableWidget(0, 4); self.table.setHorizontalHeaderLabels(["ID", "Name", "Process", "Phone"]); self.table.setColumnHidden(0, True); self.table.setSortingEnabled(True); self.table.cellDoubleClicked.connect(self.load_selected); self.layout.addWidget(self.table)
        self.refresh()

    def load_selected(self, row: int, _column: int) -> None:
        self.selected_id = int(self.table.item(row, 0).text()); self.name.setText(self.table.item(row, 1).text()); self.process.setCurrentText(self.table.item(row, 2).text()); self.phone.setText(self.table.item(row, 3).text()); self.save_button.setText("Update Vendor")

    def clear_form(self) -> None:
        self.selected_id = None; self.name.clear(); self.phone.clear(); self.process.setCurrentIndex(0); self.save_button.setText("Add Vendor")

    def save(self) -> None:
        try:
            with session_scope() as session:
                if self.selected_id is None:
                    MasterDataService(session).create_vendor(self.name.text(), self.process.currentText(), phone=self.phone.text()); message = "Vendor added successfully."
                else:
                    vendor = session.get(Vendor, self.selected_id)
                    if vendor is None: raise ValueError("Vendor not found.")
                    if not self.name.text().strip(): raise ValueError("Vendor name is required.")
                    vendor.vendor_name = self.name.text().strip(); vendor.process_type = self.process.currentText(); vendor.phone = self.phone.text(); message = "Vendor updated successfully."
            self.info(message); self.clear_form(); self.refresh()
        except Exception as exc:
            self.error(str(exc))

    def refresh(self) -> None:
        with session_scope() as session:
            vendors = session.scalars(select(Vendor).order_by(Vendor.vendor_name))
            fill_table(self.table, ([v.vendor_id, v.vendor_name, v.process_type, v.phone] for v in vendors))
