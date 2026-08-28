from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.schemas.job_work import (
    JobWorkIssueCreate, JobWorkIssueItemResponse, JobWorkIssueListResponse, JobWorkIssueResponse,
    JobWorkReceiptCreate, JobWorkReceiptItemResponse, JobWorkReceiptListResponse, JobWorkReceiptResponse,
)
from app.services.jobwork_service import JobWorkService

router = APIRouter(prefix="/job-work", tags=["Job Work"])


def _issue_to_response(issue) -> JobWorkIssueResponse:
    items = [JobWorkIssueItemResponse(
        issue_item_id=item.issue_item_id, saree_id=item.saree_id,
        saree_code=item.saree.saree_code if item.saree else None,
        saree_name=item.saree.saree_name if item.saree else None,
        issued_qty=item.issued_qty,
    ) for item in issue.items]
    return JobWorkIssueResponse(
        issue_id=issue.issue_id, issue_no=issue.issue_no, vendor_id=issue.vendor_id,
        vendor_name=issue.vendor.vendor_name if issue.vendor else None,
        issue_date=issue.issue_date, status=issue.status, remarks=issue.remarks, items=items,
    )


def _receipt_to_response(receipt) -> JobWorkReceiptResponse:
    items = [JobWorkReceiptItemResponse(
        receipt_item_id=item.receipt_item_id, saree_id=item.saree_id,
        saree_code=item.saree.saree_code if item.saree else None,
        saree_name=item.saree.saree_name if item.saree else None,
        received_qty=item.received_qty, rejected_qty=item.rejected_qty, process_cost=item.process_cost,
    ) for item in receipt.items]
    return JobWorkReceiptResponse(
        receipt_id=receipt.receipt_id, receipt_no=receipt.receipt_no,
        issue_id=receipt.issue_id, issue_no=receipt.issue.issue_no if receipt.issue else None,
        vendor_id=receipt.vendor_id, vendor_name=receipt.vendor.vendor_name if receipt.vendor else None,
        receipt_date=receipt.receipt_date, items=items,
    )


# --- Issues ---
@router.get("/issues", response_model=JobWorkIssueListResponse)
async def list_issues(
    status: str | None = None, vendor_id: int | None = None,
    search: str = "", date_from: str | None = None, date_to: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    issues, total = await JobWorkService(db).list_issues(status, vendor_id, search, date_from, date_to, page, page_size)
    return JobWorkIssueListResponse(
        items=[_issue_to_response(i) for i in issues],
        total=total, page=page, page_size=page_size,
    )


@router.post("/issues", response_model=JobWorkIssueResponse, status_code=201)
async def create_issue(body: JobWorkIssueCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        lines = [(item.saree_id, item.issued_qty) for item in body.items]
        issue = await JobWorkService(db).issue(body.vendor_id, lines, body.issue_date, body.remarks)
        from sqlalchemy.orm import selectinload
        from app.models.job_work import JobWorkIssue, JobWorkIssueItem
        issue = await db.get(JobWorkIssue, issue.issue_id, options=[
            selectinload(JobWorkIssue.vendor),
            selectinload(JobWorkIssue.items).selectinload(JobWorkIssueItem.saree),
        ])
        return _issue_to_response(issue)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/issues/{issue_id}/pending-qty")
async def get_pending_qty(issue_id: int, saree_id: int, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    qty = await JobWorkService(db).pending_issue_qty(issue_id, saree_id)
    return {"pending_qty": qty}


# --- Receipts ---
@router.get("/receipts", response_model=JobWorkReceiptListResponse)
async def list_receipts(
    issue_id: int | None = None, search: str = "",
    date_from: str | None = None, date_to: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    receipts, total = await JobWorkService(db).list_receipts(issue_id, search, date_from, date_to, page, page_size)
    return JobWorkReceiptListResponse(
        items=[_receipt_to_response(r) for r in receipts],
        total=total, page=page, page_size=page_size,
    )


@router.post("/receipts", response_model=JobWorkReceiptResponse, status_code=201)
async def create_receipt(body: JobWorkReceiptCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        lines = [(item.saree_id, item.received_qty, item.rejected_qty, item.process_cost) for item in body.items]
        receipt = await JobWorkService(db).receive(body.issue_id, body.vendor_id, lines, body.receipt_date)
        from sqlalchemy.orm import selectinload
        from app.models.job_work import JobWorkReceipt, JobWorkReceiptItem
        receipt = await db.get(JobWorkReceipt, receipt.receipt_id, options=[
            selectinload(JobWorkReceipt.vendor),
            selectinload(JobWorkReceipt.issue),
            selectinload(JobWorkReceipt.items).selectinload(JobWorkReceiptItem.saree),
        ])
        return _receipt_to_response(receipt)
    except ValueError as e:
        raise HTTPException(400, str(e))
