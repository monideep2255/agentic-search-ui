"""Phase 8.6's re-land follow-up: the guardrail's R-05 and R-06, through the
real node.

## What these arms pin

- R-05 (F-8.6-RJ01, RJ08, RA02): the guard classifier's second request
  waits `_CLASSIFIER_RETRY_BACKOFF_S` after an ERROR, so an error lasting
  about a second no longer ends the question. A provider's own
  `Retry-After` is honoured when it fits the budget; when it does not, no
  second request is made.
- Card 72, option A, and R-10 (F-8.6-FJ11, FJ04, FA05, FA02): a first
  request unanswered after `_CLASSIFIER_HEDGE_AFTER_S` gets an identical
  second beside it, the first not cancelled; the first usable reply wins
  and the other is cancelled and charged as a cancelled call. Two requests
  at most, in flight or in total, a rate limit included. The backoff never
  carries the second request past the hedge point. A `Retry-After` is
  honoured whichever request carried it, and a rate limit tells the person
  to try again later, with `retry_after_s` the provider's wait. Each
  request is logged with its time and the upstream host (D's logging). No
  verdict is still no answer, and no path passes the guardrail's budget.
- R-06 (F-8.6-RJ03, RJ09), then R-10 (F-8.6-FA03): in Jev mode, a refusal
  that only Jev's OWN relevancy pick could change waits only until
  `decide()` says Jev failed (`jev_failed`), not for the guard tier's
  fallback pick, and never on a clock of its own: a stalled event loop
  that delays Jev's request no longer cuts off a pick Jev delivers inside
  its own bound. The refusal is the same one, only sooner; Jev's own pick
  still decides exactly as before, through the real `decide()`.
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
import logging
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


def _unavailable() -> BaseException:
    return litellm.ServiceUnavailableError(message="503 (stub)", llm_provider="openrouter", model="m")


#: What the `_prices` fixture's prices make a guard request cost: one that
#: answered (`fake_response`'s 10 prompt and 5 completion tokens), and one
#: cancelled, which `call_tier` charges the tier's whole output ceiling.
_ANSWERED_GUARD_CALL = 10 * 1e-6 + 5 * 2e-6
_CANCELLED_GUARD_CALL = harness_module._TIER_MAX_TOKENS["guard"] * 2e-6


class _Requests(list):  # type: ignore[type-arg]
    """The monotonic time of every classifier request, plus the most that
    were ever in flight at once and the numbers of those cancelled."""

    def __init__(self) -> None:
        super().__init__()
        self.peak = 0
        self.cancelled: list[int] = []


def _classifier(monkeypatch: pytest.MonkeyPatch, *behaviours: Any) -> _Requests:
    """Stub the guard classifier's requests, one behaviour per request, the
    last repeating: "hang" sleeps past any budget, a float answers `_ADMIT`
    after that many seconds, a tuple `(seconds, outcome[, upstream host])`
    waits and then takes `outcome`, a callable returns an exception to raise
    or a reply's content, anything else is the reply's content."""
    times = _Requests()
    active = [0]

    async def _acompletion(**_kwargs: Any) -> Any:
        behaviour = behaviours[min(len(times), len(behaviours) - 1)]
        times.append(time.monotonic())
        number = len(times)
        active[0] += 1
        times.peak = max(times.peak, active[0])
        try:
            if isinstance(behaviour, str) and behaviour == "hang":
                await asyncio.sleep(60)
                raise AssertionError("a hung request was never cut")
            provider = None
            if isinstance(behaviour, tuple):
                delay, behaviour, *rest = behaviour
                provider = rest[0] if rest else None
                await asyncio.sleep(delay)
            elif isinstance(behaviour, float):
                await asyncio.sleep(behaviour)
                behaviour = _ADMIT
            if callable(behaviour):
                behaviour = behaviour()
            if isinstance(behaviour, BaseException):
                raise behaviour
            reply = fake_response(behaviour)
            if provider is not None:
                reply.provider = provider
            return reply
        except asyncio.CancelledError:
            times.cancelled.append(number)
            raise
        finally:
            active[0] -= 1

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


@pytest.mark.parametrize(
    ("error", "first_elapsed_s", "wait_s"),
    [
        (_call_error(_connection_error()), 1.0, 2.0),
        (_call_error(_connection_error()), 3.5, 0.5),
        (_call_error(_connection_error()), 3.9, pytest.approx(0.1)),
        (_call_error(_connection_error()), 5.0, 0.0),
        (_call_error(_rate_limited("3")), 3.9, 3.0),
    ],
    ids=[
        "an error well before the hedge point: the backoff",
        "an error half a second before it: half a second",
        "an error just before it: what is left",
        "an error after it: at once",
        "a stated Retry-After is never cut to the hedge point",
    ],
)
def test_the_backoff_never_passes_the_hedge_point(
    error: HarnessCallError, first_elapsed_s: float, wait_s: Any
) -> None:
    """R-10 (F-8.6-FJ11): the second request is never sent later than the
    hedge would have sent it, `_CLASSIFIER_HEDGE_AFTER_S` after the first,
    unless the provider itself named a later time."""
    assert graph_module._CLASSIFIER_HEDGE_AFTER_S == 4.0
    got = graph_module._classifier_retry_wait_s(error, 15.0, first_elapsed_s)
    assert got == (wait_s if not isinstance(wait_s, float) else pytest.approx(wait_s))


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
# R-05, R-10 and card 72 through the real node, with the real constants and
# the real 15-second budget.
# ---------------------------------------------------------------------------

_BUSY_NO_WAIT = (
    "The service that checks each question is busy right now. Wait a little before trying the query again."
)


def _busy(seconds: int) -> str:
    return (
        "The service that checks each question is busy right now. "
        f"Try the query again in about {seconds} seconds, not straight away."
    )


def _rate_limit_error(retry_after_s: int | None) -> dict[str, Any]:
    return {
        "fatal": True,
        "scope": "step",
        "source": "guardrail",
        "error_class": "transient",
        "message": _BUSY_NO_WAIT if retry_after_s is None else _busy(retry_after_s),
        "retry_after_s": retry_after_s or 0,
    }


@pytest.mark.asyncio
async def test_an_error_lasting_about_a_second_no_longer_ends_the_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RJ08's `blip`: the provider errors for one second after the first
    request, then answers. The first request fails at once; the second
    waits the backoff and is admitted.

    MUTATION PROOF: setting the backoff to 0.0 turns this red (the second
    request lands inside the error and the step error follows).
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
    assert len(times) == 2
    assert _gaps(times)[0] >= graph_module._CLASSIFIER_RETRY_BACKOFF_S
    assert elapsed < graph_module._CLASSIFIER_RETRY_BACKOFF_S + 1.0, elapsed


@pytest.mark.asyncio
async def test_a_rate_limit_storm_costs_two_requests_and_says_to_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-10 (F-8.6-FJ04, FA02): every request is a 429 that names no wait.
    The provider gets two requests in all, the backoff between them, never
    four; and the person is told to wait, not to retry now. Before R-10 it
    was four requests in two back-to-back pairs and "Retrying the query may
    succeed".

    MUTATION PROOF: calling `call_tier` with its own retry again
    (`retry=True`) turns this red on the request count.
    """
    times = _classifier(monkeypatch, _rate_limited)
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)

    assert result.get("step_error") == _rate_limit_error(None)
    assert _guard(events) is None
    assert len(times) == 2
    assert _gaps(times)[0] >= graph_module._CLASSIFIER_RETRY_BACKOFF_S


@pytest.mark.asyncio
async def test_a_providers_retry_after_is_honoured_when_it_fits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    times = _classifier(monkeypatch, _rate_limited("3"), _ADMIT)
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    assert result.get("step_error") is None
    assert _guard(events) == {"passed": True, "category": "ok", "reason": None}
    assert len(times) == 2
    assert _gaps(times)[0] >= 3.0


@pytest.mark.asyncio
async def test_a_retry_after_that_does_not_fit_says_when_to_come_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-10 (F-8.6-FA02): the provider says wait 20 s, which the budget
    cannot fit. No second request, at once, and the person is told to try
    again in about 20 seconds, with `retry_after_s` 20, not 0.

    MUTATION PROOF: ending this path with `_step_error_kwargs` again, R-05's
    "Retrying the query may succeed" and `retry_after_s: 0`, turns this red.
    """
    times = _classifier(monkeypatch, _rate_limited("20"))
    started = time.monotonic()
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    elapsed = time.monotonic() - started
    assert result.get("step_error") == _rate_limit_error(20)
    assert "not straight away" in result["step_error"]["message"]
    assert _guard(events) is None
    assert len(times) == 1
    assert elapsed < 1.0, elapsed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("behaviours", "requests", "retry_after_s"),
    [
        ((_rate_limited, _rate_limited("20")), 2, 20),
        ((_rate_limited("3"), _rate_limited("5")), 2, 5),
        ((_rate_limited("3"), _rate_limited), 2, 1),
    ],
    ids=[
        "the second request carried it",
        "both carried one: the later, longer one",
        "the first carried it and it has passed: at least a second",
    ],
)
async def test_a_retry_after_is_honoured_whichever_request_carried_it(
    monkeypatch: pytest.MonkeyPatch, behaviours: tuple[Any, ...], requests: int, retry_after_s: int
) -> None:
    """R-10 (F-8.6-FA05): R-05 read `Retry-After` from the last request of
    an attempt only, so which request carried it decided whether it was
    honoured. Now every request's is read."""
    times = _classifier(monkeypatch, *behaviours)
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    assert result.get("step_error") == _rate_limit_error(retry_after_s)
    assert _guard(events) is None
    assert len(times) == requests


@pytest.mark.asyncio
async def test_a_first_request_that_hangs_gets_a_hedge_at_four_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Card 72, option A, the recommendation's own case: the first request
    hangs, an identical second goes out at about 4 s WITHOUT the first being
    cancelled, answers in 1 s, and the question is admitted at about 5 s,
    not 10 to 15. The hung first request is then cancelled and charged as
    a cancelled call is charged today.

    MUTATION PROOF: setting `_CLASSIFIER_HEDGE_AFTER_S` to 10.0, R-01's
    first-attempt cut, turns this red on the elapsed time.
    """
    times = _classifier(monkeypatch, "hang", 1.0)
    started = time.monotonic()
    events, result, harness = await _run_guardrail(_ORDINARY_QUESTION)
    elapsed = time.monotonic() - started

    assert result.get("step_error") is None
    assert _guard(events) == {"passed": True, "category": "ok", "reason": None}
    assert len(times) == 2
    assert _gaps(times)[0] == pytest.approx(graph_module._CLASSIFIER_HEDGE_AFTER_S, abs=0.3)
    assert 4.8 < elapsed < 5.8, elapsed
    assert times.cancelled == [1]
    assert harness.get_query_cost_usd(harness.trace_id) == pytest.approx(_CANCELLED_GUARD_CALL + _ANSWERED_GUARD_CALL)


@pytest.mark.asyncio
async def test_a_first_reply_at_six_seconds_wins_and_the_hedge_is_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Card 72: the hedge went out at 4 s and is still in flight when the
    first request answers at 6 s. The first reply wins, the hedge is
    cancelled and charged as a cancelled call, and no third request goes.

    MUTATION PROOF: cancelling the first request when the hedge is sent
    turns this red: the question then waits for the hung hedge and fails.
    """
    times = _classifier(monkeypatch, 6.0, "hang")
    started = time.monotonic()
    events, result, harness = await _run_guardrail(_ORDINARY_QUESTION)
    elapsed = time.monotonic() - started

    assert result.get("step_error") is None
    assert _guard(events) == {"passed": True, "category": "ok", "reason": None}
    assert len(times) == 2
    assert 5.8 < elapsed < 6.6, elapsed
    assert times.cancelled == [2]
    assert harness.get_query_cost_usd(harness.trace_id) == pytest.approx(_CANCELLED_GUARD_CALL + _ANSWERED_GUARD_CALL)


@pytest.mark.asyncio
async def test_both_requests_slow_past_the_budget_give_todays_step_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Card 72: no verdict is still no answer. Both requests hang; at the
    guardrail's unchanged 15 s the question ends in today's step error, and
    nothing is admitted."""
    times = _classifier(monkeypatch, "hang")
    budget = graph_module.budget_for_step("guardrail", "lookup")
    assert budget == 15.0
    started = time.monotonic()
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    elapsed = time.monotonic() - started

    assert result.get("step_error") == _STEP_ERROR
    assert _guard(events) is None
    assert len(times) == 2
    assert budget - 0.1 < elapsed < budget + 0.5, elapsed


@pytest.mark.asyncio
async def test_a_slow_failure_then_a_slow_answer_is_admitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-10 (F-8.6-FJ11), the judge's shape with the real budget: the first
    request fails slowly, a 503 at 9.8 s, and a second answers 9.5 s after
    it was sent. R-05 admitted nothing: its second attempt started after
    the first failed, and its backoff pushed the answer past 15 s. Now the
    second went out as a hedge at 4 s and answers at about 13.5 s, inside
    the budget, so the question is admitted, whatever the first cost."""
    times = _classifier(monkeypatch, (9.8, _unavailable), (9.5, _ADMIT))
    started = time.monotonic()
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    elapsed = time.monotonic() - started

    assert result.get("step_error") is None
    assert _guard(events) == {"passed": True, "category": "ok", "reason": None}
    assert len(times) == 2
    assert 13.3 < elapsed < 14.3, elapsed


@pytest.mark.asyncio
async def test_the_log_names_each_requests_time_and_upstream_host_and_nothing_private(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Card 72, D's logging: one line per guard request with its elapsed
    time, the upstream host OpenRouter named, and the trace id; never the
    key, the question's text or the prompt."""
    times = _classifier(monkeypatch, "hang", (0.2, _ADMIT, "DeepInfra"))
    with caplog.at_level(logging.WARNING, logger=graph_module.__name__):
        _, _, harness = await _run_guardrail(_ORDINARY_QUESTION)
    ours = [r for r in caplog.records if r.getMessage().startswith("guard classification request")]
    assert {r.levelname for r in ours} == {"WARNING"}, "develop's log records WARNING and above only"
    lines = [r.getMessage() for r in ours]
    assert len(times) == 2
    assert len(lines) == 2, lines
    answered = next(line for line in lines if "answered" in line)
    cancelled = next(line for line in lines if "cancelled" in line)
    assert answered.startswith(f"guard classification request 2 of 2 (trace {harness.trace_id}): answered after 0.")
    assert answered.endswith("s, upstream DeepInfra")
    assert cancelled.startswith(f"guard classification request 1 of 2 (trace {harness.trace_id}): cancelled")
    assert cancelled.endswith("upstream not named")
    for record in caplog.records:
        text = record.getMessage()
        assert "test-key" not in text
        assert _ORDINARY_QUESTION not in text
        assert "BRCA1" not in text


# ---------------------------------------------------------------------------
# No path passes the budget, no verdict is no answer, and never more than two
# requests in flight or in total. The budget is shrunk to 2.0 s and the hedge,
# the backoff and the floor scaled with it. The 0.3 s tolerance is scheduling
# lag on a loaded machine; it stays under one backoff, so a wait taken past
# the deadline is still caught.
# ---------------------------------------------------------------------------

_SHRUNK_BUDGET_S = 2.0
_LAG_S = 0.3


def _shrink(monkeypatch: pytest.MonkeyPatch) -> None:
    real_budget = graph_module.budget_for_step

    def _budget(step: str, query_class: Any) -> float:
        return _SHRUNK_BUDGET_S if step == "guardrail" else real_budget(step, query_class)

    monkeypatch.setattr(graph_module, "budget_for_step", _budget)
    monkeypatch.setattr(graph_module, "_CLASSIFIER_HEDGE_AFTER_S", 0.5)
    monkeypatch.setattr(graph_module, "_CLASSIFIER_RETRY_BACKOFF_S", 0.5)
    monkeypatch.setattr(graph_module, "_CLASSIFIER_MIN_SECOND_ATTEMPT_S", 0.6)


_EVERY_FAILURE = [
    (("hang",), _STEP_ERROR),
    ((_rate_limited,), _rate_limit_error(None)),
    ((_rate_limited("0.6"), _rate_limited("0.6"), "hang"), _rate_limit_error(1)),
    ((_connection_error, _connection_error, "hang"), _STEP_ERROR),
    ((_rate_limited, _rate_limited, "hang"), _rate_limit_error(None)),
    (((0.2, _connection_error), "hang"), _STEP_ERROR),
    (("hang", _rate_limited("30")), None),
    (((1.0, _connection_error), (0.1, _connection_error), _ADMIT), _STEP_ERROR),
]
_EVERY_FAILURE_IDS = [
    "a hang every time",
    "a 429 every time",
    "429s naming a wait, then a hang",
    "two errors, then a hang",
    "429s naming none, then a hang",
    "a quick error, then a hang",
    "a hang, and a hedge rate-limited for 30 s",
    "a slow error with the hedge failing too: no third request",
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("behaviours", "step_error"), _EVERY_FAILURE, ids=_EVERY_FAILURE_IDS)
async def test_no_verdict_is_no_answer_and_no_path_passes_the_budget(
    monkeypatch: pytest.MonkeyPatch, behaviours: tuple[Any, ...], step_error: dict[str, Any] | None
) -> None:
    """MUTATION PROOF: `_CLASSIFIER_MAX_REQUESTS` at 3 turns the last arms
    red on the request count, and the first on the peak in flight."""
    _shrink(monkeypatch)
    times = _classifier(monkeypatch, *behaviours)
    started = time.monotonic()
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    elapsed = time.monotonic() - started
    if step_error is None:
        # The hedge carried a 30 s Retry-After at 0.5 s; 1.5 s later it is
        # still about 28.5 s off.
        got = result.get("step_error")
        assert got is not None and got["retry_after_s"] in (28, 29, 30), got
        assert got["message"] == _busy(got["retry_after_s"])
    else:
        assert result.get("step_error") == step_error
    assert _guard(events) is None
    assert elapsed < _SHRUNK_BUDGET_S + _LAG_S, elapsed
    assert len(times) <= graph_module._CLASSIFIER_MAX_REQUESTS == 2
    assert times.peak <= 2


@pytest.mark.asyncio
@pytest.mark.parametrize("behaviours", [(1.5, "hang"), (1.5,)], ids=["then a hang", "a steady 1.5 s"])
async def test_a_slow_first_reply_is_no_longer_thrown_away(
    monkeypatch: pytest.MonkeyPatch, behaviours: tuple[Any, ...]
) -> None:
    """Card 72: R-01 cut the first request at two thirds of the budget
    (1.33 s of 2.0 here) and threw away a reply that would have come at
    1.5 s. The hedge leaves it running, and it decides."""
    _shrink(monkeypatch)
    times = _classifier(monkeypatch, *behaviours)
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    assert result.get("step_error") is None
    assert _guard(events) == {"passed": True, "category": "ok", "reason": None}
    assert len(times) == 2
    assert times.cancelled == [2]


@pytest.mark.asyncio
async def test_a_quick_error_never_backs_off_past_the_hedge_point(monkeypatch: pytest.MonkeyPatch) -> None:
    """R-10 (F-8.6-FJ11): a first request that fails just before the hedge
    was due gets its second request at the hedge point, not a full backoff
    later, so the backoff never takes time from the second request. Scaled:
    budget 6 s, hedge 1.6 s, backoff 0.8 s. The first fails at 1.4 s, the
    second answers 4.2 s after it is sent: at 5.8 s now, at 6.4 s, past the
    budget, under R-05's full backoff.

    MUTATION PROOF: dropping the hedge-point cap from `_classifier_retry_wait_s`
    turns this red on the step error.
    """
    real_budget = graph_module.budget_for_step
    monkeypatch.setattr(
        graph_module,
        "budget_for_step",
        lambda step, qc: 6.0 if step == "guardrail" else real_budget(step, qc),
    )
    monkeypatch.setattr(graph_module, "_CLASSIFIER_HEDGE_AFTER_S", 1.6)
    monkeypatch.setattr(graph_module, "_CLASSIFIER_RETRY_BACKOFF_S", 0.8)
    monkeypatch.setattr(graph_module, "_CLASSIFIER_MIN_SECOND_ATTEMPT_S", 1.2)
    times = _classifier(monkeypatch, (1.4, _unavailable), (4.2, _ADMIT))
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    assert result.get("step_error") is None
    assert _guard(events) == {"passed": True, "category": "ok", "reason": None}
    assert _gaps(times)[0] == pytest.approx(1.6, abs=0.15)


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
# R-06, then R-10 (F-8.6-FA03): a refusal only Jev's own pick could change is
# not held for the guard tier's fallback, and it waits on `decide()`'s own
# signal that Jev failed, never on a clock.
# ---------------------------------------------------------------------------


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
    on it never waits for that fallback."""
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


@pytest.mark.asyncio
async def test_with_jev_a_stalled_loop_never_turns_jevs_admission_into_a_refusal(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None
) -> None:
    """F-8.6-FA03, through the real `decide()` and the real constants. The
    event loop stalls for a second after the relevancy decision starts and
    before Jev's request goes out (here, a blocking call where `decide()`
    resolves Jev's model; on develop, another question's daily-cap
    queries), and Jev then answers on topic 2.9 s after its request, inside
    its own 3-second bound. The decision took 3.9 s from its start. R-06's
    window closed 3.75 s after the start and turned Jev's admission into an
    off-topic refusal; the guardrail now waits for Jev's own word.

    MUTATION PROOF: ending `_await_jev_own_pick`'s wait 3.75 s after the
    decision began, R-06's clock, turns this red on the refusal.
    """
    _classifier(monkeypatch, _OFF_TOPIC)
    _jev_injection(monkeypatch, "not_injection")
    real_model = decide_module.resolve_jev_model

    def _stalled_model() -> str:
        time.sleep(1.0)  # a blocking call on the loop thread, as the adversary forced
        return real_model()

    monkeypatch.setattr(decide_module, "resolve_jev_model", _stalled_model)
    monkeypatch.setattr(jev_client_module, "_post", _jev_reply("on_topic", "off_topic", after_s=2.9))
    fallback = AsyncMock(side_effect=AssertionError("the guard fallback is never asked"))
    monkeypatch.setattr(decide_module, "_guard_fallback_pick", fallback)

    started = time.monotonic()
    events, _, harness = await _run_guardrail(_TREE_OF_LIFE)
    elapsed = time.monotonic() - started

    assert _guard(events) == {"passed": True, "category": "ok", "reason": None}
    assert elapsed > 3.75, elapsed  # past R-06's window: the case FA03 found
    record = next(r for r in graph_module._done_decisions(harness) or [] if r.name == "guardrail.relevancy")
    assert record.decided_by == "jev" and record.chosen == "on_topic"


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
    """Production's setting: the guard tier's relevancy pick is the only
    one, and it is waited for within the step's budget exactly as before,
    whatever the signal says."""
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


@pytest.mark.asyncio
async def test_an_unusable_reply_then_an_error_keeps_the_errors_words(monkeypatch: pytest.MonkeyPatch) -> None:
    """The step error's words follow the last request to end, as before R-10:
    an unusable first reply, then a transient error on the second, is the
    transient step error, not "could not complete"."""
    _shrink(monkeypatch)
    times = _classifier(monkeypatch, "I will look this up.", _connection_error)
    events, result, _ = await _run_guardrail(_ORDINARY_QUESTION)
    assert _guard(events) is None
    assert result.get("step_error") == _STEP_ERROR
    assert len(times) == 2
