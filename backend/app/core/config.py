from __future__ import annotations

from pydantic_settings import BaseSettings


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
    def sync_database_url(self) -> str:
        if self.DATABASE_URL_SYNC:
            return self.DATABASE_URL_SYNC
        return self.DATABASE_URL.replace("+asyncpg", "+psycopg2").replace("+aiosqlite", "")


settings = Settings()
