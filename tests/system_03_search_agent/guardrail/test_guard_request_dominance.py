"""Step 3d of the guardrail design (cards 84 and 72): the sweep against
develop's own code, which proves the guardrail change loses no question
develop answers, answers none later, never has two requests of one kind in
flight, and never passes the 15 s budget.

## The two yardsticks

Each is a copy of develop's policy at `c916cfa3`, kept here because the
code it copies is replaced on this branch. Each copy was checked case for
case against develop's REAL code, run from an export of `c916cfa3`'s `src`
through the same grid on the same virtual clock (the builder's record,
`testing/Developer/reports/2026-10-08_guardrail_design/build.md`, gives the
counts). `run_case` takes `port=False` to run whatever `src` is imported,
which is how that check runs develop's tree.

- The guard classifier: develop's two attempts in `_guardrail_after_prefilter`
  (R-01's first attempt of two thirds of the budget, R-05's backoff and
  stated `Retry-After`, each attempt one `call_tier` call with its own
  immediate resend), copied line for line as `_develop_classifier`. Step 4
  of the design keeps it unchanged, so the real node must match it in every
  case, rate-limited ones included.
- Jev's relevancy wait: develop's R-06 window (`_JEV_OWN_PICK_WINDOW_S`,
  3.75 s from the decision's start) and its real-time clocks on Jev
  (`asyncio.wait_for`), restored around this branch's code by
  `_develop_jev_clocks`. Step 3b replaces both.

## What it holds

- Every case, the new code: never two classifier requests in flight, never
  two guard picks in flight, never past the budget.
- Every case develop answers (an admission or a refusal): the new code
  answers the same, no later. The one class allowed to differ is step 3b's
  own fix, counted: develop refused a question as off topic because a server
  pause pushed Jev's on-topic pick past develop's clock, and the new code
  reads that pick and admits, as R-03 admits it without a pause.
- The rules every step keeps, case by case: nothing is admitted without the
  guard model's own verdict; Jev never removes a refusal (an injection
  verdict from either judge always refuses).
"""

from __future__ import annotations

import asyncio
import itertools
import json
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

import httpx
import litellm
import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.guardrail import classifier
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import decide as decide_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness import jev_client as jev_client_module
from system_03_search_agent.harness.harness import HarnessCallError
from tests.system_03_search_agent.model_stub import COMPLIANT_GUARD_CLASSIFICATION, fake_response
from tests.system_03_search_agent.virtual_clock import run_virtual

_REPLIES = {
    "admit": COMPLIANT_GUARD_CLASSIFICATION,
    "injection": json.dumps({**json.loads(COMPLIANT_GUARD_CLASSIFICATION), "is_injection": True, "reason": "probe"}),
    "off-topic": json.dumps({**json.loads(COMPLIANT_GUARD_CLASSIFICATION), "is_off_topic": True}),
}
_BRCA1 = "Which diseases are associated with BRCA1?"
_TREE_OF_LIFE = "Tell me about the tree of life."
_PICK_PREFIX = "Answer with exactly one of the offered options"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in _ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("CLASSIFIER_PROVIDER", raising=False)
    _quiet_caps(monkeypatch)


_ENV = {
    "GUARD_MODEL": "test-provider/guard-model",
    "PLAN_MODEL": "test-provider/plan-model",
    "SYNTH_MODEL": "test-provider/synth-model",
    "PER_QUERY_COST_CAP_USD": "1.0",
    "PER_USER_DAILY_QUERY_CAP": "100",
    "SYSTEM_DAILY_CAP_USD": "1000000",
    "USER_DB_URL": "postgresql://localhost:5432/search_agent_users",
    "OPENROUTER_API_KEY": "test-key",
}


def _quiet_caps(monkeypatch: pytest.MonkeyPatch) -> None:
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
    """What one request meets: `kind` is "reply", "unusable", "error",
    "rate_limit", "refused" or "hang"; `verdict` a key of `_REPLIES` (or a
    pick's own option); `after_s` how long it takes; `retry_after_s` a 429's
    stated wait."""

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
    seconds after the case began."""

    name: str
    outcome: Callable[[int, float], _Outcome]


async def _meet(outcome: _Outcome) -> Any:
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


class _GuardStub:
    """`litellm.acompletion` for one case: the classifier's requests meet
    `classify`, a guard pick's meet `pick`; each kind's sends and the most
    in flight at once are counted."""

    def __init__(self, classify: _Provider, pick: _Provider | None, started: float) -> None:
        self.providers = {"classify": classify, "pick": pick}
        self.started = started
        self.sent: dict[str, list[float]] = {"classify": [], "pick": []}
        self.outcomes: dict[str, list[_Outcome]] = {"classify": [], "pick": []}
        self.active: Counter[str] = Counter()
        self.peak: Counter[str] = Counter()

    async def __call__(self, **kwargs: Any) -> Any:
        system = next((m["content"] for m in kwargs["messages"] if m["role"] == "system"), "")
        kind = "pick" if system.startswith(_PICK_PREFIX) else "classify"
        provider = self.providers[kind]
        if provider is None:
            raise AssertionError(f"no {kind} request was expected")
        loop = asyncio.get_running_loop()
        sent_s = loop.time() - self.started
        self.sent[kind].append(sent_s)
        outcome = provider.outcome(len(self.sent[kind]), sent_s)
        self.outcomes[kind].append(outcome)
        self.active[kind] += 1
        self.peak[kind] = max(self.peak[kind], self.active[kind])
        try:
            return await _meet(outcome)
        finally:
            self.active[kind] -= 1


@dataclass(frozen=True)
class _Jev:
    """Jev for one case: each question's answer (`choice`, or "http_500",
    or "hang") after `after_s`, and a blocking pause of the server of
    `stall_s` as the relevancy request is sent."""

    injection: str = "not_injection"
    injection_after_s: float = 0.12
    relevancy: str = "on_topic"
    relevancy_after_s: float = 0.2
    stall_s: float = 0.0


def _jev_post(jev: _Jev) -> Callable[..., Any]:
    async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
        key = next(iter(body["questions"]))
        if key == "guardrail.injection":
            answer, after_s, other = jev.injection, jev.injection_after_s, "injection"
        else:
            answer, after_s, other = jev.relevancy, jev.relevancy_after_s, "off_topic"
            if jev.stall_s:
                asyncio.get_running_loop().stall(jev.stall_s)  # type: ignore[attr-defined]
        if answer == "hang":
            await asyncio.sleep(10_000)
        await asyncio.sleep(after_s)
        if answer == "http_500":
            return httpx.Response(500, content=b"oops")
        other = "not_injection" if answer == "injection" else ("off_topic" if answer == "on_topic" else other)
        if key == "guardrail.relevancy" and answer == "off_topic":
            other = "on_topic"
        return httpx.Response(
            200,
            json={
                "model": "jev-test",
                "answers": {key: {"choice": answer, "confidence": 0.8, "probabilities": {answer: 0.9, other: 0.1}}},
                "usage": {"input_tokens": 1, "output_tokens": 1, "cost": 0.00002},
            },
        )

    return _post


# ---------------------------------------------------------------------------
# Develop's policies at c916cfa3, copied as the yardsticks.
# ---------------------------------------------------------------------------

#: The harness's own methods, held here so a mutation of the harness below
#: reaches only the code under test, never the yardstick.
_CALL_TIER = harness_module.Harness.call_tier
_ENFORCE_TIMEOUT = harness_module.Harness.enforce_timeout

_DEVELOP_FIRST_ATTEMPT_SHARE = 2 / 3
_DEVELOP_BACKOFF_S = 2.0
_DEVELOP_MIN_SECOND_ATTEMPT_S = 3.0
_DEVELOP_JEV_OWN_PICK_WINDOW_S = 3.0 + 0.5 + 0.25


def _develop_retry_wait_s(exc: HarnessCallError, remaining_s: float) -> float | None:
    """Develop's `_classifier_retry_wait_s`, line for line (its two header
    readers, `_rate_limit_behind` and `_provider_retry_after_s`, are this
    branch's unchanged ones)."""
    if exc.source.startswith("harness.enforce_timeout"):
        return 0.0
    rate_limit = graph_module._rate_limit_behind(exc)
    stated = graph_module._provider_retry_after_s(rate_limit) if rate_limit is not None else None
    if stated is not None:
        wait_s = max(stated, _DEVELOP_BACKOFF_S)
        return wait_s if wait_s + _DEVELOP_MIN_SECOND_ATTEMPT_S <= remaining_s else None
    return max(0.0, min(_DEVELOP_BACKOFF_S, remaining_s - _DEVELOP_MIN_SECOND_ATTEMPT_S))


async def _develop_classifier(harness: Any, deadline: float, now: Callable[[], float]) -> str | None:
    """Develop's two attempts in `_guardrail_after_prefilter`, line for line:
    the verdict's category ("ok", "injection", "off_topic"), or None for any
    step error. With Jev saying "not_injection", Jev adds nothing, so this is
    the verdict in both provider modes."""
    messages = classifier.build_messages(_BRCA1)
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


def _install_develop_jev_clocks(patch: pytest.MonkeyPatch) -> None:
    """Develop's R-06 window and real-time Jev clocks, put back around this
    branch's code on `patch`: `asyncio.wait_for` for every Jev bound, the
    relevancy wait ending 3.75 s after the decision began, and no signal
    from `decide()`."""

    async def _wait_for(awaitable: Any, budget_s: float) -> Any:
        return await asyncio.wait_for(awaitable, timeout=budget_s)

    started: list[float] = []

    async def _relevancy_decision(harness: Any, trace_id: str, text: str, jev_failed: Any) -> Any:
        started.append(graph_module.time.monotonic())
        return await graph_module._decide_point(harness, trace_id, graph_module._RELEVANCY, text)

    async def _await_own_pick(task: Any, jev_failed: Any, step_deadline: float, *, point: str, trace_id: str) -> Any:
        deadline = step_deadline
        if graph_module._jev_decides():
            began = started[0] if started else graph_module.time.monotonic()
            deadline = min(step_deadline, began + _DEVELOP_JEV_OWN_PICK_WINDOW_S)
        return await graph_module._await_within_step(task, deadline, None, point=point, trace_id=trace_id)

    for module in (jev_client_module, decide_module, graph_module):
        patch.setattr(module, "wait_counting_free_time", _wait_for)
    patch.setattr(graph_module, "_relevancy_decision", _relevancy_decision)
    patch.setattr(graph_module, "_await_jev_own_pick", _await_own_pick)


# ---------------------------------------------------------------------------
# Running one case.
# ---------------------------------------------------------------------------


@dataclass
class _Run:
    verdict: str | None
    elapsed_s: float
    requests: dict[str, int]
    peak: dict[str, int]
    outcomes: dict[str, list[_Outcome]] = field(default_factory=dict)


def run_case(
    monkeypatch: pytest.MonkeyPatch,
    classify: _Provider,
    *,
    text: str = _BRCA1,
    budget_s: float = 15.0,
    jev: _Jev | None = None,
    pick: _Provider | None = None,
    port: bool = False,
) -> _Run:
    """One case on the virtual clock. `jev` None is the guard provider, the
    code default; otherwise `CLASSIFIER_PROVIDER=jev`, develop's setting.
    `port` runs develop's yardstick instead of this branch's code: the
    classifier copy alone for `_BRCA1`, and for any other question the real
    node under `_install_develop_jev_clocks`."""
    with monkeypatch.context() as patch:

        async def _go() -> _Run:
            loop = asyncio.get_running_loop()
            started = loop.time()
            stub = _GuardStub(classify, pick, started)
            patch.setattr(harness_module.litellm, "acompletion", stub)
            trace_id = f"t-{uuid.uuid4().hex[:8]}"
            harness = harness_module.Harness(trace_id)
            if port and text == _BRCA1:
                verdict = await _develop_classifier(harness, started + budget_s, loop.time)
            else:
                from system_03_search_agent.contracts.query import Query, RequestContext

                state = {
                    "query": Query(text=text, session_id="dominance", trace_id=trace_id),
                    "context": RequestContext(surface="rest_sse"),
                    "harness": harness,
                    "seq": 0,
                    "start_monotonic": started,
                }
                result = await graph_module.guardrail_node(state)  # type: ignore[arg-type]
                guard = next((e.payload for e in result.get("events", []) if e.type == "guard"), None)
                verdict = None if guard is None else guard["category"]
            return _Run(
                verdict,
                loop.time() - started,
                {kind: len(times) for kind, times in stub.sent.items()},
                dict(stub.peak),
                {kind: list(outcomes) for kind, outcomes in stub.outcomes.items()},
            )

        if jev is not None:
            patch.setenv("CLASSIFIER_PROVIDER", "jev")
            patch.setattr(jev_client_module, "_post", _jev_post(jev))
        patch.setattr(graph_module, "_step_deadline", lambda *_a, **_k: graph_module.time.monotonic() + budget_s)
        if port and text != _BRCA1:
            _install_develop_jev_clocks(patch)
        return run_virtual(patch, _go)


# ---------------------------------------------------------------------------
# The grids.
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
    slow off-topic against a fast admission, an error spell then an answer."""
    return _Provider(
        f"sent before {switch_s:g}s: {before.label()}, after: {after.label()}",
        lambda _index, t: before if t < switch_s else after,
    )


def _classifier_grid() -> list[_Provider]:
    """Every ordered triple of 17 behaviours (develop may send up to four
    requests; the fourth repeats the third), and providers whose answer
    changes with the time a request is sent."""
    behaviours = _classifier_behaviours()
    grid = [_by_index(triple) for triple in itertools.product(behaviours, repeat=3)]
    firsts = [b for b in behaviours if b.kind != "refused"]
    thens = [_Outcome("reply", 0.6, v) for v in ("admit", "injection", "off-topic")]
    for before, after, switch_s in itertools.product(firsts, thens, (0.5, 1.0, 2.5, 9.5, 11.0)):
        grid.append(_by_time(before, after, switch_s))
    return grid


@dataclass(frozen=True)
class _RelevancyCase:
    classify: _Outcome
    jev: _Jev
    pick: _Outcome

    def label(self) -> str:
        j = self.jev
        return (
            f"classifier {self.classify.label()}, Jev injection {j.injection}, Jev relevancy "
            f"{j.relevancy}@{j.relevancy_after_s:g} after a {j.stall_s:g}s pause, guard pick {self.pick.label()}"
        )


def _relevancy_grid() -> list[_RelevancyCase]:
    """A question the allowlist misses, with Jev on: the classifier's
    verdict, Jev's two picks, the guard tier's fallback pick and a server
    pause as Jev's relevancy request is sent, every combination."""
    classifies = [
        _Outcome("reply", 0.3, "admit"),
        _Outcome("reply", 0.3, "off-topic"),
        _Outcome("reply", 0.3, "injection"),
        _Outcome("reply", 6.0, "off-topic"),
        _Outcome("reply", 6.0, "admit"),
        _Outcome("hang"),
    ]
    relevancies = [("on_topic", 0.2), ("on_topic", 2.5), ("off_topic", 0.2), ("off_topic", 2.5), ("http_500", 0.1), ("hang", 0.0)]
    picks = [
        _Outcome("reply", 0.3, "on_topic"),
        _Outcome("reply", 0.3, "off_topic"),
        _Outcome("reply", 6.0, "off_topic"),
        _Outcome("hang"),
    ]
    cases = []
    for classify, injection, (relevancy, after_s), pick, stall_s in itertools.product(
        classifies, ("not_injection", "injection", "http_500"), relevancies, picks, (0.0, 0.6, 1.0)
    ):
        jev = _Jev(injection=injection, relevancy=relevancy, relevancy_after_s=after_s, stall_s=stall_s)
        cases.append(_RelevancyCase(classify, jev, pick))
    return cases


# ---------------------------------------------------------------------------
# The sweeps.
# ---------------------------------------------------------------------------


@dataclass
class _Sweep:
    cases: int = 0
    develop_answered: int = 0
    held: int = 0
    problems: list[str] = field(default_factory=list)
    classes: Counter[str] = field(default_factory=Counter)


def _check_new(sweep: _Sweep, where: str, new: _Run, budget_s: float) -> None:
    """What every case of the new code must hold, whatever develop did."""
    for kind, peak in new.peak.items():
        if peak > 1:
            sweep.problems.append(f"{where}: {peak} {kind} requests in flight at once")
    if new.elapsed_s > budget_s + 1e-6:
        sweep.problems.append(f"{where}: ended at {new.elapsed_s:.2f}s, past the {budget_s:g}s budget")


def _compare(sweep: _Sweep, where: str, old: _Run, new: _Run, *, same_requests: bool) -> bool:
    """Develop answered: the same verdict, no later. False when it differs."""
    if new.verdict != old.verdict:
        return False
    if new.elapsed_s > old.elapsed_s + 1e-6:
        sweep.problems.append(f"{where}: develop {old.elapsed_s:.2f}s, new {new.elapsed_s:.2f}s")
    elif same_requests and new.requests != old.requests:
        sweep.problems.append(f"{where}: develop {old.requests} requests, new {new.requests}")
    else:
        sweep.held += 1
    return True


def classifier_sweep(
    monkeypatch: pytest.MonkeyPatch, grid: list[_Provider], *, jev: _Jev | None, budgets: tuple[float, ...] = (15.0, 12.0)
) -> _Sweep:
    """Develop's classifier policy against the real node over `grid`. Step 4
    keeps the policy, so every case must match, verdict, moment and
    requests, rate limits included."""
    sweep = _Sweep()
    for provider, budget_s in itertools.product(grid, budgets):
        sweep.cases += 1
        old = run_case(monkeypatch, provider, budget_s=budget_s, port=True)
        new = run_case(monkeypatch, provider, budget_s=budget_s, jev=jev)
        where = f"{provider.name}, budget {budget_s:g}s"
        _check_new(sweep, where, new, budget_s)
        if old.verdict is not None:
            sweep.develop_answered += 1
        if new.verdict != old.verdict:
            sweep.problems.append(f"{where}: develop {old.verdict}, new {new.verdict}")
        elif old.verdict is not None:
            _compare(sweep, where, old, new, same_requests=True)
    return sweep


#: The classes of a paused case allowed to differ from develop, each the
#: consequence of step 3b reading Jev's own pick after a server pause where
#: develop's real-time clock gave up on it.
_PAUSE_VERDICT = "a pause: Jev's own pick now read, the verdict the same case gets with no pause"
_PAUSE_LATER = "a pause: the same verdict, later than develop by no more than the pause"
_FA03 = "of those, develop refused off topic and Jev's own on-topic pick now admits (FA03)"
_INJECTION_SOONER = (
    "Jev called it injection and made no relevancy pick: refused as injection when Jev fails, "
    "not off topic after the guard fallback (the category R-06 named)"
)


def relevancy_sweep(monkeypatch: pytest.MonkeyPatch, grid: list[_RelevancyCase]) -> _Sweep:
    """Develop's R-06 window and real-time Jev clocks against step 3b's
    signal and free-time clocks, over `grid`, with the rules every step
    keeps checked on each new result.

    With no pause, every case develop answers is answered the same, no
    later, but one class: a question Jev called injection whose relevancy
    pick Jev failed is refused as injection the moment Jev fails, where
    develop waited for the guard fallback and refused it as off topic; a
    refusal either way, never later. With a pause, step 3b reads a Jev pick develop's clock gave up
    on, so a case may differ from develop, but only toward what the same
    case gets with no pause: the same verdict as the no-pause run, and no
    later than develop by more than the pause itself. Those are counted."""
    sweep = _Sweep()
    for case in grid:
        sweep.cases += 1
        classify = _Provider(case.classify.label(), lambda _i, _t, o=case.classify: o)
        pick = _Provider(case.pick.label(), lambda _i, _t, o=case.pick: o)
        old = run_case(monkeypatch, classify, text=_TREE_OF_LIFE, jev=case.jev, pick=pick, port=True)
        new = run_case(monkeypatch, classify, text=_TREE_OF_LIFE, jev=case.jev, pick=pick)
        where = case.label()
        _check_new(sweep, where, new, 15.0)
        _check_the_rules(sweep, where, case, new)
        if old.verdict is None:
            if new.verdict is not None:
                sweep.problems.append(f"{where}: develop gave no answer, new {new.verdict}")
            continue
        sweep.develop_answered += 1
        pause_s = case.jev.stall_s
        if pause_s == 0:
            if _compare(sweep, where, old, new, same_requests=False):
                continue
            injection_sooner = (
                old.verdict == "off_topic"
                and new.verdict == "injection"
                and case.jev.injection == "injection"
                and case.jev.relevancy in ("http_500", "hang")
                and new.elapsed_s <= old.elapsed_s + 1e-6
            )
            if injection_sooner:
                sweep.classes[_INJECTION_SOONER] += 1
            else:
                sweep.problems.append(f"{where}: develop {old.verdict}, new {new.verdict}")
            continue
        calm = run_case(
            monkeypatch, classify, text=_TREE_OF_LIFE, jev=replace(case.jev, stall_s=0.0), pick=pick
        )
        if new.verdict != calm.verdict:
            sweep.problems.append(f"{where}: {new.verdict} after the pause, {calm.verdict} with none")
        elif new.elapsed_s > old.elapsed_s + pause_s + 1e-6:
            sweep.problems.append(
                f"{where}: develop {old.elapsed_s:.2f}s, new {new.elapsed_s:.2f}s, more than the {pause_s:g}s pause later"
            )
        elif new.verdict != old.verdict:
            sweep.classes[_PAUSE_VERDICT] += 1
            if old.verdict == "off_topic" and new.verdict == "ok":
                sweep.classes[_FA03] += 1
        elif new.elapsed_s > old.elapsed_s + 1e-6:
            sweep.classes[_PAUSE_LATER] += 1
        else:
            sweep.held += 1
    return sweep


def _check_the_rules(sweep: _Sweep, where: str, case: _RelevancyCase, new: _Run) -> None:
    """The rules every step keeps, on this case's new result."""
    if new.verdict == "ok":
        if case.classify.kind != "reply":
            sweep.problems.append(f"{where}: admitted without the guard model's verdict")
        if case.classify.verdict == "injection" or case.jev.injection == "injection":
            sweep.problems.append(f"{where}: admitted although a judge said injection")
        if case.classify.verdict == "off-topic" and case.jev.relevancy != "on_topic":
            sweep.problems.append(f"{where}: an off-topic verdict set aside without Jev's own on-topic pick")


# The sweeps run once per module and are read by the tests below.
_RESULTS: dict[str, _Sweep] = {}


def _cached(name: str, run: Callable[[], _Sweep]) -> _Sweep:
    if name not in _RESULTS:
        _RESULTS[name] = run()
    return _RESULTS[name]


def test_the_yardstick_is_develops_policy_on_named_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shapes whose answer develop's own tests pin: a hang then an answer
    (R-01), an error lasting about a second (R-05's blip), a 429 naming a
    wait that does not fit, and two unusable replies."""
    hang_then_admit = _by_index((_Outcome("hang"), _Outcome("reply", 0.3, "admit")))
    run = run_case(monkeypatch, hang_then_admit, port=True)
    assert (run.verdict, run.requests["classify"]) == ("ok", 2)
    assert run.elapsed_s == pytest.approx(10.3)
    blip = _by_time(_Outcome("error", 0.05), _Outcome("reply", 0.6, "admit"), 1.0)
    run = run_case(monkeypatch, blip, port=True)
    assert (run.verdict, run.requests["classify"]) == ("ok", 3)
    too_long = _by_index((_Outcome("rate_limit", 0.05, retry_after_s=13.0),))
    run = run_case(monkeypatch, too_long, port=True)
    assert (run.verdict, run.requests["classify"]) == (None, 2)
    unusable = _by_index((_Outcome("unusable", 0.3),))
    assert run_case(monkeypatch, unusable, port=True).verdict is None


def test_the_classifier_matches_develop_case_for_case_with_the_guard_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The code default. Every case: the same verdict at the same moment
    with the same requests as develop's policy, never two in flight, never
    past the budget. The grid's size is pinned, so a grid that shrank would
    show here."""
    sweep = _cached("classifier, guard", lambda: classifier_sweep(monkeypatch, _classifier_grid(), jev=None))
    assert sweep.problems == [], "\n".join(sweep.problems[:20])
    assert sweep.cases == len(_classifier_grid()) * 2 >= 10_000
    assert sweep.held == sweep.develop_answered > 0


def test_the_classifier_matches_develop_case_for_case_with_jev_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Develop's deployed setting: Jev answers the injection question
    "not_injection" in 0.12 s beside the classifier, through the changed
    Jev clock, and adds nothing."""
    sweep = _cached("classifier, jev", lambda: classifier_sweep(monkeypatch, _classifier_grid(), jev=_Jev()))
    assert sweep.problems == [], "\n".join(sweep.problems[:20])
    assert sweep.cases == len(_classifier_grid()) * 2
    assert sweep.held == sweep.develop_answered > 0


def test_the_relevancy_wait_loses_nothing_develop_answers_and_answers_nothing_later(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step 3b against develop's R-06 window, every combination of the
    classifier, Jev's two picks, the guard fallback and a server pause.
    With no pause, nothing differs from develop. With a pause, a case
    differs only toward its own no-pause verdict, no later than develop by
    more than the pause; FA03's admission is among them, as it must be."""
    sweep = _cached("relevancy", lambda: relevancy_sweep(monkeypatch, _relevancy_grid()))
    assert sweep.problems == [], "\n".join(sweep.problems[:20])
    assert sweep.cases == len(_relevancy_grid()) >= 1_000
    assert set(sweep.classes) == {_PAUSE_VERDICT, _PAUSE_LATER, _FA03, _INJECTION_SOONER}
    counted = sweep.classes[_PAUSE_VERDICT] + sweep.classes[_PAUSE_LATER] + sweep.classes[_INJECTION_SOONER]
    assert sweep.held + counted == sweep.develop_answered


def test_the_sweep_reports_its_counts(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """The counts, printed for the builder's record (`pytest -s`)."""
    for name, run in (
        ("classifier, guard", lambda: classifier_sweep(monkeypatch, _classifier_grid(), jev=None)),
        ("classifier, jev", lambda: classifier_sweep(monkeypatch, _classifier_grid(), jev=_Jev())),
        ("relevancy", lambda: relevancy_sweep(monkeypatch, _relevancy_grid())),
    ):
        sweep = _cached(name, run)
        with capsys.disabled():
            print(
                f"\n{name} sweep: {sweep.cases} cases, develop answered {sweep.develop_answered}, "
                f"held {sweep.held}, problems {len(sweep.problems)}"
            )
            for key, count in sorted(sweep.classes.items()):
                print(f"  {key}: {count}")


# ---------------------------------------------------------------------------
# The sweep is not vacuous: each shape it exists to catch turns it red.
# ---------------------------------------------------------------------------

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
    running, the first usable reply deciding. The sweep says so, on the
    requests in flight and on a verdict develop reached differently."""
    real = graph_module._dispatch_tier_call

    async def _hedged(*args: Any, **kwargs: Any) -> Any:
        first = asyncio.ensure_future(real(*args, **kwargs))
        await asyncio.wait({first}, timeout=4.0)
        if first.done():
            return first.result()
        second = asyncio.ensure_future(real(*args, **kwargs))
        done, _ = await asyncio.wait({first, second}, return_when=asyncio.FIRST_COMPLETED)
        winner = done.pop()
        for task in (first, second):
            if task is not winner:
                task.cancel()
        return winner.result()

    monkeypatch.setattr(graph_module, "_dispatch_tier_call", _hedged)
    problems = classifier_sweep(monkeypatch, _SMALL_GRID, jev=None, budgets=(15.0,)).problems
    assert any("in flight at once" in p for p in problems), problems[:5]
    assert any("develop off_topic, new ok" in p for p in problems), problems[:5]


def test_the_sweep_catches_a_backoff_after_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """F-72-V06's shape: a request held back two seconds after an error
    makes an isolated failure slower than develop, and the sweep says so, on
    the time."""

    async def _backoff_call_tier(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return await _CALL_TIER(self, *args, **kwargs)
        except HarnessCallError:
            await asyncio.sleep(2.0)
            raise

    monkeypatch.setattr(harness_module.Harness, "call_tier", _backoff_call_tier)
    problems = classifier_sweep(monkeypatch, _SMALL_GRID, jev=None, budgets=(15.0,)).problems
    assert any("develop" in p and "new" in p and "s, new" in p for p in problems), problems[:5]


def test_the_sweep_catches_a_relevancy_wait_held_for_the_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """RJ03's shape: the relevancy wait ignoring Jev's failure and waiting
    for the guard fallback answers a refusal later than develop's window."""

    async def _whole_wait(task: Any, jev_failed: Any, step_deadline: float, *, point: str, trace_id: str) -> Any:
        return await graph_module._await_within_step(task, step_deadline, None, point=point, trace_id=trace_id)

    monkeypatch.setattr(graph_module, "_await_jev_own_pick", _whole_wait)
    grid = [
        _RelevancyCase(_Outcome("reply", 0.3, "off-topic"), _Jev(relevancy="http_500", relevancy_after_s=0.1), pick)
        for pick in (_Outcome("reply", 6.0, "off_topic"), _Outcome("reply", 0.3, "on_topic"))
    ]
    problems = relevancy_sweep(monkeypatch, grid).problems
    assert any("develop" in p and "s, new" in p for p in problems), problems[:5]


def test_the_sweep_catches_jev_removing_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rule Jev never breaks: a guardrail that let Jev's "not_injection"
    replace the classifier's injection verdict is caught on the rule check."""
    real_parse = graph_module.classifier.verdict_for

    def _jev_overrides(classification: Any) -> Any:
        verdict = real_parse(classification)
        return real_parse(classification.model_copy(update={"is_injection": False})) if verdict.category == "injection" else verdict

    monkeypatch.setattr(graph_module.classifier, "verdict_for", _jev_overrides)
    grid = [_RelevancyCase(_Outcome("reply", 0.3, "injection"), _Jev(relevancy="on_topic"), _Outcome("reply", 0.3, "on_topic"))]
    problems = relevancy_sweep(monkeypatch, grid).problems
    assert any("a judge said injection" in p for p in problems), problems[:5]
