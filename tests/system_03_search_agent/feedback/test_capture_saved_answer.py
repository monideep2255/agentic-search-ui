"""The saved answer capture builds, and who it is built for (fix-plan item 10.2).

What a person gets, in their own words: they click a past search and the
answer they already got is there, with no second search charged to them.
This file grades the two halves of making that true on the write side.

## Why the fixture is a real recorded run and not a hand-written one

The whole ticket turned on one measurement: the finished answer is NOT a
text stream. A `table_header` token has `text: ""` and its visible content
in `cells`; a `table_row`'s visible content is `cells` while its `text` is
the grounded sentence behind it. So `"".join(token.text)`, which is what the
150-run measurement harness does and what "the answer text" sounds like it
means, turns a twenty-row table into twenty repetitive sentences.

A hand-written fixture would encode whatever shape the author believed in,
which is exactly the assumption this ticket was told not to make. The arms
below therefore run against
`testing/Developer/reports/2026-09-22_isolate_search/round2/
tokens_G-035.json`, 31 `token` events recorded from a real run on develop,
and the load-bearing arm asserts the join and the builder DISAGREE.

## Coverage: what this file exercises and what it omits

Exercised:

- Every token kind a real run emits, against a real run: heading,
  paragraph break, table header, table row, and prose claims.
- That a plain text join is NOT what this produces, measured on that run.
- The guest exclusion at the write, from both sides: an account run stores
  an answer, a guest run stores nothing, with the two runs identical in
  every other respect.
- That a refusal and a clarifying question store nothing.
- The bound: at it, over it.
- Hostile cell content: a pipe, a backslash, a newline.

NOT exercised:

- Whether the markdown renders the way the answer screen renders it. That
  is the frontend's contract and worker B2 owns it.
- Whether the row reaches the database. `feedback/writer.py` owns that and
  `tests/system_03_search_agent/data/test_migration_0010.py` proves the
  database's own refusal of a guest answer.
- `emphasis`. It is deliberately not rendered; see `answer_markdown_from`'s
  docstring for why bolding every emphasis term would make the saved answer
  MORE emphasised than the screen the person saw.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from system_03_search_agent.contracts.events import Event
from system_03_search_agent.contracts.query import Query
from system_03_search_agent.feedback.capture import (
    MAX_ANSWER_MARKDOWN,
    answer_markdown_from,
    assemble_interaction,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_RUN = (
    REPO_ROOT
    / "testing"
    / "Developer"
    / "reports"
    / "2026-09-22_isolate_search"
    / "round2"
    / "tokens_G-035.json"
)

_ACCOUNT = "user:11111111-1111-1111-1111-111111111111"
_GUEST = "guest:22222222-2222-2222-2222-222222222222"

_SEQ = iter(range(100_000))


def _event(event_type: str, payload: dict) -> Event:
    return Event(
        type=event_type,  # type: ignore[arg-type]
        version="v1",
        trace_id="trace-saved",
        seq=next(_SEQ),
        ts=datetime.now(UTC),
        payload=payload,
    )


def _token(text: str, *, kind=None, cells=None, marker_ids=None) -> Event:
    payload: dict = {"text": text, "marker_ids": marker_ids or []}
    if kind is not None:
        payload["kind"] = kind
    if cells is not None:
        payload["cells"] = cells
    return _event("token", payload)


def _citation(citation_id: str, display_index: int) -> Event:
    return _event(
        "citation",
        {
            "citation_id": citation_id,
            "display_index": display_index,
            "source": "NCBIGene",
            "source_id": "NCBIGene:672",
            "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
            "layer": "layer_1_graph",
            "field": "symbol",
            "claim_text": "BRCA1 is a gene.",
            "evidence_kind": "primary_assertion",
            "assertion_confidence": "asserted",
            "population_ancestry_context": None,
            "license": "public_domain_us_gov",
        },
    )


def _done(trust_outcome: str = "answer") -> Event:
    return _event(
        "done",
        {
            "total_cost_usd": 0.01,
            "total_tool_calls": 1,
            "elapsed_ms": 500,
            "trust_outcome": trust_outcome,
        },
    )


def _query(owner_id: str, *, audience_depth: str = "researcher") -> Query:
    return Query(
        text="What is BRCA1?",
        session_id="session-1",
        trace_id="trace-saved",
        owner_id=owner_id,
        audience_depth=audience_depth,  # type: ignore[arg-type]
    )


@pytest.fixture(scope="module")
def real_run_events() -> list[Event]:
    """The 31 `token` events and 20 `citation` events of a real recorded run."""
    raw = json.loads(REAL_RUN.read_text())
    events = [
        _event(entry["type"], entry["payload"])
        for entry in raw["events"]
        if entry["type"] in ("token", "citation")
    ]
    # POPULATE CHECK for every arm that uses this fixture. A missing or
    # renamed file, or a capture that stopped recording tokens, would leave
    # an empty list, and an empty list makes several assertions below pass
    # for the wrong reason.
    tokens = [e for e in events if e.type == "token"]
    assert len(tokens) >= 20, f"expected a real token stream, got {len(tokens)}"
    assert any(e.payload.get("kind") == "table_row" for e in tokens)
    assert any(e.payload.get("kind") == "table_header" for e in tokens)
    return events


# ---------------------------------------------------------------------------
# The measurement this whole ticket turned on.
# ---------------------------------------------------------------------------


def test_a_text_join_loses_the_table_and_the_builder_does_not(real_run_events) -> None:
    """The load-bearing arm. Measured, not argued.

    On this real run a plain `"".join(token.text)` yields 1448 characters and
    contains not one of the AMR gene names the person read, because every
    one of them lives in a `table_row`'s `cells`. If this arm ever goes
    green with the two agreeing, somebody has simplified the builder back
    into a join and the saved answer has quietly stopped matching the
    screen.
    """
    tokens = [e for e in real_run_events if e.type == "token"]
    joined = "".join(e.payload["text"] for e in tokens)
    built = answer_markdown_from(real_run_events)

    assert built is not None
    # POPULATE CHECK: both sides really produced content.
    assert len(joined) > 500
    assert len(built) > 500

    assert built != joined
    # The specific loss, named rather than left as an inequality: a real AMR
    # gene from a real `cells` value is in the built answer and in no part
    # of the text join.
    assert "blaCTX-M-15" not in joined
    assert "blaCTX-M-15" in built
    # And the table is a real markdown table, not prose.
    assert "| Isolate | AMR genes |" in built
    assert "| --- | --- |" in built


def test_the_real_run_renders_every_kind_it_emits(real_run_events) -> None:
    built = answer_markdown_from(real_run_events)
    assert built is not None

    # heading -> `## ...`
    assert "## Isolates and their AMR genes" in built
    # prose claim, with its own inline markers, kept verbatim
    assert "Found 20 pathogen detection isolate records for Escherichia coli" in built
    # a table row, with the marker on the first cell where the chip sits
    assert "| C236-11 [1] |" in built
    # POPULATE CHECK: the run really carried twenty rows, so a builder that
    # emitted only the header would not pass the arms above by accident.
    assert built.count("\n| ") >= 20


# ---------------------------------------------------------------------------
# Guests are excluded at the WRITE.
# ---------------------------------------------------------------------------


def test_an_account_run_stores_its_answer(real_run_events) -> None:
    row = assemble_interaction(_query(_ACCOUNT), [*real_run_events, _done()])
    assert row is not None
    assert row.answer_markdown is not None
    # POPULATE CHECK: it stored the real answer, not an empty string that
    # `is not None` would also accept.
    assert "blaCTX-M-15" in row.answer_markdown
    assert row.audience_depth == "researcher"


def test_a_guest_run_stores_nothing(real_run_events) -> None:
    """The same events, the same question, the only difference being who asked.

    This is the product owner's decision of 2026-09-22 proven from the two
    sides that make it a statement rather than a coincidence: the arm above
    shows the answer IS stored for an account, so a `None` here is the guest
    rule working and not the builder failing on this fixture.
    """
    row = assemble_interaction(_query(_GUEST), [*real_run_events, _done()])
    assert row is not None
    # POPULATE CHECK: the row itself was assembled, so the guest's run is
    # still counted. Excluding the answer must never cost a guest their row.
    assert row.query_text == "What is BRCA1?"
    assert row.owner_id == _GUEST
    assert row.citations, "the guest's citations are still captured"

    assert row.answer_markdown is None
    assert row.audience_depth is None


def test_the_row_model_refuses_a_guest_answer_outright() -> None:
    """Belt and braces: even a caller that bypassed capture cannot build one.

    `assemble_interaction` never produces this pairing, so this arm
    constructs it directly. Without the model validator this raises nothing
    and the write path's rule would hold only for as long as nobody writes a
    second assembler.
    """
    from system_03_search_agent.feedback.contracts import InteractionRow

    kwargs = {
        "trace_id": "t-1",
        "owner_id": _ACCOUNT,
        "query_text": "What is BRCA1?",
        "query_class": "lookup",
        "route": {},
        "trust_signal": "answer",
        "rubric_outcome": "pass",
        "answer_markdown": "BRCA1 is a gene [1].",
        "audience_depth": "researcher",
    }
    # POPULATE CHECK: the very same kwargs build fine for an account, so the
    # rejection below is about the owner and not about a malformed row.
    assert InteractionRow(**kwargs).answer_markdown == "BRCA1 is a gene [1]."

    with pytest.raises(ValueError, match="signed-in accounts only"):
        InteractionRow(**{**kwargs, "owner_id": _GUEST})


def test_a_saved_answer_must_record_its_depth() -> None:
    from system_03_search_agent.feedback.contracts import InteractionRow

    kwargs = {
        "trace_id": "t-2",
        "owner_id": _ACCOUNT,
        "query_text": "What is BRCA1?",
        "query_class": "lookup",
        "route": {},
        "trust_signal": "answer",
        "rubric_outcome": "pass",
        "answer_markdown": "BRCA1 is a gene [1].",
        "audience_depth": "plain_language",
    }
    assert InteractionRow(**kwargs).audience_depth == "plain_language"

    with pytest.raises(ValueError, match="audience_depth"):
        InteractionRow(**{**kwargs, "audience_depth": None})
    with pytest.raises(ValueError, match="audience_depth"):
        InteractionRow(**{**kwargs, "answer_markdown": None})


# ---------------------------------------------------------------------------
# What is deliberately not saved.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("outcome", ["refuse", "ask"])
def test_a_refusal_and_a_clarifying_question_store_nothing(outcome: str) -> None:
    """Narrow on purpose. The answer screen renders these two outcomes from
    other events entirely, so saving their tokens would show the person
    something different from what they saw."""
    events = [
        _token("I could not find evidence for this. "),
        _done(outcome),
    ]
    row = assemble_interaction(_query(_ACCOUNT), events)
    assert row is not None
    # POPULATE CHECK: the identical events under an `answer` outcome DO
    # store, so the two `None`s below are about the outcome rule.
    answered = assemble_interaction(_query(_ACCOUNT), [events[0], _done("answer")])
    assert answered is not None and answered.answer_markdown is not None

    assert row.answer_markdown is None
    assert row.audience_depth is None


def test_a_run_with_no_tokens_stores_nothing() -> None:
    row = assemble_interaction(_query(_ACCOUNT), [_done()])
    assert row is not None
    assert row.trace_id == "trace-saved"  # POPULATE CHECK: a real row exists
    assert row.answer_markdown is None


# ---------------------------------------------------------------------------
# The bound.
# ---------------------------------------------------------------------------


def test_an_answer_over_the_bound_is_dropped_whole_never_truncated() -> None:
    """A saved answer that differs from the one the person saw is worse than
    no saved answer, so the over-bound case stores nothing and the person is
    offered Run again."""
    at_bound = [_token("x" * 900) for _ in range(MAX_ANSWER_MARKDOWN // 900)]
    built = answer_markdown_from(at_bound)
    # POPULATE CHECK: the under-bound case really built something large.
    assert built is not None and len(built) > MAX_ANSWER_MARKDOWN // 2

    over = [*at_bound, _token("x" * 900), _token("x" * 900)]
    assert len("".join("x" * 900 for _ in over)) > MAX_ANSWER_MARKDOWN
    assert answer_markdown_from(over) is None


# ---------------------------------------------------------------------------
# Hostile cell content.
# ---------------------------------------------------------------------------


def test_a_pipe_in_a_cell_cannot_reshape_the_table() -> None:
    events = [
        _token("", kind="table_header", cells=["Gene", "Note"]),
        _token("row", kind="table_row", cells=["BRCA1", "a | b"]),
        _done(),
    ]
    built = answer_markdown_from(events)
    assert built is not None
    # POPULATE CHECK: the row rendered at all.
    assert "BRCA1" in built
    row_line = next(line for line in built.splitlines() if line.startswith("| BRCA1"))
    # Two columns, so three pipes at cell boundaries and one escaped.
    assert r"a \| b" in row_line
    assert row_line.count("|") - row_line.count(r"\|") == 3


def test_a_newline_in_a_cell_cannot_end_the_row() -> None:
    events = [
        _token("", kind="table_header", cells=["Gene", "Note"]),
        _token("row", kind="table_row", cells=["BRCA1", "first\nsecond"]),
        _done(),
    ]
    built = answer_markdown_from(events)
    assert built is not None
    row_line = next(line for line in built.splitlines() if line.startswith("| BRCA1"))
    assert "first second" in row_line
    # POPULATE CHECK: both halves survived, so the newline was flattened
    # rather than the cell truncated at it.
    assert "second" in row_line


def test_markers_come_from_the_citation_events_not_the_token_text() -> None:
    """A `table_row`'s visible content carries no marker at all, so the
    number beside it has to be looked up from the run's own citations."""
    events = [
        _citation("c-a", 7),
        _token("", kind="table_header", cells=["Gene"]),
        _token("Gene name: BRCA1 [7]. ", kind="table_row", cells=["BRCA1"], marker_ids=["c-a"]),
        _done(),
    ]
    built = answer_markdown_from(events)
    assert built is not None
    assert "| BRCA1 [7] |" in built

    # POPULATE CHECK plus the negative: with no citation event for that id,
    # no number is invented.
    no_citation = answer_markdown_from(
        [e for e in events if e.type != "citation"]
    )
    assert no_citation is not None
    assert "| BRCA1 |" in no_citation
    assert "[7]" not in no_citation


def test_a_list_item_renders_its_cell_with_its_marker() -> None:
    events = [
        _citation("c-b", 3),
        _token("Gene name: TP53 [3]. ", kind="list_item", cells=["TP53"], marker_ids=["c-b"]),
        _done(),
    ]
    built = answer_markdown_from(events)
    assert built == "- TP53[3]"


def test_a_table_row_with_no_header_becomes_a_list_item_not_an_invented_table() -> None:
    """Not a shape any measured run emits. It renders as a list rather than
    getting column labels nobody produced."""
    events = [
        _token("row", kind="table_row", cells=["BRCA1", "tumour suppressor"]),
        _done(),
    ]
    built = answer_markdown_from(events)
    assert built == "- BRCA1: tumour suppressor"
    assert "---" not in built


def test_the_trust_line_is_stored_beside_the_answer(real_run_events) -> None:
    """Stored, never served. The pinned wire contract has no field for it.

    Measured across 150 live runs: all 35 that ended `answer` or `flag`
    carried a trust line, so an answer saved without it would permanently
    lack the sentence that told its reader how much to trust it. See
    alembic 0010's docstring and tonight's findings file.
    """
    done = _event(
        "done",
        {
            "total_cost_usd": 0.01,
            "total_tool_calls": 1,
            "elapsed_ms": 500,
            "trust_outcome": "answer",
            "trust_line": "Sources disagree on at least one claim",
        },
    )
    row = assemble_interaction(_query(_ACCOUNT), [*real_run_events, done])
    assert row is not None
    # POPULATE CHECK: the answer itself stored, so the line below is about
    # the trust line rather than about a row that saved nothing.
    assert row.answer_markdown is not None
    assert row.answer_trust_line == "Sources disagree on at least one claim"

    # A guest gets neither, and a run whose `done` carried no line stores
    # None rather than an invented sentence.
    guest_row = assemble_interaction(_query(_GUEST), [*real_run_events, done])
    assert guest_row is not None
    assert guest_row.answer_trust_line is None

    no_line = assemble_interaction(_query(_ACCOUNT), [*real_run_events, _done()])
    assert no_line is not None
    assert no_line.answer_markdown is not None
    assert no_line.answer_trust_line is None
