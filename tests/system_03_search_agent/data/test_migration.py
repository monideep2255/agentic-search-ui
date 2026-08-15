"""Integration tests for the 0001_user_data_schema Alembic migration.

Hits real local PostgreSQL through Alembic's command API, not a mock: the
CHECK constraints, the GIN indexes, and gen_random_uuid() cannot be verified
against SQLite.

F-1.1-01 fix (2026-07-28): the upgrade/downgrade round trip, including the
`alembic downgrade base` test that drops every table, now runs against a
throwaway database created and dropped by this module, never against the
database USER_DB_URL names. USER_DB_URL's own database is used only for the
initial reachability probe below, which is read-only and never a migration
target. The scratch database is created once per test-module run, before
any test executes, and is dropped in a `finally` block after every test in
this module has finished, even if one of them fails.

The whole module skips cleanly (does not fail) when USER_DB_URL is unset or
the PostgreSQL server is unreachable, so CI without a database does not go
red. The connection probe runs once at import time.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command

REPO_ROOT = Path(__file__).resolve().parents[3]
USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")

ALL_TABLES = {
    "users",
    "auth_sessions",
    "sessions",
    "interactions",
    "cq_candidates",
    "saved_queries",
    # Build phase 4.10, revision 0003. Added by the lead rather than by the
    # builder that wrote the migration, which was forbidden from editing an
    # existing test. Adding it here STRENGTHENS both assertions that read
    # this set: line ~159 now requires `upgrade head` to create the table,
    # and the `downgrade base` test now requires it to be dropped again. A
    # new table absent from this set is silently uncovered by both.
    "guest_sessions",
}


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
    """Build an Alembic Config. The connection URL itself is resolved by
    alembic/env.py from the USER_DB_URL environment variable at run time,
    so the caller controls the target database by setting that variable
    (see the `migrated_head` fixture below), never by passing a URL here.
    """
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return cfg


@pytest.fixture(scope="module")
def scratch_db_url():
    """Create a uniquely named, throwaway PostgreSQL database for this
    module's upgrade/downgrade round trip, and drop it once every test in
    this module has finished, even if one of them fails.

    The database USER_DB_URL names is never the target of any CREATE,
    upgrade, or downgrade in this module: only this freshly created,
    randomly named database is.
    """
    db_name = f"migration_scratch_{uuid.uuid4().hex}"
    # Program-generated, never user input, but asserted anyway so this name
    # can never carry anything but a safe, quotable Postgres identifier.
    assert re.fullmatch(r"[a-z0-9_]+", db_name)
    admin_url = _with_db_name(USER_DB_URL, "postgres")

    creator_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with creator_engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        creator_engine.dispose()

    try:
        yield _with_db_name(USER_DB_URL, db_name)
    finally:
        dropper_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            with dropper_engine.connect() as conn:
                # Drop any lingering connections first; Postgres refuses to
                # drop a database with active connections.
                conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :name AND pid <> pg_backend_pid()"
                    ),
                    {"name": db_name},
                )
                conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        finally:
            dropper_engine.dispose()


@pytest.fixture()
def migrated_head(scratch_db_url, monkeypatch):
    """Point Alembic at the scratch database for this test only (via
    monkeypatch, which restores USER_DB_URL automatically at teardown),
    upgrade to head before the test, and unconditionally again after.

    A test in this module downgrades to base to prove the rollback path.
    This fixture guarantees the scratch database is left migrated to head
    when each test ends, regardless of what that test did in between.
    """
    monkeypatch.setenv("USER_DB_URL", scratch_db_url)
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    try:
        yield cfg
    finally:
        command.upgrade(cfg, "head")


def _fresh_engine() -> sa.engine.Engine:
    # Reads USER_DB_URL fresh from the environment, which `migrated_head`
    # has pointed at the scratch database for the duration of the test.
    return sa.create_engine(os.environ["USER_DB_URL"], future=True)


def test_upgrade_creates_all_six_tables(migrated_head):
    engine = _fresh_engine()
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert ALL_TABLES.issubset(tables)
    finally:
        engine.dispose()


def test_extensions_enabled_and_gen_random_uuid_resolves(migrated_head):
    engine = _fresh_engine()
    try:
        with engine.connect() as conn:
            installed = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT extname FROM pg_extension "
                        "WHERE extname IN ('pgcrypto', 'pg_trgm')"
                    )
                )
            }
            assert installed == {"pgcrypto", "pg_trgm"}

            value = conn.execute(text("SELECT gen_random_uuid()")).scalar_one()
            assert isinstance(value, uuid.UUID)
    finally:
        engine.dispose()


def test_interactions_indexes_exist(migrated_head):
    engine = _fresh_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'interactions'")
            ).fetchall()
            names = {row[0] for row in rows}
            assert {
                "idx_interactions_created_at",
                "idx_interactions_user_id",
                "idx_interactions_rubric",
                "idx_interactions_coverage_tags",
                "idx_interactions_query_trgm",
            }.issubset(names)

            # The GIN index on coverage_tags and the trigram index both use
            # the "gin" access method, not the default btree.
            gin_indexes = conn.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename = 'interactions' "
                    "AND indexdef ILIKE '%USING gin%'"
                )
            ).fetchall()
            gin_names = {row[0] for row in gin_indexes}
            assert {"idx_interactions_coverage_tags", "idx_interactions_query_trgm"}.issubset(
                gin_names
            )
    finally:
        engine.dispose()


def test_cq_candidates_status_index_exists(migrated_head):
    engine = _fresh_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'cq_candidates'")
            ).fetchall()
            assert "idx_cq_candidates_status" in {row[0] for row in rows}
    finally:
        engine.dispose()


def test_auth_sessions_refresh_token_hash_is_unique_and_indexed(migrated_head):
    """F-1.1-12 regression: the column every auth call filters by."""
    engine = _fresh_engine()
    try:
        with engine.connect() as conn:
            indexdef = conn.execute(
                text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE tablename = 'auth_sessions' "
                    "AND indexname = 'ux_auth_sessions_refresh_token_hash'"
                )
            ).scalar_one()
            assert "UNIQUE INDEX" in indexdef
            assert "refresh_token_hash" in indexdef

            # And the uniqueness is real, not just declared: a second row
            # carrying the same hash is rejected by the database.
            user_id = conn.execute(
                text(
                    "INSERT INTO users (email, password_hash) "
                    "VALUES (:email, 'not-a-real-hash') RETURNING id"
                ),
                {"email": f"{uuid.uuid4()}@example.com"},
            ).scalar_one()
            insert_session = text(
                "INSERT INTO auth_sessions (user_id, refresh_token_hash, expires_at) "
                "VALUES (:user_id, :token_hash, now() + interval '30 days')"
            )
            params = {"user_id": user_id, "token_hash": "a" * 64}
            conn.execute(insert_session, params)
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(insert_session, params)
            conn.rollback()
    finally:
        engine.dispose()


def test_users_email_is_unique_case_insensitively(migrated_head):
    """F-1.1-08 regression: the guarantee holds in the database, not only in Pydantic."""
    engine = _fresh_engine()
    try:
        with engine.connect() as conn:
            indexdef = conn.execute(
                text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE tablename = 'users' AND indexname = 'ux_users_email_lower'"
                )
            ).scalar_one()
            assert "UNIQUE INDEX" in indexdef
            assert "lower(email" in indexdef

            local_part = uuid.uuid4().hex
            insert_user = text(
                "INSERT INTO users (email, password_hash) VALUES (:email, 'not-a-real-hash')"
            )
            conn.execute(insert_user, {"email": f"{local_part}@example.com"})
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(insert_user, {"email": f"{local_part.upper()}@EXAMPLE.COM"})
            conn.rollback()
    finally:
        engine.dispose()


def test_auth_sessions_has_the_absolute_expiry_column(migrated_head):
    """F-1.1-07 regression: the ceiling a rotation chain cannot outlive."""
    engine = _fresh_engine()
    try:
        columns = {column["name"]: column for column in inspect(engine).get_columns("auth_sessions")}
        assert "absolute_expires_at" in columns
        assert columns["absolute_expires_at"]["nullable"] is True
    finally:
        engine.dispose()


def test_downgrade_to_0001_reverses_the_0002_schema_changes(migrated_head):
    """The 0002 rollback path, proven rather than asserted.

    Retargeted at build phase 4.10 from `command.downgrade(cfg, "-1")` to an
    explicit revision id. NOT a weakened check: every assertion below is
    unchanged, and the test still proves exactly what its name says. What
    changed is the navigation. `-1` meant "one step back from head", which
    landed on 0001 only while 0002 WAS head; adding revision 0003 moved
    head, so `-1` began undoing 0003 instead and the 0002 assertions failed
    against a schema 0002 was still applied to. The relative offset was a
    latent fragility that any new revision would have tripped, and it was
    tripped by the first one added after it was written. An explicit
    revision id cannot drift that way.
    """
    cfg = migrated_head
    command.downgrade(cfg, "0001_user_data_schema")

    engine = _fresh_engine()
    try:
        columns = {column["name"] for column in inspect(engine).get_columns("auth_sessions")}
        assert "absolute_expires_at" not in columns
        with engine.connect() as conn:
            names = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE tablename IN ('users', 'auth_sessions')"
                    )
                )
            }
            assert "ux_auth_sessions_refresh_token_hash" not in names
            assert "ux_users_email_lower" not in names
            # The 0001 tables themselves survive a one-step downgrade.
            assert {"users_pkey", "auth_sessions_pkey"}.issubset(names)
    finally:
        engine.dispose()
    # The migrated_head fixture re-runs `upgrade head` in its teardown.


def test_downgrade_base_removes_every_table_index_and_extension(migrated_head):
    cfg = migrated_head
    command.downgrade(cfg, "base")

    engine = _fresh_engine()
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert ALL_TABLES.isdisjoint(tables)

        with engine.connect() as conn:
            remaining_extensions = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT extname FROM pg_extension "
                        "WHERE extname IN ('pgcrypto', 'pg_trgm')"
                    )
                )
            }
            assert remaining_extensions == set()
    finally:
        engine.dispose()
    # The migrated_head fixture re-runs `upgrade head` in its teardown, so
    # the scratch database is left migrated when this test finishes. The
    # scratch_db_url fixture drops the scratch database entirely once every
    # test in this module has run.
