"""Bounded in-conversation session memory: T-4.5-03 and T-4.5-04, Section 14.

Session memory is the ONE context fragment that persists across turns rather
than arriving fresh each time, which is exactly why it is the one that needs
a hard cap and a firewall. Section 14.1:

    Session memory can shape what Think asks and what Plan schedules, but it
    can never itself become a citation.

Four rules this module exists to enforce, all of them mechanically rather
than by asking a model nicely:

    A SESSION BELONGS TO ONE CALLER, AND THE CALLER IS NAMED. Every read and
    every write takes a required `owner_id`, the namespaced principal string
    (`user:<uuid>` or `guest:<uuid>`) the auth layer already mints. It is
    never derived from `user_id`, because `user_id` is NULL for every guest
    and a NULL-versus-NULL comparison makes all guests one principal. See
    `load_for_caller` and `CallerIdentityRequired`.

    THE CAP IS COUNTED, NOT ESTIMATED. `build_session_context` counts tokens
    with the tokenizer for the tier receiving the prompt, server-side,
    before injection. Never a character count where a real count is
    available, and never a client-supplied number: the stored `token_budget`
    is clamped to Section 14.3's hard 1500 at every enforcement point. See
    `count_tokens_for_tier` and `_effective_budget`.

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

`open_threads` HAS A PRODUCER as of build phase 6.2, T-6.2-07, and this
paragraph replaces the one that said it did not. Build phase 4.5 left the
field on the contract and rendered by `_render` with nothing writing it, and
required IN WRITING that whoever added a producer delete that note in the
same change. This is that change.

`merge_turn` now takes the turn's `question` and appends it, so an open
thread is what it sounds like: a question this conversation has not closed.
Two consequences worth stating rather than leaving to be rediscovered.
Section 14.3's first compaction rule, "drop the oldest open_threads first",
NOW FIRES ON REAL DATA, where before compaction always began at the more
expensive findings merge. And the thread is what lets a follow-up resolve a
pronoun: "what variants cause it" reaches Think with the earlier questions
in order, not only the entities they resolved to.

Depends on:
    - system_03_search_agent.contracts.query (SessionMemorySummary and its caps)
    - system_03_search_agent.harness.tiers (resolve_model, for the tokenizer)
    - litellm.token_counter, the per-model tokenizer

Writes:
    - `sessions.memory` (alembic 0007), through `SessionMemoryStore`, and
      only through `save_for_caller` or `remember_turn_for_caller`, both of
      which check ownership inside the same locked transaction as the write.
    - Nothing else. `compact` returns a new model rather than mutating its
      argument, so a caller that keeps the original is never surprised.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime
from functools import lru_cache
from typing import Any, Protocol

from system_03_search_agent.contracts.query import (
    MAX_CITATION_IDS_PER_FINDING,
    MAX_CLAIM_SUMMARY_LENGTH,
    MAX_COMPRESSED_FINDINGS,
    MAX_OPEN_THREAD_LENGTH,
    MAX_OPEN_THREADS,
    MAX_REPORTED_RECORD_ID_LENGTH,
    MAX_REPORTED_RECORD_IDS,
    MAX_RESOLVED_ENTITIES,
    SESSION_MEMORY_TOKEN_BUDGET,
    CompressedFinding,
    ResolvedEntity,
    SessionMemorySummary,
)
from system_03_search_agent.harness.tiers import Tier, resolve_model

#: The steps session memory may be injected into, per Section 14.4. This
#: tuple is the declaration, not a comment: `injected_steps` returns it and
#: the premise gate asserts on it, so adding "act" here is a visible change
#: that turns a gate arm red rather than a quiet one-line edit in a caller.
#:
#: Think and Plan only, as Section 14.4 states. UI fix set 7, item 7.1
#: (2026-09-13) briefly added "guardrail" here while a memory block was
#: injected into the Guard prompt; both cuts of that block were measured
#: destabilising the Guard model, so the guardrail no longer receives one.
#: It reads memory only for a deterministic rule applied after its verdict
#: (`core.graph._is_memory_bound_follow_up`), which is not an injection.
_INJECTED_STEPS: tuple[str, ...] = ("think", "plan")

#: The model tiers those steps actually resolve to. `core/graph.py` dispatches
#: Think at the guard tier and Plan at the plan tier, so a summary written now
#: will be counted later against whichever of the two reads it first. Storage
#: time cannot know which, so `compact` counts against whichever counts
#: HIGHEST unless a caller names its tier (F-4.5-J-22: the shipped version
#: hardcoded "plan" for every decision, including the ones Think would read).
_INJECTION_TIERS: tuple[Tier, ...] = ("guard", "plan")

#: Rendered block header. Section 14.4's example shape.
_HEADER = "Session so far:"

#: What the block says when the entity list had to be shortened to fit. It is
#: disclosed rather than silently cut, the same discipline the KGX export's
#: manifest owes its truncation (build phase 4.4) and the Write step owes a
#: truncated result set (build phase 2.2).
_OMITTED_TEMPLATE = "({count} earlier resolved entities omitted for budget)"

#: How two merged claim summaries are joined, and what marks the join being
#: cut short. The marker exists so a merged entry that hit the 280-character
#: ceiling says so, rather than ending mid-word and reading as a complete
#: claim that happens to be strangely worded.
_FINDING_JOIN = "; "
_TRUNCATION_MARKER = " (truncated)"

#: Below the roughly 4 characters per token English prose averages, so a text
#: length divided by this OVER-counts. Used wherever a real tokenizer count is
#: unavailable or unverified: over-counting costs a slightly shorter block,
#: under-counting silently defeats the cap.
_SAFE_CHARS_PER_TOKEN = 3

#: A model id no provider serves, used to read back whatever default encoder
#: `litellm` falls back to when it cannot map a model. See
#: `_tokenizer_is_model_specific`.
_UNMAPPED_MODEL_PROBE = "system-3-no-such-model-tokenizer-probe"

#: Mixed scripts and a biomedical identifier, chosen because two different
#: tokenizer vocabularies disagree about it. A pure-ASCII probe would tokenize
#: identically almost everywhere and the check below would report every model
#: as unmapped.
_TOKENIZER_PROBE = "BRCA1 c.68_69delAG 東京 αβγ probe"


def _char_estimate(text: str) -> int:
    """A deliberately high character-based token estimate."""
    return -(-len(text) // _SAFE_CHARS_PER_TOKEN)


def _litellm_token_count(model: str, text: str) -> int | None:
    """`litellm`'s count for this model, or None when it cannot produce one."""
    try:
        import litellm

        return int(litellm.token_counter(model=model, text=text))
    except Exception:  # noqa: BLE001
        # Deliberately broad. A tokenizer lookup failing is not a reason to
        # fail the query. The caller decides what to do with None; this
        # function's only job is to report that no count is available.
        return None


@lru_cache(maxsize=16)
def _tokenizer_is_model_specific(model: str) -> bool:
    """Did `litellm` actually select a tokenizer for THIS model?

    It has to be asked rather than assumed. `litellm.token_counter` does not
    raise for a model it cannot map: it silently falls back to a default
    encoder and returns a number, which is why the shipped version's
    documented fail-safe branch was unreachable and why the same count came
    back for the configured plan model, for two unrelated vendors, and for a
    fabricated model name (F-4.5-A-07).

    The check is a comparison rather than a lookup table: count a probe under
    this model and under a model id no provider serves. If the two agree, the
    default encoder answered both, so the number carries no information about
    this model's vocabulary and `count_tokens_for_tier` must not trust it as
    the receiving tier's real count.

    Cached per model id because it costs two tokenizer calls and the answer
    cannot change without a process restart or a deliberate `cache_clear()`.
    """
    mine = _litellm_token_count(model, _TOKENIZER_PROBE)
    if mine is None:
        return False
    default = _litellm_token_count(_UNMAPPED_MODEL_PROBE, _TOKENIZER_PROBE)
    if default is None:
        return False
    return mine != default


def count_tokens_for_tier(text: str, *, tier: Tier) -> int:
    """Count tokens for the model this tier resolves to, failing safe.

    Section 14.4 requires "the actual tokenizer for whichever model tier is
    receiving the prompt", not an approximation, because a character-based
    estimate is wrong by a different factor for prose, for CURIEs, and for
    non-Latin scripts, and the cap it feeds is a hard one.

    Three outcomes, and the middle one is the one the shipped version got
    wrong (F-4.5-A-07, F-4.5-J-22):

    - `litellm` selected a tokenizer for this model: return its count. This
      is the case Section 14.4 describes and it is the only case that returns
      a real count unmodified.
    - `litellm` returned a number from its DEFAULT encoder because it could
      not map this model: return the larger of that number and the safe
      character estimate. The number is an approximation for an unknown
      vocabulary with an unknown error direction, so the cap must not be set
      by it alone.
    - `litellm` could not count at all: return the safe character estimate.

    Failing safe here means failing small: an over-count only costs a shorter
    block, while an under-count silently defeats the cap this function exists
    to serve.
    """
    if not text:
        return 0
    model = resolve_model(tier)
    counted = _litellm_token_count(model, text)
    if counted is None:
        return _char_estimate(text)
    if _tokenizer_is_model_specific(model):
        return counted
    return max(counted, _char_estimate(text))


def count_tokens_worst_case(text: str) -> int:
    """The highest count any tier that may receive this block would report.

    Storage-time compaction has no receiving tier: the same stored summary is
    read by Think at the guard tier and by Plan at the plan tier. Counting
    against one of them and injecting into the other is what F-4.5-J-22
    names, so this counts against both and keeps the larger.
    """
    return max(count_tokens_for_tier(text, tier=tier) for tier in _INJECTION_TIERS)


def _effective_budget(summary: SessionMemorySummary) -> int:
    """The budget actually enforced: never above Section 14.3's hard 1500.

    `token_budget` is a field on a model that can arrive from a caller or
    from a stored row written by an older or hand-edited version, and
    F-4.5-A-24 measured what that costs: a summary carrying 8000 rendered a
    19,000-character block into two prompts while the enforcement code worked
    exactly as written, because it compared against the number the summary
    brought with it. A bound a caller can raise is not a bound, so the
    contract's own ceiling is applied again here, at the point of use.
    """
    return min(summary.token_budget, SESSION_MEMORY_TOKEN_BUDGET)


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


def _merge_two_findings(
    oldest: CompressedFinding, second: CompressedFinding
) -> CompressedFinding:
    """Combine the two oldest findings into one entry, disclosing a cut.

    The merged entry keeps the OLDER trace so the reference back to a
    re-verifiable run survives the merge. A merged finding with no resolvable
    trace would be exactly the un-regroundable claim Section 14.4 forbids,
    and it would also break `merge_turn`'s idempotence, which keys on the
    trace being still present.
    """
    combined = f"{oldest.claim_summary}{_FINDING_JOIN}{second.claim_summary}"
    if len(combined) > MAX_CLAIM_SUMMARY_LENGTH:
        keep = MAX_CLAIM_SUMMARY_LENGTH - len(_TRUNCATION_MARKER)
        combined = combined[:keep] + _TRUNCATION_MARKER
    return CompressedFinding(
        claim_summary=combined,
        trace_id=oldest.trace_id,
        citation_ids=(oldest.citation_ids + second.citation_ids)[
            :MAX_CITATION_IDS_PER_FINDING
        ],
    )


def compact(
    summary: SessionMemorySummary, *, tier: Tier | None = None
) -> SessionMemorySummary:
    """Shrink a summary to fit its budget, in Section 14.3's exact order.

    The order is specified, not an implementation detail, and it encodes what
    is cheap to lose:

        1. Drop the OLDEST `open_threads` first. A thread is a note about
           what has not been done yet, and the current turn is usually about
           to supersede it. Nothing in `src/` writes this list today, so on
           real data this step is a no-op and compaction begins at step 2:
           see the no-producer paragraph in the module docstring.
        2. Then merge the OLDEST `compressed_findings` into one shorter
           combined entry. Findings are more valuable than threads because
           they record what was established.
        3. `resolved_entities` are NEVER dropped for budget reasons. They are
           small, and they are what a later turn's pronoun binds to, so
           losing them is what breaks reference resolution. They are bounded
           instead by the 50-item ceiling with FIFO eviction, which is a
           membership rule rather than a budget one.

    `tier` names the model tier that will receive this block. Passing None,
    which storage-time callers do because they cannot know, counts against
    every injection tier and keeps the largest count.

    Returns a new summary. The argument is not mutated, so a caller holding
    the original still has every entity and finding it started with.
    """
    working = summary.model_copy(deep=True)
    budget = _effective_budget(working)

    # FIFO eviction past the ceiling. This is the membership rule, and it
    # runs regardless of budget: it is not a budget drop.
    if len(working.resolved_entities) > MAX_RESOLVED_ENTITIES:
        working.resolved_entities = working.resolved_entities[-MAX_RESOLVED_ENTITIES:]

    def count(text: str) -> int:
        if tier is None:
            return count_tokens_worst_case(text)
        return count_tokens_for_tier(text, tier=tier)

    def fits(candidate: SessionMemorySummary) -> bool:
        return count(_render(candidate)) <= budget

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
        merged = _merge_two_findings(
            working.compressed_findings[0], working.compressed_findings[1]
        )
        working.compressed_findings = [merged] + working.compressed_findings[2:]

    return working


def build_session_context(summary: SessionMemorySummary, *, tier: Tier) -> str:
    """Render the block to append to Think's or Plan's dynamic suffix.

    Enforces the cap BEFORE injection, and cannot return a block over budget.
    That is the whole contract: a caller may append the return value without
    re-checking anything.

    Every count here, and every count `compact` makes on the way, is made
    against `tier`, the tier actually receiving the prompt. The shipped
    version compacted against a hardcoded "plan" and then re-measured against
    the caller's tier, so for Think the decisions about which threads to drop
    and which findings to merge were computed for a model that was not going
    to read them (F-4.5-J-22).

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
    fitted = compact(summary, tier=tier)
    budget = _effective_budget(fitted)
    block = _render(fitted)
    if count_tokens_for_tier(block, tier=tier) <= budget:
        return block

    # Last resort: shrink the rendered entity list. Descending rather than a
    # binary search because the list is capped at 50 and correctness here is
    # worth more than the handful of counts saved.
    for limit in range(len(fitted.resolved_entities) - 1, -1, -1):
        candidate = _render(fitted, entity_limit=limit)
        if count_tokens_for_tier(candidate, tier=tier) <= budget:
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
#: change and is deterministic: the same caller and the same id always map to
#: the same row, on every process and every deploy, which is the property
#: that makes it safe to derive rather than store. A random uuid4 would
#: create a new row per turn and lose the conversation.
#:
#: Build phase 4.6 writes `interactions.session_id` against the same table
#: and must use this same mapping, INCLUDING the owner, or the two will
#: disagree about which row a conversation is.
_SESSION_ID_NAMESPACE = uuid.UUID("6ba7b812-9dad-11d1-80b4-00c04fd430c8")

#: Separates the owner from the session id inside the uuid5 input. A
#: character no principal string and no session id can contain, so
#: ("guest:a", "b-c") and ("guest:a-b", "c") cannot produce the same key.
_KEY_SEPARATOR = "\x1f"


class CallerIdentityRequired(ValueError):
    """A memory operation was attempted with no caller identity.

    Raised rather than defaulted, and this is the whole point of the class
    existing. The shipped version took `user_id`, which is None for every
    guest, so "no identity" and "anonymous" were the same value and every
    anonymous caller was the same principal (F-4.5-J-02, F-4.5-A-02): any
    guest naming another guest's session id read and overwrote their
    conversation. An empty string collapsed the same way, because the check
    was `(owner_id or None) != (user_id or None)` and `("" or None)` is None
    (F-4.5-A-22).

    So the identity is now required, is never inferred, and a caller that
    cannot supply one gets an exception rather than the anonymous bucket.
    """


def _require_owner_id(owner_id: object) -> str:
    """Validate the caller identity, or refuse loudly.

    Accepts only a non-empty string with no surrounding whitespace, and does
    NOT normalize: two identities that differ by a space are two identities,
    because silently folding them together is the class of bug this function
    exists to end.
    """
    if not isinstance(owner_id, str) or not owner_id or owner_id.strip() != owner_id:
        raise CallerIdentityRequired(
            "session memory requires the caller's namespaced identity "
            "(Principal.owner_id, e.g. 'user:<uuid>' or 'guest:<uuid>'), and "
            f"got {owner_id!r}. It is never derived from user_id, which is "
            "NULL for every guest. Pass caller.owner_id."
        )
    return owner_id


def session_row_key(session_id: str, *, owner_id: str) -> uuid.UUID:
    """The `sessions.id` this caller's session id maps to.

    Keyed on the OWNER as well as the id, which is what makes two guests who
    both send `--session-id shared` two different conversations rather than
    one. `session_id` is caller-chosen with no minimum length, no format and
    no entropy requirement on any surface, so it can never be the sole key to
    a private row.

    The whole string is hashed, never parsed. The shipped version tried
    `uuid.UUID(session_id)` first, and `uuid.UUID` strips `urn:`, `uuid:`,
    braces and every hyphen anywhere in its input before parsing, so eight
    distinct caller-legal strings landed on one row and the empty string
    landed on a fixed, derivable UUID (F-4.5-A-14). Hashing the exact bytes
    means distinct strings are distinct rows, including strings that differ
    only in case or punctuation.
    """
    owner = _require_owner_id(owner_id)
    return uuid.uuid5(_SESSION_ID_NAMESPACE, f"{owner}{_KEY_SEPARATOR}{session_id}")


#: Version of the stored `sessions.memory` envelope. The envelope exists so
#: the row records WHO owns the memory, which `sessions.user_id` cannot say
#: for a guest: that column is NULL for every guest and there is no guest
#: column on the table. A payload that is not a current envelope is treated
#: as unowned and is never served, which is what retires memory written by
#: the pre-fix code rather than handing it to the first caller who asks.
_MEMORY_ENVELOPE_VERSION = 1


def _wrap(owner_id: str, summary_payload: dict[str, Any]) -> dict[str, Any]:
    """Put the owner in the row alongside the summary."""
    return {
        "v": _MEMORY_ENVELOPE_VERSION,
        "owner_id": owner_id,
        "summary": summary_payload,
    }


def _unwrap(stored: Any) -> tuple[str | None, dict[str, Any] | None]:
    """Read `(owner_id, summary_payload)` out of a stored row value.

    Returns `(None, None)` for anything that is not a current envelope: a
    NULL column, a payload written before the envelope existed, or one whose
    owner is missing or not a string. Unowned means unreadable, never
    "readable by anyone", and the caller decides whether an unowned row may
    be claimed by a write.
    """
    if not isinstance(stored, dict):
        return (None, None)
    if stored.get("v") != _MEMORY_ENVELOPE_VERSION:
        return (None, None)
    owner = stored.get("owner_id")
    summary = stored.get("summary")
    if not isinstance(owner, str) or not owner or not isinstance(summary, dict):
        return (None, None)
    return (owner, summary)


def _clamp_stored_budget(payload: dict[str, Any]) -> dict[str, Any]:
    """Clamp a stored `token_budget` on the way OUT of the database.

    A stored value is untrusted input when it is read back, not only when it
    is written: a row written by an older version, or edited by hand, must
    not be able to raise the cap it was supposed to be bounded by. This is
    the posture `auth/preferences.py` already takes for the depth key, and
    F-4.5-A-24 is what the opposite posture cost here.

    Clamps rather than rejects so a pre-existing row degrades to the correct
    budget instead of failing validation and losing the conversation.
    """
    budget = payload.get("token_budget")
    if isinstance(budget, int) and budget > SESSION_MEMORY_TOKEN_BUDGET:
        return {**payload, "token_budget": SESSION_MEMORY_TOKEN_BUDGET}
    return payload


def _summary_from_payload(payload: dict[str, Any]) -> SessionMemorySummary:
    return SessionMemorySummary.model_validate(_clamp_stored_budget(payload))


#: What a store's `apply` callback is handed and what it returns: the stored
#: owner (None when the row is unowned), the stored summary payload (None
#: when there is none), and the payload to write, or None to write nothing.
ApplyMemory = Callable[
    [str | None, "dict[str, Any] | None"], "dict[str, Any] | None"
]


class SessionMemoryStore(Protocol):
    """Where a session's owner and memory are read from and written to.

    A Protocol rather than a concrete class so the ownership CHECK can be
    tested without standing up a database, while the shipped default reads
    the real `sessions` row. The check is the security-relevant part and it
    lives above any store, in `load_for_caller`, `save_for_caller` and
    `remember_turn_for_caller`: swapping the store cannot weaken it, which is
    the property worth preserving.

    Two methods, not three. There is no bare `put`, because a write that does
    not see the row's current owner cannot check ownership against it, and a
    check made in a separate round trip before the write is a TOCTOU window
    (F-4.5-J-16). Every write goes through `update`, which hands the caller
    the current owner and the current payload with the row already locked.
    """

    async def get(
        self, session_id: str, *, owner_id: str
    ) -> tuple[str | None, dict[str, Any] | None] | None:
        """Return `(owner_id, summary_payload)`, or None if the row is unknown."""
        ...

    async def update(
        self, session_id: str, *, owner_id: str, apply: ApplyMemory
    ) -> None:
        """Read, apply, and write this session's memory as one operation.

        The row is locked for the whole of it, so the owner `apply` sees is
        the owner the write lands against, and two concurrent turns on one
        session serialize instead of losing each other's updates
        (F-4.5-A-15). `apply` may raise to abort without writing, and
        returning None writes nothing.
        """
        ...


class _PostgresSessionMemoryStore:
    """The shipped store: one row of the `sessions` table (alembic 0007)."""

    async def get(
        self, session_id: str, *, owner_id: str
    ) -> tuple[str | None, dict[str, Any] | None] | None:
        from sqlalchemy import select

        from system_03_search_agent.data.models import ChatSession
        from system_03_search_agent.data.session import session_scope

        key = session_row_key(session_id, owner_id=owner_id)

        with session_scope() as db:
            row = db.execute(
                select(ChatSession.memory).where(ChatSession.id == key)
            ).first()
        if row is None:
            return None
        return _unwrap(row[0])

    async def update(
        self, session_id: str, *, owner_id: str, apply: ApplyMemory
    ) -> None:
        from system_03_search_agent.data.models import ChatSession
        from system_03_search_agent.data.session import session_scope

        key = session_row_key(session_id, owner_id=owner_id)

        with session_scope() as db:
            # `with_for_update` is what makes the read-modify-write one
            # operation. Without it two turns of the same session both read
            # the old summary and the second commit discards the first's
            # entities and findings, which looks exactly like the feature
            # simply not remembering.
            row = db.get(ChatSession, key, with_for_update=True)
            stored_owner, stored_payload = (
                _unwrap(row.memory) if row is not None else (None, None)
            )
            new_payload = apply(stored_owner, stored_payload)
            if new_payload is None:
                return
            if row is None:
                # First turn of this session. The row is created here rather
                # than at session start because nothing else needs one: the
                # id is minted client-side and a session that never asks a
                # question should not leave a row behind. Two concurrent
                # first turns can still collide on the primary key; the
                # loser's write is lost, which is the same best-effort
                # outcome every other memory failure has.
                row = ChatSession(id=key, user_id=_account_uuid(owner_id))
                db.add(row)
            row.memory = _wrap(owner_id, new_payload)


def _account_uuid(owner_id: str) -> uuid.UUID | None:
    """The `users.id` behind this principal, or None for a guest.

    `sessions.user_id` is a foreign key to `users`, so only an account
    identity can go in it. It is bookkeeping and a join key, never the
    ownership check: the check reads the envelope's `owner_id`, which is the
    only value that distinguishes one guest from another.
    """
    if not owner_id.startswith("user:"):
        return None
    try:
        return uuid.UUID(owner_id.split(":", 1)[1])
    except ValueError:
        return None


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
      turns this into an oracle for probing which session ids are live. The
      read path never reaches this message at all: an unknown row and an
      unowned row both return None, and a row owned by someone else is
      unreachable through this caller's row key in the first place.
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
    owner_id: str,
    store: SessionMemoryStore | None = None,
) -> SessionMemorySummary | None:
    """Load this session's memory, or refuse if it is not the caller's.

    `owner_id` is the caller's namespaced principal string, `user:<uuid>` or
    `guest:<uuid>`, and it is REQUIRED. It is not `user_id` and it is not
    optional: see `CallerIdentityRequired` for why a missing identity raises
    instead of reading the anonymous bucket.

    Returns None for a session that has no memory yet, which is the ordinary
    first turn and is not an error. Returns None as well for a row whose
    memory carries no recorded owner, which is a row written before the
    ownership envelope existed: unowned memory is retired rather than served.

    Raises `SessionOwnershipError` when the row records a different owner.
    That is defence in depth rather than the primary control: the row key
    already includes the owner, so a caller cannot address another caller's
    row. The comparison exists so a store that keys differently, including a
    hand-written test double and whatever build phase 4.6 does for its
    history migration, still cannot hand memory across principals.

    The comparison is exact string equality on two validated non-empty
    strings. No truthiness coercion, which is what let `""` and None mean the
    same thing before.
    """
    owner = _require_owner_id(owner_id)
    active = store if store is not None else _default_store()
    record = await active.get(session_id, owner_id=owner)
    if record is None:
        return None
    stored_owner, payload = record
    if stored_owner is None:
        return None
    if stored_owner != owner:
        raise _ownership_refusal(session_id)
    if payload is None:
        return None
    return _summary_from_payload(payload)


def merge_turn(
    existing: SessionMemorySummary | None,
    *,
    session_id: str,
    now: datetime,
    resolved: list[ResolvedEntity],
    findings: list[CompressedFinding],
    question: str = "",
    reported_record_ids: list[str] | None = None,
) -> SessionMemorySummary:
    """Fold one finished turn into the session's memory (T-4.5-04).

    Idempotent by natural key, which the retry-safety gate in
    `production-standards` requires because the Act step retries and a turn
    can be replayed. The two keys:

    - An entity is keyed by its CURIE, which nothing ever rewrites.
    - A finding is keyed by its `trace_id`, which identifies the TURN. Every
      finding of one turn carries that turn's trace, so a summary that
      already holds any finding from this trace has already folded this turn
      and the whole batch is skipped.

    Why the turn and not the claim, stated because the shipped version keyed
    on `(trace_id, claim_summary)` and F-4.5-J-20 measured what that costs:
    `compact` MERGES the two oldest findings into one entry whose
    `claim_summary` is neither original, so the claim-level key stops
    matching the moment compaction runs, and replaying the turn re-appends
    both originals. Three replays produced a summary containing the same two
    claims three times over, growing until the 280-character ceiling cut it
    into a truncated repetition of itself. Compaction is not an edge case; it
    is the mechanism this module exists for, so the key had to be one
    compaction preserves. It does preserve the trace: a merged entry keeps
    the older of the two traces.

    The boundary, stated rather than left for a reader to discover. Merging
    keeps one of two traces and eviction past 20 findings drops the oldest
    entries, so a turn whose trace has been squeezed out of the summary
    entirely can be folded again if it is ever replayed. That is bounded by
    the summary's own size, it needs a replay of a turn several turns old,
    and no path in `src/` replays an old trace: `_remember_turn` runs once
    per run under a server-minted uuid4. Idempotence for the turn just folded
    holds unconditionally.

    Newest-last ordering is load-bearing rather than incidental. `compact`
    drops the OLDEST open threads and merges the OLDEST findings, and FIFO
    eviction past the 50-entity ceiling takes from the front, so all three
    rules depend on this list being ordered oldest to newest.
    """
    base = existing or SessionMemorySummary(session_id=session_id, last_updated=now)

    # A re-mentioned entity MOVES TO THE END rather than keeping its
    # original place (UI fix set 7, 2026-09-13, the product owner's
    # "if this is a discussion, it must flow"). `_antecedent_curie` binds a
    # pronoun to the LAST entity here, so under the old rule a session that
    # went BRCA1, then TP53, then back to BRCA1 by name still bound the next
    # "it" to TP53, because BRCA1 had kept its first position. Now "most
    # recent" means most recently mentioned. Still keyed by CURIE, still
    # idempotent: replaying a turn moves the same entities to the same end.
    entities = [
        entity
        for entity in base.resolved_entities
        if entity.curie not in {mention.curie for mention in resolved}
    ]
    seen_curies = {entity.curie for entity in entities}
    for entity in resolved:
        if entity.curie not in seen_curies:
            entities.append(entity)
            seen_curies.add(entity.curie)

    merged_findings = list(base.compressed_findings)
    # Computed from the BASE only and never added to inside the loop: every
    # finding of one turn shares that turn's trace, so growing the set as we
    # go would drop every finding after the first.
    folded_traces = {f.trace_id for f in merged_findings}
    seen_exact = {(f.trace_id, f.claim_summary) for f in merged_findings}
    for finding in findings:
        if finding.trace_id in folded_traces:
            continue
        key = (finding.trace_id, finding.claim_summary)
        if key in seen_exact:
            continue
        merged_findings.append(finding)
        seen_exact.add(key)

    # Build phase 6.2, T-6.2-07. THE PRODUCER `open_threads` never had.
    #
    # The product-owner decision of 2026-09-01 is that a follow-up carries
    # the WHOLE THREAD forward. Most of that already existed and simply was
    # not obvious: `compressed_findings` carries what each turn ESTABLISHED
    # and `resolved_entities` carries what it resolved. What nothing carried
    # was what the user actually ASKED, so a follow-up saying "what variants
    # cause it" reached Think holding the entities and no record of the
    # sentence the pronoun points back at.
    #
    # An open thread IS a question the conversation has not closed, so this
    # needs no new field and no contract change: the entry is the question
    # text and `_render` already prints it as "Open: <question>".
    #
    # THE BOUNDS ARE THE ONES ALREADY DECLARED, which is what keeps "the
    # whole thread" inside Section 14.3's hard 1500-token budget.
    # `MAX_OPEN_THREADS` is 10 and `MAX_OPEN_THREAD_LENGTH` is 200, both
    # enforced by the contract's own validator, and `compact` drops the
    # OLDEST threads first when the budget bites. So the thread is carried
    # until the cap is reached and then the oldest turns fall off.
    #
    # Deduplicated only against the IMMEDIATELY PREVIOUS entry: asking the
    # same question twice in a row adds nothing, while asking it again after
    # three other turns is a real return to a topic and the thread should
    # show that it happened.
    threads = list(base.open_threads)
    trimmed = " ".join(question.split())[:MAX_OPEN_THREAD_LENGTH]
    if trimmed and (not threads or threads[-1] != trimmed):
        threads.append(trimmed)

    # UI fix set 7, item 7.2 (2026-09-13). The records this turn's answer
    # SHOWED, so a later go-deeper turn can put the ones not yet shown
    # first. Keyed by `source_url`, deduplicated against what is already
    # remembered, newest last, FIFO past the ceiling, and never rendered
    # into a prompt (`_render` does not read it). Bounded per item by the
    # contract's own validator.
    reported = list(base.reported_record_ids)
    seen_reported = set(reported)
    for record_id in reported_record_ids or []:
        record_id = record_id[:MAX_REPORTED_RECORD_ID_LENGTH]
        if record_id and record_id not in seen_reported:
            reported.append(record_id)
            seen_reported.add(record_id)

    return compact(
        SessionMemorySummary(
            session_id=session_id,
            resolved_entities=entities[-MAX_RESOLVED_ENTITIES:],
            compressed_findings=merged_findings[-MAX_COMPRESSED_FINDINGS:],
            open_threads=threads[-MAX_OPEN_THREADS:],
            reported_record_ids=reported[-MAX_REPORTED_RECORD_IDS:],
            token_budget=base.token_budget,
            last_updated=now,
        )
    )


def _check_owner_before_write(
    stored_owner: str | None, owner: str, session_id: str
) -> None:
    """Refuse a write onto a row a different principal owns.

    An UNOWNED row may be claimed. It is a row whose memory predates the
    ownership envelope or is absent, its contents are never served to anyone
    (`_unwrap` returns no payload for it), and its key already encodes this
    caller's identity, so claiming it discloses nothing and takes nothing
    from anyone.
    """
    if stored_owner is not None and stored_owner != owner:
        raise _ownership_refusal(session_id)


async def save_for_caller(
    summary: SessionMemorySummary,
    *,
    owner_id: str,
    store: SessionMemoryStore | None = None,
) -> None:
    """Persist a session's memory, refusing if the session is not the caller's.

    Goes through the SAME ownership check as the read path rather than
    trusting that whoever assembled the summary already checked. A write path
    that skips the check is how an authorization hole reopens after the read
    path was fixed: the two are separate code paths and only one of them was
    ever the finding.

    The check runs INSIDE the store's locked update rather than in a separate
    round trip before it. The shipped version awaited a read, compared, then
    awaited a write, so the owner could change between the two and the write
    would land against a principal the check never saw (F-4.5-J-16). Build
    phase 4.6's history migration, which moves a guest session to an account,
    is exactly that owner change.
    """
    owner = _require_owner_id(owner_id)
    active = store if store is not None else _default_store()

    def apply(
        stored_owner: str | None, stored_payload: dict[str, Any] | None
    ) -> dict[str, Any]:
        del stored_payload  # an explicit save replaces, it does not merge
        _check_owner_before_write(stored_owner, owner, summary.session_id)
        return summary.model_dump(mode="json")

    await active.update(summary.session_id, owner_id=owner, apply=apply)


async def remember_turn_for_caller(
    *,
    session_id: str,
    owner_id: str,
    now: datetime,
    resolved: list[ResolvedEntity],
    findings: list[CompressedFinding],
    question: str = "",
    reported_record_ids: list[str] | None = None,
    store: SessionMemoryStore | None = None,
) -> SessionMemorySummary | None:
    """Load, fold one turn in, and save, as a single locked operation.

    This is the call the end-of-run write path wants, and the reason it
    exists as one function rather than three: load, merge and save issued
    separately are a lock-free read-modify-write, so two turns of the same
    session finishing close together both read the old summary and the second
    write discards the first's entities and findings (F-4.5-A-15). The loss
    is silent and looks identical to the feature simply not remembering.

    Returns the summary that was written, or None when the turn carried
    nothing worth recording.
    """
    owner = _require_owner_id(owner_id)
    if not resolved and not findings:
        return None
    active = store if store is not None else _default_store()
    written: SessionMemorySummary | None = None

    def apply(
        stored_owner: str | None, stored_payload: dict[str, Any] | None
    ) -> dict[str, Any]:
        nonlocal written
        _check_owner_before_write(stored_owner, owner, session_id)
        existing = (
            _summary_from_payload(stored_payload) if stored_payload else None
        )
        written = merge_turn(
            existing,
            session_id=session_id,
            now=now,
            resolved=resolved,
            findings=findings,
            question=question,
            reported_record_ids=reported_record_ids,
        )
        return written.model_dump(mode="json")

    await active.update(session_id, owner_id=owner, apply=apply)
    return written


__all__ = [
    "ApplyMemory",
    "CallerIdentityRequired",
    "SessionMemoryStore",
    "SessionOwnershipError",
    "build_session_context",
    "compact",
    "count_tokens_for_tier",
    "count_tokens_worst_case",
    "injected_steps",
    "load_for_caller",
    "merge_turn",
    "remember_turn_for_caller",
    "save_for_caller",
    "session_row_key",
]
