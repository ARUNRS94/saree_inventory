"""Connection-string handling and production guardrails.

These lock down the URL rewriting that lets the same code run against Neon, Supabase,
RDS or a plain VPS without edits.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest

from app.core.config import Settings

NEON = ("postgresql://neondb_owner:secret@ep-morning-frost-b39gtx3o-pooler.c-4."
        "ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")
SUPABASE_TXN = ("postgres://postgres.abcdefghijklmnop:secret@aws-0-us-east-1.pooler.supabase.com"
                ":6543/postgres?sslmode=require&supa=base-pooler.x")
SUPABASE_SESSION = ("postgres://postgres.abcdefghijklmnop:secret@aws-0-us-east-1.pooler.supabase.com"
                    ":5432/postgres?sslmode=require")
PRISMA = ("postgres://user:secret@host.example.com:6543/db"
          "?sslmode=require&pgbouncer=true&connection_limit=1&pool_timeout=0")
PLAIN = "postgresql://user:secret@db.internal:5432/inventory"


def make(**kwargs) -> Settings:
    """Ignore the developer's own .env so these assertions are deterministic."""
    return Settings(_env_file=None, **kwargs)


def query_of(url: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(url).query)


# --- async (runtime) URL ---

@pytest.mark.parametrize("url", [NEON, SUPABASE_TXN, SUPABASE_SESSION, PRISMA, PLAIN])
def test_runtime_url_always_targets_asyncpg(url):
    assert make(DATABASE_URL=url).async_database_url.startswith("postgresql+asyncpg://")


def test_neon_channel_binding_is_dropped():
    """asyncpg rejects channel_binding, which Neon appends by default."""
    result = make(DATABASE_URL=NEON).async_database_url
    params = query_of(result)
    assert "channel_binding" not in params
    assert "sslmode" not in params
    assert params["ssl"] == ["require"]


def test_supabase_pooler_hints_are_dropped():
    """asyncpg treats unknown query keys as connect() kwargs and raises on them."""
    params = query_of(make(DATABASE_URL=SUPABASE_TXN).async_database_url)
    assert "supa" not in params
    assert params["ssl"] == ["require"]


def test_prisma_style_parameters_are_dropped():
    params = query_of(make(DATABASE_URL=PRISMA).async_database_url)
    assert "pgbouncer" not in params
    assert "connection_limit" not in params
    assert "pool_timeout" not in params
    assert params["ssl"] == ["require"]


def test_sslmode_disable_is_preserved_as_ssl_disable():
    url = "postgresql://u:p@localhost:5432/db?sslmode=disable"
    assert query_of(make(DATABASE_URL=url).async_database_url)["ssl"] == ["disable"]


def test_credentials_and_path_survive_rewriting():
    parts = urlsplit(make(DATABASE_URL=SUPABASE_TXN).async_database_url)
    assert parts.username == "postgres.abcdefghijklmnop"
    assert parts.password == "secret"
    assert parts.hostname == "aws-0-us-east-1.pooler.supabase.com"
    assert parts.port == 6543
    assert parts.path == "/postgres"


def test_an_already_correct_url_is_left_alone():
    url = "postgresql+asyncpg://u:p@host/db"
    assert make(DATABASE_URL=url).async_database_url == url


def test_sqlite_is_untouched():
    settings = make(DATABASE_URL="sqlite+aiosqlite:///./dev.db")
    assert settings.is_sqlite
    assert settings.async_database_url == "sqlite+aiosqlite:///./dev.db"
    assert settings.sync_database_url == "sqlite:///./dev.db"


# --- sync (Alembic) URL ---

@pytest.mark.parametrize("url", [NEON, SUPABASE_TXN, PLAIN])
def test_migration_url_always_targets_psycopg2(url):
    assert make(DATABASE_URL=url).sync_database_url.startswith("postgresql+psycopg2://")


def test_migration_url_keeps_libpq_parameters():
    """psycopg2 understands sslmode and channel_binding, so they must survive."""
    params = query_of(make(DATABASE_URL=NEON).sync_database_url)
    assert params["sslmode"] == ["require"]
    assert params["channel_binding"] == ["require"]


def test_migration_url_still_drops_non_driver_parameters():
    params = query_of(make(DATABASE_URL=PRISMA).sync_database_url)
    assert "pgbouncer" not in params
    assert "connection_limit" not in params
    assert params["sslmode"] == ["require"]


def test_explicit_sync_url_wins():
    settings = make(DATABASE_URL=SUPABASE_TXN, DATABASE_URL_SYNC=SUPABASE_SESSION)
    assert urlsplit(settings.sync_database_url).port == 5432
    assert urlsplit(settings.async_database_url).port == 6543


# --- pooler detection ---

@pytest.mark.parametrize("url,expected", [
    (NEON, True),                # Neon's PgBouncer host
    (SUPABASE_TXN, True),        # Supabase transaction pooler
    (PRISMA, True),              # explicit pgbouncer hint
    (SUPABASE_SESSION, False),   # session pooler keeps prepared statements
    (PLAIN, False),
])
def test_transaction_poolers_disable_prepared_statements(url, expected):
    assert make(DATABASE_URL=url).disable_prepared_statements is expected


def test_prepared_statements_can_be_disabled_by_hand():
    assert make(DATABASE_URL=PLAIN, DB_DISABLE_PREPARED_STATEMENTS=True).disable_prepared_statements is True


# --- diagnostics ---

def test_database_target_hides_the_password():
    target = make(DATABASE_URL=SUPABASE_TXN).database_target
    assert "secret" not in target
    assert target == ("postgres.abcdefghijklmnop:<len=6>@"
                      "aws-0-us-east-1.pooler.supabase.com:6543/postgres")


def test_database_target_flags_a_quoted_password():
    url = 'postgresql+asyncpg://user:"secret"@host:5432/db'
    assert "HAS-QUOTES" in make(DATABASE_URL=url).database_target


def test_database_target_reports_password_length_for_paste_errors():
    url = "postgresql+asyncpg://user:<new>@host:5432/db"
    assert "<len=5>" in make(DATABASE_URL=url).database_target


def test_database_target_handles_sqlite():
    assert make(DATABASE_URL="sqlite+aiosqlite:///./dev.db").database_target.endswith("<no host>")


# --- derived settings ---

def test_cors_origins_are_split_and_trimmed():
    settings = make(CORS_ORIGINS=" https://a.example.com , https://b.example.com ,, ")
    assert settings.cors_origins_list == ["https://a.example.com", "https://b.example.com"]


def test_google_is_disabled_without_a_client_id():
    assert make(GOOGLE_CLIENT_ID="").google_enabled is False
    assert make(GOOGLE_CLIENT_ID="abc.apps.googleusercontent.com").google_enabled is True


def test_google_allowed_domains_are_normalised():
    settings = make(GOOGLE_ALLOWED_DOMAINS=" Example.COM , other.org ")
    assert settings.google_allowed_domains_list == ["example.com", "other.org"]


# --- production guardrails ---

def test_development_is_never_blocked():
    assert make(ENVIRONMENT="development", SECRET_KEY="change-me").validate_for_production() == []


@pytest.mark.parametrize("environment", ["production", "PRODUCTION", " prod "])
def test_production_is_recognised(environment):
    assert make(ENVIRONMENT=environment).is_production is True


def test_production_rejects_placeholder_secrets():
    problems = make(
        ENVIRONMENT="production",
        DATABASE_URL=PLAIN,
        SECRET_KEY="change-me",
        JWT_SECRET_KEY="dev-only-change-me",
        CORS_ORIGINS="https://app.example.com",
    ).validate_for_production()
    assert any("SECRET_KEY" in p for p in problems)
    assert any("JWT_SECRET_KEY" in p for p in problems)


def test_production_rejects_short_secrets():
    problems = make(
        ENVIRONMENT="production",
        DATABASE_URL=PLAIN,
        SECRET_KEY="a" * 31,
        JWT_SECRET_KEY="b" * 31,
        CORS_ORIGINS="https://app.example.com",
    ).validate_for_production()
    assert len([p for p in problems if "32 characters" in p]) == 2


def test_production_rejects_sqlite_and_empty_cors():
    problems = make(
        ENVIRONMENT="production",
        DATABASE_URL="sqlite+aiosqlite:///./dev.db",
        SECRET_KEY="a" * 40,
        JWT_SECRET_KEY="b" * 40,
        CORS_ORIGINS="",
    ).validate_for_production()
    assert any("SQLite" in p for p in problems)
    assert any("CORS_ORIGINS" in p for p in problems)


def test_a_correct_production_configuration_passes():
    assert make(
        ENVIRONMENT="production",
        DATABASE_URL=SUPABASE_TXN,
        SECRET_KEY="a" * 48,
        JWT_SECRET_KEY="b" * 48,
        CORS_ORIGINS="https://app.example.com",
    ).validate_for_production() == []
