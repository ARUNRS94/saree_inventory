"""Main PySide6 window with working navigation and CRUD workflow pages."""
from __future__ import annotations

from decimal import Decimal
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from database.database import session_scope
from database.models.entities import JobWorkIssue, PurchaseOrder, Saree, StockLedger, Supplier, Vendor
from database.repositories.inventory import InventoryRepository
from services.inventory_service import InventoryService
from services.jobwork_service import JobWorkService
from services.master_service import MasterDataService
from services.purchase_service import PurchaseLine, PurchaseService


class MainWindow(QMainWindow):
    """Application shell with pages connected to service-layer workflows."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Saree Inventory & Job Work Management")
        self.resize(1280, 800)
        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)
        self._page_loaders: list[Callable[[], QWidget]] = [
            self._dashboard_page,
            self._supplier_page,
            self._vendor_page,
            self._saree_page,
            self._purchase_page,
            self._grn_page,
            self._jobwork_issue_page,
            self._jobwork_receipt_page,
            self._reports_page,
        ]
        for loader in self._page_loaders:
            self.pages.addWidget(loader())
        self._build_toolbar()
        self._show_page(0)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        labels = ["Dashboard", "Suppliers", "Vendors", "Sarees", "Purchase", "GRN", "JW Issue", "JW Receipt", "Reports"]
        for index, label in enumerate(labels):
            action = toolbar.addAction(label)
            action.triggered.connect(lambda _checked=False, page=index: self._show_page(page))
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

    def _show_page(self, index: int) -> None:
        self.pages.removeWidget(self.pages.widget(index))
        self.pages.insertWidget(index, self._page_loaders[index]())
        self.pages.setCurrentIndex(index)

    def _page(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        heading = QLabel(title)
        heading.setStyleSheet("font-size: 24px; font-weight: 600; margin: 8px;")
        layout.addWidget(heading)
        return widget, layout

    def _message(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def _error(self, message: str) -> None:
        QMessageBox.critical(self, "Validation Error", message)

    def _dashboard_page(self) -> QWidget:
        widget, layout = self._page("Dashboard")
        with session_scope() as session:
            inventory = InventoryRepository(session)
            value = InventoryService(session).inventory_value()
            cards = QGridLayout()
            cards.addWidget(QLabel(f"Total Stock Quantity\n{inventory.current_stock()}"), 0, 0)
            cards.addWidget(QLabel(f"Inventory Value\n₹ {value:,.2f}"), 0, 1)
            cards.addWidget(QLabel(f"Purchase Orders Pending\n{inventory.pending_purchase_orders()}"), 0, 2)
            layout.addLayout(cards)
            table = QTableWidget(0, 5)
            table.setHorizontalHeaderLabels(["Date", "Type", "Reference", "Qty In", "Qty Out"])
            for row, entry in enumerate(session.query(StockLedger).order_by(StockLedger.ledger_id.desc()).limit(30)):
                table.insertRow(row)
                for col, value in enumerate([entry.transaction_date, entry.transaction_type, entry.reference_no, entry.qty_in, entry.qty_out]):
                    table.setItem(row, col, QTableWidgetItem(str(value)))
            table.setSortingEnabled(True)
            layout.addWidget(table)
        return widget

    def _supplier_page(self) -> QWidget:
        widget, layout = self._page("Supplier Master")
        form = QFormLayout()
        name = QLineEdit()
        contact = QLineEdit()
        phone = QLineEdit()
        gst = QLineEdit()
        address = QTextEdit()
        form.addRow("Supplier Name *", name)
        form.addRow("Contact Person", contact)
        form.addRow("Phone", phone)
        form.addRow("GST No", gst)
        form.addRow("Address", address)
        save = QPushButton("Add Supplier")
        form.addRow(save)
        layout.addLayout(form)
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Name", "Contact", "Phone", "GST", "Address"])
        layout.addWidget(table)

        def refresh() -> None:
            table.setRowCount(0)
            with session_scope() as session:
                for row, supplier in enumerate(MasterDataService(session).search_suppliers()):
                    table.insertRow(row)
                    for col, value in enumerate([supplier.supplier_name, supplier.contact_person, supplier.phone, supplier.gst_no, supplier.address]):
                        table.setItem(row, col, QTableWidgetItem(value or ""))

        def submit() -> None:
            try:
                with session_scope() as session:
                    MasterDataService(session).create_supplier(name.text(), contact_person=contact.text(), phone=phone.text(), gst_no=gst.text(), address=address.toPlainText())
                self._message("Saved", "Supplier added successfully.")
                self._show_page(1)
            except Exception as exc:
                self._error(str(exc))

        save.clicked.connect(submit)
        refresh()
        return widget

    def _vendor_page(self) -> QWidget:
        widget, layout = self._page("Vendor Master")
        form = QFormLayout()
        name = QLineEdit()
        process = QComboBox()
        process.addItems(["Dyeing", "Stoning", "Finishing", "Printing", "Other"])
        phone = QLineEdit()
        form.addRow("Vendor Name *", name)
        form.addRow("Process Type *", process)
        form.addRow("Phone", phone)
        save = QPushButton("Add Vendor")
        form.addRow(save)
        layout.addLayout(form)
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Name", "Process", "Phone"])
        layout.addWidget(table)

        def refresh() -> None:
            table.setRowCount(0)
            with session_scope() as session:
                for row, vendor in enumerate(session.scalars(select(Vendor).order_by(Vendor.vendor_name))):
                    table.insertRow(row)
                    for col, value in enumerate([vendor.vendor_name, vendor.process_type, vendor.phone]):
                        table.setItem(row, col, QTableWidgetItem(value or ""))

        def submit() -> None:
            try:
                with session_scope() as session:
                    MasterDataService(session).create_vendor(name.text(), process.currentText(), phone=phone.text())
                self._message("Saved", "Vendor added successfully.")
                self._show_page(2)
            except Exception as exc:
                self._error(str(exc))

        save.clicked.connect(submit)
        refresh()
        return widget

    def _saree_page(self) -> QWidget:
        widget, layout = self._page("Saree Master")
        form = QFormLayout()
        code = QLineEdit()
        name = QLineEdit()
        fabric = QLineEdit()
        design = QLineEdit()
        color = QLineEdit()
        form.addRow("Code *", code)
        form.addRow("Name *", name)
        form.addRow("Fabric", fabric)
        form.addRow("Design", design)
        form.addRow("Color", color)
        save = QPushButton("Add Saree")
        form.addRow(save)
        layout.addLayout(form)
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Code", "Name", "Fabric", "Design", "Color"])
        layout.addWidget(table)

        def refresh() -> None:
            table.setRowCount(0)
            with session_scope() as session:
                for row, saree in enumerate(MasterDataService(session).search_sarees()):
                    table.insertRow(row)
                    for col, value in enumerate([saree.saree_code, saree.saree_name, saree.fabric, saree.design_name, saree.color]):
                        table.setItem(row, col, QTableWidgetItem(value or ""))

        def submit() -> None:
            try:
                with session_scope() as session:
                    MasterDataService(session).create_saree(code.text(), name.text(), fabric=fabric.text(), design_name=design.text(), color=color.text())
                self._message("Saved", "Saree added successfully.")
                self._show_page(3)
            except Exception as exc:
                self._error(str(exc))

        save.clicked.connect(submit)
        refresh()
        return widget

    def _populate_combo(self, combo: QComboBox, rows: list[tuple[int, str]]) -> None:
        combo.clear()
        for row_id, label in rows:
            combo.addItem(label, row_id)

    def _purchase_page(self) -> QWidget:
        widget, layout = self._page("Create Purchase Order")
        form = QFormLayout()
        supplier = QComboBox()
        saree = QComboBox()
        quantity = QSpinBox(); quantity.setRange(1, 100000)
        rate = QDoubleSpinBox(); rate.setRange(0, 10000000); rate.setDecimals(2)
        amount = QLabel("0.00")
        remarks = QLineEdit()
        with session_scope() as session:
            self._populate_combo(supplier, [(s.supplier_id, s.supplier_name) for s in session.scalars(select(Supplier).order_by(Supplier.supplier_name))])
            self._populate_combo(saree, [(s.saree_id, f"{s.saree_code} - {s.saree_name}") for s in session.scalars(select(Saree).order_by(Saree.saree_code))])
        form.addRow("Supplier", supplier)
        form.addRow("Saree", saree)
        form.addRow("Quantity", quantity)
        form.addRow("Rate", rate)
        form.addRow("Amount", amount)
        form.addRow("Remarks", remarks)
        save = QPushButton("Create PO")
        form.addRow(save)
        layout.addLayout(form)
        table = QTableWidget(0, 4); table.setHorizontalHeaderLabels(["PO No", "Supplier Id", "Date", "Status"]); layout.addWidget(table)

        def recalc() -> None:
            amount.setText(f"{quantity.value() * rate.value():,.2f}")

        def refresh() -> None:
            table.setRowCount(0)
            with session_scope() as session:
                for row, po in enumerate(session.scalars(select(PurchaseOrder).order_by(PurchaseOrder.po_id.desc()))):
                    table.insertRow(row)
                    for col, value in enumerate([po.po_number, po.supplier_id, po.po_date, po.status]):
                        table.setItem(row, col, QTableWidgetItem(str(value)))

        def submit() -> None:
            try:
                with session_scope() as session:
                    po = PurchaseService(session).create_po(
                        int(supplier.currentData()),
                        [PurchaseLine(int(saree.currentData()), quantity.value(), Decimal(str(rate.value())))],
                        remarks=remarks.text(),
                    )
                    po_number = po.po_number
                self._message("Saved", f"Purchase Order {po_number} created.")
                self._show_page(4)
            except Exception as exc:
                self._error(str(exc))

        quantity.valueChanged.connect(recalc); rate.valueChanged.connect(recalc); save.clicked.connect(submit)
        recalc(); refresh()
        return widget

    def _grn_page(self) -> QWidget:
        widget, layout = self._page("Goods Receipt Against PO")
        form = QFormLayout()
        po_combo = QComboBox(); saree_combo = QComboBox()
        received = QSpinBox(); received.setRange(0, 100000)
        damaged = QSpinBox(); damaged.setRange(0, 100000)
        rate = QDoubleSpinBox(); rate.setRange(0, 10000000); rate.setDecimals(2)
        pending_label = QLabel("Pending: 0")
        with session_scope() as session:
            self._populate_combo(po_combo, [(p.po_id, p.po_number) for p in session.scalars(select(PurchaseOrder).where(PurchaseOrder.status != "CLOSED").order_by(PurchaseOrder.po_id.desc()))])
            self._populate_combo(saree_combo, [(s.saree_id, f"{s.saree_code} - {s.saree_name}") for s in session.scalars(select(Saree).order_by(Saree.saree_code))])
        form.addRow("PO", po_combo); form.addRow("Saree", saree_combo); form.addRow(pending_label)
        form.addRow("Received Qty", received); form.addRow("Damaged Qty", damaged); form.addRow("Rate", rate)
        save = QPushButton("Save GRN"); form.addRow(save); layout.addLayout(form)

        def update_pending() -> None:
            if po_combo.currentData() and saree_combo.currentData():
                with session_scope() as session:
                    pending_label.setText(f"Pending: {PurchaseService(session).pending_po_qty(int(po_combo.currentData()), int(saree_combo.currentData()))}")

        def submit() -> None:
            try:
                with session_scope() as session:
                    grn = PurchaseService(session).receive_grn(int(po_combo.currentData()), [(int(saree_combo.currentData()), received.value(), damaged.value(), Decimal(str(rate.value())))])
                    grn_number = grn.grn_number
                self._message("Saved", f"GRN {grn_number} saved and stock updated.")
                self._show_page(5)
            except Exception as exc:
                self._error(str(exc))

        po_combo.currentIndexChanged.connect(update_pending); saree_combo.currentIndexChanged.connect(update_pending); save.clicked.connect(submit)
        update_pending()
        return widget

    def _jobwork_issue_page(self) -> QWidget:
        widget, layout = self._page("Job Work Issue")
        form = QFormLayout(); vendor = QComboBox(); saree = QComboBox(); qty = QSpinBox(); qty.setRange(1, 100000); stock = QLabel("Stock: 0")
        with session_scope() as session:
            self._populate_combo(vendor, [(v.vendor_id, f"{v.vendor_name} ({v.process_type})") for v in session.scalars(select(Vendor).order_by(Vendor.vendor_name))])
            self._populate_combo(saree, [(s.saree_id, f"{s.saree_code} - {s.saree_name}") for s in session.scalars(select(Saree).order_by(Saree.saree_code))])
        form.addRow("Vendor", vendor); form.addRow("Saree", saree); form.addRow(stock); form.addRow("Issue Qty", qty)
        save = QPushButton("Issue to Vendor"); form.addRow(save); layout.addLayout(form)

        def update_stock() -> None:
            if saree.currentData():
                with session_scope() as session:
                    stock.setText(f"Stock: {InventoryRepository(session).current_stock(int(saree.currentData()))}")

        def submit() -> None:
            try:
                with session_scope() as session:
                    issue = JobWorkService(session).issue(int(vendor.currentData()), [(int(saree.currentData()), qty.value())])
                    issue_no = issue.issue_no
                self._message("Saved", f"Job Work Issue {issue_no} saved and stock reduced.")
                self._show_page(6)
            except Exception as exc:
                self._error(str(exc))

        saree.currentIndexChanged.connect(update_stock); save.clicked.connect(submit); update_stock()
        return widget

    def _jobwork_receipt_page(self) -> QWidget:
        widget, layout = self._page("Job Work Receipt")
        form = QFormLayout(); issue = QComboBox(); saree = QComboBox(); received = QSpinBox(); received.setRange(0, 100000); rejected = QSpinBox(); rejected.setRange(0, 100000); cost = QDoubleSpinBox(); cost.setRange(0, 10000000); cost.setDecimals(2); pending = QLabel("Pending: 0")
        with session_scope() as session:
            self._populate_combo(issue, [(i.issue_id, i.issue_no) for i in session.scalars(select(JobWorkIssue).where(JobWorkIssue.status != "CLOSED").order_by(JobWorkIssue.issue_id.desc()))])
            self._populate_combo(saree, [(s.saree_id, f"{s.saree_code} - {s.saree_name}") for s in session.scalars(select(Saree).order_by(Saree.saree_code))])
        form.addRow("Issue", issue); form.addRow("Saree", saree); form.addRow(pending); form.addRow("Received Qty", received); form.addRow("Rejected Qty", rejected); form.addRow("Process Cost", cost)
        save = QPushButton("Receive from Vendor"); form.addRow(save); layout.addLayout(form)

        def update_pending() -> None:
            if issue.currentData() and saree.currentData():
                with session_scope() as session:
                    pending.setText(f"Pending: {JobWorkService(session).pending_issue_qty(int(issue.currentData()), int(saree.currentData()))}")

        def submit() -> None:
            try:
                with session_scope() as session:
                    issue_row = session.get(JobWorkIssue, int(issue.currentData()))
                    receipt = JobWorkService(session).receive(int(issue.currentData()), issue_row.vendor_id, [(int(saree.currentData()), received.value(), rejected.value(), Decimal(str(cost.value())))])
                    receipt_no = receipt.receipt_no
                self._message("Saved", f"Job Work Receipt {receipt_no} saved and stock updated.")
                self._show_page(7)
            except Exception as exc:
                self._error(str(exc))

        issue.currentIndexChanged.connect(update_pending); saree.currentIndexChanged.connect(update_pending); save.clicked.connect(submit); update_pending()
        return widget

    def _reports_page(self) -> QWidget:
        widget, layout = self._page("Reports")
        table = QTableWidget(0, 3); table.setHorizontalHeaderLabels(["Saree Code", "Saree Name", "Current Stock"]); layout.addWidget(QLabel("Stock Report")); layout.addWidget(table)
        with session_scope() as session:
            for row, (code, name, stock) in enumerate(InventoryRepository(session).stock_report()):
                table.insertRow(row)
                for col, value in enumerate([code, name, stock]):
                    table.setItem(row, col, QTableWidgetItem(str(value)))
        table.setSortingEnabled(True)
        return widget
