from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.core.config import settings
from app.core.database import Base
from app.models import *  # noqa: F401,F403

config = context.config
# ConfigParser treats '%' as interpolation, and URL-encoded passwords are full of it.
config.set_main_option("sqlalchemy.url", settings.sync_database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            # SET LOCAL keeps this inside Alembic's transaction. A plain SET here would
            # open one of its own first, leaving Alembic's commit a no-op and the whole
            # upgrade rolled back on close. Fails loudly rather than queueing behind a
            # long read from a previous deployment.
            if connection.dialect.name == "postgresql":
                connection.execute(text("SET LOCAL lock_timeout = '30s'"))
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
