"""Reports UI."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTableWidget

from database.database import session_scope
from database.repositories.inventory import InventoryRepository
from ui.common import Page, fill_table


class ReportsPage(Page):
    def __init__(self) -> None:
        super().__init__("Reports")
        self.layout.addWidget(QLabel("Stock Report"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Saree Code", "Saree Name", "Current Stock"])
        self.table.setSortingEnabled(True)
        self.layout.addWidget(self.table)
        self.refresh()

    def refresh(self) -> None:
        with session_scope() as session:
            fill_table(self.table, InventoryRepository(session).stock_report())
