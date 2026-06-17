"""Database engine, session factory, and initialization helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
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
    """Create database tables for the offline SQLite store and seed defaults."""
    from database.models import entities  # noqa: F401
    from database.models.entities import VendorProcessType

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        for process_type in ["Dyeing", "Stoning", "Finishing", "Printing"]:
            exists = session.query(VendorProcessType).filter_by(process_type=process_type).first()
            if exists is None:
                session.add(VendorProcessType(process_type=process_type))
        session.commit()
