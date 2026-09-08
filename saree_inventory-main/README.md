# Saree Inventory & Job Work Management System

Offline Windows desktop ERP foundation for item inventory, contact master, purchase orders, GRN, customer issue, stock ledger, valuation, dashboard, and reports.

## Stack

- Python 3.12+
- PySide6
- SQLite
- SQLAlchemy
- Pandas / ReportLab
- PyInstaller-ready structure

## Features

- Item master for RM, Sub process, and FG items.
- Contact master for RM vendors, Sub vendors, and Customers.
- Purchase orders for RM vendors and Sub vendor process orders.
- Sub vendor stock-out supports both RM and FG items, with available stock displayed while creating a PO.
- GRN, customer issue, stock ledger, inventory valuation, dashboard, and report views.
- CSV import/export for item and contact masters.
- CSV download for the currently selected report tab.

## Run From Source

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

On first launch, `inventory.db` tables are created automatically.

## Build a Windows EXE with PyInstaller `--onedir`

Use the `--onedir` option to create a distributable folder containing the executable and its supporting files. This is recommended for PySide6 apps because the Qt runtime files remain beside the executable.

From a Windows command prompt or PowerShell:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pyinstaller --onedir --windowed --name SareeInventory app.py
```

After the build completes, run the application from:

```text
dist\SareeInventory\SareeInventory.exe
```

### Build notes

- Keep the full `dist\SareeInventory` folder together when copying the app to another Windows machine; do not copy only the `.exe` file.
- The SQLite database file (`inventory.db`) is created in the working directory on first launch. If you want the database to live beside the executable, start the app from `dist\SareeInventory` or copy an existing `inventory.db` into that folder.
- If you need a clean rebuild, remove the generated `build`, `dist`, and `SareeInventory.spec` files/folders before running PyInstaller again.
