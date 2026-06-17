"""Reports UI for stock, purchases, vendor WIP and valuation."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QTabWidget, QTableWidget, QVBoxLayout, QWidget

from database.database import session_scope
from database.models.entities import GRN, GRNItem, PurchaseOrder, PurchaseOrderItem, Supplier
from database.repositories.inventory import InventoryRepository
from ui.common import Page, fill_table, populate_combo


class ReportsPage(Page):
    def __init__(self) -> None:
        super().__init__("Reports")
        self.summary_cards = QGridLayout()
        self.layout.addLayout(self.summary_cards)
        self.vendor_filter = QComboBox()
        self.vendor_filter.currentIndexChanged.connect(self.refresh)
        self.layout.addWidget(QLabel("Vendor/Customer Filter"))
        self.layout.addWidget(self.vendor_filter)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(False)
        self.layout.addWidget(self.tabs)
        self.stock_table = self._add_table_tab("Stock Report", ["Item Code", "Item Name", "Type", "Current Stock"])
        self.purchase_table = self._add_table_tab("Purchase Report", ["PO Number", "Vendor", "Type", "Date", "Purchase Qty", "Value", "Status"])
        self.vendor_wip_table = self._add_table_tab("Sub Vendor WIP", ["Sub Vendor", "Issued Qty", "Received Qty", "Pending Qty"])
        self.valuation_table = self._add_table_tab("Inventory Valuation", ["Item", "Stock", "Latest Rate", "Value"])
        self.refresh_filters()
        self.refresh()

    def refresh_filters(self) -> None:
        current = self.vendor_filter.currentData()
        with session_scope() as session:
            rows = [(0, "All Contacts"), *[(c.supplier_id, f"{c.supplier_name} ({c.contact_type})") for c in session.scalars(select(Supplier).order_by(Supplier.supplier_name))]]
        populate_combo(self.vendor_filter, rows)
        if current is not None:
            index = self.vendor_filter.findData(current)
            if index >= 0:
                self.vendor_filter.setCurrentIndex(index)

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
            contact_id = int(self.vendor_filter.currentData() or 0)
            stock_rows = inventory.stock_report()
            purchase_rows = self._purchase_rows(session, contact_id)
            vendor_wip_rows = self._vendor_wip_rows(session, contact_id)
            valuation_rows = self._valuation_rows(inventory)
            fill_table(self.stock_table, stock_rows)
            fill_table(self.purchase_table, purchase_rows)
            fill_table(self.vendor_wip_table, vendor_wip_rows)
            fill_table(self.valuation_table, valuation_rows)
            self._refresh_summary_cards(stock_rows, purchase_rows, vendor_wip_rows, valuation_rows)

    def _refresh_summary_cards(self, stock_rows, purchase_rows, vendor_wip_rows, valuation_rows) -> None:
        while self.summary_cards.count():
            item = self.summary_cards.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        total_stock = sum(row[3] for row in stock_rows)
        total_purchase_qty = sum(int(row[4] or 0) for row in purchase_rows)
        total_pending_wip = sum(int(row[3]) for row in vendor_wip_rows)
        total_inventory_value = sum(Decimal(str(row[3] or 0)) for row in valuation_rows)
        cards = [("Total Stock", f"{total_stock} pcs"), ("Inventory Value", f"₹ {total_inventory_value:,.2f}"), ("Purchase Qty", f"{total_purchase_qty} pcs"), ("Sub Vendor WIP", f"{total_pending_wip} pcs")]
        for index, (title, value) in enumerate(cards):
            card = QLabel(f"{title}\n{value}")
            card.setProperty("card", True)
            self.summary_cards.addWidget(card, 0, index)

    def _purchase_rows(self, session, contact_id: int = 0) -> list[list[object]]:
        amount = func.coalesce(func.sum(PurchaseOrderItem.amount), 0)
        qty = func.coalesce(func.sum(PurchaseOrderItem.ordered_qty), 0)
        stmt = (
            select(PurchaseOrder.po_number, Supplier.supplier_name, Supplier.contact_type, PurchaseOrder.po_date, qty, amount, PurchaseOrder.status)
            .join(Supplier)
            .outerjoin(PurchaseOrderItem)
            .group_by(PurchaseOrder.po_id)
            .order_by(PurchaseOrder.po_date.desc(), PurchaseOrder.po_id.desc())
        )
        if contact_id:
            stmt = stmt.where(PurchaseOrder.supplier_id == contact_id)
        return [[po_no, supplier, contact_type, po_date, int(purchase_qty or 0), value, status] for po_no, supplier, contact_type, po_date, purchase_qty, value, status in session.execute(stmt)]

    def _vendor_wip_rows(self, session, contact_id: int = 0) -> list[list[object]]:
        rows: list[list[object]] = []
        stmt = select(Supplier).where(Supplier.contact_type == "Sub vendor").order_by(Supplier.supplier_name)
        if contact_id:
            stmt = stmt.where(Supplier.supplier_id == contact_id)
        for vendor in session.scalars(stmt):
            issued = session.scalar(select(func.coalesce(func.sum(PurchaseOrderItem.ordered_qty), 0)).join(PurchaseOrder).where(PurchaseOrder.supplier_id == vendor.supplier_id, PurchaseOrderItem.stock_out_saree_id.is_not(None))) or 0
            received = session.scalar(select(func.coalesce(func.sum(GRNItem.received_qty + GRNItem.damaged_qty), 0)).join(GRN).join(PurchaseOrder).where(PurchaseOrder.supplier_id == vendor.supplier_id)) or 0
            rows.append([vendor.supplier_name, int(issued), int(received), max(int(issued) - int(received), 0)])
        return rows

    def _valuation_rows(self, inventory: InventoryRepository) -> list[list[object]]:
        rows: list[list[object]] = []
        for _saree_id, code, name, stock, rate, value in inventory.inventory_valuation_rows():
            rows.append([f"{code} - {name}", stock, rate, value])
        return rows
