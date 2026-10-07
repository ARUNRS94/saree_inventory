"""Start-up migration repair: a dropped schema must not leave Alembic thinking it is at head."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text

from app.core.migrations import _alembic_config, _heal_orphaned_version


@pytest.fixture
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'probe.db'}")
    yield eng
    eng.dispose()


def _stamp(engine, revision: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text("INSERT INTO alembic_version VALUES (:r)"), {"r": revision})


def test_clears_a_version_left_behind_by_a_dropped_schema(engine):
    _stamp(engine, "003")
    assert _heal_orphaned_version(engine) is True
    with engine.connect() as conn:
        assert "alembic_version" not in inspect(conn).get_table_names()


def test_keeps_the_version_when_the_tables_are_still_there(engine):
    _stamp(engine, "003")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE items (item_id INTEGER PRIMARY KEY)"))

    assert _heal_orphaned_version(engine) is False
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "003"


def test_does_nothing_on_a_completely_empty_database(engine):
    assert _heal_orphaned_version(engine) is False


def test_does_nothing_when_the_version_table_is_empty(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))

    assert _heal_orphaned_version(engine) is False
    with engine.connect() as conn:
        assert "alembic_version" in inspect(conn).get_table_names()


def test_percent_in_the_password_survives_the_alembic_config(monkeypatch):
    """URL-encoded Supabase passwords are full of '%', which ConfigParser treats as interpolation."""
    url = "postgresql+psycopg2://postgres.ref:p%40ss%2Fword@db.supabase.co:5432/postgres"
    monkeypatch.setattr("app.core.migrations.settings.DATABASE_URL_SYNC", url)
    assert _alembic_config().get_main_option("sqlalchemy.url") == url
