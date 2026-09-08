from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings

# asyncpg rejects these libpq-only connection parameters.
_LIBPQ_ONLY_PARAMS = {"channel_binding", "sslmode", "connect_timeout", "target_session_attrs"}

_INSECURE_SECRETS = {"change-me", "change-me-to-a-random-secret-key", "change-me-to-a-jwt-secret-key",
                     "dev-only-change-me", "secret", "changeme"}


def _rewrite_pg_url(url: str, driver: str) -> str:
    """Point a Postgres URL at the given driver, translating params the driver can't take."""
    if not url or url.startswith("sqlite"):
        return url
    parts = urlsplit(url)
    if not parts.scheme.startswith(("postgres", "postgresql")):
        return url

    params = parse_qsl(parts.query, keep_blank_values=True)
    if driver == "asyncpg":
        rewritten = []
        for key, value in params:
            if key not in _LIBPQ_ONLY_PARAMS:
                rewritten.append((key, value))
            elif key == "sslmode":
                rewritten.append(("ssl", "disable" if value == "disable" else "require"))
        params = rewritten

    return urlunsplit((f"postgresql+{driver}", parts.netloc, parts.path, urlencode(params), parts.fragment))


class Settings(BaseSettings):
    APP_NAME: str = "Inventory Management"
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"
    DATABASE_URL_SYNC: str = ""
    SECRET_KEY: str = "change-me"
    JWT_SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost:5173"
    ENVIRONMENT: str = "development"

    # Connection pooling. Keep pools small: every container instance holds its own.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_RECYCLE_SECONDS: int = 300
    # Required when connecting through a transaction-mode pooler (Neon "-pooler" host, Supabase pgbouncer).
    DB_DISABLE_PREPARED_STATEMENTS: bool = False

    # Google Sign-In (Google Identity Services ID token flow)
    GOOGLE_CLIENT_ID: str = ""
    # When enabled, an unknown Google account is provisioned on first sign-in.
    GOOGLE_ALLOW_SIGNUP: bool = True
    GOOGLE_SIGNUP_ROLE: str = "viewer"
    # Comma-separated list of allowed email domains; empty means any domain.
    GOOGLE_ALLOWED_DOMAINS: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def google_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID)

    @property
    def google_allowed_domains_list(self) -> list[str]:
        return [d.strip().lower() for d in self.GOOGLE_ALLOWED_DOMAINS.split(",") if d.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def async_database_url(self) -> str:
        """Runtime URL, accepting the raw libpq string that Neon and Vercel hand out."""
        return _rewrite_pg_url(self.DATABASE_URL, "asyncpg")

    @property
    def sync_database_url(self) -> str:
        """Alembic URL. psycopg2 understands libpq parameters, so they are left intact."""
        if self.DATABASE_URL_SYNC:
            return _rewrite_pg_url(self.DATABASE_URL_SYNC, "psycopg2")
        if self.is_sqlite:
            return self.DATABASE_URL.replace("+aiosqlite", "")
        return _rewrite_pg_url(self.DATABASE_URL, "psycopg2")

    @property
    def disable_prepared_statements(self) -> bool:
        """Transaction-mode poolers break asyncpg's prepared statements."""
        if self.DB_DISABLE_PREPARED_STATEMENTS:
            return True
        host = urlsplit(self.DATABASE_URL).hostname or ""
        return "-pooler." in host or "pgbouncer" in self.DATABASE_URL

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in {"production", "prod"}

    def validate_for_production(self) -> list[str]:
        """Configuration that is safe locally but dangerous once deployed."""
        problems = []
        if not self.is_production:
            return problems
        for name in ("SECRET_KEY", "JWT_SECRET_KEY"):
            value = getattr(self, name)
            if not value or value in _INSECURE_SECRETS or len(value) < 32:
                problems.append(f"{name} must be set to a unique random value of at least 32 characters.")
        if self.is_sqlite:
            problems.append("DATABASE_URL points at SQLite; production needs PostgreSQL.")
        if not self.cors_origins_list:
            problems.append("CORS_ORIGINS must list the site origin(s).")
        return problems


settings = Settings()
