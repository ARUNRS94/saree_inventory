"""Report generation helpers for PDF and tabular exports."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table
from sqlalchemy.orm import Session

from database.repositories.inventory import InventoryRepository


class ReportService:
    def __init__(self, session: Session) -> None:
        self.inventory = InventoryRepository(session)

    def stock_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.inventory.stock_report(), columns=["Saree Code", "Saree Name", "Current Stock"])

    def export_stock_pdf(self, output_path: Path) -> Path:
        df = self.stock_dataframe()
        document = SimpleDocTemplate(str(output_path), pagesize=A4)
        rows = [list(df.columns), *df.astype(str).values.tolist()]
        document.build([Table(rows)])
        return output_path
