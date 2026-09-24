"""UI fix plan item 12.3 (2026-09-23): a bare one-to-three-word question
that opens a conversation gets a clarifying question instead of a silent
guess, with four full questions the reader can pick with one click.

The product owner's approved design, in their own words: "If clarify
needed -> yes approved". A question of one to three words, with no question
word, that OPENS a conversation (a follow-up inside a conversation is never
asked back, since memory already supplies its subject:
`docs/build/Search_and_conversation_behaviour.md`) is too ambiguous to
search silently: "reflux disease", "GERD", "BRCA1", "MeSH" and "Marfan" all
ask; "Any trials for GERD?" (four words), "What is GERD?" (a question word)
and any short follow-up with an earlier turn behind it all proceed.

Exercised:
    `_bare_topic_clarification` directly: every must-ask shape from the
    fix-plan row, every word in the question-word list exempting a
    question, the four-word cutoff, punctuation stripped before counting
    ("GERD?" still asks), and the exact question and four options built.
    Through the real five-node graph with the model stubbed (the same
    harness `test_clarification.py` uses): each must-ask example publishes
    the clarification with its four options and runs NO tool call; each
    must-not example (a question word, or four words) proceeds to a real
    search; the identical bare-topic text proceeds when an earlier turn's
    session memory is present, since that is what "opens a conversation"
    means in practice.

NOT exercised: the web UI's rendering of the four options as chips
(`frontend/src/components/answer/FollowUp.chips.test.tsx` owns that), and
live models.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest

from system_03_search_agent.contracts.query import (
    Query,
    RequestContext,
    ResolvedEntity,
    SessionMemorySummary,
)
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools.cypher_schemas import CypherQueryOutput, CypherQueryRow
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput
from tests.system_03_search_agent.model_stub import (
    COMPLIANT_GUARD_CLASSIFICATION,
    compliant_synth_narrative,
    compliant_think_classification,
    fake_response,
)

# ---------------------------------------------------------------------------
# Pure unit tests: `_bare_topic_clarification` needs no graph, no model, and
# no event loop, so these run with none of the fixtures below.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["reflux disease", "GERD", "BRCA1", "MeSH", "Marfan"],
)
def test_every_must_ask_example_from_the_fix_plan_row_asks(text: str) -> None:
    result = graph_module._bare_topic_clarification(text)
    assert result is not None, text
    assert result.question == f"What would you like to know about {text}?"
    assert len(result.options) == 4
    assert result.options == (
        f"What is {text} and what are its symptoms?",
        f"Which genes or variants are linked to {text}?",
        f"Are there clinical trials for {text}?",
        f"What does recent research say about {text}?",
    )


def test_a_question_mark_alone_does_not_exempt() -> None:
    """"A question mark alone does not exempt: `GERD?` is still ambiguous."
    The trailing punctuation is stripped from the token before counting, so
    this is still one bare word, and the echoed topic drops the mark too."""
    result = graph_module._bare_topic_clarification("GERD?")
    assert result is not None
    assert result.question == "What would you like to know about GERD?"


def test_four_words_does_not_ask() -> None:
    """"Any trials for GERD?" (four words) must proceed, per the fix-plan
    row: a fourth word states enough of a request to search."""
    assert graph_module._bare_topic_clarification("Any trials for GERD?") is None


def test_three_words_with_no_question_word_still_asks() -> None:
    assert graph_module._bare_topic_clarification("post surgical infection") is not None


@pytest.mark.parametrize("word", sorted(graph_module._BARE_TOPIC_QUESTION_WORDS))
def test_every_question_word_exempts_a_question(word: str) -> None:
    """Every word in the fix-plan row's list ("what, which, how, why, who,
    when, where, is, are, does, do, can, should, list, show, tell, find,
    any"), checked one at a time so a future edit that drops one is caught
    by name rather than by a single combined assertion."""
    assert graph_module._bare_topic_clarification(f"{word} GERD") is None
    # Case-insensitive: the reply text preserves the caller's own casing
    # elsewhere, but the exemption check itself must not be fooled by it.
    assert graph_module._bare_topic_clarification(f"{word.upper()} GERD") is None


def test_what_is_gerd_does_not_ask() -> None:
    """The fix-plan row's own worked example of a question word exempting a
    question, at its literal three-word length."""
    assert graph_module._bare_topic_clarification("What is GERD?") is None


def test_empty_and_whitespace_do_not_ask() -> None:
    assert graph_module._bare_topic_clarification("") is None
    assert graph_module._bare_topic_clarification("   ") is None


# ---------------------------------------------------------------------------
# Integration tests through the real five-node graph, model calls stubbed.
# Mirrors `test_clarification.py`'s own harness exactly, since this is the
# same class of deterministic, pre-search decision.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
    monkeypatch.setenv("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", lambda *a, **k: None)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _stubbed_models_and_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.guardrail.classifier import GUARD_SYSTEM_INSTRUCTION
    from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION

    async def _dispatch(*args: object, **kwargs: object) -> Any:
        messages = list(kwargs.get("messages") or [])
        joined = "\n".join(str(message.get("content") or "") for message in messages)
        if GUARD_SYSTEM_INSTRUCTION in joined:
            return fake_response(COMPLIANT_GUARD_CLASSIFICATION)
        if graph_module._THINK_SYSTEM_INSTRUCTION in joined:
            return fake_response(compliant_think_classification(messages))
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            return fake_response(compliant_synth_narrative(messages))
        return fake_response("MATCH (g:Gene) RETURN g LIMIT 1")

    monkeypatch.setattr(harness_module.litellm, "acompletion", _dispatch)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )

    async def _resolve(symbol: str, *, taxon: str = "human") -> str | None:
        return {"BRCA1": "NCBIGene:672"}.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _resolve)

    async def _cypher(harness: object, cypher_input: object) -> CypherQueryOutput:
        return CypherQueryOutput(
            status="ok",
            row_count=1,
            total_available=1,
            truncated=False,
            rows=[
                CypherQueryRow(
                    node_or_edge_type="Gene",
                    curie="NCBIGene:672",
                    fields={"name": "BRCA1 DNA repair associated"},
                    source_url="https://www.ncbi.nlm.nih.gov/gene/672",
                    graph_snapshot_version="v1",
                )
            ],
            error=None,
        )

    monkeypatch.setattr(graph_module, "cypher_query", _cypher)

    async def _efetch(tool_input: object, **kwargs: object) -> NcbiEfetchOutput:
        return NcbiEfetchOutput(
            status="empty",
            action="dataset_report",
            records=[],
            record_count=0,
            total_available=None,
            truncated=False,
            error=None,
        )

    monkeypatch.setattr(graph_module, "ncbi_efetch", _efetch)


async def _run(text: str, memory: SessionMemorySummary | None = None) -> list[Any]:
    trace_id = f"t-{uuid.uuid4().hex[:12]}"
    query = Query(text=text, session_id="bare-topic-test", trace_id=trace_id)
    state = {
        "query": query,
        "context": RequestContext(surface="rest_sse", session_memory=memory),
        "harness": harness_module.Harness(trace_id),
        "seq": 0,
        "start_monotonic": time.monotonic(),
        "events": [],
    }
    result = await graph_module.compiled_graph.ainvoke(state)
    return list(result.get("events", []))


def _payload(events: list[Any], event_type: str) -> dict[str, Any] | None:
    for event in events:
        if event.type == event_type:
            return event.payload
    return None


def _memory_with_tp53() -> SessionMemorySummary:
    from datetime import UTC, datetime

    return SessionMemorySummary(
        session_id="bare-topic-test",
        last_updated=datetime.now(UTC),
        resolved_entities=[
            ResolvedEntity(mention="TP53", curie="NCBIGene:7157", entity_type="Gene")
        ],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    ["reflux disease", "GERD", "BRCA1", "MeSH", "Marfan"],
)
async def test_a_bare_topic_that_opens_a_conversation_asks_and_runs_no_tool(
    text: str,
) -> None:
    """MUTATION PROOF: removing the `_bare_topic_clarification` branch in
    `think_node` turns the think, plan and token arms red; removing Plan's
    existing `clarification_needed` early return turns the tool_start arm
    red; removing Write's existing `clarification_needed` branch turns the
    token and done arms red. All three are item 7.5's own pre-existing
    machinery, reused rather than reinvented, so this arm also proves that
    reuse actually wires end to end for this new call site.
    """
    events = await _run(text)
    types = [event.type for event in events]
    assert "done" in types, types

    think = _payload(events, "think")
    assert think is not None
    expected_question = f"What would you like to know about {text}?"
    assert think["clarifying_question"] == expected_question
    assert think["resolved_entities"] == []
    assert think["clarifying_options"] == [
        f"What is {text} and what are its symptoms?",
        f"Which genes or variants are linked to {text}?",
        f"Are there clinical trials for {text}?",
        f"What does recent research say about {text}?",
    ]

    # No search at all: BRCA1 is a real, resolvable gene symbol in this
    # stub, and it still must not resolve or run a tool, because the
    # product owner's design asks BEFORE any search runs.
    assert "tool_start" not in types, types
    plan = _payload(events, "plan")
    assert plan is not None and plan["tool_calls"] == []

    token = _payload(events, "token")
    assert token is not None and token["text"] == expected_question

    done = _payload(events, "done")
    assert done is not None
    assert done["trust_outcome"] == "refuse"
    assert done["total_tool_calls"] == 0


@pytest.mark.asyncio
async def test_a_fourth_word_proceeds_to_a_real_search() -> None:
    events = await _run("Any trials for GERD?")
    types = [event.type for event in events]
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert think.get("clarifying_options") is None
    assert "tool_start" in types, types


@pytest.mark.asyncio
async def test_a_question_word_proceeds_to_a_real_search() -> None:
    events = await _run("What is GERD?")
    types = [event.type for event in events]
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert think.get("clarifying_options") is None
    assert "tool_start" in types, types


@pytest.mark.asyncio
async def test_a_short_follow_up_with_an_earlier_turn_proceeds() -> None:
    """The counterfactual that isolates "opens a conversation" from "is a
    bare topic": the exact text of a must-ask example above ("BRCA1"),
    asked with an earlier turn's session memory present, must NOT ask,
    because a follow-up inside a conversation is never asked back
    (session memory already supplies its subject). This is the same
    property `test_clarification.py`'s own counterfactual pins for item
    7.5, applied to this new call site.
    """
    # Populate-check, run first: the identical text with NO memory does ask,
    # so "proceeds" below is a statement about the memory gate, not about
    # "BRCA1" never being ambiguous in the first place.
    opening_events = await _run("BRCA1")
    opening_think = _payload(opening_events, "think")
    assert opening_think is not None
    assert opening_think["clarifying_question"] is not None

    events = await _run("BRCA1", memory=_memory_with_tp53())
    types = [event.type for event in events]
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert think.get("clarifying_options") is None
    assert "tool_start" in types, types
    assert think["resolved_entities"], "BRCA1 resolves as a real entity once asked"
