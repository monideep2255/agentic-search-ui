"""The fold: build phase 4.3, ticket T-4.3-02.

Spec: `tracker/phase_4.3.md`'s "Module contracts", "Phase premise", and
"Premise gate design" sections; `adapters/mcp/server.py`'s `_fold_run_to_
response` is the controlling precedent this module deliberately duplicates
rather than imports (`tracker/phase_4.3.md`'s "Two duplications accepted"
note: extracting a shared fold would be the better architecture and is not
done here, so it does not refactor a shipped, heavily-reviewed surface
inside a phase whose review attention belongs on a new one).

Folds one run's event stream into a single typed result after the run
reaches a terminal event, or reports the run's state so far without
waiting. Never calls `core.run.run_streaming` directly: every function here
reads a run that some other caller (schema.py's `ask` resolver) has already
created via `RunRegistry.create_run`, and only ever subscribes to or reads
the buffered events of an EXISTING run.

Ownership is not this module's concern. `fold_run`/`fold_run_snapshot`/
`fold_citations` take a bare `run_id` (or, for `fold_citations`, an already-
resolved `RunEntry`) and fold whatever that run produced; the caller
(schema.py's resolvers) is responsible for verifying the caller owns the
run before ever reaching this module, the same separation REST's own `_get_
owned_run` enforces before its three routes touch `entry` at all.

The one rule every function here obeys, added 2026-08-17 after the build
phase 4.3 judge and adversary rounds (F-4.3-A-01 through A-08, A-13, J-05,
J-06): AGGREGATE TOWARD LESS CONFIDENCE, NEVER MORE. Where two inputs
disagree, the fold reports the least reassuring one. Where nothing
assessed something, it says so rather than defaulting to the benign value.
Where anything was dropped, shortened, failed or truncated anywhere
upstream, it discloses that it was. Every one of the ten findings above was
the same defect wearing a different field name: this surface reported more
confidence than its evidence supported.

Depends on:
    - system_03_search_agent.adapters.graphql.types (AskResult, Citation,
      CitationsExport, Disclosures, GraphQLTypeError, MAX_ANSWER_LENGTH,
      MAX_CITATIONS, MAX_DISCLOSURE_NOTES, MAX_DISCLOSURE_NOTE_LENGTH,
      RunResult, TrustSignal): the type layer this module folds events
      into.
    - system_03_search_agent.contracts.events (CitationPayload, DonePayload,
      ErrorPayload, Event, GuardPayload, TokenPayload, ToolResultPayload,
      TrustSignalPayload): the Section 2.3 payload models this module folds
      events against.
    - system_03_search_agent.core.run_registry (RunEntry, default_registry):
      the SAME registry instance every other surface uses. This module
      never builds a second registry.
    - system_03_search_agent.harness.cost_control
      (sanitize_event_for_end_user): run over every event before folding,
      so no cost figure can reach this surface even if a future regression
      added a cost-shaped field somewhere in the fold.
    - system_03_search_agent.synthesis.trust (aggregate): Section 8.3.4's
      most-restrictive-claim-wins rule, reused verbatim rather than a
      second implementation of the same floor logic `core/graph.py`'s
      `write_node` and `adapters/mcp/server.py` both already use.

Reads:
    - Nothing directly. Every read goes through `default_registry`.

Writes:
    - Nothing directly. `default_registry.subscribe`/`get_run` are read-only
      from this module's side; the run's background task is started by
      whichever caller created it.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from system_03_search_agent.adapters.graphql import types as types_module
from system_03_search_agent.adapters.graphql.types import (
    MAX_ANSWER_LENGTH,
    MAX_CITATIONS,
    MAX_DISCLOSURE_NOTE_LENGTH,
    MAX_DISCLOSURE_NOTES,
    AskResult,
    Citation,
    CitationsExport,
    Disclosures,
    RunResult,
    TrustSignal,
)
from system_03_search_agent.contracts.events import (
    CitationPayload,
    DonePayload,
    ErrorPayload,
    Event,
    GuardPayload,
    TokenPayload,
    ToolResultPayload,
    TrustSignalPayload,
)
from system_03_search_agent.core.run_registry import RunEntry, default_registry
from system_03_search_agent.harness.cost_control import sanitize_event_for_end_user
from system_03_search_agent.synthesis.trust import aggregate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exception base. Every exception this module raises subclasses this one,
# and every catch in this module (and in schema.py, once it exists)
# dispatches on this base rather than an enumerated subclass list, per the
# same tracker/phase_4.3.md instruction types.py's own GraphQLTypeError
# follows.
# ---------------------------------------------------------------------------


class FoldError(Exception):
    pass


class FoldTimeoutError(FoldError):
    pass


class RunNotYetFinishedError(FoldError):
    pass


# ---------------------------------------------------------------------------
# This surface's own persona-name stub. Mirrors adapters/web_sse/app.py's
# `_STUB_PERSONA_NAME = "Assistant"` value exactly, restated rather than
# imported: importing from `adapters.web_sse.app` would invert this
# package's dependency direction (that module mounts this one's router,
# T-4.3-07), the same reasoning tracker/phase_4.3.md gives for every other
# surface-local constant in this phase.
# ---------------------------------------------------------------------------

_PERSONA_NAME = "Assistant"

# F-4.1-A-06's precedent (adapters/mcp/server.py): a wall-clock bound on the
# fold loop itself, independent of any request-level timeout security.py's
# RequestTimeoutExtension enforces at the whole-operation level (T-4.3-04).
# Per tool-call-budgets.md, a call path without a declared timeout is not
# finished. Sized the same way MCP's was: the harness's own published worst
# case for one full Guardrail->Think->Plan->Act->Write loop (guard+think+
# plan+write at 15+15+45+45=120s, plus the largest query-class Act budget,
# "exploratory" at 120s) is 240s total, not an invented number.
_FOLD_LOOP_TIMEOUT_S = 240.0

# F-4.1-A-09's precedent: never interpolate ErrorPayload.message into a
# response this surface returns; it carries raw internal text (a live
# database host, port, and username, in the finding that established this
# rule). Keyed by error_class, a fixed literal per class, restated here
# rather than imported from adapters.mcp.server for the same dependency-
# direction reason `_PERSONA_NAME` above is restated rather than imported.
_FATAL_ERROR_DISCLOSURE: dict[str, str] = {
    "transient": "This query hit a temporary error before finishing. Retrying may succeed.",
    "recoverable": "This query could not complete as requested.",
    "unexpected": "This query failed unexpectedly before finishing.",
    "cancelled": "This query was stopped before it finished.",
}


# The same fixed-literal treatment for a NON-fatal error, which the fold
# used to consume and throw away entirely (F-4.3-A-04): a run whose Layer 1
# call failed and was skipped reported a clean, low-risk, grounded answer,
# with nothing in `disclosures`, nothing in `trust_signal.message`, and
# nothing in the answer text. `production-standards.md`'s layer-degradation
# gate requires the gap be explained in the answer, and this phase's own
# premise says anything the surface drops or shortens it says so. Keyed by
# `error_class` for the identical F-4.1-A-09 reason the fatal table above
# is: `ErrorPayload.message` carries raw internal text and is never
# interpolated. `ErrorPayload.source` is likewise never interpolated: it is
# a free-form 64-character string on the payload model, not a closed set,
# so it is exactly as untrusted as `message`.
_NON_FATAL_ERROR_DISCLOSURE: dict[str, str] = {
    "transient": (
        "Part of this run hit a temporary error and did not complete, so the "
        "answer above may be built on incomplete data. Retrying may succeed."
    ),
    "recoverable": (
        "Part of this run could not complete as requested, so the answer "
        "above may be built on incomplete data."
    ),
    "unexpected": (
        "Part of this run failed unexpectedly, so the answer above may be "
        "built on incomplete data."
    ),
    "cancelled": (
        "Part of this run was stopped before it finished, so the answer above "
        "may be built on incomplete data."
    ),
}


def _fatal_error_disclosure(error_payload: ErrorPayload) -> str:
    """Sanitized, external-facing sentence for a fatal `ErrorPayload`,
    keyed by `error_class`. `error_class` is a closed four-value `Literal`
    (`contracts.events.ErrorPayload`), so the `"unexpected"` fallback below
    is defensive completeness, never reachable today.
    """
    return _FATAL_ERROR_DISCLOSURE.get(
        error_payload.error_class, _FATAL_ERROR_DISCLOSURE["unexpected"]
    )


def _non_fatal_error_disclosure(error_class: str) -> str:
    """The non-fatal sibling of `_fatal_error_disclosure`, same shape, same
    fallback, so a future `error_class` added to the contract still reaches
    the caller as a disclosure rather than as silence.
    """
    return _NON_FATAL_ERROR_DISCLOSURE.get(
        error_class, _NON_FATAL_ERROR_DISCLOSURE["unexpected"]
    )


# Tri-state floor for TrustSignalPayload.triangulated, mirroring adapters/
# mcp/server.py's own _TRIANGULATION_SEVERITY: False (ran, did not concord)
# is worse than None (not evaluated), which is worse than True (ran,
# concords).
_TRIANGULATION_SEVERITY: dict[bool | None, int] = {False: 0, None: 1, True: 2}

# The risk-tier severity map, and F-4.3-A-01's fix. The previous aggregator
# was `"high" if any(t == "high") else "low"`, a boolean special case sitting
# three lines above a sibling field (`triangulated`) that already had a
# severity map. `TrustSignalPayload.risk_tier` is a bare `str`, NOT a
# two-value Literal, so that expression collapsed EVERY value that is not
# the exact string "high" into the most reassuring value the field has,
# including "unknown", the value this very phase introduced to mean "no
# assessment ran". An aggregate must never be more reassuring than its most
# uncertain input.
#
# Ordering, worst first:
#   an unrecognized value  a tier this surface has no severity for. Ranked
#                          WORST and reported back verbatim, so a future
#                          "medium" or "critical" can never be silently
#                          downgraded to "low" the way "unknown" was. This
#                          is the fix-by-category half: the map is closed,
#                          the treatment of everything outside it is not.
#   "high"                 an assessment ran and flagged a risk. Ranked
#                          worse than "unknown" ON PURPOSE: a known risk
#                          must never be hidden behind an honest shrug,
#                          which is the inversion judge finding J-09
#                          records on the frontend's own ranking.
#   "unknown"              no assessment ran.
#   "low"                  an assessment ran and cleared it.
_RISK_TIER_SEVERITY: dict[str, int] = {"high": 1, "unknown": 2, "low": 3}
_UNRECOGNIZED_RISK_TIER_SEVERITY = 0

# The honest value for "no risk assessment reached this surface".
UNASSESSED_RISK_TIER = "unknown"


def _risk_tier_severity(risk_tier: str) -> int:
    return _RISK_TIER_SEVERITY.get(risk_tier, _UNRECOGNIZED_RISK_TIER_SEVERITY)


def _floor_risk_tier(risk_tiers: list[str]) -> str:
    """The least reassuring of `risk_tiers`, reported verbatim. Empty means
    nothing assessed it, which is `UNASSESSED_RISK_TIER`, never `"low"`.
    """
    if not risk_tiers:
        return UNASSESSED_RISK_TIER
    return min(risk_tiers, key=_risk_tier_severity)


def _floor_trust_payloads(
    payloads: list[TrustSignalPayload],
    terminal_trust_outcome: str | None,
) -> TrustSignalPayload:
    """Fold EVERY trust assessment this run produced into one answer-level
    verdict, each field floored at the least reassuring input.

    Takes every signal, not only the claim-scoped ones. The previous
    version had two disjoint branches (an answer-scope signal wins
    outright, otherwise aggregate the claim-scoped ones), which meant a run
    emitting an answer-scope `risk_tier="low"` alongside a claim-scoped
    `"high"` reported "low", and a signal whose `scope` was neither value
    (contract-legal: `scope` is optional with a `None` default,
    `contracts/events.py`) matched no branch at all and was DISCARDED,
    warning text included, then replaced by a more reassuring synthetic one
    (F-4.3-A-02). One floor over every assessment removes both shapes at
    once, and removes the branch-per-scope-value list that would have grown
    a new gap at the first scope value nobody listed.

    The single-signal fast path returns the payload UNCHANGED (message,
    `fallback_link` and `citation_id` intact) rather than rebuilding it, so
    the ordinary one-answer-scope-signal run folds exactly as it always
    did. A lone claim-scoped signal is not on that path: it still gets
    re-scoped to "answer", since it is being reported as the answer-level
    verdict.
    """
    if len(payloads) == 1 and payloads[0].scope != "claim":
        return payloads[0]
    messages: list[str] = []
    for payload in payloads:
        if payload.message and payload.message not in messages:
            messages.append(payload.message)
    merged_message = " ".join(messages)[:MAX_DISCLOSURE_NOTE_LENGTH] or None
    return TrustSignalPayload(
        outcome=aggregate(
            [payload.outcome for payload in payloads],
            default=terminal_trust_outcome or "refuse",  # type: ignore[arg-type]
        ),
        risk_tier=_floor_risk_tier([payload.risk_tier for payload in payloads]),
        grounded=all(payload.grounded for payload in payloads),
        triangulated=min(
            [payload.triangulated for payload in payloads],
            key=lambda value: _TRIANGULATION_SEVERITY[value],
        ),
        citation_id=None,
        scope="answer",
        message=merged_message,
        fallback_link=next(
            (payload.fallback_link for payload in payloads if payload.fallback_link), None
        ),
    )


def _floor_trust_signal(
    trust_signal: TrustSignalPayload,
    *,
    outcome_floor: str,
    risk_tier_floor: str,
    grounded: bool = False,
) -> TrustSignalPayload:
    """Lower `trust_signal` to at most the named floors. Every caller that
    needs to say "this run cannot be vouched for" goes through this one
    function, so no caller can accidentally RAISE a verdict while trying to
    lower it.

    That is not hypothetical. The previous fatal-error floor set
    `risk_tier="high"` unconditionally, which is a floor only while "high"
    is the worst value the field can hold; against an unrecognized tier
    (severity 0 under `_RISK_TIER_SEVERITY`) it was an upgrade toward
    reassurance inside a function whose whole job is the opposite.
    """
    return trust_signal.model_copy(
        update={
            "outcome": aggregate([trust_signal.outcome, outcome_floor]),  # type: ignore[list-item]
            "grounded": trust_signal.grounded and grounded,
            "risk_tier": _floor_risk_tier([trust_signal.risk_tier, risk_tier_floor]),
        }
    )


def _floor_trust_signal_for_fatal_error(trust_signal: TrustSignalPayload) -> TrustSignalPayload:
    """A fatal error interrupted the run, so whatever partial answer text
    exists cannot be vouched for as complete or grounded. Floors, never
    raises: `outcome` is no better than `"flag"`, `grounded` is forced
    `False`, `risk_tier` no better than `"high"`. Mirrors `adapters/mcp/
    server.py`'s `_floor_trust_signal_for_fatal_error` (F-4.1-A-01/A-05).
    """
    return _floor_trust_signal(
        trust_signal, outcome_floor="flag", risk_tier_floor="high", grounded=False
    )


def _truncate_on_word_boundary(text: str, max_length: int) -> str:
    """Truncate `text` to at most `max_length` characters, preferring the
    last whitespace boundary within the cap over a hard mid-word cut.
    Falls back to a hard cut when no boundary exists in at least the back
    half of the budget, so a single anomalously long token cannot collapse
    the answer to a sliver. Mirrors `adapters/mcp/server.py`'s `_truncate_
    on_word_boundary` exactly.
    """
    if len(text) <= max_length:
        return text
    truncated = text[:max_length]
    last_space = truncated.rfind(" ")
    if last_space > max_length // 2:
        truncated = truncated[:last_space]
    return truncated.rstrip()


# Appended when the merged message does not fit `TrustSignalPayload.
# message`'s own 500-character bound. A surface whose premise is "if we
# drop something we say so" must not truncate its own saying-so undisclosed
# (judge Section 1, clause C5, hole 3).
_MESSAGE_TRUNCATION_MARKER = " [further disclosures omitted, see notes]"


def _merge_disclosure_messages(existing: str | None, notes: list[str]) -> str:
    """Fold `notes` into `trust_signal.message`, appending to whatever was
    already there (a refusal's own message, Section 8.4) rather than
    overwriting it, then hard-caps at `TrustSignalPayload.message`'s own
    500-char max_length so a combination of disclosures can never fail
    that field's own validation when re-constructed via `model_copy`.

    The cut itself is disclosed, and the full text always survives in
    `disclosures.notes` regardless.
    """
    merged = " ".join(([existing] if existing else []) + notes)
    if len(merged) <= MAX_DISCLOSURE_NOTE_LENGTH:
        return merged
    keep = MAX_DISCLOSURE_NOTE_LENGTH - len(_MESSAGE_TRUNCATION_MARKER)
    return merged[:keep].rstrip() + _MESSAGE_TRUNCATION_MARKER


def _fallback_answer_text(
    *,
    guard_payload: GuardPayload | None,
    error_payload: ErrorPayload | None,
    run_finished: bool,
) -> str:
    """Built only when a run produced no `token` events at all: a
    guardrail-level refusal (`guard` and `done`, no `token`), a fatal error
    before Write ever ran, or a snapshot read of a run that has not got
    there yet. Cite-or-refuse still holds either way; this is defensive
    completeness for the `answer` field, which this surface's types require
    present on every result, never a second refusal wording competing with
    `write_node`'s own.

    `run_finished` exists because the last sentence used to assert "the run
    ended" on a `Query.run` poll of a HEALTHY IN-PROGRESS run, in the same
    response whose own `finished` field said `False` (judge finding J-07).
    Two fields on one result contradicting each other about one run is the
    same class of defect as every other finding this fold was corrected
    for, just pointed at the answer text instead of the trust signal.
    """
    if guard_payload is not None and not guard_payload.passed:
        reason_suffix = f" ({guard_payload.reason})" if guard_payload.reason else ""
        return (
            "This question could not be answered: it did not pass this "
            f"system's content guardrail{reason_suffix}."
        )
    if error_payload is not None:
        return _fatal_error_disclosure(error_payload)
    if not run_finished:
        return (
            "This run has not finished yet and has not produced any answer "
            "text so far; query it again once it finishes."
        )
    return "This query could not be completed: the run ended before producing an answer."


def _build_citation_from_event(event: Event) -> Citation | None:
    """Build one `Citation` from a `citation`-typed `Event`, degrading to
    `None` (logged, never raised) on a malformed payload rather than
    breaking the whole fold over one bad record. Mirrors the defensive
    posture `adapters/web_sse/app.py`'s citations route already takes
    (F-4.0-J-06), collapsed to a single `except ValueError:` rather than
    an enumerated `(TypeError, ValueError)` tuple: `event.payload` is
    already typed `dict[str, Any]` on the `Event` model (never a non-
    mapping), so the only realistic failure here is a validation failure,
    and Pydantic's own `ValidationError` (raised by `CitationPayload(**...
    )`) already subclasses `ValueError`, as does `types_module.
    GraphQLTypeError` (raised by `Citation.from_payload`). One base class
    catches both without an enumerated list to drift out of sync with its
    raiser, the exact failure tracker/phase_4.3.md names from build phase
    4.2.
    """
    try:
        payload = CitationPayload(**event.payload)
        return types_module.Citation.from_payload(payload)
    except ValueError:
        logger.warning(
            "a citation event's payload failed validation while folding; "
            "omitted from the result"
        )
        return None


# ---------------------------------------------------------------------------
# Citation collection, in ONE place. Both `_consume_event` (for `ask` and
# `run`) and `fold_citations` (for `citations`) go through the collector
# below rather than each writing its own accept-or-drop loop, because they
# had written two, and the two had already drifted: the fold counted what
# it dropped and the export did not, so the export reported
# `exportTruncated: false` while silently omitting a rejected citation
# (judge finding J-06, phase premise clause C5).
#
# Every drop is recorded against a REASON, and the reason is what the
# disclosure is built from. That is F-4.3-J-05's fix by construction rather
# than by wording: the old note attributed every omission to the
# 50-citation cap, including omissions caused by a rejected payload, which
# told the caller the surface was withholding good evidence for capacity
# when in fact it had REJECTED that evidence as untrustworthy. Those are
# opposite meanings on a trust surface.
# ---------------------------------------------------------------------------

_OMISSION_INVALID = "invalid"
_OMISSION_DUPLICATE_ID = "duplicate_id"
_OMISSION_CAP = "cap"

# Reasons are emitted in this order when several fire on one run. Any
# reason NOT listed here is still disclosed, through the fallback wording
# below and sorted after these: an omission reason a future change adds
# must not be able to vanish just because nobody added it to a list.
_OMISSION_ORDER = (_OMISSION_INVALID, _OMISSION_DUPLICATE_ID, _OMISSION_CAP)

_OMISSION_NOTES: dict[str, str] = {
    _OMISSION_CAP: (
        "{count} citation(s) beyond this surface's {cap}-citation limit were "
        "omitted; some citation markers in the answer above may not resolve "
        "to a returned citation."
    ),
    _OMISSION_INVALID: (
        "{count} citation(s) were REJECTED because their payload failed this "
        "surface's own validation (an off-host source URL, or a field outside "
        "its declared bounds) and are not included; some citation markers in "
        "the answer above may not resolve to a returned citation."
    ),
    _OMISSION_DUPLICATE_ID: (
        "{count} citation(s) repeated a citation id already returned and were "
        "omitted, so that no citation marker resolves to two different "
        "sources making different claims."
    ),
}

_OMISSION_FALLBACK_NOTE = (
    "{count} citation(s) were omitted for a reason this surface has no "
    "specific wording for; some citation markers in the answer above may not "
    "resolve to a returned citation."
)

_DUPLICATE_DISPLAY_INDEX_NOTE = (
    "{count} returned citation(s) share a display index with another returned "
    "citation, so a marker like [1] in the answer above may resolve to more "
    "than one source."
)


@dataclass
class _CitationCollector:
    """Accepts `citation` events one at a time, deduplicated by the join key
    `contracts/events.py` documents (`citation_id`), capped at
    `MAX_CITATIONS`, and recording WHY each rejected event was rejected.

    The duplicate check exists because two citation events sharing one
    `citation_id` and one `display_index` were both returned, with opposite
    claim text and no disclosure (F-4.3-A-07). The marker `[1]` in the
    answer then resolved to two sources asserting opposite things and the
    caller had no way to pick, and a claim-scoped trust signal naming that
    `citation_id` could not be bound to one citation either.
    """

    events_seen: int = 0
    citations: list[Citation] = field(default_factory=list)
    omissions: dict[str, int] = field(default_factory=dict)
    duplicate_display_indexes: int = 0
    seen_ids: set[str] = field(default_factory=set)
    seen_display_indexes: set[int] = field(default_factory=set)

    @property
    def omitted_total(self) -> int:
        return sum(self.omissions.values())

    def _omit(self, reason: str) -> None:
        self.omissions[reason] = self.omissions.get(reason, 0) + 1

    def accept(self, event: Event) -> None:
        self.events_seen += 1
        citation = _build_citation_from_event(event)
        if citation is None:
            self._omit(_OMISSION_INVALID)
            return
        if citation.citation_id in self.seen_ids:
            self._omit(_OMISSION_DUPLICATE_ID)
            return
        if len(self.citations) >= MAX_CITATIONS:
            self._omit(_OMISSION_CAP)
            return
        if citation.display_index in self.seen_display_indexes:
            # Kept, not dropped: it is real evidence with a real, distinct
            # id. The ambiguity is in the MARKER, so the marker is what the
            # disclosure names.
            self.duplicate_display_indexes += 1
        self.seen_ids.add(citation.citation_id)
        self.seen_display_indexes.add(citation.display_index)
        self.citations.append(citation)

    def disclosure_notes(self) -> list[str]:
        notes: list[str] = []
        ordered = [reason for reason in _OMISSION_ORDER if reason in self.omissions]
        ordered += sorted(reason for reason in self.omissions if reason not in _OMISSION_ORDER)
        for reason in ordered:
            template = _OMISSION_NOTES.get(reason, _OMISSION_FALLBACK_NOTE)
            notes.append(template.format(count=self.omissions[reason], cap=MAX_CITATIONS))
        if self.duplicate_display_indexes:
            notes.append(
                _DUPLICATE_DISPLAY_INDEX_NOTE.format(count=self.duplicate_display_indexes)
            )
        return notes


# ---------------------------------------------------------------------------
# The shared accumulator. Both fold_run (live, waits for a terminal event)
# and fold_run_snapshot (buffered, does not wait) consume the same event
# sequence through the same `_consume_event` function and the same
# `_finalize` function, AND both stop at the same place: the run's terminal
# event.
#
# That last clause used to be false, and the module comment that used to
# sit here asserted the two "can never silently diverge on what folding
# means" while they diverged on WHICH EVENTS THEY CONSUME (F-4.3-A-13).
# `subscribe` stops at the terminal event; `entry.events` is the whole
# buffer including anything appended after it. A stream that emitted
# `done(trust_outcome="refuse")` and then more tokens, a citation and an
# answer-scope `trust_signal(grounded=True)` gave `ask` a refusal and
# `run` the post-terminal text reported as grounded, for the SAME run id,
# one second apart. `_consume_event` now raises `terminal_event_seen` and
# both loops break on it, so the two consume an identical prefix by
# construction rather than by a comment claiming they do. The
# `test_ask_and_run_agree_on_the_same_finished_run` arm is what holds it.
# ---------------------------------------------------------------------------


@dataclass
class _Accumulator:
    answer_parts: list[str] = field(default_factory=list)
    citations_collector: _CitationCollector = field(default_factory=_CitationCollector)
    trust_signals: list[TrustSignalPayload] = field(default_factory=list)
    unscoped_trust_signals: int = 0
    terminal_trust_outcome: str | None = None
    terminal_event_seen: bool = False
    guard_payload: GuardPayload | None = None
    fatal_error_payload: ErrorPayload | None = None
    non_fatal_error_classes: list[str] = field(default_factory=list)
    truncated_tool_results: int = 0
    malformed_events: int = 0


def _parse_payload(acc: _Accumulator, event: Event, model: type[Any]) -> Any | None:
    """Parse one event's payload into its Section 2.3 model, degrading to
    `None` (logged AND disclosed, never raised) on a malformed payload.

    `_consume_event` used to wrap only its citation branch this way. Every
    other branch constructed its payload model bare, so one malformed
    `token`, `trust_signal`, `guard`, `error` or `done` payload raised out
    of the whole fold and `MaskErrors` turned the entire answer into "This
    request could not be completed due to an internal error" (judge finding
    J-08). The whole answer was lost where one record could have been
    dropped and disclosed. This is the same asymmetry every other finding
    in this round turned out to be: a principle applied to one branch and
    not to its neighbours.
    """
    try:
        return model(**event.payload)
    except ValueError:
        acc.malformed_events += 1
        logger.warning(
            "a %s event's payload failed validation while folding; dropped from the fold",
            event.type,
        )
        return None


def _consume_event(acc: _Accumulator, event: Event) -> None:
    """Fold one event into `acc`, mutating it in place.

    Every event is run through `sanitize_event_for_end_user` first
    (unconditionally: this surface's `operator_mode` is a parameter kept
    only for interface symmetry with the core, since the caller pins it
    `False` in code, T-4.3's own scope reading), which drops a `cost`
    event entirely and redacts `done.total_cost_usd`. `think`, `plan` and
    `tool_start` carry nothing this surface's schema has a field for and
    are folded out entirely by matching no branch below.

    `tool_result` is NOT folded out, and that is a change. It used to be,
    on the reasoning that it "carries nothing this surface's schema has a
    field for", but `ToolResultPayload.truncated` is precisely a "the data
    behind this answer was cut short" flag and `Disclosures` is precisely
    the channel for a fact with no other field (F-4.3-A-05). An answer
    reading "only BRCA1 is associated [1]" built from a tool that saw 500
    rows and returned 25 is the exact shape this surface must not present
    as complete.
    """
    sanitized = sanitize_event_for_end_user(event)
    if sanitized is None:
        return
    event = sanitized
    if event.type == "token":
        payload = _parse_payload(acc, event, TokenPayload)
        if payload is not None:
            acc.answer_parts.append(payload.text)
    elif event.type == "citation":
        acc.citations_collector.accept(event)
    elif event.type == "trust_signal":
        candidate = _parse_payload(acc, event, TrustSignalPayload)
        if candidate is not None:
            # No scope value is discarded. `scope` is optional with a None
            # default (`contracts/events.py`), so a scope-less signal is a
            # contract-legal event, and the old two-branch shape dropped it
            # on the floor and then manufactured a MORE REASSURING synthetic
            # signal in its place (F-4.3-A-02: a "flag / high / not
            # grounded / this answer contradicts its sources" assessment
            # reached the caller as "answer / grounded / no message"). Every
            # signal now reaches the floor in `_floor_trust_payloads`; the
            # only thing scope decides is whether it is re-labelled, and an
            # unrecognized scope is disclosed rather than assumed.
            acc.trust_signals.append(candidate)
            if candidate.scope not in ("claim", "answer"):
                acc.unscoped_trust_signals += 1
    elif event.type == "guard":
        payload = _parse_payload(acc, event, GuardPayload)
        if payload is not None:
            acc.guard_payload = payload
    elif event.type == "error":
        payload = _parse_payload(acc, event, ErrorPayload)
        if payload is None:
            return
        if payload.fatal:
            acc.fatal_error_payload = payload
            acc.terminal_event_seen = True
        else:
            # Consumed and thrown away before F-4.3-A-04: a run whose graph
            # call failed and whose Layer 1 was skipped reported a clean,
            # low-risk, grounded answer with an empty `notes`.
            acc.non_fatal_error_classes.append(payload.error_class)
    elif event.type == "tool_result":
        payload = _parse_payload(acc, event, ToolResultPayload)
        if payload is not None and payload.truncated:
            acc.truncated_tool_results += 1
    elif event.type == "done":
        payload = _parse_payload(acc, event, DonePayload)
        if payload is not None:
            acc.terminal_trust_outcome = payload.trust_outcome
        acc.terminal_event_seen = True


_NO_ASSESSMENT_NOTE = (
    "No trust assessment of any scope reached this surface for this run, so "
    "its answer is reported as ungrounded and its risk tier as unknown "
    "rather than assumed to be safe."
)

_UNSCOPED_TRUST_SIGNAL_NOTE = (
    "{count} trust assessment(s) for this run carried no recognized scope and "
    "were folded into the answer-level verdict rather than discarded."
)

_MALFORMED_EVENT_NOTE = (
    "{count} event(s) in this run could not be read by this surface and were "
    "dropped from the answer above."
)

_TRUNCATED_TOOL_RESULT_NOTE = (
    "{count} tool result(s) behind this answer were truncated by the tool "
    "itself, so the answer above may not reflect every matching record."
)

_RUN_ENDED_WITHOUT_TERMINAL_EVENT_NOTE = (
    "This run ended without a terminal event, so the answer above is PARTIAL "
    "and this surface cannot vouch for it as complete."
)

_RUN_NOT_FINISHED_NOTE = (
    "This run has not finished, so the answer above is a partial snapshot and "
    "may change."
)

_NOTES_TRUNCATION_NOTE = (
    "{count} further disclosure(s) did not fit this surface's "
    "{limit}-disclosure limit and were omitted."
)


def _cap_notes(notes: list[str]) -> list[str]:
    """Cap `notes` at `MAX_DISCLOSURE_NOTES`, disclosing the cut itself.

    A surface whose premise is "anything the surface drops or shortens, it
    says so" must not silently drop its own disclosures at a cap (judge
    Section 1, clause C5, hole 3).
    """
    if len(notes) <= MAX_DISCLOSURE_NOTES:
        return notes
    kept = notes[: MAX_DISCLOSURE_NOTES - 1]
    kept.append(
        _NOTES_TRUNCATION_NOTE.format(
            count=len(notes) - len(kept), limit=MAX_DISCLOSURE_NOTES
        )
    )
    return kept


def _finalize(
    acc: _Accumulator, *, run_finished: bool
) -> tuple[str, TrustSignal, list[Citation], Disclosures]:
    """Turn an `_Accumulator` that has consumed some (possibly incomplete)
    prefix of a run's events into the four fields every result type on
    this surface carries: `answer`, `trust_signal`, `citations`,
    `disclosures`.

    Every floor below only ever LOWERS a verdict. No path in this function
    raises one, and that is the invariant to preserve when editing it.
    """
    collector = acc.citations_collector
    citations = collector.citations
    notes: list[str] = []

    if acc.trust_signals:
        trust_payload = _floor_trust_payloads(acc.trust_signals, acc.terminal_trust_outcome)
    else:
        trust_payload = TrustSignalPayload(
            outcome=acc.terminal_trust_outcome or "refuse",  # type: ignore[arg-type]
            # "unknown", never a hardcoded "low": no assessment ran on this
            # path (no trust_signal event of any scope arrived at all), so
            # asserting a specific risk tier from nothing is exactly
            # F-4.1-J3-02's still-open defect on the sibling MCP surface.
            risk_tier=UNASSESSED_RISK_TIER,
            # F-4.3-A-03. This used to read `bool(citations) and outcome ==
            # "answer"`, i.e. it asserted the answer was GROUNDED because a
            # citation event went past, on the one path where no grounding
            # assessment ran at all. "A citation exists" is not "the answer
            # is tied to it"; deciding that is the grounding step's job and
            # this run never performed it. The line directly above carries a
            # comment explaining why asserting an unassessed risk tier is a
            # defect, and the next line went on to assert an unassessed
            # grounding verdict. `grounded` is a plain `bool` on both the
            # payload and this surface's schema, so there is no tri-state to
            # report here; False plus the explicit note below is the honest
            # pair.
            grounded=False,
            triangulated=None,
            citation_id=None,
            scope="answer",
        )
        notes.append(_NO_ASSESSMENT_NOTE)

    # The run's own terminal verdict is an assessment too, and it floors the
    # signal like any other. A `done(trust_outcome="refuse")` alongside a
    # trust_signal claiming "answer" is a disagreement, and this surface
    # reports the least reassuring side of a disagreement.
    if acc.terminal_trust_outcome is not None:
        floored_outcome = aggregate(
            [trust_payload.outcome, acc.terminal_trust_outcome]  # type: ignore[list-item]
        )
        if floored_outcome != trust_payload.outcome:
            trust_payload = trust_payload.model_copy(update={"outcome": floored_outcome})

    # Cite-or-refuse floor, unconditional: never report grounded=true or
    # outcome="answer" on a run where no citation actually survived,
    # regardless of what the run's own trust_signal event claims. A run CAN
    # emit an answer-scope trust_signal claiming outcome="answer" while
    # citing nothing, and this floor corrects that claim rather than
    # trusting it, exactly the shape `tracker/phase_4.3.md`'s "an uncited
    # answer is never reported as grounded" gate arm exercises.
    if not citations:
        update: dict[str, object] = {}
        if trust_payload.outcome == "answer":
            update["outcome"] = "refuse"
        if trust_payload.grounded:
            update["grounded"] = False
        if update:
            trust_payload = trust_payload.model_copy(update=update)

    answer_text = "".join(acc.answer_parts).strip()
    if not answer_text:
        answer_text = _fallback_answer_text(
            guard_payload=acc.guard_payload,
            error_payload=acc.fatal_error_payload,
            run_finished=run_finished,
        )

    answer_truncated = False
    if len(answer_text) > MAX_ANSWER_LENGTH:
        answer_text = _truncate_on_word_boundary(answer_text, MAX_ANSWER_LENGTH)
        answer_truncated = True
        notes.append(
            f"The answer above was truncated to this surface's {MAX_ANSWER_LENGTH}-"
            "character limit; some content was omitted."
        )

    # Built from the collector's own per-reason tally, so the sentence the
    # caller reads is the reason the citation was actually dropped.
    citations_omitted = collector.omitted_total
    notes.extend(collector.disclosure_notes())

    if acc.truncated_tool_results:
        notes.append(
            _TRUNCATED_TOOL_RESULT_NOTE.format(count=acc.truncated_tool_results)
        )

    for error_class in dict.fromkeys(acc.non_fatal_error_classes):
        notes.append(_non_fatal_error_disclosure(error_class))

    if acc.malformed_events:
        notes.append(_MALFORMED_EVENT_NOTE.format(count=acc.malformed_events))

    if acc.unscoped_trust_signals:
        notes.append(
            _UNSCOPED_TRUST_SIGNAL_NOTE.format(count=acc.unscoped_trust_signals)
        )

    if not acc.terminal_event_seen:
        # F-4.3-A-08 (the run died mid-stream, so the caller got partial
        # answer text shaped exactly like an ordinary guardrail refusal) and
        # judge J-07 (a healthy in-progress poll, which is not a defect but
        # is also not something to report as a final verdict). Both are the
        # same missing fact: nothing here has been vouched for yet.
        notes.append(
            _RUN_ENDED_WITHOUT_TERMINAL_EVENT_NOTE
            if run_finished
            else _RUN_NOT_FINISHED_NOTE
        )
        trust_payload = _floor_trust_signal(
            trust_payload,
            outcome_floor="refuse",
            risk_tier_floor=UNASSESSED_RISK_TIER,
            grounded=False,
        )

    if acc.fatal_error_payload is not None:
        trust_payload = _floor_trust_signal_for_fatal_error(trust_payload)
        notes.append(_fatal_error_disclosure(acc.fatal_error_payload))

    notes = _cap_notes(notes)
    if notes:
        trust_payload = trust_payload.model_copy(
            update={"message": _merge_disclosure_messages(trust_payload.message, notes)}
        )

    disclosures = Disclosures(
        answer_truncated=answer_truncated,
        citations_omitted=citations_omitted,
        notes=notes,
    )
    return answer_text, TrustSignal.from_payload(trust_payload), citations, disclosures


# ---------------------------------------------------------------------------
# The three public entry points.
# ---------------------------------------------------------------------------


async def fold_run(run_id: str, *, operator_mode: bool = False) -> AskResult:
    """Subscribe to `run_id` via `default_registry.subscribe` and fold its
    ENTIRE event stream into one `AskResult`, waiting for the run's
    terminal event (`done`, or a fatal `error`).

    Never calls `core.run.run_streaming`: `run_id` names a run some other
    caller has already created via `RunRegistry.create_run`.

    `operator_mode` is accepted only for interface symmetry with the rest
    of the core (`RequestContext.operator_mode`); this surface's own
    resolver pins the run's own `RequestContext.operator_mode` to `False`
    in code (mirroring `adapters/mcp/server.py`'s identical choice), so
    every event is sanitized for an end user regardless of what this
    parameter is passed as. It is never read by this function's own logic.

    Raises:
        FoldTimeoutError: this run's fold loop exceeded `_FOLD_LOOP_
            TIMEOUT_S`, a wall-clock bound independent of any per-request
            timeout `security.py`'s `RequestTimeoutExtension` enforces at
            the whole-GraphQL-operation level.
    """
    del operator_mode  # accepted for symmetry only; see docstring above.
    acc = _Accumulator()
    try:
        async with asyncio.timeout(_FOLD_LOOP_TIMEOUT_S):
            async for event in default_registry.subscribe(run_id, after_seq=-1):
                _consume_event(acc, event)
                if acc.terminal_event_seen:
                    # `subscribe` already returns at the terminal event, so
                    # this break is redundant against today's registry and
                    # is here anyway: it is the SAME stopping rule
                    # `fold_run_snapshot` applies to the raw buffer, stated
                    # in one place, so the two entry points cannot diverge
                    # on which events they consume the way F-4.3-A-13 found
                    # them doing.
                    break
    except TimeoutError:
        raise FoldTimeoutError(
            f"this query exceeded the GraphQL surface's {_FOLD_LOOP_TIMEOUT_S:.0f}s "
            "wall-clock fold budget and was aborted before finishing; retry with a "
            "narrower question, or use the REST/SSE surface to watch the run's own "
            "event stream instead of waiting for one final result"
        ) from None

    # `subscribe` returns only at the run's terminal event or once the run
    # has ended, so by this line the run is over either way.
    answer_text, trust_signal, citations, disclosures = _finalize(acc, run_finished=True)
    return AskResult(
        run_id=run_id,
        persona_name=_PERSONA_NAME,
        answer=answer_text,
        trust_signal=trust_signal,
        citations=citations,
        disclosures=disclosures,
    )


async def fold_run_snapshot(run_id: str, *, operator_mode: bool = False) -> RunResult:
    """Report `run_id`'s folded state as of RIGHT NOW, without waiting for
    the run to finish.

    Reads `entry.events` directly, the same buffered-event access path
    `adapters/web_sse/app.py`'s citations route uses (`entry.events`, never
    `default_registry.subscribe`, which would await future events this
    function must not wait for). `RunResult.finished` reflects `entry.
    finished` as observed at the moment this function reads it; a
    concurrent caller could observe a different value a moment later, the
    same inherent race any snapshot read has.

    `operator_mode` is accepted for the same interface-symmetry reason
    `fold_run` accepts it; see that function's docstring.

    Raises:
        system_03_search_agent.core.run_registry.RunNotFoundError: `run_id`
            was never created by this registry, or has since been evicted.
            Propagated unchanged: this is the registry's own well-known
            exception type, already handled by every caller that resolves
            ownership before reaching this function.
    """
    del operator_mode  # accepted for symmetry only; see fold_run's docstring.
    entry = default_registry.get_run(run_id)
    acc = _Accumulator()
    for event in entry.events:
        _consume_event(acc, event)
        if acc.terminal_event_seen:
            # STOPS AT THE TERMINAL EVENT, exactly as `default_registry.
            # subscribe` does for `fold_run`. Without this, this function
            # folded the WHOLE buffer including everything appended after
            # the terminal event, so `ask` and `run` returned contradictory
            # answers for one finished run and `run` reported post-terminal
            # text as `grounded: true` on a run `ask` had refused
            # (F-4.3-A-13).
            break
    answer_text, trust_signal, citations, disclosures = _finalize(
        acc, run_finished=entry.finished
    )
    return RunResult(
        run_id=run_id,
        finished=entry.finished,
        answer=answer_text,
        trust_signal=trust_signal,
        citations=citations,
        disclosures=disclosures,
    )


def fold_citations(entry: RunEntry) -> CitationsExport:
    """Mirror `GET /v1/query/{run_id}/citations`'s behavior over an
    already-resolved `RunEntry`, including the two facts REST discloses as
    HTTP response headers (`X-Citations-Export-Truncated`, `X-Run-
    Cancelled`), which become explicit fields here since GraphQL has no
    header channel.

    Synchronous and takes `entry` directly, not `run_id`: the caller
    (schema.py's `citations` resolver) has already resolved and owner-
    checked the entry via `default_registry.get_run` before calling this,
    the same "ownership is not this module's concern" split `fold_run`/
    `fold_run_snapshot` also hold, and there is no waiting to do here: a
    citations export only makes sense once the run has reached a terminal
    state, checked below.

    Raises:
        RunNotYetFinishedError: `entry` has not reached a terminal state
            yet. Mirrors REST's `409` for the identical precondition.
    """
    if not entry.finished:
        raise RunNotYetFinishedError(
            f"run {entry.run_id!r} has not reached a terminal state yet; "
            "query it again once the run finishes (a done event, or a "
            "stop or cancellation)"
        )

    collector = _CitationCollector()
    for event in entry.events:
        sanitized = sanitize_event_for_end_user(event)
        if sanitized is None:
            continue
        if sanitized.type == "citation":
            collector.accept(sanitized)
        if sanitized.type == "done" or (
            sanitized.type == "error" and sanitized.payload.get("fatal") is True
        ):
            # The same stopping rule `fold_run`/`fold_run_snapshot` apply
            # (F-4.3-A-13): a citation appended after the run's terminal
            # event is not part of what the run answered, so it is not part
            # of what the run's citation export contains either.
            break

    return CitationsExport(
        run_id=entry.run_id,
        # ANY omission, not only a count over the cap. This export used to
        # report `exportTruncated: false` while silently dropping a citation
        # whose payload failed validation, and `CitationsExport` carries no
        # `disclosures` field that could have said otherwise, so the phase
        # premise clause "anything the surface drops or shortens, it says
        # so" failed outright on this operation (judge finding J-06, clause
        # C5). "Truncated" is the honest reading for an export that is
        # shorter than what the run produced, whatever shortened it.
        #
        # The WHY is now carried too, in `disclosures` below: this comment
        # previously recorded that gap as open, because the field it needed
        # lived in `types.py`, another agent's file at the time. The field
        # exists now, so the collector's own per-reason wording is wired
        # through rather than left to a bare boolean.
        export_truncated=collector.omitted_total > 0,
        run_cancelled=entry.cancelled,
        citations=collector.citations,
        # `answer_truncated` is False by construction: this operation
        # returns no answer text, so there is no answer here to truncate.
        # The other two fields come from the same collector that built the
        # citation list, so the count, the reasons and the list can never
        # disagree about one export. `_cap_notes` is applied for the same
        # reason `_finalize` applies it: a surface whose premise is "if it
        # drops something it says so" must not silently drop its own
        # disclosures at their cap.
        disclosures=Disclosures(
            answer_truncated=False,
            citations_omitted=collector.omitted_total,
            notes=_cap_notes(collector.disclosure_notes()),
        ),
    )
