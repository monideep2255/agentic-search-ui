"""Integration tests for the 0001_user_data_schema Alembic migration.

Hits the real local PostgreSQL `search_agent_users` database through
Alembic's command API, not a mock: the CHECK constraints, the GIN indexes,
and gen_random_uuid() cannot be verified against SQLite.

The whole module skips cleanly (does not fail) when USER_DB_URL is unset or
the database is unreachable, so CI without a database does not go red. The
connection probe runs once at import time.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

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


def _can_connect() -> bool:
    try:
        probe_engine = sa.create_engine(USER_DB_URL)
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


if not _can_connect():
    pytest.skip(
        "search_agent_users PostgreSQL database is not reachable; "
        "set USER_DB_URL and ensure the server is running to run this suite",
        allow_module_level=True,
    )


def _alembic_config() -> Config:
    os.environ.setdefault("USER_DB_URL", USER_DB_URL)
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return cfg


@pytest.fixture()
def migrated_head():
    """Upgrade to head before the test, and unconditionally again after.

    A test in this module downgrades to base to prove the rollback path.
    This fixture guarantees the shared dev database is left migrated to
    head when the test session ends, regardless of what an individual test
    did in between, so other tickets that depend on this schema are never
    left looking at a torn-down database.
    """
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    try:
        yield cfg
    finally:
        command.upgrade(cfg, "head")


def _fresh_engine() -> sa.engine.Engine:
    return sa.create_engine(USER_DB_URL, future=True)


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
    # the shared dev database is left migrated when this test finishes.
