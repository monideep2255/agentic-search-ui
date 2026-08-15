"""Integration tests for `data/guest_sessions.py`'s creation and atomic spend (T-4.10-02).

Hits real local PostgreSQL, mirroring test_migration.py's scratch-database
pattern (create a uniquely named throwaway database, migrate it to head,
drop it when the module's tests are done), because the property under
test, that at most FREE_RUN_ALLOWANCE of several concurrent spends against
the same guest ever succeed, cannot be observed against SQLite or a mock:
it is a guarantee about how a real Postgres row lock resolves two
transactions racing the same UPDATE.

Skips cleanly (does not fail) when USER_DB_URL is unreachable, matching
every other live-database suite in this repo.

What this file covers: `create_guest_session`'s shape, `spend_one_run`'s
three states (spent, exhausted, revoked-or-unknown), its valid/invalid/null
input handling, and the concurrency guarantee design decision 3 exists for.
What it deliberately does not cover: HTTP-level behavior (`POST
/auth/guest`, `GET /v1/allowance`), which is T-4.10-04's, and is exercised
by the phase 4.10 premise gate instead.
"""

from __future__ import annotations

import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

from alembic import command
from system_03_search_agent.data.guest_sessions import (
    FREE_RUN_ALLOWANCE,
    SpendState,
    create_guest_session,
    spend_one_run,
)
from system_03_search_agent.data.models import GuestSession

REPO_ROOT = Path(__file__).resolve().parents[3]
USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")


def _can_connect(url: str) -> bool:
    try:
        probe_engine = sa.create_engine(url)
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


if not _can_connect(USER_DB_URL):
    pytest.skip(
        "search_agent_users PostgreSQL database is not reachable; "
        "set USER_DB_URL and ensure the server is running to run this suite",
        allow_module_level=True,
    )


def _with_db_name(url: str, db_name: str) -> str:
    """Return `url` with its path database name replaced by `db_name`,
    keeping the same host, port, and credentials."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{db_name}", parts.query, parts.fragment))


def _alembic_config() -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return cfg


@pytest.fixture(scope="module")
def scratch_db_url():
    """A uniquely named, throwaway database, migrated to head once for this
    module and dropped once every test in this module has finished.

    Never the database USER_DB_URL names: only this freshly created,
    randomly named database is a migration or write target anywhere below.
    USER_DB_URL itself is only touched transiently, and only so
    `alembic/env.py` (which reads it to resolve its target) points at the
    scratch database while `command.upgrade` runs; it is restored to
    whatever it held before, in a `finally` block, whether or not the
    upgrade succeeds. Every function-scoped fixture and test in this
    module then talks to the scratch database directly through an engine
    built from `url`, never by reading the environment, so nothing else in
    this file depends on that transient mutation.
    """
    db_name = f"guest_sessions_scratch_{uuid.uuid4().hex}"
    # Program-generated, never user input, but asserted anyway so this name
    # can never carry anything but a safe, quotable Postgres identifier.
    assert re.fullmatch(r"[a-z0-9_]+", db_name)
    admin_url = _with_db_name(USER_DB_URL, "postgres")

    creator_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with creator_engine.connect() as conn:
            conn.execute(sa.text(f'CREATE DATABASE "{db_name}"'))
    finally:
        creator_engine.dispose()

    url = _with_db_name(USER_DB_URL, db_name)
    previous_env_value = os.environ.get("USER_DB_URL")
    os.environ["USER_DB_URL"] = url
    try:
        command.upgrade(_alembic_config(), "head")
    finally:
        if previous_env_value is None:
            os.environ.pop("USER_DB_URL", None)
        else:
            os.environ["USER_DB_URL"] = previous_env_value

    try:
        yield url
    finally:
        dropper_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            with dropper_engine.connect() as conn:
                # Drop any lingering connections first; Postgres refuses to
                # drop a database with active connections.
                conn.execute(
                    sa.text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :name AND pid <> pg_backend_pid()"
                    ),
                    {"name": db_name},
                )
                conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        finally:
            dropper_engine.dispose()


@pytest.fixture()
def db_session(scratch_db_url):
    """A fresh Session bound to the already-migrated scratch database,
    closed after the test. Built directly from `scratch_db_url`, never by
    reading USER_DB_URL from the environment."""
    engine = sa.create_engine(scratch_db_url, future=True)
    factory = sessionmaker(bind=engine, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# create_guest_session
# ---------------------------------------------------------------------------


def test_create_guest_session_returns_a_row_with_zero_allowance_used(db_session) -> None:
    guest = create_guest_session(db_session)
    assert isinstance(guest.id, uuid.UUID)
    assert guest.runs_used == 0
    assert guest.revoked_at is None
    assert guest.migrated_to_user_id is None


def test_create_guest_session_persists_and_is_visible_to_a_fresh_lookup(db_session) -> None:
    guest = create_guest_session(db_session)
    reloaded = db_session.get(GuestSession, guest.id)
    assert reloaded is not None
    assert reloaded.runs_used == 0


def test_create_guest_session_two_calls_produce_two_distinct_ids(db_session) -> None:
    first = create_guest_session(db_session)
    second = create_guest_session(db_session)
    assert first.id != second.id


def test_create_guest_session_invalid_input_non_session_raises(db_session) -> None:
    with pytest.raises(TypeError):
        create_guest_session("not-a-session")  # type: ignore[arg-type]


def test_create_guest_session_missing_input_none_raises(db_session) -> None:
    with pytest.raises(TypeError):
        create_guest_session(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# spend_one_run: valid input, the SPENT path
# ---------------------------------------------------------------------------


def test_spend_one_run_first_call_returns_spent_with_count_one(db_session) -> None:
    guest = create_guest_session(db_session)
    result = spend_one_run(db_session, str(guest.id))
    assert result.state == SpendState.SPENT
    assert result.runs_used == 1


def test_spend_one_run_accepts_a_uuid_object_directly(db_session) -> None:
    guest = create_guest_session(db_session)
    result = spend_one_run(db_session, guest.id)
    assert result.state == SpendState.SPENT
    assert result.runs_used == 1


def test_spend_one_run_up_to_the_cap_all_succeed_in_order(db_session) -> None:
    guest = create_guest_session(db_session)
    for expected in range(1, FREE_RUN_ALLOWANCE + 1):
        result = spend_one_run(db_session, guest.id)
        assert result.state == SpendState.SPENT
        assert result.runs_used == expected


def test_spend_one_run_honors_a_caller_supplied_cap(db_session) -> None:
    guest = create_guest_session(db_session)
    assert spend_one_run(db_session, guest.id, cap=1).state == SpendState.SPENT
    assert spend_one_run(db_session, guest.id, cap=1).state == SpendState.EXHAUSTED


# ---------------------------------------------------------------------------
# spend_one_run: the EXHAUSTED path
# ---------------------------------------------------------------------------


def test_spend_one_run_past_the_cap_returns_exhausted_with_the_final_count(db_session) -> None:
    guest = create_guest_session(db_session)
    for _ in range(FREE_RUN_ALLOWANCE):
        assert spend_one_run(db_session, guest.id).state == SpendState.SPENT
    result = spend_one_run(db_session, guest.id)
    assert result.state == SpendState.EXHAUSTED
    assert result.runs_used == FREE_RUN_ALLOWANCE


def test_spend_one_run_exhausted_call_does_not_advance_the_stored_count(db_session) -> None:
    guest = create_guest_session(db_session)
    for _ in range(FREE_RUN_ALLOWANCE):
        spend_one_run(db_session, guest.id)
    spend_one_run(db_session, guest.id)
    reloaded = db_session.get(GuestSession, guest.id)
    assert reloaded.runs_used == FREE_RUN_ALLOWANCE


# ---------------------------------------------------------------------------
# spend_one_run: the REVOKED_OR_UNKNOWN path
# ---------------------------------------------------------------------------


def test_spend_one_run_on_a_revoked_session_returns_revoked_or_unknown(db_session) -> None:
    guest = create_guest_session(db_session)
    db_session.execute(
        sa.text("UPDATE guest_sessions SET revoked_at = now() WHERE id = :id"),
        {"id": guest.id},
    )
    db_session.commit()
    result = spend_one_run(db_session, guest.id)
    assert result.state == SpendState.REVOKED_OR_UNKNOWN
    assert result.runs_used is None


def test_spend_one_run_on_an_unknown_guest_id_returns_revoked_or_unknown(db_session) -> None:
    result = spend_one_run(db_session, str(uuid.uuid4()))
    assert result.state == SpendState.REVOKED_OR_UNKNOWN
    assert result.runs_used is None


def test_spend_one_run_a_revoked_session_gains_no_count(db_session) -> None:
    guest = create_guest_session(db_session)
    db_session.execute(
        sa.text("UPDATE guest_sessions SET revoked_at = now() WHERE id = :id"),
        {"id": guest.id},
    )
    db_session.commit()
    spend_one_run(db_session, guest.id)
    reloaded = db_session.get(GuestSession, guest.id)
    assert reloaded.runs_used == 0


# ---------------------------------------------------------------------------
# spend_one_run: invalid and null input
# ---------------------------------------------------------------------------


def test_spend_one_run_invalid_guest_id_string_raises_value_error(db_session) -> None:
    with pytest.raises(ValueError):
        spend_one_run(db_session, "not-a-uuid")


def test_spend_one_run_missing_guest_id_none_raises_type_error(db_session) -> None:
    with pytest.raises(TypeError):
        spend_one_run(db_session, None)  # type: ignore[arg-type]


def test_spend_one_run_empty_guest_id_raises_value_error(db_session) -> None:
    with pytest.raises(ValueError):
        spend_one_run(db_session, "")


def test_spend_one_run_non_positive_cap_raises_value_error(db_session) -> None:
    guest = create_guest_session(db_session)
    with pytest.raises(ValueError):
        spend_one_run(db_session, guest.id, cap=0)


def test_spend_one_run_negative_cap_raises_value_error(db_session) -> None:
    guest = create_guest_session(db_session)
    with pytest.raises(ValueError):
        spend_one_run(db_session, guest.id, cap=-1)


def test_spend_one_run_non_int_cap_raises_type_error(db_session) -> None:
    guest = create_guest_session(db_session)
    with pytest.raises(TypeError):
        spend_one_run(db_session, guest.id, cap="5")  # type: ignore[arg-type]


def test_spend_one_run_bool_cap_raises_type_error(db_session) -> None:
    """bool is a subclass of int; excluded explicitly, matching guest.py's
    own exclusion of bool from its numeric `exp` check."""
    guest = create_guest_session(db_session)
    with pytest.raises(TypeError):
        spend_one_run(db_session, guest.id, cap=True)  # type: ignore[arg-type]


def test_spend_one_run_non_session_raises_type_error() -> None:
    with pytest.raises(TypeError):
        spend_one_run("not-a-session", str(uuid.uuid4()))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Concurrency: the property a read-then-write implementation silently fails
# ---------------------------------------------------------------------------


def test_the_allowance_holds_under_concurrent_spends(scratch_db_url) -> None:
    """FREE_RUN_ALLOWANCE + 1 threads race the cap boundary on one guest.

    Runs against genuinely separate connections and separate SQLAlchemy
    Sessions, one per thread pulled from a pooled engine, so it is a real
    Postgres row lock under test, not Python-level locking: psycopg2
    releases the GIL during blocking network I/O, so these threads issue
    overlapping UPDATE statements against the database, and the property
    under test is how Postgres resolves that overlap.

    If `spend_one_run` ever regressed to a SELECT-then-UPDATE, more than
    FREE_RUN_ALLOWANCE threads could read a pre-increment count under the
    cap before any of their UPDATEs land, and all of them would proceed to
    write, which is exactly the bug design decision 3 exists to prevent.
    True concurrency is achieved here, so no SQL-shape-only fallback is
    needed for this test.
    """
    engine = sa.create_engine(scratch_db_url, future=True)
    factory = sessionmaker(bind=engine, future=True)
    setup_session = factory()
    try:
        guest_id = create_guest_session(setup_session).id
    finally:
        setup_session.close()

    def _attempt(_: int) -> SpendState:
        thread_session = factory()
        try:
            return spend_one_run(thread_session, guest_id).state
        finally:
            thread_session.close()

    try:
        with ThreadPoolExecutor(max_workers=FREE_RUN_ALLOWANCE + 1) as pool:
            results = list(pool.map(_attempt, range(FREE_RUN_ALLOWANCE + 1)))
    finally:
        engine.dispose()

    spent = [state for state in results if state == SpendState.SPENT]
    exhausted = [state for state in results if state == SpendState.EXHAUSTED]
    assert len(spent) <= FREE_RUN_ALLOWANCE, (
        f"{len(spent)} of {FREE_RUN_ALLOWANCE + 1} concurrent spends succeeded; "
        f"the allowance is not being enforced atomically"
    )
    assert len(spent) + len(exhausted) == FREE_RUN_ALLOWANCE + 1
