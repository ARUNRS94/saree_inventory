"""Enhanced reports UI for inventory, purchases, vendor WIP and valuation."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from PySide6.QtWidgets import QGridLayout, QLabel, QTabWidget, QTableWidget, QVBoxLayout, QWidget

from database.database import session_scope
from database.models.entities import JobWorkIssue, JobWorkIssueItem, JobWorkReceipt, JobWorkReceiptItem, PurchaseOrder, PurchaseOrderItem, Saree, Supplier, Vendor
from database.repositories.inventory import InventoryRepository
from ui.common import Page, fill_table


class ReportsPage(Page):
    def __init__(self) -> None:
        super().__init__("Reports")
        self.summary_cards = QGridLayout()
        self.layout.addLayout(self.summary_cards)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(False)
        self.layout.addWidget(self.tabs)
        self.stock_table = self._add_table_tab("Stock Report", ["Saree Code", "Saree Name", "Current Stock"])
        self.purchase_table = self._add_table_tab("Purchase Report", ["PO Number", "Supplier", "Date", "Value", "Status"])
        self.vendor_wip_table = self._add_table_tab("Vendor WIP", ["Vendor", "Issued Qty", "Received/Rejected Qty", "Pending Qty"])
        self.valuation_table = self._add_table_tab("Inventory Valuation", ["Saree", "Stock", "Latest Rate", "Value"])
        self.refresh()

    def _add_table_tab(self, title: str, headers: list[str]) -> QTableWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel(title))
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSortingEnabled(True)
        layout.addWidget(table)
        self.tabs.addTab(tab, title)
        return table

    def refresh(self) -> None:
        with session_scope() as session:
            inventory = InventoryRepository(session)
            stock_rows = inventory.stock_report()
            purchase_rows = self._purchase_rows(session)
            vendor_wip_rows = self._vendor_wip_rows(session)
            valuation_rows = self._valuation_rows(session, inventory)
            fill_table(self.stock_table, stock_rows)
            fill_table(self.purchase_table, purchase_rows)
            fill_table(self.vendor_wip_table, vendor_wip_rows)
            fill_table(self.valuation_table, valuation_rows)
            self._refresh_summary_cards(stock_rows, purchase_rows, vendor_wip_rows, valuation_rows)

    def _refresh_summary_cards(
        self,
        stock_rows: list[tuple[str, str, int]],
        purchase_rows: list[list[object]],
        vendor_wip_rows: list[list[object]],
        valuation_rows: list[list[object]],
    ) -> None:
        while self.summary_cards.count():
            item = self.summary_cards.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        total_stock = sum(row[2] for row in stock_rows)
        total_purchase_value = sum(Decimal(str(row[3] or 0)) for row in purchase_rows)
        total_pending_wip = sum(int(row[3]) for row in vendor_wip_rows)
        total_inventory_value = sum(Decimal(str(row[3] or 0)) for row in valuation_rows)
        cards = [
            ("Total Stock", f"{total_stock} pcs"),
            ("Inventory Value", f"₹ {total_inventory_value:,.2f}"),
            ("PO Value", f"₹ {total_purchase_value:,.2f}"),
            ("Vendor WIP Pending", f"{total_pending_wip} pcs"),
        ]
        for index, (title, value) in enumerate(cards):
            card = QLabel(f"{title}\n{value}")
            card.setProperty("card", True)
            self.summary_cards.addWidget(card, 0, index)

    def _purchase_rows(self, session) -> list[list[object]]:
        amount = func.coalesce(func.sum(PurchaseOrderItem.amount), 0)
        stmt = (
            select(PurchaseOrder.po_number, Supplier.supplier_name, PurchaseOrder.po_date, amount, PurchaseOrder.status)
            .join(Supplier)
            .outerjoin(PurchaseOrderItem)
            .group_by(PurchaseOrder.po_id)
            .order_by(PurchaseOrder.po_date.desc(), PurchaseOrder.po_id.desc())
        )
        return [[po_no, supplier, po_date, value, status] for po_no, supplier, po_date, value, status in session.execute(stmt)]

    def _vendor_wip_rows(self, session) -> list[list[object]]:
        rows: list[list[object]] = []
        for vendor in session.scalars(select(Vendor).order_by(Vendor.vendor_name)):
            issued = session.scalar(select(func.coalesce(func.sum(JobWorkIssueItem.issued_qty), 0)).join(JobWorkIssue).where(JobWorkIssue.vendor_id == vendor.vendor_id)) or 0
            received = session.scalar(select(func.coalesce(func.sum(JobWorkReceiptItem.received_qty + JobWorkReceiptItem.rejected_qty), 0)).join(JobWorkReceipt).where(JobWorkReceipt.vendor_id == vendor.vendor_id)) or 0
            rows.append([vendor.vendor_name, int(issued), int(received), max(int(issued) - int(received), 0)])
        return rows

    def _valuation_rows(self, session, inventory: InventoryRepository) -> list[list[object]]:
        rows: list[list[object]] = []
        for _saree_id, code, name, stock, rate, value in inventory.inventory_valuation_rows():
            rows.append([f"{code} - {name}", stock, rate, value])
        return rows
