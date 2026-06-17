"""Item master UI with RM, Sub process and FG item types."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget

from database.database import session_scope
from database.models.entities import Saree
from services.master_service import ITEM_TYPES, MasterDataService
from ui.common import Page, fill_table


class SareePage(Page):
    def __init__(self) -> None:
        super().__init__("Item Master")
        self.selected_id: int | None = None
        form = QFormLayout(); self.code = QLineEdit(); self.name = QLineEdit(); self.item_type = QComboBox(); self.remarks = QLineEdit(); self.color = QLineEdit()
        self.item_type.addItems(ITEM_TYPES)
        form.addRow("Code *", self.code); form.addRow("Name *", self.name); form.addRow("Type *", self.item_type); form.addRow("Remarks", self.remarks); form.addRow("Color", self.color)
        buttons = QHBoxLayout(); self.save_button = QPushButton("Add Item"); self.save_button.clicked.connect(self.save); clear = QPushButton("Clear"); clear.clicked.connect(self.clear_form); buttons.addWidget(self.save_button); buttons.addWidget(clear); form.addRow(buttons)
        self.layout.addLayout(form)
        self.table = QTableWidget(0, 6); self.table.setHorizontalHeaderLabels(["ID", "Code", "Name", "Type", "Remarks", "Color"]); self.table.setColumnHidden(0, True); self.table.setSortingEnabled(True); self.table.cellDoubleClicked.connect(self.load_selected); self.layout.addWidget(self.table)
        self.refresh()

    def load_selected(self, row: int, _column: int) -> None:
        self.selected_id = int(self.table.item(row, 0).text()); self.code.setText(self.table.item(row, 1).text()); self.name.setText(self.table.item(row, 2).text()); self.item_type.setCurrentText(self.table.item(row, 3).text() or "FG"); self.remarks.setText(self.table.item(row, 4).text()); self.color.setText(self.table.item(row, 5).text()); self.save_button.setText("Update Item")

    def clear_form(self) -> None:
        self.selected_id = None
        for widget in [self.code, self.name, self.remarks, self.color]: widget.clear()
        self.item_type.setCurrentText("FG")
        self.save_button.setText("Add Item")

    def save(self) -> None:
        try:
            with session_scope() as session:
                if self.selected_id is None:
                    MasterDataService(session).create_saree(self.code.text(), self.name.text(), fabric=self.item_type.currentText(), design_name=self.remarks.text(), color=self.color.text()); message = "Item added successfully."
                else:
                    item = session.get(Saree, self.selected_id)
                    if item is None: raise ValueError("Item not found.")
                    if not self.code.text().strip() or not self.name.text().strip(): raise ValueError("Item code and name are required.")
                    item.saree_code = self.code.text().strip().upper(); item.saree_name = self.name.text().strip(); item.fabric = self.item_type.currentText(); item.design_name = self.remarks.text(); item.color = self.color.text(); message = "Item updated successfully."
            self.info(message); self.clear_form(); self.refresh()
        except Exception as exc:
            self.error(str(exc))

    def refresh(self) -> None:
        with session_scope() as session:
            rows = ([s.saree_id, s.saree_code, s.saree_name, s.fabric, s.design_name, s.color] for s in MasterDataService(session).search_sarees())
            fill_table(self.table, rows)
