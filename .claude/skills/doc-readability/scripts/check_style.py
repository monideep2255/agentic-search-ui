#!/usr/bin/env python3
"""Check one markdown document against .claude/rules/writing-style.md.

The `doc-readability` skill restructures a document, adds a table of
contents, and adds diagrams. This script is the house-style gate that runs
on the RESULT: it never needs a before version, it only ever looks at the
one file it is pointed at.

WHAT THIS SCRIPT DOES NOT CHECK

Stated here because `.claude/rules/goal-contracts.md` requires a verify
surface to declare its own coverage, so a gap is arguable from the gate
itself rather than re-derived by the next reader.

  - Whether a fact is stale. That is `tracker/check_doc_drift.py`'s job: it
    computes each tracked count from source and flags a document that
    states an old value as current.
  - Whether a fact survived a rewrite. That is the sibling
    `check_preservation.py` in this same directory: it compares a before
    and an after version and fails on a dropped atom or an orphaned claim.
    This script takes one file, never two, and never compares anything.
  - Whether a file was adapted from another repository correctly. That is
    `.claude/skills/skill-adapt-verify/scripts/verify_adaptation.py`, which
    only ever targets files under `.claude/` and shares exactly one regex
    with this script, the em-dash/en-dash character class, because both
    scripts independently need to catch the same AI-written-text signal.
  - Whether the writing is good. Every arm below is structural: line
    length, a heading's second word, a fence's language tag. None of it
    reads for meaning, clarity, or argument quality.
  - Whether a Mermaid diagram is correct or parses. No renderer is
    bundled. The mermaid-labels arm checks label TEXT (length, literal
    `\\n`, `<br/>`); it never checks that the diagram is valid Mermaid
    syntax.

SEVERITY MODEL

Two severities. HARD findings are the gate: any HARD finding sets exit
code 1. ADVISORY findings print in every report but never change the exit
code on their own, because a gate that hard-fails on a judgment call gets
disabled rather than fixed; `--advisory` promotes them to blocking for one
run when the caller wants that stricter bar.

THE ARMS

  1. Prose walls (HARD). The arm this script exists for. A paragraph line
     outside a fence, heading, table row, or list item either exceeds
     `--wall-length` characters, or chains three or more items on commas
     or semicolons in one sentence. See `check_prose_walls` for why this
     operates per PHYSICAL line rather than joining wrapped continuation
     lines into one paragraph the way `check_preservation.py`'s `segment()`
     does: that machinery belongs to the no-loss comparison, not to this
     gate, and duplicating it here was explicitly out of scope for this
     script.
  2. ToC required and missing (HARD). The exact complement of
     `check_doc_drift.check_toc`, which only validates an EXISTING table of
     contents and returns no findings when one is simply absent. This arm
     is the other half: a document with 3 or more `## ` sections or over
     roughly 100 lines and no `## Table of contents` heading at all.
  3. ToC matches body (HARD). Delegates straight to
     `check_doc_drift.check_toc`. This also covers a brand-new untracked
     file, which `check_doc_drift.py` itself cannot see because it
     enumerates files through `git ls-files`.
  4. Bold (HARD). `**text**` outside a fence and outside inline code.
  5. Em dash / en dash (HARD). The measured corpus baseline is ZERO across
     all 171 tracked markdown files in this repository as of the sweep
     that shaped this script. A finding here is a new occurrence, not
     background noise, and a clean run on this arm is not evidence the
     arm did nothing; it is evidence the baseline held.
  6. Heading case (ADVISORY). A `##`-or-deeper heading whose second or
     later word is capitalized outside an allowlist of months, days,
     acronyms, backticked spans, and a bundled proper-noun list. ADVISORY
     because the allowlist is necessarily lossy; treat a finding here as a
     prompt to check, not an automatic defect.
  7. Mermaid labels (HARD). Inside a ```mermaid fence, a node or edge
     label containing a literal `\\n`, a `<br/>`, or longer than 30
     characters.
  8. Mermaid presence (ADVISORY). A document with 3 or more `## ` sections
     that reads, by a keyword heuristic, as describing a sequence,
     pipeline, flow, or layered architecture, and contains no ```mermaid
     fence. ADVISORY because "should this document have a diagram" is a
     judgment call, not a structural fact.

USAGE

  check_style.py <path> [--check] [--verbose] [--advisory]
  check_style.py --dir <directory>     # report-only sweep, never edits
  check_style.py --self-test
  check_style.py --mutation-test

  --wall-length N    tighten only (a SMALLER number catches more; a
                      larger value than the default is rejected)

  Exit 0  clean (no HARD findings, or no findings at all under --advisory)
       1  HARD findings (or, under --advisory, any findings)
       2  bad invocation, a loosened threshold, or a missing directory
       3  locked document refused
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------
# Locate the repository root and pull in the reusable pieces
# --------------------------------------------------------------------------

# This script sits at .claude/skills/doc-readability/scripts/check_style.py,
# four directories below the repository root: scripts, doc-readability,
# skills, .claude. parents[4] from the file itself lands on the root.
REPO_ROOT = Path(__file__).resolve().parents[4]
TRACKER_DIR = REPO_ROOT / "tracker"

sys.path.insert(0, str(TRACKER_DIR))
try:
    import check_doc_drift
except ImportError as exc:
    print(
        f"error: cannot import check_doc_drift from {TRACKER_DIR}: {exc}",
        file=sys.stderr,
    )
    print(
        "this script reuses fenced_line_mask, heading_index, slugify, "
        "dedupe_slugs, and check_toc from tracker/check_doc_drift.py rather "
        "than reimplementing them, and refuses to run without that import "
        "rather than degrading to a silent skip",
        file=sys.stderr,
    )
    sys.exit(2)


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

# Locked documents, frozen until the Step 6.2 reconciliation. Mirrors
# SKIP_FILES in tracker/check_doc_drift.py and LOCKED_DOCS in the sibling
# check_preservation.py.
LOCKED_DOCS = {
    "requirements/PRD.md",
    "requirements/Technical_specification.md",
}

# Chosen from a calibration sweep of the 62 tracked markdown files under
# docs/, requirements/, and the repository root (see the calibration notes
# in the phase report; the number is not re-derived here because a
# calibration constant belongs in one place, not scattered across a
# docstring and the code that uses it). 400 flagged 41 of 62 files and 588
# lines, which drowns the corpus; 700 flagged only 14 files and missed real
# offenders. 600 flagged 24 files and 251 lines, and reproduced the one
# fully line-numbered ground truth available (docs/build/
# Build_workflow_cadence.md: 5 lines over 500, 3 over 600, at the same line
# numbers) exactly.
DEFAULT_WALL_LENGTH = 600

MIN_H2_FOR_TOC = 3
MIN_LINES_FOR_TOC = 100

MAX_MERMAID_LABEL = 30

HARD = "HARD"
ADVISORY = "ADVISORY"

# Words a heading's second-or-later word is allowed to capitalize without
# tripping the heading-case arm. Bundled proper nouns from
# .claude/rules/writing-style.md's sentence-case rule.
PROPER_NOUN_ALLOWLIST = {
    "monideep", "ncbi", "nih", "hetzner", "postgresql", "age", "kgx",
    "biolink", "linkml", "cypher", "mlops", "knn", "t-sne", "python",
    "fastapi", "langgraph", "react", "graphql", "redis", "caddy",
    "mermaid", "claude", "github",
}

# "Let's Encrypt" is the one two-word entry in the allowlist and is checked
# as an adjacent pair rather than folded into the single-token set above.
LETS_ENCRYPT_PAIR = ("let's", "encrypt")

MONTHS_SET = {
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
}
DAYS_SET = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday",
}

# A run of 2+ uppercase letters, with an optional trailing apostrophe-s or
# bare s, covers the acronym examples writing-style.md names directly:
# AI, ML, NLP, RAG, LLM, SVMs, APIs.
ACRONYM_RE = re.compile(r"^[A-Z]{2,}'?s?$")

# Keyword heuristic for the mermaid-presence advisory. Deliberately broad:
# an advisory that never fires teaches nothing, and a false positive here
# costs a reader one glance, not a build failure.
MERMAID_KEYWORDS_RE = re.compile(
    r"\b(sequence|pipeline|flow|workflow|stages?|layered|architecture|"
    r"orchestrat\w*|loop)\b",
    re.IGNORECASE,
)

LIST_ITEM_RE = re.compile(r"^(?:[-*+]|\d+\.)\s+")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
BOLD_RE = re.compile(r"\*\*[^\n]+?\*\*")
DASH_RE = re.compile(r"[–—]")
BR_TAG_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})\s*([A-Za-z0-9_+\-]*)")

# One alternation covering the five bracket shapes Mermaid uses for a node
# or edge label: [box], ((circle)), {{hexagon}}, {rhombus}, |edge label|.
# The double-paren and double-brace alternatives are tried before their
# single-character counterparts so `id((Start))` is captured whole rather
# than as two nested single-paren matches.
MERMAID_LABEL_RE = re.compile(
    r"\[([^\[\]]*)\]"
    r"|\(\(([^()]*)\)\)"
    r"|\{\{([^{}]*)\}\}"
    r"|\{([^{}]*)\}"
    r"|\|([^|]*)\|"
)

EXCLUDED_DIR_PARTS = {"node_modules", "reference", "venv", ".git", "tracker", ".claude"}


@dataclass
class Finding:
    kind: str
    severity: str
    path: str
    line: int
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: [{self.severity}] [{self.kind}] {self.message}"


# --------------------------------------------------------------------------
# Small shared helpers
# --------------------------------------------------------------------------


def _strip_inline_code(line: str) -> str:
    """Blank out `inline code` spans, same length, so a `**` or a dash
    typed inside a code span never trips the bold or dash arm."""
    return INLINE_CODE_RE.sub(lambda m: " " * len(m.group()), line)


def _h2_headings(lines: list[str], mask: list[bool]) -> list[tuple[int, str]]:
    """`## ` headings only, reusing check_doc_drift.heading_index rather
    than re-scanning the file with a second heading regex.

    heading_index returns every '#'-prefixed line regardless of level, so
    filtering to exactly two leading hashes happens here against the raw
    line it points at.
    """
    out = []
    for i, text in check_doc_drift.heading_index(lines, mask):
        raw = lines[i]
        if raw.startswith("## ") and not raw.startswith("### "):
            out.append((i, text))
    return out


def _has_toc_heading(lines: list[str], mask: list[bool]) -> bool:
    for _, text in check_doc_drift.heading_index(lines, mask):
        if text.strip().lower() == "table of contents":
            return True
    return False


def _fence_langs(lines: list[str]) -> list[tuple[int, int, str]]:
    """(start, end, lang) for every fenced block, end exclusive, lang
    lowercased. check_doc_drift.fenced_line_mask only reports whether a
    line sits inside SOME fence, not which language; the mermaid arms need
    the language tag, so this is a small, purpose-built scan rather than a
    reuse of that mask, and it is intentionally not the general-purpose
    segmentation machinery the sibling check_preservation.py owns.
    """
    spans: list[tuple[int, int, str]] = []
    i = 0
    while i < len(lines):
        m = FENCE_OPEN_RE.match(lines[i].strip())
        if not m:
            i += 1
            continue
        delim, lang = m.group(1), (m.group(2) or "").lower()
        char, width = delim[0], len(delim)
        j = i + 1
        while j < len(lines):
            s = lines[j].strip()
            if len(s) >= width and s[:width] == char * width and set(s) <= {char}:
                break
            j += 1
        spans.append((i, min(j + 1, len(lines)), lang))
        i = j + 1
    return spans


# --------------------------------------------------------------------------
# Arm 1: prose walls
# --------------------------------------------------------------------------


def _wall_excluded(stripped: str) -> bool:
    """A blank line, a heading, a table row, or a list item is never a
    prose wall by definition. This checks only the line's OWN leading
    marker: a bullet's wrapped continuation line, which carries no marker
    of its own, is still evaluated as a paragraph line. That is a known,
    deliberate simplification, not an oversight: joining a wrapped bullet
    back into one logical paragraph is the job the sibling
    check_preservation.py's segment() already does for a different
    purpose, and duplicating it here was explicitly out of scope. It also
    happens to be the behavior that reproduces this repository's one
    fully line-numbered ground truth exactly (docs/build/
    Build_workflow_cadence.md, lines 146, 150, 152, 166, 168 at 500
    characters).
    """
    return (
        not stripped
        or stripped.startswith("#")
        or stripped.startswith("|")
        or bool(LIST_ITEM_RE.match(stripped))
    )


def _comma_chain_items(text: str) -> list[str]:
    """Split on top-level commas and semicolons, ignoring anything inside
    backticks, parens, brackets, or braces, and with a markdown link
    target dropped first so a URL's own punctuation never inflates the
    count. This is a heuristic approximation of "items enumerated in
    prose", not a parse: a comma inside a subordinate clause ("The agent,
    which runs continuously, updates state.") can still read as three
    parts. writing-style.md's own "no prose walls" section accepts that
    trade-off explicitly for the same reason check_preservation.py accepts
    false positives over false negatives: a missed wall costs nothing, a
    wall that never fires trains a reader to ignore it.
    """
    scrubbed = _strip_inline_code(text)
    scrubbed = re.sub(r"\(https?://[^)]*\)", " ", scrubbed)
    depth = 0
    parts: list[str] = []
    current: list[str] = []
    for ch in scrubbed:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if ch in ",;" and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    parts.append("".join(current).strip())
    return [p for p in parts if p]


# A segment opening with one of these is a subordinate or contrastive
# clause, not an item in a series. Their presence is what separates
# "a X that does A, a Y that does B, and a Z that does C" (a list wearing
# a paragraph, which writing-style.md names as the smell) from ordinary
# prose that merely contains commas.
# Mean words per item below which a comma series is treated as a bare noun
# list rather than an enumeration of facts.
MIN_SERIES_ITEM_WORDS = 4.0

_NON_SERIES_OPENERS = {
    "because", "which", "who", "whom", "whose", "that", "so", "since",
    "when", "where", "while", "though", "although", "if", "unless",
    "until", "after", "before", "as", "but", "not", "rather",
}


def _split_sentences_for_walls(text: str) -> list[str]:
    """Count a series WITHIN one sentence, never across a line.

    Counting across the whole line pooled the commas of two unrelated
    sentences and reported a wall where neither sentence had one. Measured
    on docs/build/Build_workflow_cadence.md, that alone accounted for
    several of the arm's false positives.
    """
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'`(])", text)
    return [p for p in (x.strip() for x in parts) if p]


def _is_series(items: list[str]) -> bool:
    """True only for a real enumeration: three or more parallel items whose
    LAST one is introduced by a coordinator.

    This arm used to fire on any line with three top-level commas. Measured
    against a real document, 10 of its 14 findings were ordinary prose
    carrying subordinate clauses and appositives, and an arm that is wrong
    most of the time is one a reader learns to skip, which is precisely
    the failure its own docstring said it was avoiding. Requiring the
    coordinator and rejecting subordinate openers is what distinguishes an
    enumeration from a sentence that merely has commas in it.
    """
    if len(items) < 3:
        return False
    # The coordinator does not have to open the FINAL segment. A series
    # often carries a trailing modifier ("A, B, and C, closing out the
    # stage"), and anchoring on the last segment misses every one of
    # those. Anchor on the last segment that opens with a coordinator
    # instead, and require at least three items up to that point.
    coord = -1
    for idx in range(1, len(items)):
        head = items[idx].strip().lower()
        if head.startswith("and ") or head.startswith("or ") or head in ("and", "or"):
            coord = idx
    if coord < 2:
        return False
    items = items[: coord + 1]
    # A bare noun list is ordinary English, not a list wearing a
    # paragraph. writing-style.md's own smell test is "a X that does A, a
    # Y that does B, and a Z that does C", where every item carries its
    # own predicate, and a predicate takes words. Measured on README.md:
    # "questions about genes, diseases, variants, publications, and
    # taxonomy" averages 1.2 words per item and reads correctly as prose,
    # while every genuine wall found so far averages 4 or more.
    words_per_item = sum(len(i.split()) for i in items) / len(items)
    if words_per_item < MIN_SERIES_ITEM_WORDS:
        return False
    # Only segments AFTER the first are checked. A real series opens with
    # the sentence's own subject ("The tool reads Layer 1 for the graph,
    # ..."), so testing the first segment rejects every genuine series.
    for item in items[1:]:
        words = item.strip().lower().split()
        if not words:
            return False
        head = words[0].strip(".,;:!?`\"'")
        if head in _NON_SERIES_OPENERS:
            return False
    return True


def check_prose_walls(
    rel: str, lines: list[str], mask: list[bool], wall_length: int
) -> list[Finding]:
    findings: list[Finding] = []
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        stripped = line.strip()
        if _wall_excluded(stripped):
            continue
        if len(line) > wall_length:
            findings.append(Finding(
                "wall-length", HARD, rel, i + 1,
                f"paragraph line is {len(line)} characters, over the "
                f"{wall_length}-character wall threshold; break into a "
                f"bulleted list or a table per writing-style.md",
            ))
            continue
        for sentence in _split_sentences_for_walls(stripped):
            items = _comma_chain_items(sentence)
            if _is_series(items):
                findings.append(Finding(
                    "wall-comma-chain", HARD, rel, i + 1,
                    f"prose sentence enumerates {len(items)} items chained by "
                    f"commas or semicolons; render as a bulleted list per "
                    f"writing-style.md's 'No prose walls' section",
                ))
                break
    return findings


# --------------------------------------------------------------------------
# Arm 2 and 3: table of contents
# --------------------------------------------------------------------------


def check_toc_missing(rel: str, lines: list[str], mask: list[bool]) -> list[Finding]:
    """The exact complement of check_doc_drift.check_toc: that function
    only validates an EXISTING '## Table of contents' section and returns
    no findings at all when one is simply absent. This function is the
    other half, firing when a document large enough to need one has none.
    """
    headings = _h2_headings(lines, mask)
    total_lines = len(lines)
    if len(headings) < MIN_H2_FOR_TOC and total_lines <= MIN_LINES_FOR_TOC:
        return []
    if _has_toc_heading(lines, mask):
        return []
    raw_slugs = [check_doc_drift.slugify(text) for _, text in headings]
    slugs = check_doc_drift.dedupe_slugs(raw_slugs)
    preview = ", ".join(f"#{s}" for s in slugs[:6])
    more = "" if len(slugs) <= 6 else f", plus {len(slugs) - 6} more"
    return [Finding(
        "toc-missing", HARD, rel, 1,
        f"{len(headings)} ## sections and {total_lines} lines, but no "
        f"'## Table of contents' section; writing-style.md requires one at "
        f"3+ sections or over roughly 100 lines. Expected anchors: "
        f"{preview}{more}",
    )]


def check_toc_match(rel: str, lines: list[str], mask: list[bool]) -> list[Finding]:
    """Delegates to check_doc_drift.check_toc. Also covers a brand-new
    untracked file, which check_doc_drift.py cannot see on its own because
    it enumerates files through `git ls-files`.
    """
    return [
        Finding("toc-mismatch", HARD, f.path, f.line, f.message)
        for f in check_doc_drift.check_toc(rel, lines, mask)
    ]


# --------------------------------------------------------------------------
# Arm 4: bold
# --------------------------------------------------------------------------


def check_bold(rel: str, lines: list[str], mask: list[bool]) -> list[Finding]:
    findings = []
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        scrubbed = _strip_inline_code(line)
        for m in BOLD_RE.finditer(scrubbed):
            findings.append(Finding(
                "bold", HARD, rel, i + 1,
                f"bold text {m.group()!r} outside a fence; "
                f"writing-style.md bans bold, use \"label:\" instead",
            ))
    return findings


# --------------------------------------------------------------------------
# Arm 5: em dash / en dash
# --------------------------------------------------------------------------


def check_dashes(rel: str, lines: list[str], mask: list[bool]) -> list[Finding]:
    """The measured corpus baseline is ZERO across all 171 tracked
    markdown files as of the sweep that shaped this script. A finding here
    is a new occurrence in a document that has never had one, not
    background noise a reader should learn to skip past.
    """
    findings = []
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        scrubbed = _strip_inline_code(line)
        for m in DASH_RE.finditer(scrubbed):
            name = "en dash" if m.group() == "–" else "em dash"
            findings.append(Finding(
                "dash", HARD, rel, i + 1,
                f"{name} character found; the corpus baseline for this "
                f"repository is zero across all 171 tracked markdown "
                f"files, so this is a new occurrence, not noise",
            ))
    return findings


# --------------------------------------------------------------------------
# Arm 6: heading case
# --------------------------------------------------------------------------


def _is_acronym(word: str) -> bool:
    return bool(ACRONYM_RE.match(word))


def check_heading_case(rel: str, lines: list[str], mask: list[bool]) -> list[Finding]:
    findings = []
    for i, text in check_doc_drift.heading_index(lines, mask):
        raw = lines[i]
        if not raw.startswith("##"):
            continue  # H1 (single '#') is out of scope for the "##+" rule
        scrubbed = _strip_inline_code(text)
        words = re.findall(r"[A-Za-z][A-Za-z'\-]*", scrubbed)
        # A capitalized word followed by a number is a designator, not
        # title case: "System 1", "Layer 2", "Phase 6", "Section 25" are
        # all names in this project. Detected structurally rather than by
        # growing the allowlist, since the pattern generalizes and the
        # allowlist does not.
        tokens = re.findall(r"[A-Za-z][A-Za-z'\-]*|\d+", scrubbed)
        designators = set()
        for t_idx, tok in enumerate(tokens):
            if tok[0].isalpha() and t_idx + 1 < len(tokens) and tokens[t_idx + 1].isdigit():
                designators.add(tok.lower())
        reported: set = set()
        for idx, word in enumerate(words):
            if idx == 0:
                continue
            if word.lower() in designators:
                continue
            # One finding per distinct word per heading. "Connection to
            # System 1 and System 2" reported "System" twice, which reads
            # as a duplicate defect rather than one heading to fix.
            if word.lower() in reported:
                continue
            if not word[0].isupper():
                continue
            lw = word.lower()
            if lw in MONTHS_SET or lw in DAYS_SET:
                continue
            if _is_acronym(word):
                continue
            if lw in PROPER_NOUN_ALLOWLIST:
                continue
            if (
                lw == LETS_ENCRYPT_PAIR[0]
                and idx + 1 < len(words)
                and words[idx + 1].lower() == LETS_ENCRYPT_PAIR[1]
            ):
                continue
            if (
                lw == LETS_ENCRYPT_PAIR[1]
                and idx > 0
                and words[idx - 1].lower() == LETS_ENCRYPT_PAIR[0]
            ):
                continue
            reported.add(word.lower())
            findings.append(Finding(
                "heading-case", ADVISORY, rel, i + 1,
                f'heading word "{word}" is capitalized outside the '
                f"allowlist; writing-style.md wants sentence case (only "
                f"the first word, proper nouns, acronyms, months, and "
                f"days capitalized)",
            ))
    return findings


# --------------------------------------------------------------------------
# Arm 7 and 8: mermaid
# --------------------------------------------------------------------------


def check_mermaid_labels(rel: str, lines: list[str]) -> list[Finding]:
    findings = []
    for start, end, lang in _fence_langs(lines):
        if lang != "mermaid":
            continue
        for i in range(start + 1, max(start + 1, end - 1)):
            for m in MERMAID_LABEL_RE.finditer(lines[i]):
                label = next(g for g in m.groups() if g is not None)
                if "\\n" in label:
                    findings.append(Finding(
                        "mermaid-label", HARD, rel, i + 1,
                        f"mermaid label {label!r} contains a literal "
                        f"\\n; split into separate nodes instead",
                    ))
                elif BR_TAG_RE.search(label):
                    findings.append(Finding(
                        "mermaid-label", HARD, rel, i + 1,
                        f"mermaid label {label!r} contains <br/>; "
                        f"split into separate nodes instead",
                    ))
                elif len(label) > MAX_MERMAID_LABEL:
                    findings.append(Finding(
                        "mermaid-label", HARD, rel, i + 1,
                        f"mermaid label {label!r} is {len(label)} "
                        f"characters, over the {MAX_MERMAID_LABEL}-"
                        f"character limit",
                    ))
    return findings


def check_mermaid_presence(rel: str, lines: list[str], mask: list[bool]) -> list[Finding]:
    headings = _h2_headings(lines, mask)
    if len(headings) < MIN_H2_FOR_TOC:
        return []
    body_text = "\n".join(line for i, line in enumerate(lines) if not mask[i])
    if not MERMAID_KEYWORDS_RE.search(body_text):
        return []
    if any(lang == "mermaid" for _, _, lang in _fence_langs(lines)):
        return []
    return [Finding(
        "mermaid-missing", ADVISORY, rel, 1,
        f"{len(headings)} ## sections describing a sequence, pipeline, "
        f"flow, or layered architecture by keyword, but no ```mermaid "
        f"fence; a diagram may help the reader, per writing-style.md",
    )]


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def run_all_checks(rel: str, text: str, wall_length: int) -> list[Finding]:
    lines = text.splitlines()
    mask = check_doc_drift.fenced_line_mask(lines)
    findings: list[Finding] = []
    findings.extend(check_prose_walls(rel, lines, mask, wall_length))
    findings.extend(check_toc_missing(rel, lines, mask))
    findings.extend(check_toc_match(rel, lines, mask))
    findings.extend(check_bold(rel, lines, mask))
    findings.extend(check_dashes(rel, lines, mask))
    findings.extend(check_heading_case(rel, lines, mask))
    findings.extend(check_mermaid_labels(rel, lines))
    findings.extend(check_mermaid_presence(rel, lines, mask))
    return findings


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------


def _run(checker, text, **kwargs):
    lines = text.splitlines()
    mask = check_doc_drift.fenced_line_mask(lines)
    if checker is check_mermaid_labels:
        return checker("self-test", lines)
    return checker("self-test", lines, mask, **kwargs)


def _self_test_cases() -> list[tuple]:
    """(name, checker, text, kwargs, should_fire). One true positive and
    one true negative per arm, so every arm proves it can fail as well as
    pass, per this repository's documented history of vacuous gate arms
    (LEARNINGS.md, build phases 4.3, 4.7, 4.11: three separate vacuous-
    gate-arm findings across three phases, one of them written twice)."""
    long_sentence = (
        "The stages run through the probe and then continue onward "
        "through several review gates before the dispatch step finally "
        "begins its work in earnest, which takes a while to describe. "
    ) * 4

    toc_doc_missing = (
        "# Title\n\n"
        "## First section\n\nSome text.\n\n"
        "## Second section\n\nMore text.\n\n"
        "## Third section\n\nEven more text.\n"
    )
    toc_doc_present = "## Table of contents\n\n" + toc_doc_missing

    toc_match_bad = (
        "# Title\n\n## Table of contents\n\n"
        "- [Wrong section](#wrong-anchor)\n\n"
        "## Real section\n\nText.\n"
    )
    toc_match_good = (
        "# Title\n\n## Table of contents\n\n"
        "- [Real section](#real-section)\n\n"
        "## Real section\n\nText.\n"
    )

    mermaid_presence_doc = (
        "# Title\n\n## Pipeline overview\n\n"
        "This section describes the pipeline flow.\n\n"
        "## Second section\n\nText.\n\n## Third section\n\nText.\n"
    )
    mermaid_presence_with_fence = mermaid_presence_doc + (
        "\n```mermaid\nflowchart TD\n  a[Start] --> b[End]\n```\n"
    )

    return [
        ("wall-length TP", check_prose_walls, long_sentence,
         dict(wall_length=DEFAULT_WALL_LENGTH), True),
        ("wall-length TN, same content as a bullet",
         check_prose_walls, "- " + long_sentence.strip(),
         dict(wall_length=DEFAULT_WALL_LENGTH), False),
        ("wall-comma-chain TP",
         check_prose_walls,
         "The tool reads Layer 1 for the graph, Layer 2 for the live "
         "APIs, and Layer 3 for the enrichment sources before it writes "
         "an answer.",
         dict(wall_length=DEFAULT_WALL_LENGTH), True),
        ("wall-comma-chain TN, no chain",
         check_prose_walls,
         "The tool reads the graph before it writes an answer.",
         dict(wall_length=DEFAULT_WALL_LENGTH), False),
        ("toc-missing TP", check_toc_missing, toc_doc_missing, {}, True),
        ("toc-missing TN, ToC heading present",
         check_toc_missing, toc_doc_present, {}, False),
        ("toc-mismatch TP", check_toc_match, toc_match_bad, {}, True),
        ("toc-mismatch TN, links match body",
         check_toc_match, toc_match_good, {}, False),
        ("bold TP", check_bold, "This has **bold text** in it.", {}, True),
        ("bold TN, plain text",
         check_bold, "This has plain text with no bold markers.", {}, False),
        ("dash TP", check_dashes,
         "This uses an em dash — right here.", {}, True),
        ("dash TN, regular hyphen",
         check_dashes, "This uses a regular hyphen-only sentence.", {}, False),
        ("heading-case TP", check_heading_case,
         "## Key Trade-offs\n\nText.", {}, True),
        ("heading-case TN, sentence case",
         check_heading_case, "## Key trade-offs\n\nText.", {}, False),
        ("mermaid-label TP",
         check_mermaid_labels,
         "```mermaid\nflowchart TD\n"
         "  a[This label is definitely far longer than thirty "
         "characters] --> b[ok]\n```\n",
         {}, True),
        ("mermaid-label TN, short labels",
         check_mermaid_labels,
         "```mermaid\nflowchart TD\n  a[Start] --> b[End]\n```\n",
         {}, False),
        ("mermaid-missing TP", check_mermaid_presence,
         mermaid_presence_doc, {}, True),
        ("mermaid-missing TN, fence present",
         check_mermaid_presence, mermaid_presence_with_fence, {}, False),
    ]


def run_self_test() -> int:
    failures = 0
    cases = _self_test_cases()
    for name, checker, text, kwargs, should_fire in cases:
        findings = _run(checker, text, **kwargs)
        fired = bool(findings)
        ok = fired == should_fire
        expect = "findings" if should_fire else "clean"
        got = "findings" if fired else "clean"
        print(f"{'PASS' if ok else 'FAIL'}  {name} (expected {expect}, got {got})")
        if not ok:
            failures += 1
            for f in findings[:3]:
                print(f"        {f.format()}")
    print()
    print(f"{'ok' if failures == 0 else 'error'}: {len(cases)} self-test cases, "
          f"{failures} failed")
    return failures


# --------------------------------------------------------------------------
# Mutation harness
# --------------------------------------------------------------------------

GOLDEN_DOC = """# Build workflow cadence

## Table of contents

- [Why the premise gate exists](#why-the-premise-gate-exists)
- [Running the probe](#running-the-probe)
- [Stage flow](#stage-flow)

## Why the premise gate exists

The premise gate is mandatory and blocking for any phase whose deliverable is model-generated.

- Added: 2026-07-31
- Harness: `harness/harness.py`
- Report target: `tracker/phase_N.M.md`

## Running the probe

```bash
python3 tracker/preflight.py --check
```

## Stage flow

The probe runs first. The gate runs second. The dispatch step runs last.

```mermaid
flowchart TD
  probe[Run probe] --> gate[Premise gate]
  gate --> dispatch[Dispatch builders]
```
"""


def _mutations() -> list[tuple]:
    """(name, mutated_text, expected_kind_prefix). Every mutation must be
    CAUGHT: unlike the sibling check_preservation.py, this script has no
    deliberate known-miss category, because every arm here is a direct
    structural check with no legitimate restructure to protect against.
    """
    g = GOLDEN_DOC
    long_line = (
        "The stages run through the probe and then continue onward "
        "through several review gates before the dispatch step finally "
        "begins its work in earnest, which takes a while to describe "
        "in full and keeps going for quite a while longer still. "
    ) * 3
    return [
        ("wall by length",
         g.replace(
             "The probe runs first. The gate runs second. The dispatch step runs last.",
             long_line.strip(),
         ), "wall"),
        ("wall by comma chain",
         g.replace(
             "The probe runs first. The gate runs second. The dispatch step runs last.",
             "The probe runs first, the gate runs second, and the dispatch "
             "step runs last, closing out the stage flow for this phase.",
         ), "wall"),
        ("toc heading removed",
         g.replace(
             "## Table of contents\n\n"
             "- [Why the premise gate exists](#why-the-premise-gate-exists)\n"
             "- [Running the probe](#running-the-probe)\n"
             "- [Stage flow](#stage-flow)\n\n",
             "",
         ), "toc-missing"),
        ("toc link corrupted",
         g.replace("(#running-the-probe)", "(#wrong-anchor)"), "toc-mismatch"),
        ("bold inserted",
         g.replace(
             "- Added: 2026-07-31",
             "- Added: 2026-07-31, and this is **bold** text",
         ), "bold"),
        ("em dash inserted",
         g.replace(
             "- Added: 2026-07-31",
             "- Added: 2026-07-31 — a note",
         ), "dash"),
        ("heading case violated",
         g.replace("## Running the probe", "## Running The Probe"), "heading-case"),
        ("mermaid label too long",
         g.replace(
             "probe[Run probe]",
             "probe[This label is definitely much longer than thirty characters for sure]",
         ), "mermaid-label"),
        ("mermaid fence removed",
         g.replace(
             "\n```mermaid\nflowchart TD\n"
             "  probe[Run probe] --> gate[Premise gate]\n"
             "  gate --> dispatch[Dispatch builders]\n```\n",
             "\n",
         ), "mermaid-missing"),
    ]


def run_mutation_test() -> int:
    failures = 0

    base = run_all_checks("golden", GOLDEN_DOC, DEFAULT_WALL_LENGTH)
    if base:
        print("FAIL  golden document, a fully compliant document must pass with zero findings")
        for f in base[:10]:
            print(f"        {f.format()}")
        failures += 1
    else:
        print("PASS  golden document passes clean (0 findings)")
    print()

    for name, mutated, expected_prefix in _mutations():
        findings = run_all_checks("mutant", mutated, DEFAULT_WALL_LENGTH)
        caught = any(f.kind.startswith(expected_prefix) for f in findings)
        print(f"{'PASS' if caught else 'FAIL'}  {name} "
              f"(expected kind prefix {expected_prefix!r}, "
              f"{'caught' if caught else 'NOT caught'})")
        if not caught:
            failures += 1
            for f in findings[:3]:
                print(f"        {f.format()}")

    print()
    total = len(_mutations()) + 1
    print(f"{'ok' if failures == 0 else 'error'}: {total} mutation cases, "
          f"{failures} failed")
    return failures


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

FLAGS_WITH_VALUE = {"--wall-length", "--dir"}
FLAG_ONLY = {"--check", "--verbose", "--advisory", "--self-test", "--mutation-test"}


def _flag_value(argv: list[str], name: str) -> str | None:
    if name in argv:
        idx = argv.index(name)
        if idx + 1 < len(argv):
            return argv[idx + 1]
    for arg in argv:
        if arg.startswith(name + "="):
            return arg.split("=", 1)[1]
    return None


def _positional_path(argv: list[str]) -> str | None:
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in FLAGS_WITH_VALUE:
            i += 2
            continue
        if any(arg.startswith(name + "=") for name in FLAGS_WITH_VALUE):
            i += 1
            continue
        if arg in FLAG_ONLY:
            i += 1
            continue
        if arg.startswith("--"):
            i += 1
            continue
        return arg
    return None


def _rel(path: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return path


def _read(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return None


def _resolve_wall_length(argv: list[str]) -> int | None:
    raw = _flag_value(argv, "--wall-length")
    if raw is None:
        return DEFAULT_WALL_LENGTH
    try:
        value = int(raw)
    except ValueError:
        print(f"error: --wall-length expects an integer, got {raw!r}", file=sys.stderr)
        return None
    if value <= 0:
        print(f"error: --wall-length must be positive, got {value}", file=sys.stderr)
        return None
    if value > DEFAULT_WALL_LENGTH:
        # A wall-length threshold may only be TIGHTENED, and tightening
        # means a SMALLER number here, the inverse of the sibling
        # check_preservation.py's ratio thresholds where tightening means
        # larger. Loosening the check so the check passes is a failed run,
        # per .claude/rules/goal-contracts.md, so the loosened value is
        # unreachable through the CLI rather than merely forbidden in prose.
        print(
            f"error: --wall-length may only be tightened (a smaller number "
            f"catches more). Default is {DEFAULT_WALL_LENGTH}, got {value}. "
            f"See .claude/rules/goal-contracts.md: changing the check so "
            f"the check passes is a failed run.",
            file=sys.stderr,
        )
        return None
    return value


def _iter_markdown_files(directory: str) -> list[Path] | None:
    base = Path(directory)
    if not base.is_dir():
        return None
    out = []
    for p in sorted(base.rglob("*.md")):
        if any(part in EXCLUDED_DIR_PARTS for part in p.parts):
            continue
        out.append(p)
    return out


def run_dir_sweep(directory: str, wall_length: int) -> int:
    files = _iter_markdown_files(directory)
    if files is None:
        print(f"error: {directory} is not a directory", file=sys.stderr)
        return 2

    scored: list[tuple[str, int, int]] = []
    skipped: list[tuple[str, str]] = []
    for p in files:
        rel = _rel(str(p))
        if rel in LOCKED_DOCS:
            skipped.append((rel, "locked, skipped"))
            continue
        text = _read(str(p))
        if text is None:
            skipped.append((rel, "unreadable, skipped"))
            continue
        findings = run_all_checks(rel, text, wall_length)
        hard = sum(1 for f in findings if f.severity == HARD)
        advisory = sum(1 for f in findings if f.severity == ADVISORY)
        scored.append((rel, hard, advisory))

    scored.sort(key=lambda r: (-r[1], -r[2], r[0]))

    print(f"{len(files)} markdown files under {directory}, "
          f"{len(skipped)} skipped, wall-length={wall_length}")
    print("| File | Hard | Advisory |")
    print("|---|---|---|")
    for rel, hard, advisory in scored:
        print(f"| {rel} | {hard} | {advisory} |")
    for rel, note in skipped:
        print(f"| {rel} | - | - ({note}) |")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return 1 if run_self_test() else 0
    if "--mutation-test" in argv:
        return 1 if run_mutation_test() else 0

    wall_length = _resolve_wall_length(argv)
    if wall_length is None:
        return 2

    if "--dir" in argv:
        directory = _flag_value(argv, "--dir")
        if not directory:
            print("error: --dir requires a directory argument", file=sys.stderr)
            return 2
        return run_dir_sweep(directory, wall_length)

    path = _positional_path(argv)
    if not path:
        print(__doc__.split("USAGE")[-1].strip(), file=sys.stderr)
        return 2

    rel = _rel(path)
    if rel in LOCKED_DOCS:
        print(
            f"error: {rel} is locked until the Step 6.2 reconciliation; "
            f"this gate does not check it",
            file=sys.stderr,
        )
        return 3

    text = _read(path)
    if text is None:
        return 2

    findings = run_all_checks(rel, text, wall_length)
    hard = [f for f in findings if f.severity == HARD]
    advisory = [f for f in findings if f.severity == ADVISORY]
    advisory_blocks = "--advisory" in argv

    if "--verbose" in argv:
        lines = text.splitlines()
        print(f"{rel}: {len(lines)} lines, wall-length={wall_length}")
        print(f"  hard findings: {len(hard)}")
        print(f"  advisory findings: {len(advisory)}")
        print()

    if "--check" not in argv:
        for f in findings:
            print(f.format())

    blocking = findings if advisory_blocks else hard
    status = "ok" if not blocking else "error"
    mode = "advisory promoted to blocking" if advisory_blocks else "advisory informational only"
    print(f"{status}: {len(hard)} hard | {len(advisory)} advisory | "
          f"wall-length {wall_length} ({mode})")
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
