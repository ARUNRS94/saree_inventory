"""Saree master UI with add/edit support."""
from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget

from database.database import session_scope
from database.models.entities import Saree
from services.master_service import MasterDataService
from ui.common import Page, fill_table


class SareePage(Page):
    def __init__(self) -> None:
        super().__init__("Saree Master")
        self.selected_id: int | None = None
        form = QFormLayout(); self.code = QLineEdit(); self.name = QLineEdit(); self.fabric = QLineEdit(); self.design = QLineEdit(); self.color = QLineEdit()
        form.addRow("Code *", self.code); form.addRow("Name *", self.name); form.addRow("Fabric", self.fabric); form.addRow("Design", self.design); form.addRow("Color", self.color)
        buttons = QHBoxLayout(); self.save_button = QPushButton("Add Saree"); self.save_button.clicked.connect(self.save); clear = QPushButton("Clear"); clear.clicked.connect(self.clear_form); buttons.addWidget(self.save_button); buttons.addWidget(clear); form.addRow(buttons)
        self.layout.addLayout(form)
        self.table = QTableWidget(0, 6); self.table.setHorizontalHeaderLabels(["ID", "Code", "Name", "Fabric", "Design", "Color"]); self.table.setColumnHidden(0, True); self.table.setSortingEnabled(True); self.table.cellDoubleClicked.connect(self.load_selected); self.layout.addWidget(self.table)
        self.refresh()

    def load_selected(self, row: int, _column: int) -> None:
        self.selected_id = int(self.table.item(row, 0).text()); self.code.setText(self.table.item(row, 1).text()); self.name.setText(self.table.item(row, 2).text()); self.fabric.setText(self.table.item(row, 3).text()); self.design.setText(self.table.item(row, 4).text()); self.color.setText(self.table.item(row, 5).text()); self.save_button.setText("Update Saree")

    def clear_form(self) -> None:
        self.selected_id = None
        for widget in [self.code, self.name, self.fabric, self.design, self.color]: widget.clear()
        self.save_button.setText("Add Saree")

    def save(self) -> None:
        try:
            with session_scope() as session:
                if self.selected_id is None:
                    MasterDataService(session).create_saree(self.code.text(), self.name.text(), fabric=self.fabric.text(), design_name=self.design.text(), color=self.color.text()); message = "Saree added successfully."
                else:
                    saree = session.get(Saree, self.selected_id)
                    if saree is None: raise ValueError("Saree not found.")
                    if not self.code.text().strip() or not self.name.text().strip(): raise ValueError("Saree code and name are required.")
                    saree.saree_code = self.code.text().strip().upper(); saree.saree_name = self.name.text().strip(); saree.fabric = self.fabric.text(); saree.design_name = self.design.text(); saree.color = self.color.text(); message = "Saree updated successfully."
            self.info(message); self.clear_form(); self.refresh()
        except Exception as exc:
            self.error(str(exc))

    def refresh(self) -> None:
        with session_scope() as session:
            rows = ([s.saree_id, s.saree_code, s.saree_name, s.fabric, s.design_name, s.color] for s in MasterDataService(session).search_sarees())
            fill_table(self.table, rows)
