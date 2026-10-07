from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

BACKEND_ROOT = Path(__file__).resolve().parents[2]
# Any fixed 64-bit key works; it only has to be the same across instances.
_ADVISORY_LOCK_KEY = 4815162342

# Any one of these proves the schema was really built, not just stamped.
_CORE_TABLES = frozenset({"users", "roles", "permissions", "items", "contacts",
                          "purchase_orders", "grns", "stock_ledger"})

# Last start-up outcome, surfaced on /api/health/db so a silent skip is visible.
_status: dict = {"ran": False, "detail": "Not attempted.", "error": None}


def _alembic_config() -> Config:
    # Built in memory rather than from alembic.ini so env.py skips fileConfig()
    # and leaves uvicorn's logging handlers alone.
    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    # ConfigParser treats '%' as interpolation, and URL-encoded passwords are full of it.
    cfg.set_main_option("sqlalchemy.url", settings.sync_database_url.replace("%", "%%"))
    return cfg


def _heal_orphaned_version(engine) -> bool:
    """Dropping the app's tables leaves alembic_version behind, which makes Alembic no-op.

    Clearing it is only safe when none of the real tables survive, so there is
    nothing a replay could overwrite.
    """
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        present = set(inspect(conn).get_table_names())
        if "alembic_version" not in present or _CORE_TABLES & present:
            return False
        stamped = conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        if not stamped:
            return False
        conn.execute(text("DROP TABLE alembic_version"))
        logger.warning("Found alembic_version at %s but no application tables - "
                       "clearing it so the migrations replay from scratch.", ", ".join(stamped))
        return True


def _upgrade_to_head() -> bool:
    """Returns True when a stale alembic_version had to be cleared first."""
    # A session-scoped advisory lock serialises concurrent container boots: the
    # second instance waits, then finds the database already at head and no-ops.
    # The lock is taken inside an open transaction so a transaction-mode pooler
    # pins the server connection for its lifetime.
    lock_engine = create_engine(settings.sync_database_url, poolclass=NullPool)
    try:
        with lock_engine.connect() as lock_conn:
            lock_conn.execute(text("SET lock_timeout = '60s'"))
            lock_conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK_KEY})
            # Runs on its own connection because the repair has to commit; the
            # advisory lock above still keeps other instances out of this block.
            healed = _heal_orphaned_version(lock_engine)
            command.upgrade(_alembic_config(), "head")
            lock_conn.rollback()
            return healed
    finally:
        lock_engine.dispose()


async def run_migrations() -> None:
    """Bring the database to head on start-up for hosts with no release hook (Vercel)."""
    if settings.is_sqlite:
        _status.update(ran=False, detail="Skipped: DATABASE_URL points at SQLite, not PostgreSQL.")
        logger.warning("Migrations skipped - DATABASE_URL points at SQLite (%s). "
                       "Set DATABASE_URL to your PostgreSQL connection string.", settings.database_target)
        return
    if not settings.AUTO_MIGRATE:
        _status.update(ran=False, detail="Skipped: AUTO_MIGRATE is off.")
        logger.warning("Migrations skipped - AUTO_MIGRATE is off. Run 'alembic upgrade head' manually.")
        return
    try:
        healed = await asyncio.to_thread(_upgrade_to_head)
        detail = "Schema is at head (replayed after a stale alembic_version)." if healed else "Schema is at head."
        _status.update(ran=True, detail=detail, error=None)
        logger.info(detail)
    except Exception as exc:
        _status.update(ran=False, detail="Migration failed.", error=f"{type(exc).__name__}: {exc}")
        logger.exception("Automatic migration failed - run 'alembic upgrade head' manually.")


async def schema_status() -> dict:
    """What the database reports versus what this build expects."""
    from alembic.script import ScriptDirectory

    expected = ScriptDirectory.from_config(_alembic_config()).get_current_head()
    current: str | None = None
    tables = 0
    if not settings.is_sqlite:
        def _probe() -> tuple[str | None, int]:
            engine = create_engine(settings.sync_database_url, poolclass=NullPool)
            try:
                with engine.connect() as conn:
                    revision = conn.execute(text(
                        "SELECT version_num FROM alembic_version LIMIT 1"
                    )).scalar() if conn.dialect.has_table(conn, "alembic_version") else None
                    count = conn.execute(text(
                        "SELECT count(*) FROM information_schema.tables WHERE table_schema = current_schema()"
                    )).scalar() or 0
                return revision, int(count)
            finally:
                engine.dispose()
        try:
            current, tables = await asyncio.to_thread(_probe)
        except Exception as exc:
            return {**_status, "expected_revision": expected, "error": f"{type(exc).__name__}: {exc}"}
    return {**_status, "expected_revision": expected, "current_revision": current, "tables": tables}
