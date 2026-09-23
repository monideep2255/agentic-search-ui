"""T-4.6-06: the one place an `interactions` row reaches the database.

Depends on:
    - system_03_search_agent.feedback.contracts (InteractionRow, FeedbackPayload,
      FeedbackOwnershipError, InteractionNotFound; fixed, not owned here)
    - system_03_search_agent.data.models (Interaction, ChatSession, User)
    - system_03_search_agent.data.session (session_scope)

Reads:
    - The `interactions` and `sessions` tables (Section 15).

Writes:
    - The `interactions` table, always idempotently (`ON CONFLICT (trace_id)
      DO NOTHING`), including the `owner_id` column (alembic 0008).
    - The `sessions` table, only to create a row that does not exist yet,
      and only its `id` and `user_id` columns. Never its `memory` column:
      that column belongs to `core.session_memory`, and this module has
      nothing to do with it now that ownership no longer reads it (see
      "Ownership" below).
    - The `interactions.owner_id` and `interactions.user_id` columns of
      rows already written, and only through `reassign_interaction_owner`,
      the durable half of the guest-to-account migration (F-4.6-J-01).

## What capture owes when it cannot happen

Section 16 makes this write best-effort and F-2.0-04 made the two daily
caps count what it writes. Composed, any condition that prevents a row
raises that caller's cap to infinity, which is how one NUL byte in a
question bought unlimited free queries (F-4.6-A-01). The reconciliation is
in `_minimal_interaction_values`' docstring and it is the principle the
whole module now follows: a failure a caller's own input can cause degrades
the row's CONTENT, never its existence; a failure nobody controls (the
database is unreachable) may still lose the row, exactly as Section 16
permits, because it cannot be selected for.

## Best-effort by construction (Section 16 stage 1)

`write_interaction` never raises. A write that fails is retried once, on a
fresh connection (so a broken one is not reused), and if the retry also
fails the row is dropped with a warning that never surfaces to the caller.
Losing a row is an acceptable failure mode; the caller already has their
answer and capture is bookkeeping, never a reason to fail a query a second
time (Section 16's closing paragraph, and `.claude/rules/tool-call-budgets.md`'s
retry-safety gate).

## Ownership: how `write_feedback` answers "is this row yours"

F-4.6-01: this used to be answered by deriving an owner from a proxy, the
`sessions.memory` ownership envelope `core.session_memory` writes lazily on
the first turn that resolves an entity or grounds a finding. A guest whose
turn resolved nothing had no envelope, so ownership was indeterminate and
the check correctly, and uselessly, refused: fail-closed in the right
direction and the wrong outcome, a control that refuses every guest and
destroys the product. That is build phase 4.3's lesson landing a second
time in this repository: a check that asks a proxy for safety instead of
checking the value ships the same shape of critical again.

The fix records the fact instead of deriving it. `InteractionRow.owner_id`
(alembic 0008) is the exact namespaced principal string
(`user:<uuid>` or `guest:<uuid>`) `feedback.capture.assemble_interaction`
already has in hand when it builds a row, the same value it uses to compute
`session_id`. `write_interaction` persists it onto the row it describes, so
every captured row answers its own ownership from the moment it exists,
with no dependency on whether session memory, a different module entirely,
happened to write anything for that session.

`_caller_owns_row` is now one comparison, not two branches: it compares the
row's stored `owner_id` against the caller's claimed `owner_id`, exact
string equality, nothing derived from `user_id` and nothing looked up from
`sessions.memory`. There is no registered-account branch and no guest
branch, because the same column and the same compare answer both: a
`user:<uuid>` owner_id and a `guest:<uuid>` owner_id are just two strings,
and the row already carries whichever one capture recorded.

`owner_id` is NULL only on a row written before this column existed, since
the migration adds it with no backfill. A NULL never matches any caller's
`owner_id`, because a caller's `owner_id` is always a non-empty namespaced
string (`FeedbackOwnershipError` is what a NULL row produces for every
caller, including its own true owner). NULL must not mean "anyone" and must
not mean "unowned and claimable": that is the exact `(None or None) !=
(None or None)` shape that made every guest one principal in build phase
4.5 (F-4.5-A-02), now guarded against on this table the same way.
`core.session_memory`'s own ownership machinery (`session_row_key`,
`_account_uuid`) is used elsewhere in this package, by the assembler that
built `owner_id` in the first place, but this module has no remaining
reason to import it: the check it used to support has been replaced, not
extended.
"""

from __future__ import annotations

import logging
import re
import uuid as uuid_module
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from system_03_search_agent.data.models import ChatSession, Interaction
from system_03_search_agent.data.session import session_scope
from system_03_search_agent.feedback.contracts import (
    FeedbackOwnershipError,
    FeedbackPayload,
    InteractionNotFound,
    InteractionRow,
)

__all__ = [
    "reassign_interaction_owner",
    "write_feedback",
    "write_interaction",
]

logger = logging.getLogger(__name__)

#: Section 16 stage 1: one retry, on a fresh connection, then drop. Not a
#: tunable: a larger number trades a slower background task for a marginally
#: better chance of masking a real outage, and Section 16 asks for exactly
#: one retry, not a backoff policy. This is a TOTAL attempt count (the
#: original try plus one retry), not a retry count, so it is 2, never 1:
#: `range(1, _WRITE_ATTEMPTS + 1)` below runs the body `_WRITE_ATTEMPTS`
#: times, and a value of 1 would mean zero retries ever happen.
_WRITE_ATTEMPTS = 2

#: The code points a Python `str` can hold that a PostgreSQL value cannot.
#: Stated as a CLASS rather than as the one byte an attacker happened to
#: send (F-4.6-A-01 was reproduced with `chr(0)`), because the question the
#: fix has to answer is "what can this column not store", not "what did
#: someone try".
#:
#: The class has exactly two members, and it is closed rather than
#: open-ended:
#:
#: - U+0000, the NUL. `text`, `text[]` and `jsonb` all reject it. psycopg2
#:   raises `ValueError: A string literal cannot contain NUL (0x00)
#:   characters` before the statement is ever sent, and PostgreSQL's own
#:   `jsonb` parser rejects a `\u0000` escape independently of the driver.
#: - U+D800 to U+DFFF, the surrogate code points. A Python `str` may hold a
#:   lone surrogate; UTF-8 cannot encode one, so the driver raises
#:   `UnicodeEncodeError` on the way out. Reachable here only through a
#:   value typed `Any` (a nested string inside `citations`,
#:   `normalized_entities` or `route`), because every top-level string field
#:   on `InteractionRow` is a constrained `str` and Pydantic rejects a lone
#:   surrogate on those. That reachability argument is exactly why the guard
#:   is written against the class instead of against the reachable half of
#:   it: it holds only while every upstream contract stays Pydantic-
#:   validated, and this module must not depend on that staying true.
#:
#: Everything else a `str` can hold, including every control character other
#: than NUL, every bidi override and every astral-plane character, stores
#: fine. Those are a RENDERING problem, not a storage problem, and they
#: belong to whoever prints the column (F-4.6-A-06 owns the review script's
#: terminal), not here. Stripping them here would silently destroy content
#: the review ritual needs.
_UNSTORABLE_CODE_POINTS = re.compile("[\x00\ud800-\udfff]")

#: U+FFFD REPLACEMENT CHARACTER, the Unicode-standard stand-in for a code
#: point that could not be represented. Substituted rather than deleted so
#: the loss is VISIBLE in the stored value: a reviewer reading the row can
#: see something was replaced, and a length-bounded field
#: (`query_text`'s `min_length=1`) cannot be emptied out from under its own
#: contract by a caller who sends nothing else.
_REPLACEMENT_CHARACTER = "\ufffd"


def _storable(value: Any) -> Any:
    """Recursively replace anything a PostgreSQL value cannot hold.

    Applied to the WHOLE row rather than to the one field an attacker was
    measured reaching (`query_text`), because `interactions` stores caller-
    derived strings in five places: `query_text` (`text`), `coverage_tags`
    (`text[]`), and `normalized_entities`, `route`, `citations` and
    `user_feedback` (`jsonb`, whose nested string values are typed `Any` and
    therefore unvalidated). A guard on one field is a guard on one instance;
    this one covers the category, and it covers a field added to
    `InteractionRow` tomorrow for free, because every column value in this
    module passes through here on its way to the database.

    Recurses into dicts and lists, and sanitizes dict KEYS as well as
    values: a `jsonb` object key is as much a string as its value, and
    PostgreSQL rejects a NUL in either.

    Non-string leaves (numbers, booleans, `None`, UUIDs) are returned
    untouched, so this never re-types a value on its way through.
    """
    if isinstance(value, str):
        return _UNSTORABLE_CODE_POINTS.sub(_REPLACEMENT_CHARACTER, value)
    if isinstance(value, dict):
        return {_storable(key): _storable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_storable(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_storable(item) for item in value)
    return value


#: What a degraded row's `query_text` reads, and the `coverage_tags` entry
#: that makes such a row findable. Both are constants rather than an
#: f-string carrying the failure's details, because a reviewer reading this
#: value must never be reading anything derived from the payload that
#: could not be stored in the first place.
PAYLOAD_DROPPED_TEXT = "[capture: this run's payload could not be stored]"
PAYLOAD_DROPPED_TAG = "capture:payload_dropped"


def _interaction_values(row: InteractionRow) -> dict[str, Any]:
    """The column values for one `INSERT`, named explicitly rather than
    spread from `row.model_dump()`.

    Named explicitly so a field `InteractionRow` adds later does not reach
    the database silently just because its name happens to match a column;
    the two are independent contracts (a Pydantic model and a table) that
    should only agree where this function says so.

    Every value leaves through `_storable` (F-4.6-A-01). This is the one
    chokepoint between an assembled row and the database, so sanitizing
    here rather than at each field is what makes the guarantee hold for a
    column added later as well as for the six that exist now.
    """
    return _storable({
        "trace_id": row.trace_id,
        "user_id": row.user_id,
        "session_id": row.session_id,
        "owner_id": row.owner_id,
        "query_text": row.query_text,
        "normalized_entities": row.normalized_entities,
        "query_class": row.query_class,
        "route": row.route,
        "trust_signal": row.trust_signal,
        "rubric_outcome": row.rubric_outcome,
        "rubric_score": row.rubric_score,
        "citations": row.citations,
        "coverage_tags": row.coverage_tags,
        "user_feedback": row.user_feedback,
        "experiment_id": row.experiment_id,
        "experiment_arm": row.experiment_arm,
        "cost_usd": row.cost_usd,
        "latency_ms": row.latency_ms,
        # alembic 0010, fix-plan item 10.2. Named here like every other
        # column, per this function's own rule that a field `InteractionRow`
        # gains must not reach the database just because its name matches.
        # Both are None on every guest row and on every refusal; see
        # `feedback/capture.py`'s `answer_markdown_from` for why.
        "answer_markdown": row.answer_markdown,
        "audience_depth": row.audience_depth,
        "answer_trust_line": row.answer_trust_line,
    })


def _minimal_interaction_values(row: InteractionRow) -> dict[str, Any]:
    """The same row with every payload-carrying column emptied out.

    THE PRINCIPLE THIS ENCODES, stated here because it is the load-bearing
    part of F-4.6-A-01's fix and the `_storable` guard above is only its
    first layer.

    Section 16 makes capture best-effort: "Losing a row is an acceptable
    failure mode; blocking the response is not." F-2.0-04 then made the two
    daily caps count captured rows. Composed, ANY condition that stops a row
    existing raises that caller's cap to infinity, so "best-effort" quietly
    became "a caller who can break the write is unmetered". The two
    statements are each correct and together they are a bypass.

    They are reconciled by splitting capture's failures by WHO CONTROLS
    THEM, not by how severe they are:

    - A failure the caller's own input can cause (any value derived from the
      request: the question text, a resolved entity, a citation, a feedback
      comment) must degrade the row's CONTENT and never its EXISTENCE. A
      caller must never be able to choose whether their query is counted.
    - A failure nobody controls (the user-data database is unreachable) may
      lose the row, exactly as Section 16 permits. It is not selectable by
      an attacker and it fails identically for everyone, so it cannot be
      turned into a bypass.

    `_storable` handles the causes that are known. This function handles the
    ones that are not: after the full row has failed every attempt, one last
    insert carries only the columns the caps and the ownership check need
    (`trace_id`, `owner_id`, `user_id`, `cost_usd`, `latency_ms`, and the
    three constrained classification columns), with every free-text and
    JSON column replaced by a constant. Whatever was wrong with the payload
    is not in this row, whether or not anyone anticipated it.

    `session_id` is dropped. It is the row's one nullable foreign key, so a
    `sessions` row that could not be created is itself a plausible cause of
    the failure this function is reacting to, and the column is a grouping
    aid the review ritual can live without. `user_id` is KEPT, because
    `get_user_daily_query_count` counts on it and dropping it would defeat
    the whole point of writing this row.

    A degraded row is findable rather than silent: `query_text` states
    plainly that the payload could not be stored, and `coverage_tags`
    carries `capture:payload_dropped`, which is a GIN-indexed array the
    weekly review ritual already filters on.
    """
    return _storable({
        "trace_id": row.trace_id,
        "user_id": row.user_id,
        "session_id": None,
        "owner_id": row.owner_id,
        "query_text": PAYLOAD_DROPPED_TEXT,
        "normalized_entities": [],
        "query_class": row.query_class,
        "route": {},
        "trust_signal": row.trust_signal,
        "rubric_outcome": row.rubric_outcome,
        "rubric_score": None,
        "citations": [],
        "coverage_tags": [PAYLOAD_DROPPED_TAG],
        "user_feedback": None,
        "experiment_id": None,
        "experiment_arm": None,
        "cost_usd": row.cost_usd,
        "latency_ms": row.latency_ms,
        # A payload column like every other one here, so it is emptied for
        # the same reason: this insert exists to count a run whose content
        # could not be stored, and a saved answer is content. The row then
        # reports no saved answer and the person is offered Run again.
        "answer_markdown": None,
        "audience_depth": None,
        "answer_trust_line": None,
    })


def _write_minimal_interaction_row(row: InteractionRow) -> None:
    """Insert the reduced row from `_minimal_interaction_values`.

    Deliberately does NOT touch `sessions`: the minimal row carries no
    `session_id`, so there is no foreign key to satisfy and no second
    statement that could fail for its own reasons.
    """
    with session_scope() as db:
        db.execute(
            pg_insert(Interaction)
            .values(**_minimal_interaction_values(row))
            .on_conflict_do_nothing(index_elements=["trace_id"])
        )


def _write_interaction_row(row: InteractionRow) -> None:
    """The actual write, as one transaction: session-row-if-absent, then
    the idempotent interaction insert.

    Both statements commit together (`session_scope`'s own commit-on-success
    contract), so a caller never observes an `interactions` row whose
    `session_id` foreign key is dangling: either both land, or the
    transaction rolls back and neither does, and the outer retry in
    `write_interaction` tries again from a clean connection.

    Kept separate from `write_interaction` (rather than folding the
    try/except in here) so a test can exercise the ON CONFLICT clauses
    directly, with a real `IntegrityError` propagating on a mutation,
    instead of that mutation being masked by the outer best-effort catch.
    """
    with session_scope() as db:
        if row.session_id is not None:
            # `sessions` rows are created lazily by session memory, on the
            # first turn that has something to remember (Section 14.4), so
            # capture can run on a turn that memory had nothing to file for
            # and the foreign key below would otherwise reject the insert.
            # ON CONFLICT DO NOTHING, never an upsert that overwrites: a row
            # session memory already created, possibly with real memory
            # content, must never be clobbered by this lazy fallback racing
            # it. Only `id` and `user_id` are ever set here; `memory` is
            # left to whatever created the row, or NULL if this insert is
            # the one that does. This module's own `owner_id` (F-4.6-01)
            # goes onto the `interactions` row below, never onto `sessions.
            # memory`: that envelope is `core.session_memory`'s column, and
            # ownership no longer reads it (see the module docstring).
            session_stmt = (
                pg_insert(ChatSession)
                .values(id=row.session_id, user_id=row.user_id)
                .on_conflict_do_nothing(index_elements=["id"])
            )
            db.execute(session_stmt)

        # `trace_id` is UNIQUE and this is the retry-safety gate in
        # `production-standards`: the Act step retries and this background
        # task can be redelivered, so a plain INSERT would double-write and
        # every count the weekly review ritual makes would be wrong by an
        # unknown factor. ON CONFLICT DO NOTHING is the whole of the fix,
        # and it is also what makes a client-supplied `trace_id` unable to
        # evade the daily cap by colliding with itself (F-2.0-10): a second
        # insert under the same key changes nothing, it does not refresh a
        # timestamp or bump a counter.
        interaction_stmt = (
            pg_insert(Interaction)
            .values(**_interaction_values(row))
            .on_conflict_do_nothing(index_elements=["trace_id"])
        )
        db.execute(interaction_stmt)


async def write_interaction(row: InteractionRow) -> None:
    """Persist one finished run's row. Never raises (Section 16 stage 1).

    Retried once on a fresh connection; if that also fails the row is
    dropped with a warning that carries only `row.trace_id`, never the
    exception text. `str(exc)` is not logged anywhere in this function: a
    `psycopg2.OperationalError` can carry the connection DSN in its own
    message, and Section 16's own text is explicit that no column, and by
    the same reasoning no log line, may ever carry a credential or a
    connection string. Only the exception's class name is logged, which is
    enough to distinguish "cannot connect" from "constraint violation" in
    an operator's log without repeating whatever the driver put in the
    message.

    A row is dropped ONLY when the database itself could not be written to.
    When the full row fails every attempt, one final insert carries the
    reduced row `_minimal_interaction_values` builds, so a payload nobody
    anticipated costs the row's CONTENT and never the row itself. Read that
    function's docstring for the principle; the short form is that a caller
    must never be able to choose whether their own query is counted.
    """
    for attempt in range(1, _WRITE_ATTEMPTS + 1):
        try:
            _write_interaction_row(row)
            return
        except Exception as exc:  # noqa: BLE001 - a best-effort write must catch any failure mode
            if attempt < _WRITE_ATTEMPTS:
                logger.warning(
                    "interaction write failed for trace_id=%s (%s); retrying once",
                    row.trace_id,
                    type(exc).__name__,
                )
                continue
            logger.warning(
                "interaction write failed for trace_id=%s (%s) after %d attempt(s); "
                "retrying once with the payload columns dropped",
                row.trace_id,
                type(exc).__name__,
                _WRITE_ATTEMPTS,
            )

    try:
        _write_minimal_interaction_row(row)
    except Exception as exc:  # noqa: BLE001 - the last resort must still never raise
        logger.warning(
            "interaction write failed for trace_id=%s (%s) even with the payload "
            "columns dropped; dropping the row rather than failing the query",
            row.trace_id,
            type(exc).__name__,
        )
        return
    logger.warning(
        "interaction row for trace_id=%s stored with its payload columns dropped; "
        "the run is counted and its content is not recorded",
        row.trace_id,
    )


def _caller_owns_row(row: Interaction, owner_id: str) -> bool:
    """The whole of the ownership check: does the row's own record agree?

    F-4.6-01's fix. `row.owner_id` is the exact value `feedback.capture.
    assemble_interaction` recorded for this row at capture time, the same
    namespaced principal string a registered account's or a guest's
    `owner_id` always is. One direct compare answers both cases; there is
    no branch on `row.user_id`, and nothing here looks at `sessions.memory`.

    `row.owner_id is not None` guards a NULL row, the shape only a
    pre-migration row can have (alembic 0008 adds the column with no
    backfill). A NULL never equals any caller's `owner_id`, since a
    caller's `owner_id` is always a non-empty namespaced string, so this
    refuses for every caller on a NULL row rather than guessing at one: the
    same deny-by-default posture that made every guest one principal in
    build phase 4.5 (F-4.5-A-02) is exactly what this guard exists to keep
    from happening here.
    """
    return row.owner_id is not None and row.owner_id == owner_id


async def write_feedback(
    *, trace_id: str, owner_id: str, payload: FeedbackPayload
) -> None:
    """Attach feedback to the caller's own row, and only their own.

    Raises `InteractionNotFound` when no row carries `trace_id` yet: a real,
    expected state, since capture is a background task dispatched after the
    `done` event and feedback submitted the instant an answer finishes can
    genuinely arrive first.

    Raises `FeedbackOwnershipError` when the row exists and `owner_id` does
    not own it, per `_caller_owns_row` above. The row is locked
    (`with_for_update`) for the whole check-then-write so a concurrent
    feedback write on the same row cannot interleave with this one, and the
    refusal path never reaches the `UPDATE`: the ownership check runs before
    any write statement is issued, so a caller who is refused changes
    nothing, which is the property the premise gate's ownership arm asserts
    on the stored value rather than only on the exception.

    Replaces rather than appends, and is idempotent under retry: setting
    `user_feedback` to the same payload twice leaves the same end state,
    with no read-modify-append step that a redelivered call could apply
    twice.

    The payload leaves through `_storable` for the same reason capture's
    does (F-4.6-A-01): `user_feedback` is a `jsonb` column and `comment`,
    `flagged_reason` and every `citation_flags` entry are caller-supplied
    strings, so the identical unstorable-code-point class reaches this write
    by a second route. Here the consequence would be a 500 on the caller's
    own request rather than a silently dropped row, which is a different
    failure and the same cause, and it is fixed at the same chokepoint.
    """
    with session_scope() as db:
        row = db.execute(
            select(Interaction)
            .where(Interaction.trace_id == trace_id)
            .with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise InteractionNotFound(
                f"no interaction row exists yet for trace_id={trace_id!r}"
            )
        if not _caller_owns_row(row, owner_id):
            raise FeedbackOwnershipError(
                f"trace_id={trace_id!r} is not available to this caller"
            )
        row.user_feedback = _storable(payload.model_dump(mode="json"))


def reassign_interaction_owner(
    *, old_owner_id: str, new_owner_id: str, new_user_id: str | None
) -> int:
    """Re-point already-captured `interactions` rows from one principal to another.

    F-4.6-J-01 and F-4.6-A-03. Ownership of a run is recorded in TWO places
    and the guest-to-account migration only ever updated one of them:
    `RunEntry.owner_id`, which `core/run_registry.py`'s `reassign_owner`
    rewrites in memory, and `interactions.owner_id`, the column alembic 0008
    added, which nothing rewrote at all. The feedback endpoint checks both,
    so after a signup the two disagreed, the registry check passed, the row
    check refused, and a guest who signed up and then rated the answer they
    had just watched stream was told HTTP 403 "you do not own this run" and
    their rating was discarded.

    This is the durable half of the fix. `reassign_owner` covers the runs
    still in flight, whose rows do not exist yet; this covers the rows that
    already do. The two are called together, in that order, by
    `auth/router.py`'s `_migrate_guest_session`, and the order is what
    closes the window between them: once the registry has been reassigned,
    an in-flight run captures under the NEW owner, and every row written
    before that moment carries the old one and is matched by the `UPDATE`
    below. There is no instant at which a row can be written under the old
    owner after this function has already passed over it.

    Scoped to one named principal, never to a class of them. `old_owner_id`
    is built by the caller from the `guest_id` claim decoded out of the
    token the caller actually presented, exactly as `reassign_owner`'s is,
    so a caller can only ever name their own guest identity. A version of
    this that claimed every row with a NULL `user_id`, or every row whose
    owner merely starts with `guest:`, would re-open F-4.5-A-02, where one
    anonymous identity stood for every guest.

    Never raises, matching `write_interaction`: this runs inside a signup
    that has already committed, and a bookkeeping failure must not turn a
    successful signup into a 500. It is idempotent for the same reason
    `reassign_owner` is: a second call with the same arguments matches
    nothing, because the first call already moved every row off
    `old_owner_id`.

    Returns:
        The number of rows re-pointed, for the caller to log. Zero on a
        replay, on a guest who never asked anything, and on a failure.
    """
    account_uuid: uuid_module.UUID | None
    try:
        account_uuid = uuid_module.UUID(new_user_id) if new_user_id else None
    except ValueError:
        logger.warning(
            "interaction owner migration skipped: the new user id is not a uuid"
        )
        return 0

    try:
        with session_scope() as db:
            result = db.execute(
                update(Interaction)
                .where(Interaction.owner_id == old_owner_id)
                .values(owner_id=new_owner_id, user_id=account_uuid)
            )
            return int(result.rowcount or 0)
    except Exception as exc:  # noqa: BLE001 - a best-effort migration must catch any failure mode
        # Class name only, never `str(exc)`: same secrets-gate reasoning as
        # `write_interaction`'s own logging, and this one runs on the signup
        # path where the exception could carry bound parameters.
        logger.warning(
            "interaction owner migration failed (%s); the rows keep their "
            "previous owner and signup itself is unaffected",
            type(exc).__name__,
        )
        return 0
