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
   what the code actually did). Since card 62's fix round (F-62-A05) it is
   printed when `done` arrives, from `done.trust_outcome`, the server's
   final verdict, which is also what the web, `--json` and the exit code
   read; the answer-scope `trust_signal` arrives immediately before `done`
   on a well-formed stream, so the tag appears at the same moment it did.

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

import json
import re
import unicodedata
import urllib.parse
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
    source_page_key,
)
from system_03_search_agent.contracts.token_order import (
    LISTING,
    joined_text,
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
# establishes this repository's precedent of copying a small fixed table verbatim
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


# Card 62, PR-8.10-01 (`tracker/phase_8.10.md`): the web's own words for an
# `ask` answer that arrives with no trust line (`frontend/src/hooks/
# useRunView.ts`, `OUTCOME_BY_TRUST`), copied rather than imported for the
# same adapter-independence reason as the two tables above. Printed under
# `[answer]` only when the server's final verdict, `done.trust_outcome`, is
# `ask` and `done` carries no trust line: it is the web's rendering of that
# verdict, never a line this renderer composes on its own.
_UNCONFIRMED_WITHOUT_TRUST_LINE = "Single source, not independently confirmed"

# Card 62's fix round (F-62-A01, F-62-A08, F-62-J04): the web's words for a
# run that did not finish (`useRunView.ts`, the `fatalError` branch of the
# trust block). It replaces every verdict there, and it does here: a run
# that ended on a fatal error, or before `done`, prints this and no tag.
_RUN_DID_NOT_FINISH = "Not verified · the run did not finish"

# The two cautions the web never drops beside the trust line (F-62-A02,
# `useRunView.ts`: "Two things are never dropped for it: an ungrounded
# verdict, and a high-risk tier").
_NOT_FULLY_GROUNDED = "Not fully grounded"
_HIGH_RISK_CLAIM = "High-risk claim"
# Parts of one trust line, joined as the web shows them side by side.
_TRUST_PART_SEPARATOR = " · "
# Risk tiers that carry no caution: `low`, and `unknown`, which the core
# sends for a refusal where no risk assessment ran (T-4.3-05). Every other
# value is a caution, including one this renderer does not know, since a
# risk signal should over-report rather than vanish (F-4.8-A-19).
_RISK_TIERS_WITHOUT_CAUTION = frozenset({"low", "unknown"})
_KNOWN_RISK_ORDER = ("moderate", "high", "critical")

# Every Unicode general category a one-line server string must not carry:
# the four `_ESCAPED_UNICODE_CATEGORIES` below (control, format, surrogate,
# private use) plus `Zl` and `Zp`, the line and paragraph separators. `\n`,
# `\r`, `\v`, `\f` and U+0085 are all `Cc`, and U+2028 and U+2029 are `Zl`
# and `Zp`, so no character in any of these categories can start a new line
# on a terminal or in a redirected file.
_LINE_BREAKING_OR_CONTROL_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})
_SPACE_RUN = re.compile(" {2,}")


def _single_line(text: str) -> str:
    """Server text that is printed as one line (the trust line, a risk tier),
    with every character in `_LINE_BREAKING_OR_CONTROL_CATEGORIES` removed,
    decided by Unicode category rather than by a list of characters.

    F-62-A09: a trust line carrying a newline printed a forged reference row
    right under the genuine `[answer]` tag. Each removed character becomes a
    space, runs of spaces collapse to one, and the ends are stripped,
    which is what the web does to the same text inside one `<span>`. The
    renderer's own vocabulary (`[answer]`, `References:`) is still escaped by
    `_escape_forgery_markers`, so the line cannot forge a tag either."""
    kept = "".join(
        " " if unicodedata.category(ch) in _LINE_BREAKING_OR_CONTROL_CATEGORIES else ch
        for ch in text
    )
    # Only spaces are collapsed, so the category check above is the one
    # control that removes a line break.
    return _escape_forgery_markers(_SPACE_RUN.sub(" ", kept).strip())


def _risk_caution(risk_tiers: list[str]) -> str | None:
    """The web's risk mark for the worst tier any trust signal carried, or
    None. `high` reads "High-risk claim", as on the web; another cautionary
    tier reads "<tier> risk claim"; an unrecognised tier outranks every
    known one. `unknown` is ignored rather than ranked, so it can never hide
    a `high` beside it."""
    cautions = [tier for tier in risk_tiers if tier not in _RISK_TIERS_WITHOUT_CAUTION]
    if not cautions:
        return None

    def rank(tier: str) -> int:
        return _KNOWN_RISK_ORDER.index(tier) if tier in _KNOWN_RISK_ORDER else len(_KNOWN_RISK_ORDER)

    worst = max(cautions, key=rank)
    if worst == "high":
        return _HIGH_RISK_CLAIM
    tier_text = _single_line(worst)
    return f"{tier_text} risk claim" if tier_text else _HIGH_RISK_CLAIM


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


def address_for_display(url: str) -> str:
    """The server a base URL names, as a person should see it: its scheme,
    host and port, and nothing else.

    Build phase 8.10's fix round, F-8.10-A05: `s3 login` and `s3 mcp` printed
    the whole base URL, so one written `https://user:pass@host` put the
    password on stdout, on stderr and in every error the agent read. The
    userinfo is never shown, and neither is a path, query or fragment, any
    of which can carry a secret too. Sanitized like any text the person did
    not write, since the URL can come from `--base-url` or `S3_BASE_URL`.
    """
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname or ""
        port = parts.port
    except ValueError:
        host, port = "", None
    if not host:
        return "the server s3 login used"
    if ":" in host:
        host = f"[{host}]"  # an IPv6 address
    address = f"{parts.scheme}://{host}" if parts.scheme else host
    if port is not None:
        address = f"{address}:{port}"
    return _sanitize_untrusted(address)


def _is_ask_back(
    *,
    clarifying_question: str | None,
    guard_rejected: bool,
    fatal_error_seen: bool,
    citations_seen: int,
) -> bool:
    """Whether this run's answer is a question back, not a refusal.

    Build phase 8.10. The core sends a question back ("GERD" gets "What would
    you like to know about GERD?" and four options) through the refusal path,
    so its stream says `refuse`, and every surface tells the two apart. This
    is the same rule builder Q's MCP fold uses (`adapters/mcp/server.py`,
    `_is_ask_back`), which says it mirrors the web's
    (`frontend/src/hooks/useRunView.ts`):

    - a `think` event carried a non-empty clarifying question;
    - the guardrail did not refuse the question;
    - no fatal error ended the run;
    - no citation arrived, so an answer is never relabelled.

    It reads the `think` event, never the refusal's wording.
    """
    if clarifying_question is None or guard_rejected or fatal_error_seen:
        return False
    return citations_seen == 0


def _first_clarification(payload: ThinkPayload) -> tuple[str | None, list[str]]:
    """The clarifying question a `think` event carries, trimmed, and the
    options that came with it; `(None, [])` when it carries none."""
    question = (payload.clarifying_question or "").strip()
    if not question:
        return None, []
    options = [option.strip() for option in payload.clarifying_options or [] if option.strip()]
    return question, options


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
        self._printed_references = False
        # F-4.2-A-27: once a guard rejection has fired, never let a later
        # event (a stray `trust_signal`/`done` the server should not send
        # after a rejection, but this renderer does not get to assume that
        # never happens) print `[answer]` or a references block on top of
        # it. Checked in `_write_verdict` directly, defense in depth
        # regardless of what upstream sends.
        self._guard_rejected = False

        # Build phase 8.10, T-8.10-03: a bare topic ("GERD") gets a question
        # back plus up to four full questions to pick from
        # (`ThinkPayload.clarifying_options`). The web shows them as chips;
        # this surface used to print the question and drop the options.
        # Held from the `think` event and printed, numbered, under the
        # question text just before the trust tag.
        self._clarifying_question: str | None = None
        self._clarifying_options: list[str] = []
        self._printed_options = False
        # What `_is_ask_back` needs besides the question and the guard.
        self._fatal_error_seen = False
        self._citations_seen = 0

        # Card 62's fix round. The verdict block (the tag and the one trust
        # line under it) is printed once, from `done`, the server's final
        # verdict, which is the source the web, `--json` and the exit code
        # read (F-62-A05). Trust signals only feed the two cautions the web
        # keeps beside the line (F-62-A02).
        self._done_seen = False
        self._printed_verdict = False
        self._printed_unfinished = False
        self._trust_signal_seen = False
        self._all_grounded = True
        self._risk_tiers: list[str] = []
        # Whether anything answer-shaped reached stdout, so a run that did
        # not finish says so under it.
        self._answer_written = False
        # Build phase 8.7: listing tokens that arrived before the summary are
        # held and written after it, at `done` or `finish()`, so the summary
        # stays above the records. A stream with no placement holds nothing.
        self._held_listing: list[str] = []

    def _flush_held_listing(self) -> None:
        if not self._held_listing:
            return
        held, self._held_listing = self._held_listing, []
        for text in held:
            self._out.write(text)
        self._out.flush()

    @property
    def offered_options(self) -> bool:
        """True once numbered clarifying options were printed, so `main.py`
        can say how to ask one of them in the same conversation."""
        return self._printed_options

    def _asked_back(self) -> bool:
        return _is_ask_back(
            clarifying_question=self._clarifying_question,
            guard_rejected=self._guard_rejected,
            fatal_error_seen=self._fatal_error_seen,
            citations_seen=self._citations_seen,
        )

    def _is_question_back(self, verdict: TrustOutcome) -> bool:
        """Whether the server's final verdict is a question back: the stream
        labels one `refuse`, and `_is_ask_back` tells it from a refusal. It
        is its own state, never the server's `ask` verdict, which means a
        finished answer that is not yet confirmed (F-62-A01)."""
        return verdict == "refuse" and self._asked_back()

    @staticmethod
    def _tag_word(verdict: TrustOutcome, question_back: bool) -> str:
        """The word inside the printed tag, from the server's final verdict.

        `[ask]` on this surface means a question back with options to pick
        from. The server's `ask` on a finished answer means "answered, not
        yet confirmed", which the web shows as "Answered" with the trust
        line under it, so it is tagged `[answer]` here (card 62,
        PR-8.10-01). `JsonRenderer` still reports `trust_outcome: "ask"`,
        which is the contract."""
        if question_back:
            return "ask"
        if verdict == "ask":
            return "answer"
        return verdict

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
        # The first `think` with a question wins, as on the web and over
        # MCP, and its options are the ones kept: a later event can never
        # swap in a different question.
        if self._clarifying_question is None:
            self._clarifying_question, self._clarifying_options = _first_clarification(payload)

    def _write_clarifying_options(self) -> None:
        """The numbered options under the question, once, and only for a
        question back. Each is untrusted text (built from the reader's own
        words and the server's lookup), so each goes through
        `_sanitize_untrusted` like every answer token."""
        if self._printed_options or not self._clarifying_options or not self._asked_back():
            return
        self._printed_options = True
        lines = "".join(
            f"  {number}. {_sanitize_untrusted(option)}\n"
            for number, option in enumerate(self._clarifying_options, start=1)
        )
        self._out.write(f"\n{lines}")
        self._out.flush()

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
        self._seen_marker_ids.update(payload.marker_ids)
        if payload.text:
            self._answer_written = True
        if payload.placement == LISTING:
            # Held until the summary has been written (build phase 8.7).
            self._held_listing.append(_sanitize_untrusted(payload.text))
            return
        self._out.write(_sanitize_untrusted(payload.text))
        self._out.flush()

    def _handle_citation(self, event: Event) -> None:
        payload = CitationPayload.model_validate(event.payload)
        self._citations_seen += 1
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
        """Records what the web keeps beside the trust line, and prints
        nothing. Every signal counts, claim and answer scope alike, as on
        the web (`useRunView.ts` reads every `trust_signal` for the
        grounded verdict and the worst risk tier).

        Card 62's fix round, F-62-A05: this used to print the tag from the
        first answer-scope signal, so a later `done` saying otherwise could
        not change it, and `s3`'s stdout could contradict its own exit code,
        `--json` and the web. The tag now comes from `done` alone."""
        payload = TrustSignalPayload.model_validate(event.payload)
        if self._guard_rejected:
            return
        self._trust_signal_seen = True
        if not payload.grounded:
            self._all_grounded = False
        self._risk_tiers.append(payload.risk_tier)

    def _trust_line_text(self, verdict: TrustOutcome, trust_line: str | None) -> str:
        """The one trust line under the tag, as the web shows it: "Not fully
        grounded" first when any trust signal was ungrounded, then the
        server's `done.trust_line` (or, for an `ask` verdict with none, the
        web's words for that verdict), then the risk mark. Empty when there
        is nothing the server sent to say. Every server string on it goes
        through `_single_line`."""
        parts: list[str] = []
        if self._trust_signal_seen and not self._all_grounded:
            parts.append(_NOT_FULLY_GROUNDED)
        line = _single_line(trust_line or "")
        if not line and verdict == "ask":
            line = _UNCONFIRMED_WITHOUT_TRUST_LINE
        if line:
            parts.append(line)
        risk = _risk_caution(self._risk_tiers)
        if risk is not None:
            parts.append(risk)
        return _TRUST_PART_SEPARATOR.join(parts)

    def _write_verdict(self, verdict: TrustOutcome, trust_line: str | None) -> None:
        """The tag and the one trust line under it, printed once, from the
        server's final verdict (`done`).

        Nothing is printed on a guard rejection (F-4.2-A-27: its own
        explanation is on stderr), nor after a fatal error: the web shows no
        outcome for a run that did not finish, and `finish` prints its words
        for that instead (F-62-A08). A question back reads `[ask]` with no
        trust line, since it is a question, not an answer; a refusal reads
        `[refuse]` with none either."""
        if self._printed_verdict or self._guard_rejected or self._fatal_error_seen:
            return
        self._printed_verdict = True
        question_back = self._is_question_back(verdict)
        # T-8.10-03: the options belong to the question the tokens just
        # printed, so they go between it and the tag.
        self._write_clarifying_options()
        # J-4.2-05: a leading `\n` guarantees the tag starts its own line
        # whatever the last token ended with.
        block = f"\n[{self._tag_word(verdict, question_back)}]\n"
        # A question back is a `refuse` verdict, so neither carries a line.
        if verdict != "refuse":
            line = self._trust_line_text(verdict, trust_line)
            if line:
                block += f"{line}\n"
        self._out.write(block)
        self._out.flush()

    def _write_unfinished_notice(self) -> None:
        """The web's words for a run that did not finish, under whatever
        answer text and citations already reached stdout, so a reader of a
        redirected file learns what stderr said. Never a verdict: it
        replaces the tag and the trust line (F-62-A01, F-62-J04)."""
        if (
            self._printed_unfinished
            or self._printed_verdict
            or self._guard_rejected
            or not (self._answer_written or self._citations)
        ):
            return
        self._printed_unfinished = True
        self._out.write(f"\n{_RUN_DID_NOT_FINISH}\n")
        self._out.flush()

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
        if payload.fatal:
            self._fatal_error_seen = True

        # Section 13.3: exits nonzero UNLESS fatal is false AND error_class
        # is transient or recoverable, in which case the retry policy (not
        # this renderer) gets a chance first. Read literally: fatal=False
        # with error_class in {unexpected, cancelled} still exits nonzero.
        if payload.fatal or payload.error_class not in ("transient", "recoverable"):
            self._exit_code = _EXIT_FAILURE

    def _handle_done(self, event: Event) -> None:
        payload = DonePayload.model_validate(event.payload)
        self._done_seen = True
        self._flush_held_listing()

        # The tag and the trust line, from the server's final verdict: the
        # same field the web's outcome, `--json`'s `trust_outcome` and the
        # exit code below read (F-62-A05).
        self._write_verdict(payload.trust_outcome, payload.trust_line)
        if self._fatal_error_seen:
            # A fatal error then `done` (a declined run, for one): the run
            # did not finish, and the notice sits where the tag would.
            self._write_unfinished_notice()

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
        # Build phase 8.10: the exit code follows the outcome shown, so a
        # question back exits 0 like any other `[ask]`, and a real refusal
        # still exits 1.
        if self._exit_code is None:
            refused = payload.trust_outcome == "refuse" and not self._is_question_back(
                payload.trust_outcome
            )
            self._exit_code = _EXIT_FAILURE if refused else _EXIT_OK

    # ------------------------------------------------------------------
    # References block
    # ------------------------------------------------------------------

    def _write_references_block(self) -> None:
        if self._printed_references or self._guard_rejected:
            # F-4.2-A-27: the same defense-in-depth guard as
            # `_write_verdict`. A stray `citation`/`done` arriving
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
            # Card 22 fix round (2026-10-06, J-22-06, A-22-08): one line per
            # record PAGE, not per citation. The trust line above says "Based
            # on 16 sources cited", counting distinct pages under
            # `source_page_key`; printing one line per citation listed 18
            # under it, the BRCA1 gene page three times. Every marker that
            # points at one page now sits on that page's line ("[1][6][9]
            # NCBIGene - ..."), in the order the page was first cited, so the
            # numbered lines a person counts are the sources the line names
            # and every marker in the answer still resolves to a line. The
            # first citation's source name and link spelling are printed. A
            # citation with no link is its own line, never merged.
            pages: dict[str, list[CitationPayload]] = {}
            for citation in sorted(self._citations.values(), key=lambda c: c.display_index):
                key = source_page_key(citation.source_url) or f"#{citation.display_index}"
                pages.setdefault(key, []).append(citation)
            for cited in pages.values():
                citation = cited[0]
                markers = "".join(f"[{each.display_index}]" for each in cited)
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
                self._out.write(f"{markers} {source} - {source_url}\n")
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
        self._flush_held_listing()
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
        self._write_clarifying_options()
        # Card 62's fix round (F-62-J04, F-62-A01, F-62-A08): a run that
        # ended on a fatal error or before `done` gets no tag and no trust
        # line, only the web's words for a run that did not finish. Nothing
        # here composes a verdict.
        if self._fatal_error_seen or not self._done_seen:
            self._write_unfinished_notice()
        self._write_references_block()
        return self._exit_code


class JsonRenderer:
    """`s3 ask --json`: the whole answer as one JSON object on stdout.

    Build phase 8.10, T-8.10-03. The Integrations page promised "JSON with
    --json" and no such flag existed. Same interface as `Renderer`
    (`handle()` per event, `finish()` once, returning the exit code), and the
    same exit code for the same stream, so a script can switch modes without
    re-learning what zero means. Nothing is written until `finish()`: a
    consumer parsing stdout gets exactly one complete JSON object, never a
    partial one and never a status line mixed into it.

    Text fields are written as the server sent them rather than through
    `_sanitize_untrusted`, because a JSON consumer needs the true text and a
    forged `[answer]` inside a string cannot pass for a structural field.
    `ensure_ascii=True` is what keeps the output terminal-safe instead: every
    control character, C1 byte and bidi override is written as a `\\uXXXX`
    escape, never as the raw character, so printing the object to a terminal
    executes nothing.

    Keys, all always present:
        run_id, session_id, persona_name: the run and the conversation to
            continue with `s3 ask --session-id`.
        complete: whether a final `done`, a fatal error or a guard
            rejection reached this client. False means the answer is partial.
        trust_outcome, trust_line: the verdict and the one plain trust line.
            A question back reports `ask`, as over MCP, never `refuse`.
        answer: the answer text, joined as the tokens arrived.
        citations: every citation, in display order, with its source URL.
        unresolved_markers: markers the answer used that no citation matched.
        clarifying_question, clarifying_options: a question back, and the
            full questions offered to pick from, or null and an empty list.
        next_step, next_step_query: the offer to go further, when there is one.
        guard: null, or the category and the plain reason a question was
            not taken.
        error: null, or the error class, its source and what to do next.
        stream: frames skipped as unknown, and whether the stream was cut.

    A run that never streams still gets one object with these keys, from
    `write_json_failure` (build phase 8.10's fix round, F-8.10-J08).
    """

    def __init__(
        self,
        out: TextIO,
        err: TextIO,
        *,
        session_id: str,
        run_id: str,
        persona_name: str | None = None,
        stream_state: object | None = None,
    ) -> None:
        self._out = out
        self._err = err
        self._session_id = session_id
        self._run_id = run_id
        self._persona_name = persona_name
        # The `CliClient` whose `stream_skipped_frame_count` and
        # `stream_truncated` are read once, at `finish()`.
        self._stream_state = stream_state
        self._answer_parts: list[TokenPayload] = []
        self._citations: dict[str, CitationPayload] = {}
        self._seen_marker_ids: set[str] = set()
        self._trust_outcome: str | None = None
        self._trust_line: str | None = None
        self._next_step: str | None = None
        self._next_step_query: str | None = None
        self._clarifying_question: str | None = None
        self._clarifying_options: list[str] = []
        self._guard: dict[str, str] | None = None
        self._error: dict[str, object] | None = None
        self._exit_code: int | None = None
        self._written = False
        # What `_is_ask_back` needs, as in `Renderer`.
        self._fatal_error_seen = False
        self._citations_seen = 0

    def _asked_back(self) -> bool:
        return _is_ask_back(
            clarifying_question=self._clarifying_question,
            guard_rejected=self._guard is not None,
            fatal_error_seen=self._fatal_error_seen,
            citations_seen=self._citations_seen,
        )

    def handle(self, event: Event) -> None:
        handler = getattr(self, f"_handle_{event.type}", None)
        if handler is not None:
            handler(event)

    def _handle_guard(self, event: Event) -> None:
        payload = GuardPayload.model_validate(event.payload)
        if payload.passed:
            return
        self._guard = {
            "category": payload.category,
            "message": _GUARD_CATEGORY_COPY.get(payload.category, _GUARD_CATEGORY_FALLBACK),
        }
        self._exit_code = _EXIT_FAILURE

    def _handle_think(self, event: Event) -> None:
        payload = ThinkPayload.model_validate(event.payload)
        # The first `think` with a question wins, with its own options.
        if self._clarifying_question is None:
            self._clarifying_question, self._clarifying_options = _first_clarification(payload)

    def _handle_token(self, event: Event) -> None:
        payload = TokenPayload.model_validate(event.payload)
        self._answer_parts.append(payload)
        self._seen_marker_ids.update(payload.marker_ids)

    def _handle_citation(self, event: Event) -> None:
        payload = CitationPayload.model_validate(event.payload)
        self._citations_seen += 1
        # The first source for an id wins, as in `Renderer` (F-4.2-A-19).
        self._citations.setdefault(payload.citation_id, payload)

    def _handle_trust_signal(self, event: Event) -> None:
        payload = TrustSignalPayload.model_validate(event.payload)
        if payload.scope == "answer" and self._guard is None:
            self._trust_outcome = payload.outcome

    def record_failure(self, error_class: str, message: str) -> None:
        """The stream could not be opened or read to its end, so no event
        will say why. `s3 ask --json` records it here before `finish()`, so
        the one object on stdout carries it (F-8.10-J08). A fatal error the
        stream already sent is kept, since it is the server's own account."""
        if self._error is not None and self._error.get("fatal"):
            return
        self._error = _cli_error(error_class, message)

    def _handle_error(self, event: Event) -> None:
        payload = ErrorPayload.model_validate(event.payload)
        self._error = {
            "fatal": payload.fatal,
            "error_class": payload.error_class,
            "source": payload.source,
            "message": _error_disclosure(payload.error_class),
            "retry_after_s": payload.retry_after_s,
        }
        if payload.fatal:
            self._fatal_error_seen = True
        if payload.fatal or payload.error_class not in ("transient", "recoverable"):
            self._exit_code = _EXIT_FAILURE

    def _handle_done(self, event: Event) -> None:
        payload = DonePayload.model_validate(event.payload)
        if self._guard is None:
            self._trust_outcome = payload.trust_outcome
        self._trust_line = payload.trust_line
        self._next_step = payload.next_step
        self._next_step_query = payload.next_step_query
        # The exit code follows the outcome shown, as in `Renderer`.
        if self._exit_code is None:
            asked_back = payload.trust_outcome == "refuse" and self._asked_back()
            refused = payload.trust_outcome == "refuse" and not asked_back
            self._exit_code = _EXIT_FAILURE if refused else _EXIT_OK

    def finish(self) -> int:
        complete = self._exit_code is not None
        if self._exit_code is None:
            if self._error is None:
                self.record_failure(
                    "stream_incomplete",
                    "s3: the event stream ended with no final answer or error. "
                    "Try again; if it happens again, check the connection to System 3.",
                )
            self._exit_code = _EXIT_FAILURE
        # Build phase 8.10: a question back reports `ask`, as over MCP, and
        # only a question back carries the clarifying question and options.
        asked_back = self._asked_back()
        trust_outcome = self._trust_outcome
        if trust_outcome == "refuse" and asked_back:
            trust_outcome = "ask"
        if not self._written:
            self._written = True
            document = {
                "run_id": self._run_id,
                "session_id": self._session_id,
                "persona_name": self._persona_name,
                "complete": complete,
                "trust_outcome": trust_outcome,
                "trust_line": self._trust_line,
                "answer": joined_text(self._answer_parts),
                "citations": [
                    citation.model_dump(mode="json")
                    for citation in sorted(self._citations.values(), key=lambda c: c.display_index)
                ],
                "unresolved_markers": sorted(self._seen_marker_ids - self._citations.keys()),
                "clarifying_question": self._clarifying_question if asked_back else None,
                "clarifying_options": self._clarifying_options if asked_back else [],
                "next_step": self._next_step,
                "next_step_query": self._next_step_query,
                "guard": self._guard,
                "error": self._error,
                "stream": {
                    "skipped_frames": int(
                        getattr(self._stream_state, "stream_skipped_frame_count", 0) or 0
                    ),
                    "truncated": bool(getattr(self._stream_state, "stream_truncated", False)),
                },
            }
            self._out.write(json.dumps(document, ensure_ascii=True, indent=2) + "\n")
            self._out.flush()
        return self._exit_code


#: Bound on the failure text `s3 ask --json` carries, which is the same
#: words `s3` already wrote to stderr for that failure.
_MAX_JSON_FAILURE_MESSAGE = 2000


def _cli_error(error_class: str, message: str) -> dict[str, object]:
    """The `error` value for a failure `s3` saw itself, in the same shape as
    one the event stream reports, with `source` `"s3"`."""
    return {
        "fatal": True,
        "error_class": error_class,
        "source": "s3",
        "message": message[:_MAX_JSON_FAILURE_MESSAGE],
        "retry_after_s": None,
    }


def write_json_failure(
    out: TextIO,
    *,
    session_id: str | None,
    run_id: str | None,
    persona_name: str | None,
    error_class: str,
    message: str,
) -> None:
    """`s3 ask --json` when the run never started streaming: one JSON
    object on stdout, with every key `JsonRenderer` always writes.

    Build phase 8.10's fix round, F-8.10-J08: a failure before the stream
    started, "not logged in" for one, wrote only to stderr, so a script
    parsing stdout got nothing to parse. Now it gets `complete: false`, an
    empty answer, and `error` naming the class and the same words stderr
    shows. The exit code is still non-zero; the caller returns it."""
    document = {
        "run_id": run_id,
        "session_id": session_id,
        "persona_name": persona_name,
        "complete": False,
        "trust_outcome": None,
        "trust_line": None,
        "answer": "",
        "citations": [],
        "unresolved_markers": [],
        "clarifying_question": None,
        "clarifying_options": [],
        "next_step": None,
        "next_step_query": None,
        "guard": None,
        "error": _cli_error(error_class, message),
        "stream": {"skipped_frames": 0, "truncated": False},
    }
    out.write(json.dumps(document, ensure_ascii=True, indent=2) + "\n")
    out.flush()


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
