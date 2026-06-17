"""Supplier master UI."""
from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLineEdit, QPushButton, QTableWidget, QTextEdit

from database.database import session_scope
from services.master_service import MasterDataService
from ui.common import Page, fill_table


class SupplierPage(Page):
    def __init__(self) -> None:
        super().__init__("Supplier Master")
        form = QFormLayout()
        self.name = QLineEdit()
        self.contact = QLineEdit()
        self.phone = QLineEdit()
        self.gst = QLineEdit()
        self.address = QTextEdit()
        form.addRow("Supplier Name *", self.name)
        form.addRow("Contact Person", self.contact)
        form.addRow("Phone", self.phone)
        form.addRow("GST No", self.gst)
        form.addRow("Address", self.address)
        save = QPushButton("Add Supplier")
        save.clicked.connect(self.save)
        form.addRow(save)
        self.layout.addLayout(form)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Contact", "Phone", "GST", "Address"])
        self.table.setSortingEnabled(True)
        self.layout.addWidget(self.table)
        self.refresh()

    def save(self) -> None:
        try:
            with session_scope() as session:
                MasterDataService(session).create_supplier(
                    self.name.text(),
                    contact_person=self.contact.text(),
                    phone=self.phone.text(),
                    gst_no=self.gst.text(),
                    address=self.address.toPlainText(),
                )
            self.info("Supplier added successfully.")
            self.refresh()
        except Exception as exc:
            self.error(str(exc))

    def refresh(self) -> None:
        with session_scope() as session:
            rows = ([s.supplier_name, s.contact_person, s.phone, s.gst_no, s.address] for s in MasterDataService(session).search_suppliers())
            fill_table(self.table, rows)
