"""Section 21.3's per-query Layer 2 and Layer 3 call ceiling, and 21.4's wait ceiling.

Depends on:
    - system_03_search_agent.harness.harness (`budget_for_query_class` and
      `QueryClass`), so the wait ceiling is DERIVED from the already-approved
      latency budget rather than being a second table of numbers that can
      drift from the first. Imported LAZILY, inside `wait_ceiling_s`, and
      that is load-bearing rather than untidy: the two Layer 2/3 transports
      import this module, `harness.harness` imports `litellm`, and a
      module-scope import here would put the whole model stack on the
      import path of every tool that makes an HTTP call. See the note above
      that function.

Reads:
    - Nothing from the environment. Both figures here are derived, one from
      the specification and one from the harness's own budget table.

Writes:
    - Nothing. This module counts; it does not log, emit or persist.

## Why a call ceiling exists at all, next to a cost cap that already works

Section 19's dollar caps cannot see these calls. NCBI E-utilities, the
Datasets API, PubTator3, LitVar2 and ClinicalTrials.gov are free, so a query
that issues four hundred of them spends nothing and breaches no cost cap
while consuming its own latency budget on retrieval and arriving at Write
with nothing left. Section 21.3 bounds the COUNT for that reason, and says
so: "distinct from the dollar cost cap (section 19) ... since NCBI and
enrichment calls are free".

## Why the counter lives here and charges at the transport, not at `act_node`

The obvious home is `act_node`'s planned-call loop, immediately beside the
`cost_control.check_per_query_cap` call already there. That would count the
wrong thing. `act_node` iterates PLANNED calls, of which a real query has
one to three, while Section 21.3 names where a 21st call actually comes
from: "a retry, a wider-than-expected fan-out, or an ELink traversal that
returns more targets than planned". Every one of those happens inside a
tool, below `act_node`, and is invisible to a counter that increments once
per planned call.

This is build phase 5.0's finding two arriving again for a second reason.
That phase put the audit hook at the transport chokepoints and never at
`act_node`, because five production call sites reach a data layer without
passing through `act_node` at all, and it proved that by execution rather
than by reading: the first audit line a live query ever wrote came from
`think_node`'s symbol resolution, before Act had run. A ceiling that cannot
see those calls is not the ceiling Section 21.3 describes.

So the two Layer 2/3 transports charge the budget, and `act_node` reads it.
The Layer 2/3 surface is exactly two functions and the enumeration is
closed: `ncbi_transport.execute_get` is the single HTTP chokepoint for all
eight HTTP tools, and `pathogen_ftp_transport` is the FTP path.
`graph_http_transport` is Layer 1 and is out of scope by 21.3's own wording.

## Why a ContextVar holding a mutable object, rather than a dict keyed by trace_id

A module-level `dict[trace_id, count]` is the first design that suggests
itself and it leaks: nothing evicts a finished query's entry, which is
exactly the defect F-1.2-01 recorded against `RunRegistry` and build phase
4.0 had to fix. A ContextVar is evicted by the runtime when its scope ends,
so the leak is not possible rather than merely unlikely.

The value is a MUTABLE object rather than an int on purpose. `contextvars`
copies the mapping when a task is created, so a child task rebinding an int
would increment a copy its parent and siblings never see, and a query that
fans out through `asyncio.gather` (which Section 21.3 explicitly preserves:
"independent calls within the 20-call ceiling still dispatch through
asyncio.gather") would get one budget per task instead of one per query.
Sharing one object means every task spawned inside the scope charges the
same counter, which is the whole point.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from system_03_search_agent.harness.harness import QueryClass

__all__ = [
    "MAX_LAYER_2_3_CALLS_PER_QUERY",
    "CallBudgetExceededError",
    "calls_made",
    "charge_one_call",
    "query_budget_scope",
    "reset_query_budget",
    "set_query_budget",
    "set_query_class",
    "wait_ceiling_s",
]

#: Section 21.3, stated as a number: "the at-most-20-API-calls-per-query
#: budget". Written down once, here. Changing it is a product-owner decision
#: per `system-design-patterns` pattern 4, not an implementation detail.
MAX_LAYER_2_3_CALLS_PER_QUERY: Final[int] = 20

#: Section 21.4's wait ceiling, as a fraction of the query class's own
#: latency budget rather than as a second table of absolute numbers.
#:
#: Derived, not invented, and the derivation is checkable. The spec says a
#: lookup-class query "accepts only a short queue wait, on the order of one
#: to two seconds". Ten percent of `harness._QUERY_CLASS_BUDGET_S`'s
#: product-owner-approved `lookup` figure of 15.0 seconds is 1.5 seconds,
#: which lands inside that stated range. The same fraction gives 2.0s for
#: single_hop and 3.0s for aggregate and multi_hop, matching the spec's
#: "several seconds" for a multi-hop query.
#:
#: A fraction rather than a table is what keeps the two from drifting: the
#: latency budgets were re-measured once already (build phase 2.1 widened
#: lookup from 5.0 to 15.0 against measured model latency), and a hardcoded
#: wait table would have silently kept the old proportions.
_WAIT_CEILING_FRACTION: Final[float] = 0.10

#: The cap on that fraction. `exploratory` budgets 120 seconds, and ten
#: percent of it is twelve, which is well past the "several seconds" Section
#: 21.4 describes for the longest query class. A call parked twelve seconds
#: in a queue has stopped being a slow call and become a hung one.
_WAIT_CEILING_MAX_S: Final[float] = 5.0

#: The floor under it, so a future narrower query class cannot derive a
#: ceiling so small that every queued call fails fast and the queue becomes
#: decoration.
_WAIT_CEILING_MIN_S: Final[float] = 0.5


class CallBudgetExceededError(Exception):
    """One query tried to issue more Layer 2/3 calls than Section 21.3 allows.

    Carries `limit`, `calls_made` and `tool` because
    `.claude/rules/tool-call-budgets.md` requires a budget error to tell the
    next agent step what to do about it, not merely that something failed.
    The Act step reads this to decide whether to synthesize from what it
    already has, which it cannot do from a bare failure label.
    """

    def __init__(self, *, tool: str, calls_made: int, limit: int) -> None:
        super().__init__(
            f"this query has already issued its {limit} permitted Layer 2/3 "
            f"API calls (Section 21.3); the call to {tool} was refused rather "
            "than issued. Synthesize from the results already gathered, or "
            "re-ask with a narrower query"
        )
        self.tool = tool
        self.calls_made = calls_made
        self.limit = limit


@dataclass
class _QueryBudget:
    """One query's mutable call counter and its query class.

    Shared by reference across every task the query spawns. See the module
    docstring for why that sharing is the point rather than an accident.
    """

    query_class: QueryClass
    calls: int = 0
    #: `asyncio.gather` runs coroutines on one event loop, so the increment
    #: below is already atomic with respect to other coroutines. This lock
    #: covers the case that is not: a tool that offloads a blocking call to
    #: a worker thread (`pathogen_detection`'s FTP transfer is the live
    #: candidate) and charges the budget from there.
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def charge(self, tool: str, limit: int) -> None:
        with self._lock:
            if self.calls >= limit:
                raise CallBudgetExceededError(
                    tool=tool, calls_made=self.calls, limit=limit
                )
            self.calls += 1


#: The run-scoped budget. `None` means no query scope is bound, which is a
#: real and supported state rather than an error: `s3-kgx-export` and any
#: maintenance script reach a data layer without being a query, and Section
#: 21.3 bounds "one query". See `charge_one_call`.
_budget_var: ContextVar[_QueryBudget | None] = ContextVar(
    "layer_2_3_call_budget", default=None
)


def set_query_budget(query_class: QueryClass) -> Token[_QueryBudget | None]:
    """Bind a fresh budget and return the token that unbinds it.

    Prefer `query_budget_scope`. This bare pair exists for the one caller a
    context manager does not fit: `run_streaming`'s try/finally already
    spans its whole body across a callback boundary, and reindenting that
    body under a second nested block to gain nothing is worse than a
    matched set/reset in the finally it already has. That is the same
    judgment, for the same function, that `observability.audit` already
    made for `set_trace_id`.
    """
    return _budget_var.set(_QueryBudget(query_class=query_class))


def reset_query_budget(token: Token[_QueryBudget | None]) -> None:
    """Undo one `set_query_budget`, restoring the previous binding."""
    _budget_var.reset(token)


@contextmanager
def query_budget_scope(query_class: QueryClass) -> Iterator[None]:
    """Bind a fresh per-query call budget for the duration of the block.

    One scope is one query. Entering it resets the count to zero, which is
    what makes the ceiling per query rather than per process, and leaving it
    restores whatever was bound before, so a nested scope cannot strand the
    outer one.

    Args:
        query_class: the class this query was routed to, which sets the
            queue wait ceiling `wait_ceiling_s` reports. Section 21.4 ties
            that ceiling to the caller's own latency budget rather than to
            one constant per call.
    """
    token = _budget_var.set(_QueryBudget(query_class=query_class))
    try:
        yield
    finally:
        _budget_var.reset(token)


def charge_one_call(*, tool: str, layer: int) -> None:
    """Charge one Layer 2 or Layer 3 access against the current query's budget.

    Called by the two transport chokepoints immediately BEFORE the request
    goes out, never after, so a refused call is never issued at all. That
    ordering matches `act_node`'s own discipline for the cost cap and is
    what makes "the 21st call does not reach the network" true rather than
    "the 21st call's result is discarded".

    Does nothing when no query scope is bound. That is deliberate and is a
    stated hole rather than an oversight: work outside a query, a KGX export
    batch or a maintenance script, is not a query, and refusing its 21st
    call would break a shipped delivery surface to enforce a bound that does
    not apply to it. `tracker/phase_6.0.md`'s coverage section records it.

    Args:
        tool: the caller's name, for the error message only.
        layer: 2 or 3. Accepted so a future per-layer sub-budget has the
            value it would need without changing every call site, and
            deliberately unused today: Section 21.3 states one combined
            ceiling over both layers, not one per layer.

    Raises:
        CallBudgetExceededError: if this query has already used its ceiling.
    """
    budget = _budget_var.get()
    if budget is None:
        return
    budget.charge(tool, MAX_LAYER_2_3_CALLS_PER_QUERY)


def set_query_class(query_class: QueryClass) -> None:
    """Update the running query's class once `think_node` has classified it.

    The scope has to be bound at the top of the run, before `think_node`
    runs at all, because `think_node` itself issues real Layer 2 calls for
    symbol resolution and those must be counted. But the query class is the
    output of that same step, so it is not knowable when the scope opens.

    The two facts are reconciled by opening the scope at the CONSERVATIVE
    floor, `lookup`, which is the shortest wait ceiling of the five classes,
    and widening it here once the real class is known. Failing toward the
    shortest ceiling is the safe direction: the cost of being wrong is a
    call that fails fast against a saturated pool and is retried or
    degraded, rather than one that parks for the wrong query's budget.

    The call COUNT is unaffected by class, so nothing about the Section 21.3
    ceiling depends on this ordering; only Section 21.4's wait ceiling does.

    Does nothing when no query scope is bound, matching `charge_one_call`.
    """
    budget = _budget_var.get()
    if budget is None:
        return
    budget.query_class = query_class


def calls_made() -> int | None:
    """Return how many Layer 2/3 calls this query has issued, or None.

    `None` means no query scope is bound, and it is a different fact from
    `0`, which means a scope is bound and unused. A caller that cannot tell
    those apart cannot tell "unbounded work" from "a fresh query".
    """
    budget = _budget_var.get()
    return None if budget is None else budget.calls


def wait_ceiling_s() -> float | None:
    """Return how long a call may wait in a saturated pool, or None.

    Section 21.4: "a lookup-class query ... accepts only a short queue wait
    ... A multi-hop or deep-research query ... tolerates a longer wait ...
    The queue reads the caller's remaining per-step time budget rather than
    applying one constant across every query class."

    Derived from `harness.budget_for_query_class`, so the two numbers cannot
    drift: a latency budget that is re-measured moves this ceiling with it.
    See `_WAIT_CEILING_FRACTION` for the derivation and the check against
    the spec's own stated figures.

    Returns `None` outside a query scope, where there is no query class to
    read a budget from. Every caller treats that as "use your own per-call
    default", which is what `execute_get` already did before this existed.

    The import below is deliberately local. `harness.harness` imports
    `litellm`, and this module is imported by both Layer 2/3 transports, so
    hoisting it to module scope would put the entire model stack on the
    import path of every tool that makes an HTTP call. It is also why this
    function, and not the module, is where the dependency lives.
    """
    budget = _budget_var.get()
    if budget is None:
        return None
    from system_03_search_agent.harness.harness import budget_for_query_class

    derived = budget_for_query_class(budget.query_class) * _WAIT_CEILING_FRACTION
    return min(max(derived, _WAIT_CEILING_MIN_S), _WAIT_CEILING_MAX_S)
