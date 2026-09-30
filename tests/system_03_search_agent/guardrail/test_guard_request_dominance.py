"""Card 84 (R-10 without card 72's hedge): the guard calls' two-request
policy never loses a search develop answers, and never answers it later or
differently, wherever develop answered within two requests.

## What this pins

Over one grid of provider behaviours that vary BOTH the timing and the
verdict of each reply (the lesson of 2026-09-29 in `LEARNINGS.md`: card
72's sweep varied only timings and missed a slow off-topic losing to a
fast on-topic), two policies are run:

- Develop's, at `d9e05c4e`: re-land R-01 and follow-up R-05 for the
  classifier (a first attempt of two thirds of the budget, then a second
  with the rest, each through `call_tier`'s own immediate resend, with
  R-05's backoff between them), and `call_tier`'s default retry for the
  relevancy decision's guard pick. Ported line for line below as the
  yardstick, since develop's code is replaced on this branch.
- This branch's, through the REAL code: the guardrail node for the
  classifier, and `harness.decide._run_guard_pick` for the pick.

For every case, the new policy sends at most two requests, never two at
once, and never passes the budget. For every case where develop reached a
verdict (an admission or a refusal) within its first two requests, and no
request before it stated a `Retry-After`, the new policy reaches the SAME
verdict, no later. Nothing races: one reply decides, the first usable one
in sequence, exactly as on develop.

## The two classes it cannot hold, counted rather than hidden

- Develop's verdict came from its third or fourth request. The two-request
  cap (R-10 line 4) forbids those, so such a search can be lost, for
  example an error lasting about a second that fails the first two
  requests (R-05's RJ08 blip). Counted as `third_request`.
- A request before develop's verdict stated a `Retry-After`, which develop's
  immediate resend ignored and R-10 line 4 now honours. Counted as
  `stated_wait`.

Both counts are asserted to be the only places the policies differ, and
reported by `test_the_sweep_reports_what_the_cap_gives_up`.

## How it runs

On the virtual clock (`tests/system_03_search_agent/virtual_clock.py`), with
the real constants and the real 15-second budget.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
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

_REPLIES = {
    "admit": COMPLIANT_GUARD_CLASSIFICATION,
    "injection": json.dumps({**json.loads(COMPLIANT_GUARD_CLASSIFICATION), "is_injection": True, "reason": "probe"}),
    "off-topic": json.dumps({**json.loads(COMPLIANT_GUARD_CLASSIFICATION), "is_off_topic": True}),
}
_QUESTION = "Which diseases are associated with BRCA1?"


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
# What one request meets.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Outcome:
    """What one request meets.

    - `kind`: "reply", "unusable", "error", "rate_limit", "refused" or
      "hang".
    - `verdict`, for a reply: a key of `_REPLIES` for the classifier, or
      the pick's own "on_topic" or "off_topic".
    - `after_s`: how long it takes; `retry_after_s`: a 429's stated wait.
    """

    kind: str
    after_s: float = 0.0
    verdict: str = "admit"
    retry_after_s: float | None = None

    def label(self) -> str:
        if self.kind == "reply":
            return f"{self.verdict}@{self.after_s:g}"
        if self.kind == "rate_limit":
            wait = "none" if self.retry_after_s is None else f"{self.retry_after_s:g}"
            return f"429(wait {wait})@{self.after_s:g}"
        return f"{self.kind}@{self.after_s:g}" if self.kind != "hang" else "hang"


@dataclass(frozen=True)
class _Provider:
    """`outcome(index, sent_s)`: request `index` (1-based), sent `sent_s`
    seconds after the call began."""

    name: str
    outcome: Callable[[int, float], _Outcome]


class _Stub:
    """`litellm.acompletion` for one provider: counts the requests sent, the
    most in flight at once, and whether a request before the last stated a
    wait."""

    def __init__(self, provider: _Provider, started: float, loop_time: Callable[[], float]) -> None:
        self.provider = provider
        self.started = started
        self.loop_time = loop_time
        self.sent: list[float] = []
        self.outcomes: list[_Outcome] = []
        self.active = 0
        self.peak = 0

    async def __call__(self, **kwargs: Any) -> Any:
        sent_s = self.loop_time() - self.started
        self.sent.append(sent_s)
        outcome = self.provider.outcome(len(self.sent), sent_s)
        self.outcomes.append(outcome)
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            if outcome.kind == "hang":
                await asyncio.sleep(10_000)
            await asyncio.sleep(outcome.after_s)
            if outcome.kind == "reply":
                return fake_response(_REPLIES.get(outcome.verdict, outcome.verdict))
            if outcome.kind == "unusable":
                return fake_response("I will look this up.")
            if outcome.kind == "error":
                raise litellm.ServiceUnavailableError(message="503 (stub)", llm_provider="openrouter", model="m")
            if outcome.kind == "rate_limit":
                headers = None if outcome.retry_after_s is None else {"Retry-After": f"{outcome.retry_after_s:g}"}
                raise litellm.RateLimitError("rate limited (stub)", llm_provider="openrouter", model="m", headers=headers)
            raise litellm.AuthenticationError(message="401 (stub)", llm_provider="openrouter", model="m")
        finally:
            self.active -= 1


# ---------------------------------------------------------------------------
# The grid: every ordered triple of per-request behaviours (develop may send
# up to four; the fourth repeats the third), and time-dependent providers
# whose verdict changes with the time a request is sent.
# ---------------------------------------------------------------------------


def _classifier_behaviours() -> list[_Outcome]:
    behaviours = [
        _Outcome("reply", after_s, verdict)
        for verdict, after_s in itertools.product(("admit", "injection", "off-topic"), (0.3, 6.0, 12.0))
    ]
    behaviours += [
        _Outcome("unusable", 0.3),
        _Outcome("error", 0.05),
        _Outcome("error", 9.0),
        _Outcome("rate_limit", 0.05),
        _Outcome("rate_limit", 0.05, retry_after_s=2.0),
        _Outcome("rate_limit", 0.05, retry_after_s=13.0),
        _Outcome("refused", 0.05),
        _Outcome("hang"),
    ]
    return behaviours


def _by_index(outcomes: tuple[_Outcome, ...]) -> _Provider:
    name = " | ".join(o.label() for o in outcomes)
    return _Provider(name, lambda index, _t: outcomes[min(index, len(outcomes)) - 1])


def _by_time(before: _Outcome, after: _Outcome, switch_s: float) -> _Provider:
    """Requests sent before `switch_s` meet `before`, later ones `after`: a
    slow off-topic against a fast on-topic, an error spell then an answer,
    and so on."""
    return _Provider(
        f"sent before {switch_s:g}s: {before.label()}, after: {after.label()}",
        lambda _index, t: before if t < switch_s else after,
    )


def _classifier_grid() -> list[_Provider]:
    behaviours = _classifier_behaviours()
    grid = [_by_index(triple) for triple in itertools.product(behaviours, repeat=3)]
    firsts = [b for b in behaviours if b.kind != "refused"]
    thens = [_Outcome("reply", 0.6, v) for v in ("admit", "injection", "off-topic")]
    for before, after, switch_s in itertools.product(firsts, thens, (0.5, 1.0, 2.5, 9.5, 11.0)):
        grid.append(_by_time(before, after, switch_s))
    return grid


# ---------------------------------------------------------------------------
# Develop's policies (d9e05c4e), ported line for line as the yardstick.
# ---------------------------------------------------------------------------

#: The harness's own methods, held here so a mutation of the harness in a
#: test below reaches only the new policy, never the yardstick.
_CALL_TIER = harness_module.Harness.call_tier
_ENFORCE_TIMEOUT = harness_module.Harness.enforce_timeout

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


async def _develop_classifier(harness: Any, trace_id: str, deadline: float, now: Callable[[], float]) -> str | None:
    """Develop's two attempts in `_guardrail_after_prefilter`, line for line:
    the verdict's category ("ok", "injection", "off_topic"), or None."""
    messages = classifier.build_messages(_QUESTION)
    for attempt in (1, 2):
        remaining_s = deadline - now()
        if remaining_s <= 0:
            return None
        budget_s = remaining_s * _DEVELOP_FIRST_ATTEMPT_SHARE if attempt == 1 else remaining_s
        try:
            response = await _ENFORCE_TIMEOUT(
                harness, "guardrail", _CALL_TIER(harness, "guard", messages, cache_prefix=None), budget_s
            )
        except HarnessCallError as exc:
            if attempt == 2 or exc.error_class != "transient":
                return None
            wait_s = _develop_retry_wait_s(exc, deadline - now())
            if wait_s is None:
                return None
            if wait_s > 0:
                await asyncio.sleep(wait_s)
            continue
        try:
            verdict = classifier.verdict_for(classifier.parse_classification(response.content))
        except classifier.ClassificationUnavailableError:
            continue
        return "ok" if verdict.admitted else verdict.category
    return None


async def _develop_pick(harness: Any, trace_id: str) -> str | None:
    """Develop's `_run_guard_pick`, line for line."""
    messages = decide_module._build_guard_messages("tree of life", ["on_topic", "off_topic"])
    try:
        response = await _ENFORCE_TIMEOUT(
            harness, "guardrail", _CALL_TIER(harness, "guard", messages), decide_module._GUARD_BUDGET_S
        )
    except HarnessCallError:
        return None
    return decide_module._parse_guard_choice(response.content, ["on_topic", "off_topic"])


# ---------------------------------------------------------------------------
# Running one case under one policy.
# ---------------------------------------------------------------------------


@dataclass
class _Run:
    verdict: str | None
    elapsed_s: float
    requests: int
    peak: int
    stated_wait_before_verdict: bool = False
    outcomes: list[_Outcome] = field(default_factory=list)


def _run(monkeypatch: pytest.MonkeyPatch, provider: _Provider, *, develop: bool, pick: bool = False, budget_s: float = 15.0) -> _Run:
    async def _go() -> _Run:
        loop = asyncio.get_running_loop()
        started = loop.time()
        stub = _Stub(provider, started, loop.time)
        monkeypatch.setattr(harness_module.litellm, "acompletion", stub)
        trace_id = f"t-{uuid.uuid4().hex[:8]}"
        harness = harness_module.Harness(trace_id)
        verdict: str | None
        if pick and develop:
            verdict = await _develop_pick(harness, trace_id)
        elif pick:
            verdict = await decide_module._run_guard_pick(
                harness, trace_id, "tree of life", ["on_topic", "off_topic"], point="guardrail.relevancy"
            )
        elif develop:
            verdict = await _develop_classifier(harness, trace_id, started + budget_s, loop.time)
        else:
            from system_03_search_agent.contracts.query import Query, RequestContext

            state = {
                "query": Query(text=_QUESTION, session_id="dominance", trace_id=trace_id),
                "context": RequestContext(surface="rest_sse"),
                "harness": harness,
                "seq": 0,
                "start_monotonic": started,
            }
            monkeypatch.setattr(graph_module, "_step_deadline", lambda *_a, **_k: started + budget_s)
            result = await graph_module.guardrail_node(state)  # type: ignore[arg-type]
            guard = next((e.payload for e in result.get("events", []) if e.type == "guard"), None)
            verdict = None if guard is None else guard["category"]
        stated = any(o.kind == "rate_limit" and (o.retry_after_s or 0) > 0 for o in stub.outcomes[:-1])
        return _Run(verdict, loop.time() - started, len(stub.sent), stub.peak, stated, list(stub.outcomes))

    return run_virtual(monkeypatch, _go)


@dataclass
class _Sweep:
    cases: int = 0
    develop_answered: int = 0
    held: int = 0
    problems: list[str] = field(default_factory=list)
    classes: Counter[str] = field(default_factory=Counter)


def _sweep(monkeypatch: pytest.MonkeyPatch, grid: list[_Provider], *, pick: bool = False, budgets: tuple[float, ...] = (15.0,)) -> _Sweep:
    """Both policies over `grid`: what dominance promises, checked case by
    case, and the two classes it cannot hold, counted."""
    sweep = _Sweep()
    for provider, budget_s in itertools.product(grid, budgets):
        sweep.cases += 1
        old = _run(monkeypatch, provider, develop=True, pick=pick, budget_s=budget_s)
        new = _run(monkeypatch, provider, develop=False, pick=pick, budget_s=budget_s)
        where = f"{provider.name}, budget {budget_s:g}s"
        if new.requests > decide_module.GUARD_MAX_REQUESTS:
            sweep.problems.append(f"{where}: {new.requests} requests")
        if new.peak > 1:
            sweep.problems.append(f"{where}: {new.peak} requests in flight at once")
        if new.elapsed_s > (decide_module._GUARD_BUDGET_S if pick else budget_s) + 1e-6:
            sweep.problems.append(f"{where}: ended at {new.elapsed_s:.2f}s")
        if old.verdict is None:
            continue
        sweep.develop_answered += 1
        if old.requests > decide_module.GUARD_MAX_REQUESTS:
            kind = "third_request"
        elif old.stated_wait_before_verdict:
            kind = "stated_wait"
        else:
            if new.verdict != old.verdict:
                sweep.problems.append(f"{where}: develop {old.verdict}, new {new.verdict}")
            elif new.elapsed_s > old.elapsed_s + 1e-6:
                sweep.problems.append(f"{where}: develop {old.elapsed_s:.2f}s, new {new.elapsed_s:.2f}s")
            else:
                sweep.held += 1
            continue
        if new.verdict is None:
            sweep.classes[f"{kind}: lost"] += 1
        elif new.verdict != old.verdict:
            sweep.classes[f"{kind}: {old.verdict} on develop, {new.verdict} here"] += 1
        elif new.elapsed_s > old.elapsed_s + 1e-6:
            sweep.classes[f"{kind}: same, later"] += 1
        else:
            sweep.classes[f"{kind}: same, no later"] += 1
    return sweep


# The sweeps are run once per module and read by the tests below.
_RESULTS: dict[str, _Sweep] = {}


def _classifier_sweep(monkeypatch: pytest.MonkeyPatch) -> _Sweep:
    if "classifier" not in _RESULTS:
        _RESULTS["classifier"] = _sweep(monkeypatch, _classifier_grid(), budgets=(15.0, 12.0))
    return _RESULTS["classifier"]


def _pick_grid() -> list[_Provider]:
    behaviours = [
        _Outcome("reply", after_s, verdict)
        for verdict, after_s in itertools.product(("on_topic", "off_topic"), (0.3, 6.0, 12.0))
    ]
    behaviours += [
        _Outcome("unusable", 0.3),
        _Outcome("error", 0.05),
        _Outcome("error", 9.0),
        _Outcome("rate_limit", 0.05),
        _Outcome("rate_limit", 0.05, retry_after_s=2.0),
        _Outcome("rate_limit", 0.05, retry_after_s=13.0),
        _Outcome("refused", 0.05),
        _Outcome("hang"),
    ]
    grid = [_by_index(pair) for pair in itertools.product(behaviours, repeat=2)]
    thens = [_Outcome("reply", 0.6, v) for v in ("on_topic", "off_topic")]
    for before, after, switch_s in itertools.product(behaviours, thens, (0.5, 2.5, 11.0)):
        grid.append(_by_time(before, after, switch_s))
    return grid


def test_the_classifier_never_loses_or_slows_a_search_develop_answered_within_two_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acceptance line 1. Every case: at most two requests, never two at
    once, never past the budget. Every case develop answered within two
    requests with no stated wait before its verdict: the same verdict, no
    later. The grid's size and the count held are pinned, so a grid that
    shrank or stopped exercising develop would show here."""
    sweep = _classifier_sweep(monkeypatch)
    assert sweep.problems == [], "\n".join(sweep.problems[:20])
    assert sweep.cases == len(_classifier_grid()) * 2 >= 10_000
    assert sweep.held >= sweep.develop_answered // 2, (sweep.held, sweep.develop_answered)
    differing = {k: v for k, v in sweep.classes.items() if "same, no later" not in k}
    assert all(k.startswith(("third_request", "stated_wait")) for k in differing), differing


def test_the_relevancy_pick_never_loses_or_slows_a_pick_develop_made_without_a_stated_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The relevancy decision's guard pick: develop's `call_tier` already
    sent at most two requests, so every pick develop made is made here, the
    same, no later, except where a request stated a wait."""
    sweep = _sweep(monkeypatch, _pick_grid(), pick=True)
    assert sweep.problems == [], "\n".join(sweep.problems[:20])
    assert sweep.cases == len(_pick_grid()) >= 250
    assert set(sweep.classes) <= {k for k in sweep.classes if k.startswith("stated_wait")}
    assert sweep.held >= sweep.develop_answered // 2


def test_the_sweep_reports_what_the_cap_gives_up(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """The two classes dominance cannot hold, printed with their counts for
    the builder's report (`pytest -s`). An error lasting about a second that
    fails develop's first two requests (R-05's RJ08 blip) is lost: develop
    answered it on its third request."""
    sweep = _classifier_sweep(monkeypatch)
    with capsys.disabled():
        print(f"\nclassifier sweep: {sweep.cases} cases, develop answered {sweep.develop_answered}, "
              f"held {sweep.held}")
        for key, count in sorted(sweep.classes.items()):
            print(f"  {key}: {count}")
    blip = _by_time(_Outcome("error", 0.05), _Outcome("reply", 0.6, "admit"), 1.0)
    old = _run(monkeypatch, blip, develop=True)
    new = _run(monkeypatch, blip, develop=False)
    assert (old.verdict, old.requests) == ("ok", 3)
    assert (new.verdict, new.requests) == (None, 2)
    assert sweep.classes["third_request: lost"] > 0


# ---------------------------------------------------------------------------
# The sweep is not vacuous: each shape it exists to catch turns it red.
# ---------------------------------------------------------------------------


def _mutated(monkeypatch: pytest.MonkeyPatch, grid: list[_Provider]) -> list[str]:
    return _sweep(monkeypatch, grid).problems


_SMALL_GRID = [
    _by_index(t)
    for t in itertools.product(
        [
            _Outcome("reply", 0.3, "admit"),
            _Outcome("reply", 12.0, "off-topic"),
            _Outcome("reply", 0.3, "injection"),
            _Outcome("error", 0.05),
            _Outcome("error", 9.0),
            _Outcome("hang"),
            _Outcome("unusable", 0.3),
        ],
        repeat=2,
    )
] + [
    _by_time(_Outcome("reply", 6.0, "off-topic"), _Outcome("reply", 0.6, "admit"), 3.0),
    _by_time(_Outcome("error", 0.05), _Outcome("reply", 0.6, "admit"), 0.5),
]


def test_the_sweep_catches_a_hedge(monkeypatch: pytest.MonkeyPatch) -> None:
    """Card 72's V08 shape: a second request sent while the first is still
    running, the first usable reply deciding. The slow off-topic loses to a
    fast admission, and the sweep says so, on the verdict."""
    real = decide_module.ask_guard_model

    async def _hedged(harness: Any, trace_id: str, messages: Any, **kwargs: Any) -> Any:
        first = asyncio.ensure_future(real(harness, trace_id, messages, **{**kwargs, "retry_unusable": False}))
        await asyncio.wait({first}, timeout=4.0)
        if first.done():
            return first.result()
        second = asyncio.ensure_future(real(harness, trace_id, messages, **{**kwargs, "retry_unusable": False}))
        done, _ = await asyncio.wait({first, second}, return_when=asyncio.FIRST_COMPLETED)
        winner = done.pop()
        for task in (first, second):
            if task is not winner:
                task.cancel()
        return winner.result()

    monkeypatch.setattr(graph_module, "ask_guard_model", _hedged)
    problems = _mutated(monkeypatch, _SMALL_GRID)
    assert any("in flight at once" in p for p in problems), problems[:5]
    assert any("develop off_topic, new ok" in p for p in problems), problems[:5]


def test_the_sweep_catches_a_backoff_after_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """F-72-V06's shape: a second request held back two seconds after an
    error makes an isolated failure slower than develop, and the sweep says
    so, on the time."""

    async def _backoff_call_tier(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return await _CALL_TIER(self, *args, **kwargs)
        except HarnessCallError:
            await asyncio.sleep(2.0)
            raise

    monkeypatch.setattr(harness_module.Harness, "call_tier", _backoff_call_tier)
    problems = _mutated(monkeypatch, _SMALL_GRID)
    assert any("develop 0.35s, new 2.35s" in p for p in problems), problems[:5]


def test_the_sweep_catches_a_second_request_cut_at_the_first_share(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first share applied to the second request too: a slow failure
    then a slow answer inside the budget is lost where the new policy
    promises it (FJ11), and a verdict develop reached is lost."""
    real = decide_module.ask_guard_model

    async def _cut(*args: Any, **kwargs: Any) -> Any:
        share = kwargs.get("first_share", 1.0)
        start = asyncio.get_running_loop().time()
        deadline = kwargs["deadline"]
        kwargs["deadline"] = start + (deadline - start) * share if share < 1.0 else deadline
        kwargs["first_share"] = 1.0
        return await real(*args, **kwargs)

    monkeypatch.setattr(graph_module, "ask_guard_model", _cut)
    problems = _mutated(monkeypatch, _SMALL_GRID)
    assert any("develop ok, new None" in p or "develop off_topic, new None" in p for p in problems), problems[:5]


def test_a_third_request_is_never_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cap holds against a provider that would answer a third request,
    where develop spent four."""
    provider = _by_index((_Outcome("error", 0.05), _Outcome("error", 0.05), _Outcome("reply", 0.3, "admit")))
    new = _run(monkeypatch, provider, develop=False)
    assert new.requests == 2 and new.verdict is None
    old = _run(monkeypatch, provider, develop=True)
    assert old.requests == 3 and old.verdict == "ok"
