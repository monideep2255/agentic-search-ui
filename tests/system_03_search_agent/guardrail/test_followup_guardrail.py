"""Phase 8.6's re-land follow-up and R-10 without card 72's hedge (card
84): the guardrail's guard-model calls and Jev's signal, through the real
node.

## What these arms pin

- Card 84 (R-10 line 4, F-8.6-FJ04, FA02, FA05, FJ05; F-72-J04, J05, J08,
  V05, V06), as the lead corrected it: every guard-tier call the guardrail
  makes, the classifier and the relevancy decision's guard pick, keeps
  develop's policy request for request, with its timing (R-01's attempts,
  `call_tier`'s immediate resend, R-05's backoff), and never has two
  requests in flight. Once the provider rate-limits a call, it sends at
  most two requests in all; a stated `Retry-After` is waited out first,
  or, when it does not fit, ends the question at once saying how long to
  wait; it is read from whichever request carried it. Each call writes one
  log line naming each request's outcome, time and upstream host. No
  verdict is still no answer, and no path passes the budget. FJ11 stays
  as on develop, pinned by its own test.
- R-06 (F-8.6-RJ03, RJ09), then R-10 (F-8.6-FA03, F-72-J03, J07): in Jev
  mode, a refusal that only Jev's OWN relevancy pick could change waits
  only until `decide()` says Jev failed (`jev_failed`), not for the guard
  tier's fallback pick, and never on a clock of its own: a stalled event
  loop anywhere in Jev's wait no longer cuts off a pick Jev delivers inside
  its own bound. Jev's own pick still decides exactly as before, through
  the real `decide()`.
- With the provider at its code default, the signal changes nothing.

## What they do not cover

- A live provider's real rate limits or real `Retry-After` headers: every
  model reply below is a stub, the 429 included.
- How often a live classifier fails. The arms pin what the node does when
  it does. `test_guard_request_dominance.py` sweeps the policy against
  develop's over timings and verdicts.

The timing arms run the real node on a virtual clock
(`tests/system_03_search_agent/virtual_clock.py`) with the real constants
and the real 15-second budget, so they assert exact send times and run in
milliseconds.
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


def _classifier(monkeypatch: pytest.MonkeyPatch, *behaviours: Any, only_classifier: bool = False) -> _Requests:
    """Stub the guard model's requests, one behaviour per request, the last
    repeating: "hang" sleeps past any budget, a float answers `_ADMIT`
    after that many seconds, a tuple `(seconds, outcome[, upstream host])`
    waits and then takes `outcome`, a callable returns an exception to raise
    or a reply's content, anything else is the reply's content. Times are
    the running loop's, so the stub works on the virtual clock too. With
    `only_classifier`, a request that is not the guardrail's classifier (a
    guard pick through `decide`) is answered "on_topic" at once and not
    counted."""
    times = _Requests()
    active = [0]

    async def _acompletion(**kwargs: Any) -> Any:
        if only_classifier and not _is_classifier_request(kwargs):
            return fake_response("on_topic")
        behaviour = behaviours[min(len(times), len(behaviours) - 1)]
        times.append(asyncio.get_running_loop().time())
        number = len(times)
        active[0] += 1
        times.peak = max(times.peak, active[0])
        try:
            if isinstance(behaviour, str) and behaviour == "hang":
                await asyncio.sleep(10_000)
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


def _is_classifier_request(kwargs: dict[str, Any]) -> bool:
    """The guardrail's own classifier, not a guard pick asked through
    `decide`, whose system message starts with the closed-option line."""
    system = next((m["content"] for m in kwargs["messages"] if m["role"] == "system"), "")
    return not system.startswith("Answer with exactly one of the offered options")


def _gaps(times: list[float]) -> list[float]:
    return [later - earlier for earlier, later in itertools.pairwise(times)]


def _node(monkeypatch: pytest.MonkeyPatch, text: str = _ORDINARY_QUESTION) -> tuple[list[Any], dict[str, Any], Any, float]:
    """The real node on the virtual clock, with the real budget and the real
    constants: (events, result, harness, seconds it took)."""

    async def _go() -> tuple[list[Any], dict[str, Any], Any, float]:
        started = asyncio.get_running_loop().time()
        events, result, harness = await _run_guardrail(text)
        return events, result, harness, asyncio.get_running_loop().time() - started

    return run_virtual(monkeypatch, _go)


_ADMITTED = {"passed": True, "category": "ok", "reason": None}


# ---------------------------------------------------------------------------
# Card 84: every guard-tier call sends at most two requests, one after the
# other. Through the real node, on the virtual clock, with the real
# constants and the real 15-second budget.
# ---------------------------------------------------------------------------


def _call_error(cause: BaseException | None, source: str = "harness.call_tier") -> HarnessCallError:
    error = HarnessCallError("stub", error_class="transient", source=source)
    error.__cause__ = cause
    return error


@pytest.mark.parametrize("where", ["litellm_response_headers", "headers", "response"])
def test_retry_after_is_read_wherever_the_error_carries_it(where: str) -> None:
    cause = RuntimeError("429")
    cause.status_code = 429  # type: ignore[attr-defined]
    if where == "response":
        cause.response = httpx.Response(429, headers={"retry-after": "4"})  # type: ignore[attr-defined]
    else:
        setattr(cause, where, {"RETRY-AFTER": "4"})
    error = _call_error(cause)
    assert decide_module.rate_limit_behind(error) is cause
    assert decide_module.provider_retry_after_s(cause) == pytest.approx(4.0)


def test_a_retry_after_date_is_read_as_a_wait() -> None:
    when = format_datetime(datetime.now(UTC) + timedelta(seconds=6), usegmt=True)
    wait = decide_module.provider_retry_after_s(_rate_limited(when))
    assert wait is not None and 4.5 < wait <= 6.0


def test_the_first_request_keeps_two_thirds_and_the_budget_is_unchanged() -> None:
    """Nothing the owner holds moved: the guardrail's 15 s, R-01's share,
    R-05's backoff and floor, and two requests at most once rate-limited."""
    assert graph_module.budget_for_step("guardrail", "lookup") == 15.0
    assert graph_module._CLASSIFIER_FIRST_ATTEMPT_SHARE == pytest.approx(2 / 3)
    assert decide_module.GUARD_RATE_LIMITED_MAX_REQUESTS == 2
    assert decide_module.GUARD_MIN_SECOND_REQUEST_S == 3.0
    assert decide_module.GUARD_RETRY_BACKOFF_S == 2.0


def test_a_first_request_that_hangs_gets_its_second_at_ten_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    """G-005's shape, R-01's fix, as on develop: the first request is cut at
    two thirds of the budget and the second goes at once, alone."""
    times = _classifier(monkeypatch, "hang", (0.6, _ADMIT))
    events, result, _, elapsed = _node(monkeypatch)
    assert result.get("step_error") is None
    assert _guard(events) == _ADMITTED
    assert _gaps(times) == [pytest.approx(10.0)]
    assert times.peak == 1 and times.cancelled == [1]
    assert elapsed == pytest.approx(10.6)


def test_an_error_is_followed_at_once_as_on_develop(monkeypatch: pytest.MonkeyPatch) -> None:
    """F-72-V06: one failed request no longer makes the person wait. The
    second request goes the moment the first fails, when develop's
    `call_tier` sent its own resend, so the answer comes at the same moment
    as on develop.

    MUTATION PROOF: a two-second backoff before the second request turns
    this red: admitted at 2.65 s instead of 0.65 s."""
    times = _classifier(monkeypatch, (0.05, _connection_error), (0.6, _ADMIT))
    events, result, _, elapsed = _node(monkeypatch)
    assert result.get("step_error") is None
    assert _guard(events) == _ADMITTED
    assert times == [pytest.approx(times[0]), pytest.approx(times[0] + 0.05)]
    assert elapsed == pytest.approx(0.65)


def test_fj11_stays_as_on_develop_a_slow_failure_then_a_slow_answer_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """R-10 line 2 (F-8.6-FJ11) is OPEN by the lead's correction of
    2026-09-29, which keeps develop's timing exactly for every failure that
    is not a rate limit. The first request fails after 9 s; develop resends
    at once inside the first attempt's 10 s share, cuts that at 10 s, and
    gives a third request the last 5 s, too little for a 5.5 s answer. The
    fix that admitted this (the resend keeping all 15 s) loses questions
    develop answers whenever that resend hangs and the third would have
    answered, so it cannot keep develop's timing. Pinned so a change here is
    seen, not to endorse it."""
    times = _classifier(monkeypatch, (9.0, _unavailable), (5.5, _ADMIT))
    events, result, _, elapsed = _node(monkeypatch)
    assert result.get("step_error") == _STEP_ERROR
    assert _guard(events) is None
    assert [t - times[0] for t in times] == [pytest.approx(0.0), pytest.approx(9.0), pytest.approx(10.0)]
    assert elapsed == pytest.approx(15.0)


def test_an_error_lasting_about_a_second_is_outlasted_as_on_develop(monkeypatch: pytest.MonkeyPatch) -> None:
    """R-05's RJ08 blip, kept: both requests of the first attempt fail
    inside a one-second error, the second attempt waits the 2 s backoff,
    and the question is admitted on the third request.

    MUTATION PROOF: no backoff between attempts turns this red."""
    first: list[float] = []

    def _blip() -> Any:
        now = asyncio.get_running_loop().time()
        first.append(now)
        return _connection_error() if now - first[0] < 1.0 else _ADMIT

    times = _classifier(monkeypatch, _blip)
    events, result, _, elapsed = _node(monkeypatch)
    assert result.get("step_error") is None
    assert _guard(events) == _ADMITTED
    assert len(times) == 3
    assert elapsed == pytest.approx(2.0)


def test_an_unusable_reply_is_followed_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    times = _classifier(monkeypatch, (0.5, "I will look this up."), (0.6, _ADMIT))
    events, result, _, elapsed = _node(monkeypatch)
    assert result.get("step_error") is None
    assert _guard(events) == _ADMITTED
    assert _gaps(times) == [pytest.approx(0.5)]
    assert elapsed == pytest.approx(1.1)


def test_an_unusable_reply_then_an_error_keeps_the_errors_words(monkeypatch: pytest.MonkeyPatch) -> None:
    """The step error's words follow the last request to end: an unusable
    first reply, then a transient error, is the transient step error."""
    times = _classifier(monkeypatch, "I will look this up.", _connection_error)
    events, result, _, _ = _node(monkeypatch)
    assert _guard(events) is None
    assert result.get("step_error") == _STEP_ERROR
    assert len(times) == 3  # the second attempt's request and its resend, as on develop


def test_a_guard_model_that_cannot_turn_reasoning_off_still_screens(monkeypatch: pytest.MonkeyPatch) -> None:
    """F-72-J08 at the front door: a guard model that refuses the reasoning
    block is resent without it, inside the one request, and the question is
    admitted, where `retry=False` alone failed it in 50 ms."""
    sent: list[bool] = []

    async def _acompletion(**kwargs: Any) -> Any:
        sent.append("reasoning" in kwargs)
        if "reasoning" in kwargs:
            raise litellm.BadRequestError(
                "Reasoning is mandatory for this endpoint and cannot be disabled.", model="m", llm_provider="openrouter"
            )
        return fake_response(_ADMIT)

    monkeypatch.setattr(harness_module.litellm, "acompletion", _acompletion)
    events, result, _, _ = _node(monkeypatch)
    assert result.get("step_error") is None
    assert _guard(events) == _ADMITTED
    assert sent == [True, False]


# ---------------------------------------------------------------------------
# R-10 line 4: a rate-limited guard model gets two requests at most, a
# stated wait is honoured from whichever request carried it, and the person
# is told how long to wait.
# ---------------------------------------------------------------------------

_BUSY_NO_WAIT = (
    "The service that checks each question is busy right now. "
    "Wait a little before trying the query again."
)
_BUSY_WAIT_PASSED = "The service that checks each question was busy a moment ago. Try the query again."


def _busy(seconds: int) -> str:
    wait = "about 1 second" if seconds == 1 else f"about {seconds} seconds, not straight away"
    return f"The service that checks each question is busy right now. Try the query again in {wait}."


def _rate_limit_error(message: str, retry_after_s: int) -> dict[str, Any]:
    return {
        "fatal": True,
        "scope": "step",
        "source": "guardrail",
        "error_class": "transient",
        "message": message,
        "retry_after_s": retry_after_s,
    }


def test_a_rate_limit_storm_costs_two_requests_and_says_to_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """R-10 (F-8.6-FJ04, FA02, FJ05): every request is a 429 naming no wait.
    Two requests in all, never develop's four, one after the other; the
    person is told to wait a little, not to retry now.

    MUTATION PROOF: allowing three requests to a rate-limited call turns
    this red on the request count."""
    times = _classifier(monkeypatch, _rate_limited)
    events, result, _, _ = _node(monkeypatch)
    assert result.get("step_error") == _rate_limit_error(_BUSY_NO_WAIT, 0)
    assert _guard(events) is None
    assert len(times) == 2 and times.peak == 1


def test_a_providers_retry_after_is_honoured_when_it_fits(monkeypatch: pytest.MonkeyPatch) -> None:
    """R-10 (F-8.6-FA05): develop's `call_tier` resent 0.03 s after a 429
    that said wait 3 s; now the second request waits the 3 s.

    MUTATION PROOF: ignoring the stated wait turns this red on the gap."""
    times = _classifier(monkeypatch, (0.05, _rate_limited("3")), (0.6, _ADMIT))
    events, result, _, elapsed = _node(monkeypatch)
    assert result.get("step_error") is None
    assert _guard(events) == _ADMITTED
    assert _gaps(times) == [pytest.approx(3.05)]
    assert elapsed == pytest.approx(3.65)


def test_a_retry_after_that_does_not_fit_says_when_to_come_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """R-10 (F-8.6-FA02): the provider says wait 20 s, which the budget
    cannot fit. No second request, at once, and the person is told to try
    again in about 20 seconds, with `retry_after_s` 20, not 0."""
    times = _classifier(monkeypatch, _rate_limited("20"))
    events, result, _, elapsed = _node(monkeypatch)
    assert result.get("step_error") == _rate_limit_error(_busy(20), 20)
    assert _guard(events) is None
    assert len(times) == 1
    assert elapsed < 0.01


@pytest.mark.parametrize(
    ("behaviours", "requests", "message", "retry_after_s"),
    [
        ((_rate_limited, _rate_limited("20")), 2, _busy(20), 20),
        ((_rate_limited("3"), _rate_limited("7")), 2, _busy(7), 7),
        ((_rate_limited, _rate_limited("1")), 2, _busy(1), 1),
        ((_rate_limited("3"), _rate_limited), 2, _BUSY_WAIT_PASSED, 0),
        ((_rate_limited("0"), _rate_limited), 2, _BUSY_WAIT_PASSED, 0),
    ],
    ids=[
        "the second request carried it",
        "both carried one: the later",
        "one second: 'second', with no 'not straight away'",
        "the first carried it and it has passed",
        "a stated wait of 0",
    ],
)
def test_a_retry_after_is_honoured_whichever_request_carried_it(
    monkeypatch: pytest.MonkeyPatch, behaviours: tuple[Any, ...], requests: int, message: str, retry_after_s: int
) -> None:
    """R-10 (F-8.6-FA05) and F-72-J04: every request's `Retry-After` is
    read; a wait already over is not given as "not straight away"."""
    times = _classifier(monkeypatch, *behaviours)
    events, result, _, _ = _node(monkeypatch)
    assert result.get("step_error") == _rate_limit_error(message, retry_after_s)
    assert _guard(events) is None
    assert len(times) == requests


@pytest.mark.parametrize(
    ("wait_s", "message", "retry_after_s"),
    [
        (1.0, _busy(1), 1),
        (0.2, _busy(1), 1),
        (1.2, _busy(2), 2),
        (20.0, _busy(20), 20),
        (10.0**9, _busy(86_400), 86_400),
        (0.0, _BUSY_WAIT_PASSED, 0),
        (-3.0, _BUSY_WAIT_PASSED, 0),
        (None, _BUSY_NO_WAIT, 0),
        (float("inf"), _BUSY_NO_WAIT, 0),
        (float("nan"), _BUSY_NO_WAIT, 0),
    ],
    ids=["1", "0.2", "1.2", "20", "a billion", "0", "-3", "none", "inf", "nan"],
)
def test_the_rate_limit_message_counts_seconds_in_words(wait_s: float | None, message: str, retry_after_s: int) -> None:
    got = graph_module._rate_limited_step_error(wait_s)
    assert got == _rate_limit_error(message, retry_after_s)


# ---------------------------------------------------------------------------
# No verdict is no answer, and no path passes the budget, sends a third
# request or has two in flight.
# ---------------------------------------------------------------------------

_EVERY_FAILURE = [
    (("hang",), 2, False),
    ((_rate_limited,), 2, False),
    ((_rate_limited("0.6"), _rate_limited("0.6"), "hang"), 2, False),
    ((_connection_error, _connection_error, 0.1), 3, True),
    ((_connection_error,), 4, False),
    (((9.0, _unavailable), "hang"), 3, False),
    (("hang", _connection_error, 0.1), 3, True),
    (((1.5, _ADMIT), "hang"), 1, True),
    (("I will look this up.", "hang"), 2, False),
    (("I will look this up.", "I will look this up.", 0.1), 2, False),
    ((_rate_limited("12.5"), 0.1), 1, False),
    ((_connection_error, _rate_limited, 0.1), 2, False),
    ((lambda: litellm.AuthenticationError(message="401 (stub)", llm_provider="openrouter", model="m"), 0.1), 1, False),
]
_EVERY_FAILURE_IDS = [
    "a hang every time",
    "a 429 every time",
    "429s naming a wait, then a hang",
    "two errors, then an answer: the third request, as on develop",
    "errors every time: develop's four",
    "a slow error, then a hang",
    "a hang, then an error, then an answer",
    "a slow first reply is not a failure",
    "unusable, then a hang",
    "two unusable replies, then an answer",
    "a wait that leaves too little",
    "an error, then a 429: no third request",
    "a refused key",
]


@pytest.mark.parametrize(("behaviours", "requests", "admitted"), _EVERY_FAILURE, ids=_EVERY_FAILURE_IDS)
def test_no_verdict_is_no_answer_and_no_path_passes_the_budget(
    monkeypatch: pytest.MonkeyPatch, behaviours: tuple[Any, ...], requests: int, admitted: bool
) -> None:
    """Every shape: the requests develop sent, or at most two once one was
    rate-limited; never two in flight; never past the budget; no verdict,
    no admission."""
    times = _classifier(monkeypatch, *behaviours)
    events, result, _, elapsed = _node(monkeypatch)
    assert len(times) == requests
    assert times.peak == 1
    assert elapsed <= 15.0 + 1e-6
    if admitted:
        assert result.get("step_error") is None and _guard(events) == _ADMITTED
    else:
        assert result.get("step_error") is not None and _guard(events) is None


def test_with_jev_a_classifier_that_never_answers_is_never_an_admission(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None
) -> None:
    """Jev clearing the question cannot stand in for the guard classifier."""
    _classifier(monkeypatch, _connection_error)

    async def _call_jev(**_kwargs: Any) -> Any:
        from system_03_search_agent.harness.jev_client import JevResult

        return JevResult(
            resolved_model="jev-test", choice="not_injection", confidence=0.9,
            probabilities={"not_injection": 0.95, "injection": 0.05},
            input_tokens=1, output_tokens=1, cost_usd=0.00002, latency_ms=100,
        )

    monkeypatch.setattr(graph_module, "call_jev", _call_jev)
    events, result, _, _ = _node(monkeypatch)
    assert result.get("step_error") == _STEP_ERROR
    assert _guard(events) is None


# ---------------------------------------------------------------------------
# Line 7: each guard call logs its time and the upstream host, with the
# trace id, and nothing private.
# ---------------------------------------------------------------------------


def test_each_guard_call_logs_its_time_and_upstream_host_and_nothing_private(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """One WARNING line per guard call (develop's log keeps WARNING and
    above only): the outcome, the time in all, and each request's outcome,
    time and upstream host. Never the key, the question or the prompt, and
    an upstream name from outside is cut and stripped of line breaks.

    MUTATION PROOF: dropping the upstream host from the request's words
    turns this red."""
    _classifier(monkeypatch, "hang", (0.2, _ADMIT, "Deep\nInfra" + "x" * 100))
    with caplog.at_level(logging.WARNING, logger=decide_module.__name__):
        _, _, harness, _ = _node(monkeypatch)
    ours = [r for r in caplog.records if r.getMessage().startswith("guard call guard classification")]
    assert len(ours) == 1 and ours[0].levelname == "WARNING"
    line = ours[0].getMessage()
    assert line == (
        f"guard call guard classification (trace {harness.trace_id}): answered after 10.20s in all, "
        "2 requests; request 1: cut at its budget after 10.00s; "
        f"request 2: answered after 0.20s, upstream DeepInfra{'x' * 55}"
    )
    for record in caplog.records:
        text = record.getMessage()
        assert "test-key" not in text
        assert _ORDINARY_QUESTION not in text and "BRCA1" not in text
        assert "Answer with exactly one" not in text and "\n" not in text


# ---------------------------------------------------------------------------
# F-72-J05: the relevancy decision's guard pick takes the same path.
# ---------------------------------------------------------------------------


def test_a_rate_limit_storm_gives_each_guard_call_two_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """J05's probe: every guard-model request is a 429 naming no wait, for a
    question the allowlist misses, so the relevancy decision's guard pick
    runs beside the classifier. Each call sends two at most, one after the
    other, as develop's pick already did."""
    sent: dict[str, list[float]] = {"classifier": [], "pick": []}

    async def _acompletion(**kwargs: Any) -> Any:
        which = "classifier" if _is_classifier_request(kwargs) else "pick"
        sent[which].append(asyncio.get_running_loop().time())
        raise _rate_limited()

    monkeypatch.setattr(harness_module.litellm, "acompletion", _acompletion)
    _, result, _, _ = _node(monkeypatch, _TREE_OF_LIFE)
    assert result.get("step_error") == _rate_limit_error(_BUSY_NO_WAIT, 0)
    assert len(sent["classifier"]) == 2
    assert len(sent["pick"]) == 2


@pytest.mark.parametrize(("stated", "sent_at"), [("20", [0.0]), ("3", [0.0, 3.0])], ids=["does not fit", "fits"])
def test_the_relevancy_pick_honours_a_retry_after(
    monkeypatch: pytest.MonkeyPatch, stated: str, sent_at: list[float]
) -> None:
    """F-72-J05: the pick's second request waits out the stated wait, or is
    not sent when it does not fit; develop's `call_tier` resent at once.

    MUTATION PROOF: the pick on `call_tier`'s own retry turns both red."""
    sent: list[float] = []
    started: list[float] = []

    async def _acompletion(**kwargs: Any) -> Any:
        now = asyncio.get_running_loop().time()
        started.append(now)
        if _is_classifier_request(kwargs):
            await asyncio.sleep(5.0)
            return fake_response(_ADMIT)
        sent.append(now - started[0])
        raise _rate_limited(stated)

    monkeypatch.setattr(harness_module.litellm, "acompletion", _acompletion)
    events, _, _, _ = _node(monkeypatch, _TREE_OF_LIFE)
    assert _guard(events) == _ADMITTED  # no pick fails open, as before
    assert sent == [pytest.approx(t) for t in sent_at]


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


_STALLS = [
    ("while Jev's model is resolved", 1.0),
    ("in the cap check inside Jev's wait", 0.6),
    ("in the cap check inside Jev's wait", 0.8),
    ("while Jev's reply is read", 0.6),
    ("while Jev's reply is read", 1.0),
    ("before Jev's reply arrives", 0.6),
]


@pytest.mark.parametrize(("where", "stall_s"), _STALLS, ids=[f"{s}s {w}" for w, s in _STALLS])
def test_with_jev_a_stall_anywhere_in_jevs_wait_never_turns_its_admission_into_a_refusal(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None, where: str, stall_s: float
) -> None:
    """F-8.6-FA03, which F-72-J03 found still open, through the real
    `decide()` and the real constants on the virtual clock. The classifier
    says off topic; Jev's relevancy pick says on topic 2.9 s after its
    request, inside its own 3-second bound. The server's event loop stalls
    once, blocking, somewhere inside Jev's wait: where the builder's test put
    it (resolving Jev's model, before `decide()`'s net is armed), where the
    judge put it (the cap check inside that net, before Jev's request),
    while Jev's reply is being read, or just before it arrives. Before, the
    0.6 s and 0.8 s stalls in the cap check spent the net's half-second
    margin and the question was refused as off topic. Now every clock on
    Jev counts only the time the loop was free, and Jev's admission stands.

    MUTATION PROOF: `wait_counting_free_time` counting real time again
    (`counted += now - last`) turns the 0.8 s cap-check arm and the "before
    Jev's reply arrives" arm red: the question is refused as off topic. The
    reply-read arms stay green under it, because a reply already in hand
    wins over the clock whatever the time."""
    _classifier(monkeypatch, _OFF_TOPIC)
    _jev_injection(monkeypatch, "not_injection")
    fallback = AsyncMock(side_effect=AssertionError("the guard fallback is never asked"))
    monkeypatch.setattr(decide_module, "_guard_fallback_pick", fallback)

    def _stall() -> None:
        decide_module.time.sleep(stall_s)  # the virtual clock's blocking stall

    if where == "while Jev's model is resolved":
        real_model = decide_module.resolve_jev_model
        monkeypatch.setattr(decide_module, "resolve_jev_model", lambda: (_stall(), real_model())[1])
    elif where == "in the cap check inside Jev's wait":
        real_check = decide_module.check_jev_per_query_cap
        monkeypatch.setattr(
            decide_module, "check_jev_per_query_cap", lambda harness, trace_id: (_stall(), real_check(harness, trace_id))[1]
        )
    reply = _jev_reply("on_topic", "off_topic", after_s=0.0)

    async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
        if where == "while Jev's reply is read":
            await asyncio.sleep(2.5)
            _stall()  # the reply arrives at 2.9 s, inside the stall
        elif where == "before Jev's reply arrives":
            await asyncio.sleep(2.5)
            _stall()  # the stall ends at 3.1 s, past Jev's own bound on the wall clock
            await asyncio.sleep(0.1)  # and the reply comes at 3.2 s, 2.6 s of free time
        else:
            await asyncio.sleep(2.9)
        return await reply(headers, body)

    monkeypatch.setattr(jev_client_module, "_post", _post)
    events, _, harness, elapsed = _node(monkeypatch, _TREE_OF_LIFE)

    assert _guard(events) == _ADMITTED
    assert elapsed > jev_client_module.JEV_TOTAL_TIMEOUT_S, elapsed  # past Jev's own bound on the wall clock
    record = next(r for r in graph_module._done_decisions(harness) or [] if r.name == "guardrail.relevancy")
    assert record.decided_by == "jev" and record.chosen == "on_topic"
    fallback.assert_not_called()


def test_with_jev_a_failure_signalled_mid_wait_ends_the_wait_at_once(
    monkeypatch: pytest.MonkeyPatch, _jev_on: None
) -> None:
    """F-72-J07: the live order, which every other arm skipped. The
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


@pytest.mark.parametrize(
    "behaviours",
    [("I will look this up.",), ("hang", "I will look this up.")],
    ids=["two unusable replies", "a hang, then an unusable reply"],
)
def test_no_usable_verdict_says_what_to_do_next(
    monkeypatch: pytest.MonkeyPatch, behaviours: tuple[Any, ...]
) -> None:
    """MUTATION PROOF: returning the parse error's own text again turns this
    red on the message."""
    _classifier(monkeypatch, *behaviours)
    events, result, _, _ = _node(monkeypatch)
    assert _guard(events) is None
    assert result.get("step_error") == {
        "fatal": True,
        "scope": "step",
        "source": "guardrail",
        "error_class": "recoverable",
        "message": "A step in this query could not complete. Retrying the query may succeed.",
        "retry_after_s": 0,
    }
