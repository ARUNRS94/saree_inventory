"""Main PySide6 window with ERP-style navigation and dashboard."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QTableWidget, QTableWidgetItem, QToolBar, QVBoxLayout, QWidget

from database.database import session_scope
from database.models.entities import StockLedger
from database.repositories.inventory import InventoryRepository
from services.inventory_service import InventoryService


class MainWindow(QMainWindow):
    """Application shell. UI reads summarized data from services only."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Saree Inventory & Job Work Management")
        self.resize(1200, 760)
        self._build_toolbar()
        self._build_dashboard()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        for label in ["Dashboard", "Suppliers", "Vendors", "Sarees", "Purchase Orders", "GRN", "Job Work", "Reports"]:
            toolbar.addAction(label)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

    def _build_dashboard(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 24px; font-weight: 600; margin: 8px;")
        layout.addWidget(title)

        with session_scope() as session:
            inventory = InventoryRepository(session)
            value = InventoryService(session).inventory_value()
            layout.addWidget(QLabel(f"Total Stock Quantity: {inventory.current_stock()}"))
            layout.addWidget(QLabel(f"Inventory Value: ₹ {value:,.2f}"))
            layout.addWidget(QLabel(f"Purchase Orders Pending: {inventory.pending_purchase_orders()}"))

            table = QTableWidget(0, 5)
            table.setHorizontalHeaderLabels(["Date", "Type", "Reference", "Qty In", "Qty Out"])
            for row, entry in enumerate(session.query(StockLedger).order_by(StockLedger.ledger_id.desc()).limit(20)):
                table.insertRow(row)
                for col, value in enumerate([entry.transaction_date, entry.transaction_type, entry.reference_no, entry.qty_in, entry.qty_out]):
                    table.setItem(row, col, QTableWidgetItem(str(value)))
            table.setSortingEnabled(True)
            layout.addWidget(table)

        self.setCentralWidget(container)
