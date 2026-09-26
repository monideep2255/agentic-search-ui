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

import math
import os
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from system_03_search_agent.contracts.events import CostPayload, DonePayload, Event
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
    """Read `name` as a finite, positive float.

    F-2.0-09 (adversary, confirmed high, 2026-07-28): `float()` happily
    parses `"inf"`, `"-inf"`, `"nan"`, and out-of-range literals like
    `"1e400"` (which Python's float parser silently rounds to `inf`).
    `inf` disables a cap outright (nothing is ever `> inf`) while
    `cap_fraction` in the `cost` event reports `0.0` forever, so the one
    signal an operator would use to notice the cap is disabled is itself
    falsified. `nan` is worse: every comparison against `nan` is `False`,
    so the cap silently never fires, and a downstream consumer computing
    `cap_fraction` on real data eventually hits a `nan`-tainted value.
    Reject both classes explicitly, at read time, before either is used
    to gate a cost decision.
    """
    raw = os.environ.get(name)
    if not raw:
        raise RuntimeError(
            f"{name} is not set. Set it in the environment before enforcing "
            "cost caps (see env.example)."
        )
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} is set to {raw!r}, which is not a valid number") from exc
    if not math.isfinite(value) or value <= 0:
        raise RuntimeError(
            f"{name} is set to {raw!r}, which parses to {value!r}; a cost cap "
            "must be a finite, positive number (inf, -inf, nan, and "
            "non-positive values are all rejected, since any of them "
            "silently disables the cap it is supposed to enforce)"
        )
    return value


def _read_int_env(name: str) -> int:
    """Read `name` as a positive integer. See `_read_float_env` for why
    non-positive values are rejected rather than silently accepted."""
    raw = os.environ.get(name)
    if not raw:
        raise RuntimeError(
            f"{name} is not set. Set it in the environment before enforcing "
            "cost caps (see env.example)."
        )
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} is set to {raw!r}, which is not a valid integer") from exc
    if value <= 0:
        raise RuntimeError(
            f"{name} is set to {raw!r}; a query-count cap must be a positive "
            "integer, since zero or negative values are not a meaningful cap"
        )
    return value


# How many times the per-guest attempt ceiling the shared anonymous daily
# cap must be, at minimum (F-4.10-R-11). Ten means no single anonymous
# IDENTITY can take more than a tenth of the day.
#
# F-4.10-V-01 CORRECTS what this comment used to say next, and the
# correction matters because three consecutive fixes were built on the
# sentence being removed. It read: "so it takes ten determined callers
# rather than one to deny the product to everyone else, and the mint
# throttle is what stands in front of that." Both halves were false. It
# takes ten IDENTITIES, not ten callers, and one caller mints ten identities
# for nothing; and the mint throttle stands in front of nothing at these
# values, since it admits 60 mints per minute per source and the attack
# needs 20. Measured: 20 identities from one source, zero mints refused, the
# whole 200-run day gone in 1.84 seconds.
#
# What actually bounds one caller is `anon_daily_source_share` below, which
# is keyed on the source rather than on anything the caller mints. This
# constant keeps its own narrower job: it stops the shipped defaults from
# drifting into a state where one identity alone is the whole day.
_MIN_ANON_DAILY_CAP_MULTIPLE = 10

# F-4.10-V-01, product-owner decision 2026-08-15: the share of one UTC day's
# anonymous budget any single SOURCE may take.
#
# A tenth, expressed as a divisor of `ANON_DAILY_RUN_CAP` rather than as a
# second free-floating constant, so the two cannot drift apart. At the
# shipped cap of 200 that is 20 runs per source, which is four complete
# visitors at the five-answer allowance, and it is the number the admit arm
# of the premise gate is written against.
#
# Why a share of the day rather than a tighter mint throttle, which is the
# obvious fix and is the one that is structurally unavailable: making 20
# mints refusable requires `_MINT_THROTTLE_MAX_PER_WINDOW < 20`, and the
# premise gate's own admit arm requires 25 consecutive mints from one shared
# address to succeed. Many real users share one address behind office NAT, a
# university network or conference wifi. A control that refuses those rooms
# has destroyed the product to protect it, which is the failure this phase
# built a two-armed gate to catch.
_ANON_SOURCE_SHARE_DIVISOR = 10

# The floor under that share. Without it a small configured cap divides to
# zero and the bound refuses EVERY anonymous caller, which is the same
# refuses-everybody failure the mint throttle's first version shipped
# (F-4.10-04). Five is one whole visitor's answer allowance
# (`data.guest_sessions.FREE_RUN_ALLOWANCE`), restated here as a literal
# rather than imported, because `harness` importing from `data` would invert
# this codebase's dependency direction for one integer. The two are pinned
# together by a test rather than by an import
# (`TestTheAnonymousSourceShareIsMateriallyBelowTheDay` in
# `tests/.../harness/test_cost_control.py`), so a change to either that
# breaks the relationship goes red.
_MIN_ANON_SOURCE_SHARE = 5


def anon_daily_source_share(daily_cap: int) -> int:
    """Return how many of `daily_cap`'s runs one SOURCE may take in a day.

    The third anonymous bound, and the one that answers the question the
    other two do not. `anon_daily_run_cap` bounds the day, so it holds the
    money but says nothing about who spent it. `ATTEMPT_ALLOWANCE` bounds an
    identity, and `POST /auth/guest` mints identities for free. Between them
    sat the measured attack: 20 identities from one apparent source, zero
    mints refused, all 200 of the day's runs consumed in 1.84 seconds, every
    other anonymous visitor refused until UTC midnight (F-4.10-V-01).

    Derived from the cap rather than configured separately, so an operator
    raising the day's budget raises each source's share with it and the two
    can never drift into a state where the share IS the day.

    A caller whose source cannot be determined is not bounded by this at
    all; see `data.guest_sessions.spend_one_anonymous_run`, which allows
    that case deliberately and lets the day's ceiling bound it, matching the
    mint throttle's existing choice for the same input.

    Args:
        daily_cap: the system-wide ceiling for the current UTC day, from
            `anon_daily_run_cap`.

    Returns:
        A positive integer, never zero: the floor is what stops a small
        configured cap from producing a bound that refuses everybody.

    Raises:
        TypeError: If daily_cap is not an int (bool excluded).
        ValueError: If daily_cap is not positive.
    """
    if isinstance(daily_cap, bool) or not isinstance(daily_cap, int):
        raise TypeError("daily_cap must be an int")
    if daily_cap < 1:
        raise ValueError("daily_cap must be a positive integer")
    return max(_MIN_ANON_SOURCE_SHARE, daily_cap // _ANON_SOURCE_SHARE_DIVISOR)


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


def anon_daily_run_cap() -> int:
    """Return ANON_DAILY_RUN_CAP: how many runs ALL anonymous callers
    together may start in one UTC day (build phase 4.10, design decision 8).

    This is the only enforced bound on TOTAL anonymous spend, and it exists
    because the other two cannot reach an anonymous caller at all.
    `per_user_daily_query_cap` is keyed on a `users` row and is skipped
    entirely when `user_id is None`, which is every guest by design decision
    2. `system_daily_cap_usd` sums `interactions.cost_usd`, and nothing in
    `src/` writes an `Interaction` row (F-2.0-04, build phase 4.6), so it
    reads $0.00 and can never fire.

    The per-guest ANSWER allowance is NOT a substitute. It is keyed on a
    guest identity, and `POST /auth/guest` mints those for free, so it
    bounds a variable the caller controls the supply of: the build phase
    4.10 adversary round accepted 40 paid pipelines in 0.25 seconds by
    minting one guest per run (F-4.10-A-01). This cap is keyed on the
    calendar day, which nobody controls the supply of.

    IT IS ALSO NOT A BOUND ON ONE CALLER, and this docstring used to imply
    it was ("the only enforced spending bound on an anonymous caller").
    F-4.10-R-01 measured the difference: because a guardrail refusal
    refunds the answer allowance, a caller sending only refusable text
    advanced no per-identity counter at all, so one guest token exhausted
    this shared ceiling in 1.68 seconds and every other anonymous visitor
    was refused for the rest of the day. The per-identity bound is
    `ATTEMPT_ALLOWANCE` in `data/guest_sessions.py`, which counts runs
    STARTED and is never refunded.

    AND THAT PAIR IS STILL NOT ENOUGH, which F-4.10-V-01 measured and which
    this docstring's previous last sentence got wrong. It said the two were
    "complements, not substitutes: this one bounds the system's money, that
    one bounds any single caller's share of it." The second half was false.
    `ATTEMPT_ALLOWANCE` bounds a single IDENTITY, and one caller mints
    identities for nothing: 20 mints, none refused by the throttle, took all
    200 of the day's runs in 1.84 seconds. A caller's share of the day is
    bounded by `anon_daily_source_share` above, which is keyed on the
    connection source, the one thing that attack did not vary.

    So there are three bounds and each answers a different question: this
    one, how much the system spends in a day; the source share, how much of
    that day one caller may take; `ATTEMPT_ALLOWANCE`, how much one identity
    may take. Removing any one of them restores a measured attack.
    """
    return _read_int_env("ANON_DAILY_RUN_CAP")


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
# This module owns the filtering *logic* (this set and the functions
# below); wiring it into a specific adapter's response path (the web_sse
# `/query` route, once T-2.0-07 replaces `core/run.py`'s scaffold with the
# real LangGraph loop that can actually emit a `cost` event) is out of this
# ticket's file scope (`src/system_03_search_agent/harness/cost_control.py`
# only), and is deferred to whichever ticket wires the adapter's response
# path to the real event stream.
_BUILDER_ONLY_EVENT_TYPES: frozenset[str] = frozenset({"cost"})


def _operator_user_ids() -> frozenset[str]:
    """Return the allowlist of user ids permitted to request operator visibility.

    Reads `OPERATOR_USER_IDS` fresh on every call (an operator-set env var
    changes rarely and reading it live costs nothing here, unlike the
    per-query cost caps this module also reads). Empty or unset resolves
    to an empty set, which `is_operator_user` treats as "nobody": the
    allowlist fails closed, never open, when unconfigured.
    """
    raw = os.environ.get("OPERATOR_USER_IDS", "")
    return frozenset(entry.strip() for entry in raw.split(",") if entry.strip())


def is_operator_user(user_id: str | None) -> bool:
    """Return whether `user_id` may request operator visibility (Section 19.4).

    A caller-supplied `RequestContext.operator_mode=true` is not, on its
    own, authorization to see unredacted cost and token data: `user_id`
    must also appear in the `OPERATOR_USER_IDS` allowlist. No role or
    permission system exists yet (Section 15's auth model has no
    admin/operator field), so this allowlist is the interim access
    control. `user_id=None` (no authenticated caller) is never an
    operator.
    """
    if user_id is None:
        return False
    return user_id in _operator_user_ids()


def is_end_user_visible_event_type(event_type: str) -> bool:
    """Return False for an event type that must never reach an end-user surface."""
    return event_type not in _BUILDER_ONLY_EVENT_TYPES


# F-2.0-05 (judge, filed 2026-07-28; resolved by explicit product-owner
# decision the same day: "cost is for internal. I want to see the cost,
# the token usage"). Section 19.3 and Section 19.5 read as contradictory
# in isolation: 19.3 wants `done.total_cost_usd` to carry the query's
# final cost so a subscriber that missed every intermediate `cost` event
# still gets the total, while 19.5 states no dollar figure ever reaches
# an end-user surface. The product owner's resolution: cost and token
# usage are internal-only data. `done.total_cost_usd` keeps its real
# value on the internal event list (what an operator surface, or a test,
# or `Harness.get_query_cost_usd` sees), and is redacted to 0.0 only on
# the copy that reaches an end-user-facing adapter, the same "computed
# internally, stripped only at the end-user boundary" treatment this
# module already gives the `cost` event itself. `total_cost_usd` cannot
# simply be dropped the way a whole `cost` event is: it is a required
# field on the locked `DonePayload` contract (Section 2.3), so removing
# it would be a breaking wire-contract change, not a redaction.
def _redact_done_event_for_end_user(event: Event) -> Event:
    """Return `event` with `total_cost_usd` zeroed out if `event` is a `done`
    event; return `event` unchanged for every other type.

    Constructs a new `Event`, since `Event` and its payload are immutable
    Pydantic models; the original `event` (and its real cost) is never
    mutated, so an internal caller holding the same object still sees the
    true value.
    """
    if event.type != "done":
        return event
    redacted_payload = DonePayload.model_validate(event.payload).model_copy(
        update={"total_cost_usd": 0.0}
    )
    return event.model_copy(update={"payload": redacted_payload.model_dump()})


def sanitize_event_for_end_user(event: Event) -> Event | None:
    """Sanitize one event for an end-user-facing adapter (Section 19.4, 19.5).

    The per-event sibling of `filter_events_for_end_user`, added in T-1.2-02
    for the streaming SSE path: a consumer reading events one at a time off
    a queue as they arrive (rather than holding a fully materialized list)
    calls this once per event instead of re-deriving the same drop/redact
    logic inline.

    Returns:
        None if `event` must be dropped entirely (a builder-only event
        type, currently just `cost`). Otherwise the event, redacted via
        `_redact_done_event_for_end_user` if it is a `done` event
        (unchanged for every other type).
    """
    if not is_end_user_visible_event_type(event.type):
        return None
    return _redact_done_event_for_end_user(event)


def filter_events_for_end_user(events: Iterable[Event]) -> list[Event]:
    """Sanitize an event sequence for an end-user-facing adapter (Section 19.4, 19.5).

    Drops builder-only events (currently just `cost`) entirely, and
    redacts `total_cost_usd` out of any `done` event to 0.0 (F-2.0-05),
    so no dollar figure of any kind reaches an end-user surface. Every
    end-user-facing adapter (the React UI, the public REST/SSE route,
    the MCP server, the CLI) applies this before forwarding events; only
    the operator dashboard adapter sees the unfiltered stream with real
    cost data intact.

    Built on `sanitize_event_for_end_user`, the per-event entry point,
    rather than duplicating its drop/redact logic here.
    """
    sanitized = (sanitize_event_for_end_user(event) for event in events)
    return [event for event in sanitized if event is not None]
