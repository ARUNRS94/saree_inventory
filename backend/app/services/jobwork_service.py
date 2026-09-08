from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.job_work import JobWorkIssue, JobWorkIssueItem, JobWorkReceipt, JobWorkReceiptItem
from app.services.inventory_service import InventoryService
from app.services.numbering import next_number


class JobWorkService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.inventory = InventoryService(session)

    async def issue(self, vendor_id: int, lines: list[tuple[int, int]],
                    issue_date: date | None = None, remarks: str | None = None) -> JobWorkIssue:
        if not lines:
            raise ValueError("Job work issue requires at least one item line.")
        document_date = issue_date or date.today()
        jw_issue = JobWorkIssue(
            issue_no=await next_number(self.session, JobWorkIssue, "issue_no", "JWISS", document_date),
            vendor_id=vendor_id,
            issue_date=document_date,
            remarks=remarks,
            status="OPEN",
        )
        for item_id, quantity in lines:
            await self.inventory.assert_available(item_id, quantity)
            jw_issue.items.append(JobWorkIssueItem(item_id=item_id, issued_qty=quantity))
            await self.inventory.post_ledger(
                transaction_date=document_date, transaction_type="JOBWORK_ISSUE",
                reference_no=jw_issue.issue_no, item_id=item_id, qty_out=quantity, remarks=remarks,
            )
        self.session.add(jw_issue)
        await self.session.flush()
        return jw_issue

    async def receive(self, issue_id: int, vendor_id: int,
                      lines: list[tuple[int, int, int, Decimal]],
                      receipt_date: date | None = None) -> JobWorkReceipt:
        issue = await self.session.get(JobWorkIssue, issue_id, options=[selectinload(JobWorkIssue.items)])
        if issue is None:
            raise ValueError("Job work issue not found.")
        if not lines:
            raise ValueError("Job work receipt requires at least one item line.")

        document_date = receipt_date or date.today()
        receipt = JobWorkReceipt(
            receipt_no=await next_number(self.session, JobWorkReceipt, "receipt_no", "JWREC", document_date),
            issue_id=issue_id,
            vendor_id=vendor_id,
            receipt_date=document_date,
        )
        for item_id, received_qty, rejected_qty, process_cost in lines:
            total_receipt_qty = received_qty + rejected_qty
            if received_qty < 0 or rejected_qty < 0 or total_receipt_qty <= 0:
                raise ValueError("Received or rejected quantity is required.")
            pending = await self.pending_issue_qty(issue_id, item_id)
            if total_receipt_qty > pending:
                raise ValueError(f"Receipt quantity exceeds pending job work quantity. Pending: {pending}.")
            receipt.items.append(JobWorkReceiptItem(
                item_id=item_id, received_qty=received_qty,
                rejected_qty=rejected_qty, process_cost=process_cost,
            ))
            if received_qty:
                await self.inventory.post_ledger(
                    transaction_date=document_date, transaction_type="JOBWORK_RECEIPT",
                    reference_no=receipt.receipt_no, item_id=item_id,
                    qty_in=received_qty, rate=process_cost,
                )
        self.session.add(receipt)
        await self.session.flush()
        await self._update_issue_status(issue)
        return receipt

    async def pending_issue_qty(self, issue_id: int, item_id: int) -> int:
        issued = int(await self.session.scalar(
            select(func.coalesce(func.sum(JobWorkIssueItem.issued_qty), 0))
            .where(JobWorkIssueItem.issue_id == issue_id, JobWorkIssueItem.item_id == item_id)
        ) or 0)
        received = int(await self.session.scalar(
            select(func.coalesce(func.sum(JobWorkReceiptItem.received_qty + JobWorkReceiptItem.rejected_qty), 0))
            .join(JobWorkReceipt)
            .where(JobWorkReceipt.issue_id == issue_id, JobWorkReceiptItem.item_id == item_id)
        ) or 0)
        return max(issued - received, 0)

    async def _update_issue_status(self, issue: JobWorkIssue) -> None:
        issued = sum(item.issued_qty for item in issue.items)
        received = int(await self.session.scalar(
            select(func.coalesce(func.sum(JobWorkReceiptItem.received_qty + JobWorkReceiptItem.rejected_qty), 0))
            .join(JobWorkReceipt)
            .where(JobWorkReceipt.issue_id == issue.issue_id)
        ) or 0)
        issue.status = "CLOSED" if received >= issued else "PARTIAL" if received > 0 else "OPEN"

    async def list_issues(self, status: str | None = None, vendor_id: int | None = None,
                          search: str = "", date_from=None, date_to=None,
                          page: int = 1, page_size: int = 50) -> tuple[list[JobWorkIssue], int]:
        stmt = select(JobWorkIssue).options(
            selectinload(JobWorkIssue.vendor),
            selectinload(JobWorkIssue.items).selectinload(JobWorkIssueItem.item),
        )
        count_stmt = select(func.count()).select_from(JobWorkIssue)
        if status:
            stmt = stmt.where(JobWorkIssue.status == status)
            count_stmt = count_stmt.where(JobWorkIssue.status == status)
        if vendor_id:
            stmt = stmt.where(JobWorkIssue.vendor_id == vendor_id)
            count_stmt = count_stmt.where(JobWorkIssue.vendor_id == vendor_id)
        if search:
            stmt = stmt.where(JobWorkIssue.issue_no.ilike(f"%{search}%"))
            count_stmt = count_stmt.where(JobWorkIssue.issue_no.ilike(f"%{search}%"))
        if date_from:
            stmt = stmt.where(JobWorkIssue.issue_date >= date_from)
            count_stmt = count_stmt.where(JobWorkIssue.issue_date >= date_from)
        if date_to:
            stmt = stmt.where(JobWorkIssue.issue_date <= date_to)
            count_stmt = count_stmt.where(JobWorkIssue.issue_date <= date_to)
        total = await self.session.scalar(count_stmt) or 0
        stmt = stmt.order_by(JobWorkIssue.issue_id.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all()), total

    async def list_receipts(self, issue_id: int | None = None, search: str = "",
                            date_from=None, date_to=None,
                            page: int = 1, page_size: int = 50) -> tuple[list[JobWorkReceipt], int]:
        stmt = select(JobWorkReceipt).options(
            selectinload(JobWorkReceipt.vendor),
            selectinload(JobWorkReceipt.issue),
            selectinload(JobWorkReceipt.items).selectinload(JobWorkReceiptItem.item),
        )
        count_stmt = select(func.count()).select_from(JobWorkReceipt)
        if issue_id:
            stmt = stmt.where(JobWorkReceipt.issue_id == issue_id)
            count_stmt = count_stmt.where(JobWorkReceipt.issue_id == issue_id)
        if search:
            stmt = stmt.where(JobWorkReceipt.receipt_no.ilike(f"%{search}%"))
            count_stmt = count_stmt.where(JobWorkReceipt.receipt_no.ilike(f"%{search}%"))
        if date_from:
            stmt = stmt.where(JobWorkReceipt.receipt_date >= date_from)
            count_stmt = count_stmt.where(JobWorkReceipt.receipt_date >= date_from)
        if date_to:
            stmt = stmt.where(JobWorkReceipt.receipt_date <= date_to)
            count_stmt = count_stmt.where(JobWorkReceipt.receipt_date <= date_to)
        total = await self.session.scalar(count_stmt) or 0
        stmt = stmt.order_by(JobWorkReceipt.receipt_id.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all()), total
