"""Unit tests for `feedback.capture.assemble_interaction` (T-4.6-03).

These are offline, in-process tests: they build `Event` objects directly
(the same shapes `run()` accumulates in `GraphState`) and call
`assemble_interaction` with no database, no model, and no network. The
premise gate
(`tests/system_03_search_agent/core/test_feedback_capture_premise.py`)
covers the end-to-end property that a real query causes a real row to
exist; these tests cover the assembler's own field-by-field logic, which is
faster to run and easier to pin one behaviour at a time against.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core.session_memory import (
    CallerIdentityRequired,
    session_row_key,
)
from system_03_search_agent.feedback.capture import assemble_interaction

_SEQ = iter(range(10_000))


def _event(event_type: str, payload: dict[str, object], *, trace_id: str = "trace-1"):
    from system_03_search_agent.contracts.events import Event

    return Event(
        type=event_type,  # type: ignore[arg-type]
        version="v1",
        trace_id=trace_id,
        seq=next(_SEQ),
        ts=datetime.now(UTC),
        payload=payload,
    )


def _guard_event(*, trace_id: str = "trace-1", passed: bool = True):
    return _event(
        "guard",
        {"passed": passed, "category": "ok" if passed else "injection", "reason": None},
        trace_id=trace_id,
    )


def _think_event(
    *, trace_id: str = "trace-1", query_class: str = "single_hop", entities=None
):
    return _event(
        "think",
        {
            "narrative": "thinking",
            "query_class": query_class,
            "resolved_entities": entities or [],
            "clarifying_question": None,
        },
        trace_id=trace_id,
    )


def _plan_event(*, trace_id: str = "trace-1", tool_calls=None, entities=None):
    return _event(
        "plan",
        {
            "narrative": "planning",
            "tool_calls": tool_calls or [],
            "resolved_entities": entities or [],
        },
        trace_id=trace_id,
    )


def _cost_event(*, trace_id: str = "trace-1", model_tier: str = "plan"):
    return _event(
        "cost",
        {
            "query_cost_usd": 0.001,
            "query_cap_usd": 1.0,
            "cap_fraction": 0.001,
            "model_tier": model_tier,
        },
        trace_id=trace_id,
    )


def _citation_payload(*, citation_id: str = "call-1-1", claim_text: str = "BRCA1 is a gene."):
    return {
        "citation_id": citation_id,
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


def _citation_event(*, trace_id: str = "trace-1", **overrides):
    return _event("citation", _citation_payload(**overrides), trace_id=trace_id)


def _done_event(
    *,
    trace_id: str = "trace-1",
    trust_outcome: str = "answer",
    total_cost_usd: float = 0.01,
    elapsed_ms: int = 500,
):
    return _event(
        "done",
        {
            "total_cost_usd": total_cost_usd,
            "total_tool_calls": 1,
            "elapsed_ms": elapsed_ms,
            "trust_outcome": trust_outcome,
        },
        trace_id=trace_id,
    )


def _query(*, owner_id: str | None = "guest:aaaaaaaa-0000-0000-0000-000000000000",
           session_id: str = "session-1", trace_id: str = "caller-chosen") -> Query:
    return Query(
        text="What is BRCA1?",
        session_id=session_id,
        trace_id=trace_id,
        owner_id=owner_id,
    )


# ---------------------------------------------------------------------------
# No events at all: the one case the assembler refuses outright.
# ---------------------------------------------------------------------------


def test_no_done_event_returns_none() -> None:
    """With nothing to attribute a row to, the assembler returns `None`.

    Mutation run: changed `if done_event is None: return None` to
    `if False: return None`. The call below went red (raised
    `AttributeError` from `done_event.trace_id` on a `None` instead of
    returning cleanly), confirming the guard is what prevents that crash.
    Reverted after confirming the failure.
    """
    assert assemble_interaction(_query(), []) is None


# ---------------------------------------------------------------------------
# The Guardrail-refusal shape: no plan, no think, no citation events.
# ---------------------------------------------------------------------------


def test_a_refusal_shaped_run_still_assembles_a_valid_row() -> None:
    """No plan, no think, no citation events: the row is still valid.

    This is the shape T-4.6-03's own acceptance criteria names directly:
    "A run that produced no citations, no plan and no think events still
    assembles a valid row, since a Guardrail refusal produces exactly
    that."

    Mutation run: changed `_query_class_from`'s fallback `return "lookup"`
    to `return "multi_hop"`. The `query_class` assertion below went red
    (`row.query_class` read `"multi_hop"` instead of `"lookup"`, the
    stub's own value). Reverted after confirming the failure.
    """
    events = [
        _guard_event(passed=False),
        _done_event(trust_outcome="refuse", total_cost_usd=0.0, elapsed_ms=20),
    ]
    row = assemble_interaction(_query(), events)
    assert row is not None
    assert row.query_class == "lookup"
    assert row.route == {"layers": [], "tools": [], "model_tiers": []}
    assert row.citations == []
    assert row.normalized_entities == []
    assert row.coverage_tags == []
    assert row.trust_signal == "refuse"
    assert row.rubric_outcome == "abstain"
    assert row.rubric_score is None


# ---------------------------------------------------------------------------
# trace_id: from the event envelope, never from the caller-supplied query.
# ---------------------------------------------------------------------------


def test_trace_id_comes_from_the_event_envelope_not_the_query() -> None:
    """The row's `trace_id` is the event stream's, even when it differs
    from what the caller put on the `Query`.

    Mutation run: changed `trace_id=done_event.trace_id` to
    `trace_id=query.trace_id` in `assemble_interaction`. The assertion
    below went red (`row.trace_id` read `"caller-chosen"`, the query's
    value, instead of `"server-minted"`, the event envelope's value).
    Reverted after confirming the failure.
    """
    events = [_done_event(trace_id="server-minted", trust_outcome="refuse")]
    row = assemble_interaction(_query(trace_id="caller-chosen"), events)
    assert row is not None
    assert row.trace_id == "server-minted"


# ---------------------------------------------------------------------------
# query_class: the last think event, or the stub's own fallback.
# ---------------------------------------------------------------------------


def test_query_class_reads_the_last_think_event() -> None:
    """Two think events: the later one's `query_class` wins.

    Mutation run: changed `_last_of_type`'s `for event in reversed(events)`
    to `for event in events` (first match wins instead of last). The
    assertion below went red (`row.query_class` read `"lookup"`, the first
    event's value, instead of `"multi_hop"`, the second). Reverted after
    confirming the failure.
    """
    events = [
        _think_event(query_class="lookup"),
        _think_event(query_class="multi_hop"),
        _done_event(),
    ]
    row = assemble_interaction(_query(), events)
    assert row is not None
    assert row.query_class == "multi_hop"


# ---------------------------------------------------------------------------
# route: layers, tools, and model tiers, deduplicated and sorted.
# ---------------------------------------------------------------------------


def test_route_deduplicates_and_sorts_layers_tools_and_tiers() -> None:
    """Duplicate tool calls and cost events collapse to a sorted, deduped set.

    Mutation run: changed `_route_from`'s `layers.add(call.layer)` and
    `tools.add(call.tool)` to append to a `list` instead of a `set`. The
    assertion below went red (`route["layers"]` and `route["tools"]` each
    carried the duplicate entry twice instead of once). Reverted after
    confirming the failure.
    """
    tool_calls = [
        {"tool": "cypher_query", "call_id": "c1", "layer": "layer_1_graph"},
        {"tool": "cypher_query", "call_id": "c2", "layer": "layer_1_graph"},
        {"tool": "ncbi_efetch", "call_id": "c3", "layer": "layer_2_api"},
    ]
    events = [
        _plan_event(tool_calls=tool_calls),
        _cost_event(model_tier="plan"),
        _cost_event(model_tier="synth"),
        _cost_event(model_tier="plan"),
        _done_event(),
    ]
    row = assemble_interaction(_query(), events)
    assert row is not None
    assert row.route == {
        "layers": ["layer_1_graph", "layer_2_api"],
        "tools": ["cypher_query", "ncbi_efetch"],
        "model_tiers": ["plan", "synth"],
    }


# ---------------------------------------------------------------------------
# normalized_entities: translated shape, deduplicated by curie.
# ---------------------------------------------------------------------------


def test_normalized_entities_deduplicates_by_curie_and_translates_shape() -> None:
    """Two plan events, one repeated curie: one entry, in the decision-G shape.

    Mutation run: changed `seen_curies.add(entity.curie)` to a no-op (never
    recording a curie as seen). The assertion below went red (two entries
    for `NCBIGene:672` appeared instead of one). Reverted after confirming
    the failure.
    """
    events = [
        _plan_event(
            entities=[{"text": "BRCA1", "curie": "NCBIGene:672", "confidence": 0.9}]
        ),
        _plan_event(
            entities=[{"text": "BRCA1 gene", "curie": "NCBIGene:672", "confidence": 0.95}]
        ),
        _done_event(),
    ]
    row = assemble_interaction(_query(), events)
    assert row is not None
    assert row.normalized_entities == [
        {
            "surface_form": "BRCA1",
            "curie": "NCBIGene:672",
            "entity_type": "Unknown",
            "resolution_confidence": 0.9,
        }
    ]


# ---------------------------------------------------------------------------
# citations: dumped as-is, not rebuilt.
# ---------------------------------------------------------------------------


def test_citations_are_dumped_verbatim() -> None:
    """The row's `citations` are the exact payload dicts the events carried.

    Mutation run: changed `citations = [event.payload for event in events
    if event.type == "citation"]` to always append an empty dict `{}`
    instead of `event.payload`. The assertion below went red (`row.
    citations[0]` was `{}` instead of the real payload). Reverted after
    confirming the failure.
    """
    payload = _citation_payload(citation_id="call-1-1", claim_text="a real claim")
    events = [_citation_event(citation_id="call-1-1", claim_text="a real claim"), _done_event()]
    row = assemble_interaction(_query(), events)
    assert row is not None
    assert row.citations == [payload]


def test_citations_are_capped_at_fifty() -> None:
    """More than fifty citation events truncate rather than overflow the column.

    Mutation run: changed `_MAX_CITATIONS` from `50` to `1000`. The call
    below went red (`InteractionRow` construction raised a Pydantic
    `ValidationError`, "citations: List should have at most 50 items after
    validation, not 60", since nothing truncated the list before it reached
    the model's own cap). Reverted after confirming the failure.
    """
    events = [
        _citation_event(citation_id=f"call-1-{i}") for i in range(60)
    ] + [_done_event()]
    row = assemble_interaction(_query(), events)
    assert row is not None
    assert len(row.citations) == 50


# ---------------------------------------------------------------------------
# rubric_outcome and the one deterministic hard-fail check.
# ---------------------------------------------------------------------------


def test_an_answer_with_no_citations_is_a_hard_fail() -> None:
    """`answer` with zero citations is an uncited claim: `rubric_outcome` is `fail`.

    Mutation run: changed `_hard_fails_for`'s condition from
    `if trust_signal in ("answer", "flag") and not citations:` to
    `if False:`. The assertion below went red (`row.rubric_outcome` read
    `"pass"` instead of `"fail"`). Reverted after confirming the failure.
    """
    row = assemble_interaction(_query(), [_done_event(trust_outcome="answer")])
    assert row is not None
    assert row.rubric_outcome == "fail"


def test_an_ask_with_no_citations_is_not_a_hard_fail() -> None:
    """`ask` made no claim yet, so having no citation is expected, not a fail.

    Mutation run: widened `_hard_fails_for`'s condition from
    `trust_signal in ("answer", "flag")` to also include `"ask"`. The
    assertion below went red (`row.rubric_outcome` read `"fail"` instead of
    `"pass"`). Reverted after confirming the failure.
    """
    row = assemble_interaction(_query(), [_done_event(trust_outcome="ask")])
    assert row is not None
    assert row.rubric_outcome == "pass"


def test_an_answer_with_a_citation_is_not_a_hard_fail() -> None:
    """Mutation run: removed the `and not citations` half of
    `_hard_fails_for`'s condition, so `answer`/`flag` hard-failed
    unconditionally. The assertion below went red (`row.rubric_outcome`
    read `"fail"` instead of `"pass"` even though a citation was present).
    Reverted after confirming the failure.
    """
    events = [_citation_event(), _done_event(trust_outcome="answer")]
    row = assemble_interaction(_query(), events)
    assert row is not None
    assert row.rubric_outcome == "pass"


def test_rubric_score_is_always_none() -> None:
    """Section 15 scopes `rubric_score` to offline golden-dataset replay only.

    Mutation run: changed the `InteractionRow(...)` construction's
    `rubric_score=None` to `rubric_score=0`. The assertion below went red
    (`row.rubric_score` was `0` instead of `None`). Reverted after
    confirming the failure.
    """
    row = assemble_interaction(_query(), [_done_event()])
    assert row is not None
    assert row.rubric_score is None


# ---------------------------------------------------------------------------
# Ownership: session_id and user_id, and the required-identity guard.
# ---------------------------------------------------------------------------


def test_session_id_is_session_row_key_and_user_id_is_none_for_a_guest() -> None:
    """A guest's row uses the owner-scoped session key and a NULL user_id.

    Mutation run: changed `session_row_key(query.session_id,
    owner_id=owner_id)` to `session_row_key(query.session_id,
    owner_id="some-other-owner")`. The assertion below went red (`row.
    session_id` no longer matched the value computed with the real owner
    id). Reverted after confirming the failure.
    """
    owner_id = "guest:11111111-1111-1111-1111-111111111111"
    query = _query(owner_id=owner_id, session_id="shared-session")
    row = assemble_interaction(query, [_done_event()])
    assert row is not None
    assert row.session_id == session_row_key("shared-session", owner_id=owner_id)
    assert row.user_id is None


def test_user_id_is_the_account_uuid_for_a_registered_owner() -> None:
    """Mutation run: changed `user_id = _account_uuid(owner_id)` to
    `user_id = None`. The assertion below went red (`row.user_id` was
    `None` instead of the registered account's UUID). Reverted after
    confirming the failure.
    """
    account_id = uuid.uuid4()
    owner_id = f"user:{account_id}"
    query = _query(owner_id=owner_id, session_id="acct-session")
    row = assemble_interaction(query, [_done_event()])
    assert row is not None
    assert row.user_id == account_id
    assert row.session_id == session_row_key("acct-session", owner_id=owner_id)


def test_two_guests_sharing_a_session_id_get_different_session_keys() -> None:
    """`session_id` alone is not the key; it is scoped by owner (F-4.5-A-02's shape).

    Mutation run: changed `session_row_key(query.session_id,
    owner_id=owner_id)` to `session_row_key(query.session_id,
    owner_id="fixed-owner")`, collapsing the owner scope. The assertion
    below went red (both guests' `session_id` values were identical
    instead of distinct). Reverted after confirming the failure.
    """
    first = _query(owner_id="guest:aaaaaaaa-1111-1111-1111-111111111111",
                    session_id="shared")
    second = _query(owner_id="guest:bbbbbbbb-2222-2222-2222-222222222222",
                     session_id="shared")
    row_first = assemble_interaction(first, [_done_event()])
    row_second = assemble_interaction(second, [_done_event()])
    assert row_first is not None and row_second is not None
    assert row_first.session_id != row_second.session_id


def test_owner_id_is_passed_through_from_query_unchanged() -> None:
    """F-4.6-01: the row carries the exact owner_id capture used for session_id.

    Mutation run: changed the `InteractionRow(...)` construction's
    `owner_id=owner_id` to `owner_id=owner_id.upper()` (a stand-in for any
    re-derivation or re-parsing). The assertion below went red
    (`row.owner_id` read the upper-cased value instead of the exact string
    `query.owner_id` carried). Reverted after confirming the failure.
    """
    owner_id = f"guest:{uuid.uuid4()}"
    query = _query(owner_id=owner_id, session_id="owner-id-probe")
    row = assemble_interaction(query, [_done_event()])
    assert row is not None
    assert row.owner_id == owner_id


def test_missing_owner_id_raises_caller_identity_required() -> None:
    """A query with no caller identity is a real error state, never a silent default.

    Mutation run: wrapped the `session_row_key` call in a `try/except
    CallerIdentityRequired: session_id = None`. The assertion below went
    red (no exception was raised; `assemble_interaction` returned a row
    with `session_id=None` instead of propagating the error). Reverted
    after confirming the failure.
    """
    query = _query(owner_id=None)
    with pytest.raises(CallerIdentityRequired):
        assemble_interaction(query, [_done_event()])


# ---------------------------------------------------------------------------
# cost_usd and latency_ms: read straight off the done event.
# ---------------------------------------------------------------------------


def test_cost_and_latency_are_read_from_the_done_event() -> None:
    """Mutation run: hardcoded the `InteractionRow(...)` construction's
    `cost_usd=0.0` and `latency_ms=0` instead of reading `done_payload`.
    The assertion below went red (`row.cost_usd` was `0.0` instead of
    `0.0234`). Reverted after confirming the failure.
    """
    row = assemble_interaction(
        _query(), [_done_event(total_cost_usd=0.0234, elapsed_ms=1234)]
    )
    assert row is not None
    assert row.cost_usd == 0.0234
    assert row.latency_ms == 1234


# ---------------------------------------------------------------------------
# No secret ever reaches the row: a structural check on this module's source.
# ---------------------------------------------------------------------------


def test_capture_module_never_reads_the_environment() -> None:
    """`assemble_interaction` is a pure function: no `os.environ`, no `getenv`.

    Mutation run: added `import os` at module scope and, inside
    `_route_from`, `route["leaked"] = os.environ.get("OPENROUTER_API_KEY",
    "")`. The assertions below went red (the source text then contained
    both `"os.environ"` and an `import os` line). Reverted after confirming
    the failure. This is the unit-level companion to the premise gate's
    P10, which plants a secret in the environment and greps every column
    of a real, live-written row for it; this test instead proves the
    module has no code path that could reach the environment at all.
    """
    import inspect

    import system_03_search_agent.feedback.capture as capture_module

    source = inspect.getsource(capture_module)
    assert "os.environ" not in source
    assert "getenv" not in source
    assert "import os" not in source
