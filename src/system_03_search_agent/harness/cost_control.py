"""Cost caps enforcement and the `cost` event (T-2.0-03).

Spec: Technical_specification.md Section 19.1 (2800-2811), 19.2 (2813-2819),
19.3 (2821-2825), 19.4 (2827-2831), 19.5 (2833-2840).

Depends on:
    - system_03_search_agent.harness.harness (Harness.get_query_cost_usd,
      the running per-query total this module reads and never
      re-accumulates)
    - system_03_search_agent.harness.tiers (Tier, UnknownTierError)
    - system_03_search_agent.contracts.events (CostPayload, Event)
    - system_03_search_agent.data.models (Interaction)

Reads:
    - Environment: PER_QUERY_COST_CAP_USD, PER_USER_DAILY_QUERY_CAP,
      SYSTEM_DAILY_CAP_USD (env.example)
    - The `interactions` table (Section 15), for the two restart-safe
      counters, `user_daily_query_count` and `system_daily_cost_usd`.

Writes:
    - Nothing. Persisting a completed query's Interaction row is a
      different component's job (the Write step, a later ticket); this
      module only reads rows back that some other writer already
      persisted.

Three independently tracked running counters (Section 19.2), and three
different persistence strategies:

    - `query_cost_usd`: the active query's own running total. Lives
      entirely in-process on the `Harness` instance passed in
      (`harness.get_query_cost_usd(trace_id)`), reset per query by
      construction (a new query mints a new `trace_id`). This module never
      duplicates `Harness.track_cost`'s accumulation; it only reads the
      total back to decide whether one more call may fire.
    - `user_daily_query_count` and `system_daily_cost_usd`: computed live
      against the `interactions` table on every check, via a plain
      SQLAlchemy `SELECT`, rather than cached in an in-process counter that
      starts at zero on every process restart. This is what makes the two
      restart-safe by construction: there is no in-process value to lose,
      because there is no in-process value in the first place. Section
      19.2 frames this as "persist... at query completion, so a process
      restart never loses the day's totals"; a query that has completed
      has already had its Interaction row written by whichever component
      owns that write (the Write step), so a fresh COUNT/SUM against that
      table on the next query's pre-flight check already reflects every
      prior query, restarted process or not.

Daily boundary decision: the "current daily boundary" for both the
per-user query count and the system-wide dollar total is midnight UTC,
not a per-user local time or a rolling 24-hour window. Recorded in
DECISIONS.md (T-2.0-03). There is no per-user timezone concept anywhere
in the v1 schema (Section 15's `users.profile` JSONB could hold one
later, but nothing populates it today), and a single global boundary is
simpler to reason about, test, and explain to an end user ("resets at
00:00 UTC") than a boundary that silently varies by account.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from system_03_search_agent.contracts.events import CostPayload, Event
from system_03_search_agent.data.models import Interaction
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.harness.tiers import Tier, UnknownTierError

# ---------------------------------------------------------------------------
# Environment-configured cap values. No default, no silent fallback: a
# missing cap is a configuration gap to surface at the point it is needed,
# never a value invented in code (tool-call-budgets.md; production-standards
# hardening gate).
# ---------------------------------------------------------------------------


def _read_float_env(name: str) -> float:
    raw = os.environ.get(name)
    if not raw:
        raise RuntimeError(
            f"{name} is not set. Set it in the environment before enforcing "
            "cost caps (see env.example)."
        )
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} is set to {raw!r}, which is not a valid number") from exc


def _read_int_env(name: str) -> int:
    raw = os.environ.get(name)
    if not raw:
        raise RuntimeError(
            f"{name} is not set. Set it in the environment before enforcing "
            "cost caps (see env.example)."
        )
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} is set to {raw!r}, which is not a valid integer") from exc


def per_query_cost_cap_usd() -> float:
    """Return PER_QUERY_COST_CAP_USD (Section 19.1's $0.10 starter value)."""
    return _read_float_env("PER_QUERY_COST_CAP_USD")


def per_user_daily_query_cap() -> int:
    """Return PER_USER_DAILY_QUERY_CAP (Section 19.1's 100 queries/day starter value).

    Renamed from the misnamed `PER_USER_DAILY_CAP_USD` (T-2.0-03; see
    env.example and the DECISIONS.md entry): this cap is a query count, not
    a dollar figure.
    """
    return _read_int_env("PER_USER_DAILY_QUERY_CAP")


def system_daily_cap_usd() -> float:
    """Return SYSTEM_DAILY_CAP_USD (Section 19.1's $10/day starter value)."""
    return _read_float_env("SYSTEM_DAILY_CAP_USD")


# ---------------------------------------------------------------------------
# Daily boundary: midnight UTC (see the module docstring for why).
# ---------------------------------------------------------------------------


def _day_start(now: datetime | None = None) -> datetime:
    """Return the start (00:00 UTC) of the daily boundary containing `now`."""
    moment = now or datetime.now(UTC)
    return datetime(moment.year, moment.month, moment.day, tzinfo=UTC)


def _next_day_start(now: datetime | None = None) -> datetime:
    """Return the next daily boundary after `now`, the cap's reset time."""
    return _day_start(now) + timedelta(days=1)


# ---------------------------------------------------------------------------
# Cap 1: per-query cost cap. Pre-flight estimate, checked before a call
# fires, never discovered only after the fact (Section 19.2).
# ---------------------------------------------------------------------------

# Rough, deliberately conservative (high) typical token profile per tier,
# (typical_prompt_tokens, typical_completion_tokens). This is a documented
# planning assumption, not a measured constant: guard-tier calls are short
# classification prompts, plan-tier calls carry the tool schemas and
# tool-selection reasoning, synth-tier calls carry retrieved passages and
# citation assembly and are the longest of the three. Revisit once Phase 6
# model-bench and real query logs give an empirical baseline.
_TYPICAL_TOKEN_PROFILE: dict[Tier, tuple[int, int]] = {
    "guard": (500, 100),
    "plan": (2000, 500),
    "synth": (4000, 1000),
}

# A conservative (high) blended USD-per-token ceiling used only for the
# pre-flight estimate below, not the harness's real per-call metering
# (`harness.harness._price_per_token`, which prices the exact model that
# actually answered after the call returns). Chosen as roughly the upper
# end of a frontier model's blended input/output OpenRouter price at the
# time this ticket was written, so the estimate errs toward refusing a
# borderline call rather than admitting one that turns out to cost more
# than expected.
_CONSERVATIVE_PRICE_PER_TOKEN_USD = 5e-6


def estimate_call_cost_usd(tier: Tier) -> float:
    """Return a conservative, static USD estimate for one `tier` call.

    Used only to decide, before any call is dispatched, whether the next
    call could plausibly push a query over its per-query cap. Not the
    harness's real metered cost, which is computed after the call returns
    from actual token usage and the resolved model's real OpenRouter price.

    Raises:
        UnknownTierError: for a tier outside {"guard", "plan", "synth"}.
    """
    profile = _TYPICAL_TOKEN_PROFILE.get(tier)
    if profile is None:
        raise UnknownTierError(
            f"unknown tier {tier!r}: expected one of {sorted(_TYPICAL_TOKEN_PROFILE)}"
        )
    prompt_tokens, completion_tokens = profile
    return (prompt_tokens + completion_tokens) * _CONSERVATIVE_PRICE_PER_TOKEN_USD


class QueryCapExceededError(RuntimeError):
    """Raised when dispatching one more model call would exceed the per-query cap.

    Section 19.1's trigger behavior for this cap: on catching this error,
    the agent loop stops issuing further model calls for the query and
    moves directly to Write with whatever tool results already exist, so
    the answer ships as a partial cited result, never a blank failure.
    Enforcing that routing is the loop's job (T-2.0-07 and later); this
    module only raises the classified, catchable signal.
    """

    def __init__(
        self,
        message: str,
        *,
        query_cost_usd: float,
        query_cap_usd: float,
        estimated_call_cost_usd: float,
    ) -> None:
        super().__init__(message)
        self.query_cost_usd = query_cost_usd
        self.query_cap_usd = query_cap_usd
        self.estimated_call_cost_usd = estimated_call_cost_usd


def check_per_query_cap(
    harness: Harness,
    trace_id: str,
    tier: Tier,
    *,
    query_cap_usd: float | None = None,
) -> None:
    """Pre-flight check: refuse to dispatch if the next `tier` call would exceed the cap.

    Call this immediately before `harness.call_tier(tier, ...)`, never
    after. Reads `harness.get_query_cost_usd(trace_id)`, the running total
    `Harness.track_cost` already accumulates (never duplicated here), adds
    this tier's conservative estimated call cost, and refuses before any
    network attempt if the projected total would exceed the cap.

    Args:
        query_cap_usd: overrides PER_QUERY_COST_CAP_USD when given (mainly
            for tests); resolved from the environment otherwise.

    Raises:
        QueryCapExceededError: if dispatching the next call would push the
            query's running cost past the cap.
        UnknownTierError: for a tier outside {"guard", "plan", "synth"}.
    """
    cap = per_query_cost_cap_usd() if query_cap_usd is None else query_cap_usd
    current = harness.get_query_cost_usd(trace_id)
    estimated = estimate_call_cost_usd(tier)
    projected = current + estimated
    if projected > cap:
        raise QueryCapExceededError(
            f"dispatching one more {tier!r} call for query {trace_id!r} would "
            "project its running cost past the per-query cap; stop issuing "
            "further model calls for this query and move to Write with "
            "whatever tool results already exist so the answer ships as a "
            "partial cited result",
            query_cost_usd=current,
            query_cap_usd=cap,
            estimated_call_cost_usd=estimated,
        )


# ---------------------------------------------------------------------------
# Cap 2: per-user daily query count. Checked before Guardrail runs, against
# the interactions table, restart-safe by construction (see module
# docstring).
# ---------------------------------------------------------------------------


def get_user_daily_query_count(
    session: Session, user_id: uuid.UUID, *, now: datetime | None = None
) -> int:
    """Count `user_id`'s interactions since the current daily boundary (00:00 UTC)."""
    day_start = _day_start(now)
    stmt = (
        select(func.count())
        .select_from(Interaction)
        .where(Interaction.user_id == user_id, Interaction.created_at >= day_start)
    )
    return int(session.execute(stmt).scalar_one())


def user_daily_cap_decline_message(count: int, reset_at: datetime) -> str:
    """Build the per-user daily cap decline message (Section 19.5).

    States the query count and the reset time. The count itself is not a
    dollar figure and stays visible per Section 19.5 ("Showing the query
    count itself (100/day reached) is not a dollar figure and stays
    visible"). Never includes a dollar figure or currency symbol.
    """
    reset_label = reset_at.strftime("%H:%M UTC")
    return (
        f"You've reached {count} queries today. New queries will be "
        f"available again at {reset_label}."
    )


class UserDailyQueryCapExceededError(RuntimeError):
    """Raised when a user has reached PER_USER_DAILY_QUERY_CAP for the current day.

    Section 19.1's trigger behavior: new queries from this user are
    declined for the rest of the day. Caught before Guardrail runs, per
    the acceptance criteria for this ticket.
    """

    def __init__(self, message: str, *, count: int, cap: int, reset_at: datetime) -> None:
        super().__init__(message)
        self.count = count
        self.cap = cap
        self.reset_at = reset_at


def check_user_daily_query_cap(
    session: Session,
    user_id: uuid.UUID,
    *,
    cap: int | None = None,
    now: datetime | None = None,
) -> None:
    """Decline a new query if `user_id` has reached the per-user daily query cap.

    Args:
        cap: overrides PER_USER_DAILY_QUERY_CAP when given (mainly for
            tests); resolved from the environment otherwise.

    Raises:
        UserDailyQueryCapExceededError: if `user_id`'s count for the
            current daily boundary is at or past the cap.
    """
    resolved_cap = per_user_daily_query_cap() if cap is None else cap
    count = get_user_daily_query_count(session, user_id, now=now)
    if count >= resolved_cap:
        reset_at = _next_day_start(now)
        raise UserDailyQueryCapExceededError(
            user_daily_cap_decline_message(count, reset_at),
            count=count,
            cap=resolved_cap,
            reset_at=reset_at,
        )


# ---------------------------------------------------------------------------
# Cap 3: system-wide daily dollar cap. Checked before accepting a new query
# from any user, against the interactions table, restart-safe by
# construction (see module docstring).
# ---------------------------------------------------------------------------


def get_system_daily_cost_usd(session: Session, *, now: datetime | None = None) -> float:
    """Sum every user's `cost_usd` since the current daily boundary (00:00 UTC).

    `COALESCE(SUM(...), 0)` so a day with zero completed interactions
    returns 0.0, not NULL.
    """
    day_start = _day_start(now)
    stmt = select(func.coalesce(func.sum(Interaction.cost_usd), 0)).where(
        Interaction.created_at >= day_start
    )
    total = session.execute(stmt).scalar_one()
    return float(total)


# Section 19.5: "the system states plainly that it has paused accepting new
# queries for the day to stay within its operating budget. No dollar
# figure, no technical cause named beyond 'operating budget.'"
SYSTEM_DAILY_CAP_DECLINE_MESSAGE = (
    "The system has paused accepting new queries for today to stay within "
    "its operating budget. Please try again tomorrow."
)


class SystemDailyCostCapExceededError(RuntimeError):
    """Raised once system_daily_cost_usd reaches SYSTEM_DAILY_CAP_USD.

    Section 19.1's trigger behavior: the system pauses accepting new
    queries from any user for the rest of the day.
    """


def check_system_daily_cost_cap(
    session: Session,
    *,
    cap: float | None = None,
    now: datetime | None = None,
) -> None:
    """Decline a new query if the system-wide daily dollar cap has been reached.

    Args:
        cap: overrides SYSTEM_DAILY_CAP_USD when given (mainly for tests);
            resolved from the environment otherwise.

    Raises:
        SystemDailyCostCapExceededError: if the running system-wide total
            for the current daily boundary is at or past the cap.
    """
    resolved_cap = system_daily_cap_usd() if cap is None else cap
    total = get_system_daily_cost_usd(session, now=now)
    if total >= resolved_cap:
        raise SystemDailyCostCapExceededError(SYSTEM_DAILY_CAP_DECLINE_MESSAGE)


# Section 19.5: the per-query cap's user-facing note. Not a decline (the
# query still ships an answer), but named here alongside the other two
# decline messages because the acceptance criteria for this ticket requires
# every per-query-cap, per-user-cap, and system-wide-cap user-facing string
# to carry no dollar figure or currency symbol.
PER_QUERY_CAP_PARTIAL_RESULT_NOTE = (
    "This query reached its resource limit before finishing, so the answer "
    "below reflects a partial result gathered so far."
)


# ---------------------------------------------------------------------------
# The cost event (Section 19.3), and the builder-only adapter filter
# (Section 19.4).
# ---------------------------------------------------------------------------


def build_cost_event_payload(
    harness: Harness,
    trace_id: str,
    tier: Tier,
    *,
    query_cap_usd: float | None = None,
) -> CostPayload:
    """Build the `cost` event payload after a metered model call (Section 19.3).

    `query_cost_usd` and `cap_fraction` are running totals for the active
    query, not deltas, read from `harness.get_query_cost_usd(trace_id)`,
    the same accumulator `call_tier`/`track_cost` already maintain. This
    function computes `cap_fraction` itself; it never duplicates the
    accumulation logic that produces `query_cost_usd`.

    Args:
        query_cap_usd: overrides PER_QUERY_COST_CAP_USD when given (mainly
            for tests); resolved from the environment otherwise.
    """
    cap = per_query_cost_cap_usd() if query_cap_usd is None else query_cap_usd
    current = harness.get_query_cost_usd(trace_id)
    cap_fraction = current / cap if cap > 0 else 0.0
    return CostPayload(
        query_cost_usd=current,
        query_cap_usd=cap,
        cap_fraction=cap_fraction,
        model_tier=tier,
    )


# Section 19.4: "Every end-user-facing adapter filters the cost event out:
# the React UI, the public REST and SSE route, the MCP server, and the CLI
# never forward it. Only the operator dashboard adapter subscribes to it."
#
# This module owns the filtering *logic* (this set and the two functions
# below); wiring it into a specific adapter's response path (the web_sse
# `/query` route, once T-2.0-07 replaces `core/run.py`'s scaffold with the
# real LangGraph loop that can actually emit a `cost` event) is out of this
# ticket's file scope (`src/system_03_search_agent/harness/cost_control.py`
# only), and is deferred to whichever ticket wires the adapter's response
# path to the real event stream.
_BUILDER_ONLY_EVENT_TYPES: frozenset[str] = frozenset({"cost"})


def is_end_user_visible_event_type(event_type: str) -> bool:
    """Return False for an event type that must never reach an end-user surface."""
    return event_type not in _BUILDER_ONLY_EVENT_TYPES


def filter_events_for_end_user(events: Iterable[Event]) -> list[Event]:
    """Drop builder-only events (currently just `cost`) from an event sequence.

    Every end-user-facing adapter (the React UI, the public REST/SSE
    route, the MCP server, the CLI) applies this before forwarding events;
    only the operator dashboard adapter sees the unfiltered stream.
    """
    return [event for event in events if is_end_user_visible_event_type(event.type)]
