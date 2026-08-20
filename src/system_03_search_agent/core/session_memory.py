"""Bounded in-conversation session memory: T-4.5-03 and T-4.5-04, Section 14.

Session memory is the ONE context fragment that persists across turns rather
than arriving fresh each time, which is exactly why it is the one that needs
a hard cap and a firewall. Section 14.1:

    Session memory can shape what Think asks and what Plan schedules, but it
    can never itself become a citation.

Three rules this module exists to enforce, all of them mechanically rather
than by asking a model nicely:

    THE CAP IS COUNTED, NOT ESTIMATED. `build_session_context` counts tokens
    with the real tokenizer for the tier receiving the prompt, server-side,
    before injection. Never a character count, never a client-supplied
    number. See `count_tokens_for_tier`.

    THE BLOCK GOES IN THE DYNAMIC SUFFIX. Callers append the returned block
    to the live tail of the Think and Plan prompts. It never enters the
    system block, because `.claude/rules/prompt-cache-discipline.md` makes
    that block the prompt-cache stable prefix and a per-session value there
    misses the cache on every request whose memory has changed, which is
    every request. Nothing errors when that breaks; the bill just climbs.

    IT REACHES TWO STEPS AND NO OTHERS. `injected_steps` is the single
    declaration of which. Never Act, because tool calls must execute against
    fresh retrieval. Never Write, because memory must never become a citable
    source.

Depends on:
    - system_03_search_agent.contracts.query (SessionMemorySummary and its caps)
    - system_03_search_agent.harness.tiers (resolve_model, for the tokenizer)
    - litellm.token_counter, the per-model tokenizer

Writes:
    - Nothing. This module is pure with respect to the summary it is given:
      `compact` returns a new model rather than mutating its argument, so a
      caller that keeps the original is never surprised.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Protocol

from system_03_search_agent.contracts.query import (
    MAX_COMPRESSED_FINDINGS,
    MAX_RESOLVED_ENTITIES,
    CompressedFinding,
    ResolvedEntity,
    SessionMemorySummary,
)
from system_03_search_agent.harness.tiers import Tier, resolve_model

#: The steps session memory may be injected into, per Section 14.4. This
#: tuple is the declaration, not a comment: `injected_steps` returns it and
#: the premise gate asserts on it, so adding "act" here is a visible change
#: that turns a gate arm red rather than a quiet one-line edit in a caller.
_INJECTED_STEPS: tuple[str, ...] = ("think", "plan")

#: Rendered block header. Section 14.4's example shape.
_HEADER = "Session so far:"

#: What the block says when the entity list had to be shortened to fit. It is
#: disclosed rather than silently cut, the same discipline the KGX export's
#: manifest owes its truncation (build phase 4.4) and the Write step owes a
#: truncated result set (build phase 2.2).
_OMITTED_TEMPLATE = "({count} earlier resolved entities omitted for budget)"


def count_tokens_for_tier(text: str, *, tier: Tier) -> int:
    """Count tokens with the real tokenizer for the model this tier resolves to.

    Section 14.4 requires "the actual tokenizer for whichever model tier is
    receiving the prompt", not an approximation, because a character-based
    estimate is wrong by a different factor for prose, for CURIEs, and for
    non-Latin scripts, and the cap it feeds is a hard one.

    The fallback matters as much as the happy path. When the tier's model is
    one `litellm` cannot map to a tokenizer, this OVER-counts deliberately
    rather than guessing low: an under-count silently defeats the cap this
    function exists to serve, while an over-count only costs a slightly
    shorter block. Failing safe here means failing small.
    """
    if not text:
        return 0
    model = resolve_model(tier)
    try:
        import litellm

        return int(litellm.token_counter(model=model, text=text))
    except Exception:  # noqa: BLE001
        # Deliberately broad. A tokenizer lookup failing is not a reason to
        # fail the query, and every alternative here is a guess; the only
        # question is whether the guess is safe. 1 token per 3 characters is
        # below the ~4 that English prose averages, so this over-counts.
        return -(-len(text) // 3)


def _render(summary: SessionMemorySummary, *, entity_limit: int | None = None) -> str:
    """Render the summary into the compact block Section 14.4 shows.

    `entity_limit` is the last-resort lever described in `build_session_context`
    and is never used to drop entities from the summary itself.
    """
    entities = summary.resolved_entities
    omitted = 0
    if entity_limit is not None and len(entities) > entity_limit:
        omitted = len(entities) - entity_limit
        entities = entities[:entity_limit]

    parts: list[str] = []
    for entity in entities:
        parts.append(
            f"resolved {entity.mention} to {entity.curie} ({entity.entity_type})"
        )
    if omitted:
        parts.append(_OMITTED_TEMPLATE.format(count=omitted))
    for finding in summary.compressed_findings:
        parts.append(f"Established: {finding.claim_summary}")
    for thread in summary.open_threads:
        parts.append(f"Open: {thread}")

    if not parts:
        return ""
    return f"{_HEADER} " + ". ".join(parts) + "."


def compact(summary: SessionMemorySummary) -> SessionMemorySummary:
    """Shrink a summary to fit `token_budget`, in Section 14.3's exact order.

    The order is specified, not an implementation detail, and it encodes what
    is cheap to lose:

        1. Drop the OLDEST `open_threads` first. A thread is a note about
           what has not been done yet, and the current turn is usually about
           to supersede it.
        2. Then merge the OLDEST `compressed_findings` into one shorter
           combined entry. Findings are more valuable than threads because
           they record what was established.
        3. `resolved_entities` are NEVER dropped for budget reasons. They are
           small, and they are what a later turn's pronoun binds to, so
           losing them is what breaks reference resolution. They are bounded
           instead by the 50-item ceiling with FIFO eviction, which is a
           membership rule rather than a budget one.

    Returns a new summary. The argument is not mutated, so a caller holding
    the original still has every entity and finding it started with.
    """
    tier: Tier = "plan"
    working = summary.model_copy(deep=True)

    # FIFO eviction past the ceiling. This is the membership rule, and it
    # runs regardless of budget: it is not a budget drop.
    if len(working.resolved_entities) > MAX_RESOLVED_ENTITIES:
        working.resolved_entities = working.resolved_entities[-MAX_RESOLVED_ENTITIES:]

    def fits(candidate: SessionMemorySummary) -> bool:
        return (
            count_tokens_for_tier(_render(candidate), tier=tier)
            <= candidate.token_budget
        )

    if fits(working):
        return working

    # Step 1: oldest open_threads first, one at a time, stopping the moment
    # it fits. Dropping the whole list when one would do loses context for
    # nothing.
    while working.open_threads and not fits(working):
        working.open_threads = working.open_threads[1:]
    if fits(working):
        return working

    # Step 2: merge the oldest findings into one shorter combined entry.
    while len(working.compressed_findings) > 1 and not fits(working):
        oldest, second = working.compressed_findings[0], working.compressed_findings[1]
        merged = CompressedFinding(
            claim_summary=f"{oldest.claim_summary}; {second.claim_summary}"[:280],
            # The merged entry keeps the OLDER trace so the reference back to
            # a re-verifiable run survives the merge. A merged finding with no
            # resolvable trace would be exactly the un-regroundable claim
            # Section 14.4 forbids.
            trace_id=oldest.trace_id,
            citation_ids=(oldest.citation_ids + second.citation_ids)[:5],
        )
        working.compressed_findings = [merged] + working.compressed_findings[2:]

    return working


def build_session_context(summary: SessionMemorySummary, *, tier: Tier) -> str:
    """Render the block to append to Think's or Plan's dynamic suffix.

    Enforces the cap BEFORE injection, and cannot return a block over budget.
    That is the whole contract: a caller may append the return value without
    re-checking anything.

    On the one case Section 14.3 leaves open, stated rather than decided
    silently: the section says resolved entities are never dropped for budget
    reasons, and it also makes the token budget hard. Those two collide when
    the entities ALONE exceed the budget. This resolves it by distinguishing
    the STORED summary from the RENDERED block, which is the distinction the
    section is really drawing: `compact` never drops an entity from memory,
    so it is still there next turn when the budget may allow it, while this
    function renders as many as fit and DISCLOSES how many it left out. The
    alternative, returning a block over budget, would make the cap advisory,
    and a cap that is sometimes exceeded is not a cap. Logged in DECISIONS.md
    on 2026-08-20.
    """
    fitted = compact(summary)
    block = _render(fitted)
    if count_tokens_for_tier(block, tier=tier) <= fitted.token_budget:
        return block

    # Last resort: shrink the rendered entity list. Descending rather than a
    # binary search because the list is capped at 50 and correctness here is
    # worth more than the handful of counts saved.
    for limit in range(len(fitted.resolved_entities) - 1, -1, -1):
        candidate = _render(fitted, entity_limit=limit)
        if count_tokens_for_tier(candidate, tier=tier) <= fitted.token_budget:
            return candidate

    # Nothing fits, not even an empty entity list. Return nothing rather than
    # something over budget: the caller's contract is that this never exceeds
    # the cap, and an empty block degrades orchestration while a
    # budget-busting one degrades every prompt after it.
    return ""


def injected_steps(summary: SessionMemorySummary) -> tuple[str, ...]:
    """The agent-loop steps this summary may be injected into (Section 14.4).

    Takes the summary it describes rather than being a bare constant so that
    a future per-summary policy has somewhere to live, and so a caller cannot
    read the tuple without having a summary in hand.

    Never "act": tool calls execute against fresh retrieval, always. Never
    "write": a relevant `compressed_finding` must be re-verified by a
    scheduled Act step or a reuse of its original trace's cached
    `tool_result`, never asserted from the summary text.
    """
    del summary  # policy is currently uniform; the parameter is the seam
    return _INJECTED_STEPS


__all__ = [
    "build_session_context",
    "compact",
    "count_tokens_for_tier",
    "injected_steps",
]


#: Namespace for mapping a caller's session id to a `sessions.id` row key.
#:
#: `Query.session_id` is a free-form string of up to 64 characters, and the
#: surfaces genuinely send different shapes: the web UI sends
#: `crypto.randomUUID()`, the CLI sends a bare 32-character hex string, and
#: MCP accepts whatever the caller passes. `sessions.id` is a UUID column. So
#: the two cannot be the same value, and an early version of this store
#: silently DROPPED every session whose id did not parse as a UUID, which
#: made memory inert for the CLI and for most MCP callers while looking
#: correct for the browser.
#:
#: uuid5 is used rather than a new text column because it needs no schema
#: change and is deterministic: the same caller id always maps to the same
#: row, on every process and every deploy, which is the property that makes
#: it safe to derive rather than store. A random uuid4 would create a new row
#: per turn and lose the conversation.
#:
#: Build phase 4.6 writes `interactions.session_id` against the same table
#: and must use this same mapping, or the two will disagree about which row a
#: conversation is.
_SESSION_ID_NAMESPACE = uuid.UUID("6ba7b812-9dad-11d1-80b4-00c04fd430c8")


def session_row_key(session_id: str) -> uuid.UUID:
    """The `sessions.id` this caller-supplied session id maps to."""
    try:
        return uuid.UUID(session_id)
    except ValueError:
        return uuid.uuid5(_SESSION_ID_NAMESPACE, session_id)


class SessionMemoryStore(Protocol):
    """Where a session's owner and memory are read from.

    A Protocol rather than a concrete class so the ownership CHECK can be
    tested without standing up a database, while the shipped default reads
    the real `sessions` row. The check is the security-relevant part and it
    lives in `load_for_caller`, above any store: swapping the store cannot
    weaken it, which is the property worth preserving.
    """

    async def get(self, session_id: str) -> tuple[str | None, dict[str, Any] | None] | None:
        """Return `(owner_user_id, memory_payload)`, or None if unknown."""
        ...

    async def put(
        self, session_id: str, user_id: str | None, payload: dict[str, Any]
    ) -> None:
        """Write this session's memory, creating the row if it is new."""
        ...


class _PostgresSessionMemoryStore:
    """The shipped store: one row of the `sessions` table (alembic 0007)."""

    async def get(
        self, session_id: str
    ) -> tuple[str | None, dict[str, Any] | None] | None:
        from sqlalchemy import select

        from system_03_search_agent.data.models import ChatSession
        from system_03_search_agent.data.session import session_scope

        key = session_row_key(session_id)

        with session_scope() as db:
            row = db.execute(
                select(ChatSession.user_id, ChatSession.memory).where(
                    ChatSession.id == key
                )
            ).first()
        if row is None:
            return None
        owner, payload = row
        return (str(owner) if owner is not None else None, payload)


    async def put(
        self, session_id: str, user_id: str | None, payload: dict[str, Any]
    ) -> None:
        from system_03_search_agent.data.models import ChatSession
        from system_03_search_agent.data.session import session_scope

        key = session_row_key(session_id)

        with session_scope() as db:
            row = db.get(ChatSession, key)
            if row is None:
                # First turn of this session. The row is created here rather
                # than at session start because nothing else needs one: the
                # id is minted client-side and a session that never asks a
                # question should not leave a row behind.
                row = ChatSession(id=key, user_id=uuid.UUID(user_id) if user_id else None)
                db.add(row)
            row.memory = payload
            db.commit()


def _default_store() -> SessionMemoryStore:
    return _PostgresSessionMemoryStore()


class SessionOwnershipError(Exception):
    """A caller asked for a session that is not theirs (F-4.1-A-15).

    Boarded at build phase 4.1 and deliberately deferred to whichever phase
    first wired a `Query.session_id` consumer, on the reasoning that binding a
    session to its owner means designing the ownership model ahead of the
    phase that actually needs it. Build phase 4.5 is that phase.

    The gap it closes, in the finding's own words: every surface accepts a
    caller-supplied `session_id` with length validation and no check that it
    belongs to the caller. That was harmless while nothing READ the id.
    The moment session memory became readable by it, naming another account's
    session id would have handed over their conversation: the entities they
    resolved, the findings they established, and the threads they left open.
    """


def _ownership_refusal(session_id: str) -> SessionOwnershipError:
    """Build the refusal, worded once so every raise site agrees.

    Two properties, both required rather than stylistic:

    - It never says whether the session EXISTS. "Not yours" and "no such
      session" are the same message on purpose, because distinguishing them
      turns this into an oracle for probing which session ids are live.
    - It says what to do next, per the retry-safety gate in
      `production-standards`. The reader here is often an agent step, and
      "denied" tells it nothing about whether to retry.
    """
    return SessionOwnershipError(
        f"session {session_id!r} is not available to this caller; start a new "
        "session, or retry with the session id this caller was issued. Do not "
        "retry this id: it will not become available."
    )


async def load_for_caller(
    *,
    session_id: str,
    user_id: str | None,
    store: SessionMemoryStore | None = None,
) -> SessionMemorySummary | None:
    """Load this session's memory, or refuse if it is not the caller's.

    Returns None for a session that has no memory yet, which is the ordinary
    first turn and is not an error.

    Raises `SessionOwnershipError` when the stored session belongs to someone
    else. The check is deliberately conservative in BOTH directions:

    - A session owned by an account is readable only by that account.
    - A session owned by nobody (an anonymous session, `user_id` NULL) is
      never handed to an authenticated caller, and vice versa. A guest
      session's contents are not automatically the property of whoever signs
      in next on that browser; migrating them is build phase 4.6's explicit
      history-migration step, not something that should happen silently here.
    """
    active = store if store is not None else _default_store()
    record = await active.get(session_id)
    if record is None:
        return None
    owner_id, payload = record
    if (owner_id or None) != (user_id or None):
        raise _ownership_refusal(session_id)
    if payload is None:
        return None
    return SessionMemorySummary.model_validate(payload)


def merge_turn(
    existing: SessionMemorySummary | None,
    *,
    session_id: str,
    now: datetime,
    resolved: list[ResolvedEntity],
    findings: list[CompressedFinding],
) -> SessionMemorySummary:
    """Fold one finished turn into the session's memory (T-4.5-04).

    Idempotent by natural key, which the retry-safety gate in
    `production-standards` requires because the Act step retries and a turn
    can be replayed: an entity is keyed by its CURIE and a finding by its
    `trace_id` plus summary, so folding the same turn twice produces the same
    summary as folding it once. A blind append would grow the list on every
    retry and evict real history to make room for duplicates.

    Newest-last ordering is load-bearing rather than incidental. `compact`
    drops the OLDEST open threads and merges the OLDEST findings, and FIFO
    eviction past the 50-entity ceiling takes from the front, so all three
    rules depend on this list being ordered oldest to newest.
    """
    base = existing or SessionMemorySummary(session_id=session_id, last_updated=now)

    entities = list(base.resolved_entities)
    seen_curies = {entity.curie for entity in entities}
    for entity in resolved:
        if entity.curie not in seen_curies:
            entities.append(entity)
            seen_curies.add(entity.curie)

    merged_findings = list(base.compressed_findings)
    seen_findings = {(f.trace_id, f.claim_summary) for f in merged_findings}
    for finding in findings:
        key = (finding.trace_id, finding.claim_summary)
        if key not in seen_findings:
            merged_findings.append(finding)
            seen_findings.add(key)

    return compact(
        SessionMemorySummary(
            session_id=session_id,
            resolved_entities=entities[-MAX_RESOLVED_ENTITIES:],
            compressed_findings=merged_findings[-MAX_COMPRESSED_FINDINGS:],
            open_threads=list(base.open_threads),
            token_budget=base.token_budget,
            last_updated=now,
        )
    )


async def save_for_caller(
    summary: SessionMemorySummary,
    *,
    user_id: str | None,
    store: SessionMemoryStore | None = None,
) -> None:
    """Persist a session's memory, refusing if the session is not the caller's.

    Goes through the SAME ownership check as the read path rather than
    trusting that whoever assembled the summary already checked. A write path
    that skips the check is how an authorization hole reopens after the read
    path was fixed: the two are separate code paths and only one of them was
    ever the finding.
    """
    active = store if store is not None else _default_store()
    record = await active.get(summary.session_id)
    if record is not None:
        owner_id, _payload = record
        if (owner_id or None) != (user_id or None):
            raise _ownership_refusal(summary.session_id)
    await active.put(
        summary.session_id, user_id, summary.model_dump(mode="json")
    )
