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
   critical; hardened at the round-3 fix, F-4.2-RR-01 and F-4.2-RR-02;
   the claim below narrowed to precise, per round-5's sweep, F-4.2-V4-01,
   after it was found false twice: F-4.2-D-03's own round-4 fix already
   named `_render_cli_api_error`/`_render_http_status_error` as sites that
   used to bypass it, and round 5 found a THIRD bypass, a `Content-Type`
   header interpolated raw in `_run_login` and in `credentials.py`'s
   `_refresh_and_store`, plus a fourth in `_actionable_suffix_for_status`'s
   `Retry-After` header. A docstring claiming blanket coverage is worth
   less than a docstring stating exactly which mechanism covers which
   field, so this is now the latter, not a repeat of the former).
   Every FREEFORM-TEXT field this module writes that traces back to Layer
   2 or Layer 3 content, an NCBI record body, a PubTator annotation, a
   ClinicalTrials.gov study, model narrative text assembled from any of
   them, or a raw HTTP response header (a `Content-Type` or `Retry-After`
   value this module or a sibling module never controls), is untrusted
   external text per `ai-security-standards.md`'s "treat AI output as
   untrusted" rule, and this module is the one place that text reaches a
   terminal, an execution surface, not a display surface. Two distinct,
   independently sound mechanisms cover it, and a field is protected by
   exactly one:

   a. `_sanitize_untrusted` (defined below), for every freeform string
      this module or `main.py` interpolates directly into an f-string
      before a `self._out`/`self._err`/`err` write: `token.text`,
      `citation.source`, `citation.source_url`, `error.source`,
      `think`/`plan` narrative text, `tool_result.summary`,
      `CliApiError.message` (both `_render_cli_api_error` and
      `_render_http_status_error`, since F-4.2-D-03), the
      `persona_name` the create-run response body carries and
      `_status_prefix` writes on every think and plan line (since
      F-4.5-A-11, which found it exempted by a comment that was wrong
      about where the value came from), the `Content-Type`
      header text in `main.py`'s `_run_login` and in
      `_render_credentials_error`'s general branch (covering
      `credentials.py`'s `RefreshError`, since F-4.2-V4-01), and the
      `Retry-After` header text in `_actionable_suffix_for_status` (also
      F-4.2-V4-01's sweep). It neutralizes every character in a closed
      set of Unicode general categories carrying no legitimate display
      content, `Cc` control bytes (which is what defeats ANSI CSI/OSC
      terminal-control sequences, since both begin with a `Cc` byte),
      `Cf` format characters (which is what defeats a bidirectional
      override, since a hostile source can no longer make a bidi-aware
      terminal display a cited claim in reverse), `Cs` surrogates, and
      `Co` private-use code points, into a visible escaped form, and
      separately escapes any occurrence of this renderer's own closed
      structural vocabulary, the four trust-outcome words in brackets and
      the references header, matched case-insensitively and against
      fullwidth/halfwidth compatibility forms so a hostile source cannot
      forge either one visually either. See `_sanitize_untrusted`'s own
      docstring for the full threat model and the two-option choice this
      ticket's report names.
   b. Python's own `repr()` (the `!r` conversion), for the two
      bounded-length identifier fields this module interpolates as a
      quoted, escaped representation rather than as raw display text:
      `citation.citation_id` (`_handle_citation`'s redefinition warning)
      and a `marker_id` drawn from `token.marker_ids`
      (`_write_references_block`'s unresolved-marker lines). `repr()`
      escapes every non-printable character, `Cc` and `Cf` alike, into
      the same visible `\\xHH`/`\\uHHHH` form `_escape_control_bytes` above
      produces by hand, so a hostile id can never emit a raw control byte
      or bidi override through either of these two sites; it is not a
      gap `_sanitize_untrusted` needs to also cover, and routing an
      already-`repr()`-safe value through it a second time would only
      double-escape a legitimate backslash.

   Every field this module handles that is NOT covered by (a) or (b) is
   not freeform untrusted text at all: it is a closed `Literal` type
   Pydantic validates at `Event` construction (`tool_start.tool`,
   `tool_start.layer`, `tool_result.status`, `cost.model_tier`,
   `trust_signal.outcome`/`done.trust_outcome`), a plain number
   (`citation.display_index`, `cost.query_cost_usd`,
   `done.total_cost_usd`, `done.elapsed_ms`), or a fixed literal this
   module itself owns (`_GUARD_CATEGORY_COPY`,
   `_CLI_FATAL_ERROR_DISCLOSURE`), never server- or Layer-2/3-supplied
   free text, so no sanitizer applies to it.

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
import unicodedata
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
    # Added 2026-09-22 with the `compute_request` category. Not in
    # Section 12.6's table either, for the same reason `write_seeking`
    # is not: the locked section predates the category.
    "compute_request": (
        "this product cannot run a sequence search or read a variant "
        "file. Ask about a specific gene, variant, or paper and it can "
        "assemble cited evidence."
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
    # F-4.2-A-20: the MCP precedent's "Retrying may succeed" (F-4.1-A-09,
    # server.py's own `_MCP_FATAL_ERROR_DISCLOSURE`) does not carry over
    # unedited here. That copy promises a behaviour this surface does not
    # have: main.py's retry policy covers only `stop` and
    # `fetch_citations` (idempotent REST calls via `_call_with_one_refresh`)
    # and, by structural rule, never `create_run`
    # (`_create_run_never_retried`); nothing in this CLI retries the
    # STREAM itself on a fatal `transient` error, so "retrying" is never
    # something the CLI does on the user's behalf. The actionable copy
    # below names the real, available next step instead: run the command
    # again yourself, which starts a genuinely new `s3 ask` (a fresh
    # `POST /v1/query`), never a resumption of this failed one.
    "transient": "this query hit a temporary error before finishing. Run 's3 ask' again to start a new attempt.",
    "recoverable": "this query could not complete as requested.",
    "unexpected": "this query failed unexpectedly before finishing.",
    "cancelled": "this query was stopped before it finished.",
}


def _error_disclosure(error_class: str) -> str:
    return _CLI_FATAL_ERROR_DISCLOSURE.get(error_class, _CLI_FATAL_ERROR_DISCLOSURE["unexpected"])


# ----------------------------------------------------------------------
# Untrusted-content sanitization (F-4.2-A-01, critical; hardened at build
# phase 4.2's round-3 fix, F-4.2-RR-01 and F-4.2-RR-02)
# ----------------------------------------------------------------------
#
# A CLI writes to a terminal, and a terminal EXECUTES control sequences.
# `token.text`, `citation.source`, `citation.source_url`, every narrative
# and summary field this module prints, and `error.source` all trace back
# to Layer 2/3 content or model output built from it, which is untrusted
# external text per `ai-security-standards.md`. Left unescaped, a hostile
# field can clear the screen (`\x1b[2J`), reposition the cursor, retitle
# the window (`\x1b]0;...\x07`), conceal text (`\x1b[8m`), overwrite an
# already-printed line (`\r`), or, the round-3 finding (F-4.2-RR-01), use
# a Unicode bidirectional override (U+202E RIGHT-TO-LEFT OVERRIDE and
# its siblings) to make a bidi-aware terminal DISPLAY a cited clinical
# claim as the opposite of what it actually encodes, with no control byte
# in range 0x00-0x9F involved at all. This is the ONE call site every
# such field is routed through before either stream sees it.
#
# F-4.2-RR-01's fix generalizes the original C0/C1 range check to a
# Unicode GENERAL CATEGORY check (`unicodedata.category`), rather than
# hand-listing the five bidi characters the round-3 verifier happened to
# name: a hand-enumerated set is exactly how this gap arose in the first
# place (C0 and C1 were enumerated and every other control-shaped
# character was implicitly trusted). `_ESCAPED_UNICODE_CATEGORIES` below
# names the categories that carry no legitimate DISPLAY content of their
# own: `Cc` (control, which is what C0/C1 already were, so this is a
# strict superset of the original coverage, never a narrowing), `Cf`
# (format: every bidi embedding/override/isolate control, zero-width
# joiner/non-joiner, the byte-order mark, and the internal zero-width
# padding the round-3 verifier used to defeat the old literal-string
# forgery match), `Cs` (surrogate, reachable via a crafted `\udXXX` JSON
# escape even though Python source text cannot contain one directly), and
# `Co` (private use, code points with no assigned, publicly-defined
# glyph at all, so a terminal or font renders them unpredictably).
# Deliberately NOT escaped: every other category, including `Cn`
# (unassigned) code points and the ordinary letter, mark, number, and
# punctuation categories real biomedical text needs (Greek letters,
# superscripts, em dashes, `p.Arg175His` and `HLA-DRB1*15:01` notation,
# percent signs). No `Cf` character is preserved: every member of that
# category is a formatting instruction to a renderer, never
# content a reader needs to see, so this module escapes the category
# uniformly rather than carve out an exception a future hostile field
# could hide inside.
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
#
# F-4.2-RR-02 hardened this second defence: the original match was
# case-sensitive and literal-ASCII-only, so `[ANSWER]`, a fullwidth
# `［answer］`, or a fullwidth colon in `References：` passed through
# unescaped, each visually close enough to the genuine tag to confuse a
# reader. `_forgery_matching_view` (below) builds a same-length matching
# view of the text, per character, folding a compatibility form (a
# fullwidth or halfwidth glyph) to its canonical ASCII counterpart via
# Unicode NFKC and lowercasing the ASCII range, then matches
# `_FORGERY_PATTERN` against THAT view while still escaping the
# corresponding span of the ORIGINAL text, never the view itself, so a
# legitimate fullwidth CJK passage elsewhere in the same field is never
# rewritten. This does NOT close the harder half of the confusable
# problem: a true cross-script homoglyph, for example Cyrillic 'а'
# (U+0430) standing in for Latin 'a', is canonically distinct from its
# Latin look-alike with no NFKC compatibility mapping between the two, so
# `аnswer` inside brackets still does not match `_FORGERY_PATTERN` today.
# Closing that fully needs Unicode's separate confusables data (UTS #39),
# which this fix does not implement; see `_forgery_matching_view`'s own
# docstring for the same residual stated again at the point it matters.
_ESCAPE_EXEMPT_CHARS = frozenset({"\n"})

# Every Unicode general category this module treats as carrying no
# legitimate DISPLAY content: `Cc` (control, the original C0/C1 range),
# `Cf` (format, every bidi control and zero-width character), `Cs`
# (surrogate), `Co` (private use). See the block comment above for why
# each is included and why no member of `Cf` is exempted.
_ESCAPED_UNICODE_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co"})

# The closed `TrustOutcome` vocabulary (`contracts.events.TrustOutcome`)
# plus the references header, matched only when they appear inside
# UNTRUSTED text, and only ever matched against `_forgery_matching_view`'s
# normalized, lowercased view, never against the original text directly.
# This pattern is never applied to a literal this module itself writes.
_FORGERY_PATTERN = re.compile(r"\[(?P<word>answer|flag|ask|refuse)\]|(?P<ref>references:)")


def _escape_control_bytes(text: str) -> str:
    """Neutralize every character whose Unicode general category is in
    `_ESCAPED_UNICODE_CATEGORIES` (except `\\n`) into a visible, printable
    escape form (`\\xHH`/`\\uHHHH`/`\\UHHHHHHHH`), never a silent deletion:
    a reader can still see something was there, where deletion would let
    an attacker hide content instead of merely fail to forge it. `\\n` is
    exempt because it is common in legitimate narrative text and, on its
    own, only moves the cursor down a line; it carries no terminal-control
    risk the way `\\r` (line overwrite), an ESC-led CSI/OSC sequence, or a
    bidi override (F-4.2-RR-01) does. This alone defeats every ANSI
    CSI/OSC sequence: both begin with the C0 ESC byte (0x1B) or a C1
    single-byte equivalent (0x9B for CSI, 0x9D for OSC), both category
    `Cc`, and once that lead byte is rewritten into printable text, a
    terminal has nothing left to interpret as an escape sequence. It also
    defeats every bidi override/embedding/isolate control (category `Cf`)
    the same way, since a terminal that no longer sees the raw bidi
    control character has nothing left to reorder display around.
    """
    out: list[str] = []
    for ch in text:
        if ch in _ESCAPE_EXEMPT_CHARS:
            out.append(ch)
            continue
        if unicodedata.category(ch) in _ESCAPED_UNICODE_CATEGORIES:
            code = ord(ch)
            if code < 0x100:
                out.append(f"\\x{code:02x}")
            elif code <= 0xFFFF:
                out.append(f"\\u{code:04x}")
            else:
                out.append(f"\\U{code:08x}")
        else:
            out.append(ch)
    return "".join(out)


def _forgery_matching_view(text: str) -> str:
    """Builds a same-LENGTH view of `text` used only to LOCATE a forged
    structural marker; `_escape_forgery_markers` always performs the
    actual escape on the ORIGINAL text at the same index range, never on
    this view, so no legitimate character in the untrusted text is ever
    rewritten by this function.

    Two bounded, well-defined foldings, both applied one character at a
    time so the view's length and index alignment with `text` never
    drifts (a whole-string `unicodedata.normalize` or `str.casefold` can
    both change length, for example a ligature decomposing to two
    characters or German 'ß' casefolding to "ss", either of which would
    silently misalign every index past that point):

        - Unicode NFKC compatibility normalization of each character in
          isolation, kept only when it collapses to exactly one
          character. This folds a fullwidth or halfwidth compatibility
          form (`［`, `Ａ`, `：`) to its canonical ASCII counterpart,
          closing the fullwidth-bracket and fullwidth-colon bypass
          F-4.2-RR-02's verifier found.
        - An ASCII-only (`A`-`Z`) lowercase fold on whatever that leaves,
          so `[ANSWER]`/`[Answer]` match the same as `[answer]` without
          reaching for `str.casefold`, which is not length-preserving in
          general (the German 'ß' case above).

    This does NOT catch a true cross-script homoglyph (a Cyrillic 'а'
    standing in for a Latin 'a'): NFKC is a compatibility-decomposition
    normalization, not a confusables table, and the two letters are
    canonically distinct code points with no compatibility mapping
    between them. Closing that residual needs Unicode's separate
    confusables data (UTS #39), which this fix does not implement; stated
    once more here since it is the one bypass this function still lets
    through.
    """
    view_chars: list[str] = []
    for ch in text:
        folded = unicodedata.normalize("NFKC", ch)
        if len(folded) != 1:
            folded = ch
        if "A" <= folded <= "Z":
            folded = folded.lower()
        view_chars.append(folded)
    return "".join(view_chars)


def _escape_forgery_markers(text: str) -> str:
    """Escape a byte-identical (or, since F-4.2-RR-02, a
    case-folded/compatibility-normalized) copy of this renderer's own
    trust tag or references header wherever one appears inside untrusted
    text, so a forged occurrence can never be indistinguishable from the
    genuine line this module itself writes. Matching happens against
    `_forgery_matching_view(text)`, never `text` itself; the escape
    insertion always applies to the corresponding span of the ORIGINAL
    `text`, preserving whatever characters were actually there. The
    backslash insertion is visible, not a deletion, matching
    `_escape_control_bytes`'s convention above, and keeps this module's
    original insertion point for a plain-ASCII match unchanged: `[answer]`
    embedded in a hostile field becomes the literal text `[\\answer]`
    (backslash right after the opening bracket), and `References:`
    becomes `References\\:` (backslash right before the closing colon). A
    fullwidth or mixed-case match gets the same positional treatment
    against its own original characters, for example `［answer］` becomes
    `［\\answer］`.
    """
    view = _forgery_matching_view(text)
    pieces: list[str] = []
    cursor = 0
    for match in _FORGERY_PATTERN.finditer(view):
        start, end = match.span()
        pieces.append(text[cursor:start])
        if match.group("word") is not None:
            pieces.append(text[start] + "\\" + text[start + 1 : end])
        else:
            pieces.append(text[start : end - 1] + "\\" + text[end - 1 : end])
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


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

    def __init__(
        self,
        out: TextIO,
        err: TextIO,
        *,
        operator: bool,
        persona_name: str | None = None,
    ) -> None:
        self._out = out
        self._err = err
        self._operator = operator
        # T-4.5-10, closing F-4.2-03. Section 13.3 asks the status line to be
        # prefixed with the persona name, and until build phase 4.5 there was
        # no value to prefix it WITH: `persona_name` is resolved once on the
        # `POST /v1/query` response body and never repeated on a streamed
        # event, so this renderer, which only ever sees events, could not
        # invent one. It is now passed in by the caller, which does hold the
        # response body. Optional because a renderer constructed for a run
        # whose create call never returned still has to render the failure.
        self._persona_name = persona_name

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

    def _status_prefix(self, step: str) -> str:
        """The status-line prefix for one agent-loop step (Section 13.3).

        The persona name IS sanitized, and finding F-4.5-A-11 is why this
        docstring now says the opposite of what it used to say. It used to
        claim the name "comes from this process's own curated list via
        `core.persona`, never from the server's event stream", and used that
        claimed provenance to justify writing it raw. The claim was false.
        This process never imports `core.persona`: `CliClient.create_run`
        parses `persona_name` off the `POST /v1/query` response body and
        `main.py` hands that value straight to this renderer. It is a
        server-supplied freeform string, which is exactly the category this
        module's docstring says must go through `_sanitize_untrusted`.

        A terminal is an execution surface, not a display surface. An
        unsanitized name from a hostile server, a `--base-url` pointed at
        one, or any proxy in between, gets ANSI CSI and OSC control
        sequences written to the user's stderr on every think and plan line,
        and can forge this renderer's own structural vocabulary. Nothing
        about the value's shape prevents that; only the sanitizer does.

        Sanitized once here rather than at construction, so there is exactly
        one place the raw value can reach a write, and it is this one.
        """
        if self._persona_name is None:
            return f"[{step}]"
        return f"[{_sanitize_untrusted(self._persona_name)} | {step}]"

    def _handle_think(self, event: Event) -> None:
        payload = ThinkPayload.model_validate(event.payload)
        # F-4.2-03 is closed here: the persona prefix Section 13.3 asks for.
        # It still degrades to the bare label when no name was supplied,
        # rather than fabricating one, which was the correct half of the old
        # behaviour and is kept.
        narrative = _sanitize_untrusted(payload.narrative)
        self._err.write(f"{self._status_prefix('think')} {narrative}\n")
        self._err.flush()

    def _handle_plan(self, event: Event) -> None:
        payload = PlanPayload.model_validate(event.payload)
        narrative = _sanitize_untrusted(payload.narrative)
        self._err.write(f"{self._status_prefix('plan')} {narrative}\n")
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

        # F-4.2-D-04 (round 4): the "References:" header is now gated on
        # `self._citations` alone, not on the combined `not self._citations
        # and not unresolved` condition above (which only decides whether
        # to bail out entirely). Round 2's F-4.2-A-26 fix moved the
        # unresolved-marker note off stdout and onto stderr, which left
        # this header's own guard technically satisfied (there was
        # something to report) while having nothing left to print under
        # it: zero delivered citations plus one or more unresolved markers
        # used to fall through to "\nReferences:\n" with no `[n]` line
        # under it at all, an empty section presented as complete on the
        # exact surface the cite-or-refuse gate's refusal arm exists to
        # police. Printing the header only when there is at least one real
        # citation to list closes that regardless of what `unresolved`
        # contains.
        if self._citations:
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

        if unresolved:
            for marker_id in unresolved:
                # Design decision 1: say so honestly rather than dropping a
                # marker the answer text referenced but never got a
                # citation for, rather than silently omitting it.
                #
                # F-4.2-D-04 (round 4): disclosed on BOTH streams now,
                # reversing half of F-4.2-A-26's move. F-4.2-A-26 moved
                # this note off stdout because it used to sit INSIDE the
                # numbered references list, where a reader of a redirected
                # `answer.txt` could mistake an internal completeness note
                # for a genuine, resolved citation row. That problem was
                # about SHAPE, not STREAM: a redirected
                # `s3 ask "..." > answer.txt` has no other stream a later
                # reader can consult, so stderr-only silence left the one
                # reader who most needs the disclosure, someone auditing
                # the answer file after the fact, with a `[n]` marker and
                # no way to learn it was never actually sourced. The fix
                # keeps stderr for an operator watching the run live, and
                # also writes a distinctly shaped `[unresolved: ...]` line
                # to stdout, a different bracket vocabulary from the
                # numbered `[n] source - url` citation rows above, so it
                # can never be mistaken for a genuine citation the way the
                # pre-A-26 shape could.
                self._out.write(f"[unresolved: marker {marker_id!r} has no citation]\n")
                self._err.write(f"[unresolved] marker {marker_id!r} was never sent a citation\n")
            self._out.flush()
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
            # `done` would have done. The truncation notice itself goes
            # to stderr, matching every other diagnostic in this
            # renderer, and never claims a trust outcome this renderer
            # was never told.
            self._exit_code = _EXIT_FAILURE
            self._err.write(
                "error: the run ended before a final answer was received; "
                "any answer text above is incomplete and its citations may "
                "be partial.\n"
            )
            self._err.flush()

        # F-4.2-D-01 (round 4): this call used to sit ONLY inside the `if`
        # branch above, so it only ever ran on the undetermined-state
        # path (no terminal event reached this renderer at all). A
        # terminal fatal `error` (`_handle_error`) sets `_exit_code`
        # itself, on its own, before `finish()` is ever called, so that
        # path skipped the `if` branch entirely and, unlike
        # `_handle_done`, `_handle_error` never calls
        # `_write_references_block` either. A stopped run is exactly this
        # shape: its terminal event is a fatal `error` with
        # `error_class="cancelled"`, never a `done`, so a citation
        # delivered before the stop used to leave a `[n]` marker on
        # stdout with no references section under it at all, the same
        # defect J-4.2-04 named for the no-terminal-event case, but
        # wider: every stopped run and every fatal server error, not only
        # a dropped connection. Moving this call outside the `if` so it
        # runs on every path fixes that. It is safe unconditionally:
        # `_write_references_block` is idempotent
        # (`self._printed_references` guards it, so a clean `done` that
        # already printed it here is a no-op) and honors the
        # guard-rejection suppression internally (F-4.2-A-27), so a
        # rejected run still prints nothing.
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
    """Renders one of `client.py`'s five typed errors.

    F-4.2-D-03 (round 4): `exc.message` is NOT always the server's own
    curated text. `CliApiError`'s own docstring in `client.py` claims it
    is, but `client.py`'s `_parse_error_detail` falls back to
    `response.text.strip()` for any non-JSON error body (confirmed by
    reading that function directly), so any proxy, CDN, or captive-portal
    error page sitting in front of the API server can reach `exc.message`
    verbatim, with no curation and no sanitization applied anywhere
    upstream of this call site. This function no longer trusts that
    claim: `message` is routed through `_sanitize_untrusted` (module
    docstring, decision 3) the same as every other untrusted field this
    renderer writes, before it ever reaches `err`.
    `_actionable_suffix_for_status` is reused rather than duplicated: it
    is a pure function of status code, reason, and headers, and this call
    site has all three (`exc.status_code`, `exc.reason`, and a
    synthesized `Retry-After` header when `exc` is a `RateLimitedError`
    carrying `retry_after_s`), so the 429/401/403/404/409 action copy
    stays identical to the bare-httpx path instead of drifting into a
    second, hand-maintained copy of the same table.
    """
    from system_03_search_agent.adapters.cli.client import RateLimitedError

    message = exc.message[:500] if exc.message else (
        f"the server refused the request (HTTP {exc.status_code})"
    )
    message = _sanitize_untrusted(message)
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
    """Renders a bare, untyped `httpx.HTTPStatusError` (the fallback shape
    documented on `render_client_error` above).

    F-4.2-D-03 (round 4): `detail`, whether a dict's `message` field or a
    bare string, is parsed straight from the response body this function
    receives, with no upstream curation guaranteed the way
    `_render_cli_api_error`'s docstring used to (incorrectly) claim for
    `CliApiError.message`. `message` is routed through
    `_sanitize_untrusted` before it reaches `err`, closing the same gap
    this function's sibling above closes.
    """
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
    message = _sanitize_untrusted(message)

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
        # F-4.2-V4-01's own sweep, a sixth instance of the same shape
        # found rather than named in this ticket's brief: `headers` here
        # can be the REAL response headers (`_render_http_status_error`'s
        # call site, the bare-`httpx.HTTPStatusError` fallback path), not
        # only the synthetic, already-int-parsed `Headers` object
        # `_render_cli_api_error` builds from `RateLimitedError.
        # retry_after_s` (itself parsed through `client.py`'s own
        # `int(raw_value)`, which can only ever produce a plain integer
        # or None). A raw `Retry-After` header from a hostile or
        # misconfigured proxy is server-controlled content with no
        # sanitizer between it and this function's `wait_clause`, the
        # identical unsanitized-header shape as the two findings this
        # sweep was named for. Routed through `_sanitize_untrusted` here
        # closes it at this function's own boundary rather than at each
        # of its two call sites separately.
        retry_after = headers.get("retry-after")
        wait_clause = f"wait about {_sanitize_untrusted(retry_after)}s" if retry_after else "wait"
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
