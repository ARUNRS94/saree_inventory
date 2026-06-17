# Saree Inventory & Job Work Management System

Offline Windows desktop ERP foundation for saree inventory, purchase orders, GRN, job work, stock ledger, valuation, dashboard, and reports.

## Stack

- Python 3.12+
- PySide6
- SQLite
- SQLAlchemy
- Pandas / ReportLab
- PyInstaller-ready structure

## Run

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

On first launch, `inventory.db` tables are created automatically.
