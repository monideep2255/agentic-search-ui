"""Alembic environment script for the user-data schema migrations.

Depends on:
    - system_03_search_agent.data.base (Base, get_user_db_url)
    - system_03_search_agent.data.models (imported for its side effect of
      registering every table on Base.metadata)

Reads:
    - Environment variable: USER_DB_URL. Never logged; alembic.ini carries
      no sqlalchemy.url key so a connection string with credentials is
      never committed to a config file.

Writes:
    - Nothing directly. DDL execution is owned by the revision scripts
      under alembic/versions/.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make the src/ layout importable when Alembic runs standalone (not via pytest,
# which already has pythonpath = ["src"] configured in pyproject.toml).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from system_03_search_agent.data import models  # noqa: F401  (registers tables)
from system_03_search_agent.data.base import Base, get_user_db_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Resolved at runtime from the environment, never hardcoded in alembic.ini.
config.set_main_option("sqlalchemy.url", get_user_db_url())

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode, emitting SQL without a live connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode, against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
