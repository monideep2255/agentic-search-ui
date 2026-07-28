"""Declarative base and engine for the user-data database.

Depends on:
    - Environment variable: USER_DB_URL

Reads:
    - Environment variable: USER_DB_URL, read fresh on first engine creation.
      Never hardcoded, never defaulted, and never logged.

Writes:
    - Nothing. Table creation and migration are owned exclusively by Alembic
      (alembic/versions/), never by Base.metadata.create_all() in application
      code.

This module never imports, references, or constructs a connection to the
knowledge-graph database or its read-only role. The engine here is built
only from USER_DB_URL, which points at the separate search_agent_users
instance.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base shared by every user-data ORM model."""


def get_user_db_url() -> str:
    """Return the user-data connection string from the environment.

    Raises:
        RuntimeError: if USER_DB_URL is not set. There is no default,
            fallback, or hardcoded connection string: a silent fallback here
            could point the application at the wrong database.
    """
    url = os.environ.get("USER_DB_URL")
    if not url:
        raise RuntimeError(
            "USER_DB_URL is not set. Set it in the environment before "
            "connecting to the user-data database (see env.example)."
        )
    return url


def create_user_db_engine(url: str | None = None) -> Engine:
    """Build a SQLAlchemy engine bound to the user-data database.

    Args:
        url: an explicit connection string to use instead of resolving
            USER_DB_URL. Intended for tests that need a scoped connection;
            application code should omit this and let the engine resolve
            USER_DB_URL itself.
    """
    return create_engine(url or get_user_db_url(), pool_pre_ping=True, future=True)


_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first use."""
    global _engine
    if _engine is None:
        _engine = create_user_db_engine()
    return _engine


def reset_engine() -> None:
    """Dispose of and clear the process-wide engine.

    Intended for tests that need a fresh engine after changing USER_DB_URL,
    never called by application code during normal operation.
    """
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
