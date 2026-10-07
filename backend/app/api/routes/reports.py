from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.services.inventory_service import InventoryService
from app.services.master_service import item_type_label

router = APIRouter(prefix="/reports", tags=["Reports"])


def _vendors(row: dict) -> str:
    return ", ".join(row.get("vendors") or []) or "-"


def _money(value: Decimal | float | int) -> str:
    return f"{Decimal(str(value)):.2f}"


async def _build(db: AsyncSession, report: str, search: str, item_type: str | None,
                 vendor: str | None, hide_zero: bool, transaction_type: str | None,
                 date_from: date | None, date_to: date | None) -> tuple[str, list[str], list[list[str]]]:
    """Returns the file stem, the header row and the body rows for one report."""
    service = InventoryService(db)
    if report == "stock":
        rows = await service.stock_report(search, item_type, vendor, hide_zero)
        headers = ["Item Name", "Type", "Category", "Vendors", "Current Stock"]
        body = [[r["item_name"], item_type_label(r["item_type"]), r.get("category") or "-",
                 _vendors(r), str(r["current_stock"])] for r in rows]
        return "stock_report", headers, body
    if report == "valuation":
        rows = await service.inventory_valuation(search, item_type, vendor, hide_zero)
        headers = ["Item Name", "Type", "Vendors", "Stock", "Rate", "Value"]
        body = [[r["item_name"], item_type_label(r["item_type"]), _vendors(r),
                 str(r["current_stock"]), _money(r["latest_rate"]), _money(r["value"])] for r in rows]
        return "valuation_report", headers, body
    if report == "movement":
        rows = await service.movement_report(search, transaction_type, date_from, date_to)
        headers = ["Date", "Type", "Reference", "Item Name", "In", "Out", "Rate", "Remarks"]
        body = [[r["transaction_date"].isoformat(), r["transaction_type"].replace("_", " "),
                 r["reference_no"], r["item_name"], str(r["qty_in"]), str(r["qty_out"]),
                 _money(r["rate"]), r["remarks"]] for r in rows]
        return "movement_report", headers, body
    raise HTTPException(404, f"Unknown report: {report}")


def _filter_summary(search: str, item_type: str | None, vendor: str | None, hide_zero: bool,
                    transaction_type: str | None, date_from: date | None, date_to: date | None) -> list[str]:
    applied = [
        ("Search", search),
        ("Type", item_type_label(item_type) if item_type else None),
        ("Vendor", vendor),
        ("Transaction", transaction_type.replace("_", " ") if transaction_type else None),
        ("From", date_from),
        ("To", date_to),
        ("Excluding zero stock", "Yes" if hide_zero else None),
    ]
    return [f"{label}: {value}" for label, value in applied if value]


@router.get("/{report}/csv")
async def report_csv(
    report: str, search: str = "", item_type: str | None = None, vendor: str | None = None,
    hide_zero: bool = False, transaction_type: str | None = None,
    date_from: date | None = None, date_to: date | None = None,
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    stem, headers, body = await _build(db, report, search, item_type, vendor, hide_zero,
                                       transaction_type, date_from, date_to)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(body)
    return StreamingResponse(
        io.BytesIO(buffer.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={stem}.csv"},
    )


@router.get("/{report}/pdf")
async def report_pdf(
    report: str, search: str = "", item_type: str | None = None, vendor: str | None = None,
    hide_zero: bool = False, transaction_type: str | None = None,
    date_from: date | None = None, date_to: date | None = None,
    db: AsyncSession = Depends(get_db), _user=Depends(get_current_user),
):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    stem, headers, body = await _build(db, report, search, item_type, vendor, hide_zero,
                                       transaction_type, date_from, date_to)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), title=stem)
    styles = getSampleStyleSheet()

    flow = [
        Paragraph(stem.replace("_", " ").title(), styles["Title"]),
        Paragraph(f"Generated {date.today():%d %b %Y} | {len(body)} row(s)", styles["Normal"]),
    ]
    summary = _filter_summary(search, item_type, vendor, hide_zero, transaction_type, date_from, date_to)
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
