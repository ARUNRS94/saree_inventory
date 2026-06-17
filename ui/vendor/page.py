"""Vendor master UI."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QLineEdit, QPushButton, QTableWidget
from sqlalchemy import select

from database.database import session_scope
from database.models.entities import Vendor
from services.master_service import MasterDataService
from ui.common import Page, fill_table


class VendorPage(Page):
    def __init__(self) -> None:
        super().__init__("Vendor Master")
        form = QFormLayout()
        self.name = QLineEdit()
        self.process = QComboBox()
        self.process.addItems(["Dyeing", "Stoning", "Finishing", "Printing", "Other"])
        self.phone = QLineEdit()
        form.addRow("Vendor Name *", self.name)
        form.addRow("Process Type *", self.process)
        form.addRow("Phone", self.phone)
        save = QPushButton("Add Vendor")
        save.clicked.connect(self.save)
        form.addRow(save)
        self.layout.addLayout(form)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Process", "Phone"])
        self.table.setSortingEnabled(True)
        self.layout.addWidget(self.table)
        self.refresh()

    def save(self) -> None:
        try:
            with session_scope() as session:
                MasterDataService(session).create_vendor(self.name.text(), self.process.currentText(), phone=self.phone.text())
            self.info("Vendor added successfully.")
            self.refresh()
        except Exception as exc:
            self.error(str(exc))

    def refresh(self) -> None:
        with session_scope() as session:
            vendors = session.scalars(select(Vendor).order_by(Vendor.vendor_name))
            fill_table(self.table, ([v.vendor_name, v.process_type, v.phone] for v in vendors))
