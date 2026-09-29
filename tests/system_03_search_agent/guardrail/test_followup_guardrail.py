"""Phase 8.6's re-land follow-up: the guardrail's R-05 and R-06, through the
real node.

## What these arms pin

- R-05 (F-8.6-RJ01, RJ08, RA02): the guard classifier's second request
  waits `_CLASSIFIER_RETRY_BACKOFF_S` after an ERROR, so an error lasting
  about a second no longer ends the question. A provider's own
  `Retry-After` is honoured when it fits the budget; when it does not, no
  second request is made.
- Card 72, option A, R-10 and its fix round (F-8.6-FJ11, FJ04, FA05,
  FA02; F-72-A04, A05, J01, J04, J06, J08, A02, J05): a first request not
  ended at the hedge point, two thirds of the budget, 10 s of 15, gets an
  identical second beside it, the first not cancelled, and none with less
  than two seconds left. After an error the second goes when develop's
  last request would have, never after the hedge point. Two requests at
  most, in flight or in total, a rate limit included. When two usable
  replies are in hand the stricter decides, and an unusable reply never
  beats a usable one. A `Retry-After` is honoured whichever request
  carried it, and a rate limit tells the person to try again later, in
  words that count one second as one. Each request is logged with its
  time and the upstream host (D's logging). The relevancy decision's
  guard pick takes the same path. No verdict is still no answer, and no
  path passes the guardrail's budget.
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

The timing arms run the real node on a virtual clock
(`tests/system_03_search_agent/virtual_clock.py`) with the real constants
and the real 15-second budget, so they assert exact send times and run in
milliseconds. `test_guard_request_dominance.py` holds the sweep against
develop's policy.
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
from types import SimpleNamespace
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
# When the second request goes (R-05, R-10 and its fix round, F-72-A04):
# read from the first request's failure alone.
# ---------------------------------------------------------------------------


def _call_error(cause: BaseException | None, source: str = "harness.call_tier", error_class: str = "transient") -> HarnessCallError:
    error = HarnessCallError("stub", error_class=error_class, source=source)
    error.__cause__ = cause
    return error


@pytest.mark.parametrize(
    ("error", "failed_at", "second_at"),
    [
        (None, 0.05, 0.05),
        (_call_error(_connection_error()), 0.05, 2.15),
        (_call_error(_connection_error()), 1.0, 5.0),
        (_call_error(_connection_error()), 4.0, 9.0),
        (_call_error(_connection_error()), 9.8, 10.0),
        (_call_error(_rate_limited()), 0.05, 2.15),
        (_call_error(_rate_limited("3")), 0.05, 3.05),
        (_call_error(_rate_limited("0.5")), 0.05, 2.05),
        (_call_error(_rate_limited("11")), 0.05, 11.05),
        (_call_error(_rate_limited("12")), 0.05, None),
        (_call_error(_rate_limited("20")), 0.05, None),
        (_call_error(_rate_limited("soon")), 0.05, 2.15),
        (_call_error(_connection_error(), error_class="recoverable"), 0.05, None),
    ],
    ids=[
        "an unusable reply: at once",
        "a fast error: when develop's fourth request went",
        "an error after 1 s: the same",
        "an error after 4 s: never later than develop gave its second chance",
        "a slow error at 9.8 s: at the hedge point, never a backoff past it",
        "a rate limit naming no wait: as an error",
        "a rate limit naming 3 s: 3 s",
        "a rate limit naming less than the backoff: the backoff",
        "a rate limit naming a wait that just fits",
        "a rate limit naming a wait that does not fit: none",
        "a rate limit naming 20 s: none",
        "a Retry-After that is not a wait: as an error",
        "an error that is not transient: none",
    ],
)
def test_when_the_second_request_goes(error: HarnessCallError | None, failed_at: float, second_at: float | None) -> None:
    """The first request was sent at 0 with 15 s of budget, so the hedge
    point is 10 s. MUTATION PROOF: sending the second at once after any
    error turns every error arm red, and dropping the hedge-point cap turns
    "a slow error at 9.8 s" red."""
    assert decide_module.GUARD_RETRY_BACKOFF_S == 2.0
    assert decide_module.GUARD_MIN_SECOND_ATTEMPT_S == 3.0
    got = decide_module.second_request_at(error, sent_at=0.0, failed_at=failed_at, hedge_at=10.0, deadline=15.0)
    if second_at is None:
        assert got is None
    else:
        assert got == pytest.approx(second_at)


@pytest.mark.parametrize("where", ["litellm_response_headers", "headers", "response"])
def test_retry_after_is_read_wherever_the_error_carries_it(where: str) -> None:
    cause = RuntimeError("429")
    cause.status_code = 429  # type: ignore[attr-defined]
    if where == "response":
        cause.response = httpx.Response(429, headers={"retry-after": "4"})  # type: ignore[attr-defined]
    else:
        setattr(cause, where, {"RETRY-AFTER": "4"})
    assert decide_module.provider_retry_after_s(decide_module.rate_limit_behind(_call_error(cause))) == 4.0


def test_a_retry_after_date_is_read_as_a_wait() -> None:
    when = format_datetime(datetime.now(UTC) + timedelta(seconds=6), usegmt=True)
    wait = decide_module.provider_retry_after_s(_rate_limited(when))
    assert wait is not None and 4.5 < wait <= 6.0


# ---------------------------------------------------------------------------
# Through the real node on the virtual clock: the real 15 s budget and the
# real constants, and the exact moments requests went out.
# ---------------------------------------------------------------------------

_BUSY_NO_WAIT = (
    "The service that checks each question is busy right now. Wait a little before trying the query again."
)


def _busy(seconds: int) -> str:
    unit = "second" if seconds == 1 else "seconds"
    return (
        "The service that checks each question is busy right now. "
        f"Try the query again in about {seconds} {unit}, not straight away."
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


def test_an_error_lasting_about_a_second_no_longer_ends_the_question(monkeypatch: pytest.MonkeyPatch) -> None:
    """RJ08's `blip`: the provider errors for one second after the first
    request, then answers. The second request goes when develop's last would
    have, about 2 s in, past the blip, and the question is admitted.

    MUTATION PROOF: sending the second request at once after an error turns
    this red: it lands inside the blip, and the step error follows."""
    first: list[float] = []

    def _blip() -> Any:
        now = asyncio.get_running_loop().time()
        first.append(now)
        return _connection_error() if now - first[0] < 1.0 else _ADMIT

    times = _classifier(monkeypatch, _blip)
    events, result, _, elapsed = _node(monkeypatch)
    assert result.get("step_error") is None
    assert _guard(events) == _ADMITTED
    assert len(times) == 2
    assert _gaps(times)[0] == pytest.approx(2.0, abs=0.01)
    assert elapsed == pytest.approx(2.0, abs=0.01)


def test_a_rate_limit_storm_costs_two_requests_and_says_to_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """R-10 (F-8.6-FJ04, FA02): every request is a 429 that names no wait.
    Two requests in all, the second after the backoff, never four; and the
    person is told to wait, not to retry now.

    MUTATION PROOF: calling `call_tier` with its own retry again
    (`retry=True`) turns this red on the request count."""
    times = _classifier(monkeypatch, _rate_limited)
    events, result, _, _ = _node(monkeypatch)
    assert result.get("step_error") == _rate_limit_error(None)
    assert _guard(events) is None
    assert len(times) == 2
    assert _gaps(times)[0] >= decide_module.GUARD_RETRY_BACKOFF_S


def test_a_providers_retry_after_is_honoured_when_it_fits(monkeypatch: pytest.MonkeyPatch) -> None:
    times = _classifier(monkeypatch, _rate_limited("3"), _ADMIT)
    events, result, _, _ = _node(monkeypatch)
    assert result.get("step_error") is None
    assert _guard(events) == _ADMITTED
    assert len(times) == 2
    assert _gaps(times)[0] == pytest.approx(3.0)


def test_a_retry_after_that_does_not_fit_says_when_to_come_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """R-10 (F-8.6-FA02): the provider says wait 20 s, which the budget
    cannot fit. No second request, at once, and the person is told to try
    again in about 20 seconds, with `retry_after_s` 20."""
    times = _classifier(monkeypatch, _rate_limited("20"))
    events, result, _, elapsed = _node(monkeypatch)
    assert result.get("step_error") == _rate_limit_error(20)
    assert _guard(events) is None
    assert len(times) == 1
    assert elapsed < 0.01


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
        "the first carried it and it has passed: one second",
    ],
)
def test_a_retry_after_is_honoured_whichever_request_carried_it(
    monkeypatch: pytest.MonkeyPatch, behaviours: tuple[Any, ...], requests: int, retry_after_s: int
) -> None:
    """R-10 (F-8.6-FA05): every request's `Retry-After` is read. The last arm
    is F-72-J04's: the message says "about 1 second", not "1 seconds"."""
    times = _classifier(monkeypatch, *behaviours)
    events, result, _, _ = _node(monkeypatch)
    assert result.get("step_error") == _rate_limit_error(retry_after_s)
    assert _guard(events) is None
    assert len(times) == requests


@pytest.mark.parametrize(
    ("waits", "message", "retry_after_s"),
    [
        ([(1.0, 0.0)], _busy(1), 1),
        ([(0.2, 0.0)], _busy(1), 1),
        ([(2.0, 0.0)], _busy(2), 2),
        ([(float("inf"), 0.0), (3.0, 0.0)], _busy(3), 3),
        ([(float("nan"), 0.0)], _BUSY_NO_WAIT, 0),
    ],
    ids=["one second", "less than a second", "two seconds", "an infinite wait is not a wait", "nan alone"],
)
def test_the_rate_limit_message_counts_seconds_in_words(
    monkeypatch: pytest.MonkeyPatch, waits: list[tuple[float, float]], message: str, retry_after_s: int
) -> None:
    """F-72-J04: "about 1 seconds, not straight away" read as broken. One
    is "second"; a wait that is not a number is not stated."""
    monkeypatch.setattr(graph_module, "time", SimpleNamespace(monotonic=lambda: 0.0))
    got = graph_module._rate_limited_step_error(waits)
    assert got["message"] == message
    assert got["retry_after_s"] == retry_after_s


def test_a_first_request_that_hangs_gets_a_second_where_develop_sent_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """F-72-A04: the first request hangs, and an identical second goes out
    beside it at 10 s, two thirds of the 15 s budget, where develop cut the
    first and sent a fresh one. It answers in 0.6 s. The hung first request
    is then cancelled and charged as a cancelled call.

    MUTATION PROOF: `GUARD_HEDGE_SHARE` at 4/15, the builder's 4 s hedge,
    turns this red on the send time (and the sweep red on A04's spells)."""
    times = _classifier(monkeypatch, "hang", 0.6)
    events, result, harness, elapsed = _node(monkeypatch)
    assert result.get("step_error") is None
    assert _guard(events) == _ADMITTED
    assert _gaps(times) == [pytest.approx(10.0)]
    assert elapsed == pytest.approx(10.6)
    assert times.cancelled == [1]
    assert harness.get_query_cost_usd(harness.trace_id) == pytest.approx(_CANCELLED_GUARD_CALL + _ANSWERED_GUARD_CALL)


@pytest.mark.parametrize("spell_s", [3.0, 5.0, 8.0])
def test_a_slow_spell_develop_outlasted_is_outlasted_again(monkeypatch: pytest.MonkeyPatch, spell_s: float) -> None:
    """F-72-A04, the adversary's burst: every request SENT during the first
    `spell_s` seconds hangs, and later ones answer in 0.6 s. The builder's
    4 s hedge sent both requests inside a 5 or 8 s spell and lost the
    search at 15 s; develop answered at 10.6 s, and so does this."""

    first: list[float] = []

    async def _acompletion(**_kwargs: Any) -> Any:
        now = asyncio.get_running_loop().time()
        first.append(now)
        if now - first[0] < spell_s:
            await asyncio.sleep(10_000)
        await asyncio.sleep(0.6)
        return fake_response(_ADMIT)

    monkeypatch.setattr(harness_module.litellm, "acompletion", _acompletion)
    events, result, _, elapsed = _node(monkeypatch)
    assert result.get("step_error") is None
    assert _guard(events) == _ADMITTED
    assert [t - first[0] for t in first] == [0.0, pytest.approx(10.0)]
    assert elapsed == pytest.approx(10.6)


def test_a_slow_first_reply_is_no_longer_thrown_away(monkeypatch: pytest.MonkeyPatch) -> None:
    """Card 72: develop cut the first request at 10 s and threw away a reply
    that would have come at 12 s. It now runs on; the hedge sent at 10 s is
    still hanging, is cancelled, and no third request goes."""
    times = _classifier(monkeypatch, 12.0, "hang")
    events, result, harness, elapsed = _node(monkeypatch)
    assert result.get("step_error") is None
    assert _guard(events) == _ADMITTED
    assert len(times) == 2
    assert elapsed == pytest.approx(12.0)
    assert times.cancelled == [2]
    assert harness.get_query_cost_usd(harness.trace_id) == pytest.approx(_CANCELLED_GUARD_CALL + _ANSWERED_GUARD_CALL)


def test_both_requests_slow_past_the_budget_give_todays_step_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """No verdict is still no answer: both requests hang, and at the
    guardrail's unchanged 15 s the question ends in today's step error."""
    times = _classifier(monkeypatch, "hang")
    assert graph_module.budget_for_step("guardrail", "lookup") == 15.0
    events, result, _, elapsed = _node(monkeypatch)
    assert result.get("step_error") == _STEP_ERROR
    assert _guard(events) is None
    assert len(times) == 2
    assert elapsed == pytest.approx(15.0)


def test_a_slow_failure_then_an_answer_is_admitted(monkeypatch: pytest.MonkeyPatch) -> None:
    """F-8.6-FJ11's own shape: a 503 at 9.8 s, and a second request that
    answers 4 s after it is sent. R-05's 2 s backoff put that answer at
    15.8 s, past the budget. The second now goes at the hedge point, 10 s,
    and the question is admitted at 14 s.

    MUTATION PROOF: dropping the hedge-point cap from `second_request_at`
    turns this red on the step error."""
    times = _classifier(monkeypatch, (9.8, _unavailable), (4.0, _ADMIT))
    events, result, _, elapsed = _node(monkeypatch)
    assert result.get("step_error") is None
    assert _guard(events) == _ADMITTED
    assert _gaps(times) == [pytest.approx(10.0)]
    assert elapsed == pytest.approx(14.0)


def test_the_log_names_each_requests_time_and_upstream_host_and_nothing_private(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Card 72, D's logging: one line per guard request with its elapsed
    time, the upstream host OpenRouter named, and the trace id; never the
    key, the question's text or the prompt."""
    times = _classifier(monkeypatch, "hang", (0.2, _ADMIT, "DeepInfra"))
    with caplog.at_level(logging.WARNING, logger=decide_module.__name__):
        _, _, harness, _ = _node(monkeypatch)
    ours = [r for r in caplog.records if r.getMessage().startswith("guard classification request")]
    assert {r.levelname for r in ours} == {"WARNING"}, "develop's log records WARNING and above only"
    lines = [r.getMessage() for r in ours]
    assert len(times) == 2
    assert len(lines) == 2, lines
    answered = next(line for line in lines if "request 2 of 2" in line)
    cancelled = next(line for line in lines if "request 1 of 2" in line)
    assert answered == f"guard classification request 2 of 2 (trace {harness.trace_id}): answered after 0.20s, upstream DeepInfra"
    assert cancelled.startswith(f"guard classification request 1 of 2 (trace {harness.trace_id}): cancelled")
    assert cancelled.endswith("upstream not named")
    for record in caplog.records:
        text = record.getMessage()
        assert "test-key" not in text
        assert _ORDINARY_QUESTION not in text
        assert "BRCA1" not in text


# ---------------------------------------------------------------------------
# F-72-J01, J10: when two usable replies are in hand, the stricter decides.
# ---------------------------------------------------------------------------

_INJECTION = json.dumps({**json.loads(COMPLIANT_GUARD_CLASSIFICATION), "is_injection": True, "reason": "probe"})
_REFUSED_INJECTION_CATEGORY = "injection"


@pytest.mark.parametrize(
    ("first", "second"),
    [((_ADMIT, 0), (_INJECTION, 0)), ((_INJECTION, 0), (_ADMIT, 0)), ((_ADMIT, 1), (_INJECTION, 0))],
    ids=[
        "the first admits, the second refuses, the same tick",
        "the first refuses, the second admits, the same tick",
        "the judge's probe: the refusal ends first, the admission one tick after",
    ],
)
def test_two_replies_in_hand_the_refusal_wins(
    monkeypatch: pytest.MonkeyPatch, first: tuple[str, int], second: tuple[str, int]
) -> None:
    """F-72-J01, through the real `guardrail_node`: both replies end at 12 s,
    in one loop pass or one tick apart. Before, the request with the lower
    number decided, so "admit" on request 1 admitted a question request 2
    had already called injection, and the log said that reply was
    cancelled. Now every reply in hand is read and the refusal wins.

    MUTATION PROOF: choosing the first usable reply by request number
    instead of the strictest turns the first arm red."""
    gate: dict[str, asyncio.Event] = {}
    replies = [first, second]
    count = [0]

    async def _acompletion(**_kwargs: Any) -> Any:
        count[0] += 1
        content, ticks_after = replies[count[0] - 1]
        if count[0] == 1:
            await asyncio.sleep(12.0)
            gate.setdefault("released", asyncio.Event()).set()
        else:
            await gate.setdefault("released", asyncio.Event()).wait()
        for _ in range(ticks_after):
            await asyncio.sleep(0)
        return fake_response(content)

    monkeypatch.setattr(harness_module.litellm, "acompletion", _acompletion)
    events, result, _, elapsed = _node(monkeypatch)
    guard = _guard(events)
    assert result.get("step_error") is None
    assert guard is not None and guard["passed"] is False and guard["category"] == _REFUSED_INJECTION_CATEGORY
    assert count[0] == 2
    assert elapsed == pytest.approx(12.0)


def test_the_stricter_reply_ranks_are_the_refusals_first() -> None:
    from system_03_search_agent.guardrail import classifier

    admit = classifier.parse_classification(_ADMIT)
    injection = classifier.parse_classification(_INJECTION)
    off = classifier.parse_classification(_OFF_TOPIC)
    ranks = [
        graph_module._classifier_strictness((c, classifier.verdict_for(c))) for c in (admit, off, injection)
    ]
    assert ranks == [0, 1, 2]
    pick = decide_module._pick_strictness("on_topic")
    assert pick(None) < pick("on_topic") < pick("off_topic")


# ---------------------------------------------------------------------------
# F-72-J06: an unusable fast reply never beats a usable slow one.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "behaviours",
    [((12.0, _ADMIT), (0.5, "I will look this up.")), ((11.0, "I will look this up."), (2.0, _ADMIT))],
    ids=["the hedge's reply is unusable, the first's usable", "the first's reply is unusable, the hedge's usable"],
)
def test_a_usable_slow_reply_beats_an_unusable_fast_one(
    monkeypatch: pytest.MonkeyPatch, behaviours: tuple[Any, ...]
) -> None:
    """Both requests in flight (the hedge went at 10 s); the one that ends
    first is unusable, the other answers later. The question waits for the
    usable reply and is admitted at 12 s.

    MUTATION PROOF: ending the question on an unusable reply while the
    other request still runs turns both arms red."""
    times = _classifier(monkeypatch, *behaviours)
    events, result, _, elapsed = _node(monkeypatch)
    assert result.get("step_error") is None
    assert _guard(events) == _ADMITTED
    assert len(times) == 2
    assert elapsed == pytest.approx(12.0)


# ---------------------------------------------------------------------------
# F-72-A05: no hedge with less than about 2 s left, and a request never sent
# is never charged.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("left_s", [4.3, 4.9, 5.9])
def test_no_hedge_goes_out_with_too_little_left(monkeypatch: pytest.MonkeyPatch, left_s: float) -> None:
    """The adversary's shape: the daily-cap checks before the classifier
    took long, leaving `left_s` of the 15 s. The hedge point then leaves
    less than `GUARD_MIN_HEDGE_S`, so no second request goes, and only the
    one request is charged, as a cut call.

    MUTATION PROOF: `GUARD_MIN_HEDGE_S` at 0 turns every arm red on the
    request count and the charge."""
    monkeypatch.setattr(
        cost_control, "check_system_daily_cost_cap", lambda *a, **k: graph_module.time.sleep(15.0 - left_s)
    )
    times = _classifier(monkeypatch, "hang")
    _, result, harness, elapsed = _node(monkeypatch)
    assert result.get("step_error") == _STEP_ERROR
    assert len(times) == 1
    assert elapsed == pytest.approx(15.0)
    assert harness.get_query_cost_usd(harness.trace_id) == pytest.approx(_CANCELLED_GUARD_CALL)


# ---------------------------------------------------------------------------
# No path passes the budget, no verdict is no answer, and never more than two
# requests in flight or in total.
# ---------------------------------------------------------------------------

_EVERY_FAILURE = [
    (("hang",), _STEP_ERROR),
    ((_rate_limited,), _rate_limit_error(None)),
    ((_rate_limited("6"), _rate_limited("6"), "hang"), _rate_limit_error(6)),
    ((_connection_error, _connection_error, "hang"), _STEP_ERROR),
    ((_rate_limited, _rate_limited, "hang"), _rate_limit_error(None)),
    (((2.0, _connection_error), "hang"), _STEP_ERROR),
    (("hang", _rate_limited("30")), None),
    (((9.8, _connection_error), (0.1, _connection_error), _ADMIT), _STEP_ERROR),
]
_EVERY_FAILURE_IDS = [
    "a hang every time",
    "a 429 every time",
    "429s naming a wait, then a hang",
    "two errors, then a hang",
    "429s naming none, then a hang",
    "a slower error, then a hang",
    "a hang, and a hedge rate-limited for 30 s",
    "a slow error with the second failing too: no third request",
]


@pytest.mark.parametrize(("behaviours", "step_error"), _EVERY_FAILURE, ids=_EVERY_FAILURE_IDS)
def test_no_verdict_is_no_answer_and_no_path_passes_the_budget(
    monkeypatch: pytest.MonkeyPatch, behaviours: tuple[Any, ...], step_error: dict[str, Any] | None
) -> None:
    """MUTATION PROOF: `GUARD_MAX_REQUESTS` at 3 turns the last arms red on
    the request count."""
    times = _classifier(monkeypatch, *behaviours)
    events, result, _, elapsed = _node(monkeypatch)
    if step_error is None:
        # The hedge at 10 s carried a 30 s Retry-After; 5 s later it is 25 s off.
        assert result.get("step_error") == _rate_limit_error(25)
    else:
        assert result.get("step_error") == step_error
    assert _guard(events) is None
    assert elapsed <= 15.0 + 1e-6, elapsed
    assert len(times) <= decide_module.GUARD_MAX_REQUESTS == 2
    assert times.peak <= 2


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


def test_a_guard_model_that_cannot_turn_reasoning_off_still_screens(monkeypatch: pytest.MonkeyPatch) -> None:
    """F-72-J08 at the front door: a guard model that refuses the reasoning
    block is resent without it, inside the one request, and the question is
    admitted, where the builder's `retry=False` failed it in 50 ms."""
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
# F-72-A02, J05: the relevancy decision's guard pick takes the same path.
# ---------------------------------------------------------------------------


def test_a_rate_limit_storm_gives_each_guard_call_two_requests_and_a_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """J05's own probe: every guard-model request is a 429 naming no wait,
    for a question the allowlist misses, so the relevancy decision's guard
    pick runs beside the classifier. Before, the pick's second request went
    out at once, ignoring the provider; now each call sends two at most,
    the second after the backoff.

    MUTATION PROOF: `_run_guard_pick` calling `call_tier` with its default
    retry again turns this red on the pick's gap."""
    sent: dict[str, list[float]] = {"classifier": [], "pick": []}

    async def _acompletion(**kwargs: Any) -> Any:
        which = "classifier" if _is_classifier_request(kwargs) else "pick"
        sent[which].append(asyncio.get_running_loop().time())
        raise _rate_limited()

    monkeypatch.setattr(harness_module.litellm, "acompletion", _acompletion)
    _, result, _, _ = _node(monkeypatch, _TREE_OF_LIFE)
    assert result.get("step_error") == _rate_limit_error(None)
    assert len(sent["classifier"]) == 2
    assert len(sent["pick"]) == 2
    assert _gaps(sent["pick"])[0] >= decide_module.GUARD_RETRY_BACKOFF_S


def test_the_relevancy_pick_honours_a_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[float] = []

    async def _acompletion(**kwargs: Any) -> Any:
        if _is_classifier_request(kwargs):
            return fake_response(_ADMIT)
        sent.append(asyncio.get_running_loop().time())
        raise _rate_limited("20")

    monkeypatch.setattr(harness_module.litellm, "acompletion", _acompletion)
    events, _, _, _ = _node(monkeypatch, _TREE_OF_LIFE)
    assert _guard(events) == _ADMITTED  # no pick fails open, as before
    assert len(sent) == 1


@pytest.mark.parametrize("jev", [None, "fails"], ids=["the guard provider", "Jev on, its relevancy pick failing"])
def test_in_a_slow_spell_a_question_the_allowlist_misses_is_not_held_to_15_s(
    monkeypatch: pytest.MonkeyPatch, jev: str | None
) -> None:
    """F-72-A02: every guard-model request sent in the first 8 s hangs;
    later ones answer in 0.6 s. The classifier's second request answers at
    10.6 s, and now the relevancy pick's does too, so "Why do naked mole
    rats live so long?" passes at about 10.6 s, where before its unhedged
    pick held it to the budget's end, 15 s."""
    if jev is not None:
        monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")

        async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
            return httpx.Response(500, content=b"down")

        monkeypatch.setattr(jev_client_module, "_post", _post)

        async def _call_jev(**_kwargs: Any) -> Any:
            raise jev_client_module.JevCallError("down", reason="http_error")

        monkeypatch.setattr(graph_module, "call_jev", _call_jev)
    started: list[float] = []

    async def _acompletion(**kwargs: Any) -> Any:
        now = asyncio.get_running_loop().time()
        started.append(now)
        if now - started[0] < 8.0:
            await asyncio.sleep(10_000)
        await asyncio.sleep(0.6)
        return fake_response(_ADMIT if _is_classifier_request(kwargs) else "on_topic")

    monkeypatch.setattr(harness_module.litellm, "acompletion", _acompletion)
    events, result, _, elapsed = _node(monkeypatch, "Why do naked mole rats live so long?")
    assert result.get("step_error") is None
    assert _guard(events) == _ADMITTED
    assert elapsed == pytest.approx(10.6, abs=0.01)


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
    judge put it (the cap check inside that net, before Jev's request), or
    while Jev's reply is being read. Before, the 0.6 s and 0.8 s stalls in
    the cap check spent the net's half-second margin and the question was
    refused as off topic. Now every clock on Jev counts only the time the
    loop was free, and Jev's admission stands.

    MUTATION PROOF: `wait_counting_free_time` counting real time again
    (`counted += now - last`) turns the cap-check and reply-read arms red:
    the question is refused as off topic."""
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
def test_no_usable_verdict_says_what_to_do_next(monkeypatch: pytest.MonkeyPatch, behaviours: tuple[Any, ...]) -> None:
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


def test_an_unusable_reply_then_an_error_keeps_the_errors_words(monkeypatch: pytest.MonkeyPatch) -> None:
    """The step error's words follow the last request to end, as before R-10:
    an unusable first reply, then a transient error on the second, is the
    transient step error, not "could not complete"."""
    times = _classifier(monkeypatch, "I will look this up.", _connection_error)
    events, result, _, _ = _node(monkeypatch)
    assert _guard(events) is None
    assert result.get("step_error") == _STEP_ERROR
    assert len(times) == 2
