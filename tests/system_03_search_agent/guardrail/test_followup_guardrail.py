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
- R-06 (F-8.6-RJ03, RJ09), then step 3b of the guardrail design
  (F-8.6-FA03, F-72-J03, J07): in Jev mode, a refusal that only Jev's OWN
  relevancy pick could change waits only until `decide()` says Jev failed
  (`jev_failed`), not for the guard tier's fallback pick, and never on a
  clock of its own: a server pause that delays Jev's request no longer cuts
  off a pick Jev delivers inside its own bound, and every clock on Jev
  counts only time the server was free, up to `JEV_STALL_ALLOWANCE_S`. The
  refusal is the same one, only sooner; Jev's own pick still decides
  exactly as before, through the real `decide()`. Six pause arms and the
  mid-wait arm run on the virtual clock (`tests/system_03_search_agent/
  virtual_clock.py`).
- With the provider at its code default, the signal changes nothing.

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
from collections.abc import Callable
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
from tests.system_03_search_agent.virtual_clock import run_virtual


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
        "start_monotonic": graph_module.time.monotonic(),
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
    after that many seconds, a tuple `(seconds, behaviour)` waits and then
    takes `behaviour`, a callable returns an exception to raise or a reply's
    content, anything else is the reply's content. Returns the running
    loop's time of every request, so it works on the virtual clock too."""
    times: list[float] = []

    async def _acompletion(**_kwargs: Any) -> Any:
        behaviour = behaviours[min(len(times), len(behaviours) - 1)]
        times.append(asyncio.get_running_loop().time())
        if isinstance(behaviour, str) and behaviour == "hang":
            await asyncio.sleep(60)
            raise AssertionError("a hung request was never cut")
        if isinstance(behaviour, tuple):
            delay, behaviour = behaviour
            await asyncio.sleep(delay)
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
# R-06, then step 3b of the guardrail design (F-8.6-FA03, F-72-J03, J07): a
# refusal only Jev's own pick could change is not held for the guard tier's
# fallback, and it waits on `decide()`'s own signal that Jev failed, never on
# a clock of its own.
# ---------------------------------------------------------------------------


def test_the_guardrail_has_no_clock_of_its_own_for_jevs_pick() -> None:
    """R-06's window, 3.75 s from the decision's start, is gone: a server
    pause that moved Jev's request later cut off a pick Jev still delivered
    inside its own bound (FA03). The stall arms below prove the behaviour;
    this keeps the clock from coming back by name."""
    assert not hasattr(graph_module, "_JEV_OWN_PICK_WINDOW_S")
    assert not hasattr(graph_module, "_jev_own_pick_deadline")
    assert jev_client_module.JEV_STALL_ALLOWANCE_S == 2.0


def _jev_reply(choice: str, other: str, *, after_s: float) -> Any:
    """A `jev_client._post` stand-in: Jev's real reply shape, `after_s` late."""

    async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
        key = next(iter(body["questions"]))
        await asyncio.sleep(after_s)
        return httpx.Response(
            200,
            json={
                "model": "jev-test",
                "answers": {key: {"choice": choice, "confidence": 0.8, "probabilities": {choice: 0.9, other: 0.1}}},
                "usage": {"input_tokens": 1, "output_tokens": 1, "cost": 0.00002},
            },
        )

    return _post


@pytest.mark.asyncio
async def test_decide_says_jev_failed_before_it_asks_the_guard_tier(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None
) -> None:
    """The signal itself, through the real `decide()`: set once Jev fails,
    and set BEFORE the guard tier's fallback is asked, so a caller waiting
    on it never waits for that fallback.

    MUTATION PROOF: setting the event after the fallback instead turns this
    red (`[False]`)."""
    seen_when_guard_asked: list[bool] = []
    failed = asyncio.Event()

    async def _fallback(*_args: Any, **_kwargs: Any) -> str:
        seen_when_guard_asked.append(failed.is_set())
        return "on_topic"

    async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
        return httpx.Response(503, content=b"unavailable")

    monkeypatch.setattr(jev_client_module, "_post", _post)
    monkeypatch.setattr(decide_module, "_guard_fallback_pick", _fallback)
    harness = harness_module.Harness("t-signal")
    record = await decide_module.decide(
        harness, "t-signal", "guardrail.relevancy", "x", ["on_topic", "off_topic"], jev_failed=failed
    )
    assert record.decided_by == "guard" and record.fallback_reason == "http_error"
    assert seen_when_guard_asked == [True]


@pytest.mark.asyncio
async def test_decide_never_says_jev_failed_when_jev_picked(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None
) -> None:
    monkeypatch.setattr(jev_client_module, "_post", _jev_reply("on_topic", "off_topic", after_s=0.0))
    failed = asyncio.Event()
    harness = harness_module.Harness("t-picked")
    record = await decide_module.decide(
        harness, "t-picked", "guardrail.relevancy", "x", ["on_topic", "off_topic"], jev_failed=failed
    )
    assert record.decided_by == "jev"
    assert not failed.is_set()


@pytest.mark.asyncio
async def test_with_the_guard_provider_decide_says_at_once_that_jev_will_not_pick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _classifier(monkeypatch, "on_topic")
    failed = asyncio.Event()
    harness = harness_module.Harness("t-guard")
    await decide_module.decide(
        harness, "t-guard", "guardrail.relevancy", "x", ["on_topic", "off_topic"], jev_failed=failed
    )
    assert failed.is_set()


def _relevancy(
    monkeypatch: pytest.MonkeyPatch, *, after_s: float, pick: str, by: str
) -> list[str]:
    """Stub `decide()` for `guardrail.relevancy`: a record after `after_s`,
    Jev's own pick (`by` "jev") or the guard tier's after Jev failed. When
    Jev failed, the stub says so at once through `jev_failed`, exactly as
    the real `decide()` does before it asks the guard tier."""
    asked: list[str] = []

    async def _decide(
        harness: Any, trace_id: str, point: str, state: str, options: Any, **kwargs: Any
    ) -> DecisionRecord:
        asked.append(point)
        if by != "jev" and kwargs.get("jev_failed") is not None:
            kwargs["jev_failed"].set()
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


_SLOW_FALLBACK_S = 3.0


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback_pick", ["on_topic", "off_topic"])
async def test_with_jev_failing_an_off_topic_refusal_is_not_held_for_the_fallback(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None, fallback_pick: str
) -> None:
    """RJ03: the classifier says off topic at once and Jev's relevancy pick
    fails, so only the guard tier's fallback is left, and its pick never
    sets the refusal aside. The refusal comes when Jev says it failed, not
    after the fallback, and it is the same off-topic refusal.

    MUTATION PROOF: reading the R-03 branch against `step_deadline` again
    turns this red on the elapsed time.
    """
    _classifier(monkeypatch, _OFF_TOPIC)
    _jev_injection(monkeypatch, "not_injection")
    _relevancy(monkeypatch, after_s=_SLOW_FALLBACK_S, pick=fallback_pick, by="guard")

    started = time.monotonic()
    events, _, _ = await _run_guardrail(_TREE_OF_LIFE)
    elapsed = time.monotonic() - started

    guard = _guard(events)
    assert guard is not None and guard["passed"] is False and guard["category"] == "off_topic"
    assert elapsed < 1.0, elapsed


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
async def test_with_jev_its_own_pick_decides_as_before(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None, pick: str, by: str, passed: bool, category: str
) -> None:
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
    """Through the REAL `decide()` and the real constants, a Jev relevancy
    reply that comes back just inside Jev's own 3-second bound is still
    read and still sets the classifier's off-topic refusal aside, the
    tree-of-life admission R-03 made, and no guard fallback is asked."""
    _classifier(monkeypatch, _OFF_TOPIC)
    _jev_injection(monkeypatch, "not_injection")
    fallback = AsyncMock(side_effect=AssertionError("the guard fallback is never asked"))
    monkeypatch.setattr(decide_module, "_guard_fallback_pick", fallback)
    monkeypatch.setattr(
        jev_client_module, "_post", _jev_reply("on_topic", "off_topic", after_s=jev_client_module.JEV_TOTAL_TIMEOUT_S - 0.2)
    )
    events, _, harness = await _run_guardrail(_TREE_OF_LIFE)
    assert _guard(events) == {"passed": True, "category": "ok", "reason": None}
    record = next(r for r in graph_module._done_decisions(harness) or [] if r.name == "guardrail.relevancy")
    assert record.decided_by == "jev" and record.chosen == "on_topic"
    fallback.assert_not_called()


def _node(monkeypatch: pytest.MonkeyPatch, text: str) -> tuple[list[Any], dict[str, Any], Any, float]:
    """The real node on the virtual clock, with the real budget and the real
    constants: (events, result, harness, seconds it took)."""

    async def _go() -> tuple[list[Any], dict[str, Any], Any, float]:
        started = asyncio.get_running_loop().time()
        events, result, harness = await _run_guardrail(text)
        return events, result, harness, asyncio.get_running_loop().time() - started

    return run_virtual(monkeypatch, _go)


class _StallingCostControl:
    """`decide`'s view of `cost_control`, whose per-query cap check pauses
    the server once, blocking, before Jev's request: the judge's spot for
    F-72-J03, inside `decide()`'s outer net and before Jev's own bound."""

    def __init__(self, stall: Callable[[], None]) -> None:
        self._stall = stall
        self._stalled = False

    def __getattr__(self, name: str) -> Any:
        return getattr(cost_control, name)

    def check_per_query_cap(self, *args: Any, **kwargs: Any) -> None:
        if not self._stalled:
            self._stalled = True
            self._stall()
        cost_control.check_per_query_cap(*args, **kwargs)


def _stall_jevs_wait(monkeypatch: pytest.MonkeyPatch, where: str, stall_s: float) -> None:
    """Jev's relevancy pick answers on topic 2.9 s after its request, inside
    its own 3-second bound, and the server pauses once, for `stall_s`,
    `where` in Jev's wait."""

    def _stall() -> None:
        decide_module.time.sleep(stall_s)  # the virtual clock's blocking pause

    if where == "while Jev's model is resolved":
        real_model = decide_module.resolve_jev_model
        monkeypatch.setattr(decide_module, "resolve_jev_model", lambda: (_stall(), real_model())[1])
    elif where == "in the cap check inside Jev's wait":
        monkeypatch.setattr(decide_module, "cost_control", _StallingCostControl(_stall))
    reply = _jev_reply("on_topic", "off_topic", after_s=0.0)

    async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
        if where == "while Jev's reply is read":
            await asyncio.sleep(2.5)
            _stall()  # the reply arrives at 2.9 s, inside the pause
        elif where == "as Jev's request is sent":
            _stall()  # inside Jev's own bound, before the request goes out
            await asyncio.sleep(2.9)
        elif where == "before Jev's reply arrives":
            await asyncio.sleep(2.5)
            _stall()  # the pause ends past Jev's own bound on the wall clock
            await asyncio.sleep(0.1)  # and the reply comes 2.6 s of free time in
        else:
            await asyncio.sleep(2.9)
        return await reply(headers, body)

    monkeypatch.setattr(jev_client_module, "_post", _post)


_STALLS = [
    ("while Jev's model is resolved", 1.0),
    ("in the cap check inside Jev's wait", 0.6),
    ("in the cap check inside Jev's wait", 0.8),
    ("while Jev's reply is read", 0.6),
    ("while Jev's reply is read", 1.0),
    ("before Jev's reply arrives", 0.6),
]


@pytest.mark.parametrize(("where", "stall_s"), _STALLS, ids=[f"{s}s {w}" for w, s in _STALLS])
def test_with_jev_a_pause_anywhere_in_jevs_wait_never_turns_its_admission_into_a_refusal(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None, where: str, stall_s: float
) -> None:
    """F-8.6-FA03, which F-72-J03 found still open, through the real
    `decide()`, the real `jev_client` and the real constants on the virtual
    clock. The classifier says off topic; Jev's relevancy pick says on topic
    2.9 s after its request. The server's event loop pauses once, blocking,
    somewhere inside Jev's wait: before `decide()`'s net is armed, in the cap
    check inside it before Jev's request, while Jev's reply is read, or just
    before it arrives. On develop the 0.6 s and 0.8 s pauses in the cap
    check spent the net's half-second margin, and the pause before the
    reply pushed Jev past its own 3 s bound on the wall clock: the question
    was refused as off topic. Now every clock on Jev counts only time the
    loop was free, and Jev's admission stands.

    MUTATION PROOF: `wait_counting_free_time` counting real time again
    (`counted += now - last`) turns the 0.8 s cap-check arm and the "before
    Jev's reply arrives" arm red: the question is refused as off topic. The
    reply-read arms stay green under it, because a reply already in hand
    wins over the clock whatever the time."""
    _classifier(monkeypatch, _OFF_TOPIC)
    _jev_injection(monkeypatch, "not_injection")
    fallback = AsyncMock(side_effect=AssertionError("the guard fallback is never asked"))
    monkeypatch.setattr(decide_module, "_guard_fallback_pick", fallback)
    _stall_jevs_wait(monkeypatch, where, stall_s)

    events, _, harness, elapsed = _node(monkeypatch, _TREE_OF_LIFE)

    assert _guard(events) == {"passed": True, "category": "ok", "reason": None}
    assert elapsed > jev_client_module.JEV_TOTAL_TIMEOUT_S, elapsed  # past Jev's own bound on the wall clock
    record = next(r for r in graph_module._done_decisions(harness) or [] if r.name == "guardrail.relevancy")
    assert record.decided_by == "jev" and record.chosen == "on_topic"
    fallback.assert_not_called()


def test_with_jev_a_pause_past_the_allowance_still_ends_jevs_clock(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None
) -> None:
    """The residual both reviews named, pinned as the code does it (fix
    round, J-GR-02): Jev's clock ends at its 3 s bound plus the 2 s
    allowance of real time from when its wait began, whatever the pause. A
    2.5 s pause as Jev's request is sent, then a reply 2.9 s later, comes at
    5.4 s, past the 5 s, so Jev's clock has ended and the classifier's
    off-topic refusal stands; the guard tier's fallback, even saying on
    topic, never sets it aside. It is the reply's lateness past the 5 s that
    refuses, not the pause's length: a 4.7 s pause before a 0.2 s reply is
    still read (`test_with_jev_a_long_pause_before_a_fast_reply_is_still_read`
    below). Nothing is admitted that the guard model refused without Jev's
    own pick. The same pause under the allowance admits (the arms above)."""
    _classifier(monkeypatch, _OFF_TOPIC)
    _jev_injection(monkeypatch, "not_injection")
    monkeypatch.setattr(decide_module, "_guard_fallback_pick", AsyncMock(return_value="on_topic"))
    _stall_jevs_wait(monkeypatch, "as Jev's request is sent", 2.5)

    events, _, _, _ = _node(monkeypatch, _TREE_OF_LIFE)

    guard = _guard(events)
    assert guard is not None and guard["passed"] is False and guard["category"] == "off_topic"


def test_with_jev_a_long_pause_before_a_fast_reply_is_still_read(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None
) -> None:
    """J-GR-02, the true statement pinned through the real node: a pause is
    not refused for being over 2 s. The server pauses 4.7 s as Jev's request
    is sent and Jev answers on topic 0.2 s later, at 4.9 s, inside its bound
    plus the allowance, so Jev's pick is read and sets the classifier's
    off-topic verdict aside, as with no pause."""
    _classifier(monkeypatch, _OFF_TOPIC)
    _jev_injection(monkeypatch, "not_injection")
    monkeypatch.setattr(decide_module, "_guard_fallback_pick", AsyncMock(return_value="off_topic"))
    reply = _jev_reply("on_topic", "off_topic", after_s=0.0)

    async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
        decide_module.time.sleep(4.7)  # the virtual clock's blocking pause
        await asyncio.sleep(0.2)
        return await reply(headers, body)

    monkeypatch.setattr(jev_client_module, "_post", _post)
    events, _, _, elapsed = _node(monkeypatch, _TREE_OF_LIFE)
    assert _guard(events) == {"passed": True, "category": "ok", "reason": None}
    assert elapsed == pytest.approx(4.9, abs=0.06)


def test_with_jev_a_failure_signalled_mid_wait_ends_the_wait_at_once(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None
) -> None:
    """F-72-J07: the live order, which every stub arm above skips. The
    classifier says off topic at 0.05 s, so the guardrail is already
    waiting when Jev fails at 2 s and `decide()` says so; the guard tier's
    fallback would take 5 s more. The off-topic refusal comes at 2 s, not
    7 s.

    MUTATION PROOF: `_await_jev_own_pick` ignoring the event (waiting only
    on the decision and the deadline) turns this red: 7.0 s."""
    _classifier(monkeypatch, (0.05, _OFF_TOPIC))
    _jev_injection(monkeypatch, "not_injection")

    async def _decide(
        harness: Any, trace_id: str, point: str, state: str, options: Any, **kwargs: Any
    ) -> DecisionRecord:
        await asyncio.sleep(2.0)
        kwargs["jev_failed"].set()
        await asyncio.sleep(5.0)
        return DecisionRecord(
            name=point, options=list(options), chosen="on_topic", decided_by="guard",
            guard_choice="on_topic", fallback_reason="timeout",
        )

    monkeypatch.setattr(graph_module, "decide", _decide)
    events, _, _, elapsed = _node(monkeypatch, _TREE_OF_LIFE)
    guard = _guard(events)
    assert guard is not None and guard["passed"] is False and guard["category"] == "off_topic"
    assert elapsed == pytest.approx(2.0, abs=0.01)


@pytest.mark.asyncio
async def test_with_jev_an_injection_refusal_is_not_held_for_the_relevancy_fallback(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None
) -> None:
    """RJ09: the classifier admits, Jev calls the text injection, and Jev's
    relevancy pick fails. The injection refusal comes when Jev says it
    failed, not after the guard tier's fallback."""
    _classifier(monkeypatch, _ADMIT)
    _jev_injection(monkeypatch, "injection")
    _relevancy(monkeypatch, after_s=_SLOW_FALLBACK_S, pick="on_topic", by="guard")

    started = time.monotonic()
    events, _, _ = await _run_guardrail(_TREE_OF_LIFE)
    elapsed = time.monotonic() - started

    guard = _guard(events)
    assert guard is not None and guard["passed"] is False and guard["category"] == "injection"
    assert elapsed < 1.0, elapsed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("pick", "category"),
    [("off_topic", "off_topic"), ("on_topic", "injection")],
)
async def test_with_jev_an_injection_refusal_keeps_the_category_jevs_own_relevancy_gives(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None, pick: str, category: str
) -> None:
    """Jev's own relevancy pick decides the category, as before: off topic
    when it says so, injection otherwise."""
    _classifier(monkeypatch, _ADMIT)
    _jev_injection(monkeypatch, "injection")
    _relevancy(monkeypatch, after_s=0.1, pick=pick, by="jev")
    events, _, _ = await _run_guardrail(_TREE_OF_LIFE)
    guard = _guard(events)
    assert guard is not None and guard["passed"] is False and guard["category"] == category


@pytest.mark.asyncio
async def test_with_the_default_provider_the_signal_changes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production's code default: the guard tier's relevancy pick is the
    only one, and it is waited for within the step's budget exactly as
    before, whatever the signal says (the stub sets it at once)."""
    _classifier(monkeypatch, _ADMIT)
    asked = _relevancy(monkeypatch, after_s=0.8, pick="off_topic", by="guard")
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
    red on the message."""
    _shrink(monkeypatch)
    _classifier(monkeypatch, *behaviours)
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    assert _guard(events) is None
    assert result.get("step_error") == {
        "fatal": True,
        "scope": "step",
        "source": "guardrail",
        "error_class": "recoverable",
        "message": "A step in this query could not complete. Retrying the query may succeed.",
        "retry_after_s": 0,
    }

