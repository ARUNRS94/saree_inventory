"""Dashboard UI page with operational cards and stock summaries."""
from __future__ import annotations

from sqlalchemy import func, select
from PySide6.QtWidgets import QGridLayout, QLabel, QTableWidget

from database.database import session_scope
from database.models.entities import Saree, StockLedger, Supplier
from database.repositories.inventory import InventoryRepository
from services.inventory_service import InventoryService
from ui.common import Page, fill_table


class DashboardPage(Page):
    def __init__(self) -> None:
        super().__init__("Dashboard")
        with session_scope() as session:
            inventory = InventoryRepository(session)
            stock_types = inventory.stock_by_item_type()
            cards = QGridLayout()
            card_texts = [
                f"RM Stock\n{stock_types.get('RM', 0)} pcs",
                f"WIP Stock\n{stock_types.get('Sub process', 0)} pcs",
                f"FG Stock\n{stock_types.get('FG', 0)} pcs",
                f"Stock Value\nRs. {InventoryService(session).inventory_value():,.2f}",
                f"Pending POs\n{inventory.pending_purchase_orders()}",
                f"Contacts / Items\n{session.scalar(select(func.count()).select_from(Supplier)) or 0} / {session.scalar(select(func.count()).select_from(Saree)) or 0}",
            ]
            for index, text in enumerate(card_texts):
                card = QLabel(text)
                card.setProperty("card", True)
                cards.addWidget(card, index // 3, index % 3)
            self.layout.addLayout(cards)

            self.layout.addWidget(QLabel("Recent Stock Ledger"))
            self.ledger_table = QTableWidget(0, 6)
            self.ledger_table.setHorizontalHeaderLabels(["Date", "Type", "Reference", "Item ID", "Qty In", "Qty Out"])
            entries = session.query(StockLedger).order_by(StockLedger.ledger_id.desc()).limit(30)
            fill_table(self.ledger_table, ([e.transaction_date, e.transaction_type, e.reference_no, e.saree_id, e.qty_in, e.qty_out] for e in entries))
            self.ledger_table.setSortingEnabled(True)
            self.layout.addWidget(self.ledger_table)

            self.layout.addWidget(QLabel("Current Stock Summary"))
            self.stock_table = QTableWidget(0, 4)
            self.stock_table.setHorizontalHeaderLabels(["Item Code", "Item Name", "Type", "Current Stock"])
            fill_table(self.stock_table, inventory.stock_report())
            self.stock_table.setSortingEnabled(True)
            self.layout.addWidget(self.stock_table)
