"""T-4.13-01: the owner-scoped read path over `interactions` (`tracker/phase_4.13.md`).

Depends on:
    - system_03_search_agent.data.models (Interaction)
    - system_03_search_agent.data.session (session_scope)

Reads:
    - The `interactions` table (Section 15), scoped to one caller's own
      `owner_id`.

Writes:
    - Nothing. This module is read-only.

## Ownership: the same posture as `feedback/writer.py`

`_caller_owns_row` there is the model this module copies: one direct
`row.owner_id == owner_id` compare, deny-by-default on a row with no
recorded owner. `list_history` below applies the identical rule at the SQL
boundary rather than in Python, filtering on `Interaction.owner_id ==
owner_id` and nothing else. Never `user_id` (NULL for every guest, the
exact shape that made every guest one principal in build phase 4.5,
F-4.5-A-02), never `session_id`, never a value derived or "equivalent" to
the caller's own `owner_id`.

A row whose `owner_id` IS NULL (the pre-alembic-0008 shape, still
permitted by the table though no live write path produces it any more) can
never match a real caller's non-empty `owner_id` string: SQL's own NULL
semantics already make `NULL = 'guest:...'` evaluate to NULL rather than
TRUE, so the `WHERE` clause excludes such a row with no extra `IS NOT
NULL` guard needed. Stated explicitly here, once, so the next reader does
not have to re-derive it from `_caller_owns_row`'s equivalent comment.

## Why this module opens its own session rather than taking one

`feedback/writer.py`'s functions (`write_interaction`, `write_feedback`,
`reassign_interaction_owner`) are each self-contained: they open a
`session_scope()` of their own rather than accepting a caller-supplied
`Session`. This module matches that precedent rather than the FastAPI
dependency-injection shape `adapters/web_sse/app.py`'s other GET handlers
use, so `list_history` stays a plain, directly callable function with the
exact two-argument shape (`owner_id`, `limit`) this ticket names, testable
with no FastAPI request context at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from system_03_search_agent.data.models import Interaction
from system_03_search_agent.data.session import session_scope

__all__ = ["DEFAULT_LIMIT", "MAX_LIMIT", "HistoryEntry", "list_history"]

#: T-4.13-02's contract: `limit` defaults to 20. Restated here, not
#: imported from the endpoint module, so this function's own contract does
#: not depend on an adapter importing it correctly, and a caller of this
#: module directly (a script, a future non-HTTP surface) gets the same
#: default the endpoint does.
DEFAULT_LIMIT = 20

#: T-4.13-02's contract: a `limit` above this is refused, never silently
#: clamped (`tool-call-budgets`: an error must say what to do next, not
#: quietly do something else).
MAX_LIMIT = 50

#: Mirrors `feedback.contracts.InteractionRow.owner_id`'s own bound
#: (`max_length=128`): a caller's real `owner_id` can never legitimately
#: exceed the width the write path already enforces at capture time, so
#: anything longer is refused here, cheaply and deterministically, before a
#: query is even built rather than after a round trip to the database.
_MAX_OWNER_ID_LENGTH = 128


@dataclass(frozen=True)
class HistoryEntry:
    """One row of a caller's own history, exactly what `GET /v1/history` renders.

    No answer narrative: `interactions` stores none
    (`feedback/contracts.py`'s `InteractionRow`), and decision D-4.13-01
    (`tracker/phase_4.13.md`) is why this type does not invent one.
    `citation_count` is a count, not the citations themselves, for the same
    reason.
    """

    trace_id: str
    question: str
    asked_at: datetime
    trust_signal: str
    citation_count: int


def list_history(owner_id: str, limit: int = DEFAULT_LIMIT) -> list[HistoryEntry]:
    """The caller's own past questions, newest first, in a total order.

    Refuses, by raising `ValueError`, rather than issuing a query, when
    `owner_id` is empty or longer than `_MAX_OWNER_ID_LENGTH`, or when
    `limit` is outside `[1, MAX_LIMIT]`. The endpoint (T-4.13-02) validates
    `limit` before this function is ever called (`FastAPIQuery(ge=1,
    le=MAX_LIMIT)`), so the bound here is defense in depth for any other
    caller of this module, not the caller-facing refusal itself; the
    caller-facing 422 and its actionable message live in the endpoint.

    Ordering is `created_at DESC, id DESC`, a TOTAL order rather than
    `created_at` alone: `created_at` carries a server default
    (`now()`), so two rows written inside the same clock tick can share a
    timestamp, and an `ORDER BY` on that column alone would then return
    them in a database-chosen, not caller-visible, order. `id` (a
    `gen_random_uuid()` primary key) breaks every tie deterministically.

    F-4.13-J-01's correction: this docstring used to point at the premise
    gate's `test_the_list_is_newest_first_and_the_order_is_total` clause as
    the proof of that property. That arm was renamed to
    `test_the_list_reads_newest_first` by commit `ebb62f4` and F-4.13-01 is
    the record of WHY: no black-box call through `GET /v1/history` can
    force two rows onto one shared timestamp, so that clause never reaches
    the tie the `id` tiebreaker exists for and cannot prove the total order
    holds (measured 10 of 10 green under mutation with the tiebreaker
    dropped, before the correction). The total order IS proven, in
    `tests/system_03_search_agent/feedback/test_history.py::test_order_
    is_total_when_created_at_collides`, which forces six rows onto one
    explicit timestamp, a shape only reachable below this HTTP endpoint.

    The `LIMIT` is a real SQL `LIMIT` clause, applied by the database,
    never a Python-side slice of a larger fetched result: slicing in
    Python would still pay the cost, and the query time, of fetching every
    row a caller has ever asked, for a response that only ever shows the
    newest page of them. F-4.13-J-03: this is a STATIC property of the
    `.limit(limit)` call below, verified by reading this function and by
    `ruff`, not a claim any black-box call through `list_history` can
    prove at runtime; `tests/system_03_search_agent/feedback/
    test_history.py`'s own coverage statement says the same.
    """
    if not owner_id:
        raise ValueError("owner_id must not be empty")
    if len(owner_id) > _MAX_OWNER_ID_LENGTH:
        raise ValueError(
            f"owner_id is capped at {_MAX_OWNER_ID_LENGTH} characters, got {len(owner_id)}"
        )
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if limit > MAX_LIMIT:
        raise ValueError(f"limit is capped at {MAX_LIMIT}, got {limit}")

    with session_scope() as session:
        rows = session.execute(
            select(
                Interaction.trace_id,
                Interaction.query_text,
                Interaction.created_at,
                Interaction.trust_signal,
                Interaction.citations,
            )
            .where(Interaction.owner_id == owner_id)
            .order_by(Interaction.created_at.desc(), Interaction.id.desc())
            .limit(limit)
        ).all()

    return [
        HistoryEntry(
            trace_id=row.trace_id,
            question=row.query_text,
            asked_at=row.created_at,
            trust_signal=row.trust_signal,
            citation_count=len(row.citations or []),
        )
        for row in rows
    ]
