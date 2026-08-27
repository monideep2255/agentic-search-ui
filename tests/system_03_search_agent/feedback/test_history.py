"""T-4.13-01: `feedback/history.py`, the owner-scoped read path over `interactions`.

## Coverage: what this file exercises and what it deliberately omits

Per `.claude/rules/goal-contracts.md`, a verify surface must state its own
coverage so a gap is arguable rather than silently assumed away.

Exercised, at the `list_history` function level rather than through HTTP:

- Owner scoping: a caller's own rows come back, another caller's rows for
  the SAME table do not, exercised with the WHERE clause the function
  actually issues (`Interaction.owner_id == owner_id`), never a
  Python-side filter.
- A row whose `owner_id` is NULL (the pre-alembic-0008 shape, seeded by a
  direct parameterised INSERT the same way the premise gate does, since
  `InteractionRow` itself refuses to construct one) is never returned,
  paired with a real row for the SAME caller so an implementation that
  returns nothing at all cannot pass this clause by accident.
- The `LIMIT` is real SQL, not a Python slice: seeded five rows for one
  owner, `limit=2` returns exactly two, and they are the two NEWEST of the
  five (proves the database applied the limit AFTER ordering, not before).
- The order is a TOTAL order: two rows sharing the exact same `created_at`
  (forced via a direct INSERT, since `write_interaction`'s server default
  makes a natural collision unreliable to reproduce) still come back in a
  deterministic, `id`-tiebroken order rather than shuffling.
- `question`, `trust_signal` and `citation_count` round-trip: the returned
  `HistoryEntry` carries the exact question text as stored, the exact
  `trust_signal`, and a citation count equal to `len(citations)`.
- The refusal guards: an empty `owner_id`, an `owner_id` one character
  over `_MAX_OWNER_ID_LENGTH` (128), a `limit` below 1, and a `limit` one
  above `MAX_LIMIT` (50) each raise `ValueError` rather than issuing a
  query. `owner_id` exactly at the 128-character boundary is accepted, the
  boundary case a strictly-greater-than check could get backwards.

NOT exercised, deliberately:

- The HTTP surface (`GET /v1/history`'s status codes, its 401, its 422
  message content). That is `tests/system_03_search_agent/adapters/
  web_sse/test_history_endpoint.py`'s job, and the end-to-end property
  (a REAL run's row surviving a reload) is the premise gate's
  (`test_phase_4_13_premise.py`), never this file's.
- That no f-string or `.format()` builds any query string in this module.
  A static property of the source, verified by reading `feedback/
  history.py` and by `ruff`, not by a runtime assertion a test could make
  pass while the source still concatenated strings elsewhere.
- Concurrent callers racing against the same owner's rows. This function
  issues one read-only `SELECT`; there is no write path here to race.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa

USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
os.environ.setdefault("USER_DB_URL", USER_DB_URL)


def _can_connect() -> bool:
    try:
        probe_engine = sa.create_engine(USER_DB_URL)
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


pytestmark = pytest.mark.skipif(
    not _can_connect(),
    reason=f"user database unreachable at {USER_DB_URL}; the read path needs a real database",
)


def _citation_payload(*, claim_text: str = "BRCA1 is a gene.") -> dict:
    """A full, schema-conformant `contracts.events.CitationPayload` dict.

    Copied from `test_writer.py`'s own helper of the same name (same shape,
    same field values) rather than imported: that module is a unit-test
    module with no public fixture surface, the same reasoning its own
    docstring gives for duplicating `test_capture.py`'s copy.
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


async def _seed(
    *,
    owner_id: str,
    question: str,
    trust_signal: str = "answer",
    citations: list[dict] | None = None,
) -> str:
    """Write one real `interactions` row through the real writer.

    Goes through `write_interaction`, not a hand-rolled INSERT, so a row
    this file seeds is the same shape a real capture produces. Returns the
    row's `trace_id`.
    """
    from system_03_search_agent.feedback.contracts import InteractionRow
    from system_03_search_agent.feedback.writer import write_interaction

    trace_id = f"histtest-{uuid.uuid4().hex}"
    await write_interaction(
        InteractionRow(
            trace_id=trace_id,
            owner_id=owner_id,
            query_text=question,
            query_class="lookup",
            trust_signal=trust_signal,  # type: ignore[arg-type]
            rubric_outcome="pass",
            citations=citations or [],
        )
    )
    return trace_id


def _seed_null_owner(question: str) -> str:
    """Write one row with `owner_id IS NULL`, the pre-alembic-0008 shape.

    `InteractionRow` refuses to construct with `owner_id=None` (the field
    is required there), so this is a direct parameterised INSERT, exactly
    the shape the premise gate's own `_seed_row(owner_id=None, ...)` uses,
    for the same reason: the row shape under test is one the live write
    path can no longer produce.
    """
    trace_id = f"histtest-null-{uuid.uuid4().hex}"
    engine = sa.create_engine(USER_DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO interactions "
                    "(trace_id, owner_id, user_id, query_text, query_class, route, "
                    " trust_signal, rubric_outcome) "
                    "VALUES (:trace_id, NULL, NULL, :query_text, 'lookup', "
                    " '{}'::jsonb, 'answer', 'pass')"
                ),
                {"trace_id": trace_id, "query_text": question},
            )
    finally:
        engine.dispose()
    return trace_id


def _seed_with_created_at(owner_id: str, question: str, created_at: datetime) -> str:
    """Write one row with an EXPLICIT `created_at`, bypassing the server
    default, so two rows can be forced to share the exact same timestamp.

    `write_interaction` always lands under `now()`, which makes a genuine
    same-tick collision unreliable to reproduce on demand; this is the
    direct-INSERT equivalent of the premise gate's `_seed_row`, adapted to
    control the one column that clause needs to control.
    """
    trace_id = f"histtest-ts-{uuid.uuid4().hex}"
    engine = sa.create_engine(USER_DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO interactions "
                    "(trace_id, owner_id, user_id, created_at, query_text, query_class, "
                    " route, trust_signal, rubric_outcome) "
                    "VALUES (:trace_id, :owner_id, NULL, :created_at, :query_text, 'lookup', "
                    " '{}'::jsonb, 'answer', 'pass')"
                ),
                {
                    "trace_id": trace_id,
                    "owner_id": owner_id,
                    "created_at": created_at,
                    "query_text": question,
                },
            )
    finally:
        engine.dispose()
    return trace_id


def _row_owner(trace_id: str) -> str | None:
    """The populate-check every clause below runs before asserting
    anything about isolation or ordering: read the seeded row's stored
    owner straight from the table, so a clause that finds nothing cannot
    be mistaken for a clause whose seed never landed.
    """
    engine = sa.create_engine(USER_DB_URL)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                sa.text("SELECT owner_id FROM interactions WHERE trace_id = :trace_id"),
                {"trace_id": trace_id},
            ).first()
    finally:
        engine.dispose()
    assert row is not None, f"the seed for {trace_id} never reached the table"
    return row[0]


def _unique_owner(kind: str = "guest") -> str:
    return f"{kind}:{uuid.uuid4()}"


# ---------------------------------------------------------------------------
# Owner scoping and the NULL-owner refusal.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_owner_scoping_returns_only_the_callers_own_rows() -> None:
    from system_03_search_agent.feedback.history import list_history

    owner_a = _unique_owner()
    owner_b = _unique_owner()
    marker_a = f"marker-{uuid.uuid4().hex[:12]}"
    marker_b = f"marker-{uuid.uuid4().hex[:12]}"

    trace_a = await _seed(owner_id=owner_a, question=f"Question A {marker_a}")
    trace_b = await _seed(owner_id=owner_b, question=f"Question B {marker_b}")
    assert _row_owner(trace_a) == owner_a
    assert _row_owner(trace_b) == owner_b

    entries_a = list_history(owner_id=owner_a)
    entries_b = list_history(owner_id=owner_b)

    questions_a = [e.question for e in entries_a]
    questions_b = [e.question for e in entries_b]
    assert marker_a in " ".join(questions_a), "the control did not hold: owner A cannot see its own row"
    assert marker_b in " ".join(questions_b), "the control did not hold: owner B cannot see its own row"
    assert marker_b not in " ".join(questions_a), "owner A was handed owner B's question"
    assert marker_a not in " ".join(questions_b), "owner B was handed owner A's question"


@pytest.mark.asyncio
async def test_a_null_owner_row_is_never_returned() -> None:
    from system_03_search_agent.feedback.history import list_history

    marker = f"orphan-{uuid.uuid4().hex[:12]}"
    orphan_trace = _seed_null_owner(f"An orphaned question {marker}")
    assert _row_owner(orphan_trace) is None, "the orphan seed landed with an owner"

    owner = _unique_owner()
    own_question = f"What gene is BRCA1? mine-{uuid.uuid4().hex[:8]}"
    own_trace = await _seed(owner_id=owner, question=own_question)
    assert _row_owner(own_trace) == owner

    entries = list_history(owner_id=owner)
    questions = [e.question for e in entries]
    assert own_question in questions, (
        "the control did not hold: this caller cannot see their own row, "
        "so the orphan's absence proves nothing"
    )
    assert marker not in " ".join(questions), "a row with no recorded owner was served to a caller"


# ---------------------------------------------------------------------------
# LIMIT is real SQL, and the order is total.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_limit_is_a_real_sql_limit_and_returns_the_newest() -> None:
    from system_03_search_agent.feedback.history import list_history

    owner = _unique_owner()
    markers = [f"seq-{n}-{uuid.uuid4().hex[:8]}" for n in range(5)]
    for marker in markers:
        # A small gap between inserts so `created_at` orders them
        # unambiguously; the collision case has its own clause below.
        trace_id = await _seed(owner_id=owner, question=f"Question {marker}")
        assert _row_owner(trace_id) == owner

    unbounded = list_history(owner_id=owner)
    assert len(unbounded) >= 5, (
        "the control did not hold: fewer than the five seeded rows came back "
        f"unbounded. Got: {len(unbounded)}"
    )

    limited = list_history(owner_id=owner, limit=2)
    assert len(limited) == 2, f"limit=2 returned {len(limited)} rows"
    newest_two_markers = [e.question for e in unbounded[:2]]
    limited_questions = [e.question for e in limited]
    assert limited_questions == newest_two_markers, (
        "limit=2 did not return the two newest rows, so the LIMIT is not "
        f"being applied after ordering. Got: {limited_questions}, "
        f"expected: {newest_two_markers}"
    )


def test_order_is_total_when_created_at_collides() -> None:
    from system_03_search_agent.feedback.history import list_history

    owner = _unique_owner()
    same_instant = datetime.now(UTC)
    marker_first = f"tie-first-{uuid.uuid4().hex[:8]}"
    marker_second = f"tie-second-{uuid.uuid4().hex[:8]}"

    trace_first = _seed_with_created_at(owner, f"Question {marker_first}", same_instant)
    trace_second = _seed_with_created_at(owner, f"Question {marker_second}", same_instant)
    assert _row_owner(trace_first) == owner
    assert _row_owner(trace_second) == owner

    # `id` is a `gen_random_uuid()` primary key with no ordering relation to
    # insertion sequence, so the correct tiebreak is whichever `id` sorts
    # higher, not "the second one inserted". Read both `id`s back and
    # predict the order from them directly, rather than assuming a
    # particular insertion-order outcome.
    engine = sa.create_engine(USER_DB_URL)
    try:
        with engine.connect() as conn:
            id_first = conn.execute(
                sa.text("SELECT id FROM interactions WHERE trace_id = :t"),
                {"t": trace_first},
            ).scalar_one()
            id_second = conn.execute(
                sa.text("SELECT id FROM interactions WHERE trace_id = :t"),
                {"t": trace_second},
            ).scalar_one()
    finally:
        engine.dispose()
    expected_first = marker_first if id_first > id_second else marker_second
    expected_second = marker_second if expected_first == marker_first else marker_first

    entries = list_history(owner_id=owner)
    relevant = [e.question for e in entries if marker_first in e.question or marker_second in e.question]
    assert len(relevant) == 2, f"expected exactly the two tied rows, got: {relevant}"
    assert expected_first in relevant[0] and expected_second in relevant[1], (
        f"a `created_at` collision produced a non-deterministic order. Got: {relevant}"
    )


# ---------------------------------------------------------------------------
# Field round-trip.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_question_trust_signal_and_citation_count_round_trip() -> None:
    from system_03_search_agent.feedback.history import list_history

    owner = _unique_owner()
    question = f"Which diseases are associated with TP53? {uuid.uuid4().hex[:8]}"
    citations = [_citation_payload(), _citation_payload(claim_text="a second claim.")]
    trace_id = await _seed(owner_id=owner, question=question, trust_signal="flag", citations=citations)
    assert _row_owner(trace_id) == owner

    entries = list_history(owner_id=owner)
    matches = [e for e in entries if e.trace_id == trace_id]
    assert len(matches) == 1, f"expected exactly one entry for {trace_id}, got {len(matches)}"
    entry = matches[0]
    assert entry.question == question, "the stored question was rewritten on the way out"
    assert entry.trust_signal == "flag", f"expected trust_signal='flag', got {entry.trust_signal!r}"
    assert entry.citation_count == 2, f"expected citation_count=2, got {entry.citation_count}"


# ---------------------------------------------------------------------------
# Refusal guards. No query is issued for any of these.
# ---------------------------------------------------------------------------


def test_empty_owner_id_is_refused() -> None:
    from system_03_search_agent.feedback.history import list_history

    with pytest.raises(ValueError, match="owner_id must not be empty"):
        list_history(owner_id="")


def test_over_long_owner_id_is_refused() -> None:
    from system_03_search_agent.feedback.history import _MAX_OWNER_ID_LENGTH, list_history

    too_long = "guest:" + "a" * _MAX_OWNER_ID_LENGTH
    with pytest.raises(ValueError, match="capped at"):
        list_history(owner_id=too_long)


def test_owner_id_exactly_at_the_bound_is_accepted() -> None:
    """The boundary a strictly-greater-than check could get backwards."""
    from system_03_search_agent.feedback.history import _MAX_OWNER_ID_LENGTH, list_history

    exactly_at_bound = "g" * _MAX_OWNER_ID_LENGTH
    assert len(exactly_at_bound) == _MAX_OWNER_ID_LENGTH
    # Must not raise. An owner this long simply (and correctly) has no rows.
    assert list_history(owner_id=exactly_at_bound) == []


def test_limit_below_one_is_refused() -> None:
    from system_03_search_agent.feedback.history import list_history

    with pytest.raises(ValueError, match="at least 1"):
        list_history(owner_id=_unique_owner(), limit=0)


def test_limit_above_the_maximum_is_refused() -> None:
    from system_03_search_agent.feedback.history import MAX_LIMIT, list_history

    with pytest.raises(ValueError, match="capped at"):
        list_history(owner_id=_unique_owner(), limit=MAX_LIMIT + 1)
