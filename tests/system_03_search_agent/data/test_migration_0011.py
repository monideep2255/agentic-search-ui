"""Column-level coverage for alembic 0011, the stored risk tier (card 71).

What a person gets: a reopened answer shows the "High-risk claim" tag the live
answer showed, and an answer saved before the column existed shows no tag.
Follows `test_migration_0010.py`'s convention, for its reason: the full-chain
check in `test_migration.py` cannot see a column-only migration.

Exercised:

- The column exists after `upgrade head`, TEXT, nullable, no default, and
  with no CHECK constraint (card 71 fix round: the bound lives in code,
  `feedback/capture.py`, so a long tier costs the tag and never the row).
- A row inserted without the column is legal and reads back NULL (an old row).
- The upgrade over a table that already holds rows keeps every row, each
  with a NULL tier, and the downgrade over rows that hold a tier keeps
  every row too (J-71T-05).
- The DOWNGRADE removes the column, one revision, inspected either side, and
  the round trip repeats.
- The column the migration adds is the column the ORM declares, and the ORM
  declares no constraint the migration does not add.

NOT exercised: what capture stores (`feedback/test_capture_saved_answer.py`)
and what the endpoint serves (`feedback/test_history_saved_answer.py`).

Skips cleanly, never fails, when the PostgreSQL server is unreachable. Runs in
a uniquely named throwaway database, never the shared one.
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
    db_name = f"migration_0011_scratch_{uuid.uuid4().hex}"
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


REVISION = "0011_interactions_risk_tier"
PREVIOUS_REVISION = "0010_interactions_saved_answer"
TABLE = "interactions"
COLUMN = "risk_tier"
#: The CHECK the first build added and the fix round removed. Every arm
#: asserts it is absent, so it cannot come back unseen.
LENGTH = "ck_interactions_risk_tier_length"


def _insert(engine: sa.engine.Engine, **overrides) -> None:
    values = {
        "trace_id": uuid.uuid4().hex,
        "owner_id": f"user:{uuid.uuid4()}",
        "query_text": "what does BRCA1 do?",
        "query_class": "lookup",
        "route": "{}",
        "trust_signal": "answer",
        "rubric_outcome": "pass",
    }
    columns = list(values) + list(overrides)
    values.update(overrides)
    names = ", ".join(columns)
    marks = ", ".join("CAST(:route AS jsonb)" if c == "route" else f":{c}" for c in columns)
    with engine.begin() as conn:
        conn.execute(text(f"INSERT INTO interactions ({names}) VALUES ({marks})"), values)


def test_the_revision_still_sits_directly_on_top_of_0010() -> None:
    path = REPO_ROOT / "alembic" / "versions" / "0011_interactions_risk_tier.py"
    spec = importlib.util.spec_from_file_location("_rev0011", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == REVISION
    assert module.down_revision == PREVIOUS_REVISION


def test_the_rollback_plan_names_the_order_downgrade_first_then_the_previous_build() -> None:
    """A-71T-05, J-71T-10: the written plan an operator follows. The previous
    build cannot start once 0011 has run, and this build cannot serve after
    the downgrade, so the plan must say downgrade first, then redeploy at
    once. Mutation: restoring the first build's plan ("drops the constraint
    and then the column ... shows no tag") turns this red."""
    path = REPO_ROOT / "alembic" / "versions" / "0011_interactions_risk_tier.py"
    doc = path.read_text().split('"""')[1]
    plan = doc.split("## Rollback plan", 1)[1].split("## ", 1)[0]
    downgrade_at = plan.index(f"alembic downgrade {PREVIOUS_REVISION}")
    redeploy_at = plan.index("redeploy the previous build")
    assert downgrade_at < redeploy_at
    assert "reopening any saved answer fails" in plan


def test_the_column_exists_after_upgrade_nullable_with_no_default(migrated_head) -> None:
    engine = _fresh_engine()
    try:
        columns = _columns(engine)
        assert "trace_id" in columns  # POPULATE CHECK: the table was found
        assert COLUMN in columns
        assert isinstance(columns[COLUMN]["type"], sa.Text)
        assert columns[COLUMN]["nullable"] is True
        assert columns[COLUMN]["default"] is None
        assert LENGTH not in _check_constraint_names(engine)
    finally:
        engine.dispose()


def test_an_old_row_reads_null_and_the_database_refuses_no_tier(migrated_head) -> None:
    """The database holds no bound: a value over 16 characters is not a
    reason to lose a row there. Capture never writes one (it stores NULL)."""
    engine = _fresh_engine()
    try:
        _insert(engine)  # an old-shape row: names no risk_tier
        _insert(engine, risk_tier="high")
        _insert(engine, risk_tier="x" * 17)
        with engine.connect() as conn:
            stored = sorted(
                (r[0] or "") for r in conn.execute(text("SELECT risk_tier FROM interactions"))
            )
        # POPULATE CHECK: all three landed, the old one as NULL.
        assert stored == ["", "high", "x" * 17]
    finally:
        engine.dispose()


def test_the_migration_keeps_every_row_of_a_populated_table_both_ways(migrated_head) -> None:
    """J-71T-05: upgrade over rows saved before 0011, then downgrade over
    rows that hold a tier. No row is lost either way."""
    cfg = migrated_head
    command.downgrade(cfg, PREVIOUS_REVISION)
    engine = _fresh_engine()
    try:
        assert COLUMN not in _columns(engine)  # POPULATE CHECK: really at 0010
        for _ in range(3):
            _insert(engine)  # rows saved before the column existed
    finally:
        engine.dispose()

    command.upgrade(cfg, REVISION)
    engine = _fresh_engine()
    try:
        with engine.connect() as conn:
            tiers = [r[0] for r in conn.execute(text("SELECT risk_tier FROM interactions"))]
        assert tiers == [None, None, None]
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE interactions SET risk_tier = 'high' WHERE trace_id = "
                    "(SELECT trace_id FROM interactions LIMIT 1)"
                )
            )
        _insert(engine, risk_tier="moderate")
        with engine.connect() as conn:
            held = conn.execute(
                text("SELECT count(*) FROM interactions WHERE risk_tier IS NOT NULL")
            ).scalar_one()
        assert held == 2  # POPULATE CHECK: the downgrade below drops real tiers
    finally:
        engine.dispose()

    command.downgrade(cfg, PREVIOUS_REVISION)
    engine = _fresh_engine()
    try:
        assert COLUMN not in _columns(engine)
        with engine.connect() as conn:
            count = conn.execute(text("SELECT count(*) FROM interactions")).scalar_one()
        assert count == 4
    finally:
        engine.dispose()


def test_downgrade_removes_the_column_and_its_constraint_and_the_round_trip_repeats(
    migrated_head,
) -> None:
    cfg = migrated_head
    engine = _fresh_engine()
    try:
        assert COLUMN in _columns(engine)  # POPULATE CHECK: there was something to remove
    finally:
        engine.dispose()

    command.downgrade(cfg, PREVIOUS_REVISION)
    engine = _fresh_engine()
    try:
        after = _columns(engine)
        assert COLUMN not in after
        assert "trace_id" in after and "answer_markdown" in after
    finally:
        engine.dispose()

    command.upgrade(cfg, REVISION)
    engine = _fresh_engine()
    try:
        assert COLUMN in _columns(engine)
        assert LENGTH not in _check_constraint_names(engine)
    finally:
        engine.dispose()


def test_the_orm_declares_the_column_the_migration_adds() -> None:
    from system_03_search_agent.data.models import Interaction

    assert COLUMN in Interaction.__table__.columns
    column = Interaction.__table__.columns[COLUMN]
    assert column.nullable is True
    assert isinstance(column.type, sa.Text)
    # The ORM declares no bound the migration does not add (J-71T-07).
    names = {constraint.name for constraint in Interaction.__table__.constraints}
    assert "ck_interactions_audience_depth" in names  # POPULATE CHECK
    assert LENGTH not in names
    assert not any("risk_tier" in str(getattr(c, "sqltext", "")) for c in Interaction.__table__.constraints)
