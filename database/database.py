"""Database engine, session factory, and initialization helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config.settings import DATABASE_URL


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create database tables for the offline SQLite store."""
    from database.models import entities  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()


def _run_lightweight_migrations() -> None:
    """Add new columns required by the contact/item workflow to existing SQLite DBs."""
    inspector = inspect(engine)
    with engine.begin() as connection:
        supplier_columns = {column["name"] for column in inspector.get_columns("suppliers")}
        if "contact_type" not in supplier_columns:
            connection.execute(text("ALTER TABLE suppliers ADD COLUMN contact_type VARCHAR(30) DEFAULT 'RM vendor'"))
        item_columns = {column["name"] for column in inspector.get_columns("sarees")}
        if "stock_out_saree_id" not in {column["name"] for column in inspector.get_columns("purchase_order_items")}:
            connection.execute(text("ALTER TABLE purchase_order_items ADD COLUMN stock_out_saree_id INTEGER"))
        connection.execute(text("UPDATE suppliers SET contact_type = 'RM vendor' WHERE contact_type IS NULL OR contact_type = ''"))
        connection.execute(text(
            "INSERT INTO suppliers (supplier_name, contact_person, phone, gst_no, address, contact_type, is_active) "
            "SELECT vendor_name, contact_person, phone, gst_no, address, 'Sub vendor', is_active FROM vendors "
            "WHERE NOT EXISTS (SELECT 1 FROM suppliers WHERE suppliers.supplier_name = vendors.vendor_name AND suppliers.contact_type = 'Sub vendor')"
        ))
        if "fabric" in item_columns:
            connection.execute(text("UPDATE sarees SET fabric = 'FG' WHERE fabric IS NULL OR fabric = ''"))
