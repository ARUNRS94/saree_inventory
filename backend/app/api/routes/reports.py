from __future__ import annotations

import io
from decimal import Decimal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/stock/csv")
async def stock_csv(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    rows = await InventoryService(db).stock_report()
    output = io.StringIO()
    output.write("Item Code,Item Name,Type,Current Stock\n")
    for r in rows:
        output.write(f"{r['item_code']},{r['item_name']},{r['item_type']},{r['current_stock']}\n")
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=stock_report.csv"},
    )


@router.get("/valuation/csv")
async def valuation_csv(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    rows = await InventoryService(db).inventory_valuation()
    output = io.StringIO()
    output.write("Item Code,Item Name,Current Stock,Latest Rate,Value\n")
    for r in rows:
        output.write(f"{r['item_code']},{r['item_name']},{r['current_stock']},{r['latest_rate']},{r['value']}\n")
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=valuation_report.csv"},
    )


@router.get("/stock/pdf")
async def stock_pdf(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    rows = await InventoryService(db).stock_report()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    data = [["Item Code", "Item Name", "Type", "Current Stock"]]
    for r in rows:
        data.append([r["item_code"], r["item_name"], r["item_type"], str(r["current_stock"])])
    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    doc.build([table])
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=stock_report.pdf"},
    )


@router.get("/valuation/pdf")
async def valuation_pdf(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    rows = await InventoryService(db).inventory_valuation()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    data = [["Item Code", "Item Name", "Stock", "Rate", "Value"]]
    for r in rows:
        data.append([r["item_code"], r["item_name"], str(r["current_stock"]), str(r["latest_rate"]), str(r["value"])])
    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    doc.build([table])
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=valuation_report.pdf"},
    )
