"""UI fix set 7, item 7.5 (2026-09-13): a follow-up that refers to nothing
asks for the missing detail instead of refusing.

The product owner's retest words: "the follow up must retain context or ask
clarification if the question is not clear. Because if this is a discussion,
it must flow." The retain half is Plan's antecedent binding; this file pins
the ask half through the real five-node graph with the model stubbed.

Exercised:
    "What variants cause it?" with NO session memory: Think publishes the
    clarifying question, Plan selects no tool, no tool starts, Write's text
    IS the question, and the run ends `refuse` (no claim was made).
    The same words WITH a remembered BRCA1: no clarifying question, and a
    tool runs, so the rule never fires when memory can answer the reference.
    A question that names its own entity, with no memory: no clarifying
    question, so an ordinary question is never asked to repeat itself.
    A question with no referring word and no entity ("Tell me about
    genes"): no clarifying question either.
    Card 145: a first question about to be asked back is read a second time;
    it answers when that reading resolves, is asked back when it does not,
    and a question that resolves, or that memory answers, makes one Think
    call. The second reading fails closed past Think's budget.

NOT exercised: the web UI's rendering of the question (frontend tests own
that), and the live models.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import UTC, datetime
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


def _memory_with_brca1() -> SessionMemorySummary:
    return SessionMemorySummary(
        session_id="clarification-test",
        last_updated=datetime.now(UTC),
        resolved_entities=[
            ResolvedEntity(mention="BRCA1", curie="NCBIGene:672", entity_type="Gene")
        ],
    )


async def _run(text: str, memory: SessionMemorySummary | None = None) -> list[Any]:
    trace_id = f"t-{uuid.uuid4().hex[:12]}"
    query = Query(text=text, session_id="clarification-test", trace_id=trace_id)
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


@pytest.mark.asyncio
async def test_a_follow_up_with_nothing_to_point_at_asks_which() -> None:
    """MUTATION PROOF: removing the `clarification_needed` branch in
    `write_node` turns the token arm red; removing `_needs_clarification`
    from `think_node` turns the think arm red; removing Plan's early return
    turns the tool_start arm red.
    """
    events = await _run("What variants cause it?")
    types = [event.type for event in events]
    # Populate-check: the graph ran to completion.
    assert "done" in types, types

    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == graph_module.CLARIFICATION_QUESTION
    assert think["resolved_entities"] == []

    assert "tool_start" not in types, types
    plan = _payload(events, "plan")
    assert plan is not None and plan["tool_calls"] == []

    token = _payload(events, "token")
    assert token is not None
    assert token["text"] == graph_module.CLARIFICATION_QUESTION
    assert "which gene, variant or condition" in token["text"]

    done = _payload(events, "done")
    assert done is not None and done["trust_outcome"] == "refuse"
    assert done["total_tool_calls"] == 0


@pytest.mark.asyncio
async def test_the_same_words_with_a_remembered_gene_are_answered_not_questioned() -> None:
    """The counterfactual: memory supplies the antecedent, so the rule must
    stay silent and a tool must run."""
    events = await _run("What variants cause it?", memory=_memory_with_brca1())
    types = [event.type for event in events]
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert "tool_start" in types, types
    token = _payload(events, "token")
    assert token is not None and token["text"] != graph_module.CLARIFICATION_QUESTION


@pytest.mark.asyncio
async def test_a_question_naming_its_own_entity_is_never_asked_to_repeat_itself() -> None:
    events = await _run("Which diseases are associated with BRCA1?")
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert think["resolved_entities"], "populate-check: BRCA1 resolves in this stub"
    assert "tool_start" in [event.type for event in events]


@pytest.mark.asyncio
async def test_a_question_with_no_referring_word_is_not_questioned() -> None:
    events = await _run("Tell me about breast cancer genes")
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    token = _payload(events, "token")
    assert token is None or token["text"] != graph_module.CLARIFICATION_QUESTION


# Card 145 (2026-10-22): a first question is read a second time before it is
# asked back. The owner's decision: "when the system is about to ask a first
# question back because it read no subject, it reads the question a second
# time and asks back only if that reading also finds nothing; no question
# that answers today pays for it."
#
# The gap the diagnosis named: a first question that names its own subject
# in plain English, carries a referring word ("it"), and whose first reading
# does not confirm. The condition here is a stand-in, chosen so no test
# question reaches a prompt; MedGen is stubbed to confirm it.

_OWN_SUBJECT_QUESTION = "What causes croup in children, and how is it usually treated?"
_CROUP_CURIE = "MedGen:C0010380"


def _think_reply(entities: list[dict[str, str]]) -> str:
    return json.dumps(
        {
            "query_class": "exploratory",
            "narrative": "stand-in classification for tests",
            "entities": entities,
        }
    )


@pytest.fixture
def think_readings(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Count Think's classification calls and, when `script` is set, answer
    them in order from it; every other model call keeps the file's stub."""
    record: dict[str, Any] = {"calls": 0, "script": None}
    inner = harness_module.litellm.acompletion

    async def _dispatch(*args: object, **kwargs: object) -> Any:
        messages = list(kwargs.get("messages") or [])
        joined = "\n".join(str(message.get("content") or "") for message in messages)
        if graph_module._THINK_SYSTEM_INSTRUCTION in joined:
            record["calls"] += 1
            script = record["script"]
            if script is not None:
                return fake_response(script[min(record["calls"], len(script)) - 1])
        return await inner(*args, **kwargs)

    monkeypatch.setattr(harness_module.litellm, "acompletion", _dispatch)

    async def _medgen(mention: str) -> tuple[list[str], int]:
        return ([_CROUP_CURIE], 1) if mention.strip().lower() == "croup" else ([], 0)

    monkeypatch.setattr(graph_module, "resolve_disease_mention_to_curies", _medgen)
    return record


@pytest.mark.asyncio
async def test_an_unread_first_question_is_read_again_and_answered(
    think_readings: dict[str, Any],
) -> None:
    """MUTATION PROOF: removing the card 145 block in `_think` asks this
    question back (think arm red) and makes one Think call (count arm red)."""
    think_readings["script"] = [
        _think_reply([]),
        _think_reply([{"text": "croup", "entity_type": "disease"}]),
    ]
    events = await _run(_OWN_SUBJECT_QUESTION)
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert [entity["curie"] for entity in think["resolved_entities"]] == [_CROUP_CURIE]
    assert think_readings["calls"] == 2
    token = _payload(events, "token")
    assert token is None or token["text"] != graph_module.CLARIFICATION_QUESTION


@pytest.mark.asyncio
async def test_two_readings_that_find_nothing_still_ask_back(
    think_readings: dict[str, Any],
) -> None:
    """The other direction: the second reading finds nothing either, so the
    person is asked back exactly as before card 145."""
    think_readings["script"] = [_think_reply([]), _think_reply([])]
    events = await _run(_OWN_SUBJECT_QUESTION)
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == graph_module.CLARIFICATION_QUESTION
    assert think["resolved_entities"] == []
    assert think_readings["calls"] == 2
    assert "tool_start" not in [event.type for event in events]


@pytest.mark.asyncio
async def test_a_second_reading_naming_an_unknown_condition_still_asks_back(
    think_readings: dict[str, Any],
) -> None:
    """A second reading that names a span NCBI does not confirm resolves
    nothing, so it is not taken: the ask-back stands."""
    think_readings["script"] = [
        _think_reply([]),
        _think_reply([{"text": "children", "entity_type": "disease"}]),
    ]
    events = await _run(_OWN_SUBJECT_QUESTION)
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == graph_module.CLARIFICATION_QUESTION
    assert think_readings["calls"] == 2


@pytest.mark.asyncio
async def test_the_dangling_first_message_is_still_asked_back_after_two_readings(
    think_readings: dict[str, Any],
) -> None:
    """`test_a_follow_up_with_nothing_to_point_at_asks_which`'s question with
    the file's own stub: both readings name nothing, so it is asked back."""
    events = await _run("What variants cause it?")
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == graph_module.CLARIFICATION_QUESTION
    assert think_readings["calls"] == 2


@pytest.mark.asyncio
async def test_a_question_that_resolves_makes_exactly_one_think_call(
    think_readings: dict[str, Any],
) -> None:
    """No question that answers today pays for the second reading."""
    events = await _run("What does the BRCA1 gene do and why is it studied?")
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert think["resolved_entities"], "populate-check: BRCA1 resolves in this stub"
    assert think_readings["calls"] == 1


@pytest.mark.asyncio
async def test_a_plain_english_subject_that_resolves_first_time_makes_one_call(
    think_readings: dict[str, Any],
) -> None:
    think_readings["script"] = [_think_reply([{"text": "croup", "entity_type": "disease"}])]
    events = await _run(_OWN_SUBJECT_QUESTION)
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert think_readings["calls"] == 1


@pytest.mark.asyncio
async def test_a_remembered_subject_makes_exactly_one_think_call(
    think_readings: dict[str, Any],
) -> None:
    """Memory answers the reference, so the ask-back never comes near and
    neither does the second reading."""
    events = await _run("What variants cause it?", memory=_memory_with_brca1())
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert think_readings["calls"] == 1


@pytest.mark.asyncio
async def test_the_second_reading_fails_closed_past_think_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bounded by Think's own step deadline: none left reads nothing, and a
    reading still running when it ends is dropped. Either way the caller
    asks back as today."""
    calls = {"n": 0}

    async def _slow(*args: object, **kwargs: object) -> Any:
        calls["n"] += 1
        await asyncio.sleep(5)
        raise AssertionError("the deadline should have stopped this reading")

    monkeypatch.setattr(graph_module, "_run_think_classification", _slow)
    harness = harness_module.Harness("t-deadline")
    spent = await graph_module._read_question_again(harness, "t", [], time.monotonic() - 1)
    assert spent is None and calls["n"] == 0
    started = time.monotonic()
    late = await graph_module._read_question_again(harness, "t", [], time.monotonic() + 0.05)
    assert late is None and calls["n"] == 1
    assert time.monotonic() - started < 1.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "early_exit",
    [{"cap_exceeded": True}, {"step_error": {"source": "think"}}],
    ids=["cost_cap", "step_error"],
)
async def test_the_second_reading_fails_closed_on_an_early_exit(
    monkeypatch: pytest.MonkeyPatch, early_exit: dict[str, Any]
) -> None:
    async def _exit(*args: object, **kwargs: object) -> Any:
        return early_exit

    monkeypatch.setattr(graph_module, "_run_think_classification", _exit)
    result = await graph_module._read_question_again(
        harness_module.Harness("t-exit"), "t", [], time.monotonic() + 30
    )
    assert result is None
