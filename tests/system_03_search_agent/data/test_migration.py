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
