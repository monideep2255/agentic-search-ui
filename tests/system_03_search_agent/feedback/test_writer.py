"""T-4.6-06: `feedback/writer.py`, the one place a row reaches the database.

## Coverage: what this file exercises and what it deliberately omits

Per `.claude/rules/goal-contracts.md`, a verify surface must state its own
coverage so a gap is arguable rather than silently assumed away.

Exercised:

- The idempotent insert: `ON CONFLICT (trace_id) DO NOTHING` actually fires,
  tested against the real clause rather than against the outer best-effort
  catch, which would mask a plain-insert mutation just as effectively as
  the real clause does (see `test_a_second_insert_under_the_same_trace_id_
  changes_nothing`'s own docstring for why the inner function is tested
  directly).
- The lazy `sessions` row: created when absent, left untouched (not
  overwritten) when session memory already created it first, and the
  `interactions` insert still succeeds either way because both statements
  commit in one transaction.
- `write_interaction` never raises: a permanent failure is swallowed after
  one retry, a transient failure that clears on retry still leaves a row,
  and no exception text (only the exception's class name) reaches the log.
- The unstorable-code-point class (F-4.6-A-01): a NUL in every column that
  can carry one, and a `text[]` entry; a lone surrogate where it is actually
  reachable, inside a string VALUE nested in a `jsonb` column; and the
  boundary in the other direction, that ordinary control characters, ANSI
  escapes and bidi overrides are stored UNCHANGED, because this is a
  storability guard and not a control-character stripper. F-4.6-11 retired
  the "NUL in a `jsonb` object KEY" arm this used to carry: `normalized_
  entities`, `route`, `citations` and `user_feedback` are now each bounded
  against a real Pydantic model (`_NormalizedEntityShape`, `_RouteShape`,
  `CitationPayload`, `FeedbackPayload`) with `extra="forbid"`, so every key
  those four columns can ever carry is a fixed, code-defined literal, never
  a caller- or tool-supplied string. `InteractionRow` construction now
  rejects a dict with any other key before it reaches `_storable` at all,
  so a NUL (or anything else) in a KEY of one of these four columns is no
  longer a reachable case through this module, and `_storable`'s own
  key-sanitizing branch (`_storable(key)` in its dict comprehension) is
  retained as defense in depth for any future field rather than because
  this file can still exercise it against these four.
- The degraded-row fallback: a permanent full-row failure still leaves a
  countable row carrying the identity and accounting columns, marked in
  `query_text` and in `coverage_tags` so the review ritual can find it. Its
  boundary is covered too: when the minimal insert also fails, the row is
  genuinely dropped and nothing raises, which is the case Section 16 still
  permits.
- Feedback payloads pass through the same storability guard, since
  `comment`, `flagged_reason` and every `citation_flags` entry are
  caller-supplied strings landing in a `jsonb` column.
- `reassign_interaction_owner` (F-4.6-J-01): a migrated guest's rows move to
  the new account with `user_id` set, a bystanding guest's rows are
  untouched, a replay is a no-op, and a malformed account id is refused
  rather than raised.
- Feedback ownership (F-4.6-01's fix): one direct compare of the row's
  stored `owner_id` (alembic 0008) against the caller's claimed `owner_id`,
  covered for both a registered-account shape (`user:<uuid>`) and a guest
  shape (`guest:<uuid>`). Both the positive case (the true owner succeeds)
  and the negative case (a different principal is refused AND the stored
  value is unchanged, not just that an exception came back) are covered for
  each shape.
- The refuse-on-NULL branch: a row with no recorded `owner_id`, the shape
  only a pre-migration row can have, refuses feedback even from the caller
  who happens to be its true owner. NULL must not mean "anyone" (F-4.5-A-02).
- Repeat feedback replaces rather than appends, and `InteractionNotFound`
  for a `trace_id` nothing has captured yet.
- No secret reaches the log line when a write fails.

Every test is mutation-proven: the specific line each test exists to catch
is named in that test's own docstring, and each was run once with that line
reverted to confirm it actually goes red before being restored. That
history is recorded in this ticket's tracker entry rather than repeated
per-test here.

NOT exercised, deliberately:

- The assembler (`feedback/capture.py`) and the run epilogue dispatch
  (`core/run.py`). This file constructs `InteractionRow` values directly;
  it does not run a real query through the agent loop. That end-to-end
  property, "a real query causes a row to exist", is the premise gate's
  job (`tests/system_03_search_agent/core/test_feedback_capture_premise.py`),
  not this file's.
- Concurrency between two `write_feedback` calls racing on the same row.
  `with_for_update()` is the design answer; this file does not exercise two
  connections contending for the same lock.
- `write_interaction`'s outer retry against a REAL transient database
  failure (a dropped connection mid-write). The retry path is exercised by
  monkeypatching the inner write function to fail on demand, not by
  actually severing a connection.
- The CAP consequence of any of the above. Every arm here counts rows;
  none of them calls `get_user_daily_query_count` or
  `get_system_daily_cost_usd`. "A row exists" and "the cap can see it" are
  two claims and this file only makes the first.
  `tests/system_03_search_agent/feedback/test_capture_bypasses.py` makes the
  second, end to end through `run()`.
- The run epilogue. Nothing here drives a query, so nothing here can tell
  whether a real run reaches this module at all. That is the premise gate's
  job (`tests/system_03_search_agent/core/test_feedback_capture_premise.py`).
- Whether a caller can put an unstorable code point into `Query.text` in the
  first place. That is a boundary-validator question owned by
  `contracts/query.py`, and this module deliberately does not depend on the
  answer: it guards the storage boundary, which is the last one before the
  database and the only one that sees every field.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy import text

from alembic import command

REPO_ROOT = Path(__file__).resolve().parents[3]
USER_DB_URL = os.environ.get(
    "USER_DB_URL", "postgresql://localhost:5432/search_agent_users"
)


def _can_connect(url: str) -> bool:
    try:
        probe = sa.create_engine(url)
        with probe.connect():
            pass
        probe.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


if not _can_connect(USER_DB_URL):
    pytest.skip(
        "search_agent_users PostgreSQL is not reachable; set USER_DB_URL and "
        "start the server to run this suite",
        allow_module_level=True,
    )


def _with_db_name(url: str, db_name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (parts.scheme, parts.netloc, f"/{db_name}", parts.query, parts.fragment)
    )


@pytest.fixture(scope="module")
def scratch_db_url():
    """A throwaway database for this module, dropped when the module ends.

    The same shape `test_migration_0007_session_memory.py` and the phase
    4.6 premise gate both use: every test here counts rows or inspects
    exact column values, and a shared development database already carries
    residue from other suites' fixtures.
    """
    db_name = f"feedback_writer_{uuid.uuid4().hex}"
    assert re.fullmatch(r"[a-z0-9_]+", db_name)
    admin_url = _with_db_name(USER_DB_URL, "postgres")

    creator = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with creator.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        creator.dispose()

    url = _with_db_name(USER_DB_URL, db_name)
    previous = os.environ.get("USER_DB_URL")
    os.environ["USER_DB_URL"] = url
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    command.upgrade(cfg, "head")

    try:
        yield url
    finally:
        if previous is None:
            os.environ.pop("USER_DB_URL", None)
        else:
            os.environ["USER_DB_URL"] = previous
        dropper = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            with dropper.connect() as conn:
                conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :name AND pid <> pg_backend_pid()"
                    ),
                    {"name": db_name},
                )
                conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        finally:
            dropper.dispose()


@pytest.fixture()
def scratch_db(scratch_db_url, monkeypatch):
    """Point the application's own engine at the scratch database.

    `data/base.py` memoises one engine per process, so setting the
    environment variable alone changes nothing for code that has already
    created it. Both resets are required, and the teardown repeats them so
    a later module does not inherit this one's connection.
    """
    from system_03_search_agent.data import base as base_module
    from system_03_search_agent.data import session as session_module

    monkeypatch.setenv("USER_DB_URL", scratch_db_url)
    base_module.reset_engine()
    session_module.reset_session_factory()
    try:
        yield scratch_db_url
    finally:
        base_module.reset_engine()
        session_module.reset_session_factory()


# ---------------------------------------------------------------------------
# Row builders and DB readers.
# ---------------------------------------------------------------------------


def _citation_payload(*, claim_text: str = "BRCA1 is a gene.") -> dict:
    """A full, schema-conformant `contracts.events.CitationPayload` dict.

    F-4.6-11 bounds `InteractionRow.citations` by validating each entry
    against `CitationPayload` itself, so a partial dict like
    `{"claim_text": "..."}` can no longer be passed to `_make_row` below:
    it never reaches the database at all, because `InteractionRow`
    construction now rejects it outright. This mirrors `test_capture.py`'s
    own `_citation_payload` helper (same shape, same field values) rather
    than inventing a third copy of the same fixture; it is duplicated
    locally rather than imported because `test_capture.py` is a unit-test
    module with no public fixture surface of its own.
    """
    return {
        "citation_id": "call-1-1",
        "display_index": 1,
        "source": "NCBIGene",
        "source_id": "NCBIGene:672",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
        "layer": "layer_1_graph",
        "field": "symbol",
        "claim_text": claim_text,
        "evidence_kind": "primary_assertion",
        "assertion_confidence": "asserted",
        "population_ancestry_context": None,
        "license": "public_domain_us_gov",
    }


def _make_row(
    *,
    trace_id: str | None = None,
    session_id=None,
    user_id=None,
    owner_id: str | None = None,
    **overrides,
):
    from system_03_search_agent.feedback.contracts import InteractionRow

    fields = {
        "trace_id": trace_id or f"tw-{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "session_id": session_id,
        # `InteractionRow.owner_id` is required (F-4.6-01): a real row
        # always carries the exact owner_id capture recorded it for. A
        # fresh, otherwise-unclaimed guest id is the default so a test that
        # does not care about ownership does not accidentally collide with
        # another test's owner.
        "owner_id": owner_id if owner_id is not None else f"guest:{uuid.uuid4()}",
        "query_text": "What is BRCA1?",
        "normalized_entities": [],
        "query_class": "lookup",
        "route": {},
        "trust_signal": "answer",
        "rubric_outcome": "pass",
        "rubric_score": None,
        "citations": [],
        "coverage_tags": [],
        "user_feedback": None,
        "experiment_id": None,
        "experiment_arm": None,
        "cost_usd": 0.01,
        "latency_ms": 250,
    }
    fields.update(overrides)
    return InteractionRow(**fields)


def _insert_user(url: str) -> uuid.UUID:
    account_id = uuid.uuid4()
    engine = sa.create_engine(url, future=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, password_hash) "
                    "VALUES (:id, :email, :pw)"
                ),
                {
                    "id": str(account_id),
                    "email": f"tw-{account_id}@example.test",
                    "pw": "not-a-real-hash",
                },
            )
    finally:
        engine.dispose()
    return account_id


def _fetch_interaction(url: str, trace_id: str):
    engine = sa.create_engine(url, future=True)
    try:
        with engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT trace_id, user_id, session_id, owner_id, query_text, "
                    "trust_signal, rubric_outcome, citations, coverage_tags, "
                    "user_feedback, cost_usd, latency_ms FROM interactions "
                    "WHERE trace_id = :tid"
                ),
                {"tid": trace_id},
            ).fetchone()
    finally:
        engine.dispose()


def _null_out_owner_id(url: str, trace_id: str) -> None:
    """Simulate a row written before alembic 0008 added the column.

    A raw `UPDATE`, not `InteractionRow(owner_id=None)`, because the field
    is required (F-4.6-01): the assembler always has a valid owner_id by
    the time it builds a row, so the model refuses to construct one without
    it. A pre-migration row is a real state the database can hold even
    though the model can no longer represent it, and this is how a test
    reaches that state.
    """
    engine = sa.create_engine(url, future=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE interactions SET owner_id = NULL WHERE trace_id = :tid"),
                {"tid": trace_id},
            )
    finally:
        engine.dispose()


def _count_interactions(url: str, trace_id: str) -> int:
    engine = sa.create_engine(url, future=True)
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT count(*) FROM interactions WHERE trace_id = :tid"),
                {"tid": trace_id},
            ).scalar_one()
    finally:
        engine.dispose()


def _read_interaction(url: str, trace_id: str):
    """One row, read back with every column this file asserts on.

    Returns the SQLAlchemy `Row` rather than the ORM object, so a test is
    reading what the database holds rather than what a session cached.
    """
    engine = sa.create_engine(url, future=True)
    try:
        with engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT trace_id, user_id, session_id, owner_id, query_text, "
                    "normalized_entities, route, citations, coverage_tags, "
                    "user_feedback, cost_usd, latency_ms "
                    "FROM interactions WHERE trace_id = :tid"
                ),
                {"tid": trace_id},
            ).one()
    finally:
        engine.dispose()

def _fetch_session(url: str, session_id: uuid.UUID):
    engine = sa.create_engine(url, future=True)
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT id, user_id, memory FROM sessions WHERE id = :sid"),
                {"sid": str(session_id)},
            ).fetchone()
    finally:
        engine.dispose()


def _insert_session_with_memory(url: str, session_id: uuid.UUID, memory: dict | None) -> None:
    import json

    engine = sa.create_engine(url, future=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO sessions (id, memory) VALUES (:id, CAST(:memory AS JSONB))"
                ),
                {
                    "id": str(session_id),
                    "memory": json.dumps(memory) if memory is not None else None,
                },
            )
    finally:
        engine.dispose()


def _owned_envelope(owner_id: str) -> dict:
    """A minimal, genuinely valid envelope, built the same way
    `core.session_memory._wrap` builds one, so this file never invents a
    shape that module would refuse to read.
    """
    from system_03_search_agent.contracts.query import SessionMemorySummary
    from system_03_search_agent.core.session_memory import _wrap

    summary = SessionMemorySummary(session_id="tw-probe-session", last_updated=datetime.now(UTC))
    return _wrap(owner_id, summary.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# write_interaction: the idempotent insert.
# ---------------------------------------------------------------------------


def test_a_second_insert_under_the_same_trace_id_changes_nothing(scratch_db) -> None:
    """`ON CONFLICT (trace_id) DO NOTHING`, tested against the real clause.

    This calls the inner `_write_interaction_row` directly rather than the
    public `write_interaction`, because `write_interaction`'s own
    best-effort catch would swallow the `IntegrityError` a plain INSERT
    raises on the second call just as quietly as the real ON CONFLICT
    clause does, leaving the row count at 1 either way and masking the
    mutation from an outer-function test.

    Mutation-proven: replacing `.on_conflict_do_nothing(...)` with a plain
    `.values(...)` insert (no ON CONFLICT clause at all) raises
    `sqlalchemy.exc.IntegrityError` on the second call, unhandled at this
    level, which fails this test outright. Restored after confirming red.
    """
    from system_03_search_agent.feedback import writer as writer_module

    row = _make_row(query_text="the first write")
    writer_module._write_interaction_row(row)
    # A second row built with the SAME trace_id but different content: if
    # this silently overwrote (an upsert) rather than doing nothing, the
    # content assertion below would catch that too.
    second = _make_row(trace_id=row.trace_id, query_text="a different write")
    writer_module._write_interaction_row(second)

    assert _count_interactions(scratch_db, row.trace_id) == 1
    stored = _fetch_interaction(scratch_db, row.trace_id)
    assert stored.query_text == "the first write", (
        "the second insert changed the stored row, so this is an upsert, "
        "not ON CONFLICT DO NOTHING"
    )


@pytest.mark.asyncio
async def test_write_interaction_creates_the_sessions_row_when_absent(scratch_db) -> None:
    """The FK a lazily-created session would otherwise reject.

    Mutation-proven: deleting the `if row.session_id is not None:` block
    (and its INSERT) makes this raise `IntegrityError` on the interactions
    insert, since `sessions.id` would not exist for the FK to reference,
    and `write_interaction`'s outer catch would swallow that into an empty
    table, failing the `stored is not None` assertion below. Restored after
    confirming red.
    """
    from system_03_search_agent.feedback.writer import write_interaction

    session_id = uuid.uuid4()
    row = _make_row(session_id=session_id)
    await write_interaction(row)

    session_row = _fetch_session(scratch_db, session_id)
    assert session_row is not None, "no sessions row was created for the FK"
    assert session_row.user_id is None, "a guest row must carry a NULL sessions.user_id"

    stored = _fetch_interaction(scratch_db, row.trace_id)
    assert stored is not None, "the interactions row was not written"
    assert str(stored.session_id) == str(session_id)


@pytest.mark.asyncio
async def test_write_interaction_never_overwrites_a_session_row_that_already_exists(
    scratch_db,
) -> None:
    """The lazy create must be ON CONFLICT DO NOTHING, never an upsert.

    A session memory write could have created this row first, with real
    memory content. This plants that content and proves it survives.

    Mutation-proven: changing the session INSERT's
    `.on_conflict_do_nothing(...)` to `.on_conflict_do_update(...)` (or
    dropping the ON CONFLICT clause) either overwrites the planted memory
    with NULL or raises an IntegrityError that empties the table; either
    way the `memory is not None` assertion below goes red. Restored after
    confirming red.
    """
    from system_03_search_agent.feedback.writer import write_interaction

    session_id = uuid.uuid4()
    envelope = _owned_envelope("guest:" + str(uuid.uuid4()))
    _insert_session_with_memory(scratch_db, session_id, envelope)

    row = _make_row(session_id=session_id)
    await write_interaction(row)

    session_row = _fetch_session(scratch_db, session_id)
    assert session_row.memory is not None, "the pre-existing memory envelope was wiped"
    assert session_row.memory.get("owner_id") == envelope["owner_id"]

    stored = _fetch_interaction(scratch_db, row.trace_id)
    assert stored is not None, (
        "the interactions insert did not happen when the sessions row already existed"
    )


@pytest.mark.asyncio
async def test_write_interaction_persists_owner_id(scratch_db) -> None:
    """F-4.6-01: the column the ownership check now reads is actually written.

    Mutation-proven: removing `"owner_id": row.owner_id` from
    `_interaction_values` makes the stored value `None` instead of the real
    owner_id, since the column has no server default to fall back on, and
    the assertion below goes red. Restored after confirming red.
    """
    from system_03_search_agent.feedback.writer import write_interaction

    owner_id = f"guest:{uuid.uuid4()}"
    row = _make_row(owner_id=owner_id)
    await write_interaction(row)

    stored = _fetch_interaction(scratch_db, row.trace_id)
    assert stored is not None
    assert stored.owner_id == owner_id


# ---------------------------------------------------------------------------
# write_interaction: best-effort, never raises.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_permanent_failure_is_retried_once_then_degraded_not_dropped(
    scratch_db, monkeypatch
) -> None:
    """Section 16: retried once, never raised. REPLACED, not weakened.

    This test used to assert `_count_interactions(...) == 0` after a
    permanent failure, which encoded exactly the behaviour F-4.6-A-01
    exploits: one NUL byte in a question made the write fail
    deterministically, the row vanished, and both daily caps stopped
    counting that caller. The assertion was correct about the code and
    wrong about the requirement, so it is retargeted at the property that
    is still true (two attempts, no exception) plus the one that replaced
    the third (the run is still counted, with its payload dropped).

    Mutation-proven: replacing the `for attempt in range(1,
    _WRITE_ATTEMPTS + 1):` retry loop with a single unretried call makes
    the call-count assert fail (1 instead of 2), and deleting the
    `_write_minimal_interaction_row` call makes the row count read 0.
    Restored after confirming red both ways.
    """
    from system_03_search_agent.feedback import writer as writer_module

    calls: list[int] = []

    def _always_fails(row) -> None:
        calls.append(1)
        raise RuntimeError("simulated permanent database failure")

    monkeypatch.setattr(writer_module, "_write_interaction_row", _always_fails)

    row = _make_row(user_id=None, query_text="a question with something unstorable")
    await writer_module.write_interaction(row)  # must not raise

    assert len(calls) == 2, f"expected exactly 2 attempts, got {len(calls)}"
    assert _count_interactions(scratch_db, row.trace_id) == 1, (
        "a permanent write failure dropped the row entirely, so the caller's "
        "daily caps cannot see the query they just ran (F-4.6-A-01)"
    )

    stored = _read_interaction(scratch_db, row.trace_id)
    assert stored.owner_id == row.owner_id, (
        "the degraded row must still answer its own ownership, or the caller "
        "cannot rate their own answer"
    )
    assert stored.query_text == writer_module.PAYLOAD_DROPPED_TEXT
    assert writer_module.PAYLOAD_DROPPED_TAG in stored.coverage_tags, (
        "a degraded row must be findable by the weekly review ritual rather "
        "than silently indistinguishable from a real one"
    )
    assert float(stored.cost_usd) == pytest.approx(row.cost_usd), (
        "the degraded row must still carry what the run cost, or the "
        "system-wide daily cost cap stays blind to it"
    )


@pytest.mark.asyncio
async def test_a_database_that_cannot_be_written_to_at_all_still_drops_the_row(
    scratch_db, monkeypatch
) -> None:
    """The other half of the split, and the half Section 16 still allows.

    `_minimal_interaction_values`' docstring divides capture's failures by
    who controls them: a failure the caller's input can cause degrades the
    row's content, a failure nobody controls may lose the row. This arm is
    the second case. It matters that it stays true: a version that retried
    forever, or that raised, would turn an outage into a failed query for a
    caller who already has their answer.

    Mutation: remove the `try`/`except` around
    `_write_minimal_interaction_row` in `write_interaction`. This test goes
    red by raising `RuntimeError` out of `write_interaction`, breaking its
    documented never-raises contract.
    """
    from system_03_search_agent.feedback import writer as writer_module

    def _always_fails(row) -> None:
        raise RuntimeError("simulated unreachable user-data database")

    monkeypatch.setattr(writer_module, "_write_interaction_row", _always_fails)
    monkeypatch.setattr(writer_module, "_write_minimal_interaction_row", _always_fails)

    row = _make_row()
    await writer_module.write_interaction(row)  # must not raise

    assert _count_interactions(scratch_db, row.trace_id) == 0


# ---------------------------------------------------------------------------
# F-4.6-A-01: values a PostgreSQL column cannot hold.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_nul_byte_in_any_column_still_leaves_a_row(scratch_db) -> None:
    """The finding's own instance, and every sibling column at once.

    F-4.6-A-01 was measured through `query_text`, but a `text` column is
    not the only one a NUL reaches: `coverage_tags` is `text[]`, and
    `normalized_entities`, `route` and `citations` are `jsonb`, whose
    string VALUES are still typed `Any` inside `_storable` and are never
    validated by an upper bound on content. This arm plants one in a
    legitimate string value of each. It no longer plants one in a `jsonb`
    object KEY: F-4.6-11 bounds these three columns against real Pydantic
    models with `extra="forbid"` (`_NormalizedEntityShape`, `_RouteShape`,
    `CitationPayload`), so every key they can carry is fixed and
    code-defined, never caller- or tool-supplied, and a dict with any other
    key is rejected at `InteractionRow` construction, before `_storable`
    ever sees it. See this file's own coverage note above for the account
    of what that retires.

    Mutation: replace `_storable`'s body with `return value`. Ran it. This
    test goes red on the row count reading 0, and the log shows the real
    mechanism, `ValueError` from psycopg2 twice, then the degraded-row
    fallback, which then ALSO stores because the minimal row's constants
    carry nothing unstorable. So the count actually read 1 with
    `query_text` reading the dropped-payload marker, and the assertion that
    caught it was the one on the stored text, not the one on the count.
    Recorded because the count assertion alone would have passed, which is
    the second layer of the fix masking the first.
    """
    from system_03_search_agent.feedback.writer import write_interaction

    row = _make_row(
        query_text=f"What is BRCA1?{chr(0)}",
        coverage_tags=[f"concept:Gene{chr(0)}"],
        normalized_entities=[
            {
                "surface_form": f"BRCA1{chr(0)}",
                "curie": "NCBIGene:672",
                "entity_type": "Unknown",
                "resolution_confidence": 0.9,
            }
        ],
        route={"tools": [f"cypher_query{chr(0)}"]},
        citations=[_citation_payload(claim_text=f"a claim{chr(0)}")],
    )
    await write_interaction(row)

    assert _count_interactions(scratch_db, row.trace_id) == 1
    stored = _read_interaction(scratch_db, row.trace_id)
    assert stored.query_text == "What is BRCA1?\ufffd", (
        "the unstorable code point was not replaced, so this row landed "
        "through the degraded-payload fallback rather than intact"
    )
    assert stored.coverage_tags == ["concept:Gene\ufffd"]
    assert stored.normalized_entities == [
        {
            "surface_form": "BRCA1\ufffd",
            "curie": "NCBIGene:672",
            "entity_type": "Unknown",
            "resolution_confidence": 0.9,
        }
    ]
    assert stored.route == {"tools": ["cypher_query\ufffd"]}
    assert stored.citations == [_citation_payload(claim_text="a claim\ufffd")]


def test_a_lone_surrogate_in_citations_is_now_rejected_at_construction() -> None:
    """F-4.6-11 moved this defense up a layer, measured rather than assumed.

    Before F-4.6-11, `citations` was typed `list[dict[str, Any]]`, so a
    lone surrogate in a nested string value reached `_storable` completely
    unvalidated and was reachable only there
    (`test_storable_still_replaces_a_lone_surrogate_directly` below covers
    that mechanism as a unit). This test's own predecessor asserted exactly
    that reachability, through `write_interaction` end to end.

    The prediction behind this rewrite was that bounding `citations` against
    `contracts.events.CitationPayload` (F-4.6-11) would leave the surrogate
    reaching `_storable` unfiltered, since `CitationPayload.claim_text` only
    declares `max_length`, a LENGTH bound, not a Unicode-well-formedness one.
    That prediction was WRONG, and this is recorded because it is the
    opposite of what was expected going in: pydantic-core's own `str`
    validation already refuses to construct any model with a lone surrogate
    in a `str` field, `max_length` or not, the identical mechanism that
    already protected `InteractionRow.query_text` before this ticket. So
    `CitationPayload.model_validate(item)` inside `InteractionRow`'s
    `_bound_each_citation` validator raises here, and the WHOLE row fails to
    construct, `pydantic.ValidationError` with `type=string_unicode`, before
    `write_interaction` is ever reached.

    This closes the surrogate class for `citations`, `normalized_entities`
    and `route` together (all three now validate through a real model with
    typed `str` leaves), not just for `citations` alone: none of them can
    carry a lone surrogate into a legitimate `InteractionRow` any more.
    `user_feedback` is the fourth bounded field but is not closed by this
    same argument, since `feedback.writer.write_feedback` assigns it
    directly to the ORM row rather than through `InteractionRow`'s
    validator; that path already went through pydantic's own `str`
    validation earlier, at `FeedbackPayload` construction in
    `feedback.record_feedback`, for the identical reason.

    Mutation: reverted `InteractionRow.citations`'s field validator to
    `return value` (no `CitationPayload.model_validate` call). Ran it. This
    test went red: `InteractionRow(**fields)` returned a row instead of
    raising, confirming the validator, not some other layer, is what
    catches this. Reverted after confirming red.
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="string_unicode"):
        _make_row(citations=[_citation_payload(claim_text="a claim\ud800")])


def test_storable_still_replaces_a_lone_surrogate_directly() -> None:
    """`_storable`'s own scrub, unit-tested now that `InteractionRow` closes
    the only path this file used to reach it through for `citations`.

    `writer.py`'s own module docstring names exactly this situation:
    "[the reachability argument] holds only while every upstream contract
    stays Pydantic-validated, and this module must not depend on that
    staying true." F-4.6-11 is that argument holding, for `citations`,
    `normalized_entities` and `route`; `_storable`'s scrub is kept anyway,
    as defense in depth against a future field that is `Any`-typed the way
    these three used to be, and this test is what keeps that code path
    covered now that no fixture reaches it through a full row.

    Mutation: narrow `_UNSTORABLE_CODE_POINTS` to `[\x00]`, the enumeration
    of the instance F-4.6-A-01 actually reported. Ran it directly against
    this call. The assertion below went red (`result` carried the raw
    `\ud800` unchanged instead of the replacement character). Reverted
    after confirming the failure.
    """
    from system_03_search_agent.feedback import writer as writer_module

    result = writer_module._storable({"claim_text": "a claim\ud800"})
    assert result == {"claim_text": "a claim\ufffd"}


@pytest.mark.asyncio
async def test_ordinary_control_characters_are_stored_unchanged(scratch_db) -> None:
    """The boundary in the other direction, and the reason this is not a
    control-character stripper.

    A tab, a newline, an ANSI escape and a bidi override all store fine in
    a `text` column. They are a RENDERING problem, which F-4.6-A-06 files
    against the review script's own terminal, and destroying them here
    would corrupt the content the review ritual reads while fixing nothing.

    Mutation: widen `_UNSTORABLE_CODE_POINTS` to the whole C0 range,
    `[\x00-\x1f\ud800-\udfff]`, which is the tempting over-correction.
    This test goes red on the stored text.
    """
    from system_03_search_agent.feedback.writer import write_interaction

    original = "line one\nline two\tand \x1b[2K and \u202e reversed"
    row = _make_row(query_text=original)
    await write_interaction(row)

    stored = _read_interaction(scratch_db, row.trace_id)
    assert stored.query_text == original


@pytest.mark.asyncio
async def test_feedback_with_a_nul_byte_in_its_comment_is_stored(scratch_db) -> None:
    """The same class arriving through the caller's own request body.

    `user_feedback` is a `jsonb` column and `comment`, `flagged_reason` and
    every `citation_flags` entry are caller-supplied strings, so the
    identical unstorable value reaches the database by a second route. Here
    the consequence is a 500 on a request the caller is watching rather
    than a silently dropped row, which is a different failure and the same
    cause.

    Mutation: drop the `_storable(...)` wrapper from the
    `row.user_feedback = ...` assignment. Ran it. This test goes red by
    raising out of `write_feedback`, and the exception is SQLAlchemy's
    `DataError` ("\u0000 cannot be converted to text") from the `UPDATE`
    itself rather than the `ValueError` psycopg2 raises for a plain `text`
    column, because this value is serialized into `jsonb` first. Recorded
    because it is the same class arriving as a different exception, and a
    handler written against `ValueError` would have missed it.
    """
    from system_03_search_agent.feedback.contracts import (
        FeedbackCitationFlag,
        FeedbackPayload,
    )
    from system_03_search_agent.feedback.writer import (
        write_feedback,
        write_interaction,
    )

    row = _make_row()
    await write_interaction(row)

    await write_feedback(
        trace_id=row.trace_id,
        owner_id=row.owner_id,
        payload=FeedbackPayload(
            rating="down",
            comment=f"this was wrong{chr(0)}",
            citation_flags=[
                FeedbackCitationFlag(citation_id="1", reason=f"bad{chr(0)}")
            ],
        ),
    )

    stored = _read_interaction(scratch_db, row.trace_id)
    assert stored.user_feedback["comment"] == "this was wrong\ufffd"
    assert stored.user_feedback["citation_flags"][0]["reason"] == "bad\ufffd"


# ---------------------------------------------------------------------------
# F-4.6-J-01: the durable half of the guest-to-account migration.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_migrated_guests_row_moves_to_the_new_account(scratch_db) -> None:
    """The finding, at this module's own seam.

    Mutation: make `reassign_interaction_owner` return 0 without issuing
    the `UPDATE`. This test goes red on the `owner_id` assertion, and the
    feedback call below then raises `FeedbackOwnershipError`, which is
    exactly the HTTP 403 the user saw on the answer they were looking at.
    """
    from system_03_search_agent.feedback.contracts import FeedbackPayload
    from system_03_search_agent.feedback.writer import (
        reassign_interaction_owner,
        write_feedback,
        write_interaction,
    )

    account = _insert_user(scratch_db)
    guest_owner = f"guest:{uuid.uuid4()}"
    row = _make_row(owner_id=guest_owner, user_id=None)
    await write_interaction(row)

    moved = reassign_interaction_owner(
        old_owner_id=guest_owner,
        new_owner_id=f"user:{account}",
        new_user_id=str(account),
    )

    assert moved == 1
    stored = _read_interaction(scratch_db, row.trace_id)
    assert stored.owner_id == f"user:{account}"
    assert stored.user_id == account, (
        "interactions.user_id stayed NULL, so the new account's daily query "
        "cap will never count the queries it just inherited"
    )

    # The point of the whole fix: the account can now rate its own answer.
    await write_feedback(
        trace_id=row.trace_id,
        owner_id=f"user:{account}",
        payload=FeedbackPayload(rating="up"),
    )
    assert _read_interaction(scratch_db, row.trace_id).user_feedback["rating"] == "up"


@pytest.mark.asyncio
async def test_a_migration_never_touches_another_principals_row(scratch_db) -> None:
    """F-4.5-A-02's guard, applied to the new write path.

    A migration that claimed every row with a NULL `user_id`, or every row
    whose `owner_id` merely starts with `guest:`, would hand one guest's
    conversation to whoever signed up next. The `WHERE` clause names one
    principal exactly.

    Mutation: change the `WHERE` clause to
    `Interaction.owner_id.like("guest:%")`. Ran it. This test goes red, and
    the assertion that fires first is `moved == 1`, reading 10, because the
    over-matching `UPDATE` sweeps up every guest row the module-scoped
    scratch database is holding at that moment. The bystander assertion
    below it would have caught the same defect; the count catches it one
    line earlier and states the blast radius, which is the more useful
    signal.
    """
    from system_03_search_agent.feedback.writer import (
        reassign_interaction_owner,
        write_interaction,
    )

    account = _insert_user(scratch_db)
    mine = f"guest:{uuid.uuid4()}"
    theirs = f"guest:{uuid.uuid4()}"
    my_row = _make_row(owner_id=mine, user_id=None)
    their_row = _make_row(owner_id=theirs, user_id=None)
    await write_interaction(my_row)
    await write_interaction(their_row)

    moved = reassign_interaction_owner(
        old_owner_id=mine,
        new_owner_id=f"user:{account}",
        new_user_id=str(account),
    )

    assert moved == 1
    assert _read_interaction(scratch_db, their_row.trace_id).owner_id == theirs, (
        "a bystanding guest's row was handed to the migrating account"
    )
    assert _read_interaction(scratch_db, their_row.trace_id).user_id is None


@pytest.mark.asyncio
async def test_a_replayed_migration_is_a_clean_no_op(scratch_db) -> None:
    """Idempotent, matching `reassign_owner`'s own contract: signup and
    login both call this, and a retried request must not be a second event.

    Mutation: none available that is not also caught above. This arm exists
    for the retry-safety gate in `production-standards` rather than for a
    line of code, and it is recorded as such rather than dressed up with an
    invented mutation.
    """
    from system_03_search_agent.feedback.writer import (
        reassign_interaction_owner,
        write_interaction,
    )

    account = _insert_user(scratch_db)
    guest_owner = f"guest:{uuid.uuid4()}"
    row = _make_row(owner_id=guest_owner, user_id=None)
    await write_interaction(row)

    first = reassign_interaction_owner(
        old_owner_id=guest_owner,
        new_owner_id=f"user:{account}",
        new_user_id=str(account),
    )
    second = reassign_interaction_owner(
        old_owner_id=guest_owner,
        new_owner_id=f"user:{account}",
        new_user_id=str(account),
    )

    assert (first, second) == (1, 0)
    assert _read_interaction(scratch_db, row.trace_id).owner_id == f"user:{account}"


def test_a_migration_with_a_non_uuid_account_never_raises() -> None:
    """The one input shape that can reach this function malformed.

    `new_user_id` is a string on the caller's side (`auth/router.py` passes
    `str(user.id)`), so a caller that ever passes something else must be
    refused rather than allowed to raise inside a committed signup.

    Mutation: delete the `try`/`except ValueError` around the UUID parse.
    This test goes red by raising `ValueError`.
    """
    from system_03_search_agent.feedback.writer import reassign_interaction_owner

    assert (
        reassign_interaction_owner(
            old_owner_id="guest:whatever",
            new_owner_id="user:whatever",
            new_user_id="not-a-uuid",
        )
        == 0
    )


@pytest.mark.asyncio
async def test_a_transient_failure_that_clears_on_retry_still_leaves_a_row(
    scratch_db, monkeypatch
) -> None:
    """The retry is real work, not a formality: a second attempt can succeed.

    Mutation-proven: removing the retry (calling `_write_interaction_row`
    only once) leaves the interactions table empty, since the first and
    only attempt is the one programmed to fail; the count assertion below
    then reads 0 instead of 1. Restored after confirming red.
    """
    from system_03_search_agent.feedback import writer as writer_module

    real_write = writer_module._write_interaction_row
    calls: list[int] = []

    def _fails_once_then_succeeds(row) -> None:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("simulated transient failure")
        real_write(row)

    monkeypatch.setattr(writer_module, "_write_interaction_row", _fails_once_then_succeeds)

    row = _make_row()
    await writer_module.write_interaction(row)

    assert len(calls) == 2
    assert _count_interactions(scratch_db, row.trace_id) == 1


@pytest.mark.asyncio
async def test_no_secret_reaches_the_log_line(scratch_db, monkeypatch, caplog) -> None:
    """The log line must never contain a credential or connection string.

    Mutation-proven: changing the `logger.warning(...)` calls in
    `write_interaction` to interpolate `str(exc)` instead of
    `type(exc).__name__` makes the planted secret appear in `caplog.text`,
    which the assertion below catches. Restored after confirming red.
    """
    from system_03_search_agent.feedback import writer as writer_module

    planted = f"postgresql://user:sk-secret-{uuid.uuid4().hex}@bad-host/db"

    def _always_fails(row) -> None:
        raise RuntimeError(planted)

    monkeypatch.setattr(writer_module, "_write_interaction_row", _always_fails)

    row = _make_row()
    with caplog.at_level(logging.WARNING, logger=writer_module.logger.name):
        await writer_module.write_interaction(row)

    assert planted not in caplog.text, "a secret-shaped exception message reached the log"
    assert row.trace_id in caplog.text, "the trace_id should be present for operators to act on"


# ---------------------------------------------------------------------------
# write_feedback: ownership.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registered_owner_can_write_feedback(scratch_db) -> None:
    """Positive case, registered-account shape: `user:<uuid>` admitted.

    Mutation-proven: changing `_caller_owns_row`'s `row.owner_id == owner_id`
    to `False` makes this raise `FeedbackOwnershipError` for the true owner.
    Restored after confirming red.
    """
    from system_03_search_agent.feedback.contracts import FeedbackPayload
    from system_03_search_agent.feedback.writer import write_feedback, write_interaction

    account_id = _insert_user(scratch_db)
    owner_id = f"user:{account_id}"
    row = _make_row(user_id=account_id, owner_id=owner_id)
    await write_interaction(row)

    await write_feedback(
        trace_id=row.trace_id,
        owner_id=owner_id,
        payload=FeedbackPayload(rating="up"),
    )

    stored = _fetch_interaction(scratch_db, row.trace_id)
    assert stored.user_feedback == {
        "rating": "up",
        "comment": None,
        "flagged_reason": None,
        "citation_flags": [],
    }


@pytest.mark.asyncio
async def test_a_different_registered_account_is_refused_and_writes_nothing(
    scratch_db,
) -> None:
    """Negative case, registered-account shape: asserted on the stored value.

    Mutation-proven: deleting the `if not _caller_owns_row(...): raise
    FeedbackOwnershipError(...)` guard in `write_feedback` makes the
    stranger's write succeed, and `after != before` (in fact `after ==
    "down"`) fails the equality assertion below even though no exception
    would be raised to catch. Restored after confirming red.
    """
    from system_03_search_agent.feedback.contracts import (
        FeedbackOwnershipError,
        FeedbackPayload,
    )
    from system_03_search_agent.feedback.writer import write_feedback, write_interaction

    owner_account = _insert_user(scratch_db)
    stranger_account = _insert_user(scratch_db)
    owner_id = f"user:{owner_account}"
    row = _make_row(user_id=owner_account, owner_id=owner_id)
    await write_interaction(row)

    await write_feedback(
        trace_id=row.trace_id,
        owner_id=owner_id,
        payload=FeedbackPayload(rating="up"),
    )
    before = _fetch_interaction(scratch_db, row.trace_id).user_feedback

    with pytest.raises(FeedbackOwnershipError):
        await write_feedback(
            trace_id=row.trace_id,
            owner_id=f"user:{stranger_account}",
            payload=FeedbackPayload(rating="down"),
        )

    after = _fetch_interaction(scratch_db, row.trace_id).user_feedback
    assert after == before, "a non-owner's write changed the stored feedback"


@pytest.mark.asyncio
async def test_guest_owner_can_write_feedback_via_owner_id(scratch_db) -> None:
    """Positive case, guest shape: `guest:<uuid>` admitted with no envelope.

    This is F-4.6-01's own repro shape: a guest whose turn resolved nothing
    (no entity, no finding) never gets a `sessions.memory` envelope at all,
    the session row `write_interaction` creates below is left with `memory`
    NULL, and the true owner must still be able to rate their own answer.

    Mutation-proven: changing `_caller_owns_row`'s `row.owner_id == owner_id`
    to `False` makes this raise `FeedbackOwnershipError` for the true owner,
    the exact regression this test exists to catch. Restored after
    confirming red.
    """
    from system_03_search_agent.feedback.contracts import FeedbackPayload
    from system_03_search_agent.feedback.writer import write_feedback, write_interaction

    owner_id = f"guest:{uuid.uuid4()}"
    session_id = uuid.uuid4()
    row = _make_row(session_id=session_id, owner_id=owner_id)  # no pre-existing sessions row
    await write_interaction(row)

    assert _fetch_session(scratch_db, session_id).memory is None, (
        "this test's premise is a turn that resolved nothing, so the "
        "session row must carry no memory envelope"
    )

    await write_feedback(
        trace_id=row.trace_id, owner_id=owner_id, payload=FeedbackPayload(rating="up")
    )
    stored = _fetch_interaction(scratch_db, row.trace_id)
    assert stored.user_feedback["rating"] == "up"


@pytest.mark.asyncio
async def test_a_different_guest_is_refused_and_writes_nothing(scratch_db) -> None:
    """Negative case, guest shape: two guests, one row, one true owner.

    Mutation-proven: same guard as the registered-account negative test.
    Deleting the ownership check in `write_feedback` lets the stranger's
    write land, and the stored-value equality assertion below catches it
    even though the call would no longer raise. Restored after confirming
    red.
    """
    from system_03_search_agent.feedback.contracts import (
        FeedbackOwnershipError,
        FeedbackPayload,
    )
    from system_03_search_agent.feedback.writer import write_feedback, write_interaction

    owner_id = f"guest:{uuid.uuid4()}"
    stranger_id = f"guest:{uuid.uuid4()}"
    row = _make_row(owner_id=owner_id)
    await write_interaction(row)
    await write_feedback(
        trace_id=row.trace_id, owner_id=owner_id, payload=FeedbackPayload(rating="up")
    )
    before = _fetch_interaction(scratch_db, row.trace_id).user_feedback

    with pytest.raises(FeedbackOwnershipError):
        await write_feedback(
            trace_id=row.trace_id,
            owner_id=stranger_id,
            payload=FeedbackPayload(rating="down"),
        )

    after = _fetch_interaction(scratch_db, row.trace_id).user_feedback
    assert after == before, "a different guest's write changed the stored feedback"


@pytest.mark.asyncio
async def test_a_row_with_no_owner_id_refuses_even_the_true_caller(scratch_db) -> None:
    """The documented, deliberate cost of never guessing at a NULL owner_id.

    `owner_id` is NULL only on a row written before alembic 0008 added the
    column. Nothing on such a row distinguishes its true owner from any
    other caller, so `write_feedback` refuses rather than trust an
    unverifiable claim, even from the caller who happens to be telling the
    truth. NULL must not mean "anyone" (F-4.5-A-02).

    Mutation-proven: changing `_caller_owns_row`'s `row.owner_id is not
    None` guard to always `True` makes the `row.owner_id == owner_id`
    compare run against `None == "guest:..."`, which is still False and
    would not by itself flip this test; the mutation that actually
    reproduces the bug is changing the whole return to
    `return owner_id is not None` (attribute the row to whoever asks,
    regardless of what is stored), which makes this test's `pytest.raises`
    block fail to raise. Confirmed red, then restored.
    """
    from system_03_search_agent.feedback.contracts import (
        FeedbackOwnershipError,
        FeedbackPayload,
    )
    from system_03_search_agent.feedback.writer import write_feedback, write_interaction

    true_owner = f"guest:{uuid.uuid4()}"
    row = _make_row(owner_id=true_owner)
    await write_interaction(row)
    _null_out_owner_id(scratch_db, row.trace_id)
    assert _fetch_interaction(scratch_db, row.trace_id).owner_id is None

    with pytest.raises(FeedbackOwnershipError):
        await write_feedback(
            trace_id=row.trace_id,
            owner_id=true_owner,
            payload=FeedbackPayload(rating="up"),
        )


@pytest.mark.asyncio
async def test_repeat_feedback_replaces_rather_than_appends(scratch_db) -> None:
    """Idempotent under retry: the second write is the final state, not a merge.

    Mutation-proven, and rebuilt once after the first attempt turned out
    vacuous (this docstring used to claim a different mutation, and it did
    not actually reproduce red; the corrected claim below was verified
    against the real code before being written down). A naive full-key
    dict merge, `{**(row.user_feedback or {}), **payload.model_dump(...)}`,
    is byte-for-byte indistinguishable from a plain replace for this
    payload: `FeedbackPayload.model_dump()` always emits every field,
    including an explicitly unset `comment` as `None`, so the second
    call's dump already carries `"comment": None` and overwrites the first
    call's value under either implementation. That mutation was tried and
    left this test green, which is exactly the vacuous-arm shape this
    repository's `goal-contracts` rule warns about.

    The mutation that actually reproduces the append/merge bug this test
    exists to catch is a COALESCING merge, one that only overwrites a
    field when the new payload's value is not `None`, keeping the old
    value otherwise:

        new_dump = payload.model_dump(mode="json")
        existing = row.user_feedback or {}
        row.user_feedback = {
            **existing,
            **{k: v for k, v in new_dump.items() if v is not None},
        }

    Under that mutation the second call's `comment=None` is filtered out of
    the update, so the first call's `"first pass"` survives, and the
    `stored["comment"] is None` assertion below goes red. Confirmed red
    against exactly this implementation, then restored.
    """
    from system_03_search_agent.feedback.contracts import FeedbackPayload
    from system_03_search_agent.feedback.writer import write_feedback, write_interaction

    account_id = _insert_user(scratch_db)
    owner = f"user:{account_id}"
    row = _make_row(user_id=account_id, owner_id=owner)
    await write_interaction(row)

    await write_feedback(
        trace_id=row.trace_id,
        owner_id=owner,
        payload=FeedbackPayload(rating="down", comment="first pass"),
    )
    await write_feedback(
        trace_id=row.trace_id,
        owner_id=owner,
        payload=FeedbackPayload(rating="up"),
    )

    stored = _fetch_interaction(scratch_db, row.trace_id).user_feedback
    assert stored["rating"] == "up"
    assert stored["comment"] is None, (
        "the first submission's comment survived a replacement write, so "
        "this is an append/merge rather than a replace"
    )


@pytest.mark.asyncio
async def test_feedback_on_an_uncaptured_trace_id_raises_not_found(scratch_db) -> None:
    """A real, expected state: feedback can arrive before capture does.

    Mutation-proven: changing `scalar_one_or_none()` plus the `if row is
    None: raise InteractionNotFound(...)` guard to instead construct and
    write a new row makes this test's `pytest.raises` fail to raise, and a
    stray row would appear where the acceptance criteria requires an
    explicit refusal instead. Restored after confirming red.
    """
    from system_03_search_agent.feedback.contracts import (
        FeedbackPayload,
        InteractionNotFound,
    )
    from system_03_search_agent.feedback.writer import write_feedback

    with pytest.raises(InteractionNotFound):
        await write_feedback(
            trace_id=f"never-captured-{uuid.uuid4().hex}",
            owner_id=f"guest:{uuid.uuid4()}",
            payload=FeedbackPayload(rating="up"),
        )
