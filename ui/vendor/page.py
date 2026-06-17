"""Vendor master UI with editable process type master and add/edit vendor support."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget
from sqlalchemy import select

from database.database import session_scope
from database.models.entities import Vendor, VendorProcessType
from services.master_service import MasterDataService
from ui.common import Page, fill_table, populate_combo


class VendorPage(Page):
    def __init__(self) -> None:
        super().__init__("Vendor Master")
        self.selected_id: int | None = None
        self.selected_process_id: int | None = None
        form = QFormLayout(); self.name = QLineEdit(); self.process = QComboBox(); self.phone = QLineEdit()
        form.addRow("Vendor Name *", self.name); form.addRow("Process Type *", self.process); form.addRow("Phone", self.phone)
        buttons = QHBoxLayout(); self.save_button = QPushButton("Add Vendor"); self.save_button.clicked.connect(self.save); clear = QPushButton("Clear"); clear.clicked.connect(self.clear_form); buttons.addWidget(self.save_button); buttons.addWidget(clear); form.addRow(buttons)
        self.layout.addLayout(form)

        process_form = QHBoxLayout(); self.new_process = QLineEdit(); self.new_process.setPlaceholderText("Process type, e.g. Embroidery"); self.process_button = QPushButton("Add Process Type"); self.process_button.clicked.connect(self.save_process_type); clear_process = QPushButton("Clear Process"); clear_process.clicked.connect(self.clear_process_form); process_form.addWidget(self.new_process); process_form.addWidget(self.process_button); process_form.addWidget(clear_process); self.layout.addLayout(process_form)
        self.process_table = QTableWidget(0, 2); self.process_table.setHorizontalHeaderLabels(["ID", "Process Type"]); self.process_table.setColumnHidden(0, True); self.process_table.setSortingEnabled(True); self.process_table.cellDoubleClicked.connect(self.load_process_selected); self.layout.addWidget(self.process_table)

        self.table = QTableWidget(0, 4); self.table.setHorizontalHeaderLabels(["ID", "Name", "Process", "Phone"]); self.table.setColumnHidden(0, True); self.table.setSortingEnabled(True); self.table.cellDoubleClicked.connect(self.load_selected); self.layout.addWidget(self.table)
        self.refresh()

    def load_selected(self, row: int, _column: int) -> None:
        self.selected_id = int(self.table.item(row, 0).text()); self.name.setText(self.table.item(row, 1).text()); self.process.setCurrentText(self.table.item(row, 2).text()); self.phone.setText(self.table.item(row, 3).text()); self.save_button.setText("Update Vendor")

    def clear_form(self) -> None:
        self.selected_id = None; self.name.clear(); self.phone.clear(); self.process.setCurrentIndex(0); self.save_button.setText("Add Vendor")

    def load_process_selected(self, row: int, _column: int) -> None:
        self.selected_process_id = int(self.process_table.item(row, 0).text())
        self.new_process.setText(self.process_table.item(row, 1).text())
        self.process_button.setText("Update Process Type")

    def clear_process_form(self) -> None:
        self.selected_process_id = None; self.new_process.clear(); self.process_button.setText("Add Process Type")

    def save_process_type(self) -> None:
        try:
            value = self.new_process.text().strip()
            if not value:
                raise ValueError("Process type is required.")
            with session_scope() as session:
                duplicate = session.scalar(select(VendorProcessType).where(VendorProcessType.process_type == value))
                if self.selected_process_id is None:
                    if duplicate is None:
                        session.add(VendorProcessType(process_type=value))
                    message = "Process type saved."
                else:
                    process_type = session.get(VendorProcessType, self.selected_process_id)
                    if process_type is None:
                        raise ValueError("Process type not found.")
                    old_value = process_type.process_type
                    if duplicate is not None and duplicate.process_type_id != self.selected_process_id:
                        raise ValueError("Process type already exists.")
                    process_type.process_type = value
                    for vendor in session.scalars(select(Vendor).where(Vendor.process_type == old_value)):
                        vendor.process_type = value
                    message = "Process type updated."
            self.info(message); self.clear_process_form(); self.refresh()
        except Exception as exc:
            self.error(str(exc))

    def save(self) -> None:
        try:
            with session_scope() as session:
                if self.selected_id is None:
                    if not self.process.currentText().strip(): raise ValueError("Create a vendor process type first.")
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
            process_types = list(session.scalars(select(VendorProcessType).where(VendorProcessType.is_active.is_(True)).order_by(VendorProcessType.process_type)))
            populate_combo(self.process, [(p.process_type, p.process_type) for p in process_types])
            fill_table(self.process_table, ([p.process_type_id, p.process_type] for p in process_types))
            vendors = session.scalars(select(Vendor).order_by(Vendor.vendor_name))
            fill_table(self.table, ([v.vendor_id, v.vendor_name, v.process_type, v.phone] for v in vendors))
