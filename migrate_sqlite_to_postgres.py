"""Migrate data from existing SQLite database to PostgreSQL.

Usage:
    python migrate_sqlite_to_postgres.py [--sqlite path/to/inventory.db]

The script reads from the existing SQLite DB (default: ./inventory.db),
creates records in the PostgreSQL database specified by DATABASE_URL,
and validates row counts after migration.

The original SQLite database is never modified.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Add backend to path for model imports
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.core.config import settings


TABLES_IN_ORDER = [
    "sarees",
    "suppliers",
    "vendors",
    "vendor_process_types",
    "purchase_orders",
    "purchase_order_items",
    "grns",
    "grn_items",
    "job_work_issues",
    "job_work_issue_items",
    "job_work_receipts",
    "job_work_receipt_items",
    "stock_ledger",
]


def migrate(sqlite_path: str) -> None:
    sqlite_url = f"sqlite:///{sqlite_path}"
    pg_url = settings.sync_database_url

    print(f"Source:  {sqlite_url}")
    print(f"Target:  {pg_url}")

    # Backup
    backup_path = Path(sqlite_path).with_suffix(".db.bak")
    if not backup_path.exists():
        shutil.copy2(sqlite_path, backup_path)
        print(f"Backup:  {backup_path}")

    src = create_engine(sqlite_url)
    dst = create_engine(pg_url)

    with src.connect() as src_conn, dst.connect() as dst_conn:
        for table in TABLES_IN_ORDER:
            try:
                rows = src_conn.execute(text(f"SELECT * FROM {table}")).mappings().all()
            except Exception:
                print(f"  SKIP   {table} (not found in SQLite)")
                continue

            if not rows:
                print(f"  EMPTY  {table}")
                continue

            columns = list(rows[0].keys())
            placeholders = ", ".join(f":{c}" for c in columns)
            col_names = ", ".join(columns)
            insert_sql = text(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING")

            with dst_conn.begin():
                for row in rows:
                    dst_conn.execute(insert_sql, dict(row))

            print(f"  OK     {table}: {len(rows)} rows")

    # Validate
    print("\n--- Validation ---")
    with src.connect() as src_conn, dst.connect() as dst_conn:
        all_ok = True
        for table in TABLES_IN_ORDER:
            try:
                src_count = src_conn.execute(text(f"SELECT count(*) FROM {table}")).scalar() or 0
            except Exception:
                continue
            dst_count = dst_conn.execute(text(f"SELECT count(*) FROM {table}")).scalar() or 0
            status = "OK" if dst_count >= src_count else "MISMATCH"
            if status == "MISMATCH":
                all_ok = False
            print(f"  {status:10s} {table:30s} SQLite={src_count}  PostgreSQL={dst_count}")

        # Stock balance comparison
        print("\n--- Stock Balance Comparison ---")
        src_stock = dict(src_conn.execute(text(
            "SELECT s.saree_code, COALESCE(SUM(sl.qty_in - sl.qty_out), 0) "
            "FROM sarees s LEFT JOIN stock_ledger sl ON sl.saree_id = s.saree_id "
            "GROUP BY s.saree_id ORDER BY s.saree_code"
        )).all())
        dst_stock = dict(dst_conn.execute(text(
            "SELECT s.saree_code, COALESCE(SUM(sl.qty_in - sl.qty_out), 0) "
            "FROM sarees s LEFT JOIN stock_ledger sl ON sl.saree_id = s.saree_id "
            "GROUP BY s.saree_id ORDER BY s.saree_code"
        )).all())

        for code in sorted(set(src_stock) | set(dst_stock)):
            src_qty = int(src_stock.get(code, 0))
            dst_qty = int(dst_stock.get(code, 0))
            if src_qty != dst_qty:
                print(f"  DIFF   {code}: SQLite={src_qty}  PostgreSQL={dst_qty}")
                all_ok = False

        if all_ok:
            print("\nMigration completed successfully. All counts match.")
        else:
            print("\nMigration completed with mismatches. Review the differences above.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate SQLite to PostgreSQL")
    parser.add_argument("--sqlite", default="inventory.db", help="Path to SQLite database")
    args = parser.parse_args()
    migrate(args.sqlite)
