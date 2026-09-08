"""Job work issue and receipt UI pages."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QPushButton, QSpinBox
from sqlalchemy import select

from database.database import session_scope
from database.models.entities import JobWorkIssue, Saree, Vendor
from database.repositories.inventory import InventoryRepository
from services.jobwork_service import JobWorkService
from ui.common import Page, populate_combo


class JobWorkIssuePage(Page):
    def __init__(self) -> None:
        super().__init__("Job Work Issue")
        form = QFormLayout()
        self.vendor = QComboBox()
        self.saree = QComboBox()
        self.stock = QLabel("Stock: 0")
        self.quantity = QSpinBox(); self.quantity.setRange(1, 100000)
        form.addRow("Vendor", self.vendor)
        form.addRow("Saree", self.saree)
        form.addRow(self.stock)
        form.addRow("Issue Qty", self.quantity)
        save = QPushButton("Issue to Vendor")
        save.clicked.connect(self.save)
        form.addRow(save)
        self.layout.addLayout(form)
        self.saree.currentIndexChanged.connect(self.update_stock)
        self.refresh()

    def refresh(self) -> None:
        with session_scope() as session:
            populate_combo(self.vendor, [(v.vendor_id, f"{v.vendor_name} ({v.process_type})") for v in session.scalars(select(Vendor).order_by(Vendor.vendor_name))])
            populate_combo(self.saree, [(s.saree_id, f"{s.saree_code} - {s.saree_name}") for s in session.scalars(select(Saree).order_by(Saree.saree_code))])
        self.update_stock()

    def update_stock(self) -> None:
        if self.saree.currentData() is None:
            self.stock.setText("Stock: 0")
            return
        with session_scope() as session:
            self.stock.setText(f"Stock: {InventoryRepository(session).current_stock(int(self.saree.currentData()))}")

    def save(self) -> None:
        try:
            if self.vendor.currentData() is None or self.saree.currentData() is None:
                raise ValueError("Create a vendor and saree before issuing job work.")
            with session_scope() as session:
                issue = JobWorkService(session).issue(int(self.vendor.currentData()), [(int(self.saree.currentData()), self.quantity.value())])
                issue_no = issue.issue_no
            self.info(f"Job Work Issue {issue_no} saved and stock reduced.")
            self.refresh()
        except Exception as exc:
            self.error(str(exc))


class JobWorkReceiptPage(Page):
    def __init__(self) -> None:
        super().__init__("Job Work Receipt")
        form = QFormLayout()
        self.issue = QComboBox()
        self.saree = QComboBox()
        self.pending = QLabel("Pending: 0")
        self.received = QSpinBox(); self.received.setRange(0, 100000)
        self.rejected = QSpinBox(); self.rejected.setRange(0, 100000)
        self.cost = QDoubleSpinBox(); self.cost.setRange(0, 10000000); self.cost.setDecimals(2)
        form.addRow("Issue", self.issue)
        form.addRow("Saree", self.saree)
        form.addRow(self.pending)
        form.addRow("Received Qty", self.received)
        form.addRow("Rejected Qty", self.rejected)
        form.addRow("Process Cost", self.cost)
        save = QPushButton("Receive from Vendor")
        save.clicked.connect(self.save)
        form.addRow(save)
        self.layout.addLayout(form)
        self.issue.currentIndexChanged.connect(self.update_pending)
        self.saree.currentIndexChanged.connect(self.update_pending)
        self.refresh()

    def refresh(self) -> None:
        with session_scope() as session:
            populate_combo(self.issue, [(i.issue_id, i.issue_no) for i in session.scalars(select(JobWorkIssue).where(JobWorkIssue.status != "CLOSED").order_by(JobWorkIssue.issue_id.desc()))])
            populate_combo(self.saree, [(s.saree_id, f"{s.saree_code} - {s.saree_name}") for s in session.scalars(select(Saree).order_by(Saree.saree_code))])
        self.update_pending()

    def update_pending(self) -> None:
        if self.issue.currentData() is None or self.saree.currentData() is None:
            self.pending.setText("Pending: 0")
            return
        with session_scope() as session:
            qty = JobWorkService(session).pending_issue_qty(int(self.issue.currentData()), int(self.saree.currentData()))
            self.pending.setText(f"Pending: {qty}")

    def save(self) -> None:
        try:
            if self.issue.currentData() is None or self.saree.currentData() is None:
                raise ValueError("Create an open job work issue before receiving.")
            with session_scope() as session:
                issue = session.get(JobWorkIssue, int(self.issue.currentData()))
                if issue is None:
                    raise ValueError("Job work issue not found.")
                receipt = JobWorkService(session).receive(
                    int(self.issue.currentData()),
                    issue.vendor_id,
                    [(int(self.saree.currentData()), self.received.value(), self.rejected.value(), Decimal(str(self.cost.value())))],
                )
                receipt_no = receipt.receipt_no
            self.info(f"Job Work Receipt {receipt_no} saved and stock updated.")
            self.refresh()
        except Exception as exc:
            self.error(str(exc))
