from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings

# asyncpg takes only a handful of query parameters; libpq options and pooler hints make it raise.
_ASYNCPG_PARAMS = {"ssl"}

# Query parameters no PostgreSQL driver accepts: Supabase appends `pgbouncer`/`supa`,
# Prisma-style URLs add connection_limit/pool_timeout/schema.
_NON_DRIVER_PARAMS = {"pgbouncer", "supa", "connection_limit", "pool_timeout", "schema"}

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
        cleaned: dict[str, str] = {}
        for key, value in params:
            if key == "sslmode":
                cleaned["ssl"] = "disable" if value == "disable" else "require"
            elif key in _ASYNCPG_PARAMS:
                cleaned[key] = value
        params = list(cleaned.items())
    else:
        params = [(k, v) for k, v in params if k not in _NON_DRIVER_PARAMS]

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

    # Argon2id cost. Defaults follow the OWASP minimum (m=19MiB, t=2, p=1), which suits
    # the single vCPU a serverless container gets; the library default of p=4 just contends.
    ARGON2_TIME_COST: int = 2
    ARGON2_MEMORY_KIB: int = 19456
    ARGON2_PARALLELISM: int = 1

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
        parts = urlsplit(self.DATABASE_URL)
        host = parts.hostname or ""
        # Neon's PgBouncer host, Supabase's transaction pooler (port 6543), or an explicit hint.
        return "-pooler." in host or parts.port == 6543 or "pgbouncer" in self.DATABASE_URL

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
