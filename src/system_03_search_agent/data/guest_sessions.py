"""Data-layer functions for `guest_sessions`: creation and the atomic spend.

T-4.10-02, design decision 3 (`tracker/phase_4.10.md`): the allowance is
counted by ONE conditional `UPDATE ... RETURNING`, never a `SELECT`
followed by an `UPDATE`. A read-then-write lets two concurrent requests
both observe four used and both take the fifth, turning a five-search
allowance into six reachable by anyone who opens two tabs. `spend_one_run`
below is that single statement; the classification lookup it runs when the
UPDATE returns no row happens strictly AFTER the write decision is already
final, so it never gates the write and never reintroduces the race.

Depends on:
    - system_03_search_agent.data.models (GuestSession)

Reads:
    - The `guest_sessions` table.

Writes:
    - The `guest_sessions` table: one INSERT per `create_guest_session`
      call, one conditional UPDATE per `spend_one_run` call, one conditional
      decrement per `refund_one_run` call.
    - The `guest_daily_usage` table: one conditional upsert per
      `spend_one_anonymous_run` call, and one conditional decrement per
      `refund_one_run` call that is given a `daily_day`.

    Every public function here commits (or rolls back) the session it is
    given, matching how `auth/router.py` manages its own session's
    transaction boundary directly rather than through a shared
    repository-commit helper; callers pass a session scoped to one
    operation. `spend_one_anonymous_run` and `refund_one_run` each touch
    both tables and commit ONCE, so the two counters can never disagree
    because one statement landed and the other did not (design decision 8's
    constraint 1, and F-4.10-R-03, which measured that constraint being
    violated by a function that committed twice).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import Enum
from typing import Final

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from system_03_search_agent.data.models import GuestSession

# The free-run allowance a fresh guest session starts with, and the default
# cap `spend_one_run` enforces when the caller does not override it. Five,
# per design decision 6's wire shape and the premise gate's own
# `_EXPECTED_FREE_SEARCHES`. Named here rather than left as a magic number
# at each call site: changing this value changes what the five dots in
# `components/guest/GuestAllowance.tsx` mean.
FREE_RUN_ALLOWANCE: Final[int] = 5

# F-4.10-R-01, product-owner decision 2026-08-15: a guest gets five ANSWERS
# and at most ten ATTEMPTS. Ten rather than five because the whole point of
# the F-4.10-A-04 refund is that a clumsy question should not cost a visitor
# an answer, and a ceiling equal to the answer allowance would make the
# refund purely decorative. Ten rather than fifty because this is the only
# per-identity bound on how much of the SHARED daily budget one anonymous
# caller can move: at ten, draining a 200-run day needs 20 mints instead of
# one, which is a burst the per-source mint throttle can see.
#
# Not an env var, deliberately, matching FREE_RUN_ALLOWANCE directly above:
# both numbers are product decisions about what a guest gets, and a second
# way to configure them is a second way for the wire shape, the copy and the
# enforcement to disagree.
ATTEMPT_ALLOWANCE: Final[int] = 10


class SpendState(str, Enum):
    """The outcomes `spend_one_run` can report.

    Never a bare bool: a caller needs to distinguish "no allowance left"
    (the 403 `guest_allowance_exhausted` design decision 5 calls for) from
    "this id no longer identifies a spendable session" (revoked by
    migration, or never existed), and a bool collapses both to False.
    """

    SPENT = "spent"
    EXHAUSTED = "exhausted"
    REVOKED_OR_UNKNOWN = "revoked_or_unknown"
    # F-4.10-R-01, build phase 4.10. Distinct from EXHAUSTED because the two
    # mean different things to the person reading the refusal: EXHAUSTED is
    # "you have had your five answers", which is the sign-in wall's own
    # sentence, while this one is "you have asked as many questions as a
    # guest can, and most of them were refused before they were answered".
    # Both are permanent for this identity, so both are a 403 rather than a
    # 429 by design decision 5's reasoning (retrying never helps, so a
    # Retry-After would be a lie the UI would repeat); they carry different
    # machine-readable reasons so the wall can say something true for each.
    ATTEMPTS_EXHAUSTED = "attempts_exhausted"
    # Build phase 4.10, design decision 8. Distinct from EXHAUSTED because
    # the two mean opposite things to the caller and therefore carry
    # different HTTP statuses: EXHAUSTED is this guest's own allowance,
    # spent for good, and retrying never helps (403). This one is the
    # system-wide daily ceiling on ALL anonymous runs, which resets at UTC
    # midnight and which signing in bypasses entirely (429). Collapsing
    # them would make one of the two messages a lie.
    DAILY_CAP_REACHED = "daily_cap_reached"


@dataclass(frozen=True)
class SpendResult:
    """The outcome of one `spend_one_run` call.

    `runs_used` is populated on SPENT (the new count, straight off the
    UPDATE's own `RETURNING` clause) and on EXHAUSTED and ATTEMPTS_EXHAUSTED
    (the count at the moment of refusal, so a caller can report it
    honestly); it is None on REVOKED_OR_UNKNOWN, where there is no live
    count to report.

    `attempts_used` follows the same rule for the attempt counter
    (F-4.10-R-01) and is None wherever `runs_used` is.
    """

    state: SpendState
    runs_used: int | None = None
    attempts_used: int | None = None


def create_guest_session(session: Session) -> GuestSession:
    """Insert a new `guest_sessions` row and return it, allowance at zero.

    Commits the given session, so pass a session scoped to this one call.

    Args:
        session: an active SQLAlchemy Session bound to the user-data
            engine.

    Returns:
        The newly inserted GuestSession, with its server-generated `id`,
        `created_at`, and `last_seen_at` populated.

    Raises:
        TypeError: If session is not a Session.
    """
    if not isinstance(session, Session):
        raise TypeError("session must be a sqlalchemy.orm.Session")
    guest = GuestSession()
    session.add(guest)
    session.commit()
    session.refresh(guest)
    return guest


def _coerce_guest_id(guest_id: object) -> uuid.UUID:
    """Normalize `guest_id` to a `uuid.UUID`, raising on any other shape."""
    if isinstance(guest_id, uuid.UUID):
        return guest_id
    if not isinstance(guest_id, str):
        raise TypeError("guest_id must be a str or uuid.UUID")
    if not guest_id:
        raise ValueError("guest_id must not be empty")
    try:
        return uuid.UUID(guest_id)
    except ValueError:
        raise ValueError("guest_id is not a valid UUID") from None


def _validate_cap(cap: object) -> int:
    """Validate `cap` is a real, positive int (bool excluded)."""
    if isinstance(cap, bool) or not isinstance(cap, int):
        raise TypeError("cap must be an int")
    if cap < 1:
        raise ValueError("cap must be a positive integer")
    return cap


# The single conditional spend statement design decision 3 specifies, now
# gated on BOTH ceilings (F-4.10-R-01). Each `... < :cap` is evaluated
# against the PRE-update row, so Postgres's own row-level lock on the UPDATE
# is what makes two concurrent callers racing this statement unable to both
# push either count past its ceiling: the second waits for the first's
# transaction to commit, then re-evaluates this WHERE clause against the row
# the first just wrote.
#
# BOTH counters advance in this ONE statement, and both ceilings gate it, so
# there is no ordering between them for a concurrent caller to slip through.
# Spending the attempt in a second statement would reopen exactly the
# read-then-write window the single conditional UPDATE exists to close.
_SPEND_STATEMENT = text(
    "UPDATE guest_sessions"
    "   SET runs_used = runs_used + 1,"
    "       attempts_used = attempts_used + 1,"
    "       last_seen_at = now()"
    " WHERE id = :guest_id AND revoked_at IS NULL"
    "   AND runs_used < :cap AND attempts_used < :attempt_cap"
    " RETURNING runs_used, attempts_used"
)


def _apply_spend(
    session: Session,
    guest_uuid: uuid.UUID,
    *,
    cap: int,
    attempt_cap: int,
) -> SpendResult:
    """Run the conditional spend and classify a refusal. Commits NOTHING.

    Split out of `spend_one_run` for F-4.10-R-03: design decision 8's
    constraint 1 requires the per-guest spend and the per-day spend to
    happen in ONE transaction, and a helper that commits cannot be composed
    into one. `spend_one_run` below is this function plus a commit, for the
    callers that genuinely are a single operation;
    `spend_one_anonymous_run` composes this one with the daily statement and
    commits once at the end.
    """
    spent_row = session.execute(
        _SPEND_STATEMENT,
        {"guest_id": guest_uuid, "cap": cap, "attempt_cap": attempt_cap},
    ).first()
    if spent_row is not None:
        return SpendResult(
            SpendState.SPENT,
            runs_used=int(spent_row[0]),
            attempts_used=int(spent_row[1]),
        )

    lookup_row = session.execute(
        select(
            GuestSession.revoked_at,
            GuestSession.runs_used,
            GuestSession.attempts_used,
        ).where(GuestSession.id == guest_uuid)
    ).first()
    if lookup_row is None or lookup_row[0] is not None:
        return SpendResult(SpendState.REVOKED_OR_UNKNOWN)
    runs_used, attempts_used = int(lookup_row[1]), int(lookup_row[2])
    # ANSWERS are checked first, and the order is a decision rather than an
    # accident. A guest who has had all five answers is exactly the visitor
    # the sign-in wall's own sentence describes ("you have used your free
    # searches"), and that is the more informative and more actionable of
    # the two refusals. ATTEMPTS_EXHAUSTED is reported only when the answer
    # allowance is genuinely still open, which is the case the attempt
    # ceiling was added for: a caller who only ever triggers refusals.
    if runs_used >= cap:
        return SpendResult(
            SpendState.EXHAUSTED, runs_used=runs_used, attempts_used=attempts_used
        )
    return SpendResult(
        SpendState.ATTEMPTS_EXHAUSTED, runs_used=runs_used, attempts_used=attempts_used
    )


def spend_one_run(
    session: Session,
    guest_id: str | uuid.UUID,
    *,
    cap: int = FREE_RUN_ALLOWANCE,
    attempt_cap: int = ATTEMPT_ALLOWANCE,
) -> SpendResult:
    """Spend one run against `guest_id`'s allowance, atomically.

    The spend and both cap checks happen in a single conditional
    `UPDATE ... RETURNING` (design decision 3): a row comes back only when
    the session is not revoked, its pre-update `runs_used` was still under
    `cap`, and its pre-update `attempts_used` was still under
    `attempt_cap`. When no row comes back, a read-only lookup classifies
    WHY for an honest caller-facing message; that lookup runs strictly
    after the write decision is already final and never gates it, so it
    cannot reintroduce the read-then-write race this function exists to
    avoid.

    THE TWO COUNTERS ARE ASYMMETRIC, and that asymmetry is the whole of the
    F-4.10-R-01 fix. Both advance here, on every run this identity starts.
    Only `runs_used` is ever given back (`refund_one_run` below); the
    attempt is permanent. So a guardrail refusal still costs the caller
    nothing they can feel, and still costs them one of their finite chances
    to make the system do work.

    Args:
        session: a session scoped to this one operation; this function
            commits it.
        guest_id: the guest session id, as a string (typically straight
            off a decoded guest token's `guest_id` claim) or a `uuid.UUID`.
        cap: the ANSWER allowance ceiling. Defaults to FREE_RUN_ALLOWANCE.
        attempt_cap: the ATTEMPT ceiling, counting every run started
            whatever its outcome. Defaults to ATTEMPT_ALLOWANCE.

    Returns:
        A SpendResult: SPENT with the new counts, EXHAUSTED or
        ATTEMPTS_EXHAUSTED with the counts at refusal, or
        REVOKED_OR_UNKNOWN with no counts.

    Raises:
        TypeError: If guest_id is not a str or uuid.UUID, if cap or
            attempt_cap is not an int, or if session is not a Session.
        ValueError: If guest_id is an empty or malformed string, or cap or
            attempt_cap is not a positive integer.
    """
    if not isinstance(session, Session):
        raise TypeError("session must be a sqlalchemy.orm.Session")
    guest_uuid = _coerce_guest_id(guest_id)
    validated_cap = _validate_cap(cap)
    validated_attempt_cap = _validate_cap(attempt_cap)

    result = _apply_spend(
        session, guest_uuid, cap=validated_cap, attempt_cap=validated_attempt_cap
    )
    session.commit()
    return result


# The system-wide daily spend, design decision 8. An upsert rather than an
# UPDATE, because the first anonymous run of a UTC day has no row yet, and
# a SELECT-then-INSERT would race two callers into two INSERTs and a
# primary-key violation. `ON CONFLICT ... DO UPDATE ... WHERE` keeps the
# whole decision inside one statement: Postgres takes the row lock, the
# second caller re-evaluates the WHERE against what the first just wrote,
# and RETURNING yields a row only when the write actually happened. That is
# the same property `_SPEND_STATEMENT` above relies on, one level up.
#
# The INSERT arm has no cap check and does not need one: `anon_daily_run_cap`
# is read through `_read_int_env`, which rejects zero and negatives, so the
# first run of a day is always within a valid cap.
_DAILY_SPEND_STATEMENT = text(
    "INSERT INTO guest_daily_usage (day, runs_used) VALUES (:day, 1)"
    " ON CONFLICT (day) DO UPDATE"
    "    SET runs_used = guest_daily_usage.runs_used + 1"
    "  WHERE guest_daily_usage.runs_used < :daily_cap"
    " RETURNING runs_used"
)

# The ANSWER refund, used by `refund_one_run` when a run that WAS admitted
# turns out to produce nothing (a guardrail refusal, F-4.10-A-04).
# Conditional on `runs_used > 0` so it can never drive the count negative and
# trip the table's CHECK constraint, whatever else touched the row in
# between.
#
# `attempts_used` IS DELIBERATELY ABSENT FROM THIS STATEMENT, and its absence
# is the F-4.10-R-01 fix rather than an omission. Give the attempt back and
# the caller is unbounded again: they never advance a counter that stops
# them, so they can start runs until the SHARED daily budget is gone, which
# is what took the anonymous product offline in 1.68 seconds. The answer is
# refunded because a visitor should not be punished for one clumsy question;
# the attempt is not, because the system must still be able to say "enough".
_UNSPEND_STATEMENT = text(
    "UPDATE guest_sessions SET runs_used = runs_used - 1"
    " WHERE id = :guest_id AND runs_used > 0"
    " RETURNING runs_used"
)

# The SHARED daily refund (F-4.10-R-01 part B). Same `> 0` guard as the
# statement above, for the same reason: the row's CHECK constraint must be
# unreachable no matter what else touched it in between.
_DAILY_UNSPEND_STATEMENT = text(
    "UPDATE guest_daily_usage SET runs_used = runs_used - 1"
    " WHERE day = :day AND runs_used > 0"
    " RETURNING runs_used"
)


def refund_one_run(
    session: Session,
    guest_id: str | uuid.UUID,
    *,
    daily_day: date | None = None,
) -> bool:
    """Give one ANSWER back to `guest_id`, and never an attempt.

    F-4.10-A-04, product-owner decision 2026-08-15: a guardrail refusal must
    not cost a visitor one of their five free searches. A first-time visitor
    who asks five off-topic questions would otherwise meet the sign-in wall
    having never received a single answer.

    F-4.10-R-01, product-owner decision the same day, is the correction that
    made the first decision safe, and it has two halves.

    The first half is what this statement does NOT touch: `attempts_used`.
    The original refund gave back the only counter a refusable-text caller
    ever advanced, which removed the per-identity bound entirely. Measured:
    one guest token, minted once, started 200 paid pipelines in 1.68 seconds
    with its own allowance still reading `used: 0` and drained the whole
    day's anonymous budget for everyone else. The attempt is permanent, so
    that caller now stops at ATTEMPT_ALLOWANCE.

    The second half is `daily_day`. `guest_daily_usage` is the SHARED
    ceiling, and charging it for a refusal that cost nothing is what made
    the drain cheap. Pass `daily_day` when, and only when, the refused run
    made NO model call: a pre-filter refusal returns before the Guard tier
    is ever dispatched (`core/graph.py`'s `_decline_for_guardrail(...,
    charged=False)`), so the day's budget was charged for zero dollars of
    work. Leave it `None` for a refusal that came AFTER a real Guard-tier
    call: that run genuinely spent money, the day's budget is what bounds
    money, and refunding it would reopen the free-compute path the original
    decision was written to avoid.

    The day is passed in rather than computed here so the refund lands on
    the day the run was actually CHARGED. A run refused a few seconds after
    UTC midnight would otherwise decrement the new day's row, taking a slot
    from the day that never charged it.

    Both statements run in ONE transaction, for design decision 8's
    constraint 1 reason applied to the reverse direction: an answer given
    back while the day's refund failed would leave the two counters
    disagreeing with no compensation path.

    Idempotent in the sense `production-standards`' retry-safety gate needs:
    the caller fires it at most once per run (see `core/run_registry.py`), and
    a call against a row already at zero matches nothing and returns False
    rather than driving the count negative.

    Not conditional on `revoked_at IS NULL`, deliberately. A session revoked
    by migration between the spend and the refusal can never spend again, so
    decrementing it changes nothing observable; adding the predicate would
    only create a second definition of "live" for the reporting path and the
    enforcement path to disagree about, which is the F-4.10-A-03 shape.

    Args:
        session: a session scoped to this one operation; this function
            commits it.
        guest_id: the guest session id, string or UUID.
        daily_day: the UTC calendar day whose SHARED anonymous budget should
            also be given back, or None to leave it charged. Pass a day only
            for a refusal that made no model call.

    Returns:
        True when an answer was actually given back, False when there was
        nothing to give back (no row, or the count was already zero). The
        daily refund is not reflected in this value: it is a different
        counter with a different meaning, and a caller that treats "the day
        was already at zero" as "the visitor was not refunded" would be
        reading one fact off another.

    Raises:
        TypeError: If guest_id is not a str or uuid.UUID, if daily_day is
            not a date, or session is not a Session.
        ValueError: If guest_id is an empty or malformed string.
    """
    if not isinstance(session, Session):
        raise TypeError("session must be a sqlalchemy.orm.Session")
    if daily_day is not None and not isinstance(daily_day, date):
        raise TypeError("daily_day must be a datetime.date or None")
    guest_uuid = _coerce_guest_id(guest_id)
    refunded_row = session.execute(_UNSPEND_STATEMENT, {"guest_id": guest_uuid}).first()
    if daily_day is not None:
        session.execute(_DAILY_UNSPEND_STATEMENT, {"day": daily_day})
    session.commit()
    return refunded_row is not None


def spend_one_anonymous_run(
    session: Session,
    guest_id: str | uuid.UUID,
    *,
    cap: int = FREE_RUN_ALLOWANCE,
    attempt_cap: int = ATTEMPT_ALLOWANCE,
    daily_cap: int,
) -> SpendResult:
    """Spend one anonymous run against ALL THREE bounds, in ONE transaction.

    This is what the query endpoint calls. `spend_one_run` above is the
    per-guest primitive and is NOT sufficient on its own for the production
    path: it bounds a guest identity, and `POST /auth/guest` mints those for
    free, so alone it bounds a variable the caller controls the supply of.
    The build phase 4.10 adversary round accepted 40 paid pipelines in 0.25
    seconds against exactly that gap (F-4.10-A-01).

    ONE TRANSACTION, which is design decision 8's constraint 1 stated
    verbatim: "The two spends, per-guest and per-day, happen in ONE
    transaction. A per-guest spend that commits while the daily spend fails
    charges a visitor for a run they never got." F-4.10-R-03 measured the
    shipped code violating exactly that: `spend_one_run` committed its own
    increment first, and making the daily statement raise left the guest
    charged AND returned a 500. Nothing commits here until both statements
    have succeeded, so a failure of either leaves the caller charged for
    nothing.

    The per-guest spend still runs FIRST inside that transaction, and the
    ordering argument is unchanged:

    - Per-guest first: a daily refusal rolls back an increment that was
      never charged to anyone, leaving the guest's own count untouched.
    - Daily first: a per-guest refusal would leave the SYSTEM-WIDE counter
      advanced by a run nobody was allowed to start, so a caller whose own
      allowance is spent could still burn down the day's budget for
      everyone else just by retrying. That is a denial of service handed
      out for free.

    What changed with the transaction is HOW the daily refusal reverses the
    per-guest spend: a `ROLLBACK`, not a compensating UPDATE. The
    compensating statement could only cover the refusal case, which is why
    a raising daily statement escaped it. A rollback covers every way the
    second statement can fail, including a raise and a lost connection,
    because nothing was ever committed to compensate for.

    Lock ordering is always guest row then daily row, in every caller, so
    two concurrent spends cannot deadlock on each other.

    `daily_cap` is keyword-only and has NO default, so the system-wide bound
    cannot be omitted by accident. Passing it is a decision written down at
    the call site.

    Args:
        session: a session scoped to this one operation; this function
            commits or rolls it back.
        guest_id: the guest session id, string or UUID.
        cap: this guest's own ANSWER allowance ceiling.
        attempt_cap: this guest's ATTEMPT ceiling (F-4.10-R-01).
        daily_cap: the system-wide ceiling on anonymous runs for the current
            UTC day, from `harness.cost_control.anon_daily_run_cap`.

    Returns:
        A SpendResult. SPENT carries the guest's new counts. EXHAUSTED,
        ATTEMPTS_EXHAUSTED, REVOKED_OR_UNKNOWN and DAILY_CAP_REACHED are all
        refusals, kept distinct because they mean different things to the
        caller.

    Raises:
        TypeError, ValueError: as `spend_one_run`, plus for a `daily_cap`
            that is not a positive int.
    """
    if not isinstance(session, Session):
        raise TypeError("session must be a sqlalchemy.orm.Session")
    guest_uuid = _coerce_guest_id(guest_id)
    validated_cap = _validate_cap(cap)
    validated_attempt_cap = _validate_cap(attempt_cap)
    validated_daily_cap = _validate_cap(daily_cap)

    guest_result = _apply_spend(
        session, guest_uuid, cap=validated_cap, attempt_cap=validated_attempt_cap
    )
    if guest_result.state is not SpendState.SPENT:
        # Nothing was written (the conditional UPDATE matched no row), so
        # there is nothing to commit. Rolling back rather than committing
        # ends the transaction without asserting that a write happened.
        session.rollback()
        return guest_result

    # UTC, never the server's local date. A ceiling that resets at an
    # operator's midnight is a ceiling whose window moves with a
    # deployment's timezone, and two hosts in different zones would
    # disagree about which day a run belongs to.
    today = datetime.now(UTC).date()
    daily_row = session.execute(
        _DAILY_SPEND_STATEMENT, {"day": today, "daily_cap": validated_daily_cap}
    ).first()
    if daily_row is None:
        session.rollback()
        return SpendResult(SpendState.DAILY_CAP_REACHED)
    session.commit()
    return guest_result
