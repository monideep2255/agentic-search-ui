"""R-10's fix round (F-72-A04): the guard classifier's hedged policy never
loses a search that develop's policy before card 72 would have answered.

## What this pins

The product owner's decision of 2026-09-29: over one grid of guard-model
behaviours, BOTH policies are run, develop's (re-land R-01 and follow-up
R-05: a first attempt of two thirds of the budget, cut there, then a
second with what is left, each through `call_tier`'s own retry) and the
one this branch ships (`harness.decide.ask_guard_model`). For every case
where develop's policy reaches a verdict inside the guardrail's 15 s, the
new one does too, with never more than two requests.

The provider's behaviour depends on WHEN a request is sent, not on which
request it is, because that is what the evidence shows: card 72's
diagnosis measured the guard model's upstream slow in bursts, and the
adversary's card 63 data shows failures clustered in time. The families:

- Slow spells in which every request sent hangs for good, of lengths
  either side of develop's 10 s cut (A04's own shape).
- Slow spells in which requests sent are held and answered when the spell
  ends, and slow windows with a long reply time.
- Stalls that start after the first request was sent and catch it in
  flight.
- Error spells (a 503 or a dropped connection) with the error arriving
  fast or slowly, from a single failed request to a spell past the budget.
- Rate-limit spells, with an honest `Retry-After` (the wait left in the
  spell) and with none.
- Spells of unusable replies, and a refused key.

## What it does not cover, and why

Two shapes no two-request policy can match develop on, because develop
spent up to four requests: a provider that fails the first two requests
and answers the third whatever the time, and a mix of two different
failures in sequence (a hang, then errors). And a provider that names a
`Retry-After` and answers before it is up: R-10 line 4 requires the wait
to be honoured, so the new policy waits where develop's immediate resend
ignored it. Errors that take between about 1.5 and 8 seconds to arrive,
in a spell, are covered as single failures only: there develop's four
requests put its last one later than a second request can go while
still leaving an isolated failure the time develop gave it. The fix
report states each of these.

## How it runs

On a virtual clock (`tests/system_03_search_agent/virtual_clock.py`): an
event loop whose `time()` jumps to the next timer instead of sleeping, with
`time.monotonic` in the guardrail's modules read from it. The real constants and the real 15 s budget apply, and the whole
grid runs in a few seconds.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import litellm
import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.guardrail import classifier
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import decide as decide_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.harness import HarnessCallError
from tests.system_03_search_agent.model_stub import COMPLIANT_GUARD_CLASSIFICATION, fake_response
from tests.system_03_search_agent.virtual_clock import run_virtual

_ADMIT = COMPLIANT_GUARD_CLASSIFICATION
_INJECTION = json.dumps({**json.loads(COMPLIANT_GUARD_CLASSIFICATION), "is_injection": True, "reason": "probe"})
_BUDGET_S = 15.0


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
    monkeypatch.setenv("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
    monkeypatch.delenv("CLASSIFIER_PROVIDER", raising=False)
    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", lambda *a, **k: None)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", lambda *a, **k: None)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )


# ---------------------------------------------------------------------------
# The provider's behaviour, by the time a request is sent.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Outcome:
    """What one request meets: `kind` is "answer", "unusable", "error",
    "rate_limit", "refused" or "hang"; `after_s` how long it takes."""

    kind: str
    after_s: float = 0.0
    retry_after_s: float | None = None
    content: str = _ADMIT


def _error() -> BaseException:
    return litellm.ServiceUnavailableError(message="503 (stub)", llm_provider="openrouter", model="m")


def _connection() -> BaseException:
    return litellm.APIConnectionError(message="connection reset (stub)", llm_provider="openrouter", model="m")


def _rate_limited(retry_after_s: float | None) -> BaseException:
    headers = {"Retry-After": f"{retry_after_s:.3f}"} if retry_after_s is not None else None
    return litellm.RateLimitError("rate limited (stub)", llm_provider="openrouter", model="m", headers=headers)


def _refused() -> BaseException:
    return litellm.AuthenticationError(message="401 (stub)", llm_provider="openrouter", model="m")


@dataclass(frozen=True)
class _Provider:
    """One provider behaviour: `outcome(sent_s)` by the seconds since the
    question's guardrail began."""

    name: str
    outcome: Callable[[float], _Outcome]


def _spell_hang(length_s: float, reply_s: float) -> _Provider:
    """Every request sent during the first `length_s` hangs for good (A04)."""
    return _Provider(
        f"hang spell {length_s}s, then {reply_s}s replies",
        lambda t: _Outcome("hang") if t < length_s else _Outcome("answer", reply_s),
    )


def _spell_held(length_s: float, reply_s: float) -> _Provider:
    """Requests sent during the spell are held and answered as it ends."""
    return _Provider(
        f"held spell {length_s}s, then {reply_s}s replies",
        lambda t: _Outcome("answer", max(0.0, length_s - t) + reply_s),
    )


def _slow_window(length_s: float, slow_s: float, reply_s: float) -> _Provider:
    return _Provider(
        f"slow window {length_s}s at {slow_s}s, then {reply_s}s",
        lambda t: _Outcome("answer", slow_s) if t < length_s else _Outcome("answer", reply_s),
    )


def _stall_in_flight(start_s: float, end_s: float, reply_s: float) -> _Provider:
    """A stall from `start_s` to `end_s` loses every request that is being
    served at any moment inside it, the first included."""

    def _outcome(t: float) -> _Outcome:
        if t < end_s and t + reply_s > start_s:
            return _Outcome("hang")
        return _Outcome("answer", reply_s)

    return _Provider(f"stall {start_s}-{end_s}s in flight, {reply_s}s replies", _outcome)


def _error_spell(length_s: float, fail_after_s: float, reply_s: float, kind: str = "error") -> _Provider:
    return _Provider(
        f"{kind} spell {length_s}s failing after {fail_after_s}s, then {reply_s}s",
        lambda t: _Outcome(kind, fail_after_s) if t < length_s else _Outcome("answer", reply_s),
    )


def _rate_limit_spell(length_s: float, fail_after_s: float, reply_s: float, *, honest: bool) -> _Provider:
    """429s for every request sent in the spell; `honest` ones name the wait
    left in the spell, the others name none."""

    def _outcome(t: float) -> _Outcome:
        if t < length_s:
            return _Outcome("rate_limit", fail_after_s, retry_after_s=(length_s - t) if honest else None)
        return _Outcome("answer", reply_s)

    label = "honest Retry-After" if honest else "no Retry-After"
    return _Provider(f"429 spell {length_s}s ({label}) after {fail_after_s}s, then {reply_s}s", _outcome)


def _grid() -> list[_Provider]:
    replies = (0.6, 1.5, 3.0)
    grid: list[_Provider] = []
    for length_s, reply_s in itertools.product((0.5, 3.0, 5.0, 8.0, 9.9, 10.5, 12.0, 20.0), replies):
        grid.append(_spell_hang(length_s, reply_s))
    for length_s, reply_s in itertools.product((3.0, 8.0, 11.0, 14.5, 20.0), replies):
        grid.append(_spell_held(length_s, reply_s))
    for length_s, slow_s, reply_s in itertools.product((3.0, 8.0, 12.0, 20.0), (4.0, 9.0, 11.0, 14.0), replies):
        grid.append(_slow_window(length_s, slow_s, reply_s))
    for (start_s, end_s), reply_s in itertools.product(((0.2, 3.0), (1.0, 8.0), (1.0, 12.0), (0.5, 20.0)), replies):
        grid.append(_stall_in_flight(start_s, end_s, reply_s))
    for kind, (length_s, fail_after_s), reply_s in itertools.product(
        ("error", "connection"),
        itertools.product((0.01, 1.0, 2.0, 2.2, 3.0, 5.0, 8.0, 12.0, 20.0), (0.05, 0.5, 1.0)),
        replies,
    ):
        grid.append(_error_spell(length_s, fail_after_s, reply_s, kind))
    # Slow errors and medium ones: a single failed request (see the module
    # docstring for why a spell of them is not in the grid).
    for fail_after_s, reply_s in itertools.product((2.0, 4.0, 6.0, 9.8, 12.0), replies):
        grid.append(_error_spell(0.01, fail_after_s, reply_s))
    for (length_s, fail_after_s), reply_s, honest in itertools.product(
        itertools.product((0.01, 1.0, 3.0, 8.0, 11.0, 20.0), (0.05, 0.5)), replies, (True, False)
    ):
        grid.append(_rate_limit_spell(length_s, fail_after_s, reply_s, honest=honest))
    for (length_s, fail_after_s), reply_s in itertools.product(
        itertools.product((0.01, 3.0, 20.0), (0.05, 1.0, 6.0)), replies
    ):
        grid.append(_error_spell(length_s, fail_after_s, reply_s, "unusable"))
    grid.append(_error_spell(20.0, 0.05, 0.6, "refused"))
    return grid


class _Stub:
    """`litellm.acompletion` for one provider, counting the requests sent."""

    def __init__(self, provider: _Provider, started: float, loop_time: Callable[[], float]) -> None:
        self.provider = provider
        self.started = started
        self.loop_time = loop_time
        self.sent: list[float] = []

    async def __call__(self, **_kwargs: Any) -> Any:
        sent_s = self.loop_time() - self.started
        self.sent.append(sent_s)
        outcome = self.provider.outcome(sent_s)
        if outcome.kind == "hang":
            await asyncio.sleep(10_000)
        await asyncio.sleep(outcome.after_s)
        if outcome.kind == "answer":
            return fake_response(outcome.content)
        if outcome.kind == "unusable":
            return fake_response("I will look this up.")
        if outcome.kind == "error":
            raise _error()
        if outcome.kind == "connection":
            raise _connection()
        if outcome.kind == "rate_limit":
            raise _rate_limited(outcome.retry_after_s)
        raise _refused()


# ---------------------------------------------------------------------------
# Develop's policy (d23674f4), kept here as the yardstick, and the new one.
# ---------------------------------------------------------------------------

_DEVELOP_FIRST_ATTEMPT_SHARE = 2 / 3
_DEVELOP_BACKOFF_S = 2.0
_DEVELOP_MIN_SECOND_ATTEMPT_S = 3.0


def _develop_retry_wait_s(exc: HarnessCallError, remaining_s: float) -> float | None:
    """Develop's `_classifier_retry_wait_s`, line for line."""
    if exc.source.startswith("harness.enforce_timeout"):
        return 0.0
    rate_limit = decide_module.rate_limit_behind(exc)
    stated = decide_module.provider_retry_after_s(rate_limit) if rate_limit is not None else None
    if stated is not None:
        wait_s = max(stated, _DEVELOP_BACKOFF_S)
        return wait_s if wait_s + _DEVELOP_MIN_SECOND_ATTEMPT_S <= remaining_s else None
    return max(0.0, min(_DEVELOP_BACKOFF_S, remaining_s - _DEVELOP_MIN_SECOND_ATTEMPT_S))


async def _develop_policy(harness: Any, trace_id: str, messages: Any, deadline: float, now: Callable[[], float]) -> bool:
    """Develop's two attempts in `_guardrail_after_prefilter`, line for line:
    True when a verdict was reached."""
    for attempt in (1, 2):
        remaining_s = deadline - now()
        if remaining_s <= 0:
            return False
        budget_s = remaining_s * _DEVELOP_FIRST_ATTEMPT_SHARE if attempt == 1 else remaining_s
        try:
            response = await graph_module._dispatch_tier_call(
                harness, trace_id, "guard", "guardrail", messages, budget_s=budget_s, cache_prefix=None
            )
        except HarnessCallError as exc:
            if attempt == 2 or exc.error_class != "transient":
                return False
            wait_s = _develop_retry_wait_s(exc, deadline - now())
            if wait_s is None:
                return False
            if wait_s > 0:
                await asyncio.sleep(wait_s)
            continue
        try:
            classifier.verdict_for(classifier.parse_classification(response.content))
            return True
        except classifier.ClassificationUnavailableError:
            continue
    return False


@dataclass
class _Run:
    verdict: bool
    requests: int
    elapsed_s: float


def _run_policy(
    monkeypatch: pytest.MonkeyPatch, provider: _Provider, *, develop: bool, budget_s: float = _BUDGET_S
) -> _Run:
    async def _go() -> _Run:
        loop = asyncio.get_running_loop()
        started = loop.time()
        stub = _Stub(provider, started, loop.time)
        monkeypatch.setattr(harness_module.litellm, "acompletion", stub)
        trace_id = f"t-{uuid.uuid4().hex[:8]}"
        harness = harness_module.Harness(trace_id)
        messages = classifier.build_messages("Which diseases are associated with BRCA1?")
        deadline = started + budget_s
        if develop:
            verdict = await _develop_policy(harness, trace_id, messages, deadline, loop.time)
        else:
            asked = await graph_module._classify_within_budget(harness, trace_id, messages, deadline)
            verdict = isinstance(asked, tuple)
        return _Run(verdict=verdict, requests=len(stub.sent), elapsed_s=loop.time() - started)

    return run_virtual(monkeypatch, _go)


#: The guardrail's whole budget, and what is left of it when the daily-cap
#: checks before the classifier took three seconds.
_BUDGETS_S = (_BUDGET_S, 12.0)


def _sweep(monkeypatch: pytest.MonkeyPatch, grid: list[_Provider] | None = None) -> tuple[int, int, list[str]]:
    """Every provider in the grid under both policies, at each budget:
    (cases, cases develop answered, every case that breaks dominance, the
    budget or the cap)."""
    problems: list[str] = []
    answered = cases = 0
    for provider, budget_s in itertools.product(grid or _grid(), _BUDGETS_S):
        cases += 1
        develop = _run_policy(monkeypatch, provider, develop=True, budget_s=budget_s)
        new = _run_policy(monkeypatch, provider, develop=False, budget_s=budget_s)
        answered += develop.verdict
        where = f"{provider.name}, budget {budget_s}s"
        if develop.verdict and not new.verdict:
            problems.append(f"{where}: develop answered, the new policy did not")
        if new.requests > decide_module.GUARD_MAX_REQUESTS:
            problems.append(f"{where}: {new.requests} requests")
        if new.elapsed_s > budget_s + 1e-6:
            problems.append(f"{where}: ended at {new.elapsed_s:.2f}s")
    return cases, answered, problems


def test_the_new_policy_answers_every_search_develop_answers_with_two_requests_at_most(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-72-A04. The grid's size and develop's answered count are pinned too,
    so a grid that shrank or stopped exercising develop would show here."""
    cases, answered, problems = _sweep(monkeypatch)
    assert problems == [], "\n".join(problems[:20])
    assert cases == len(_grid()) * len(_BUDGETS_S) >= 750
    assert answered >= cases // 2, (answered, cases)


def test_the_sweep_catches_the_four_second_hedge(monkeypatch: pytest.MonkeyPatch) -> None:
    """The sweep is not vacuous: the builder's hedge at 4 s of 15, a share
    of 4/15, loses A04's spells, and the sweep says so."""
    monkeypatch.setattr(decide_module, "GUARD_HEDGE_SHARE", 4 / 15)
    _, _, problems = _sweep(monkeypatch)
    lost = [p for p in problems if p.startswith(("hang spell 5.0s", "hang spell 8.0s"))]
    assert lost, problems[:5]


def test_the_sweep_catches_a_retry_at_once_after_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nor is it blind to the other timing: a second request sent at once
    after an error lands inside an error spell that develop's backoff and
    second attempt outlast (RJ08's blip)."""
    monkeypatch.setattr(
        decide_module,
        "second_request_at",
        lambda error, *, sent_at, failed_at, hedge_at, deadline: (
            None if error is not None and error.error_class != "transient" else failed_at
        ),
    )
    _, _, problems = _sweep(monkeypatch)
    assert any(p.startswith("error spell 1.0s") for p in problems), problems[:5]


def test_a_third_request_is_never_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cap holds against a provider that would answer a third request."""
    run = _run_policy(monkeypatch, _error_spell(20.0, 0.05, 0.6), develop=False)
    assert run.requests == 2 and not run.verdict
    develop = _run_policy(monkeypatch, _error_spell(20.0, 0.05, 0.6), develop=True)
    assert develop.requests == 4, "develop spent four requests on the same spell"
