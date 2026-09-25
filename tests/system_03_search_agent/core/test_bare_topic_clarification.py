"""UI fix plan item 12.3, REDESIGNED 2026-09-24: a one-to-three-word
question that opens a conversation is asked back or searched by a model's
own reading of it, never by a word list.

The product owner's instruction, verbatim: "Please do not hardcode!
Hopefully not that dumb". The first build decided ask-or-proceed from a
question-word list, then a request-word list, and offered four fixed
template questions; all three are withdrawn. What replaced them is one
guard-tier call, `core.clarify`'s `build_clarify_messages`/
`parse_clarify_reply`, dispatched from `core.graph._clarify_or_proceed` and
wired at the top of `think_node`. `core.clarify`'s own module owns the
prompt and the strict parse; `test_clarify.py` grades that in isolation.
This file grades the WIRING: the trigger that decides whether the
classifier is even called, and what `think_node` does with each of its
three possible outcomes.

Exercised, each through the real five-node graph with the model stubbed
per tier (the same harness `test_clarification.py` uses):
    `ask_back: true` publishes the classifier's OWN question and options
    and runs NO tool call. `ask_back: false` proceeds to a real search.
    A malformed classifier reply, and a classifier call that raises
    `HarnessCallError`, both proceed to a real search, the fail-open rule
    stated in `core.clarify`'s own module docstring. A four-word question
    never calls the classifier at all. A short follow-up with an earlier
    turn's session memory present never calls it either, since memory
    already supplies the subject.

NOT exercised: `core.clarify`'s own parsing and bounds (`test_clarify.py`
owns that), and the web UI's rendering of the four options as chips
(`frontend/src/components/answer/FollowUp.clarifyingOptions.test.tsx`
owns that; unchanged by this redesign, since the wire contract
`ThinkPayload.clarifying_options` did not change).
"""

from __future__ import annotations

import json
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
from system_03_search_agent.core import clarify
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.harness import HarnessCallError
from system_03_search_agent.tools.cypher_schemas import CypherQueryOutput, CypherQueryRow
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput
from tests.system_03_search_agent.model_stub import (
    COMPLIANT_GUARD_CLASSIFICATION,
    compliant_synth_narrative,
    compliant_think_classification,
    fake_response,
)


def _clarify_reply(topic: str) -> str:
    """A well-formed `ask_back: true` reply for `topic`, matching
    `core.clarify.ClarifyDecision`'s own bounds."""
    return json.dumps(
        {
            "ask_back": True,
            "question": f"What would you like to know about {topic}?",
            "options": [
                f"What is {topic}?",
                f"What does recent research say about {topic}?",
                f"Are there clinical trials on {topic}?",
                f"Which genes or diseases are linked to {topic}?",
            ],
        }
    )


_PROCEED_REPLY = json.dumps({"ask_back": False, "question": "", "options": []})


# ---------------------------------------------------------------------------
# Harness: the same fixtures `test_clarification.py` uses, plus a
# configurable clarify-call outcome.
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


def _install_tools(monkeypatch: pytest.MonkeyPatch) -> None:
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


def _install_models(
    monkeypatch: pytest.MonkeyPatch,
    *,
    clarify_reply: str | BaseException | None,
) -> list[str]:
    """Stub `litellm.acompletion` per tier, and record which tiers' prompts
    were actually dispatched (by their fixed instruction text), so a test
    can assert the classifier was, or was never, called.

    `clarify_reply`:
        - a string: the clarify call's raw completion content.
        - an exception instance: the clarify call raises it (simulates a
          `HarnessCallError` or a `cost_control.QueryCapExceededError`).
        - None: this test never expects the clarify call to be reached;
          reaching it raises `AssertionError` so a wrong-trigger regression
          fails loudly here rather than silently returning a plausible
          value.
    """
    from system_03_search_agent.guardrail.classifier import GUARD_SYSTEM_INSTRUCTION
    from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION

    dispatched: list[str] = []

    async def _dispatch(*args: object, **kwargs: object) -> Any:
        messages = list(kwargs.get("messages") or [])
        joined = "\n".join(str(message.get("content") or "") for message in messages)
        if clarify.CLARIFY_SYSTEM_INSTRUCTION in joined:
            dispatched.append("clarify")
            if clarify_reply is None:
                raise AssertionError("the clarify classifier was called but no reply was configured")
            if isinstance(clarify_reply, BaseException):
                raise clarify_reply
            return fake_response(clarify_reply)
        if GUARD_SYSTEM_INSTRUCTION in joined:
            dispatched.append("guard")
            return fake_response(COMPLIANT_GUARD_CLASSIFICATION)
        if graph_module._THINK_SYSTEM_INSTRUCTION in joined:
            dispatched.append("think")
            return fake_response(compliant_think_classification(messages))
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            dispatched.append("synth")
            return fake_response(compliant_synth_narrative(messages))
        dispatched.append("other")
        return fake_response("MATCH (g:Gene) RETURN g LIMIT 1")

    monkeypatch.setattr(harness_module.litellm, "acompletion", _dispatch)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )
    return dispatched


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


# ---------------------------------------------------------------------------
# ask_back: true
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ask_back_true_shows_the_models_question_and_runs_no_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MUTATION PROOF: removing `_clarify_or_proceed`'s `ask_back` check in
    `think_node` (always falling through) turns the think and token arms
    red; removing Plan's existing `clarification_needed` early return
    turns the tool_start arm red; removing Write's existing
    `clarification_needed` branch turns the token and done arms red. All
    three are item 7.5's own pre-existing machinery, reused rather than
    reinvented.
    """
    _install_tools(monkeypatch)
    dispatched = _install_models(monkeypatch, clarify_reply=_clarify_reply("insulin"))

    events = await _run("insulin")
    types = [event.type for event in events]
    assert "done" in types, types
    # "other" is the guardrail.relevancy classifier (build phase 8.2):
    # "insulin" is not on the vocabulary allowlist, so a classifier judges
    # its topic. Nothing past the clarify call runs: no Think, no tool.
    assert [d for d in dispatched if d != "other"] == ["guard", "clarify"], dispatched

    think = _payload(events, "think")
    assert think is not None
    expected_question = "What would you like to know about insulin?"
    assert think["clarifying_question"] == expected_question
    assert think["resolved_entities"] == []
    assert think["clarifying_options"] == [
        "What is insulin?",
        "What does recent research say about insulin?",
        "Are there clinical trials on insulin?",
        "Which genes or diseases are linked to insulin?",
    ]

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
async def test_ask_back_true_options_are_tailored_to_whatever_the_model_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No template lives in `think_node` any more: whatever four strings
    the classifier sends are what the reader sees, unmodified."""
    _install_tools(monkeypatch)
    custom = json.dumps(
        {
            "ask_back": True,
            "question": "Which BRCA1 aspect do you mean?",
            "options": [
                "What is BRCA1?",
                "Which conditions are linked to BRCA1?",
            ],
        }
    )
    _install_models(monkeypatch, clarify_reply=custom)

    events = await _run("BRCA1")
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == "Which BRCA1 aspect do you mean?"
    assert think["clarifying_options"] == [
        "What is BRCA1?",
        "Which conditions are linked to BRCA1?",
    ]
    assert "tool_start" not in [event.type for event in events]


# ---------------------------------------------------------------------------
# ask_back: false, and every failure mode. All proceed to a real search.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ask_back_false_proceeds_to_a_real_search(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_tools(monkeypatch)
    dispatched = _install_models(monkeypatch, clarify_reply=_PROCEED_REPLY)

    events = await _run("BRCA1")
    types = [event.type for event in events]
    assert dispatched[:2] == ["guard", "clarify"], dispatched
    assert "think" in dispatched, dispatched

    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert think.get("clarifying_options") is None
    assert "tool_start" in types, types


@pytest.mark.asyncio
async def test_a_malformed_reply_proceeds_to_a_real_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fail-open rule, on the parse half: `parse_clarify_reply` raises
    `ClarifyUnavailableError` for text that is not valid JSON, and
    `_clarify_or_proceed` turns that into `None`, which `think_node`
    treats exactly like `ask_back: false`."""
    _install_tools(monkeypatch)
    dispatched = _install_models(monkeypatch, clarify_reply="not valid json at all")

    events = await _run("BRCA1")
    types = [event.type for event in events]
    assert "clarify" in dispatched, dispatched

    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert "tool_start" in types, types


@pytest.mark.asyncio
async def test_a_schema_invalid_reply_proceeds_to_a_real_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fail-open rule again, on a reply that IS valid JSON but fails
    `ClarifyDecision`'s own bounds (here, `ask_back: true` with only one
    option, under `MIN_CLARIFY_OPTIONS`)."""
    _install_tools(monkeypatch)
    bad = json.dumps({"ask_back": True, "question": "Which?", "options": ["only one?"]})
    dispatched = _install_models(monkeypatch, clarify_reply=bad)

    events = await _run("BRCA1")
    assert "clarify" in dispatched, dispatched
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert "tool_start" in [event.type for event in events]


@pytest.mark.asyncio
async def test_a_call_failure_proceeds_to_a_real_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fail-open rule on the DISPATCH half: a `HarnessCallError` (a
    timeout, or an exhausted-retry transport failure) from the classifier
    call itself, not from parsing its reply."""
    _install_tools(monkeypatch)
    dispatched = _install_models(
        monkeypatch,
        clarify_reply=HarnessCallError("simulated timeout", error_class="transient"),
    )

    events = await _run("BRCA1")
    assert "clarify" in dispatched, dispatched
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert "tool_start" in [event.type for event in events]


@pytest.mark.asyncio
async def test_a_cap_hit_proceeds_to_a_real_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fail-open rule on the cost-cap half: the classifier call itself
    is what `cost_control.QueryCapExceededError` blocks, and even then the
    QUESTION still gets an honest attempt at a real search rather than
    being silently dropped."""
    _install_tools(monkeypatch)
    dispatched = _install_models(
        monkeypatch,
        clarify_reply=cost_control.QueryCapExceededError(
            "simulated cap hit",
            query_cost_usd=1.0,
            query_cap_usd=1.0,
            estimated_call_cost_usd=0.01,
        ),
    )

    events = await _run("BRCA1")
    assert "clarify" in dispatched, dispatched
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert "tool_start" in [event.type for event in events]


# ---------------------------------------------------------------------------
# The trigger: 1 to 3 words, opening the conversation. Anything else never
# reaches the classifier at all.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_four_words_never_calls_the_classifier(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_tools(monkeypatch)
    dispatched = _install_models(monkeypatch, clarify_reply=None)

    events = await _run("Any trials for GERD?")
    assert "clarify" not in dispatched, dispatched
    assert "tool_start" in [event.type for event in events]


@pytest.mark.asyncio
async def test_a_short_follow_up_with_an_earlier_turn_never_calls_the_classifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The counterfactual that isolates "opens a conversation" from "is
    short": the exact text of a must-trigger example ("BRCA1"), asked with
    an earlier turn's session memory present, never reaches the
    classifier, because a follow-up inside a conversation is never asked
    back (session memory already supplies its subject).

    Populate-check, run first: the identical text with NO memory DOES call
    the classifier, so "never calls it" below is a statement about the
    memory gate, not about the trigger never firing for this text at all.
    """
    _install_tools(monkeypatch)
    opening_dispatched = _install_models(monkeypatch, clarify_reply=_clarify_reply("BRCA1"))
    opening_events = await _run("BRCA1")
    assert "clarify" in opening_dispatched, opening_dispatched
    opening_think = _payload(opening_events, "think")
    assert opening_think is not None and opening_think["clarifying_question"] is not None

    dispatched = _install_models(monkeypatch, clarify_reply=None)
    events = await _run("BRCA1", memory=_memory_with_tp53())

    assert "clarify" not in dispatched, dispatched
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert "tool_start" in [event.type for event in events]
    assert think["resolved_entities"], "BRCA1 resolves as a real entity once asked"
