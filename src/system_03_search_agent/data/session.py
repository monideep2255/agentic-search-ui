"""Session factory and FastAPI dependency for the user-data database.

Depends on:
    - system_03_search_agent.data.base (get_engine)

Reads:
    - Nothing directly. Delegates to base.get_engine(), which reads
      USER_DB_URL.

Writes:
    - Nothing.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker

from system_03_search_agent.data.base import get_engine

_session_factory: sessionmaker[Session] | None = None


def get_session_factory() -> sessionmaker[Session]:
    """Return the process-wide session factory, creating it on first use."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _session_factory


def reset_session_factory() -> None:
    """Clear the process-wide session factory.

    Intended for tests that need a fresh factory after resetting the engine,
    never called by application code during normal operation.
    """
    global _session_factory
    _session_factory = None


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide one transactional scope: commit on success, rollback on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a database session, closed after the request."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
