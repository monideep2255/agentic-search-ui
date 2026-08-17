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

Depends on:
    - system_03_search_agent.adapters.graphql.types (AskResult, Citation,
      CitationsExport, Disclosures, GraphQLTypeError, MAX_ANSWER_LENGTH,
      MAX_CITATIONS, MAX_DISCLOSURE_NOTES, MAX_DISCLOSURE_NOTE_LENGTH,
      RunResult, TrustSignal): the type layer this module folds events
      into.
    - system_03_search_agent.contracts.events (CitationPayload, DonePayload,
      ErrorPayload, Event, GuardPayload, TokenPayload, TrustSignalPayload):
      the Section 2.3 payload models this module folds events against.
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
from typing import Literal

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


def _fatal_error_disclosure(error_payload: ErrorPayload) -> str:
    """Sanitized, external-facing sentence for a fatal `ErrorPayload`,
    keyed by `error_class`. `error_class` is a closed four-value `Literal`
    (`contracts.events.ErrorPayload`), so the `"unexpected"` fallback below
    is defensive completeness, never reachable today.
    """
    return _FATAL_ERROR_DISCLOSURE.get(
        error_payload.error_class, _FATAL_ERROR_DISCLOSURE["unexpected"]
    )


# Tri-state floor for TrustSignalPayload.triangulated, mirroring adapters/
# mcp/server.py's own _TRIANGULATION_SEVERITY: False (ran, did not concord)
# is worse than None (not evaluated), which is worse than True (ran,
# concords).
_TRIANGULATION_SEVERITY: dict[bool | None, int] = {False: 0, None: 1, True: 2}


def _aggregate_claim_trust_signals(
    claim_signals: list[TrustSignalPayload],
    terminal_trust_outcome: str | None,
) -> TrustSignalPayload:
    """Synthesize an answer-scope trust signal from claim-scoped ones only,
    for a run that emitted trust_signal events but never an answer-scope
    one. Every field floors at the worst claim-scoped verdict, mirroring
    `adapters/mcp/server.py`'s `_aggregate_claim_trust_signals` exactly
    (F-4.1-A-02's fix): the previous, wrong behavior took the first signal
    or a fixed cheerful default, both of which can contradict the actual
    claim-level verdicts they discard.
    """
    outcomes = [signal.outcome for signal in claim_signals]
    resolved_outcome = aggregate(outcomes, default=terminal_trust_outcome or "refuse")
    risk_tier: Literal["low", "high"] = (
        "high" if any(signal.risk_tier == "high" for signal in claim_signals) else "low"
    )
    grounded = all(signal.grounded for signal in claim_signals)
    triangulated_values = [signal.triangulated for signal in claim_signals]
    triangulated = min(triangulated_values, key=lambda value: _TRIANGULATION_SEVERITY[value])
    return TrustSignalPayload(
        outcome=resolved_outcome,
        risk_tier=risk_tier,
        grounded=grounded,
        triangulated=triangulated,
        citation_id=None,
        scope="answer",
    )


def _floor_trust_signal_for_fatal_error(trust_signal: TrustSignalPayload) -> TrustSignalPayload:
    """A fatal error interrupted the run, so whatever partial answer text
    exists cannot be vouched for as complete or grounded. Floors, never
    raises: `outcome` is no better than `"flag"`, `grounded` is forced
    `False`, `risk_tier` is forced `"high"`. Mirrors `adapters/mcp/server.
    py`'s `_floor_trust_signal_for_fatal_error` (F-4.1-A-01/A-05).
    """
    return trust_signal.model_copy(
        update={
            "outcome": aggregate([trust_signal.outcome, "flag"]),
            "grounded": False,
            "risk_tier": "high",
        }
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


def _merge_disclosure_messages(existing: str | None, notes: list[str]) -> str:
    """Fold `notes` into `trust_signal.message`, appending to whatever was
    already there (a refusal's own message, Section 8.4) rather than
    overwriting it, then hard-caps at `TrustSignalPayload.message`'s own
    500-char max_length so a combination of disclosures can never fail
    that field's own validation when re-constructed via `model_copy`.
    """
    parts = ([existing] if existing else []) + notes
    return " ".join(parts)[:MAX_DISCLOSURE_NOTE_LENGTH]


def _fallback_answer_text(
    *, guard_payload: GuardPayload | None, error_payload: ErrorPayload | None
) -> str:
    """Built only when a run's terminal state produced no `token` events at
    all: a guardrail-level refusal (`guard` and `done`, no `token`), or a
    fatal error before Write ever ran. Cite-or-refuse still holds either
    way; this is defensive completeness for the `answer` field, which this
    surface's types require present on every result, never a second
    refusal wording competing with `write_node`'s own.
    """
    if guard_payload is not None and not guard_payload.passed:
        reason_suffix = f" ({guard_payload.reason})" if guard_payload.reason else ""
        return (
            "This question could not be answered: it did not pass this "
            f"system's content guardrail{reason_suffix}."
        )
    if error_payload is not None:
        return _fatal_error_disclosure(error_payload)
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
# The shared accumulator. Both fold_run (live, waits for a terminal event)
# and fold_run_snapshot (buffered, does not wait) consume the same event
# sequence through the same `_consume_event` function and the same
# `_finalize` function, so the two entry points can never silently diverge
# on what folding means.
# ---------------------------------------------------------------------------


@dataclass
class _Accumulator:
    answer_parts: list[str] = field(default_factory=list)
    citation_events_seen: int = 0
    citations: list[Citation] = field(default_factory=list)
    answer_trust_signal: TrustSignalPayload | None = None
    claim_trust_signals: list[TrustSignalPayload] = field(default_factory=list)
    terminal_trust_outcome: str | None = None
    guard_payload: GuardPayload | None = None
    fatal_error_payload: ErrorPayload | None = None


def _consume_event(acc: _Accumulator, event: Event) -> None:
    """Fold one event into `acc`, mutating it in place.

    Every event is run through `sanitize_event_for_end_user` first
    (unconditionally: this surface's `operator_mode` is a parameter kept
    only for interface symmetry with the core, since the caller pins it
    `False` in code, T-4.3's own scope reading), which drops a `cost`
    event entirely and redacts `done.total_cost_usd`. `think`, `plan`,
    `tool_start`, and `tool_result` carry nothing this surface's schema has
    a field for, and are folded out entirely by simply not matching any
    branch below, mirroring Section 13.2's own framing for the sibling MCP
    surface.
    """
    sanitized = sanitize_event_for_end_user(event)
    if sanitized is None:
        return
    event = sanitized
    if event.type == "token":
        acc.answer_parts.append(TokenPayload(**event.payload).text)
    elif event.type == "citation":
        acc.citation_events_seen += 1
        if len(acc.citations) < MAX_CITATIONS:
            citation = _build_citation_from_event(event)
            if citation is not None:
                acc.citations.append(citation)
    elif event.type == "trust_signal":
        candidate = TrustSignalPayload(**event.payload)
        if candidate.scope == "answer":
            acc.answer_trust_signal = candidate
        elif candidate.scope == "claim":
            acc.claim_trust_signals.append(candidate)
    elif event.type == "guard":
        acc.guard_payload = GuardPayload(**event.payload)
    elif event.type == "error":
        payload = ErrorPayload(**event.payload)
        if payload.fatal:
            acc.fatal_error_payload = payload
    elif event.type == "done":
        acc.terminal_trust_outcome = DonePayload(**event.payload).trust_outcome


def _finalize(acc: _Accumulator) -> tuple[str, TrustSignal, list[Citation], Disclosures]:
    """Turn an `_Accumulator` that has consumed some (possibly incomplete)
    prefix of a run's events into the four fields every result type on
    this surface carries: `answer`, `trust_signal`, `citations`,
    `disclosures`.
    """
    if acc.answer_trust_signal is not None:
        trust_payload = acc.answer_trust_signal
    elif acc.claim_trust_signals:
        trust_payload = _aggregate_claim_trust_signals(
            acc.claim_trust_signals, acc.terminal_trust_outcome
        )
    else:
        resolved_outcome = acc.terminal_trust_outcome or "refuse"
        trust_payload = TrustSignalPayload(
            outcome=resolved_outcome,
            # "unknown", never a hardcoded "low": no assessment ran on this
            # path (no trust_signal event of any scope arrived at all), so
            # asserting a specific risk tier from nothing is exactly
            # F-4.1-J3-02's still-open defect on the sibling MCP surface.
            # tracker/phase_4.3.md folds the decided fix ("unknown" rather
            # than a hardcoded "low") into this phase's path for the same
            # field on the refusal sites core/graph.py owns; this branch
            # applies the identical principle to this surface's own
            # synthetic-signal fallback, which no core refusal site
            # produces.
            risk_tier="unknown",
            grounded=bool(acc.citations) and resolved_outcome == "answer",
            triangulated=None,
            citation_id=None,
            scope="answer",
        )

    # Cite-or-refuse floor, unconditional: never report grounded=true or
    # outcome="answer" on a run where no citation event actually arrived,
    # regardless of what the run's own trust_signal event claims. This is
    # stricter than the branch above (which only applies when no answer-
    # scope signal was ever emitted): a run CAN emit an answer-scope
    # trust_signal claiming outcome="answer" while citing nothing, and this
    # floor corrects that claim rather than trusting it, exactly the shape
    # `tracker/phase_4.3.md`'s "an uncited answer is never reported as
    # grounded" gate arm exercises.
    if not acc.citations:
        update: dict[str, object] = {}
        if trust_payload.outcome == "answer":
            update["outcome"] = "refuse"
        if trust_payload.grounded:
            update["grounded"] = False
        if update:
            trust_payload = trust_payload.model_copy(update=update)

    raw_answer_text = "".join(acc.answer_parts).strip()
    answer_text = raw_answer_text
    if not answer_text:
        answer_text = _fallback_answer_text(
            guard_payload=acc.guard_payload, error_payload=acc.fatal_error_payload
        )

    notes: list[str] = []
    answer_truncated = False

    if len(answer_text) > MAX_ANSWER_LENGTH:
        answer_text = _truncate_on_word_boundary(answer_text, MAX_ANSWER_LENGTH)
        answer_truncated = True
        notes.append(
            f"The answer above was truncated to this surface's {MAX_ANSWER_LENGTH}-"
            "character limit; some content was omitted."
        )

    citations_omitted = max(0, acc.citation_events_seen - len(acc.citations))
    if citations_omitted > 0:
        notes.append(
            f"{citations_omitted} citation(s) beyond this surface's {MAX_CITATIONS}-"
            "citation limit were omitted; some citation markers in the answer "
            "above may not resolve to a returned citation."
        )

    if acc.fatal_error_payload is not None:
        trust_payload = _floor_trust_signal_for_fatal_error(trust_payload)
        notes.append(_fatal_error_disclosure(acc.fatal_error_payload))

    if notes:
        trust_payload = trust_payload.model_copy(
            update={"message": _merge_disclosure_messages(trust_payload.message, notes)}
        )

    disclosures = Disclosures(
        answer_truncated=answer_truncated,
        citations_omitted=citations_omitted,
        notes=notes[:MAX_DISCLOSURE_NOTES],
    )
    return answer_text, TrustSignal.from_payload(trust_payload), acc.citations, disclosures


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
    except TimeoutError:
        raise FoldTimeoutError(
            f"this query exceeded the GraphQL surface's {_FOLD_LOOP_TIMEOUT_S:.0f}s "
            "wall-clock fold budget and was aborted before finishing; retry with a "
            "narrower question, or use the REST/SSE surface to watch the run's own "
            "event stream instead of waiting for one final result"
        ) from None

    answer_text, trust_signal, citations, disclosures = _finalize(acc)
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
    answer_text, trust_signal, citations, disclosures = _finalize(acc)
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

    citation_events_total = 0
    citations: list[Citation] = []
    for event in entry.events:
        sanitized = sanitize_event_for_end_user(event)
        if sanitized is None or sanitized.type != "citation":
            continue
        citation_events_total += 1
        if len(citations) < MAX_CITATIONS:
            citation = _build_citation_from_event(sanitized)
            if citation is not None:
                citations.append(citation)

    return CitationsExport(
        run_id=entry.run_id,
        export_truncated=citation_events_total > MAX_CITATIONS,
        run_cancelled=entry.cancelled,
        citations=citations,
    )
