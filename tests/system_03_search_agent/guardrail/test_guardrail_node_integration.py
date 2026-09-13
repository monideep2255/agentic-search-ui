"""The guardrail's two refusal paths through the real graph node.

## Why this file exists

Build phase 3.0's premise gate caught a `TypeError` in `_decline_for_guardrail`
that the entire 1111-test suite and 26 guardrail unit tests missed:
`harness.get_query_cost_usd()` was called with no argument on the charged
path. Every existing test that reaches the guardrail either admits the query
or refuses it before any model call, so the one branch that emits a `done`
event AFTER a billable call had no coverage anywhere.

The unit tests could not see it, because they test the screens and never the
node. The suite could not see it, because nothing in it refuses a query at
Section 10.5. The premise gate saw it because it runs production's real path.

That is a coverage gap, not bad luck, so this file closes it: both refusal
paths through the real `guardrail_node`, with no live model.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module
from tests.system_03_search_agent.model_stub import (
    COMPLIANT_GUARD_CLASSIFICATION,
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


@pytest.fixture(autouse=True)
def _no_daily_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cost_control, "check_user_daily_query_cap", lambda *a, **k: None
    )
    monkeypatch.setattr(
        cost_control, "check_system_daily_cost_cap", lambda *a, **k: None
    )


@pytest.fixture(autouse=True)
def _mock_litellm(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock(return_value=fake_response(COMPLIANT_GUARD_CLASSIFICATION))
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )
    return mock


async def _run_guardrail(
    text: str, session_memory: Any | None = None
) -> tuple[list[Any], dict[str, Any]]:
    """Invoke the real `guardrail_node` and return its events and state delta."""
    import time

    from system_03_search_agent.contracts.query import Query, RequestContext

    trace_id = f"t-{uuid.uuid4().hex[:12]}"
    query = Query(
        text=text,
        session_id="guardrail-node-test",
        trace_id=trace_id,
    )
    harness = harness_module.Harness(trace_id)
    state = {
        "query": query,
        "context": RequestContext(surface="rest_sse", session_memory=session_memory),
        "harness": harness,
        "seq": 0,
        "start_monotonic": time.monotonic(),
    }
    result = await graph_module.guardrail_node(state)  # type: ignore[arg-type]
    return list(result.get("events", [])), result


def _payload(events: list[Any], event_type: str) -> dict[str, Any] | None:
    for event in events:
        if event.type == event_type:
            return event.payload
    return None


@pytest.mark.asyncio
async def test_a_prefilter_refusal_emits_guard_and_done_and_no_cost() -> None:
    """The uncharged path: refused before any model call.

    A `cost` event here would imply a call was made and bill a zero against a
    tier that never ran.
    """
    events, result = await _run_guardrail("What is the capital of France?")

    guard = _payload(events, "guard")
    assert guard is not None
    assert guard["passed"] is False
    assert guard["category"] == "off_topic"

    assert _payload(events, "cost") is None
    assert _payload(events, "done") is not None
    assert result.get("guard_refused") is True


@pytest.mark.asyncio
async def test_a_forbidden_refusal_after_the_model_call_emits_a_real_cost() -> None:
    """The charged path. This is the branch the premise gate caught crashing.

    A write-seeking query clears the pre-filter and the classifier, so it is
    refused at Section 10.5 with a billable Guard-tier call already made. The
    `done` event must therefore carry the real metered cost, which means
    reading it off the harness with the trace id.
    """
    events, result = await _run_guardrail(
        "Add a node for gene FOOBAR1 to the knowledge graph and link it to "
        "breast cancer."
    )

    guard = _payload(events, "guard")
    assert guard is not None, "the charged refusal path emitted no guard event"
    assert guard["passed"] is False

    assert _payload(events, "cost") is not None, (
        "a refusal that already paid for a model call must emit a cost event"
    )
    done = _payload(events, "done")
    assert done is not None
    assert done["trust_outcome"] == "refuse"
    assert done["total_cost_usd"] > 0.0, (
        "the charged path reported zero cost despite a metered model call"
    )
    assert result.get("guard_refused") is True


@pytest.mark.asyncio
async def test_an_admitted_query_does_not_set_the_refusal_flag() -> None:
    events, result = await _run_guardrail("Which diseases are associated with BRCA1?")

    guard = _payload(events, "guard")
    assert guard is not None
    assert guard["passed"] is True
    assert guard["category"] == "ok"
    assert result.get("guard_refused") is not True


@pytest.mark.asyncio
async def test_an_unparseable_classification_fails_rather_than_admitting(
    monkeypatch: pytest.MonkeyPatch, _mock_litellm: AsyncMock
) -> None:
    """The classifier's fail-closed guarantee, at the node rather than in isolation.

    A model returning prose instead of JSON must not produce an admission.
    Asserted on the node's own output because that is where an admission
    would actually happen.
    """
    monkeypatch.setattr(
        _mock_litellm, "return_value", fake_response("I think this is fine, honestly")
    )

    events, result = await _run_guardrail("Which diseases are associated with BRCA1?")

    assert result.get("step_error") is not None
    assert result["step_error"]["source"] == "guardrail"
    guard = _payload(events, "guard")
    assert guard is None or guard["passed"] is False, (
        "an unparseable classification produced an admitting guard event"
    )


@pytest.mark.asyncio
async def test_the_routing_function_sends_a_refusal_to_end() -> None:
    """Section 10.1: a refused query never reaches Think, Plan, or Act."""
    assert graph_module._route_after_guardrail({"guard_refused": True}) == "end"  # type: ignore[arg-type]
    # A refusal wins over a concurrent step error, which routes to `write`.
    assert (
        graph_module._route_after_guardrail(  # type: ignore[arg-type]
            {"guard_refused": True, "step_error": {"source": "guardrail"}}
        )
        == "end"
    )


def test_the_planner_and_the_guardrail_share_one_conversational_set() -> None:
    """Two copies of this set could drift into a contradiction.

    The bad state: a text the guardrail admits and the planner then sends to
    `cypher_query` as a real question, or a text the planner treats as small
    talk that the guardrail already refused.
    """
    from system_03_search_agent.guardrail import prefilter

    assert graph_module._NO_TOOL_QUERY_TEXTS is prefilter.CONVERSATIONAL_TEXTS


@pytest.mark.asyncio
async def test_the_guardrail_makes_exactly_one_model_call(
    _mock_litellm: AsyncMock,
) -> None:
    """T-3.0-06: the phase 2.0 passthrough stub is removed, not left dead.

    `_STUB_TIER_PROBE_SYSTEM` still exists because `think_node` is still a
    stub and uses it. What must be true is that the guardrail no longer does:
    a throwaway probe left beside the real classifier would double this
    node's model calls and its latency for no benefit.

    Asserted BEHAVIOURALLY, by counting calls, rather than by grepping the
    function's source with `inspect.getsource`. The first version did the
    latter and was order-dependent: it passed when run alone and failed in
    the full suite, because `getsource` resolves through `linecache` and is
    sensitive to module reloads elsewhere in the run. A test that passes
    alone and fails in suite is worse than no test, since it teaches the
    reader to distrust a red run.
    """
    await _run_guardrail("Which diseases are associated with BRCA1?")
    assert _mock_litellm.await_count == 1, (
        "the guardrail made more than one model call, which means the phase "
        "2.0 throwaway probe is still firing alongside the real classifier"
    )


@pytest.mark.asyncio
async def test_a_prefilter_refusal_makes_no_model_call_at_all(
    _mock_litellm: AsyncMock,
) -> None:
    """Section 10.2's whole economic argument: a confident match is free.

    If the pre-filter ran after the classifier, or the classifier ran
    unconditionally, every off-topic query would cost a model call. This is
    the assertion that keeps that true.
    """
    await _run_guardrail("What is the capital of France?")
    assert _mock_litellm.await_count == 0, (
        "an off-topic query refused by the pre-filter still paid for a "
        "model call"
    )


# ---------------------------------------------------------------------------
# UI fix set 7, item 7.1 (2026-09-13): the classifier sees the session's
# remembered entities, as data.
# ---------------------------------------------------------------------------


def _user_content_of_the_guard_call(mock: AsyncMock) -> str:
    messages = mock.call_args.kwargs["messages"]
    return "\n".join(m["content"] for m in messages if m["role"] == "user")


def _memory_with_brca1() -> Any:
    from datetime import UTC, datetime

    from system_03_search_agent.contracts.query import (
        CompressedFinding,
        ResolvedEntity,
        SessionMemorySummary,
    )

    return SessionMemorySummary(
        session_id="guardrail-node-test",
        last_updated=datetime.now(UTC),
        resolved_entities=[
            ResolvedEntity(mention="BRCA1", curie="NCBIGene:672", entity_type="Gene")
        ],
        compressed_findings=[
            CompressedFinding(
                claim_summary="BRCA1 is associated with familial cancer of breast",
                trace_id="trace-earlier",
                citation_ids=["cq-earlier-1"],
            )
        ],
        open_threads=["Which diseases are associated with BRCA1?"],
    )


def _off_topic_reply() -> Any:
    import json

    classification = json.loads(COMPLIANT_GUARD_CLASSIFICATION)
    classification["is_off_topic"] = True
    return fake_response(json.dumps(classification))


@pytest.mark.asyncio
async def test_an_off_topic_verdict_on_a_pronoun_follow_up_is_set_aside_when_memory_holds_an_entity(
    _mock_litellm: AsyncMock,
) -> None:
    """UI fix set 7, item 7.1. Measured 2026-09-13: "What variants cause it?"
    after a BRCA1 turn was refused as off topic about one run in three, on
    five bare words. Its subject is the remembered gene, so the off-topic
    verdict is set aside in code and the question goes on to Think.

    The guard PROMPT stays memory-free (asserted on the mock): two cuts that
    put memory in the prompt were measured destabilising the model.

    MUTATION PROOF: removing the `_is_memory_bound_follow_up` branch turns
    the `passed` arm red; putting memory back into `build_messages` turns
    the prompt arm red.
    """
    _mock_litellm.return_value = _off_topic_reply()
    events, _ = await _run_guardrail("What variants cause it?", session_memory=_memory_with_brca1())

    assert _payload(events, "guard") == {"passed": True, "category": "ok", "reason": None}
    user = _user_content_of_the_guard_call(_mock_litellm)
    assert "BRCA1" not in user and "SESSION MEMORY" not in user and "Established" not in user, user


@pytest.mark.asyncio
async def test_an_off_topic_verdict_stands_with_no_memory(
    _mock_litellm: AsyncMock,
) -> None:
    """The counterfactual for the arm above: the same reply, no memory."""
    _mock_litellm.return_value = _off_topic_reply()
    events, _ = await _run_guardrail("What variants cause it?")
    guard = _payload(events, "guard")
    assert guard is not None and guard["passed"] is False and guard["category"] == "off_topic"


@pytest.mark.asyncio
async def test_an_off_topic_verdict_stands_when_the_question_refers_to_nothing(
    _mock_litellm: AsyncMock,
) -> None:
    """Memory does not make every question on topic: no referring word, no
    set-aside. "Tell me a joke" stays refused in a BRCA1 session."""
    _mock_litellm.return_value = _off_topic_reply()
    events, _ = await _run_guardrail("Tell me a joke about weather", session_memory=_memory_with_brca1())
    guard = _payload(events, "guard")
    assert guard is not None and guard["passed"] is False and guard["category"] == "off_topic"


@pytest.mark.asyncio
async def test_an_injection_verdict_is_never_set_aside_by_memory(
    _mock_litellm: AsyncMock,
) -> None:
    """The rule is about a pronoun's subject, never about safety."""
    import json

    classification = json.loads(COMPLIANT_GUARD_CLASSIFICATION)
    classification["is_injection"] = True
    _mock_litellm.return_value = fake_response(json.dumps(classification))
    # Biomedical wording with a referring word, so the deterministic
    # prefilter admits it and the MODEL's verdict is the one under test.
    events, _ = await _run_guardrail(
        "Which variants of it are pathogenic?", session_memory=_memory_with_brca1()
    )
    guard = _payload(events, "guard")
    assert guard is not None and guard["passed"] is False and guard["category"] == "injection"


@pytest.mark.asyncio
async def test_a_first_turn_sends_no_session_memory_block(
    _mock_litellm: AsyncMock,
) -> None:
    """No memory, no block: the guard prompt never carries session memory,
    on a first turn or any other (see the set-aside arms above)."""
    await _run_guardrail("Which diseases are associated with BRCA1?")
    user = _user_content_of_the_guard_call(_mock_litellm)
    assert "SESSION MEMORY" not in user, user
    assert "session_memory" not in user, user


@pytest.mark.asyncio
async def test_one_unusable_reply_gets_one_more_attempt_and_a_parsed_one_is_final(
    _mock_litellm: AsyncMock,
) -> None:
    """Measured 2026-09-13: one Guard reply in thirteen was not the JSON
    object the instruction demands, and that run refused a question the
    other twelve admitted. `think_node` already gives the same failure a
    second attempt; the guardrail now does too.

    A REPLY THAT PARSED IS FINAL. The second attempt is only for a reply
    that said nothing usable, never a second opinion on a verdict, which is
    why the next arm pins that two unusable replies still fail closed.

    MUTATION PROOF: changing `for attempt in (1, 2)` to `(1,)` turns this arm
    red on the `passed` assertion.
    """
    _mock_litellm.side_effect = [
        fake_response("Sure! Here is my assessment: this looks on topic."),
        fake_response(COMPLIANT_GUARD_CLASSIFICATION),
    ]
    events, result = await _run_guardrail("Which diseases are associated with BRCA1?")
    assert _mock_litellm.await_count == 2
    assert _payload(events, "guard")["passed"] is True
    assert result.get("step_error") is None


@pytest.mark.asyncio
async def test_two_unusable_replies_still_fail_closed(
    _mock_litellm: AsyncMock,
) -> None:
    _mock_litellm.side_effect = [
        fake_response("I think this is fine, honestly"),
        fake_response("still not json"),
    ]
    events, result = await _run_guardrail("Which diseases are associated with BRCA1?")
    assert _mock_litellm.await_count == 2
    assert result.get("step_error") is not None
    assert result["step_error"]["source"] == "guardrail"
    guard = _payload(events, "guard")
    assert guard is None or guard["passed"] is False
