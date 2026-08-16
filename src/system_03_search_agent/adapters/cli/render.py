"""The CLI renderer: build phase 4.2, `tracker/phase_4.2.md`, ticket T-4.2-04.

Spec: `requirements/Technical_specification.md` Section 13.3 (the CLI's ten
rendering rules), Section 2.2 (the event envelope), Section 2.3 (the
per-type payload models), Section 9.1 (`CitationPayload`, referenced not
restated).

`Renderer` is one of the fixed interfaces `tracker/phase_4.2.md`'s lead
section names before dispatch. It consumes the real `Event` envelope
`main.py` (T-4.2-05) decodes off the SSE stream and turns it into exactly
what Section 13.3 specifies: the answer body plus a references block on
stdout, every status line and every failure on stderr, and a process exit
code. It never talks to the network, never reads a credential, and never
retries anything; those are `client.py`, `credentials.py`, and `main.py`'s
jobs. This module owns rendering only.

Two design decisions worth stating up front, since Section 13.3's prose and
the pre-committed premise gate (`tests/system_03_search_agent/adapters/cli/
test_phase_4_2_premise.py`) pull in slightly different directions and the
gate is the one that cannot be edited:

1. Marker fidelity. `core/graph.py`'s `_narrative_chunks` already bakes the
   literal `[n]` text into each `token.text` sentence, using the SAME
   `display_index` numbers the accompanying `citation` events carry
   (`citation_id_by_display = {c.display_index: c.citation_id for c in
   citations}`). `token.marker_ids` is metadata for THIS renderer to use
   for completeness checking, not raw material to build a `[n]` string
   from. So `handle()` prints `token.text` verbatim and never inserts,
   renumbers, or removes a bracketed marker itself. It separately tracks
   every marker id a token has referenced against every citation id a
   `citation` event has actually delivered, and reports the honest gap (a
   marker with no matching citation) in the references block rather than
   silently dropping it.

2. Trust-prefix placement versus true token-by-token streaming. Section
   13.3 calls the trust prefix "a one-line prefix on the answer body," and
   `token` is specified to print live as the growing answer body. Read
   literally together, both cannot be true at once for a value (the
   answer-level trust outcome) that Section 8.3.4 computes only once every
   claim-level signal is in, i.e. near the end of the stream. This module
   keeps genuine live token streaming (`system-design-patterns` rule 6's
   time-to-first-token guarantee) and prints the trust-outcome tag as a
   standalone stdout line at the point the answer-scope `trust_signal`
   event actually arrives, which in every fixture this ticket read is
   already immediately before `done`. `TestGoldenPath`/`TestRefusalPath`
   in the premise gate only assert substring membership, never position,
   so this satisfies the gate; it is flagged here, and again in this
   ticket's final report, as a real ambiguity rather than something
   quietly resolved one way.

Depends on:
    - system_03_search_agent.contracts.events (Event and every Section 2.3
      payload model `handle()` validates a raw `event.payload` dict
      against before rendering it).

Reads:
    - Nothing outside the `Event` objects `handle()` receives and the
      `httpx` exception objects `render_client_error()` receives.

Writes:
    - The `out` and `err` `TextIO` streams passed to `Renderer.__init__`,
      and to `render_client_error`'s `err` parameter. Nothing else: no
      file, no log, no network call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

import httpx

from system_03_search_agent.contracts.events import (
    CitationPayload,
    CostPayload,
    DonePayload,
    ErrorPayload,
    Event,
    GuardPayload,
    PlanPayload,
    ThinkPayload,
    TokenPayload,
    ToolResultPayload,
    ToolStartPayload,
    TrustSignalPayload,
)

if TYPE_CHECKING:
    from system_03_search_agent.contracts.events import TrustOutcome

# Exit codes. Two values only: the CLI reports success or failure, never a
# graded severity, since nothing downstream of `s3 ask` in a shell pipeline
# reads anything finer than zero-or-not.
_EXIT_OK = 0
_EXIT_FAILURE = 1

# Section 12.6's `GuardrailBanner` copy table, mirrored here rather than
# imported: `adapters/cli` does not depend on the web frontend, and
# `contracts/events.py`'s own `NCBI_SOURCE_URL_PATTERN` comment already
# establishes this repo's precedent of copying a small fixed table verbatim
# across a module boundary instead of reaching across it. `guard.reason` is
# model-generated free text (`ThinkPayload`/`GuardPayload` docstrings in
# `contracts/events.py`); Section 12.6 never renders it raw, choosing copy
# from `guard.category` instead, and this surface follows the same rule for
# the same reason production-standards states for `error.message`: a fixed
# literal per closed enum value, never raw model output, at a
# security-relevant rendering boundary.
_GUARD_CATEGORY_COPY: dict[str, str] = {
    "off_topic": (
        "this looks outside biomedical research. Try a gene, variant, "
        "pathogen, or paper question."
    ),
    "medical_advice": (
        "this system can assemble cited evidence about a condition or "
        "variant, but a clinician makes the diagnosis or treatment call."
    ),
    "injection": "that request could not be processed as a research question.",
    "rate_limited": "today's question limit has been reached. Try again after it resets.",
    "cost_capped": "the system is at capacity right now. Try again shortly.",
    # Not in Section 12.6's table (the web UI's own table has no row for
    # this category either): a Layer 1 read-only-by-design fallback, since
    # `write_seeking` is the one guard category this rule's own source
    # section never gave copy for. Flagged in this ticket's final report.
    "write_seeking": (
        "this system only reads from the knowledge graph and NCBI APIs; it "
        "cannot perform a write, update, or delete operation."
    ),
}
_GUARD_CATEGORY_FALLBACK = "this question could not be processed."

# `adapters/mcp/server.py`'s `_MCP_FATAL_ERROR_DISCLOSURE` precedent
# (F-4.1-A-09), copied verbatim rather than imported for the same
# adapter-independence reason as the guard table above: a fixed, sanitized
# literal per `error_class`, since `ErrorPayload.message` is NOT
# pre-sanitized on every code path that constructs one (confirmed by
# reading `core/graph.py`'s `_step_error_kwargs`, which curates `message`
# for `HarnessCallError`-derived failures but is not the only constructor
# site in that module). Interpolating `error.message` directly here would
# make this surface only as safe as the least-careful ErrorPayload
# constructor call anywhere in the codebase, today or in a future change;
# this table holds the line independently of that.
_CLI_FATAL_ERROR_DISCLOSURE: dict[str, str] = {
    "transient": "this query hit a temporary error before finishing. Retrying may succeed.",
    "recoverable": "this query could not complete as requested.",
    "unexpected": "this query failed unexpectedly before finishing.",
    "cancelled": "this query was stopped before it finished.",
}


def _error_disclosure(error_class: str) -> str:
    return _CLI_FATAL_ERROR_DISCLOSURE.get(error_class, _CLI_FATAL_ERROR_DISCLOSURE["unexpected"])


class Renderer:
    """Renders one run's `Event` stream per Section 13.3's ten rules.

    One `Renderer` per run. `handle()` is called once per event in arrival
    order; `finish()` is called exactly once after the stream ends (on a
    terminal `done` or a terminal fatal `error`) and returns the process
    exit code `main.py` passes to `sys.exit`.
    """

    def __init__(self, out: TextIO, err: TextIO, *, operator: bool) -> None:
        self._out = out
        self._err = err
        self._operator = operator

        # Citation bookkeeping for the references block and the honest
        # unresolved-marker report (design decision 1 above).
        self._citations: dict[str, CitationPayload] = {}
        self._seen_marker_ids: set[str] = set()

        # Terminal-state bookkeeping. `_exit_code` is the single source of
        # truth `finish()` reads; every path that can end the run sets it.
        self._exit_code: int | None = None
        self._printed_trust_prefix = False
        self._printed_references = False

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def handle(self, event: Event) -> None:
        handler = getattr(self, f"_handle_{event.type}", None)
        if handler is None:
            # `Event.type` is a closed Literal validated at construction
            # (contracts/events.py), so this is defensive completeness for
            # a future additive event type this renderer has not been
            # taught yet, never a reachable path today. Silently ignoring
            # an unknown type is safer than crashing a run that is
            # otherwise rendering correctly.
            return
        handler(event)

    def _handle_guard(self, event: Event) -> None:
        payload = GuardPayload.model_validate(event.payload)
        if payload.passed:
            return
        copy = _GUARD_CATEGORY_COPY.get(payload.category, _GUARD_CATEGORY_FALLBACK)
        self._err.write(f"guard: {copy}\n")
        self._exit_code = _EXIT_FAILURE

    def _handle_think(self, event: Event) -> None:
        payload = ThinkPayload.model_validate(event.payload)
        # No persona name is available here. Section 13.3 asks for the
        # status line to be "prefixed with the persona name," but neither
        # `ThinkPayload` nor this class's fixed constructor carries one:
        # Section 12.7's own "Design note for Section 2 or 13 alignment"
        # already flags that `persona_name` is resolved once, in `POST
        # /v1/query`'s response body, not on any streamed event. This
        # renderer cannot invent a value it was never given, so the line
        # below omits the persona prefix rather than fabricate one.
        # Flagged again in this ticket's final report.
        self._err.write(f"[think] {payload.narrative}\n")

    def _handle_plan(self, event: Event) -> None:
        payload = PlanPayload.model_validate(event.payload)
        self._err.write(f"[plan] {payload.narrative}\n")

    def _handle_tool_start(self, event: Event) -> None:
        payload = ToolStartPayload.model_validate(event.payload)
        self._err.write(f"[tool] {payload.tool} ({payload.layer}): {payload.status}\n")

    def _handle_tool_result(self, event: Event) -> None:
        payload = ToolResultPayload.model_validate(event.payload)
        truncated_note = ", truncated" if payload.truncated else ""
        self._err.write(
            f"[tool] {payload.tool} ({payload.layer}): {payload.status} - "
            f"{payload.summary} ({payload.result_count} result(s){truncated_note})\n"
        )

    def _handle_token(self, event: Event) -> None:
        payload = TokenPayload.model_validate(event.payload)
        # Verbatim: the server already baked the `[n]` markers into this
        # text using its own citations' display_index (design decision 1).
        # This is the only place `handle()` writes to `self._out` for
        # answer content, matching Section 13.3's "printed to stdout as
        # the growing answer body."
        self._out.write(payload.text)
        self._seen_marker_ids.update(payload.marker_ids)

    def _handle_citation(self, event: Event) -> None:
        payload = CitationPayload.model_validate(event.payload)
        self._citations[payload.citation_id] = payload

    def _handle_trust_signal(self, event: Event) -> None:
        payload = TrustSignalPayload.model_validate(event.payload)
        if payload.scope != "answer":
            # Per-claim signals (`scope == "claim"`) do not get their own
            # rendered line: Section 13.3 names one prefix "on the answer
            # body," singular, not one per claim. The web UI's own
            # per-citation chip is the only surface that renders the
            # claim-level signal (Section 12.4); this plain-text surface
            # has no analogous inline chip to attach it to.
            return
        self._write_trust_prefix(payload.outcome)

    def _write_trust_prefix(self, outcome: TrustOutcome) -> None:
        if self._printed_trust_prefix:
            return
        self._out.write(f"[{outcome}]\n")
        self._printed_trust_prefix = True

    def _handle_cost(self, event: Event) -> None:
        if not self._operator:
            # Second, independent suppression layer (this ticket's
            # constraint 3): the server already strips `cost` events for a
            # non-operator caller, but this check holds even if that
            # upstream suppression ever regresses. Keyed only on the
            # `operator` flag this Renderer was constructed with, never on
            # anything the event itself claims about the caller.
            return
        payload = CostPayload.model_validate(event.payload)
        self._err.write(
            f"[cost] ${payload.query_cost_usd:.4f} of ${payload.query_cap_usd:.2f} cap "
            f"({payload.cap_fraction:.1%}), {payload.model_tier} tier\n"
        )

    def _handle_error(self, event: Event) -> None:
        payload = ErrorPayload.model_validate(event.payload)
        disclosure = _error_disclosure(payload.error_class)
        retry_note = (
            f" Retry in about {payload.retry_after_s}s." if payload.retry_after_s > 0 else ""
        )
        self._err.write(f"error [{payload.source}]: {disclosure}{retry_note}\n")

        # Section 13.3: exits nonzero UNLESS fatal is false AND error_class
        # is transient or recoverable, in which case the retry policy (not
        # this renderer) gets a chance first. Read literally: fatal=False
        # with error_class in {unexpected, cancelled} still exits nonzero.
        if payload.fatal or payload.error_class not in ("transient", "recoverable"):
            self._exit_code = _EXIT_FAILURE

    def _handle_done(self, event: Event) -> None:
        payload = DonePayload.model_validate(event.payload)

        # Fallback: if the answer-scope trust_signal never arrived (should
        # not happen on a well-formed stream, but `done.trust_outcome`
        # carries the same value regardless per Section 2.3), print the
        # prefix now rather than lose it.
        self._write_trust_prefix(payload.trust_outcome)

        self._write_references_block()

        # Cost is never printed for a non-operator credential (constraint
        # 3), and per this module's own design choice it never reaches
        # stdout at all, even for an operator: it is diagnostic, not
        # answer content, and belongs with the other dim status lines.
        if self._operator:
            self._err.write(
                f"[done] cost=${payload.total_cost_usd:.4f} "
                f"tool_calls={payload.total_tool_calls} elapsed={payload.elapsed_ms}ms\n"
            )

        # A guard rejection or a fatal error already set a nonzero exit
        # code; a `done` event does not follow either on a well-formed
        # stream, but if it somehow does, that earlier failure still wins.
        if self._exit_code is None:
            self._exit_code = _EXIT_FAILURE if payload.trust_outcome == "refuse" else _EXIT_OK

    # ------------------------------------------------------------------
    # References block
    # ------------------------------------------------------------------

    def _write_references_block(self) -> None:
        if self._printed_references:
            return
        self._printed_references = True

        unresolved = sorted(self._seen_marker_ids - self._citations.keys())
        if not self._citations and not unresolved:
            return

        self._out.write("\nReferences:\n")
        for citation in sorted(self._citations.values(), key=lambda c: c.display_index):
            self._out.write(f"[{citation.display_index}] {citation.source} - {citation.source_url}\n")
        for marker_id in unresolved:
            # Design decision 1: say so honestly rather than dropping a
            # marker the answer text referenced but never got a citation
            # for, rather than silently omitting it from the block.
            self._out.write(f"[unresolved] marker {marker_id!r} was never sent a citation\n")

    # ------------------------------------------------------------------
    # Exit
    # ------------------------------------------------------------------

    def finish(self) -> int:
        # A run that never reached a terminal `done`, a terminal fatal
        # `error`, or a guard rejection is not a run that finished
        # cleanly, so the safe default on an otherwise-undetermined state
        # is failure, never success-by-omission.
        return self._exit_code if self._exit_code is not None else _EXIT_FAILURE


# ----------------------------------------------------------------------
# HTTP-level (non-SSE-event) failures
# ----------------------------------------------------------------------


def render_client_error(err: TextIO, exc: BaseException) -> int:
    """Render a REST-call failure to stderr and return the process exit code.

    Not part of `Renderer`'s fixed interface (`handle()` only ever accepts
    a decoded `Event`, and none of `POST /v1/query`, `/auth/refresh`,
    `/v1/query/{run_id}/stop`, or `/v1/query/{run_id}/citations` ever wrap
    their own failure in one). `main.py` (T-4.2-05) calls this directly at
    the point one of those calls raises, before any `Event` for that
    request could ever reach `Renderer.handle()`. This is the ticket's
    "MIXED ERROR-BODY SHAPES" constraint made concrete: `client.py`'s
    fixed interface names no dedicated exception type, so this handles the
    standard shape an `httpx.AsyncClient` raises on
    `response.raise_for_status()`, per the pre-build source read's own
    finding on `app.py` error bodies (`tracker/phase_4.2.md`): a
    structured body on 429 (`{"detail": {"reason", "message"}}`, both
    already curated, hand-authored copy in `app.py`, e.g.
    `_CONCURRENT_RUN_CAP_MESSAGE`, never raw exception text) and a bare
    string body on 401/403/404/409 (`{"detail": "..."}`, the same kind of
    curated literal, e.g. `auth/router.py`'s `_INVALID_REFRESH_DETAIL`).
    Both are already safe to display verbatim, unlike `ErrorPayload.
    message` above: they are fixed `HTTPException(detail=...)` literals in
    this codebase, never `str(exc)`.

    Flagged in this ticket's final report as an addition beyond the four
    interfaces `tracker/phase_4.2.md`'s lead section fixed, since no
    signature for HTTP-level (as opposed to event-stream) error rendering
    was named there.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return _render_http_status_error(err, exc)
    if isinstance(exc, httpx.TimeoutException):
        err.write(
            "error: the request to the server timed out. Check your network "
            "connection and try again.\n"
        )
        return _EXIT_FAILURE
    if isinstance(exc, httpx.HTTPError):
        err.write(
            "error: could not reach the server. Check that it is running and "
            "your network connection, then try again.\n"
        )
        return _EXIT_FAILURE
    err.write("error: the request failed unexpectedly. Try again.\n")
    return _EXIT_FAILURE


def _render_http_status_error(err: TextIO, exc: httpx.HTTPStatusError) -> int:
    response = exc.response
    status_code = response.status_code
    try:
        body = response.json()
    except ValueError:
        body = None
    detail = body.get("detail") if isinstance(body, dict) else None

    if isinstance(detail, dict):
        reason = str(detail.get("reason", ""))[:128]
        message = str(detail.get("message", "the request was refused"))[:500]
    elif isinstance(detail, str):
        reason = ""
        message = detail[:500]
    else:
        reason = ""
        message = f"the server refused the request (HTTP {status_code})"

    action = _actionable_suffix_for_status(status_code, reason, response.headers)
    err.write(f"error: {message}{action}\n")
    return _EXIT_FAILURE


def _actionable_suffix_for_status(status_code: int, reason: str, headers: httpx.Headers) -> str:
    """An actionable next step per `.claude/rules/tool-call-budgets.md`,
    never a bare "the request failed". The 429 branch is a fallback: the
    server's own curated `message` (rendered above) already names the
    actionable step for every 429 this codebase raises today
    (`_CONCURRENT_RUN_CAP_MESSAGE` and its siblings in `app.py` all
    already say "wait" or "sign in"), so this only fires if a future 429
    ever ships with no `message` at all.
    """
    if status_code == 429:
        retry_after = headers.get("retry-after")
        wait_clause = f"wait about {retry_after}s" if retry_after else "wait"
        return f" Please {wait_clause}, or sign in for a higher limit, then try again."
    if status_code == 401:
        return " Run `s3 login` to re-authenticate."
    if status_code == 403:
        return " You do not have access to this resource."
    if status_code == 404:
        return " Check the run ID and try again."
    if status_code == 409:
        return " Wait for the run to reach a terminal state, then try again."
    return ""
