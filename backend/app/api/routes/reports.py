from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.company_settings import CompanySettings
from app.services.inventory_service import InventoryService
from app.services.master_service import item_type_label
from app.services.purchase_service import PurchaseService

router = APIRouter(prefix="/reports", tags=["Reports"])

# Document exports are rendered in one pass, so the row count is bounded.
DOCUMENT_EXPORT_LIMIT = 1_000


@dataclass(frozen=True)
class ReportFilters:
    """Every filter the report endpoints accept; each report reads the ones it needs."""

    search: str = ""
    item_type: str | None = None
    vendor: str | None = None
    hide_zero: bool = False
    transaction_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    voucher_number: str | None = None
    vendor_voucher_number: str | None = None
    status: str | None = None
    contact_id: int | None = None
    grn_type: str | None = None


def report_filters(
    search: str = "", item_type: str | None = None, vendor: str | None = None,
    hide_zero: bool = False, transaction_type: str | None = None,
    date_from: date | None = None, date_to: date | None = None,
    voucher_number: str | None = None, vendor_voucher_number: str | None = None,
    status: str | None = None, contact_id: int | None = None, grn_type: str | None = None,
) -> ReportFilters:
    return ReportFilters(
        search=search, item_type=item_type, vendor=vendor, hide_zero=hide_zero,
        transaction_type=transaction_type, date_from=date_from, date_to=date_to,
        voucher_number=voucher_number, vendor_voucher_number=vendor_voucher_number,
        status=status, contact_id=contact_id, grn_type=grn_type,
    )


def _vendors(row: dict) -> str:
    return ", ".join(row.get("vendors") or []) or "-"


def _joined(row: dict, key: str) -> str:
    return ", ".join(row.get(key) or []) or "-"


def _money(value: Decimal | float | int) -> str:
    return f"{Decimal(str(value)):.2f}"


async def _company_name(db: AsyncSession) -> str:
    name = await db.scalar(select(CompanySettings.value).where(CompanySettings.key == "company_name"))
    return (name or "").strip()


async def _build(db: AsyncSession, report: str, f: ReportFilters) -> tuple[str, list[str], list[list[str]]]:
    """Returns the file stem, the header row and the body rows for one report."""
    service = InventoryService(db)
    if report == "stock":
        rows = await service.stock_report(f.search, f.item_type, f.vendor, f.hide_zero,
                                          f.voucher_number, f.vendor_voucher_number)
        headers = ["Item Name", "Type", "GSS Voucher No", "Vendor Voucher No", "Vendors", "Current Stock"]
        body = [[r["item_name"], item_type_label(r["item_type"]),
                 _joined(r, "voucher_numbers"), _joined(r, "vendor_voucher_numbers"),
                 _vendors(r), str(r["current_stock"])] for r in rows]
        return "stock_report", headers, body
    if report == "valuation":
        rows = await service.inventory_valuation(f.search, f.item_type, f.vendor, f.hide_zero,
                                                 f.voucher_number, f.vendor_voucher_number)
        headers = ["Item Name", "Type", "GSS Voucher No", "Vendor Voucher No", "Vendors", "Stock", "Rate", "Value"]
        body = [[r["item_name"], item_type_label(r["item_type"]),
                 _joined(r, "voucher_numbers"), _joined(r, "vendor_voucher_numbers"), _vendors(r),
                 str(r["current_stock"]), _money(r["latest_rate"]), _money(r["value"])] for r in rows]
        return "valuation_report", headers, body
    if report == "movement":
        rows = await service.movement_report(f.search, f.transaction_type, f.date_from, f.date_to)
        headers = ["Date", "Type", "Reference", "Vendor", "Item Name", "In", "Out", "Rate", "Amount", "Remarks"]
        body = [[r["transaction_date"].isoformat(), r["transaction_type"].replace("_", " "),
                 r["reference_no"], r["vendor_name"] or "-", r["item_name"],
                 str(r["qty_in"]), str(r["qty_out"]), _money(r["rate"]), _money(r["amount"]),
                 r["remarks"]] for r in rows]
        if rows:
            total = sum((Decimal(str(r["amount"])) for r in rows), Decimal("0"))
            body.append(["", "", "", "", "", "", "", "Total", _money(total), ""])
        return "movement_report", headers, body
    if report == "vouchers":
        pos, _total = await PurchaseService(db).list_pos(
            f.status, f.contact_id, f.search, f.date_from, f.date_to, 1, DOCUMENT_EXPORT_LIMIT,
        )
        headers = ["GSS Voucher No", "Voucher Ref", "Date", "Sub Vendor", "Status", "Stock In Item",
                   "Stock Out Item", "Target FG Item", "Qty", "Rate", "Amount", "LR No"]
        body = [
            [po.voucher_number or "-", po.po_number, po.po_date.isoformat(),
             po.contact.contact_name if po.contact else "-", po.status,
             item.item.item_name if item.item else "-",
             item.stock_out_item.item_name if item.stock_out_item else "-",
             item.target_fg_item.item_name if item.target_fg_item else "-",
             str(item.ordered_qty), _money(item.rate), _money(item.amount), item.lr_number or "-"]
            for po in pos for item in po.items
        ]
        return "voucher_report", headers, body
    if report == "grns":
        grns, _total = await PurchaseService(db).list_grns(
            None, f.search, f.date_from, f.date_to, 1, DOCUMENT_EXPORT_LIMIT, f.grn_type, f.voucher_number,
        )
        headers = ["GRN No", "Date", "Inward Type", "Vendor", "GSS Voucher No", "Vendor Voucher No",
                   "Stock In Item", "Received", "Damaged/NC", "Short Of", "Rate", "Amount", "LR No", "PO Number"]
        body = []
        for grn in grns:
            contact = grn.contact or (grn.purchase_order.contact if grn.purchase_order else None)
            for item in grn.items:
                body.append([
                    grn.grn_number, grn.grn_date.isoformat(),
                    "Raw Material" if grn.grn_type == "RM" else "Sub Vendor",
                    contact.contact_name if contact else "-",
                    (grn.purchase_order.voucher_number if grn.purchase_order else None) or "-",
                    grn.vendor_voucher_number or "-",
                    item.item.item_name if item.item else "-",
                    str(item.received_qty), str(item.damaged_qty), str(item.short_qty or 0),
                    _money(item.rate), _money(Decimal(item.received_qty) * item.rate),
                    item.lr_number or "-", item.po_number or "-",
                ])
        return "grn_report", headers, body
    raise HTTPException(404, f"Unknown report: {report}")


def _filter_summary(f: ReportFilters) -> list[str]:
    applied = [
        ("Search", f.search),
        ("Type", item_type_label(f.item_type) if f.item_type else None),
        ("Vendor", f.vendor),
        ("GSS Voucher No", f.voucher_number),
        ("Vendor Voucher No", f.vendor_voucher_number),
        ("Transaction", f.transaction_type.replace("_", " ") if f.transaction_type else None),
        ("Status", f.status),
        ("Inward Type", f.grn_type),
        ("From", f.date_from),
        ("To", f.date_to),
        ("Excluding zero stock", "Yes" if f.hide_zero else None),
    ]
    return [f"{label}: {value}" for label, value in applied if value]


@router.get("/{report}/csv")
async def report_csv(
    report: str, filters: ReportFilters = Depends(report_filters),
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    stem, headers, body = await _build(db, report, filters)
    company = await _company_name(db)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if company:
        writer.writerow([company])
    writer.writerow([stem.replace("_", " ").title(), f"Generated {date.today():%d %b %Y}"])
    summary = _filter_summary(filters)
    if summary:
        writer.writerow(["Filters", *summary])
    writer.writerow([])
    writer.writerow(headers)
    writer.writerows(body)
    return StreamingResponse(
        io.BytesIO(buffer.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={stem}.csv"},
    )


@router.get("/{report}/pdf")
async def report_pdf(
    report: str, filters: ReportFilters = Depends(report_filters),
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    stem, headers, body = await _build(db, report, filters)
    company = await _company_name(db)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), title=stem)
    styles = getSampleStyleSheet()

    title = stem.replace("_", " ").title()
    flow = [Paragraph(company, styles["Title"]), Paragraph(title, styles["Heading2"])] if company \
        else [Paragraph(title, styles["Title"])]
    flow.append(Paragraph(f"Generated {date.today():%d %b %Y} | {len(body)} row(s)", styles["Normal"]))
    summary = _filter_summary(filters)
    if summary:
        flow.append(Paragraph("Filters - " + " | ".join(summary), styles["Normal"]))
    flow.append(Spacer(1, 12))

    table = Table([headers] + (body or [["No data"] + [""] * (len(headers) - 1)]), repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    flow.append(table)
    doc.build(flow)
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={stem}.pdf"},
    )
