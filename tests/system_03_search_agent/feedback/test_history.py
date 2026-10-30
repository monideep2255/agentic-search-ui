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
- `limit` bounds the page to exactly that many rows, and they are the
  NEWEST rows: seeded five rows for one owner, `limit=2` returns exactly
  two, and they are the two newest of the five. F-4.13-J-03's correction:
  this does NOT prove the `LIMIT` is applied by the database rather than
  by a Python-side slice of a larger fetched result, a claim this bullet
  used to make. Measured: replacing the SQL `.limit(limit)` with
  `.limit(MAX_LIMIT)` plus a Python-side `[:limit]` left this clause, and
  all 31 others in this file, green. That the `LIMIT` clause is real SQL
  is a STATIC property of the source (`feedback/history.py`'s own
  `.limit(limit)` call), like the f-string bullet below, not something a
  black-box call through `list_history` can distinguish at runtime.
- The order is a TOTAL order: two rows sharing the exact same `created_at`
  (forced via a direct INSERT, since `write_interaction`'s server default
  makes a natural collision unreliable to reproduce) still come back in a
  deterministic, `id`-tiebroken order rather than shuffling.
- `question`, `trust_signal` and `citation_count` round-trip: the returned
  `HistoryEntry` carries the exact question text as stored, the exact
  `trust_signal`, and a citation count equal to `len(citations)`.
- A stored `citations` value that is NOT a list (F-4.13-RV-02). The column
  is `JSONB NOT NULL` with no check constraint, so it accepts a scalar
  number, a boolean, a string, an object, and the JSON literal `null`,
  none of which the `Mapped[list[Any]]` annotation actually guarantees.
  Each of the five is seeded by direct parameterised INSERT (the write
  path validates `citations` and cannot produce them) and asserted to
  yield `citation_count is None` with no exception, beside a well-formed
  sibling row that still reports its real count.
- The refusal guards: an empty `owner_id`, an `owner_id` one character
  over `_MAX_OWNER_ID_LENGTH` (128), a `limit` below 1, and a `limit` one
  above `MAX_LIMIT` (50) each raise `ValueError` rather than issuing a
  query. `owner_id` exactly at the 128-character boundary is accepted, the
  boundary case a strictly-greater-than check could get backwards.

- Card 136.1, the `before` cursor of `list_history_page`: paging at the
  boundaries (20, 21, 40 and 41 rows, and 45 rows into 20, 20 and 5), every
  row exactly once and in order, `has_more` false on the last page; ties on
  one timestamp split across page boundaries; another owner's `trace_id`, a
  `trace_id` that never existed, and this owner's cursor beside a
  stranger's interleaved rows; an empty, over-long or control-character
  cursor refused with `ValueError` before any query. One clause goes
  through `GET /v1/history` itself, against this real database, to pin that
  a stranger's cursor and a cursor that never existed return byte-identical
  responses.

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


def _citation_payload(
    *,
    claim_text: str = "BRCA1 is a gene.",
    source_url: str = "https://www.ncbi.nlm.nih.gov/gene/672",
) -> dict:
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
        "source_url": source_url,
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


def _seed_with_raw_citations(owner_id: str, question: str, citations_json: str) -> str:
    """Write one row whose `citations` column holds an ARBITRARY JSON value.

    `interactions.citations` is `JSONB NOT NULL DEFAULT '[]'::jsonb` with no
    check constraint (alembic 0001), so the column accepts any JSON value
    while `Interaction.citations`'s Python annotation says `list[Any]`.
    `InteractionRow.citations` is a validated `list[dict]`, so the live
    write path cannot produce the mismatch and cannot seed this shape,
    exactly the reasoning `_seed_null_owner` above gives for its own direct
    INSERT.

    `citations_json` is a JSON literal (`'5'`, `'"abc"'`, `'null'`), cast
    server-side, and it is passed as a BOUND PARAMETER, never concatenated
    into the statement.
    """
    trace_id = f"histtest-cit-{uuid.uuid4().hex}"
    engine = sa.create_engine(USER_DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO interactions "
                    "(trace_id, owner_id, user_id, query_text, query_class, route, "
                    " trust_signal, rubric_outcome, citations) "
                    "VALUES (:trace_id, :owner_id, NULL, :query_text, 'lookup', "
                    " '{}'::jsonb, 'answer', 'pass', CAST(:citations AS jsonb))"
                ),
                {
                    "trace_id": trace_id,
                    "owner_id": owner_id,
                    "query_text": question,
                    "citations": citations_json,
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
# The page is bounded and newest-first, and the order is total.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_limit_returns_exactly_the_newest_n_rows() -> None:
    """`limit` bounds the page size, and the page returned is the newest N.

    F-4.13-J-03's correction: renamed from `test_limit_is_a_real_sql_
    limit_and_returns_the_newest`. This clause cannot tell a real SQL
    `LIMIT` apart from a Python-side slice of a larger fetch, only that
    the OUTCOME (count and which rows) is correct; see the module
    docstring's coverage bullet for why that half of the old name was
    unproven.
    """
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


#: How many rows this clause ties on one timestamp. Six is not decoration,
#: and F-4.13-01 is why it is not two.
#:
#: The clause's whole job is to fail when the `id` tiebreaker is dropped
#: from the ORDER BY. With the tiebreaker gone, PostgreSQL returns tied
#: rows in an order it never promised, and that order can coincide with
#: the id-descending order this clause predicts. With two rows it
#: coincides half the time, so the clause caught a measured 3 of 10
#: mutation runs: a coin flip, which is worse than no clause at all,
#: because a real finding then reads as noise (the same reasoning that
#: made the doc-readability gate's non-determinism its worst defect).
#:
#: The odds of an accidental match are 1/N!, so six rows moves it from
#: 1 in 2 to 1 in 720.
_TIED_ROW_COUNT = 6


def test_order_is_total_when_created_at_collides() -> None:
    from system_03_search_agent.feedback.history import list_history

    owner = _unique_owner()
    same_instant = datetime.now(UTC)
    markers = [f"tie-{n}-{uuid.uuid4().hex[:8]}" for n in range(_TIED_ROW_COUNT)]

    trace_ids = {
        marker: _seed_with_created_at(owner, f"Question {marker}", same_instant)
        for marker in markers
    }
    for marker, trace_id in trace_ids.items():
        assert _row_owner(trace_id) == owner, f"the seed for {marker} never landed"

    # `id` is a `gen_random_uuid()` primary key with no ordering relation to
    # insertion sequence, so the correct tiebreak is whichever `id` sorts
    # higher, not "the one inserted last". Read every `id` back and predict
    # the order from them directly, rather than assuming a particular
    # insertion-order outcome.
    engine = sa.create_engine(USER_DB_URL)
    try:
        with engine.connect() as conn:
            ids = {
                marker: conn.execute(
                    sa.text("SELECT id FROM interactions WHERE trace_id = :t"),
                    {"t": trace_id},
                ).scalar_one()
                for marker, trace_id in trace_ids.items()
            }
    finally:
        engine.dispose()
    expected = sorted(markers, key=lambda marker: ids[marker], reverse=True)

    entries = list_history(owner_id=owner, limit=_TIED_ROW_COUNT)
    returned = [
        next(marker for marker in markers if marker in entry.question)
        for entry in entries
        if any(marker in entry.question for marker in markers)
    ]
    assert len(returned) == _TIED_ROW_COUNT, (
        f"expected exactly the {_TIED_ROW_COUNT} tied rows, got: {returned}"
    )
    assert returned == expected, (
        f"a `created_at` collision produced a non-deterministic order. "
        f"Got: {returned}, expected: {expected}"
    )


# ---------------------------------------------------------------------------
# Field round-trip.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_question_trust_signal_and_citation_count_round_trip() -> None:
    from system_03_search_agent.feedback.history import list_history

    owner = _unique_owner()
    question = f"Which diseases are associated with TP53? {uuid.uuid4().hex[:8]}"
    # Card 22: the count is distinct record pages, so the round trip seeds
    # two citations of one gene page (with and without a trailing slash)
    # and one of a second page, and reads back 2, not 3.
    citations = [
        _citation_payload(),
        _citation_payload(
            claim_text="a second claim.", source_url="https://www.ncbi.nlm.nih.gov/gene/672/"
        ),
        _citation_payload(
            claim_text="a third claim.", source_url="https://www.ncbi.nlm.nih.gov/medgen/C0346153"
        ),
    ]
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
# F-4.13-RV-02: a stored `citations` value that is not a list.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("citations_json", "shape"),
    [
        ("5", "a JSONB scalar number"),
        ("true", "a JSONB scalar boolean"),
        ('"abc"', "a JSONB string"),
        ('{"a": 1}', "a JSONB object"),
        ("null", "the JSON literal null"),
    ],
)
@pytest.mark.asyncio
async def test_a_non_list_citations_value_yields_no_count_and_never_raises(
    citations_json: str, shape: str
) -> None:
    """F-4.13-RV-02, measured against the real column rather than reasoned.

    Two separate failures, both from one row and both reproduced here:

    - `5` and `true` raised `TypeError: object of type 'int' has no len()`
      out of `list_history` itself, ABOVE the endpoint's per-row guard, so
      the caller's entire history returned 500. That is the outcome
      F-4.13-A-02 was filed for, by the route A-02's fix did not reach.
    - `"abc"` did not raise at all, which is worse: `len("abc")` is 3, so
      the row was served with `citation_count: 3` and `omitted_count: 0`, a
      source count nothing counted, presented as complete.

    The required behaviour for every shape is the same: no exception, and
    `citation_count is None` rather than a number. `null` is included
    deliberately: it reads back as Python `None`, and the pre-fix
    `len(row.citations or [])` reported it as 0, which asserts "this answer
    cited nothing" about a row that does not say so.
    """
    from system_03_search_agent.feedback.history import list_history

    owner = _unique_owner()
    question = f"A row whose citations column holds {shape} {uuid.uuid4().hex[:8]}"
    trace_id = _seed_with_raw_citations(owner, question, citations_json)
    assert _row_owner(trace_id) == owner, "the seed never reached the table"

    # Must not raise. Before the fix, three of these five parameter sets
    # raised out of this exact call.
    entries = list_history(owner_id=owner)

    matches = [entry for entry in entries if entry.trace_id == trace_id]
    assert len(matches) == 1, (
        f"the row must still be READ, only its count withheld; got {len(matches)} matches"
    )
    assert matches[0].citation_count is None, (
        f"an unreadable citations value must yield no count, not a substituted "
        f"one; got citation_count={matches[0].citation_count!r}"
    )
    assert matches[0].question == question, "the question itself must survive intact"


@pytest.mark.asyncio
async def test_one_unreadable_row_does_not_cost_its_well_formed_siblings() -> None:
    """The blast-radius half of F-4.13-RV-02, and the populate-check for the
    clause above: a real list still counts, in the same page as a row that
    cannot.

    Without this, a fix that returned `None` for EVERY row would leave the
    parameterised clause above fully green while deleting the feature.
    """
    from system_03_search_agent.feedback.history import list_history

    owner = _unique_owner()
    good_trace = await _seed(
        owner_id=owner,
        question=f"A well-formed row {uuid.uuid4().hex[:8]}",
        citations=[
            _citation_payload(),
            _citation_payload(
                claim_text="a second claim.",
                source_url="https://www.ncbi.nlm.nih.gov/medgen/C0346153",
            ),
        ],
    )
    bad_trace = _seed_with_raw_citations(owner, f"A scalar row {uuid.uuid4().hex[:8]}", "5")
    assert _row_owner(good_trace) == owner
    assert _row_owner(bad_trace) == owner

    entries = list_history(owner_id=owner)
    by_trace = {entry.trace_id: entry for entry in entries}

    assert good_trace in by_trace, "the well-formed sibling was lost with the bad row"
    assert by_trace[good_trace].citation_count == 2, (
        f"a real list must still be counted; got "
        f"{by_trace[good_trace].citation_count!r}"
    )
    assert bad_trace in by_trace
    assert by_trace[bad_trace].citation_count is None


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



# ---------------------------------------------------------------------------
# Card 136.1: older pages through the `before` cursor.
# ---------------------------------------------------------------------------


def _seed_many(owner_id: str, created_ats: list[datetime], tag: str) -> list[str]:
    """Write one row per timestamp for `owner_id`, in one transaction.

    Direct parameterised INSERT for the same reason `_seed_with_created_at`
    gives: the timestamps, and so the page boundaries and the ties, are the
    thing under test. One engine and one transaction for the lot, so a
    41-row seed costs one round of connection setup, not 41.
    """
    trace_ids = [f"histpage-{tag}-{n}-{uuid.uuid4().hex[:12]}" for n in range(len(created_ats))]
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
                [
                    {
                        "trace_id": trace_id,
                        "owner_id": owner_id,
                        "created_at": created_at,
                        "query_text": f"Question {trace_id}",
                    }
                    for trace_id, created_at in zip(trace_ids, created_ats, strict=True)
                ],
            )
    finally:
        engine.dispose()
    return trace_ids


def _expected_order(trace_ids: list[str]) -> list[str]:
    """The newest-first total order, read back from the stored columns."""
    engine = sa.create_engine(USER_DB_URL)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT trace_id FROM interactions WHERE trace_id = ANY(:ids) "
                    "ORDER BY created_at DESC, id DESC"
                ),
                {"ids": trace_ids},
            ).all()
    finally:
        engine.dispose()
    assert len(rows) == len(trace_ids), "populate-check: a seeded row never landed"
    return [row[0] for row in rows]


def _walk(owner_id: str, limit: int) -> tuple[list[list[str]], list[bool]]:
    """Follow `before` from the newest page to the end, the way the rail does."""
    from system_03_search_agent.feedback.history import list_history_page

    pages: list[list[str]] = []
    flags: list[bool] = []
    before: str | None = None
    for _ in range(100):
        page = list_history_page(owner_id=owner_id, limit=limit, before=before)
        pages.append([entry.trace_id for entry in page.entries])
        flags.append(page.has_more)
        # J-136S4-01: the cursor is the one the server names, the oldest
        # row this page read; it agrees with `has_more` by construction.
        assert (page.next_before is not None) == page.has_more
        if not page.has_more:
            return pages, flags
        assert page.next_before == page.entries[-1].trace_id
        before = page.next_before
    raise AssertionError("paging never ended: has_more stayed true for 100 pages")


def _distinct_times(count: int) -> list[datetime]:
    base = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
    return [base.replace(minute=n % 60, hour=12 + n // 60) for n in range(count)]


@pytest.mark.parametrize(
    ("row_count", "expected_sizes", "expected_flags"),
    [
        (20, [20], [False]),
        (21, [20, 1], [True, False]),
        (40, [20, 20], [True, False]),
        (41, [20, 20, 1], [True, True, False]),
        (45, [20, 20, 5], [True, True, False]),
    ],
)
def test_older_pages_reach_every_row_once_and_has_more_ends_at_the_last(
    row_count: int, expected_sizes: list[int], expected_flags: list[bool]
) -> None:
    from system_03_search_agent.feedback.history import DEFAULT_LIMIT

    owner = _unique_owner()
    trace_ids = _seed_many(owner, _distinct_times(row_count), tag=f"n{row_count}")
    expected = _expected_order(trace_ids)

    pages, flags = _walk(owner, DEFAULT_LIMIT)

    assert [len(page) for page in pages] == expected_sizes
    assert flags == expected_flags
    walked = [trace_id for page in pages for trace_id in page]
    assert walked == expected, "a row was lost, repeated or put out of order across pages"


def test_ties_on_one_timestamp_split_cleanly_across_page_boundaries() -> None:
    """45 rows on five timestamps, nine rows each, paged seven at a time:
    every page boundary but one falls inside a tie. Without the `id` half
    of the keyset, a boundary inside a tie loses or repeats rows."""
    owner = _unique_owner()
    base = datetime(2026, 10, 2, 9, 0, 0, tzinfo=UTC)
    created_ats = [base.replace(minute=n // 9) for n in range(45)]
    trace_ids = _seed_many(owner, created_ats, tag="tie")
    expected = _expected_order(trace_ids)

    pages, flags = _walk(owner, 7)

    assert [len(page) for page in pages] == [7, 7, 7, 7, 7, 7, 3]
    assert flags == [True] * 6 + [False]
    walked = [trace_id for page in pages for trace_id in page]
    assert len(set(walked)) == 45, "a row was repeated across pages"
    assert walked == expected


def test_another_owners_cursor_returns_nothing_of_theirs_or_ours() -> None:
    from system_03_search_agent.feedback.history import HistoryPage, list_history_page

    owner = _unique_owner()
    stranger = _unique_owner()
    # The stranger's rows sit at the same instants as the owner's, so any
    # leak of their (created_at, id) into the owner's page would show.
    times = _distinct_times(6)
    mine = _seed_many(owner, times, tag="mine")
    theirs = _seed_many(stranger, times, tag="theirs")

    # Control: each owner's own cursor does page through their own rows.
    own_page = list_history_page(owner_id=owner, limit=20, before=_expected_order(mine)[0])
    assert [e.trace_id for e in own_page.entries] == _expected_order(mine)[1:]
    their_page = list_history_page(
        owner_id=stranger, limit=20, before=_expected_order(theirs)[0]
    )
    assert [e.trace_id for e in their_page.entries] == _expected_order(theirs)[1:]

    for cursor in theirs:
        page = list_history_page(owner_id=owner, limit=20, before=cursor)
        assert page == HistoryPage(entries=[], next_before=None), (
            f"a stranger's cursor {cursor} returned {page}"
        )
    never_existed = list_history_page(
        owner_id=owner, limit=20, before=f"histpage-none-{uuid.uuid4().hex}"
    )
    assert never_existed == HistoryPage(entries=[], next_before=None)


def test_an_own_cursor_never_returns_a_strangers_interleaved_rows() -> None:
    from system_03_search_agent.feedback.history import list_history_page

    owner = _unique_owner()
    stranger = _unique_owner()
    times = _distinct_times(10)
    mine = _seed_many(owner, times[::2], tag="mine-il")
    theirs = _seed_many(stranger, times[1::2], tag="theirs-il")

    page = list_history_page(owner_id=owner, limit=20, before=_expected_order(mine)[0])

    returned = [entry.trace_id for entry in page.entries]
    assert returned == _expected_order(mine)[1:]
    assert not set(returned) & set(theirs)


def test_a_strangers_cursor_and_an_unknown_one_answer_identically_over_http() -> None:
    """Through `GET /v1/history` and the REAL owner filter: the two bodies
    are byte-identical, so the response never confirms that another
    person's search exists."""
    import asyncio

    from httpx import ASGITransport, AsyncClient

    from system_03_search_agent.adapters.web_sse.app import app
    from system_03_search_agent.auth.dependencies import Principal, get_caller

    owner = _unique_owner()
    stranger = _unique_owner()
    _seed_many(owner, _distinct_times(3), tag="http-mine")
    theirs = _seed_many(stranger, _distinct_times(3), tag="http-theirs")

    async def fetch(before: str) -> tuple[int, bytes, dict[str, str]]:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/history", params={"before": before})
        return response.status_code, response.content, dict(response.headers)

    app.dependency_overrides[get_caller] = lambda: Principal(
        owner_id=owner, user_id=None, kind="guest"
    )
    try:
        stranger_result = asyncio.run(fetch(theirs[0]))
        unknown_result = asyncio.run(fetch(f"histpage-none-{uuid.uuid4().hex}"))
    finally:
        app.dependency_overrides.pop(get_caller, None)

    assert stranger_result[0] == 200
    assert stranger_result == unknown_result
    assert b'"items":[]' in stranger_result[1]
    assert b'"has_more":false,"next_before":null' in stranger_result[1]


def test_a_page_of_only_withheld_rows_never_stops_the_walk_over_http() -> None:
    """A-136S4-01, A-136S4-02 and J-136S4-03 against the real database and
    the real per-row guard: 45 rows, the middle 20 with a `citations` value
    that is not a list, so the second page withholds every row. Following
    the server's `next_before` still reaches the five oldest, each
    withheld row is counted once, and the last page ends the walk."""
    import asyncio

    from httpx import ASGITransport, AsyncClient

    from system_03_search_agent.adapters.web_sse.app import app
    from system_03_search_agent.auth.dependencies import Principal, get_caller

    owner = _unique_owner()
    expected = _expected_order(_seed_many(owner, _distinct_times(45), tag="withheld"))
    engine = sa.create_engine(USER_DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "UPDATE interactions SET citations = '\"x\"'::jsonb "
                    "WHERE trace_id = ANY(:ids)"
                ),
                {"ids": expected[20:40]},
            )
    finally:
        engine.dispose()

    async def walk() -> list[dict]:
        bodies: list[dict] = []
        params: dict[str, str] = {}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(10):
                response = await client.get("/v1/history", params=params)
                assert response.status_code == 200, response.text
                bodies.append(response.json())
                if bodies[-1]["next_before"] is None:
                    return bodies
                params = {"before": bodies[-1]["next_before"]}
        raise AssertionError("paging never ended")

    app.dependency_overrides[get_caller] = lambda: Principal(
        owner_id=owner, user_id=None, kind="guest"
    )
    try:
        bodies = asyncio.run(walk())
    finally:
        app.dependency_overrides.pop(get_caller, None)

    assert [(b["count"], b["omitted_count"], b["has_more"]) for b in bodies] == [
        (20, 0, True),
        (0, 20, True),
        (5, 0, False),
    ]
    shown = [item["trace_id"] for body in bodies for item in body["items"]]
    assert shown == expected[:20] + expected[40:], "the oldest searches were never reached"


@pytest.mark.parametrize(
    "cursor",
    ["", "t" * 65, "abc\x00def", "line\nbreak", "del\x7f"],
    ids=["empty", "over-long", "nul", "newline", "delete"],
)
def test_a_malformed_cursor_is_refused_before_any_query(cursor: str) -> None:
    from system_03_search_agent.feedback.history import list_history_page

    with pytest.raises(ValueError):
        list_history_page(owner_id=_unique_owner(), before=cursor)


def test_a_cursor_exactly_at_the_bound_is_accepted() -> None:
    from system_03_search_agent.feedback.history import HistoryPage, list_history_page

    assert list_history_page(owner_id=_unique_owner(), before="t" * 64) == HistoryPage(
        entries=[], next_before=None
    )


def test_list_history_keeps_its_shape_for_the_mcp_tool() -> None:
    """The MCP tool calls `list_history(owner_id, limit)` and reads a list."""
    from system_03_search_agent.feedback.history import list_history

    owner = _unique_owner()
    trace_ids = _seed_many(owner, _distinct_times(3), tag="mcp")
    entries = list_history(owner_id=owner, limit=2)
    assert isinstance(entries, list)
    assert [entry.trace_id for entry in entries] == _expected_order(trace_ids)[:2]
