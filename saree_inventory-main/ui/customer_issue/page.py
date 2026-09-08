"""Customer issue UI for finished-goods stock out."""
from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QComboBox, QFormLayout, QLineEdit, QPushButton, QSpinBox
from sqlalchemy import select

from database.database import session_scope
from database.models.entities import Saree, Supplier
from services.inventory_service import InventoryService
from ui.common import Page, populate_combo


class CustomerIssuePage(Page):
    def __init__(self) -> None:
        super().__init__("Issue to Customer")
        form = QFormLayout(); self.customer = QComboBox(); self.item = QComboBox(); self.quantity = QSpinBox(); self.quantity.setRange(1, 100000); self.reference = QLineEdit(); self.remarks = QLineEdit()
        form.addRow("Customer", self.customer); form.addRow("FG Item", self.item); form.addRow("Qty Out", self.quantity); form.addRow("Reference", self.reference); form.addRow("Remarks", self.remarks)
        save = QPushButton("Save Customer Issue"); save.clicked.connect(self.save); form.addRow(save)
        self.layout.addLayout(form)
        self.refresh()

    def refresh(self) -> None:
        with session_scope() as session:
            populate_combo(self.customer, [(c.supplier_id, c.supplier_name) for c in session.scalars(select(Supplier).where(Supplier.contact_type == "Customer").order_by(Supplier.supplier_name))])
            populate_combo(self.item, [(s.saree_id, f"{s.saree_code} - {s.saree_name}") for s in session.scalars(select(Saree).where(Saree.fabric == "FG").order_by(Saree.saree_code))])

    def save(self) -> None:
        try:
            if self.customer.currentData() is None or self.item.currentData() is None:
                raise ValueError("Create a Customer contact and FG item before issuing stock.")
            with session_scope() as session:
                service = InventoryService(session)
                item_id = int(self.item.currentData())
                service.assert_available(item_id, self.quantity.value())
                reference = self.reference.text().strip() or f"CUST-{date.today():%Y%m%d}"
                service.post_ledger(transaction_date=date.today(), transaction_type="CUSTOMER_ISSUE", reference_no=reference, saree_id=item_id, qty_out=self.quantity.value(), remarks=self.remarks.text())
            self.info("Customer issue saved and FG stock reduced."); self.reference.clear(); self.remarks.clear(); self.refresh()
        except Exception as exc:
            self.error(str(exc))
