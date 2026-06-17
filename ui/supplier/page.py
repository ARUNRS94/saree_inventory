"""Contact master UI for RM vendors, Sub vendors and Customers."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget, QTextEdit

from database.database import session_scope
from database.models.entities import Supplier
from services.master_service import CONTACT_TYPES, MasterDataService
from ui.common import Page, fill_table


class SupplierPage(Page):
    def __init__(self) -> None:
        super().__init__("Contact Master")
        self.selected_id: int | None = None
        form = QFormLayout()
        self.name = QLineEdit(); self.contact_type = QComboBox(); self.contact = QLineEdit(); self.phone = QLineEdit(); self.gst = QLineEdit(); self.address = QTextEdit()
        self.contact_type.addItems(CONTACT_TYPES)
        form.addRow("Contact Name *", self.name); form.addRow("Type of Contact *", self.contact_type); form.addRow("Contact Person", self.contact); form.addRow("Phone", self.phone); form.addRow("GST No", self.gst); form.addRow("Address", self.address)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("Add Contact"); self.save_button.clicked.connect(self.save)
        clear = QPushButton("Clear"); clear.clicked.connect(self.clear_form)
        buttons.addWidget(self.save_button); buttons.addWidget(clear); form.addRow(buttons)
        self.layout.addLayout(form)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Type", "Contact", "Phone", "GST", "Address"])
        self.table.setColumnHidden(0, True); self.table.setSortingEnabled(True)
        self.table.cellDoubleClicked.connect(self.load_selected)
        self.layout.addWidget(self.table)
        self.refresh()

    def load_selected(self, row: int, _column: int) -> None:
        self.selected_id = int(self.table.item(row, 0).text())
        self.name.setText(self.table.item(row, 1).text())
        self.contact_type.setCurrentText(self.table.item(row, 2).text() or "RM vendor")
        self.contact.setText(self.table.item(row, 3).text()); self.phone.setText(self.table.item(row, 4).text()); self.gst.setText(self.table.item(row, 5).text()); self.address.setPlainText(self.table.item(row, 6).text())
        self.save_button.setText("Update Contact")

    def clear_form(self) -> None:
        self.selected_id = None
        for widget in [self.name, self.contact, self.phone, self.gst]:
            widget.clear()
        self.contact_type.setCurrentText("RM vendor")
        self.address.clear(); self.save_button.setText("Add Contact")

    def save(self) -> None:
        try:
            with session_scope() as session:
                if self.selected_id is None:
                    MasterDataService(session).create_contact(self.name.text(), self.contact_type.currentText(), contact_person=self.contact.text(), phone=self.phone.text(), gst_no=self.gst.text(), address=self.address.toPlainText())
                    message = "Contact added successfully."
                else:
                    contact = session.get(Supplier, self.selected_id)
                    if contact is None:
                        raise ValueError("Contact not found.")
                    if not self.name.text().strip():
                        raise ValueError("Contact name is required.")
                    contact.supplier_name = self.name.text().strip(); contact.contact_type = self.contact_type.currentText(); contact.contact_person = self.contact.text(); contact.phone = self.phone.text(); contact.gst_no = self.gst.text(); contact.address = self.address.toPlainText()
                    message = "Contact updated successfully."
            self.info(message); self.clear_form(); self.refresh()
        except Exception as exc:
            self.error(str(exc))

    def refresh(self) -> None:
        with session_scope() as session:
            rows = ([s.supplier_id, s.supplier_name, s.contact_type, s.contact_person, s.phone, s.gst_no, s.address] for s in MasterDataService(session).search_contacts())
            fill_table(self.table, rows)
