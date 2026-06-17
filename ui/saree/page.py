"""Saree master UI."""
from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLineEdit, QPushButton, QTableWidget

from database.database import session_scope
from services.master_service import MasterDataService
from ui.common import Page, fill_table


class SareePage(Page):
    def __init__(self) -> None:
        super().__init__("Saree Master")
        form = QFormLayout()
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.fabric = QLineEdit()
        self.design = QLineEdit()
        self.color = QLineEdit()
        form.addRow("Code *", self.code)
        form.addRow("Name *", self.name)
        form.addRow("Fabric", self.fabric)
        form.addRow("Design", self.design)
        form.addRow("Color", self.color)
        save = QPushButton("Add Saree")
        save.clicked.connect(self.save)
        form.addRow(save)
        self.layout.addLayout(form)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Fabric", "Design", "Color"])
        self.table.setSortingEnabled(True)
        self.layout.addWidget(self.table)
        self.refresh()

    def save(self) -> None:
        try:
            with session_scope() as session:
                MasterDataService(session).create_saree(
                    self.code.text(),
                    self.name.text(),
                    fabric=self.fabric.text(),
                    design_name=self.design.text(),
                    color=self.color.text(),
                )
            self.info("Saree added successfully.")
            self.refresh()
        except Exception as exc:
            self.error(str(exc))

    def refresh(self) -> None:
        with session_scope() as session:
            rows = ([s.saree_code, s.saree_name, s.fabric, s.design_name, s.color] for s in MasterDataService(session).search_sarees())
            fill_table(self.table, rows)
