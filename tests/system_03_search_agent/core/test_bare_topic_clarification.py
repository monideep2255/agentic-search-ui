"""UI fix plan item 12.3: a one-to-three-word question that opens a
conversation is asked back or searched by a classifier's reading of it,
never by a word list.

REDESIGNED 2026-09-24 on the product owner's instruction, "Please do not
hardcode! Hopefully not that dumb", and ROUTED THROUGH THE CLASSIFIER SEAM
on 2026-09-25 (build phase 8.2, builder J; DECISIONS.md cards 5 and 9).
`decide(point="think.ask_back")` decides whether to ask, and
`core.clarify`'s guard-tier writer writes what to ask; `think_node` starts
both at the same moment and shows the writer's words only on a real
`ask_back` pick. `test_clarify.py` grades the writer's strict parse in
isolation; this file grades the WIRING.

Exercised, each through the real five-node graph with the models and
`decide()` stubbed: an `ask_back` pick with usable choices publishes the
writer's OWN question and options and runs NO tool; the decision and the
writer run at the same time; a `proceed` pick searches even though the
writer wrote choices; no usable pick (both models down, or the seam
raising) searches; an `ask_back` pick whose choices could not be written
(unparseable, schema-invalid, a failed call, a cap hit) searches, the
fail-open rule. A four-word question and a short follow-up with session
memory never reach the decision or the writer.

NOT exercised: `core.clarify`'s own parsing and bounds (`test_clarify.py`
owns that), `decide()` itself (`tests/system_03_search_agent/harness/
test_decide.py`), and the web UI's rendering of the options as chips
(`frontend/src/components/answer/FollowUp.clarifyingOptions.test.tsx`;
unchanged, since the wire contract `ThinkPayload.clarifying_options` did
not change).
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

import pytest

from system_03_search_agent.contracts.events import DecisionRecord
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
    """A well-formed writer reply for `topic`, matching
    `core.clarify.ClarifyChoices`' own bounds."""
    return json.dumps(
        {
            "question": f"What would you like to know about {topic}?",
            "options": [
                f"What is {topic}?",
                f"What does recent research say about {topic}?",
                f"Are there clinical trials on {topic}?",
                f"Which genes or diseases are linked to {topic}?",
            ],
        }
    )


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
# decide(), stubbed per point (build phase 8.2, builder J). Every point not
# named in `picks` answers its SAFE option, so a test about ask_back is
# never disturbed by another decision the loop makes on the same question.
# ---------------------------------------------------------------------------

_SAFE_PICKS: dict[str, str] = {
    "guardrail.relevancy": "on_topic",
    "think.ask_back": "proceed",
    "think.recent_years": "not_applicable",
    "plan.literature": "not_literature",
}


def _record(point: str, options: Any, pick: str | None) -> DecisionRecord:
    """A record with `pick` made by Jev, or, for None, the record `decide`
    returns when NEITHER model produced a pick: `chosen` is then only its
    filler, the first offered option (F-J-04)."""
    if pick is None:
        return DecisionRecord(
            name=point,
            options=list(options),
            chosen=next(iter(options)),
            decided_by="guard",
            fallback_reason="timeout",
        )
    return DecisionRecord(
        name=point,
        options=list(options),
        chosen=pick,
        decided_by="jev",
        jev_choice=pick,
        guard_choice=pick,
        agreed=True,
    )


def _install_decide(
    monkeypatch: pytest.MonkeyPatch,
    picks: dict[str, str | None | BaseException] | None = None,
    *,
    gate: Any = None,
) -> list[str]:
    """Stub `core.graph.decide`. Returns the list of points asked, in order.

    `picks[point]` is a pick, None for "no usable pick", or an exception
    the seam raises. `gate`, when given, is awaited by the ask_back
    decision before it answers, which is how a test proves the choices
    writer was started alongside it rather than after it.
    """
    asked: list[str] = []
    configured = dict(picks or {})

    async def _decide(harness: Any, trace_id: str, point: str, state: str, options: Any, **kwargs: Any) -> DecisionRecord:
        asked.append(point)
        assert kwargs.get("instructions") and kwargs.get("criteria"), (
            f"{point} was asked without its description"
        )
        if point == "think.ask_back" and gate is not None:
            await asyncio.wait_for(gate.wait(), timeout=1.0)
        pick = configured.get(point, _SAFE_PICKS.get(point))
        if isinstance(pick, BaseException):
            raise pick
        return _record(point, options, pick)

    monkeypatch.setattr(graph_module, "decide", _decide)
    return asked


# ---------------------------------------------------------------------------
# ask_back decided, with usable choices: the question is asked back.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ask_back_shows_the_writers_question_and_runs_no_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MUTATION PROOF: making `think_node` ignore the `think.ask_back` pick
    (always falling through) turns the think and token arms red; removing
    Plan's existing `clarification_needed` early return turns the
    tool_start arm red; removing Write's existing `clarification_needed`
    branch turns the token and done arms red. All three are item 7.5's own
    pre-existing machinery, reused rather than reinvented.
    """
    _install_tools(monkeypatch)
    dispatched = _install_models(monkeypatch, clarify_reply=_clarify_reply("insulin"))
    asked = _install_decide(monkeypatch, {"think.ask_back": "ask_back"})

    events = await _run("insulin")
    types = [event.type for event in events]
    assert "done" in types, types
    assert "think.ask_back" in asked, asked
    # The writer ran; Think's own classification never did.
    assert dispatched == ["guard", "clarify"], dispatched

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
async def test_the_choices_are_whatever_the_writer_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No template lives in `think_node`: whatever strings the writer sends
    are what the reader sees, unmodified."""
    _install_tools(monkeypatch)
    custom = json.dumps(
        {
            "question": "Which BRCA1 aspect do you mean?",
            "options": [
                "What is BRCA1?",
                "Which conditions are linked to BRCA1?",
            ],
        }
    )
    _install_models(monkeypatch, clarify_reply=custom)
    _install_decide(monkeypatch, {"think.ask_back": "ask_back"})

    events = await _run("BRCA1")
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == "Which BRCA1 aspect do you mean?"
    assert think["clarifying_options"] == [
        "What is BRCA1?",
        "Which conditions are linked to BRCA1?",
    ]
    assert "tool_start" not in [event.type for event in events]


@pytest.mark.asyncio
async def test_the_decision_and_the_writer_run_at_the_same_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Card 6: a person waits for one call, not two. The ask_back decision
    below refuses to answer until the writer has STARTED; run one after
    the other, it would time out and the question would not be asked back.
    """
    writer_started = asyncio.Event()
    _install_tools(monkeypatch)
    dispatched = _install_models(monkeypatch, clarify_reply=_clarify_reply("insulin"))

    real_writer = graph_module._write_clarify_choices

    async def _writer(*args: Any, **kwargs: Any) -> Any:
        writer_started.set()
        return await real_writer(*args, **kwargs)

    monkeypatch.setattr(graph_module, "_write_clarify_choices", _writer)
    _install_decide(monkeypatch, {"think.ask_back": "ask_back"}, gate=writer_started)

    events = await _run("insulin")
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"], dispatched


# ---------------------------------------------------------------------------
# Everything else searches: proceed, and every failure mode.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_proceed_searches_even_when_the_writer_wrote_choices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The writer always writes; only the classifier's pick shows it."""
    _install_tools(monkeypatch)
    dispatched = _install_models(monkeypatch, clarify_reply=_clarify_reply("BRCA1"))
    _install_decide(monkeypatch, {"think.ask_back": "proceed"})

    events = await _run("BRCA1")
    types = [event.type for event in events]
    assert "clarify" in dispatched and "think" in dispatched, dispatched

    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert think.get("clarifying_options") is None
    assert "tool_start" in types, types


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ask_back_pick",
    [
        # Neither model produced a pick. `chosen` is decide()'s filler,
        # the first option, "ask_back": trusting it would ask every short
        # question back whenever both models are down (F-J-04).
        None,
        # The seam itself raised.
        RuntimeError("seam down"),
    ],
)
async def test_no_usable_ask_back_decision_searches(
    monkeypatch: pytest.MonkeyPatch, ask_back_pick: Any
) -> None:
    _install_tools(monkeypatch)
    _install_models(monkeypatch, clarify_reply=_clarify_reply("BRCA1"))
    _install_decide(monkeypatch, {"think.ask_back": ask_back_pick})

    events = await _run("BRCA1")
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert "tool_start" in [event.type for event in events]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "writer_reply",
    [
        # Not JSON: `parse_clarify_reply` raises ClarifyUnavailableError.
        "not valid json at all",
        # JSON, but under `ClarifyChoices`' own two-option floor.
        json.dumps({"question": "Which?", "options": ["only one?"]}),
        # The writing call itself failed.
        HarnessCallError("simulated timeout", error_class="transient"),
        # The writing call was refused by the per-query cost cap.
        cost_control.QueryCapExceededError(
            "simulated cap hit",
            query_cost_usd=1.0,
            query_cap_usd=1.0,
            estimated_call_cost_usd=0.01,
        ),
    ],
)
async def test_ask_back_with_no_usable_choices_searches(
    monkeypatch: pytest.MonkeyPatch, writer_reply: Any
) -> None:
    """The fail-open rule: the classifier said ask back, but there is
    nothing honest to ask with, so the question gets a real search rather
    than an empty or invented question."""
    _install_tools(monkeypatch)
    dispatched = _install_models(monkeypatch, clarify_reply=writer_reply)
    _install_decide(monkeypatch, {"think.ask_back": "ask_back"})

    events = await _run("BRCA1")
    assert "clarify" in dispatched, dispatched
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert "tool_start" in [event.type for event in events]


# ---------------------------------------------------------------------------
# The trigger: 1 to 3 words, opening the conversation. Anything else never
# reaches the ask_back decision or the writer at all.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_four_words_never_reach_ask_back(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_tools(monkeypatch)
    dispatched = _install_models(monkeypatch, clarify_reply=None)
    asked = _install_decide(monkeypatch)

    events = await _run("Any trials for GERD?")
    assert "clarify" not in dispatched, dispatched
    assert "think.ask_back" not in asked, asked
    assert "tool_start" in [event.type for event in events]


@pytest.mark.asyncio
async def test_a_short_follow_up_with_an_earlier_turn_never_reaches_ask_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The counterfactual that isolates "opens a conversation" from "is
    short": the exact text of a must-trigger example ("BRCA1"), asked with
    an earlier turn's session memory present, never reaches the ask_back
    decision, because a follow-up inside a conversation is never asked
    back (session memory already supplies its subject).

    Populate-check, run first: the identical text with NO memory IS asked
    back, so "never" below is a statement about the memory gate, not about
    the trigger never firing for this text at all.
    """
    _install_tools(monkeypatch)
    opening_dispatched = _install_models(monkeypatch, clarify_reply=_clarify_reply("BRCA1"))
    _install_decide(monkeypatch, {"think.ask_back": "ask_back"})
    opening_events = await _run("BRCA1")
    assert "clarify" in opening_dispatched, opening_dispatched
    opening_think = _payload(opening_events, "think")
    assert opening_think is not None and opening_think["clarifying_question"] is not None

    dispatched = _install_models(monkeypatch, clarify_reply=None)
    asked = _install_decide(monkeypatch, {"think.ask_back": "ask_back"})
    events = await _run("BRCA1", memory=_memory_with_tp53())

    assert "clarify" not in dispatched, dispatched
    assert "think.ask_back" not in asked, asked
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert "tool_start" in [event.type for event in events]
    assert think["resolved_entities"], "BRCA1 resolves as a real entity once asked"


# ---------------------------------------------------------------------------
# think.recent_years (build phase 8.2, card 4, item 12.15): the same ask-back
# mechanism, asked when the classifier says a question wants recent work
# without saying how recent. `decide()` is stubbed per point as above.
# ---------------------------------------------------------------------------


def _spy_searches(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Record every ESearch the plan makes, answering each as empty."""
    searches: list[dict[str, Any]] = []

    async def _efetch(tool_input: Any, **kwargs: object) -> NcbiEfetchOutput:
        dumped = tool_input.model_dump()
        if dumped.get("action") == "search":
            searches.append(dumped)
        return NcbiEfetchOutput(
            status="empty",
            action=dumped.get("action", "search"),
            records=[],
            record_count=0,
            total_available=None,
            truncated=False,
            error=None,
        )

    monkeypatch.setattr(graph_module, "ncbi_efetch", _efetch)
    return searches


@pytest.mark.asyncio
async def test_recent_work_with_no_range_asks_how_far_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MUTATION PROOF: making `_asks_for_unbounded_recent_work` return False
    turns every arm here red: the question is searched instead of asked."""
    _install_tools(monkeypatch)
    _install_models(monkeypatch, clarify_reply=None)
    asked = _install_decide(monkeypatch, {"think.recent_years": "recent_unbounded"})

    events = await _run("recent papers on statins")
    assert "think.recent_years" in asked, asked
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == clarify.RECENT_WINDOW_QUESTION
    assert think["clarifying_options"] == [
        "Recent papers on statins from the last 12 months?",
        "Recent papers on statins from the last 5 years?",
        "Recent papers on statins from the last 10 years?",
    ]
    assert "tool_start" not in [event.type for event in events]


@pytest.mark.asyncio
async def test_a_short_opener_can_be_asked_how_far_back_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Three words: ask_back said proceed, recent_years said unbounded, and
    the recent_years decision was gathered with the other two."""
    _install_tools(monkeypatch)
    _install_models(monkeypatch, clarify_reply=_clarify_reply("statins"))
    asked = _install_decide(
        monkeypatch, {"think.ask_back": "proceed", "think.recent_years": "recent_unbounded"}
    )

    events = await _run("recent statin papers")
    assert {"think.ask_back", "think.recent_years"} <= set(asked), asked
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] == clarify.RECENT_WINDOW_QUESTION


@pytest.mark.asyncio
async def test_a_stated_range_is_never_asked_again_whatever_the_classifier_said(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Code verifies the one value it may read: "since 2022" is right there
    to search with, so a classifier that still said unbounded is overruled,
    and the search carries the range as a publication-date limit."""
    _install_tools(monkeypatch)
    searches = _spy_searches(monkeypatch)
    _install_models(monkeypatch, clarify_reply=None)
    _install_decide(monkeypatch, {"think.recent_years": "recent_unbounded"})

    events = await _run("papers on statins since 2022")
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    pubmed = [s for s in searches if s.get("db") == "pubmed"]
    assert pubmed and pubmed[0]["term"].endswith('AND ("2022/01/01"[dp] : "3000"[dp])'), pubmed


@pytest.mark.asyncio
@pytest.mark.parametrize("recent_pick", ["not_applicable", None, RuntimeError("seam down")])
async def test_anything_but_recent_unbounded_searches(
    monkeypatch: pytest.MonkeyPatch, recent_pick: Any
) -> None:
    """`not_applicable`, no usable pick (both models down), and a failed
    seam all search: the fail-open rule."""
    _install_tools(monkeypatch)
    _install_models(monkeypatch, clarify_reply=None)
    _install_decide(monkeypatch, {"think.recent_years": recent_pick})

    events = await _run("recent papers on statins")
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert "tool_start" in [event.type for event in events]


@pytest.mark.asyncio
async def test_the_picked_window_narrows_the_pubmed_search_to_those_years(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The choice a person clicks is asked as its own question, and its
    range reaches ESearch as a publication-date limit: only papers from
    those years can come back."""
    from datetime import UTC, datetime

    from system_03_search_agent.core import breadth_plan

    _install_tools(monkeypatch)
    searches = _spy_searches(monkeypatch)
    _install_models(monkeypatch, clarify_reply=None)
    _install_decide(monkeypatch)

    picked = clarify.recent_window_choices("recent papers on statins").options[1]
    events = await _run(picked)

    expected = breadth_plan.parse_publication_window(picked, today=datetime.now(UTC).date())
    assert expected is not None and expected.label == "the last 5 years"
    pubmed = [s for s in searches if s.get("db") == "pubmed"]
    assert pubmed and pubmed[0]["term"] == f"statins AND {expected.clause()}", pubmed
    plan = _payload(events, "plan")
    assert plan is not None and "published the last 5 years" in plan["narrative"], plan


# ---------------------------------------------------------------------------
# plan.literature (build phase 8.2, card 3): started by Think, read by Plan.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_literature_decision_starts_at_think_and_plan_reads_it_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Think starts it so it overlaps Think's own work; Plan reads that same
    decision rather than asking again, so a search question asks it once."""
    _install_tools(monkeypatch)
    _install_models(monkeypatch, clarify_reply=None)
    asked = _install_decide(monkeypatch)

    await _run("which papers discuss statin side effects")
    assert asked.count("plan.literature") == 1, asked


@pytest.mark.asyncio
async def test_a_question_asked_back_cancels_the_literature_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No search follows a question asked back, so the literature decision
    Think started is stopped rather than left spending, and it is never
    read."""
    started = asyncio.Event()
    cancelled = asyncio.Event()
    _install_tools(monkeypatch)
    _install_models(monkeypatch, clarify_reply=None)
    base = _install_decide(monkeypatch, {"think.recent_years": "recent_unbounded"})
    inner = graph_module.decide

    async def _decide(harness: Any, trace_id: str, point: str, *args: Any, **kwargs: Any) -> Any:
        if point == "plan.literature":
            started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.set()
                raise
        return await inner(harness, trace_id, point, *args, **kwargs)

    monkeypatch.setattr(graph_module, "decide", _decide)
    events = await _run("recent papers on statins")
    await asyncio.sleep(0)
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] == clarify.RECENT_WINDOW_QUESTION
    assert started.is_set() and cancelled.is_set(), base
