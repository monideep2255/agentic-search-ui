"""Build phase 4.6: the feedback loop's v1 stages (Section 16).

Depends on:
    - system_03_search_agent.feedback.capture (assembles a row from a run)
    - system_03_search_agent.feedback.writer (persists one, owner-scoped)

Reads:
    - Environment variable: USER_DB_URL, by way of data/session.py

Writes:
    - The `interactions` and `sessions` tables in the user-data database

Section 16 ships three of the loop's five stages in v1: stage 1 (capture),
stage 3 (the human-gated weekly review) and stage 5 (few-shot promotion).
Stage 2, the automated mine-and-cluster job, is out of scope for v1 per the
PRD and `.claude/rules/v1-scope-boundary.md`, and stage 4's trigger rule runs
inside the manual review rather than as its own pass.

This package is the whole of the capture path. Two functions are public, and
the rest of the modules are implementation:

- `capture_run(query, events)`: stage 1. Called once from the run epilogue,
  after the caller already has their answer. Best-effort by construction.
- `record_feedback(...)`: the user's half of stage 1, written to a row that
  already exists, only ever by the principal that owns it.

The review ritual (`feedback.review`) and the promotion path
(`feedback.promotion`) are run by a human on a cadence, not by the
application, so they are imported directly by their scripts rather than
re-exported here.
"""

from __future__ import annotations

from system_03_search_agent.feedback.contracts import (
    FeedbackOwnershipError,
    FeedbackPayload,
    InteractionNotFound,
    InteractionRow,
)

__all__ = [
    "FeedbackOwnershipError",
    "FeedbackPayload",
    "InteractionNotFound",
    "InteractionRow",
    "capture_run",
    "record_feedback",
]


async def capture_run(query: object, events: list[object]) -> None:
    """Stage 1: fold one finished run into exactly one `interactions` row.

    Deferred import rather than a module-level one, so importing this package
    never pulls in SQLAlchemy or the assembler's event contracts. The same
    shape `core/run.py` already uses for `_remember_turn`, and for the same
    reason: the run path is hot and this is bookkeeping.

    Never raises. A capture failure is logged and dropped, because losing a
    row is an acceptable failure mode and blocking a response the caller
    already received is not (Section 16 stage 1).
    """
    from system_03_search_agent.feedback.capture import assemble_interaction
    from system_03_search_agent.feedback.writer import write_interaction

    row = assemble_interaction(query, events)
    if row is None:
        return
    await write_interaction(row)


async def record_feedback(
    *,
    trace_id: str,
    owner_id: str,
    rating: str | None = None,
    comment: str | None = None,
    flagged_reason: str | None = None,
    citation_flags: list[dict[str, str]] | None = None,
) -> None:
    """Attach the caller's own feedback to their own row.

    Raises `FeedbackOwnershipError` when the principal does not own the row
    and `InteractionNotFound` when no row exists yet. Both are real states a
    surface must tell apart, which is why neither is swallowed here the way
    `capture_run`'s failures are: this one is a request the caller is
    watching, not a background task nobody sees.
    """
    from system_03_search_agent.feedback.writer import write_feedback

    payload = FeedbackPayload(
        rating=rating,
        comment=comment,
        flagged_reason=flagged_reason,
        citation_flags=citation_flags or [],
    )
    await write_feedback(trace_id=trace_id, owner_id=owner_id, payload=payload)
