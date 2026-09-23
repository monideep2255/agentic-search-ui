"""T-4.13-01: the owner-scoped read path over `interactions` (`tracker/phase_4.13.md`).

Depends on:
    - system_03_search_agent.data.models (Interaction)
    - system_03_search_agent.data.session (session_scope)

Reads:
    - The `interactions` table (Section 15), scoped to one caller's own
      `owner_id`.

Writes:
    - `interactions.answer_markdown`, `interactions.audience_depth` and
      `interactions.answer_trust_line`, set to NULL, and ONLY by
      `forget_saved_answers_for_account`.

      This line used to read "Nothing. This module is read-only", and it was
      replaced in the same change that made it false rather than left to be
      trusted by the next reader. `list_history` and `get_saved_answer` are
      still read-only, and every other statement in this file about
      ownership and about never mutating a row still holds: the one writer
      here clears a saved answer and never touches a row's identity,
      question, citations, cost or latency.

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
from typing import Any
from uuid import UUID

from sqlalchemy import select, update

from system_03_search_agent.data.models import Interaction
from system_03_search_agent.data.session import session_scope

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "HistoryEntry",
    "SavedAnswer",
    "forget_saved_answers_for_account",
    "get_saved_answer",
    "list_history",
]

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

#: Mirrors `feedback.contracts.InteractionRow.trace_id`'s own bound
#: (`max_length=64`), for the same reason `_MAX_OWNER_ID_LENGTH` mirrors
#: `owner_id`'s: a real stored `trace_id` cannot exceed the width the write
#: path enforces, so anything longer is refused before a query is built.
_MAX_TRACE_ID_LENGTH = 64


@dataclass(frozen=True)
class HistoryEntry:
    """One row of a caller's own history, exactly what `GET /v1/history` renders.

    No answer narrative HERE, and the reason changed on 2026-09-23. This
    paragraph used to say `interactions` stores no answer at all (decision
    D-4.13-01, `tracker/phase_4.13.md`), and that became false when alembic
    0010 added `answer_markdown` for fix-plan item 10.2. It is rewritten
    rather than left standing, because a confident sentence is where the
    next reader stops checking.

    The table now stores an answer for a signed-in account's answered runs.
    This type still carries none, by a different and narrower argument: a
    page of history is a list of what you asked, and dragging up to fifty
    answers across the wire to render a list of questions would make the
    rail slower for everyone to serve a row nobody clicked. `has_saved_
    answer` below is the one boolean that list needs; `get_saved_answer`
    fetches the answer itself, once, when a person actually opens one.
    `citation_count` is a count rather than the citations for the same
    reason it always was.

    `citation_count` is `None`, never a guess, when the row's stored
    `citations` value is not the list this table's Python type declares.
    See `_citation_count` below for why that is reachable at all, and
    `adapters/web_sse/app.py`'s history handler for what it does with an
    unknown count (it drops the row and discloses the drop; it never
    publishes a number nothing computed).
    """

    trace_id: str
    question: str
    asked_at: datetime
    trust_signal: str
    citation_count: int | None
    #: Whether this row holds the answer it gave, so the rail can offer to
    #: open it instead of re-asking (fix-plan item 10.2). Computed in SQL as
    #: `answer_markdown IS NOT NULL`, so listing a page of history never
    #: fetches a single character of answer text. False is the ordinary case
    #: and carries no fault: a guest's row, a refusal, a row from before the
    #: column existed, or an answer over the stored bound.
    has_saved_answer: bool = False


def _citation_count(stored: object) -> int | None:
    """How many citations a stored `interactions.citations` value holds, or
    `None` when that cannot be answered from what is actually stored.

    F-4.13-RV-02. This used to be `len(row.citations or [])` inline, and
    that single expression carried an assumption the DATABASE does not
    enforce. `Interaction.citations` is annotated `Mapped[list[Any]]`, but
    the column is `JSONB NOT NULL DEFAULT '[]'::jsonb` (alembic 0001) with
    no check constraint, and JSONB accepts any JSON value: an object, a
    string, a number, a boolean, or the JSON literal `null`. The annotation
    is a statement of intent about the write path, not a guarantee about
    what a read gets back.

    Two failure shapes were measured against the real database, both from
    one row sitting beside well-formed ones:

    - a JSONB scalar (`5`, `true`) raised `TypeError: object of type 'int'
      has no len()` out of `list_history`, one layer ABOVE the handler's
      per-row guard, so the caller's ENTIRE history returned 500. That is
      precisely the outcome F-4.13-A-02 was filed for, reached by the one
      route A-02's fix did not cover.
    - a JSONB string (`"abc"`) is quieter and worse: `len` succeeds and
      reports `citation_count: 3` with `omitted_count: 0`, a source count
      nothing counted, published as complete.

    So this returns a count only when it actually counted something, and
    `None` otherwise, per the rule this repository settled in F-3.3-J-04
    (2026-08-15): if the system drops or shortens anything, it discloses
    that it did, and it never substitutes a fabricated value for a missing
    one. The JSON literal `null` reads back as Python `None` and is
    UNREADABLE rather than zero: "no citations recorded" and "this row does
    not say" are different claims, and only the first one may be shown to a
    reader as a count of sources.

    ## The class this belongs to, not just this field

    The general rule, stated here because the instance is one line and the
    rule is the part worth keeping: a value read back OUT of the database
    is untrusted input, exactly like a value arriving over HTTP, and no
    computation may be performed on one before its type is checked. This
    module reads five columns, and only this one needed a guard, because
    the other four are enforced by their own column types (`trace_id`,
    `query_text` and `trust_signal` are `TEXT NOT NULL`, `created_at` is
    `timestamptz NOT NULL`) and are passed onward untouched for the
    response model to judge, which it already does. `citations` was the
    only one this module computed over.

    Swept for siblings rather than assumed unique: `interactions` has four
    other JSONB columns (`normalized_entities`, `route`, `user_feedback`,
    plus `sessions.memory`), and nothing else in `src/` computes over a
    stored value of any of them on the way out. `feedback/writer.py` reads
    those attributes only to copy an already-validated `InteractionRow`
    INTO the database, and `core/session_memory.py`'s `_unwrap` already
    applies exactly this posture to `sessions.memory`, which is where the
    posture was taken from rather than invented here.

    The invariant this preserves for the whole module: `list_history` never
    raises because of what a stored row CONTAINS. It raises only on its own
    arguments. Anything it cannot read honestly is handed onward in a form
    the single downstream guard can judge, so exactly one place decides
    what a bad row costs the caller.
    """
    if isinstance(stored, list):
        return len(stored)
    return None


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
                # A boolean computed by the database, never the text itself:
                # a page of twenty rows must not drag twenty saved answers
                # across the wire to answer a yes/no question about each.
                Interaction.answer_markdown.isnot(None).label("has_saved_answer"),
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
            citation_count=_citation_count(row.citations),
            has_saved_answer=bool(row.has_saved_answer),
        )
        for row in rows
    ]


@dataclass(frozen=True)
class SavedAnswer:
    """The answer one past search gave, exactly as it stood on screen.

    Fix-plan item 10.2. What the person gets: they click a past search and
    the answer they already got is there at once, with no second search
    charged to them.

    `citations` is the row's stored `citations` column, which build phase
    4.6 has been writing since it shipped: the full `CitationPayload` dicts,
    the same shape the answer screen already renders. No new column was
    needed for the citation half of this feature, and inventing one would
    have stored the same facts twice.
    """

    trace_id: str
    question: str
    asked_at: datetime
    depth: str
    answer_markdown: str
    citations: list[Any]
    trust_signal: str
    #: The one plain sentence the person read under their answer. Carried on
    #: this type and NOT on the HTTP response, because the pinned wire
    #: contract has no field for it; see alembic 0010's docstring. A caller
    #: of this module directly gets the fact; the endpoint does not publish
    #: it until the product owner says so.
    trust_line: str | None = None


def get_saved_answer(owner_id: str, trace_id: str) -> SavedAnswer | None:
    """One of the caller's own saved answers, or None.

    ONE None FOR THREE CAUSES, and that is the design rather than a
    shortcut. This returns None when the row does not exist, when it exists
    and belongs to somebody else, and when it exists, is the caller's, and
    holds no saved answer. The surface turns all three into the same 404,
    because any answer that distinguished them would confirm to a stranger
    that a given `trace_id` exists and belongs to someone. A 403 on another
    person's row is exactly that confirmation.

    The ownership rule is `list_history`'s, unchanged and for the same
    reasons: one direct `owner_id` comparison at the SQL boundary, never
    `user_id` (NULL for every guest), never `session_id`, never anything
    derived. A row with a NULL `owner_id` can never match a real caller's
    non-empty string, by SQL's own NULL semantics.

    `answer_markdown IS NOT NULL` is part of the WHERE clause rather than a
    Python check afterwards, so a row with no saved answer is never fetched
    and there is one shape of result to reason about instead of two.
    """
    if not owner_id:
        raise ValueError("owner_id must not be empty")
    if len(owner_id) > _MAX_OWNER_ID_LENGTH:
        raise ValueError(
            f"owner_id is capped at {_MAX_OWNER_ID_LENGTH} characters, got {len(owner_id)}"
        )
    if not trace_id:
        raise ValueError("trace_id must not be empty")
    if len(trace_id) > _MAX_TRACE_ID_LENGTH:
        raise ValueError(
            f"trace_id is capped at {_MAX_TRACE_ID_LENGTH} characters, got {len(trace_id)}"
        )

    with session_scope() as session:
        row = session.execute(
            select(
                Interaction.trace_id,
                Interaction.query_text,
                Interaction.created_at,
                Interaction.trust_signal,
                Interaction.citations,
                Interaction.answer_markdown,
                Interaction.audience_depth,
                Interaction.answer_trust_line,
            ).where(
                Interaction.owner_id == owner_id,
                Interaction.trace_id == trace_id,
                Interaction.answer_markdown.isnot(None),
            )
        ).first()

    if row is None:
        return None
    return SavedAnswer(
        trace_id=row.trace_id,
        question=row.query_text,
        asked_at=row.created_at,
        # A saved answer always records its own depth: `InteractionRow`
        # refuses to hold one without the other and the database repeats the
        # rule. `"researcher"` is the floor for a row written directly into
        # the database around both, and it is the product's own default
        # rather than an invented value.
        depth=row.audience_depth or "researcher",
        answer_markdown=row.answer_markdown,
        citations=row.citations if isinstance(row.citations, list) else [],
        trust_signal=row.trust_signal,
        trust_line=row.answer_trust_line,
    )


def forget_saved_answers_for_account(user_id: UUID) -> int:
    """Clear every saved answer belonging to one account. Returns the count.

    THIS FUNCTION IS CALLED BY NOTHING TODAY, and that is stated here rather
    than implied, because a confident sentence describing a wiring that does
    not exist is the failure this repository has shipped four times.

    The product owner's decision of 2026-09-22 was: store the answer for
    signed-in accounts only, and delete it with the account. The first half
    is enforced at the write. The second half cannot be proven end to end,
    because THERE IS NO ACCOUNT DELETE PATH: no route under `adapters/` or
    `auth/` declares a DELETE verb and no code anywhere under `src/` deletes
    a `User` row (searched 2026-09-22, recorded in
    `testing/Developer/reports/2026-09-23_overnight/findings.md`). Worse,
    the existing foreign key would not deliver it either:
    `interactions.user_id` is `ON DELETE SET NULL`, so deleting the account
    row leaves its interactions behind with a null user and the link back to
    the account gone.

    So this exists, tested, so that a future delete path cannot ship without
    it. WHAT THAT PATH MUST DO, in one line: call this function inside the
    same transaction that deletes the user, BEFORE the user row goes, since
    `ON DELETE SET NULL` destroys the only link the moment it does.

    `audience_depth` is cleared alongside the answer, because a depth with
    no answer is a fact about a person's reading preference with nothing
    left to attach it to, and `InteractionRow` refuses that pairing anyway.
    The row itself is KEPT: it carries the cost and latency the daily caps
    and the weekly review ritual count, and this function's job is to forget
    the answer, not to rewrite the record that a query happened.
    """
    with session_scope() as session:
        result = session.execute(
            update(Interaction)
            .where(
                Interaction.user_id == user_id,
                Interaction.answer_markdown.isnot(None),
            )
            .values(answer_markdown=None, audience_depth=None, answer_trust_line=None)
        )
    return int(result.rowcount or 0)
