"""Job work issue and receipt workflows."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models.entities import JobWorkIssue, JobWorkIssueItem, JobWorkReceipt, JobWorkReceiptItem
from services.inventory_service import InventoryService
from services.numbering import next_number


class JobWorkService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.inventory = InventoryService(session)

    def issue(self, vendor_id: int, lines: list[tuple[int, int]], issue_date: date | None = None, remarks: str | None = None) -> JobWorkIssue:
        document_date = issue_date or date.today()
        issue = JobWorkIssue(issue_no=next_number(self.session, JobWorkIssue, "issue_no", "JWISS", document_date), vendor_id=vendor_id, issue_date=document_date, remarks=remarks, status="OPEN")
        for saree_id, quantity in lines:
            self.inventory.assert_available(saree_id, quantity)
            issue.items.append(JobWorkIssueItem(saree_id=saree_id, issued_qty=quantity))
            self.inventory.post_ledger(transaction_date=document_date, transaction_type="JOBWORK_ISSUE", reference_no=issue.issue_no, saree_id=saree_id, qty_out=quantity, remarks=remarks)
        self.session.add(issue)
        return issue

    def receive(self, issue_id: int, vendor_id: int, lines: list[tuple[int, int, int, Decimal]], receipt_date: date | None = None) -> JobWorkReceipt:
        issue = self.session.get(JobWorkIssue, issue_id)
        if issue is None:
            raise ValueError("Job work issue not found.")
        document_date = receipt_date or date.today()
        receipt = JobWorkReceipt(receipt_no=next_number(self.session, JobWorkReceipt, "receipt_no", "JWREC", document_date), issue_id=issue_id, vendor_id=vendor_id, receipt_date=document_date)
        for saree_id, received_qty, rejected_qty, process_cost in lines:
            if received_qty < 0 or rejected_qty < 0 or received_qty + rejected_qty <= 0:
                raise ValueError("Received or rejected quantity is required.")
            receipt.items.append(JobWorkReceiptItem(saree_id=saree_id, received_qty=received_qty, rejected_qty=rejected_qty, process_cost=process_cost))
            if received_qty:
                self.inventory.post_ledger(transaction_date=document_date, transaction_type="JOBWORK_RECEIPT", reference_no=receipt.receipt_no, saree_id=saree_id, qty_in=received_qty, rate=process_cost)
        self.session.add(receipt)
        self._update_issue_status(issue)
        return receipt

    def _update_issue_status(self, issue: JobWorkIssue) -> None:
        issued = sum(item.issued_qty for item in issue.items)
        received = int(self.session.scalar(select(func.coalesce(func.sum(JobWorkReceiptItem.received_qty + JobWorkReceiptItem.rejected_qty), 0)).join(JobWorkReceipt).where(JobWorkReceipt.issue_id == issue.issue_id)) or 0)
        issue.status = "CLOSED" if received >= issued else "PARTIAL" if received > 0 else "OPEN"
