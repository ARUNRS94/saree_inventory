from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

BACKEND_ROOT = Path(__file__).resolve().parents[2]
# Any fixed 64-bit key works; it only has to be the same across instances.
_ADVISORY_LOCK_KEY = 4815162342


def _alembic_config() -> Config:
    # Built in memory rather than from alembic.ini so env.py skips fileConfig()
    # and leaves uvicorn's logging handlers alone.
    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.sync_database_url)
    return cfg


def _upgrade_to_head() -> None:
    # A session-scoped advisory lock serialises concurrent container boots: the
    # second instance waits, then finds the database already at head and no-ops.
    # The lock is taken inside an open transaction so a transaction-mode pooler
    # pins the server connection for its lifetime.
    lock_engine = create_engine(settings.sync_database_url, poolclass=NullPool)
    try:
        with lock_engine.connect() as lock_conn:
            lock_conn.execute(text("SET lock_timeout = '60s'"))
            lock_conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK_KEY})
            command.upgrade(_alembic_config(), "head")
            lock_conn.rollback()
    finally:
        lock_engine.dispose()


async def run_migrations() -> None:
    """Bring the database to head on start-up for hosts with no release hook (Vercel)."""
    if not settings.AUTO_MIGRATE or settings.is_sqlite:
        return
    try:
        await asyncio.to_thread(_upgrade_to_head)
        logger.info("Database schema is at head.")
    except Exception:
        logger.exception("Automatic migration failed - run 'alembic upgrade head' manually.")
