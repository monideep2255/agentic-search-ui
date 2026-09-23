"""Column-level coverage for alembic 0010, the saved answer (fix-plan item 10.2).

Follows the convention `test_migration_0008_interactions_owner_id.py` set,
for the same mechanical reason it gives: `test_migration.py`'s `ALL_TABLES`
check is structurally blind to a column-only migration, since `upgrade head`
creates `interactions` whether or not the column landed and `downgrade base`
drops the table whether or not the column was reversed.

What makes this revision worth its own file is not the two columns. It is
the three CHECK constraints, and in particular
`ck_interactions_answer_account_only`, which is where the product owner's
"signed-in accounts only" stops being a promise made in Python and becomes
something the database refuses. A migration that added the columns and
silently skipped that constraint would leave every Python-side guard in
place and still permit a guest's answer to be written by any path that does
not go through `InteractionRow`. Only a real INSERT against a real
PostgreSQL server can tell those two worlds apart.

## Coverage: what this file exercises and what it deliberately omits

Exercised:

- Both columns exist after `upgrade head`, TEXT and nullable.
- The database REFUSES a guest row carrying an answer, and ACCEPTS the same
  row for an account. Both arms, because an arm that only proves the
  refusal cannot distinguish a working constraint from a table that rejects
  every insert for some unrelated reason.
- The database refuses an answer over the 32000 bound and accepts one at it.
- The database refuses an `audience_depth` outside the four-value
  vocabulary.
- The DOWNGRADE actually removes both columns and all three constraints,
  stepped down by exactly one revision and inspected either side, which is
  the only shape that tells "reversed" from "dropped with the table".
- The round trip repeats: down one, up one, and everything is back.
- The columns the migration adds are the columns the ORM declares.

NOT exercised:

- Which string an assembled row actually carries. That is
  `feedback/capture.py`'s contract and
  `tests/system_03_search_agent/feedback/test_capture.py` owns it.
- Whether the endpoints serve what is stored. `tests/system_03_search_agent/
  adapters/web_sse/test_saved_answer_endpoint.py` owns that.
- Lock duration of the two `ADD COLUMN`s on a populated table. Both are
  nullable with no default, so they are metadata-only on modern PostgreSQL,
  but nothing here measures that on the version a deployment runs.
- Every revision after 0010. This file steps down to 0009 and back.

Skips cleanly, never fails, when the PostgreSQL server is unreachable.

Depends on:
    - alembic/versions/0010_interactions_saved_answer.py (under test)
    - system_03_search_agent.data.models (Interaction, the ORM declaration)
    - A reachable local PostgreSQL server named by USER_DB_URL

Writes:
    - A uniquely named throwaway database, created and dropped by this
      module. USER_DB_URL's own database is used only for a read-only
      reachability probe and is never a migration target.
"""

from __future__ import annotations

import importlib.util
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

REPO_ROOT = Path(__file__).resolve().parents[3]
USER_DB_URL = os.environ.get(
    "USER_DB_URL", "postgresql://localhost:5432/search_agent_users"
)

REVISION = "0010_interactions_saved_answer"
PREVIOUS_REVISION = "0009_interactions_history_idx"

TABLE = "interactions"
ANSWER_COLUMN = "answer_markdown"
DEPTH_COLUMN = "audience_depth"

ACCOUNT_ONLY = "ck_interactions_answer_account_only"
LENGTH = "ck_interactions_answer_markdown_length"
DEPTH = "ck_interactions_audience_depth"

MAX_ANSWER_MARKDOWN_CHARS = 32000


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
    db_name = f"migration_0010_scratch_{uuid.uuid4().hex}"
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
    monkeypatch.setenv("USER_DB_URL", scratch_db_url)
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    # The scratch database is module-scoped, so rows written by one arm
    # would otherwise be counted by the next. Emptied per test rather than
    # made module-scoped, so each arm's own counts mean what they say: a
    # count that silently included a sibling's rows is exactly the kind of
    # arm that passes while measuring the wrong thing.
    engine = _fresh_engine()
    try:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE interactions CASCADE"))
    finally:
        engine.dispose()
    try:
        yield cfg
    finally:
        command.upgrade(cfg, "head")


def _fresh_engine() -> sa.engine.Engine:
    return sa.create_engine(os.environ["USER_DB_URL"], future=True)


def _columns(engine: sa.engine.Engine) -> dict:
    return {col["name"]: col for col in inspect(engine).get_columns(TABLE)}


def _check_constraint_names(engine: sa.engine.Engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'interactions'::regclass AND contype = 'c'"
            )
        ).all()
    return {row[0] for row in rows}


def _insert(engine: sa.engine.Engine, **overrides) -> None:
    """Insert one minimal `interactions` row, overridable field by field.

    Only the NOT NULL columns are named, so this stays a statement about the
    constraints under test rather than about the rest of the table.
    """
    values = {
        "trace_id": uuid.uuid4().hex,
        "owner_id": f"user:{uuid.uuid4()}",
        "query_text": "what does BRCA1 do?",
        "query_class": "lookup",
        "route": "{}",
        "trust_signal": "answer",
        "rubric_outcome": "pass",
        "answer_markdown": None,
        "audience_depth": None,
    }
    values.update(overrides)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO interactions "
                "(trace_id, owner_id, query_text, query_class, route, trust_signal, "
                " rubric_outcome, answer_markdown, audience_depth) "
                "VALUES (:trace_id, :owner_id, :query_text, :query_class, "
                " CAST(:route AS jsonb), :trust_signal, :rubric_outcome, "
                " :answer_markdown, :audience_depth)"
            ),
            values,
        )


def test_the_revision_still_sits_directly_on_top_of_0009() -> None:
    """Pins: the step this file exercises is the step it names."""
    path = REPO_ROOT / "alembic" / "versions" / "0010_interactions_saved_answer.py"
    spec = importlib.util.spec_from_file_location("_rev0010", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.revision == REVISION
    assert module.down_revision == PREVIOUS_REVISION, (
        "revision 0010 no longer sits directly on top of "
        f"{PREVIOUS_REVISION}, so this file's one-step downgrade exercises a "
        f"different revision than the one it grades. down_revision="
        f"{module.down_revision!r}"
    )
    assert module.MAX_ANSWER_MARKDOWN_CHARS == MAX_ANSWER_MARKDOWN_CHARS


def test_both_columns_exist_after_upgrade(migrated_head) -> None:
    engine = _fresh_engine()
    try:
        columns = _columns(engine)
        # POPULATE CHECK: the table itself was found and has its own
        # long-standing columns, so an empty or missing-table result cannot
        # masquerade as "the new columns are absent" or as a pass.
        assert "trace_id" in columns and "owner_id" in columns

        assert ANSWER_COLUMN in columns
        assert DEPTH_COLUMN in columns
        assert isinstance(columns[ANSWER_COLUMN]["type"], sa.Text)
        assert isinstance(columns[DEPTH_COLUMN]["type"], sa.Text)
        assert columns[ANSWER_COLUMN]["nullable"] is True
        assert columns[DEPTH_COLUMN]["nullable"] is True
        assert columns[ANSWER_COLUMN]["default"] is None
        assert columns[DEPTH_COLUMN]["default"] is None
    finally:
        engine.dispose()


def test_all_three_check_constraints_exist_after_upgrade(migrated_head) -> None:
    engine = _fresh_engine()
    try:
        names = _check_constraint_names(engine)
        # POPULATE CHECK: revision 0001's own constraints are present, so an
        # empty result set cannot pass as "the new ones are there".
        assert "ck_interactions_query_class" in names
        assert {ACCOUNT_ONLY, LENGTH, DEPTH} <= names
    finally:
        engine.dispose()


def test_the_database_refuses_a_guest_answer_and_accepts_an_account_one(
    migrated_head,
) -> None:
    """The product owner's decision, enforced where no code can route around it.

    Both directions, deliberately. A refusal arm on its own cannot tell a
    working constraint from a table that rejects everything.
    """
    engine = _fresh_engine()
    try:
        # Accepts: an account row carrying an answer.
        _insert(
            engine,
            owner_id=f"user:{uuid.uuid4()}",
            answer_markdown="TP53 is a tumour suppressor [1].",
            audience_depth="researcher",
        )
        with engine.connect() as conn:
            stored = conn.execute(
                text(
                    "SELECT count(*) FROM interactions WHERE answer_markdown IS NOT NULL"
                )
            ).scalar()
        # POPULATE CHECK: the accepted row really landed, so the refusal
        # below is a statement about the constraint rather than about an
        # insert helper that never writes anything.
        assert stored == 1

        # Refuses: the identical row for a guest.
        with pytest.raises(sa.exc.IntegrityError) as excinfo:
            _insert(
                engine,
                owner_id=f"guest:{uuid.uuid4()}",
                answer_markdown="TP53 is a tumour suppressor [1].",
                audience_depth="researcher",
            )
        assert ACCOUNT_ONLY in str(excinfo.value)

        # And a guest row with NO answer is still perfectly legal, because
        # this constraint must never stop a guest's run being counted.
        _insert(engine, owner_id=f"guest:{uuid.uuid4()}")
        with engine.connect() as conn:
            total = conn.execute(text("SELECT count(*) FROM interactions")).scalar()
        assert total == 2
    finally:
        engine.dispose()


def test_the_database_bounds_the_stored_answer(migrated_head) -> None:
    engine = _fresh_engine()
    try:
        _insert(
            engine,
            answer_markdown="x" * MAX_ANSWER_MARKDOWN_CHARS,
            audience_depth="plain_language",
        )
        with engine.connect() as conn:
            longest = conn.execute(
                text("SELECT max(char_length(answer_markdown)) FROM interactions")
            ).scalar()
        # POPULATE CHECK: the at-the-bound row landed at its full length, so
        # the rejection below is about the bound and not about a truncating
        # insert.
        assert longest == MAX_ANSWER_MARKDOWN_CHARS

        with pytest.raises(sa.exc.IntegrityError) as excinfo:
            _insert(
                engine,
                answer_markdown="x" * (MAX_ANSWER_MARKDOWN_CHARS + 1),
                audience_depth="plain_language",
            )
        assert LENGTH in str(excinfo.value)
    finally:
        engine.dispose()


def test_the_database_refuses_an_unknown_depth(migrated_head) -> None:
    engine = _fresh_engine()
    try:
        for depth in (
            "clinical_brief",
            "researcher",
            "deep_technical",
            "plain_language",
        ):
            _insert(engine, answer_markdown=f"an answer at {depth}", audience_depth=depth)
        with engine.connect() as conn:
            accepted = conn.execute(
                text("SELECT count(*) FROM interactions WHERE audience_depth IS NOT NULL")
            ).scalar()
        # POPULATE CHECK: all four legal values really landed.
        assert accepted == 4

        with pytest.raises(sa.exc.IntegrityError) as excinfo:
            _insert(engine, answer_markdown="an answer", audience_depth="expert")
        assert DEPTH in str(excinfo.value)
    finally:
        engine.dispose()


def test_downgrade_removes_both_columns_and_all_three_constraints(
    migrated_head,
) -> None:
    """Steps down by exactly one revision and inspects either side.

    `test_migration.py`'s full-chain `downgrade base` drops every table,
    which proves this revision's `downgrade()` does not error and proves
    nothing about what it removed.
    """
    cfg = migrated_head
    engine = _fresh_engine()
    try:
        before = _columns(engine)
        # POPULATE CHECK for the whole arm: the columns were there to remove.
        assert ANSWER_COLUMN in before and DEPTH_COLUMN in before
        assert {ACCOUNT_ONLY, LENGTH, DEPTH} <= _check_constraint_names(engine)
    finally:
        engine.dispose()

    command.downgrade(cfg, PREVIOUS_REVISION)

    engine = _fresh_engine()
    try:
        after = _columns(engine)
        assert ANSWER_COLUMN not in after
        assert DEPTH_COLUMN not in after
        # The table itself survived: this is a column rollback, not a drop.
        assert "trace_id" in after and "owner_id" in after
        names = _check_constraint_names(engine)
        assert not ({ACCOUNT_ONLY, LENGTH, DEPTH} & names)
        assert "ck_interactions_query_class" in names
    finally:
        engine.dispose()

    command.upgrade(cfg, REVISION)

    engine = _fresh_engine()
    try:
        again = _columns(engine)
        assert ANSWER_COLUMN in again and DEPTH_COLUMN in again
        assert {ACCOUNT_ONLY, LENGTH, DEPTH} <= _check_constraint_names(engine)
    finally:
        engine.dispose()


def test_the_migration_and_the_orm_declare_the_same_columns(migrated_head) -> None:
    """A migration and a model that disagree produce a runtime failure no
    schema test sees."""
    from system_03_search_agent.data.models import Interaction

    engine = _fresh_engine()
    try:
        columns = _columns(engine)
    finally:
        engine.dispose()

    declared = {column.name for column in Interaction.__table__.columns}
    # POPULATE CHECK: the ORM really declares a table with columns.
    assert "trace_id" in declared
    assert ANSWER_COLUMN in declared
    assert DEPTH_COLUMN in declared
    assert declared <= set(columns)
