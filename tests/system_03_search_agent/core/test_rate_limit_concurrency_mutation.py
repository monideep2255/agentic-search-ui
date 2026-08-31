"""T-6.0-03: prove build phase 6.0's premise-gate arms can actually fail.

WHY THIS FILE EXISTS. `test_rate_limit_concurrency_premise.py`'s own
docstring records that eight of its arms first went red at a single shared
ImportError line, which is one failure wearing eight costumes rather than
eight arms, and that only three of the eight have since been seen red for
their own distinct reason. An arm nobody has watched fail has proven
nothing about its own ability to fail. This file closes that gap by
mutating the shipped implementation, one property at a time, and asserting
the arm that owns that property goes red.

THE RULE THIS FILE FOLLOWS, from build phase 4.15: add the mutation case in
the same edit as the arm. That phase found a mutation harness claiming to
cover every arm TWICE, the second claim written inside the fix for the
first and naming an uncovered arm as covered, and the durable repair was to
delete the completeness claim rather than to write a more careful one. So
there is no "every arm is covered" sentence anywhere in this file. What
there is instead is `test_zz_every_premise_arm_has_a_mutation`, which
COMPUTES the correspondence from an explicit `_drives` marker on each
mutation. A computed check goes stale loudly; a sentence does not.

THE FIRST VERSION OF THAT COMPUTED CHECK WAS ITSELF VACUOUS, and it is
recorded here rather than quietly fixed, because it is the fourth instance
of this shape in this repository and the second inside build phase 6.0.
It imported the eight arms by name into this module's namespace and then
compared `dir(premise)` against `globals()` by substring. Every arm was
therefore present in BOTH sets and matched itself, so the check would have
reported full coverage for an arm with no mutation at all. It also made
pytest re-collect and re-run all eight arms here, which is why the run
reported 20 tests when this file defines 12. Both symptoms had one cause:
importing the functions instead of the module. Filed as F-6.0-03.

MUTATIONS RUN IN-PROCESS VIA MONKEYPATCH, never by editing the tree.
LEARNINGS.md, 2026-08-27: a mutation harness that mutates the shared
working tree means the repository genuinely contains the defect for the
length of the run, and any concurrent reader is entitled to report it as
real. One reviewer did exactly that. `monkeypatch` confines every mutation
below to this process and unwinds it per test.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

import pytest

from system_03_search_agent.harness import call_budget
from system_03_search_agent.tools import ncbi_transport

from . import test_rate_limit_concurrency_premise as premise


@pytest.fixture(autouse=True)
def _reset_transport_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("NCBI_EUTILS_RPS", raising=False)
    ncbi_transport.reset_rate_limiters_for_tests()
    yield
    ncbi_transport.reset_rate_limiters_for_tests()


def drives(arm_name: str) -> Callable[[Callable], Callable]:
    """Record which premise arm a mutation is responsible for driving red.

    The marker the correspondence check below reads. Declared per mutation
    rather than inferred from the function's name, because inferring it
    from a name is what made the first version of that check match arms
    against themselves.
    """

    def _decorate(fn: Callable) -> Callable:
        fn._drives = arm_name  # type: ignore[attr-defined]
        return fn

    return _decorate


async def _assert_arm_fails(arm_name: str) -> None:
    """Require the named premise arm to fail under the mutation in force.

    Looks the arm up on the premise MODULE rather than taking a function
    imported into this namespace, so pytest never re-collects the arms here
    and this module's namespace stays free of them.

    Catches `BaseException` rather than `AssertionError`: an arm may
    legitimately go red by raising the typed error it was asserting about,
    and requiring one exception class would make this harness pass or fail
    on the shape of the failure rather than on whether there was one.
    """
    arm = getattr(premise, arm_name)
    try:
        result = arm()
        if asyncio.iscoroutine(result):
            await result
    except BaseException:  # noqa: BLE001 - any failure is the point
        return
    pytest.fail(
        f"{arm_name} PASSED under a mutation that breaks the property it "
        "claims to check. The arm is vacuous: it cannot distinguish the "
        "control holding from nothing having happened"
    )


# ===========================================================================
# One mutation per arm.
# ===========================================================================


@drives("test_a1_the_per_query_call_ceiling_exists_and_is_twenty")
@pytest.mark.asyncio
async def test_a1_mutation_ceiling_is_not_twenty(monkeypatch: pytest.MonkeyPatch) -> None:
    """A1 reads the constant. Move it and A1 must notice."""
    monkeypatch.setattr(call_budget, "MAX_LAYER_2_3_CALLS_PER_QUERY", 19)
    await _assert_arm_fails("test_a1_the_per_query_call_ceiling_exists_and_is_twenty")


@drives("test_a2_the_twenty_first_layer_2_call_in_one_query_is_refused")
@pytest.mark.asyncio
async def test_a2_mutation_transport_charges_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mutation that matters: the ceiling exists but nothing charges it.

    This is the failure mode the whole design argument is about. A counter
    wired only into `act_node` would leave `execute_get` exactly like this,
    charging nothing, and A2 is the only arm that would notice.
    """
    monkeypatch.setattr(call_budget, "charge_one_call", lambda **_kwargs: None)
    await _assert_arm_fails("test_a2_the_twenty_first_layer_2_call_in_one_query_is_refused")


@drives("test_a3_a_second_query_gets_its_own_fresh_ceiling")
@pytest.mark.asyncio
async def test_a3_mutation_budget_is_process_wide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A3 owns per-query isolation, so a shared counter must make it red.

    Mutates the scope into one reusing a single budget for every query,
    which is precisely the module-level-counter design `call_budget`'s own
    docstring rejects.
    """
    from contextlib import contextmanager

    shared: dict[str, object] = {}

    @contextmanager
    def _leaky_scope(query_class: str):
        if "budget" not in shared:
            shared["budget"] = call_budget._QueryBudget(query_class=query_class)
        handle = call_budget._budget_var.set(shared["budget"])  # type: ignore[arg-type]
        try:
            yield
        finally:
            call_budget._budget_var.reset(handle)

    monkeypatch.setattr(call_budget, "query_budget_scope", _leaky_scope)
    await _assert_arm_fails("test_a3_a_second_query_gets_its_own_fresh_ceiling")


@drives("test_a4_the_ceiling_covers_a_second_transport_surface")
@pytest.mark.asyncio
async def test_a4_mutation_charging_never_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A4 owns the second transport surface reaching the same budget."""
    monkeypatch.setattr(call_budget, "charge_one_call", lambda **_kwargs: None)
    await _assert_arm_fails("test_a4_the_ceiling_covers_a_second_transport_surface")


@drives("test_a5_a_call_outside_any_query_scope_is_not_refused")
@pytest.mark.asyncio
async def test_a5_mutation_unscoped_work_is_bounded_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A5 owns the direction of failure for work that is not a query.

    Mutates `charge_one_call` into one bounding every caller, scope or no
    scope, which is the over-eager implementation that would break
    `s3-kgx-export` while looking stricter and therefore safer.
    """
    counter = {"n": 0}

    def _bounds_everything(*, tool: str, layer: int) -> None:
        counter["n"] += 1
        if counter["n"] > call_budget.MAX_LAYER_2_3_CALLS_PER_QUERY:
            raise call_budget.CallBudgetExceededError(
                tool=tool,
                calls_made=counter["n"] - 1,
                limit=call_budget.MAX_LAYER_2_3_CALLS_PER_QUERY,
            )

    monkeypatch.setattr(call_budget, "charge_one_call", _bounds_everything)
    await _assert_arm_fails("test_a5_a_call_outside_any_query_scope_is_not_refused")


@drives("test_a6_the_queue_wait_ceiling_varies_with_query_class")
@pytest.mark.asyncio
async def test_a6_mutation_ceiling_ignores_query_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A6 owns the ordering. A constant ceiling is the pre-6.0 behaviour."""
    monkeypatch.setattr(call_budget, "wait_ceiling_s", lambda: 1.5)
    await _assert_arm_fails("test_a6_the_queue_wait_ceiling_varies_with_query_class")


@drives("test_a6b_a_saturated_pool_refuses_a_lookup_before_a_deep_research")
@pytest.mark.asyncio
async def test_a6b_mutation_ceiling_ignores_query_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A6b owns the same ordering, observed through the pool itself.

    A6 and A6b are driven red by the same mutation here, and that is worth
    stating rather than hiding: on this mutation alone A6b is a duplicate of
    A6. What makes it more than one is the NEXT mutation, where the ceiling
    is computed correctly and never passed to `acquire`, which no mutation
    of `wait_ceiling_s` can produce and which A6 cannot see.
    """
    monkeypatch.setattr(call_budget, "wait_ceiling_s", lambda: 1.5)
    await _assert_arm_fails(
        "test_a6b_a_saturated_pool_refuses_a_lookup_before_a_deep_research"
    )


@drives("test_a6b_a_saturated_pool_refuses_a_lookup_before_a_deep_research")
@pytest.mark.asyncio
async def test_a6b_mutation_transport_ignores_the_query_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The value-computed-but-never-used mutation, build phase 4.15's shape.

    `wait_ceiling_s` keeps returning the right number; the limiter stops
    honouring it. An arm that only asked the budget what it would supply
    stays green here, which is exactly why A6b drives the pool.
    """
    original = ncbi_transport.RateLimiter.acquire

    async def _ignores_the_ceiling(self, wait_ceiling_s, **kwargs):  # type: ignore[no-untyped-def]
        return await original(self, 3600.0, **kwargs)

    monkeypatch.setattr(ncbi_transport.RateLimiter, "acquire", _ignores_the_ceiling)
    await _assert_arm_fails(
        "test_a6b_a_saturated_pool_refuses_a_lookup_before_a_deep_research"
    )


@drives("test_a7_the_web_adapter_comment_no_longer_claims_an_absent_cap")
@pytest.mark.asyncio
async def test_a7_mutation_the_named_cap_moves(monkeypatch: pytest.MonkeyPatch) -> None:
    """A7 pins F-6.0-01: the comment names 20, so 20 is what must be there."""
    monkeypatch.setattr(call_budget, "MAX_LAYER_2_3_CALLS_PER_QUERY", 25)
    await _assert_arm_fails("test_a7_the_web_adapter_comment_no_longer_claims_an_absent_cap")


# ===========================================================================
# Section 21.2, measured rather than read off the shape of the registry.
# ===========================================================================


@pytest.mark.asyncio
async def test_one_familys_pool_is_shared_across_concurrent_queries() -> None:
    """Section 21.2: ten concurrent users draw on ONE budget, not ten.

    `tracker/phase_6.0.md` recorded 21.2 as BUILT on the strength of
    `get_rate_limiter` being a process-wide registry. That is a fact about
    the shape of a dict, not about behaviour under concurrency, and this
    repository has been wrong in exactly that direction before: build phase
    4.15 shipped an arm proving two apps held different signing keys that
    only ever re-proved their databases differed.

    So this measures. Twelve calls are issued from twelve CONCURRENT tasks,
    each inside its own query budget scope, against a family paced at 4
    requests per second. A shared pool schedules the last about 11/4
    seconds after the first. Private pools would schedule all twelve at
    once and the span would be near zero.
    """
    limiter = ncbi_transport.RateLimiter(
        requests_per_second=4.0, queue_depth=25, family="eutils"
    )
    acquired_at: list[float] = []
    started = time.monotonic()

    async def _one_users_call() -> None:
        with call_budget.query_budget_scope("lookup"):
            await limiter.acquire(30.0)
            acquired_at.append(time.monotonic() - started)

    await asyncio.gather(*[_one_users_call() for _ in range(12)])

    # POPULATE-CHECK. A span assertion over an empty or short list would
    # pass for reasons that have nothing to do with sharing.
    assert len(acquired_at) == 12, (
        f"populate-check failed: {len(acquired_at)} of 12 concurrent calls "
        "were scheduled, so the span below is not measuring 12 callers"
    )

    span = max(acquired_at) - min(acquired_at)
    # Twelve calls at 4 per second span 11 intervals, 2.75 seconds. Asserted
    # loosely at half that, since this is real wall-clock time on a shared
    # machine and the property under test is "they queued behind each
    # other", not the exact pacing arithmetic the limiter's own unit tests
    # already cover.
    assert span > 1.3, (
        f"twelve concurrent calls against one 4 requests/second family were "
        f"scheduled within {span:.2f}s of each other. Section 21.2 requires "
        "one shared token bucket per family across every concurrent query, "
        "so they must queue behind one another rather than each getting a "
        "private pool"
    )


@pytest.mark.asyncio
async def test_concurrent_queries_each_keep_their_own_call_budget() -> None:
    """The other half of 21.2: the POOL is shared, the BUDGET is not.

    These two are easy to conflate and they are opposites. Section 21.2 says
    the rate limit belongs to the API and is shared process-wide. Section
    21.3 says the call ceiling belongs to one query. A design sharing both
    would let one heavy query exhaust every concurrent user's ceiling.

    This also exercises the ContextVar decision directly: the budget is a
    mutable object shared BY REFERENCE within a scope and invisible across
    scopes, and only a concurrent test can tell those two apart.
    """
    observed: list[int | None] = []

    async def _one_query(calls: int) -> None:
        with call_budget.query_budget_scope("lookup"):
            for _ in range(calls):
                call_budget.charge_one_call(tool="probe", layer=2)
                await asyncio.sleep(0)
            observed.append(call_budget.calls_made())

    await asyncio.gather(_one_query(3), _one_query(7), _one_query(5))

    # POPULATE-CHECK: all three queries must have reported.
    assert len(observed) == 3, (
        f"populate-check failed: {len(observed)} of 3 concurrent queries "
        "reported a count"
    )
    assert sorted(x for x in observed if x is not None) == [3, 5, 7], (
        f"each concurrent query must count only its own calls; observed "
        f"{sorted(x for x in observed if x is not None)} instead of [3, 5, 7]. "
        "A shared counter would show 15 somewhere"
    )


# ===========================================================================
# The correspondence check, computed rather than claimed.
# ===========================================================================


def test_zz_every_premise_arm_has_a_mutation() -> None:
    """Every arm in the premise module is driven red by a mutation here.

    Computed from the `_drives` markers rather than asserted in prose,
    because build phase 4.15 found the prose version wrong twice in one
    phase, the second time inside the fix for the first.

    Read the module docstring's F-6.0-03 note before changing this: the
    first version of this check compared two name sets that both contained
    the arms, so every arm matched itself and the check would have reported
    full coverage for an arm with no mutation at all.
    """
    arms = {name for name in dir(premise) if name.startswith("test_a")}
    mutated = {
        fn._drives for fn in globals().values() if callable(fn) and hasattr(fn, "_drives")
    }

    # POPULATE-CHECK. Either set coming back empty would make the comparison
    # pass or fail for an import reason rather than a coverage one, and an
    # empty `mutated` is the exact state this check exists to catch.
    assert arms, "populate-check failed: found no arms in the premise module"
    assert mutated, "populate-check failed: found no _drives markers in this module"

    # The two sets are built from different places by construction: `arms`
    # from the premise module's namespace, `mutated` from markers written by
    # hand here. Nothing an arm does can put its own name into `mutated`.
    unknown = sorted(mutated - arms)
    assert not unknown, (
        f"these mutations name a premise arm that does not exist: {unknown}. "
        "A marker naming nothing is worse than no marker, since it counts "
        "toward coverage while testing nothing"
    )

    uncovered = sorted(arms - mutated)
    assert not uncovered, (
        f"these premise arms have no mutation driving them red: {uncovered}. "
        "Add the mutation case in the same edit as the arm (build phase 4.15)"
    )
