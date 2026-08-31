"""Build phase 6.0's premise gate: one question may not call the world forever.

WHAT THIS GATE IS FOR. Technical specification Section 21.3 bounds the
number of Layer 2 and Layer 3 tool calls a single query may issue at 20,
separately from the dollar cap in Section 19, because NCBI and enrichment
calls are free and a cost cap therefore cannot see them at all. Measured
against the shipped tree on 2026-08-31: that bound does not exist. There is
no constant, no counter and no enforcement anywhere in `src/`. `act_node`
checks `cost_control.check_per_query_cap` immediately before each dispatch
and nothing checks call count, anywhere, at any layer.

THE ARM THAT MATTERS IS A2, and this docstring says so up front because the
obvious fix would pass a weaker gate while leaving the defect. The bound
looks like it belongs in `act_node`'s planned-call loop, next to the cost
check that is already there. It does not. `act_node` iterates PLANNED calls,
of which a real query has one to three, and Section 21.3 names the cases a
21st call actually arrives from: "a retry, a wider-than-expected fan-out, or
an ELink traversal that returns more targets than planned". All three happen
inside a tool, below `act_node`, invisible to a counter that increments once
per planned call. Build phase 5.0 established the same thing for the audit
hook and proved it by execution rather than by reading: five production call
sites reach a data layer without passing through `act_node`, and the first
audit line a live query ever wrote was `think_node`'s symbol resolution,
before Act had run at all.

So A2 drives `ncbi_transport.execute_get` directly, twenty-one times inside
one query scope, and asserts the twenty-first never reaches the client. A
gate that only drove `act_node` would go green on the wrong fix.

EVERY ARM CARRIES A POPULATE-CHECK, per build phases 4.7, 4.11 and 4.15.
Three phases running produced vacuous arms, and in 4.7 the repair for a
vacuous arm was itself vacuous. Every negative or comparative assertion here
first proves the thing it measures was available to be measured: that calls
actually reached the fake client, that a pool was actually saturated, that a
scope was actually exhausted. An arm that cannot distinguish "the control
held" from "nothing happened" is not an arm.

WHAT THIS GATE CANNOT PROVE ABOUT ITSELF, recorded at the moment it was
watched failing rather than left for a reviewer to find:

- HOW THIS GATE WAS WATCHED FAILING, in two stages, because the two say
  different things. Against the tree before any implementation, all eight
  arms went red at `_budget_api()`'s ImportError: `harness/call_budget.py`
  did not exist. That proved the API was absent and nothing more, since
  eight arms failing at one shared line is one failure wearing eight
  costumes, which is the shape F-5.0-16 already cost this repository a
  round. Against the tree with the implementation half-wired, three arms
  then went red INDIVIDUALLY and for three different reasons, which is the
  evidence that they are separate arms: A2 and A3 on a rate ceiling that
  bit before the call ceiling (F-6.0-02, real behaviour, kept), and A6b on
  a saturation depth past both ceilings (a defect in the arm, fixed).
  Five arms have still never been seen red for their own reason, and
  T-6.0-03's mutation harness owes one mutation per arm before any of them
  should be read as proven.
- A6 pins that the wait ceiling VARIES with query class. It does not pin
  the specific numbers, deliberately: `.claude/rules/tool-call-budgets.md`
  requires asking the product owner before locking a queue or budget
  constant, so a gate that asserted "lookup gets 1.5s" would be pinning a
  number nobody has approved. The property is the ordering, not the values.
- Nothing here exercises the FTP transport against a real FTP server. A4
  drives the counting function directly at the layer `pathogen_ftp_transport`
  would call it from, so it proves the ceiling covers a second surface, not
  that the FTP call site was wired correctly. That wiring is A4's known gap
  and T-6.0-03 owns closing it.
- This gate needs no network and no model, so it runs in the ordinary suite
  rather than behind `RUN_PREMISE_GATE=1`. That is a deliberate difference
  from the tool phases' gates: what this phase ships is deterministic
  enforcement, not model-generated output, so the live-ground-truth property
  that makes those gates expensive does not apply here.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from system_03_search_agent.tools import ncbi_transport

# The API this phase must ship. Imported through a helper rather than at
# module scope so a missing module fails each arm at its own populate-check
# line, with the arm's own name in the failure, rather than collapsing the
# whole module into one collection error that names nothing.


def _budget_api() -> Any:
    """Return the `harness.call_budget` module, or fail this arm naming it.

    T-6.0-01 ships it. Until then every arm below fails here, which is the
    gate doing its job: the bound Section 21.3 requires is absent.
    """
    try:
        from system_03_search_agent.harness import call_budget
    except ImportError as exc:  # pragma: no cover - the failing branch today
        pytest.fail(
            "Section 21.3's per-query Layer 2/3 call budget does not exist: "
            "system_03_search_agent.harness.call_budget is not importable "
            f"({exc}). T-6.0-01 ships it."
        )
    return call_budget


class _FakeClient:
    """Same shape as `test_ncbi_transport.py`'s `_FakeClient`.

    A scripted sequence of canned responses and no real network. `calls`
    is what every populate-check below reads: it is the only evidence that
    a request actually left this process, as opposed to being refused
    before it was ever attempted, and those two are exactly what this gate
    has to tell apart.
    """

    def __init__(self, items: list[httpx.Response]) -> None:
        self._items = list(items)
        self.calls: list[dict[str, Any]] = []

    async def get(self, url: str, timeout: float | None = None) -> httpx.Response:
        self.calls.append({"url": url, "timeout": timeout})
        if not self._items:
            return httpx.Response(200, text="{}")
        return self._items.pop(0)


@pytest.fixture(autouse=True)
def _reset_transport_state(monkeypatch: pytest.MonkeyPatch):
    """Isolate each arm from every rate-limit pool the previous arm used.

    `get_rate_limiter` caches one limiter per family for the life of the
    process, deliberately, so pacing is enforced across calls rather than
    reset per call. That is correct in production and would silently couple
    these arms to each other, since A6 saturates a pool on purpose.
    """
    monkeypatch.delenv("NCBI_EUTILS_RPS", raising=False)
    ncbi_transport.reset_rate_limiters_for_tests()
    yield
    ncbi_transport.reset_rate_limiters_for_tests()


async def _noop_sleep(_seconds: float) -> None:
    """Consume a scheduled wait without spending wall-clock time on it.

    Only for arms that never want the clock to move, which today is A6b,
    where a pool must STAY saturated while two ceilings are compared
    against it. Everywhere else use `_FakeClock`, for the reason its own
    docstring gives.
    """
    return


class _FakeClock:
    """A monotonic clock that advances exactly when the limiter sleeps.

    A2 and A3 drive twenty sequential calls through a 3 requests/second
    pool. With `_noop_sleep` the clock never moves, so each call's
    scheduled wait grows by a third of a second while its ceiling stays
    fixed, and the sixth call is refused by the RATE ceiling before the
    CALL ceiling those arms exist to test is ever reached. That is not an
    artifact: it is F-6.0-02, real behaviour, found by A2 failing this way
    and recorded in `tracker/phase_6.0.md` rather than tidied away here.

    Advancing the clock on sleep is what real time does, and it is what
    lets these two arms measure one ceiling at a time. Using a fake clock
    rather than real sleeps keeps the suite fast without changing which
    property is under test.
    """

    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds


# ===========================================================================
# A1: the ceiling exists, and it is the number Section 21.3 states.
# ===========================================================================


def test_a1_the_per_query_call_ceiling_exists_and_is_twenty() -> None:
    """Section 21.3: "at most 20 API calls per query", stated as a number.

    The weakest arm here on purpose. It pins the constant so that every
    other arm can refer to one figure instead of hardcoding 20 five times,
    and so that a later change to the number is a single visible edit rather
    than a diff spread across a test file.
    """
    call_budget = _budget_api()

    limit = getattr(call_budget, "MAX_LAYER_2_3_CALLS_PER_QUERY", None)
    assert limit is not None, (
        "call_budget must expose MAX_LAYER_2_3_CALLS_PER_QUERY, the one place "
        "Section 21.3's figure is written down"
    )
    assert limit == 20, (
        f"Section 21.3 states a 20-call ceiling; the code says {limit}. "
        "Changing this figure is a product-owner decision per "
        "system-design-patterns pattern 4, not a test edit"
    )


# ===========================================================================
# A2: the 21st Layer 2 call in one query never reaches the network.
# ===========================================================================


@pytest.mark.asyncio
async def test_a2_the_twenty_first_layer_2_call_in_one_query_is_refused() -> None:
    """The arm this gate exists for. Counted at the transport, not at Act.

    Drives `execute_get` directly, which is the single chokepoint all eight
    Layer 2 and Layer 3 HTTP tools reach the network through, so this arm
    holds regardless of which tool issued the call or whether `act_node` was
    ever on the stack.
    """
    call_budget = _budget_api()
    limit = call_budget.MAX_LAYER_2_3_CALLS_PER_QUERY

    clock = _FakeClock()
    client = _FakeClient([httpx.Response(200, text="{}") for _ in range(limit + 1)])

    with call_budget.query_budget_scope(query_class="lookup"):
        for _ in range(limit):
            await ncbi_transport.execute_get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                {"db": "pubmed", "term": "BRCA1"},
                family="eutils",
                client=client,
                sleep_fn=clock.sleep,
                time_fn=clock.time,
            )

        # POPULATE-CHECK. Everything below asserts a call did NOT happen,
        # which is satisfied just as well by nothing having happened at all.
        # This line is what separates those two: the first `limit` calls
        # must have genuinely reached the client before the refusal means
        # anything.
        assert len(client.calls) == limit, (
            f"populate-check failed: expected {limit} requests to reach the "
            f"client before the ceiling bites, saw {len(client.calls)}. The "
            "refusal assertion below would be vacuous"
        )

        with pytest.raises(call_budget.CallBudgetExceededError) as excinfo:
            await ncbi_transport.execute_get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                {"db": "pubmed", "term": "BRCA1"},
                family="eutils",
                client=client,
                sleep_fn=clock.sleep,
                time_fn=clock.time,
            )

    assert len(client.calls) == limit, (
        f"the {limit + 1}th call reached the network: the client saw "
        f"{len(client.calls)} requests, not {limit}. Section 21.3 requires "
        "the harness to refuse it, not to issue it and discard the result"
    )

    # `.claude/rules/tool-call-budgets.md`: a budget error is an instruction
    # to the next agent step, not just a failure label. It must say what was
    # exhausted and by how much, or the Act step cannot decide anything with
    # it.
    error = excinfo.value
    assert getattr(error, "limit", None) == limit, (
        "CallBudgetExceededError must carry the limit it enforced"
    )
    assert getattr(error, "calls_made", None) == limit, (
        "CallBudgetExceededError must carry how many calls were already made"
    )


# ===========================================================================
# A3: the ceiling is per query, not per process.
# ===========================================================================


@pytest.mark.asyncio
async def test_a3_a_second_query_gets_its_own_fresh_ceiling() -> None:
    """Section 21.3 bounds "one query", so exhausting it must not bound the next.

    The failure this rules out is a module-level counter that is never
    reset, which would pass A2 perfectly and then refuse every call the
    process makes after the twentieth, for the life of the process.
    """
    call_budget = _budget_api()
    limit = call_budget.MAX_LAYER_2_3_CALLS_PER_QUERY

    clock = _FakeClock()
    client = _FakeClient([])
    first_scope_raised = False

    with call_budget.query_budget_scope(query_class="lookup"):
        for _ in range(limit):
            await ncbi_transport.execute_get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                {"db": "pubmed"},
                family="eutils",
                client=client,
                sleep_fn=clock.sleep,
                time_fn=clock.time,
            )
        try:
            await ncbi_transport.execute_get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                {"db": "pubmed"},
                family="eutils",
                client=client,
                sleep_fn=clock.sleep,
                time_fn=clock.time,
            )
        except call_budget.CallBudgetExceededError:
            first_scope_raised = True

    # POPULATE-CHECK. The second scope succeeding proves nothing unless the
    # first scope actually reached its ceiling: if the ceiling never fired
    # at all, both scopes succeed and this arm is decoration.
    assert first_scope_raised, (
        "populate-check failed: the first query scope never hit its ceiling, "
        "so the second scope succeeding says nothing about scope isolation"
    )

    calls_before_second_scope = len(client.calls)
    with call_budget.query_budget_scope(query_class="lookup"):
        await ncbi_transport.execute_get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {"db": "pubmed"},
            family="eutils",
            client=client,
            sleep_fn=clock.sleep,
            time_fn=clock.time,
        )

    assert len(client.calls) == calls_before_second_scope + 1, (
        "a second query inherited the first query's exhausted budget. The "
        "ceiling is per query (Section 21.3), so it must reset per scope"
    )


# ===========================================================================
# A4: the ceiling spans both Layer 2/3 transports, not only the HTTP one.
# ===========================================================================


def test_a4_the_ceiling_covers_a_second_transport_surface() -> None:
    """The Layer 2/3 surface is two functions, and both must charge the budget.

    `ncbi_transport.execute_get` is the HTTP chokepoint for all eight HTTP
    tools; `pathogen_ftp_transport` is the FTP path for `pathogen_detection`.
    A ceiling wired into only the first is a ceiling one tool walks around.

    This arm drives the charging function directly rather than an FTP
    server, so it proves the budget is chargeable from a second surface. It
    does NOT prove `pathogen_ftp_transport` actually calls it, which is this
    arm's stated gap and T-6.0-03's job to close.
    """
    call_budget = _budget_api()
    limit = call_budget.MAX_LAYER_2_3_CALLS_PER_QUERY

    with call_budget.query_budget_scope(query_class="exploratory"):
        for _ in range(limit):
            call_budget.charge_one_call(tool="pathogen_detection", layer=3)

        # POPULATE-CHECK. `calls_made` must show the charges landed, or the
        # refusal below could be a refusal of nothing.
        assert call_budget.calls_made() == limit, (
            f"populate-check failed: charged {limit} calls, counter reads "
            f"{call_budget.calls_made()}"
        )

        with pytest.raises(call_budget.CallBudgetExceededError):
            call_budget.charge_one_call(tool="pathogen_detection", layer=3)


# ===========================================================================
# A5: work outside a query is not a query, and is not bounded like one.
# ===========================================================================


@pytest.mark.asyncio
async def test_a5_a_call_outside_any_query_scope_is_not_refused() -> None:
    """Section 21.3 bounds a QUERY. A batch job is not one.

    `s3-kgx-export` and any future maintenance script reach a data layer
    without a query scope around them. Refusing their twenty-first call
    would break a shipped delivery surface to enforce a bound that does not
    apply to it. This arm pins that direction of failure deliberately, and
    the coverage note in `tracker/phase_6.0.md` records it as a hole rather
    than pretending it is not one: unscoped work is genuinely unbounded here.
    """
    call_budget = _budget_api()
    limit = call_budget.MAX_LAYER_2_3_CALLS_PER_QUERY

    client = _FakeClient([])
    for _ in range(limit + 1):
        await ncbi_transport.execute_get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {"db": "pubmed"},
            family="eutils",
            client=client,
            sleep_fn=_noop_sleep,
        )

    # POPULATE-CHECK and assertion are the same count here, so state both
    # readings: the calls must have happened (populate), and all of them
    # must have happened (the property).
    assert len(client.calls) == limit + 1, (
        f"{limit + 1} unscoped calls were attempted and {len(client.calls)} "
        "reached the client. Outside a query scope there is no per-query "
        "budget to charge, so none may be refused"
    )
    assert call_budget.calls_made() is None, (
        "calls_made() must report None outside a query scope, so a caller "
        "can tell 'no budget is bound' from 'a budget is bound and empty'"
    )


# ===========================================================================
# A6: how long a call waits for a saturated pool depends on the query class.
# ===========================================================================


@pytest.mark.asyncio
async def test_a6_the_queue_wait_ceiling_varies_with_query_class() -> None:
    """Section 21.4: the wait ceiling reads the caller's own latency budget.

    Quoting the spec: "a lookup-class query (5 second total budget) accepts
    only a short queue wait ... A multi-hop or deep-research query (30 second
    or 2 minute budget) tolerates a longer wait ... The queue reads the
    caller's remaining per-step time budget rather than applying one constant
    across every query class."

    Today `execute_get`'s `wait_ceiling_s` defaults to `timeout_s`, a
    per-call constant, and no caller in `core/graph.py` supplies anything
    else. So every query class currently gets the same ceiling, which is
    precisely the "one constant" the spec rules out.

    This arm pins the ORDERING, not the numbers. Locking a specific figure
    here would pin a queue constant no product owner has approved, which
    `.claude/rules/tool-call-budgets.md` forbids.
    """
    call_budget = _budget_api()

    with call_budget.query_budget_scope(query_class="lookup"):
        lookup_ceiling = call_budget.wait_ceiling_s()
    with call_budget.query_budget_scope(query_class="exploratory"):
        deep_ceiling = call_budget.wait_ceiling_s()

    # POPULATE-CHECK. A comparison of two Nones, or of two values one of
    # which was never computed, would pass or fail for reasons that have
    # nothing to do with query class.
    assert lookup_ceiling is not None and deep_ceiling is not None, (
        "populate-check failed: wait_ceiling_s() returned None inside a "
        f"query scope (lookup={lookup_ceiling}, deep={deep_ceiling}), so the "
        "comparison below would not be measuring query class"
    )
    assert lookup_ceiling > 0 and deep_ceiling > 0, (
        "populate-check failed: a wait ceiling of zero or less refuses every "
        "queued call outright, which would satisfy the ordering below for "
        "the wrong reason"
    )

    assert deep_ceiling > lookup_ceiling, (
        f"deep_research's queue wait ceiling ({deep_ceiling}s) must exceed "
        f"lookup's ({lookup_ceiling}s). Section 21.4 ties the ceiling to the "
        "query's own latency budget rather than one constant per call"
    )


@pytest.mark.asyncio
async def test_a6b_a_saturated_pool_refuses_a_lookup_before_a_deep_research() -> None:
    """The same ordering, observed through the pool rather than read off a function.

    A6 asks the budget what ceiling it would supply. This asks the limiter
    what it actually does with one, against a genuinely saturated pool, so a
    correct `wait_ceiling_s` that nothing ever passes to `acquire` cannot
    pass both arms. That gap, a value computed and never used, is the shape
    build phase 4.15 shipped four times.
    """
    call_budget = _budget_api()

    limiter = ncbi_transport.RateLimiter(
        requests_per_second=1.0, queue_depth=25, family="eutils"
    )
    clock = {"now": 0.0}

    def _time_fn() -> float:
        return clock["now"]

    # Saturate to a depth BETWEEN the two ceilings, which is the only depth
    # that can tell them apart. Three calls at one per second push
    # `_next_available` three seconds ahead while the clock stays put, so
    # the next caller faces a 3.0s wait: past a lookup's ceiling and inside
    # a deep-research one.
    #
    # Saturating deeper is what this arm did first, and it failed for a
    # reason worth keeping: at ten seconds deep BOTH ceilings refuse, the
    # arm goes red, and it looks exactly like a broken implementation. A
    # comparative arm has to be run at a point where the two things being
    # compared can actually differ, or it is measuring the saturation depth
    # rather than the query class.
    for _ in range(3):
        await limiter.acquire(60.0, time_fn=_time_fn, sleep_fn=_noop_sleep)

    with call_budget.query_budget_scope(query_class="lookup"):
        lookup_ceiling = call_budget.wait_ceiling_s()
    with call_budget.query_budget_scope(query_class="exploratory"):
        deep_ceiling = call_budget.wait_ceiling_s()

    # POPULATE-CHECK. The pool must really be saturated: if the wait were
    # zero, both ceilings would be accepted and the arm would prove nothing.
    with pytest.raises(ncbi_transport.TransportRateLimitedError):
        await limiter.acquire(0.0, time_fn=_time_fn, sleep_fn=_noop_sleep)

    lookup_refused = False
    try:
        await limiter.acquire(lookup_ceiling, time_fn=_time_fn, sleep_fn=_noop_sleep)
    except ncbi_transport.TransportRateLimitedError:
        lookup_refused = True

    deep_refused = False
    try:
        await limiter.acquire(deep_ceiling, time_fn=_time_fn, sleep_fn=_noop_sleep)
    except ncbi_transport.TransportRateLimitedError:
        deep_refused = True

    assert lookup_refused and not deep_refused, (
        "against a pool saturated 3 seconds deep, a lookup query "
        f"(ceiling {lookup_ceiling}s, refused={lookup_refused}) must fail "
        f"fast where a deep_research query (ceiling {deep_ceiling}s, "
        f"refused={deep_refused}) waits. Section 21.4"
    )


# ===========================================================================
# A7: F-6.0-01, the comment that claims this ceiling already exists.
# ===========================================================================


def test_a7_the_web_adapter_comment_no_longer_claims_an_absent_cap() -> None:
    """F-6.0-01: `adapters/web_sse/app.py:231` describes a check that is not there.

    The comment justifying `_MAX_CITATIONS_PER_RUN = 50` says a run's
    citation count "is already implicitly bounded by Section 21's
    at-most-20-tool-calls-per-query cap, so this is defense in depth, not the
    primary bound". No such cap existed when that was written. This is the
    fifth instance in this repository of a confident sentence describing a
    check that is not there, and build phase 4.15's conclusion was that such
    a sentence is where the next reader stops looking.

    The repair is ordering rather than deletion: once T-6.0-01 lands the
    sentence becomes true, and this arm is what holds the two together, so
    the comment cannot become true-by-accident or stay false unnoticed.
    """
    call_budget = _budget_api()

    from system_03_search_agent.adapters.web_sse import app as web_app

    per_run_citations = web_app._MAX_CITATIONS_PER_RUN

    # POPULATE-CHECK. The comment's argument is that the citation cap is
    # slack relative to the call ceiling. If the citation cap were the
    # tighter of the two, the sentence would be wrong for a different reason
    # and this arm would be asserting the wrong relationship.
    assert per_run_citations > 0, (
        f"populate-check failed: _MAX_CITATIONS_PER_RUN reads "
        f"{per_run_citations}, so the bound the comment reasons about is not "
        "present to reason about"
    )

    assert call_budget.MAX_LAYER_2_3_CALLS_PER_QUERY == 20, (
        "the comment at adapters/web_sse/app.py names a 20-call cap by that "
        "number. If the ceiling ever moves, the comment moves in the same "
        "edit or it becomes false again"
    )
