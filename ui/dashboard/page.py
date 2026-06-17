"""Dashboard UI page."""
from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel, QTableWidget

from database.database import session_scope
from database.models.entities import StockLedger
from database.repositories.inventory import InventoryRepository
from services.inventory_service import InventoryService
from ui.common import Page, fill_table


class DashboardPage(Page):
    def __init__(self) -> None:
        super().__init__("Dashboard")
        with session_scope() as session:
            inventory = InventoryRepository(session)
            cards = QGridLayout()
            cards.addWidget(QLabel(f"Total Stock Quantity\n{inventory.current_stock()}"), 0, 0)
            cards.addWidget(QLabel(f"Inventory Value\n₹ {InventoryService(session).inventory_value():,.2f}"), 0, 1)
            cards.addWidget(QLabel(f"Purchase Orders Pending\n{inventory.pending_purchase_orders()}"), 0, 2)
            self.layout.addLayout(cards)
            self.table = QTableWidget(0, 5)
            self.table.setHorizontalHeaderLabels(["Date", "Type", "Reference", "Qty In", "Qty Out"])
            entries = session.query(StockLedger).order_by(StockLedger.ledger_id.desc()).limit(30)
            fill_table(self.table, ([e.transaction_date, e.transaction_type, e.reference_no, e.qty_in, e.qty_out] for e in entries))
            self.table.setSortingEnabled(True)
            self.layout.addWidget(self.table)
