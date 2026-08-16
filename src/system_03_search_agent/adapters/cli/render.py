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

Three design decisions worth stating up front, since Section 13.3's prose
and the pre-committed premise gate (`tests/system_03_search_agent/adapters/
cli/test_phase_4_2_premise.py`) pull in slightly different directions and
the gate is the one that cannot be edited:

1. Marker fidelity. `core/graph.py`'s `_narrative_chunks` already bakes the
   literal `[n]` text into each `token.text` sentence, using the SAME
   `display_index` numbers the accompanying `citation` events carry
   (`citation_id_by_display = {c.display_index: c.citation_id for c in
   citations}`). `token.marker_ids` is metadata for THIS renderer to use
   for completeness checking, not raw material to build a `[n]` string
   from. So `handle()` prints `token.text` verbatim (after the
   character-level sanitization decision 3 describes, which never touches
   marker digits or their order) and never inserts, renumbers, or removes
   a bracketed marker itself. It separately tracks every marker id a token
   has referenced against every citation id a `citation` event has
   actually delivered, and reports the honest gap (a marker with no
   matching citation) in the references block rather than silently
   dropping it.

2. Trust-prefix placement versus true token-by-token streaming. Section
   13.3 calls the trust prefix "a one-line prefix on the answer body," and
   `token` is specified to print live as the growing answer body. Read
   literally together, both cannot be true at once for a value (the
   answer-level trust outcome) that Section 8.3.4 computes only once every
   claim-level signal is in, i.e. near the end of the stream. This module
   keeps genuine live token streaming (`system-design-patterns` rule 6's
   time-to-first-token guarantee) and prints the trust-outcome tag as a
   standalone stdout line (build phase 4.2 review, J-4.2-05: a leading
   `\n` now guarantees the tag never glues to the last token's own text,
   closing the gap between this docstring's earlier "standalone" claim and
   what the code actually did) at the point the answer-scope `trust_signal`
   event actually arrives, which in every fixture this ticket read is
   already immediately before `done`.

3. Untrusted-content sanitization (build phase 4.2 review, F-4.2-A-01,
   critical). Every field this module writes that traces back to Layer 2
   or Layer 3 content, an NCBI record body, a PubTator annotation, a
   ClinicalTrials.gov study, or model narrative text assembled from any of
   them, is untrusted external text per `ai-security-standards.md`'s
   "treat AI output as untrusted" rule, and this module is the one place
   that text reaches a terminal, an execution surface, not a display
   surface. `_sanitize_untrusted` (defined below) is the one call site
   every such field is routed through before `self._out`/`self._err`
   writes it: it neutralizes C0/C1 control bytes (which is what defeats
   ANSI CSI/OSC terminal-control sequences, since both begin with a C0/C1
   control byte) into a visible escaped form, and separately escapes any
   literal occurrence of this renderer's own closed structural vocabulary,
   the four trust-outcome words in brackets and the references header, so
   a hostile source cannot forge either one byte-for-byte. See
   `_sanitize_untrusted`'s own docstring for the full threat model and the
   two-option choice this ticket's report names.

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
      file, no log, no network call. Both streams are flushed after every
      write (F-4.2-A-07): a `TextIO` the interpreter chooses to buffer
      would otherwise hold the first answer token, and every dim status
      line, invisible until the process exits, defeating
      `system-design-patterns` rule 6's time-to-first-token guarantee on
      exactly the surface that guarantee is supposed to cover. One flush
      per SSE-driven event write is not aggressive: the write rate is
      already bounded by network arrival, not by CPU, so the added
      syscall is negligible next to the latency that already separates
      one event from the next.
"""

from __future__ import annotations

import re
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
    from system_03_search_agent.adapters.cli.client import CliApiError
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


# ----------------------------------------------------------------------
# Untrusted-content sanitization (F-4.2-A-01, critical)
# ----------------------------------------------------------------------
#
# A CLI writes to a terminal, and a terminal EXECUTES control sequences.
# `token.text`, `citation.source`, `citation.source_url`, every narrative
# and summary field this module prints, and `error.source` all trace back
# to Layer 2/3 content or model output built from it, which is untrusted
# external text per `ai-security-standards.md`. Left unescaped, a hostile
# field can clear the screen (`\x1b[2J`), reposition the cursor, retitle
# the window (`\x1b]0;...\x07`), conceal text (`\x1b[8m`), or overwrite an
# already-printed line (`\r`). This is the ONE call site every such field
# is routed through before either stream sees it.
#
# A second, distinct attack survives a perfect control-character
# sanitizer alone: because `token.text` is printed close to verbatim
# (design decision 1 above), a hostile source can still print the
# LITERAL, printable text of this renderer's own structural output,
# `[answer]`/`[flag]`/`[ask]`/`[refuse]` or `References:`, and have a
# reader mistake it for the genuine trust tag or references header. Two
# honest defences exist: mark this renderer's own structural lines so
# they are distinguishable (for example a sentinel byte no sanitized
# untrusted text can ever reproduce), or escape a bracket-marker-shaped
# run inside untrusted text so it can never be byte-identical to the
# genuine tag. This module takes the second option. The first would need
# a literal control byte on every successful run's trust line and
# references header, degrading the ordinary, non-adversarial case (an
# odd glyph in front of `[answer]` on every real run, or in a redirected
# file) to buy a property the escape approach buys without touching a
# single byte of legitimate output. `_FORGERY_PATTERN` targets exactly
# the closed vocabulary at risk, the four `TrustOutcome` words and the
# references header, so it cannot false-positive on an ordinary numeric
# citation marker like `[1]`, which design decision 1 requires this
# module to leave untouched.
_C0_C1_ESCAPE_EXEMPT = "\n"

# The closed `TrustOutcome` vocabulary (`contracts.events.TrustOutcome`)
# plus the references header, matched only when they appear inside
# UNTRUSTED text. This pattern is never applied to a literal this module
# itself writes.
_FORGERY_PATTERN = re.compile(r"\[(answer|flag|ask|refuse)\]|References:")


def _escape_control_bytes(text: str) -> str:
    """Neutralize C0 (except `\\n`) and C1 control bytes into a visible,
    printable escape form (`\\xHH`/`\\uHHHH`), never a silent deletion: a
    reader can still see something was there, where deletion would let an
    attacker hide content instead of merely fail to forge it. `\\n` is
    exempt because it is common in legitimate narrative text and, on its
    own, only moves the cursor down a line; it carries no terminal-control
    risk the way `\\r` (line overwrite) or an ESC-led CSI/OSC sequence
    does. This alone defeats every ANSI CSI/OSC sequence too: both begin
    with the C0 ESC byte (0x1B) or a C1 single-byte equivalent (0x9B for
    CSI, 0x9D for OSC), and once that lead byte is rewritten into
    printable text, a terminal has nothing left to interpret as an escape
    sequence.
    """
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if ch == _C0_C1_ESCAPE_EXEMPT:
            out.append(ch)
        elif code < 0x20 or code == 0x7F:
            out.append(f"\\x{code:02x}")
        elif 0x80 <= code <= 0x9F:
            out.append(f"\\u{code:04x}")
        else:
            out.append(ch)
    return "".join(out)


def _escape_forgery_markers(text: str) -> str:
    """Escape a byte-identical copy of this renderer's own trust tag or
    references header wherever one appears inside untrusted text, so a
    forged occurrence can never be indistinguishable from the genuine
    line this module itself writes. The backslash insertion is visible,
    not a deletion, matching `_escape_control_bytes`'s convention above:
    `[answer]` embedded in a hostile field becomes the literal text
    `[\\answer]`, and `References:` becomes `References\\:`.
    """

    def _replace(match: re.Match[str]) -> str:
        word = match.group(1)
        if word is not None:
            return f"[\\{word}]"
        return "References\\:"

    return _FORGERY_PATTERN.sub(_replace, text)


def _sanitize_untrusted(text: str) -> str:
    """The one function every untrusted string field is routed through
    before this module writes it to `self._out` or `self._err`. Composes
    the control-byte defence and the forgery defence above; order does
    not matter between the two since neither one's output can create a
    new match for the other (escaping a control byte never produces a
    literal `[answer]`/`References:` substring, and escaping those words
    never introduces a raw control byte).
    """
    return _escape_forgery_markers(_escape_control_bytes(text))


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
        # F-4.2-A-27: once a guard rejection has fired, never let a later
        # event (a stray `trust_signal`/`done` the server should not send
        # after a rejection, but this renderer does not get to assume that
        # never happens) print `[answer]` or a references block on top of
        # it. Checked in `_write_trust_prefix` directly, defense in depth
        # regardless of what upstream sends.
        self._guard_rejected = False

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
        self._err.flush()
        self._guard_rejected = True
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
        narrative = _sanitize_untrusted(payload.narrative)
        self._err.write(f"[think] {narrative}\n")
        self._err.flush()

    def _handle_plan(self, event: Event) -> None:
        payload = PlanPayload.model_validate(event.payload)
        narrative = _sanitize_untrusted(payload.narrative)
        self._err.write(f"[plan] {narrative}\n")
        self._err.flush()

    def _handle_tool_start(self, event: Event) -> None:
        payload = ToolStartPayload.model_validate(event.payload)
        self._err.write(f"[tool] {payload.tool} ({payload.layer}): {payload.status}\n")
        self._err.flush()

    def _handle_tool_result(self, event: Event) -> None:
        payload = ToolResultPayload.model_validate(event.payload)
        truncated_note = ", truncated" if payload.truncated else ""
        summary = _sanitize_untrusted(payload.summary)
        self._err.write(
            f"[tool] {payload.tool} ({payload.layer}): {payload.status} - "
            f"{summary} ({payload.result_count} result(s){truncated_note})\n"
        )
        self._err.flush()

    def _handle_token(self, event: Event) -> None:
        payload = TokenPayload.model_validate(event.payload)
        # Verbatim, after sanitization: the server already baked the
        # `[n]` markers into this text using its own citations'
        # display_index (design decision 1), and `_sanitize_untrusted`
        # (design decision 3) never touches a marker digit, only C0/C1
        # control bytes and a byte-identical forgery of this renderer's
        # own structural vocabulary. This is the only place `handle()`
        # writes to `self._out` for answer content, matching Section
        # 13.3's "printed to stdout as the growing answer body." Flushed
        # immediately (F-4.2-A-07): an unflushed stream buffers the
        # answer until process exit, which is indistinguishable from not
        # streaming at all from the reader's side of the pipe.
        self._out.write(_sanitize_untrusted(payload.text))
        self._out.flush()
        self._seen_marker_ids.update(payload.marker_ids)

    def _handle_citation(self, event: Event) -> None:
        payload = CitationPayload.model_validate(event.payload)
        existing = self._citations.get(payload.citation_id)
        if existing is not None and existing != payload:
            # F-4.2-A-19: a second `citation` event citing an id already
            # bound to a DIFFERENT source is a conflicting redefinition.
            # A `[n]` marker for this id may already be visible on
            # screen (or already written into a redirected file) by the
            # time this arrives, so last-write-wins would point an
            # already-printed marker at a source the reader never saw.
            # Reject the redefinition (the first source for this id
            # wins, matching what may already be on screen) and flag it
            # audibly rather than accept the swap silently. A genuine
            # duplicate (same id, identical fields) is not a conflict
            # and is not warned about.
            self._err.write(
                f"warning: citation {payload.citation_id!r} was redefined "
                "mid-run; the redefinition was ignored and the first "
                "source for this id is kept.\n"
            )
            self._err.flush()
            return
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
        if self._printed_trust_prefix or self._guard_rejected:
            # F-4.2-A-27: a guard rejection already printed its own
            # explanation to stderr and set the exit code; never let a
            # later `trust_signal`/`done` print `[answer]` (or any other
            # outcome) on top of a run this renderer already knows was
            # rejected.
            return
        # J-4.2-05: a leading `\n` guarantees this tag starts its own
        # line regardless of whether the last token write ended in a
        # newline, closing the gap between this module's own docstring
        # claim ("a standalone stdout line") and what the code used to
        # do (glue the tag to the end of the last token, verified at
        # byte index 36 mid-sentence in the judge's own probe).
        self._out.write(f"\n[{outcome}]\n")
        self._out.flush()
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
        self._err.flush()

    def _handle_error(self, event: Event) -> None:
        payload = ErrorPayload.model_validate(event.payload)
        disclosure = _error_disclosure(payload.error_class)
        retry_note = (
            f" Retry in about {payload.retry_after_s}s." if payload.retry_after_s > 0 else ""
        )
        source = _sanitize_untrusted(payload.source)
        self._err.write(f"error [{source}]: {disclosure}{retry_note}\n")
        self._err.flush()

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
            self._err.flush()

        # A guard rejection or a fatal error already set a nonzero exit
        # code; a `done` event does not follow either on a well-formed
        # stream, but if it somehow does, that earlier failure still wins.
        if self._exit_code is None:
            self._exit_code = _EXIT_FAILURE if payload.trust_outcome == "refuse" else _EXIT_OK

    # ------------------------------------------------------------------
    # References block
    # ------------------------------------------------------------------

    def _write_references_block(self) -> None:
        if self._printed_references or self._guard_rejected:
            # F-4.2-A-27: the same defense-in-depth guard as
            # `_write_trust_prefix`. A stray `citation`/`done` arriving
            # after a guard rejection must not print a references block
            # on top of it either, or a rejected run would print nothing
            # via the trust tag but still leak a "References:" block.
            return
        self._printed_references = True

        unresolved = sorted(self._seen_marker_ids - self._citations.keys())
        if not self._citations and not unresolved:
            return

        self._out.write("\nReferences:\n")
        for citation in sorted(self._citations.values(), key=lambda c: c.display_index):
            source = _sanitize_untrusted(citation.source)
            # `source_url` is also constrained by `contracts.events.
            # NCBI_SOURCE_URL_PATTERN` (build phase 4.2 review, F-4.2-A-01
            # second half: the pattern is now end-anchored to a restricted
            # URL character class, so a control byte or embedded newline
            # can no longer reach a validated `CitationPayload` at all).
            # Sanitizing it here too is defense in depth, not redundancy:
            # this function has no way to know whether the `Event` it is
            # rendering was actually validated through that model, only
            # that `citation.source` (unconstrained beyond `max_length`)
            # still needs it regardless.
            source_url = _sanitize_untrusted(citation.source_url)
            self._out.write(f"[{citation.display_index}] {source} - {source_url}\n")
        self._out.flush()
        for marker_id in unresolved:
            # Design decision 1: say so honestly rather than dropping a
            # marker the answer text referenced but never got a citation
            # for, rather than silently omitting it from the block.
            # F-4.2-A-26: moved to stderr. This diagnostic used to land on
            # stdout inside the references block, so `s3 ask "..." >
            # answer.txt` captured an internal completeness note alongside
            # the citations a reader expects that file to hold. The
            # disclosure itself is kept, honest per design decision 1;
            # only its destination moved.
            self._err.write(f"[unresolved] marker {marker_id!r} was never sent a citation\n")
        if unresolved:
            self._err.flush()

    # ------------------------------------------------------------------
    # Exit
    # ------------------------------------------------------------------

    def finish(self) -> int:
        # A run that never reached a terminal `done`, a terminal fatal
        # `error`, or a guard rejection is not a run that finished
        # cleanly, so the safe default on an otherwise-undetermined state
        # is failure, never success-by-omission.
        if self._exit_code is None:
            # J-4.2-04: the stream ended (interrupted, dropped connection,
            # a crash before any terminal `done`/fatal-error/guard event)
            # with no clean terminal state ever reaching this renderer.
            # Whatever answer text is already on stdout can carry a `[n]`
            # marker with no matching citation and no sign anywhere that
            # the run was cut off; `main.py:533-535` returning without
            # calling `finish()` at all on the interrupt path is a
            # separate defect in that module, outside this file's
            # ownership, but THIS renderer's own half of the fix is to
            # make sure that whenever `finish()` IS reached on an
            # undetermined run, the references block for whatever was
            # actually delivered gets printed, exactly like a clean
            # `done` would have done. `_write_references_block` is
            # idempotent (`self._printed_references` guards it), so this
            # is safe to call even if a partial block already printed.
            # The truncation notice itself goes to stderr, matching every
            # other diagnostic in this renderer, and never claims a trust
            # outcome this renderer was never told.
            self._exit_code = _EXIT_FAILURE
            self._err.write(
                "error: the run ended before a final answer was received; "
                "any answer text above is incomplete and its citations may "
                "be partial.\n"
            )
            self._err.flush()
            self._write_references_block()
        return self._exit_code


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
    "MIXED ERROR-BODY SHAPES" constraint made concrete.

    Two distinct failure shapes reach this function, and both are handled:

    1. `client.py`'s own typed hierarchy (`CliApiError` and its five
       subclasses: `AuthExpiredError`, `ForbiddenError`, `NotFoundError`,
       `ConflictError`, `RateLimitedError`). This is what `CliClient`
       actually raises for every non-2xx response from `create_run`,
       `stream_events`, `stop`, and `fetch_citations` (`client.py`'s
       `_raise_for_status`), so it is the primary, expected shape and is
       checked first. `CliApiError.message` already carries the server's
       own curated, hand-authored copy (e.g. `app.py`'s
       `_CONCURRENT_RUN_CAP_MESSAGE` for a 429, `auth/router.py`'s
       `_INVALID_REFRESH_DETAIL` for a 401), parsed once in `client.py`'s
       `_parse_error_detail` from either mixed body shape the pre-build
       source read found (a structured `{"detail": {"reason", "message"}}`
       on 429, a bare string `{"detail": "..."}` on 401/403/404/409), so
       this function never re-parses a response body itself.
    2. A bare `httpx` exception (`HTTPStatusError`, `TimeoutException`, or
       the broader `HTTPError`). Kept as the fallback path for a genuinely
       transport-level failure that never reached `client.py`'s own
       `_raise_for_status`, for example a call this module is exercised
       against directly in a unit test, or a future call site that talks
       to `httpx` without going through `CliClient`. `client.py`'s typed
       hierarchy does not subclass any `httpx` exception type, so without
       the explicit `CliApiError` branch above, every one of the five
       typed errors `CliClient` actually raises fell through to the bare,
       unhelpful fallback at the bottom of this function (the real defect
       this branch fixes; `tracker/phase_4.2.md` finding filed at the
       phase 4.2 to 4.3 ticket seam).

    Flagged in this ticket's final report as an addition beyond the four
    interfaces `tracker/phase_4.2.md`'s lead section fixed, since no
    signature for HTTP-level (as opposed to event-stream) error rendering
    was named there.
    """
    from system_03_search_agent.adapters.cli.client import CliApiError

    if isinstance(exc, CliApiError):
        return _render_cli_api_error(err, exc)
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


def _render_cli_api_error(err: TextIO, exc: CliApiError) -> int:
    """Renders one of `client.py`'s five typed errors. `exc.message` is
    always the server's own already-curated, already-actionable text (see
    `CliApiError`'s own docstring in `client.py`), never a raw exception
    string, so it is safe to write verbatim, the same trust boundary
    `_render_http_status_error` below already applies to a bare-httpx
    `detail` string. `_actionable_suffix_for_status` is reused rather than
    duplicated: it is a pure function of status code, reason, and headers,
    and this call site has all three (`exc.status_code`, `exc.reason`, and
    a synthesized `Retry-After` header when `exc` is a `RateLimitedError`
    carrying `retry_after_s`), so the 429/401/403/404/409 action copy stays
    identical to the bare-httpx path instead of drifting into a second,
    hand-maintained copy of the same table.
    """
    from system_03_search_agent.adapters.cli.client import RateLimitedError

    message = exc.message[:500] if exc.message else (
        f"the server refused the request (HTTP {exc.status_code})"
    )
    retry_after_s = exc.retry_after_s if isinstance(exc, RateLimitedError) else None
    headers = (
        httpx.Headers({"retry-after": str(retry_after_s)})
        if retry_after_s is not None
        else httpx.Headers()
    )
    action = _actionable_suffix_for_status(exc.status_code, exc.reason or "", headers)
    err.write(f"error: {message}{action}\n")
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
