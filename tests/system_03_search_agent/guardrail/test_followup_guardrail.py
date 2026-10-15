"""Phase 8.6's re-land follow-up: the guardrail's R-05 and R-06, through the
real node.

## What these arms pin

- R-05 (F-8.6-RJ01, RJ08, RA02): the guard classifier's second attempt
  waits `_CLASSIFIER_RETRY_BACKOFF_S` after an ERROR, so an error lasting
  about a second no longer ends the question, and a rate-limiting provider
  is never sent more than the two requests of one attempt back to back.
  A provider's own `Retry-After` is honoured when it fits the budget; when
  it does not, no second attempt is made. A first attempt that ran out of
  time still gets its second at once (R-01, G-005). No verdict is still no
  answer, and no path passes the guardrail's budget.
- R-06 (F-8.6-RJ03, RJ09): in Jev mode, a refusal that only Jev's OWN
  relevancy pick could change waits no longer than Jev's own window
  (`_JEV_OWN_PICK_WINDOW_S`), not for the guard tier's fallback pick. The
  refusal is the same one, only sooner; Jev's own pick inside the window
  still decides exactly as before, through the real `decide()`.
- With the provider at its code default, R-06 changes nothing.

## What they do not cover

- A live provider's real rate limits or real `Retry-After` headers: every
  model reply below is a stub, the 429 included.
- How often a live classifier fails. The arms pin what the node does when
  it does.

Most arms keep the real constants and the real 15-second budget and run in
two or three seconds. The arms that walk every failure shape to its end
shrink the budget, and scale the backoff and the second attempt's floor
with it, so they run fast; those arms say so.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import Any
from unittest.mock import AsyncMock

import httpx
import litellm
import pytest

from system_03_search_agent.contracts.events import DecisionRecord
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import decide as decide_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness import jev_client as jev_client_module
from system_03_search_agent.harness.harness import HarnessCallError
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
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("CLASSIFIER_PROVIDER", raising=False)


@pytest.fixture(autouse=True)
def _no_daily_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", lambda *a, **k: None)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _prices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )


@pytest.fixture
def _jev_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")


_ADMIT = COMPLIANT_GUARD_CLASSIFICATION
_OFF_TOPIC = json.dumps({**json.loads(COMPLIANT_GUARD_CLASSIFICATION), "is_off_topic": True})
_ORDINARY_QUESTION = "Which diseases are associated with BRCA1?"
_TREE_OF_LIFE = "Tell me about the tree of life."
_STEP_ERROR = {
    "fatal": True,
    "scope": "step",
    "source": "guardrail",
    "error_class": "transient",
    "message": "A step in this query hit a temporary error. Retrying the query may succeed.",
    "retry_after_s": 0,
}


async def _run_guardrail(text: str) -> tuple[list[Any], dict[str, Any], Any]:
    from system_03_search_agent.contracts.query import Query, RequestContext

    trace_id = f"t-{uuid.uuid4().hex[:12]}"
    harness = harness_module.Harness(trace_id)
    state = {
        "query": Query(text=text, session_id="followup-guardrail-test", trace_id=trace_id),
        "context": RequestContext(surface="rest_sse"),
        "harness": harness,
        "seq": 0,
        "start_monotonic": time.monotonic(),
    }
    result = await graph_module.guardrail_node(state)  # type: ignore[arg-type]
    return list(result.get("events", [])), result, harness


def _guard(events: list[Any]) -> dict[str, Any] | None:
    return next((e.payload for e in events if e.type == "guard"), None)


def _rate_limited(retry_after: str | None = None) -> BaseException:
    headers = {"Retry-After": retry_after} if retry_after is not None else None
    return litellm.RateLimitError("rate limited (stub)", llm_provider="openrouter", model="m", headers=headers)


def _connection_error() -> BaseException:
    return litellm.APIConnectionError(message="connection reset (stub)", llm_provider="openrouter", model="m")


def _classifier(monkeypatch: pytest.MonkeyPatch, *behaviours: Any) -> list[float]:
    """Stub the guard classifier's requests, one behaviour per request, the
    last repeating: "hang" sleeps past any budget, a float answers `_ADMIT`
    after that many seconds, a callable returns an exception to raise or a
    reply's content, anything else is the reply's content. Returns the
    monotonic time of every request."""
    times: list[float] = []

    async def _acompletion(**_kwargs: Any) -> Any:
        behaviour = behaviours[min(len(times), len(behaviours) - 1)]
        times.append(time.monotonic())
        if behaviour == "hang":
            await asyncio.sleep(60)
            raise AssertionError("a hung request was never cut")
        if isinstance(behaviour, float):
            await asyncio.sleep(behaviour)
            return fake_response(_ADMIT)
        if callable(behaviour):
            behaviour = behaviour()
        if isinstance(behaviour, BaseException):
            raise behaviour
        return fake_response(behaviour)

    monkeypatch.setattr(harness_module.litellm, "acompletion", _acompletion)
    return times


def _gaps(times: list[float]) -> list[float]:
    return [later - earlier for earlier, later in itertools.pairwise(times)]


# ---------------------------------------------------------------------------
# R-05: how long the second attempt waits, read from the failure alone.
# ---------------------------------------------------------------------------


def _call_error(cause: BaseException | None, source: str = "harness.call_tier") -> HarnessCallError:
    error = HarnessCallError("stub", error_class="transient", source=source)
    error.__cause__ = cause
    return error


@pytest.mark.parametrize(
    ("error", "remaining_s", "wait_s"),
    [
        (_call_error(None, source="harness.enforce_timeout:guardrail"), 5.0, 0.0),
        (_call_error(_connection_error()), 15.0, 2.0),
        (_call_error(_connection_error()), 4.0, 1.0),
        (_call_error(_connection_error()), 2.5, 0.0),
        (_call_error(_rate_limited()), 15.0, 2.0),
        (_call_error(_rate_limited("3")), 15.0, 3.0),
        (_call_error(_rate_limited("0.5")), 15.0, 2.0),
        (_call_error(_rate_limited("12")), 15.0, 12.0),
        (_call_error(_rate_limited("12.5")), 15.0, None),
        (_call_error(_rate_limited("20")), 15.0, None),
        (_call_error(_rate_limited("soon")), 15.0, 2.0),
    ],
    ids=[
        "an attempt that ran out of time: at once",
        "an error, the budget untouched: the backoff",
        "an error, four seconds left: shortened to keep three",
        "an error, too little left for any wait: at once",
        "a rate limit naming no wait: the backoff",
        "a rate limit naming 3 s: 3 s",
        "a rate limit naming less than the backoff: the backoff",
        "a rate limit naming a wait that just fits",
        "a rate limit naming a wait that does not fit: no second attempt",
        "a rate limit naming 20 s: no second attempt",
        "a Retry-After that is not a wait: the backoff",
    ],
)
def test_the_second_attempts_wait(error: HarnessCallError, remaining_s: float, wait_s: float | None) -> None:
    assert graph_module._CLASSIFIER_RETRY_BACKOFF_S == 2.0
    assert graph_module._CLASSIFIER_MIN_SECOND_ATTEMPT_S == 3.0
    got = graph_module._classifier_retry_wait_s(error, remaining_s)
    if wait_s is None:
        assert got is None
    else:
        assert got == pytest.approx(wait_s)


@pytest.mark.parametrize("where", ["litellm_response_headers", "headers", "response"])
def test_retry_after_is_read_wherever_the_error_carries_it(where: str) -> None:
    cause = RuntimeError("429")
    cause.status_code = 429  # type: ignore[attr-defined]
    if where == "response":
        cause.response = httpx.Response(429, headers={"retry-after": "4"})  # type: ignore[attr-defined]
    else:
        setattr(cause, where, {"RETRY-AFTER": "4"})
    assert graph_module._classifier_retry_wait_s(_call_error(cause), 15.0) == pytest.approx(4.0)


def test_a_retry_after_date_is_read_as_a_wait() -> None:
    when = format_datetime(datetime.now(UTC) + timedelta(seconds=6), usegmt=True)
    wait = graph_module._classifier_retry_wait_s(_call_error(_rate_limited(when)), 15.0)
    assert wait is not None and 4.5 < wait <= 6.0


# ---------------------------------------------------------------------------
# R-05 through the real node, with the real constants and the real budget.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_error_lasting_about_a_second_no_longer_ends_the_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RJ08's `blip`: the provider errors for one second after the first
    request, then answers. Both of the first attempt's requests fail at
    once; the second attempt waits the backoff and is admitted.

    MUTATION PROOF: setting the backoff to 0.0 turns this red (the second
    attempt's requests land inside the error and the step error follows).
    """
    first: list[float] = []

    def _blip() -> Any:
        first.append(time.monotonic())
        return _connection_error() if time.monotonic() - first[0] < 1.0 else _ADMIT

    times = _classifier(monkeypatch, _blip)
    started = time.monotonic()
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    elapsed = time.monotonic() - started

    assert result.get("step_error") is None
    assert _guard(events) == {"passed": True, "category": "ok", "reason": None}
    assert len(times) == 3
    assert _gaps(times)[1] >= graph_module._CLASSIFIER_RETRY_BACKOFF_S
    assert elapsed < graph_module._CLASSIFIER_RETRY_BACKOFF_S + 1.0, elapsed


@pytest.mark.asyncio
async def test_a_rate_limit_storm_is_never_sent_more_than_two_requests_back_to_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RJ01 and RA02: every request is a 429 that names no wait. The provider
    gets `call_tier`'s own pair, then nothing for the backoff, then the
    second attempt's pair, and the question ends in the step error, not an
    answer. Before R-05 the four came within a hundredth of a second."""
    times = _classifier(monkeypatch, _rate_limited)
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)

    assert result.get("step_error") == _STEP_ERROR
    assert _guard(events) is None
    assert len(times) == 4
    gaps = _gaps(times)
    assert gaps[1] >= 2.0, gaps
    assert gaps[0] < 0.5 and gaps[2] < 0.5, gaps


@pytest.mark.asyncio
async def test_a_providers_retry_after_is_honoured_when_it_fits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    times = _classifier(monkeypatch, _rate_limited("3"), _rate_limited("3"), _ADMIT)
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    assert result.get("step_error") is None
    assert _guard(events) == {"passed": True, "category": "ok", "reason": None}
    assert len(times) == 3
    assert _gaps(times)[1] >= 3.0


@pytest.mark.asyncio
async def test_a_providers_retry_after_that_does_not_fit_gets_no_second_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    times = _classifier(monkeypatch, _rate_limited("20"))
    started = time.monotonic()
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    elapsed = time.monotonic() - started
    assert result.get("step_error") == _STEP_ERROR
    assert _guard(events) is None
    assert len(times) == 2
    assert elapsed < 1.0, elapsed


@pytest.mark.asyncio
async def test_a_hung_first_attempt_still_gets_its_second_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G-005's shape, R-01's fix, unchanged: no backoff after a timeout."""
    budget = graph_module.budget_for_step("guardrail", "lookup")
    first_attempt = budget * graph_module._CLASSIFIER_FIRST_ATTEMPT_SHARE
    times = _classifier(monkeypatch, "hang", _ADMIT)
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    assert result.get("step_error") is None
    assert _guard(events) == {"passed": True, "category": "ok", "reason": None}
    assert len(times) == 2
    assert _gaps(times)[0] == pytest.approx(first_attempt, abs=0.3)


# ---------------------------------------------------------------------------
# R-05: no path passes the budget, and no verdict is no answer. The budget
# is shrunk to 2.0 s and the backoff and floor scaled with it. The 0.3 s
# tolerance is scheduling lag on a loaded machine; it stays under one
# backoff, so a wait taken past the deadline is still caught.
# ---------------------------------------------------------------------------

_SHRUNK_BUDGET_S = 2.0
_LAG_S = 0.3


def _shrink(monkeypatch: pytest.MonkeyPatch) -> None:
    real_budget = graph_module.budget_for_step

    def _budget(step: str, query_class: Any) -> float:
        return _SHRUNK_BUDGET_S if step == "guardrail" else real_budget(step, query_class)

    monkeypatch.setattr(graph_module, "budget_for_step", _budget)
    monkeypatch.setattr(graph_module, "_CLASSIFIER_RETRY_BACKOFF_S", 0.5)
    monkeypatch.setattr(graph_module, "_CLASSIFIER_MIN_SECOND_ATTEMPT_S", 0.6)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "behaviours",
    [
        ("hang",),
        (_rate_limited,),
        (_rate_limited("0.6"), _rate_limited("0.6"), "hang"),
        (_connection_error, _connection_error, "hang"),
        (1.5, "hang"),
        (1.5,),
        (_rate_limited, _rate_limited, "hang"),
    ],
    ids=[
        "a hang every time",
        "a 429 every time",
        "429s naming a wait, then a hang",
        "two errors, then a hang",
        "a slow first reply cut, then a hang",
        "a provider slower than the second attempt's share",
        "429s naming none, then a hang",
    ],
)
async def test_no_verdict_is_no_answer_and_no_path_passes_the_budget(
    monkeypatch: pytest.MonkeyPatch, behaviours: tuple[Any, ...]
) -> None:
    _shrink(monkeypatch)
    _classifier(monkeypatch, *behaviours)
    started = time.monotonic()
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    elapsed = time.monotonic() - started
    assert result.get("step_error") == _STEP_ERROR
    assert _guard(events) is None
    assert elapsed < _SHRUNK_BUDGET_S + _LAG_S, elapsed


@pytest.mark.asyncio
async def test_with_jev_a_classifier_that_never_answers_is_never_an_admission(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None
) -> None:
    """Jev clearing the question cannot stand in for the guard classifier."""
    _shrink(monkeypatch)
    _classifier(monkeypatch, _connection_error)

    async def _call_jev(**_kwargs: Any) -> Any:
        from system_03_search_agent.harness.jev_client import JevResult

        return JevResult(
            resolved_model="jev-test", choice="not_injection", confidence=0.9,
            probabilities={"not_injection": 0.95, "injection": 0.05},
            input_tokens=1, output_tokens=1, cost_usd=0.00002, latency_ms=100,
        )

    monkeypatch.setattr(graph_module, "call_jev", _call_jev)
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    assert result.get("step_error") == _STEP_ERROR
    assert _guard(events) is None


# ---------------------------------------------------------------------------
# R-06: a refusal only Jev's own pick could change is not held for the guard
# tier's fallback.
# ---------------------------------------------------------------------------


def test_jevs_window_covers_decides_own_wait_for_jev() -> None:
    """If `decide()` ever waited longer for Jev than this window, a late
    Jev pick could be cut off here and a refusal made where it set one
    aside before. This keeps the two in step."""
    assert graph_module._JEV_OWN_PICK_WINDOW_S > decide_module._JEV_WAIT_S
    assert graph_module._JEV_OWN_PICK_WINDOW_S < graph_module.budget_for_step("guardrail", "lookup")


def _relevancy(
    monkeypatch: pytest.MonkeyPatch, *, after_s: float, pick: str, by: str
) -> list[str]:
    """Stub `decide()` for `guardrail.relevancy`: a record after `after_s`,
    Jev's own pick (`by` "jev") or the guard tier's after Jev failed."""
    asked: list[str] = []

    async def _decide(
        harness: Any, trace_id: str, point: str, state: str, options: Any, **kwargs: Any
    ) -> DecisionRecord:
        asked.append(point)
        await asyncio.sleep(after_s)
        if by == "jev":
            return DecisionRecord(
                name=point, options=list(options), chosen=pick, decided_by="jev",
                jev_choice=pick, jev_confidence=0.88, jev_latency_ms=140,
            )
        return DecisionRecord(
            name=point, options=list(options), chosen=pick, decided_by="guard",
            guard_choice=pick, fallback_reason="timeout",
        )

    monkeypatch.setattr(graph_module, "decide", _decide)
    return asked


def _jev_injection(monkeypatch: pytest.MonkeyPatch, pick: str) -> None:
    from system_03_search_agent.harness.jev_client import JevResult

    other = "not_injection" if pick == "injection" else "injection"

    async def _call_jev(**_kwargs: Any) -> Any:
        await asyncio.sleep(0.05)
        return JevResult(
            resolved_model="jev-test", choice=pick, confidence=0.7,
            probabilities={pick: 0.85, other: 0.15},
            input_tokens=1, output_tokens=1, cost_usd=0.00002, latency_ms=50,
        )

    monkeypatch.setattr(graph_module, "call_jev", _call_jev)


_FAST_WINDOW_S = 0.4
_SLOW_FALLBACK_S = 3.0


def _fast_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Jev's window shrunk so the arms run fast; the step budget stays real."""
    monkeypatch.setattr(graph_module, "_JEV_OWN_PICK_WINDOW_S", _FAST_WINDOW_S)


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback_pick", ["on_topic", "off_topic"])
async def test_with_jev_failing_an_off_topic_refusal_is_not_held_for_the_fallback(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None, fallback_pick: str
) -> None:
    """RJ03: the classifier says off topic at once and Jev's relevancy pick
    fails, so only the guard tier's fallback is left, and its pick never
    sets the refusal aside. The refusal comes at the end of Jev's window,
    not after the fallback, and it is the same off-topic refusal.

    MUTATION PROOF: reading the R-03 branch against `step_deadline` again
    turns this red on the elapsed time.
    """
    _fast_window(monkeypatch)
    _classifier(monkeypatch, _OFF_TOPIC)
    _jev_injection(monkeypatch, "not_injection")
    _relevancy(monkeypatch, after_s=_SLOW_FALLBACK_S, pick=fallback_pick, by="guard")

    started = time.monotonic()
    events, _, _ = await _run_guardrail(_TREE_OF_LIFE)
    elapsed = time.monotonic() - started

    guard = _guard(events)
    assert guard is not None and guard["passed"] is False and guard["category"] == "off_topic"
    assert elapsed < _FAST_WINDOW_S + 0.4, elapsed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("pick", "by", "passed", "category"),
    [
        ("on_topic", "jev", True, "ok"),
        ("off_topic", "jev", False, "off_topic"),
        ("on_topic", "guard", False, "off_topic"),
    ],
    ids=["Jev's own on_topic sets it aside", "Jev's own off_topic", "a fast fallback never sets it aside"],
)
async def test_with_jev_a_pick_inside_the_window_decides_as_before(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None, pick: str, by: str, passed: bool, category: str
) -> None:
    _fast_window(monkeypatch)
    _classifier(monkeypatch, _OFF_TOPIC)
    _jev_injection(monkeypatch, "not_injection")
    _relevancy(monkeypatch, after_s=0.1, pick=pick, by=by)
    events, _, _ = await _run_guardrail(_TREE_OF_LIFE)
    guard = _guard(events)
    assert guard is not None and guard["passed"] is passed and guard["category"] == category


@pytest.mark.asyncio
async def test_with_jev_a_late_jev_pick_through_the_real_decide_still_sets_the_refusal_aside(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None
) -> None:
    """The window is not a guess about Jev's speed: through the REAL
    `decide()` and the real constants, a Jev relevancy reply that comes back
    just inside Jev's own 3-second bound is still read and still sets the
    classifier's off-topic refusal aside, the tree-of-life admission R-03
    made, and no guard fallback is asked."""
    _classifier(monkeypatch, _OFF_TOPIC)
    _jev_injection(monkeypatch, "not_injection")
    fallback = AsyncMock(side_effect=AssertionError("the guard fallback is never asked"))
    monkeypatch.setattr(decide_module, "_guard_fallback_pick", fallback)

    async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
        key = next(iter(body["questions"]))
        await asyncio.sleep(jev_client_module.JEV_TOTAL_TIMEOUT_S - 0.2)
        return httpx.Response(
            200,
            json={
                "model": "jev-test",
                "answers": {key: {"choice": "on_topic", "confidence": 0.8,
                                  "probabilities": {"on_topic": 0.9, "off_topic": 0.1}}},
                "usage": {"input_tokens": 1, "output_tokens": 1, "cost": 0.00002},
            },
        )

    monkeypatch.setattr(jev_client_module, "_post", _post)
    events, _, harness = await _run_guardrail(_TREE_OF_LIFE)
    assert _guard(events) == {"passed": True, "category": "ok", "reason": None}
    record = next(r for r in graph_module._done_decisions(harness) or [] if r.name == "guardrail.relevancy")
    assert record.decided_by == "jev" and record.chosen == "on_topic"
    fallback.assert_not_called()


@pytest.mark.asyncio
async def test_with_jev_an_injection_refusal_is_not_held_for_the_relevancy_fallback(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None
) -> None:
    """RJ09: the classifier admits, Jev calls the text injection, and Jev's
    relevancy pick fails. The injection refusal comes at the end of Jev's
    window, not after the guard tier's fallback."""
    _fast_window(monkeypatch)
    _classifier(monkeypatch, _ADMIT)
    _jev_injection(monkeypatch, "injection")
    _relevancy(monkeypatch, after_s=_SLOW_FALLBACK_S, pick="on_topic", by="guard")

    started = time.monotonic()
    events, _, _ = await _run_guardrail(_TREE_OF_LIFE)
    elapsed = time.monotonic() - started

    guard = _guard(events)
    assert guard is not None and guard["passed"] is False and guard["category"] == "injection"
    assert elapsed < _FAST_WINDOW_S + 0.4, elapsed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("pick", "category"),
    [("off_topic", "off_topic"), ("on_topic", "injection")],
)
async def test_with_jev_an_injection_refusal_keeps_the_category_jevs_own_relevancy_gives(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None, pick: str, category: str
) -> None:
    """Inside Jev's window its own relevancy pick decides the category, as
    before: off topic when it says so, injection otherwise."""
    _fast_window(monkeypatch)
    _classifier(monkeypatch, _ADMIT)
    _jev_injection(monkeypatch, "injection")
    _relevancy(monkeypatch, after_s=0.1, pick=pick, by="jev")
    events, _, _ = await _run_guardrail(_TREE_OF_LIFE)
    guard = _guard(events)
    assert guard is not None and guard["passed"] is False and guard["category"] == category


@pytest.mark.asyncio
async def test_with_the_default_provider_the_window_changes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production's setting: the guard tier's relevancy pick is the only
    one, and it is waited for within the step's budget exactly as before,
    past any Jev window."""
    _fast_window(monkeypatch)
    _classifier(monkeypatch, _ADMIT)
    asked = _relevancy(monkeypatch, after_s=_FAST_WINDOW_S + 0.4, pick="off_topic", by="guard")
    events, _, _ = await _run_guardrail(_TREE_OF_LIFE)
    guard = _guard(events)
    assert asked == ["guardrail.relevancy"]
    assert guard is not None and guard["passed"] is False and guard["category"] == "off_topic"


def test_the_stub_classifier_replies_parse() -> None:
    """The two stub replies above are what they claim to be."""
    from system_03_search_agent.guardrail import classifier

    admitted = classifier.verdict_for(classifier.parse_classification(_ADMIT))
    off = classifier.verdict_for(classifier.parse_classification(_OFF_TOPIC))
    assert admitted.admitted is True
    assert off.admitted is False and off.category == "off_topic"


# ---------------------------------------------------------------------------
# R-08 (F-8.6-RJ10): two unusable classifier replies tell the person what to
# do next, not an internal part's name.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "behaviours",
    [("I will look this up.",), ("hang", "I will look this up.")],
    ids=["two unusable replies", "a hang, then an unusable reply"],
)
async def test_no_usable_verdict_says_what_to_do_next(
    monkeypatch: pytest.MonkeyPatch, behaviours: tuple[Any, ...]
) -> None:
    """MUTATION PROOF: returning the parse error's own text again turns this
    red on the message.

    Fix round, A-GR-10: the class is "transient", the guardrail's own check
    not finishing, so the web app reads its guardrail words; "recoverable"
    is left to failures the question caused (content policy, a 400)."""
    _shrink(monkeypatch)
    _classifier(monkeypatch, *behaviours)
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    assert _guard(events) is None
    assert result.get("step_error") == {
        "fatal": True,
        "scope": "step",
        "source": "guardrail",
        "error_class": "transient",
        "message": "A step in this query could not complete. Retrying the query may succeed.",
        "retry_after_s": 0,
    }


# ---------------------------------------------------------------------------
# Fix round of the guardrail design, A-GR-10: the class a guardrail failure
# carries on the wire is what the web app reads to choose its words, so each
# kind of failure carries its own category. Only the guardrail's own check
# not finishing is "transient"; a failure the question caused is
# "recoverable"; one asking again cannot fix is "unexpected".
# ---------------------------------------------------------------------------


def _content_policy() -> BaseException:
    return litellm.ContentPolicyViolationError(
        message="content policy (stub)", model="m", llm_provider="openrouter"
    )


def _bad_request() -> BaseException:
    return litellm.BadRequestError("bad request (stub)", model="m", llm_provider="openrouter")


def _unauthorised() -> BaseException:
    return litellm.AuthenticationError(message="401 (stub)", llm_provider="openrouter", model="m")


_FAILURE_KINDS = [
    ("both attempts time out", ("hang",), "transient"),
    ("two unreadable replies", ("I will look this up.",), "transient"),
    ("a content-policy refusal", (_content_policy,), "recoverable"),
    ("a 400", (_bad_request,), "recoverable"),
    ("a 401", (_unauthorised,), "unexpected"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("behaviours", "error_class"), [k[1:] for k in _FAILURE_KINDS], ids=[k[0] for k in _FAILURE_KINDS]
)
async def test_each_kind_of_guardrail_failure_carries_its_own_category(
    monkeypatch: pytest.MonkeyPatch, behaviours: tuple[Any, ...], error_class: str
) -> None:
    """A-GR-10: the web app shows "a problem on our side, try asking again"
    for a guardrail failure of class "transient" only. A content-policy
    refusal or a 400 is caused by the question and stays "recoverable" (its
    words say to rephrase); a 401 stays "unexpected" (asking again cannot
    fix it). Two unreadable replies are the check not finishing, so they
    are "transient" like two timeouts.

    MUTATION PROOF: the unusable-verdict error back at "recoverable" turns
    the unreadable arm red."""
    _shrink(monkeypatch)
    _classifier(monkeypatch, *behaviours)
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    assert _guard(events) is None
    step_error = result.get("step_error")
    assert step_error is not None
    assert (step_error["source"], step_error["error_class"]) == ("guardrail", error_class)
