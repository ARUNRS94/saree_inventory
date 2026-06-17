"""Dashboard UI page with operational cards and summaries."""
from __future__ import annotations

from sqlalchemy import func, select
from PySide6.QtWidgets import QGridLayout, QLabel, QTableWidget

from database.database import session_scope
from database.models.entities import JobWorkIssue, JobWorkIssueItem, JobWorkReceipt, JobWorkReceiptItem, PurchaseOrder, Saree, StockLedger, Supplier, Vendor
from database.repositories.inventory import InventoryRepository
from services.inventory_service import InventoryService
from ui.common import Page, fill_table


class DashboardPage(Page):
    def __init__(self) -> None:
        super().__init__("Dashboard")
        with session_scope() as session:
            inventory = InventoryRepository(session)
            vendor_pending = self._vendor_pending_qty(session)
            cards = QGridLayout()
            card_texts = [
                f"Total Stock\n{inventory.current_stock()} pcs",
                f"Stock Value\n₹ {InventoryService(session).inventory_value():,.2f}",
                f"Pending POs\n{inventory.pending_purchase_orders()}",
                f"Vendor WIP Pending\n{vendor_pending} pcs",
                f"Saree Designs\n{session.scalar(select(func.count()).select_from(Saree)) or 0}",
                f"Suppliers / Vendors\n{session.scalar(select(func.count()).select_from(Supplier)) or 0} / {session.scalar(select(func.count()).select_from(Vendor)) or 0}",
            ]
            for index, text in enumerate(card_texts):
                card = QLabel(text)
                card.setProperty("card", True)
                cards.addWidget(card, index // 3, index % 3)
            self.layout.addLayout(cards)

            self.layout.addWidget(QLabel("Recent Stock Ledger"))
            self.ledger_table = QTableWidget(0, 6)
            self.ledger_table.setHorizontalHeaderLabels(["Date", "Type", "Reference", "Saree ID", "Qty In", "Qty Out"])
            entries = session.query(StockLedger).order_by(StockLedger.ledger_id.desc()).limit(30)
            fill_table(self.ledger_table, ([e.transaction_date, e.transaction_type, e.reference_no, e.saree_id, e.qty_in, e.qty_out] for e in entries))
            self.ledger_table.setSortingEnabled(True)
            self.layout.addWidget(self.ledger_table)

            self.layout.addWidget(QLabel("Current Stock Summary"))
            self.stock_table = QTableWidget(0, 3)
            self.stock_table.setHorizontalHeaderLabels(["Saree Code", "Saree Name", "Current Stock"])
            fill_table(self.stock_table, inventory.stock_report())
            self.stock_table.setSortingEnabled(True)
            self.layout.addWidget(self.stock_table)

    def _vendor_pending_qty(self, session) -> int:
        issued = session.scalar(select(func.coalesce(func.sum(JobWorkIssueItem.issued_qty), 0)).join(JobWorkIssue)) or 0
        received = session.scalar(select(func.coalesce(func.sum(JobWorkReceiptItem.received_qty + JobWorkReceiptItem.rejected_qty), 0)).join(JobWorkReceipt)) or 0
        return max(int(issued) - int(received), 0)
