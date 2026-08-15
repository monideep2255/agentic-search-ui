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
      call, one conditional UPDATE per `spend_one_run` call. Both commit
      the session they are given, matching how `auth/router.py` manages
      its own session's transaction boundary directly rather than through
      a shared repository-commit helper; callers pass a session scoped to
      one operation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
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


class SpendState(str, Enum):
    """The three outcomes `spend_one_run` can report.

    Never a bare bool: a caller needs to distinguish "no allowance left"
    (the 403 `guest_allowance_exhausted` design decision 5 calls for) from
    "this id no longer identifies a spendable session" (revoked by
    migration, or never existed), and a bool collapses both to False.
    """

    SPENT = "spent"
    EXHAUSTED = "exhausted"
    REVOKED_OR_UNKNOWN = "revoked_or_unknown"


@dataclass(frozen=True)
class SpendResult:
    """The outcome of one `spend_one_run` call.

    `runs_used` is populated on SPENT (the new count, straight off the
    UPDATE's own `RETURNING` clause) and on EXHAUSTED (the count at the
    moment of refusal, so a caller can report it honestly); it is None on
    REVOKED_OR_UNKNOWN, where there is no live count to report.
    """

    state: SpendState
    runs_used: int | None = None


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


# The single conditional spend statement design decision 3 specifies
# verbatim. `runs_used < :cap` is evaluated against the PRE-update row, so
# Postgres's own row-level lock on the UPDATE is what makes two concurrent
# callers racing this statement unable to both push the count past `cap`:
# the second waits for the first's transaction to commit, then re-evaluates
# this WHERE clause against the row the first just wrote.
_SPEND_STATEMENT = text(
    "UPDATE guest_sessions"
    "   SET runs_used = runs_used + 1, last_seen_at = now()"
    " WHERE id = :guest_id AND revoked_at IS NULL AND runs_used < :cap"
    " RETURNING runs_used"
)


def spend_one_run(
    session: Session,
    guest_id: str | uuid.UUID,
    *,
    cap: int = FREE_RUN_ALLOWANCE,
) -> SpendResult:
    """Spend one run against `guest_id`'s allowance, atomically.

    The spend and the cap check happen in a single conditional
    `UPDATE ... RETURNING` (design decision 3): a row comes back only when
    the session is not revoked and its pre-update `runs_used` was still
    under `cap`. When no row comes back, a read-only lookup classifies WHY
    for an honest caller-facing message; that lookup runs strictly after
    the write decision is already final and never gates it, so it cannot
    reintroduce the read-then-write race this function exists to avoid.

    Args:
        session: a session scoped to this one operation; this function
            commits it.
        guest_id: the guest session id, as a string (typically straight
            off a decoded guest token's `guest_id` claim) or a `uuid.UUID`.
        cap: the allowance ceiling. Defaults to FREE_RUN_ALLOWANCE.

    Returns:
        A SpendResult: SPENT with the new count, EXHAUSTED with the count
        at refusal, or REVOKED_OR_UNKNOWN with no count.

    Raises:
        TypeError: If guest_id is not a str or uuid.UUID, if cap is not an
            int, or if session is not a Session.
        ValueError: If guest_id is an empty or malformed string, or cap is
            not a positive integer.
    """
    if not isinstance(session, Session):
        raise TypeError("session must be a sqlalchemy.orm.Session")
    guest_uuid = _coerce_guest_id(guest_id)
    validated_cap = _validate_cap(cap)

    spent_row = session.execute(
        _SPEND_STATEMENT, {"guest_id": guest_uuid, "cap": validated_cap}
    ).first()
    if spent_row is not None:
        session.commit()
        return SpendResult(SpendState.SPENT, runs_used=int(spent_row[0]))

    lookup_row = session.execute(
        select(GuestSession.revoked_at, GuestSession.runs_used).where(
            GuestSession.id == guest_uuid
        )
    ).first()
    session.commit()
    if lookup_row is None or lookup_row[0] is not None:
        return SpendResult(SpendState.REVOKED_OR_UNKNOWN)
    return SpendResult(SpendState.EXHAUSTED, runs_used=int(lookup_row[1]))
