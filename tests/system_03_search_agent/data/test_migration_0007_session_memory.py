"""Column-level coverage for alembic 0007, `sessions.memory` (F-4.5-J-21).

Build phase 4.5 shipped revision 0007 with no test naming the column it
adds. That breaks a pattern this repository already set twice, and the
pattern exists for a mechanical reason rather than a stylistic one:
`test_migration.py`'s `ALL_TABLES` check is structurally blind to a
column-only migration. `upgrade head` still creates every table in that set
with the column missing, and `downgrade base` still drops every table
whether or not the column was ever reversed, so both directions of a
column-only revision pass while doing nothing.

`test_auth_sessions_has_the_absolute_expiry_column` (revision 0002) and
`test_guest_sessions_has_the_attempt_counter_column` (revision 0005) are the
two prior instances. This file is the third, in a new module rather than
appended to theirs because a concurrent fix round owns that file.

What `sessions.memory` carries makes the gap worth closing rather than
noting: it is the whole of a caller's session memory, including the
ownership envelope that records WHICH principal the memory belongs to. A
migration that silently failed to add it would take the feature back to
being inert, which is F-4.5-09's failure mode, and the ownership fix on top
of it would have nowhere to write the owner.

## Coverage: what this file exercises and what it deliberately omits

Exercised:

- The column exists after `upgrade head`, with the declared type (JSONB),
  nullability (nullable) and server default (none). Each of the three is a
  property the migration states and that nothing else checks.
- The DOWNGRADE actually removes it. `test_migration.py`'s full-chain
  `downgrade base` drops every table, which proves 0007's `downgrade()` does
  not error and proves nothing about what it removed. This steps 0007 down
  by exactly one revision and inspects the column list either side, which is
  the only shape that can tell "reversed" from "dropped along with the
  table".
- The round trip is repeatable: down one, up one, and the column is back
  with the same declared shape. A downgrade that leaves residue would make
  the second upgrade fail on a duplicate column.
- The column the migration adds is the column the ORM declares. A migration
  and a model that disagree produce a runtime failure no schema test sees.

NOT exercised:

- Anything about the CONTENT of the column: the envelope shape, the owner
  field, the clamped budget. That is `core/session_memory.py`'s contract and
  `tests/system_03_search_agent/core/test_session_memory.py` owns it. A
  schema test that asserted on payload shape would be asserting on data this
  file never writes.
- The `sessions` table's other columns, its indexes, and its foreign key to
  `users`. Revision 0001 created them and `test_migration.py` owns them.
- Concurrent migration behaviour, and whether the ADD COLUMN takes a lock
  long enough to matter on a populated table. `add_column` with no default
  is metadata-only on modern PostgreSQL, so there is no rewrite to measure,
  but nothing here proves that on the version a deployment actually runs.
- Every revision after 0007. This file steps down to 0006 and back and never
  touches head beyond what the shared fixture already does.

Skips cleanly, never fails, when the PostgreSQL server is unreachable, the
same as `test_migration.py`.

Depends on:
    - alembic/versions/0007_session_memory.py (the revision under test)
    - system_03_search_agent.data.models (ChatSession, the ORM declaration)
    - A reachable local PostgreSQL server named by USER_DB_URL

Writes:
    - A uniquely named throwaway database, created and dropped by this
      module. USER_DB_URL's own database is used only for a read-only
      reachability probe and is never a migration target.
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
USER_DB_URL = os.environ.get(
    "USER_DB_URL", "postgresql://localhost:5432/search_agent_users"
)

#: The revision under test and the one immediately before it. Named as
#: constants so a later revision inserted between them fails loudly here
#: rather than silently testing the wrong step.
REVISION = "0007_session_memory"
PREVIOUS_REVISION = "0006_guest_source_daily_usage"

TABLE = "sessions"
COLUMN = "memory"


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
    parts = urlsplit(url)
    return urlunsplit(
        (parts.scheme, parts.netloc, f"/{db_name}", parts.query, parts.fragment)
    )


def _alembic_config() -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return cfg


@pytest.fixture(scope="module")
def scratch_db_url():
    """A throwaway database for this module, dropped when the module ends.

    The same shape `test_migration.py` uses, and for the same reason: this
    module runs `downgrade`, and a downgrade must never be pointed at the
    database USER_DB_URL names.
    """
    db_name = f"migration_0007_scratch_{uuid.uuid4().hex}"
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
    """Upgrade the scratch database to head, and leave it there.

    Unconditionally re-upgraded in the teardown, because the rollback arm
    below steps the chain down and a test that failed mid-step would
    otherwise leave the database behind for the next one.
    """
    monkeypatch.setenv("USER_DB_URL", scratch_db_url)
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    try:
        yield cfg
    finally:
        command.upgrade(cfg, "head")


def _fresh_engine() -> sa.engine.Engine:
    return sa.create_engine(os.environ["USER_DB_URL"], future=True)


def _column(engine: sa.engine.Engine, table: str, column: str) -> dict | None:
    return {
        col["name"]: col for col in inspect(engine).get_columns(table)
    }.get(column)


def test_the_revision_still_sits_directly_on_top_of_0006() -> None:
    """Pins: the step this file exercises is the step it names.

    The rollback arm below downgrades by one revision. If another revision is
    ever inserted between 0006 and 0007, that single step would exercise the
    new revision instead and the arms here would report on the wrong
    migration while staying green. Reading `down_revision` off the module is
    what makes that a failure rather than a silent substitution.
    """
    import importlib.util

    path = REPO_ROOT / "alembic" / "versions" / "0007_session_memory.py"
    spec = importlib.util.spec_from_file_location("_rev0007", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.revision == REVISION
    assert module.down_revision == PREVIOUS_REVISION, (
        "revision 0007 no longer sits directly on top of "
        f"{PREVIOUS_REVISION}, so this file's one-step downgrade exercises a "
        f"different revision than the one it grades. down_revision="
        f"{module.down_revision!r}"
    )


def test_sessions_has_the_memory_column(migrated_head) -> None:
    """Pins: `upgrade head` actually adds `sessions.memory`, as JSONB, nullable.

    The control is `op.add_column` in `0007_session_memory.upgrade`. The
    table-level `ALL_TABLES` check in `test_migration.py` cannot see it: it
    asserts the `sessions` TABLE exists, which is revision 0001's work and
    stays true with this column missing.

    All three declared properties are asserted, not just presence. Nullable
    with no server default is what makes the revision safe to run against a
    populated table under the expand-contract rule, and JSONB rather than
    JSON is what makes the stored envelope queryable and, more immediately,
    what the ORM declares.
    """
    engine = _fresh_engine()
    try:
        column = _column(engine, TABLE, COLUMN)
        assert column is not None, (
            f"{TABLE}.{COLUMN} is missing after `upgrade head`. Revision 0007 "
            "is the only thing that adds it, and nothing else in the suite "
            "would notice: the table-level check sees the table, not the "
            f"column. columns={sorted(c['name'] for c in inspect(engine).get_columns(TABLE))}"
        )
        assert isinstance(column["type"], sa.dialects.postgresql.JSONB), (
            "sessions.memory is not JSONB. The revision declares "
            f"postgresql.JSONB and the ORM declares it too. type={column['type']!r}"
        )
        assert column["nullable"] is True, (
            "sessions.memory is NOT NULL, so every session row that existed "
            "before this revision would have had to be backfilled for the "
            "upgrade to succeed. The revision declares nullable=True."
        )
        assert column.get("default") is None, (
            "sessions.memory carries a server default. The revision declares "
            "none, and a default would make 'this session has no memory yet' "
            f"indistinguishable from an empty summary. default={column.get('default')!r}"
        )
    finally:
        engine.dispose()


def test_the_downgrade_removes_exactly_that_column(migrated_head) -> None:
    """Pins: `0007_session_memory.downgrade` reverses what the upgrade did.

    The existing full-chain `downgrade base` test drops every table, so it
    proves `downgrade()` does not raise and proves nothing about what it
    removed: the column disappears either way, with the table. Stepping down
    exactly one revision and inspecting the still-present table is the only
    shape that can tell a reversal from a table drop.

    The rest of the table is asserted unchanged in the same breath. A
    `downgrade` that dropped the wrong column, or more than one, would
    otherwise satisfy an assertion that only checked `memory` is gone.
    """
    cfg = migrated_head
    engine = _fresh_engine()
    try:
        before = {c["name"] for c in inspect(engine).get_columns(TABLE)}
        assert COLUMN in before
    finally:
        engine.dispose()

    command.downgrade(cfg, f"{REVISION}-1")

    engine = _fresh_engine()
    try:
        after = {c["name"] for c in inspect(engine).get_columns(TABLE)}
        assert TABLE in inspect(engine).get_table_names(), (
            "the downgrade dropped the sessions TABLE rather than the column "
            "it added. Revision 0001 owns the table and 0007 must leave it."
        )
        assert COLUMN not in after, (
            f"{TABLE}.{COLUMN} survived a downgrade past revision 0007, so "
            "the rollback the migration gate requires does not actually roll "
            "anything back. A re-upgrade would then fail on a duplicate "
            "column, which is how this is discovered in production instead."
        )
        assert before - after == {COLUMN}, (
            "the downgrade removed more than the column the upgrade added. "
            f"removed={sorted(before - after)}"
        )
    finally:
        engine.dispose()


def test_the_round_trip_is_repeatable(migrated_head) -> None:
    """Pins: down one, up one, and the column is back with the same shape.

    A downgrade that leaves residue behind, an index or a type, makes the
    second upgrade fail on a duplicate. `tracker/BOARD.md` records one manual
    up-and-down run of this revision by one person on one machine; this is
    the same check, run by something that will run again.
    """
    cfg = migrated_head
    command.downgrade(cfg, f"{REVISION}-1")
    command.upgrade(cfg, REVISION)

    engine = _fresh_engine()
    try:
        column = _column(engine, TABLE, COLUMN)
        assert column is not None, (
            "sessions.memory did not come back after a down-and-up round "
            "trip, so the revision is not re-runnable."
        )
        assert isinstance(column["type"], sa.dialects.postgresql.JSONB)
        assert column["nullable"] is True
    finally:
        engine.dispose()


def test_the_migration_and_the_orm_declare_the_same_column(migrated_head) -> None:
    """Pins: `data.models.ChatSession.memory` matches what 0007 creates.

    A migration and a model that disagree produce a runtime failure no schema
    test sees, because each one is internally consistent. This is the one
    place the two are compared.
    """
    from system_03_search_agent.data.models import ChatSession

    declared = ChatSession.__table__.columns.get(COLUMN)
    assert declared is not None, (
        "the ORM no longer declares ChatSession.memory, so the column "
        "revision 0007 creates is written by nothing."
    )
    assert isinstance(declared.type, sa.dialects.postgresql.JSONB), (
        f"the ORM declares sessions.memory as {declared.type!r} while the "
        "migration creates JSONB."
    )
    assert declared.nullable is True

    engine = _fresh_engine()
    try:
        column = _column(engine, TABLE, COLUMN)
        assert column is not None
        assert column["nullable"] is declared.nullable
    finally:
        engine.dispose()
