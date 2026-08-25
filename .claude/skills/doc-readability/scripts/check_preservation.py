#!/usr/bin/env python3
"""Prove that restructuring a markdown document lost none of its facts.

The `doc-readability` skill breaks prose walls into bullets and tables,
adds a table of contents, adds Mermaid diagrams, and adds first-principles
explanation. Every one of those edits moves text around, and a model that
moves text around drops a clause. This script is the mechanism that makes
losing a fact a build failure rather than a review finding.

THE ASYMMETRY, WHICH IS THE WHOLE DESIGN

Findings are only ever computed in one direction: BEFORE minus AFTER. Every
arm is a containment or coverage test of the old document inside the new
one. Content that appears in the after version and not the before version
is computed too, but it is never a finding: it is the additions manifest,
and it cannot change the exit code. That is what lets the skill ADD an
explanation without weakening the no-loss guarantee, and it is why the
comparison is not a diff. A diff is symmetric; this is not.

WHY A NAIVE DIFF WOULD BE USELESS HERE

A legitimate restructure destroys word order, deletes connectives, and
collapses repetition. "The judge round runs first, and then, additionally,
the adversary round runs" becomes two bullets and loses "and then,
additionally". A sentence-level or line-level diff fires on every one of
those, so it would be turned off within a day. Three properties keep the
false-positive rate near zero:

  1. Word order is never compared. Every arm is set or multiset based.
  2. CONNECTIVES and STOPWORDS are removed before counting, so the words a
     wall-to-bullet conversion actually loses are words the gate ignores.
  3. Repetition is invisible to the soft arm, which compares distinct
     types rather than tokens, because a restructure freely collapses
     three mentions of a term into one bullet.

THE THREE ARMS

  Arm 1, hard containment. Every number, date, path, URL, identifier, code
  line, and carrier word in the before version must appear in the after
  version, at least as many times. Implemented as Counter subtraction,
  which keeps only positive residues and is therefore inherently
  one-directional. Zero tolerance.

  Arm 2, soft type retention. The fraction of distinct ordinary content
  words retained must meet --lex-threshold (default 0.97). Every missing
  type is printed, so a reviewer sees dropped words rather than a ratio.

  Arm 3, claim anchoring. This is the arm that catches "the sentence
  vanished" when the sentence carried no number. Both versions segment
  into claim units (a sentence, a list item, a table row, a heading, a
  whole fence). Each before-unit must find an after-unit holding all of
  its hard atoms and at least --claim-coverage of its ordinary types; if
  no single unit clears it, the union of the three best-overlapping
  after-units is tried, which is what lets one sentence legitimately
  become three bullets. An unanchored before-unit is an orphan claim, and
  a before-unit carrying a negation whose anchor carries none is a
  negation drop, which is the cheapest way to invert a claim while keeping
  every word.

ONE DELIBERATE FALSE POSITIVE, DOCUMENTED SO IT IS NOT REMOVED

"Five failing query shapes" restructured into five bullets that never
state the count will fire on NUM "5". This is correct behaviour, not a
bug. The remedy is a five-word lead-in ("Five failing query shapes:"), and
the gate prefers that cost over a missed fact. If this arm is ever removed
because it fired, the gate stops catching a deleted count, which is the
single most common thing a restructure loses.

WHAT THIS SCRIPT DOES NOT CHECK

Stated here because `.claude/rules/goal-contracts.md` requires a verify
surface to declare its own coverage, so that a gap is arguable from the
gate itself rather than re-derived by the next reader.

  - Truth. It checks that a fact SURVIVED a rewrite, never that the fact
    was correct. A wrong number preserved perfectly passes every arm.
    Staleness is `tracker/check_doc_drift.py`'s job.
  - Scope inversion and attribution swap. "A depends on B" rewritten as
    "B depends on A" keeps every atom and passes. Asserted as a known miss
    in --mutation-test.
  - A value swap, whether within one claim unit or across two. "3 of 9"
    rewritten as "9 of 3" leaves the multiset identical, and so does
    exchanging two numbers between neighbouring sentences.

    This entry was CORRECTED after being measured, and the correction is
    left visible rather than tidied away, because the reasoning matters
    more than the conclusion. An earlier version of Arm 3 unioned only the
    three highest-overlap after-units, and under that rule the cross-unit
    swap WAS caught, so this block claimed it as covered. Running the gate
    against a real document (docs/build/Build_workflow_cadence.md) showed
    that same narrowness reporting three legitimate sentence-to-bullets
    splits as orphan claims. Widening the union to greedy set cover fixed
    the false positives and gave up the cross-unit swap with it.

    The two are not separable at the atom level. "One sentence carrying
    two numbers becomes two bullets, one number each" and "two numbers
    swapped between two sentences" present the identical evidence to any
    set-based arm. A union wide enough to permit the first cannot reject
    the second. The false positives were the more expensive failure, since
    a gate that fires on correct work gets switched off, so the trade was
    made deliberately in that direction. Both swaps are asserted as known
    misses in --mutation-test.
  - Ordering semantics. An ordered list reordered keeps every atom.
  - Whether added prose is accurate. Additions are reported, never graded.
    That is the `doc-auditor` agent's job and the owner's review of the
    additions manifest.
  - Style. Owned entirely by check_style.py in this same directory.
  - Whether a Mermaid block actually parses. No renderer is bundled.
  - Any document not named on the command line. There is no sweep mode,
    by design: the skill runs on one document per invocation.

USAGE

  check_preservation.py --before <path> --after <path> [--check|--verbose|--additions]
  check_preservation.py --git <path>        # working tree against git HEAD
  check_preservation.py --self-test
  check_preservation.py --mutation-test

  --lex-threshold F     tighten only, default 0.97
  --claim-coverage F    tighten only, default 0.70

  Exit 0  nothing lost
       1  findings, at least one atom or claim did not survive
       2  bad invocation, or a threshold was loosened
       3  locked document refused
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

# Locked documents, frozen until the Step 6.2 reconciliation. Enforced here
# as well as in the skill's prose, because `system-design-patterns.md`
# pattern 8 says the strongest constraint is removing the ability, not
# asking the model not to use it. Mirrors SKIP_FILES in
# tracker/check_doc_drift.py.
LOCKED_DOCS = {
    "requirements/PRD.md",
    "requirements/Technical_specification.md",
}

DEFAULT_LEX_THRESHOLD = 0.97
DEFAULT_CLAIM_COVERAGE = 0.70

# The maximum number of missing ordinary-word types printed in a report.
# The count is always reported in full; only the enumeration is capped.
MAX_LISTED_TYPES = 40

# A claim unit is exempt from Arm 3 when it carries no hard atom and fewer
# than this many ordinary types. "That is the bar." is not a claim worth
# anchoring, and forcing it to anchor produces noise that trains a reader
# to ignore the arm. Every exempted unit is counted and reported as
# `claims skipped`, so the exemption is visible rather than silent.
MIN_CLAIM_TYPES = 5

# How many after-units may be unioned to anchor one before-unit. A prose
# wall legitimately becomes a lead-in plus several bullets, so the union
# has to be wider than a pair, but an unbounded union would let a
# before-unit be "covered" by scavenging words from all over the document,
# which is the same as not checking at all.
#
# Raised from 4 to 6 against a measured case rather than a guess: one
# sentence in docs/build/Build_workflow_cadence.md restructured into a
# lead-in, three bullets, and a trailing sentence, which is five units and
# an entirely ordinary shape. The mutation harness was re-run after the
# change to confirm no arm went blind at the wider setting.
MAX_UNION_UNITS = 6

# How many candidate after-units the greedy cover considers. Bounded so a
# pathological document cannot turn one claim check into a full scan.
CANDIDATE_POOL = 24

# How much of an after-unit's own wording must come from a before-unit for
# it to count as a fragment of that sentence. Used only by the negation
# check, to find where the other half of a split sentence went.
FRAGMENT_COVERAGE = 0.75

# Words a restructure legitimately deletes when a sentence becomes a
# bullet or a table cell. Excluded from the ordinary-word arm before
# counting. This single list is what keeps Arm 2 from firing on every
# legitimate wall-to-bullet conversion.
CONNECTIVES = {
    "additionally", "also", "although", "because", "besides", "consequently",
    "conversely", "furthermore", "hence", "however", "indeed", "instead",
    "likewise", "meanwhile", "moreover", "nevertheless", "nonetheless",
    "notably", "now", "particularly", "rather", "regardless", "since",
    "specifically", "still", "then", "therefore", "though", "thus",
    "whereas", "while", "yet",
}

# The verb a colon replaces, plus the adverbs that order discourse rather
# than state a fact. This list is deliberately SHORT and locative: these
# are the words a "Label: detail" conversion deletes by construction, so
# "The harness lives in X" becoming "Harness: X" loses the word "lives"
# and no fact at all. Every entry must pass that test, which is why
# reporting verbs such as "returns", "produces", and "states" are NOT here:
# each of those carries a claim about what something does, and a gate that
# ignored them would stop catching a real deletion.
LIGHT_VERBS = {
    "lives", "live", "sits", "sit", "resides", "reside", "lies", "lie",
    "stands", "stand", "belongs", "belong", "goes", "go", "comes", "come",
    "first", "second", "third", "fourth", "fifth", "next", "finally",
    "lastly", "above", "below",
}

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on", "at",
    "by", "for", "with", "from", "into", "onto", "over", "under", "about",
    "as", "is", "are", "was", "were", "be", "been", "being", "am", "do",
    "does", "did", "have", "has", "had", "having", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "it", "its", "this",
    "that", "these", "those", "there", "here", "he", "she", "they", "them",
    "their", "his", "her", "our", "ours", "we", "us", "you", "your", "yours",
    "i", "me", "my", "mine", "who", "whom", "whose", "which", "what", "when",
    "where", "how", "why", "than", "so", "too", "very", "just", "only",
    "own", "same", "each", "any", "all", "both", "few", "more", "most",
    "other", "some", "such", "up", "out", "off", "down", "again", "once",
    "s", "t", "d", "ll", "re", "ve", "m",
}

# Negation carriers, checked per anchored claim pair rather than
# document-wide. A document-wide count would pass while one claim silently
# flipped, since another claim elsewhere would supply the missing "not".
NEGATIONS = {
    "not", "never", "no", "none", "nor", "neither", "cannot", "without",
    "nothing", "nobody", "n't", "unable",
}

MONTHS = (
    "January|February|March|April|May|June|July|August|September|October"
    "|November|December"
)

MONTH_NUM = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

WORD_NUMBERS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19", "twenty": "20",
}

CODE_EXTENSIONS = (
    "py|md|ts|tsx|js|jsx|json|ya?ml|sh|sql|html|css|txt|toml|cfg|ini|tsv|csv"
)

# Tokens that end in a period without ending a sentence.
ABBREVIATIONS = {
    "e.g", "i.e", "vs", "etc", "cf", "fig", "no", "mr", "mrs", "ms", "dr",
    "prof", "st", "approx", "al",
}

# Fences whose content is prose rather than code. A fact that moves from a
# paragraph into a Mermaid node label has not been lost, so a mermaid
# fence must be tokenized as prose or the gate would report a false
# positive on exactly the edit the skill is designed to make.
PROSE_FENCE_LANGS = {"", "mermaid", "text", "markdown", "md", "plain"}

# --------------------------------------------------------------------------
# Atom categories
# --------------------------------------------------------------------------

CAT_CODELINE = "CODELINE"
CAT_URL = "URL"
CAT_PATH = "PATH"
CAT_DATE = "DATE"
CAT_IDENT = "IDENT"
CAT_NUM = "NUM"
CAT_LEXC = "LEX-CARRIER"
CAT_LEXO = "LEX-ORDINARY"

# Categories compared as an exact multiset: a single missing occurrence is
# a finding, with no budget, no threshold, and no variant matching. These
# are the categories where a one-character difference is a different fact,
# so "84.3" and "84.5" must never match and neither must two file paths
# differing in case.
COUNTED_CATEGORIES = (
    CAT_CODELINE, CAT_URL, CAT_PATH, CAT_DATE, CAT_IDENT, CAT_NUM,
)

# Carrier words are held to zero tolerance like the counted categories,
# but matched through variants rather than exactly, because a carrier can
# legitimately inflect across a restructure. "restructuring" is 13
# characters and therefore a carrier, while "restructure" is 11 and
# therefore ordinary, so an exact-match arm would report a lost word every
# time a heading changed tense. Zero tolerance on WHETHER the word
# survived, tolerance on WHICH form it survived in.
HARD_CATEGORIES = COUNTED_CATEGORIES + (CAT_LEXC,)

# One master alternation, ordered by precedence, so a single left-to-right
# pass assigns every character to at most one atom. Order matters: URL
# before PATH (a URL contains slashes), DATE before NUM (2026-08-25 is one
# date, not three numbers), PATH before IDENT (graph_connection.py is a
# path, not an identifier), IDENT before NUM (F-2.1-A5-03 is one ticket).
TOKEN_RE = re.compile(
    r"(?P<url>[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s<>()\[\]\"'`]+)"
    r"|`(?P<btick>[^`\n]+)`"
    r"|(?P<ticket>\b[A-Z]{1,4}-\d+(?:\.\d+)*(?:-[A-Za-z0-9]+)*\b)"
    r"|(?P<date_iso>\b\d{4}-\d{2}-\d{2}\b)"
    rf"|(?P<date_mdy>\b(?:{MONTHS})\s+\d{{1,2}}(?:,?\s+\d{{4}})?\b)"
    rf"|(?P<date_dmy>\b\d{{1,2}}\s+(?:{MONTHS})(?:,?\s+\d{{4}})?\b)"
    r"|(?P<path>(?:[A-Za-z0-9_.\-]+/)+[A-Za-z0-9_.\-*]+"
    rf"|\b[A-Za-z0-9_\-]+\.(?:{CODE_EXTENSIONS})\b)"
    r"|(?P<ident>\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b"
    r"|\b[A-Z]{2,}(?:[0-9]+)?\b"
    r"|\b[a-z]+[A-Z][A-Za-z0-9]*\b"
    r"|\b[A-Za-z]+(?:-[A-Za-z]+)*-\d+[A-Za-z0-9.\-]*\b)"
    r"|(?P<num>\b\d+(?:,\d{3})*(?:\.\d+)?\s?(?:percent|%)?x?\b)"
    r"|(?P<word>[A-Za-z][A-Za-z'’\-]*)"
)

FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})\s*([A-Za-z0-9_+\-]*)")


@dataclass(frozen=True)
class Atom:
    category: str
    value: str


@dataclass
class Unit:
    """One claim unit: a sentence, list item, table row, heading, or fence."""

    kind: str          # heading | bullet | table | fence | prose
    line: int          # 1-indexed line in its own document
    text: str
    atoms: list[Atom] = field(default_factory=list)

    def counted(self) -> Counter:
        """The exact-match multiset: numbers, dates, paths, URLs,
        identifiers, code lines."""
        return Counter(a for a in self.atoms if a.category in COUNTED_CATEGORIES)

    def carrier_types(self) -> set:
        return {a.value for a in self.atoms if a.category == CAT_LEXC}

    def lexo_types(self) -> set:
        return {a.value for a in self.atoms if a.category == CAT_LEXO}

    def word_types(self) -> set:
        """Carrier and ordinary words together, which is the pool Arm 3
        measures coverage against. A carrier word moving into a table cell
        still counts as covering the claim it came from."""
        return {a.value for a in self.atoms
                if a.category in (CAT_LEXC, CAT_LEXO)}

    def all_keys(self) -> set:
        return {(a.category, a.value) for a in self.atoms}

    def negations(self) -> int:
        return sum(1 for a in self.atoms
                   if a.category in (CAT_LEXC, CAT_LEXO)
                   and a.value in NEGATIONS)


@dataclass
class Finding:
    kind: str          # atom | claim | negation | retention
    path: str
    line: int
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: [{self.kind}] {self.message}"


# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------


def _norm_num(raw: str) -> str:
    """Strip thousands separators and trailing noise, keep decimals exact.

    "1,742" and "1742" are the same number. "27x" keeps its multiplier
    because "27x faster" and "27 faster" are different claims. "76 percent"
    and "76%" normalize together so a restructure may switch between them.
    """
    v = raw.strip().lower().replace(",", "")
    v = re.sub(r"\s*percent$", "%", v)
    return v


def _norm_date(raw: str, group: str) -> str:
    """To ISO where a year is present, else MM-DD, so "August 25, 2026" and
    "2026-08-25" compare equal."""
    v = raw.strip()
    if group == "date_iso":
        return v
    m = re.search(r"([A-Za-z]+)", v)
    d = re.search(r"\b(\d{1,2})\b", v)
    y = re.search(r"\b(\d{4})\b", v)
    if not m or not d:
        return v.lower()
    mm = MONTH_NUM.get(m.group(1).lower(), "00")
    dd = d.group(1).zfill(2)
    return f"{y.group(1)}-{mm}-{dd}" if y else f"{mm}-{dd}"


def _norm_path(raw: str) -> str:
    """Strip a leading ./ and trailing punctuation or possessive. Case is
    preserved: file paths are case-sensitive and a case change is a real
    defect, not a formatting choice."""
    v = raw.strip().strip("`")
    v = re.sub(r"^\./", "", v)
    v = re.sub(r"(?:'s|’s)$", "", v)
    return v.rstrip(".,;:!?)’'\"")


def _norm_url(raw: str) -> str:
    return raw.strip().rstrip(".,;:!?)’'\"").rstrip("/")


def _norm_ident(raw: str) -> str:
    """Case preserved, for the same reason paths are."""
    return raw.strip().strip("`").rstrip(".,;:!?)")


def _norm_word(raw: str) -> str:
    v = raw.lower().strip("'’-")
    v = re.sub(r"(?:'s|’s)$", "", v)
    return v


def _variants(word: str) -> set:
    """Every surface form this word could legitimately take across a
    restructure, as a SET rather than a single canonical stem.

    Canonical stemming is the wrong tool here, and it fails in a way that
    produces false positives rather than false negatives, which is the
    expensive direction for a gate someone has to trust. A stemmer that
    strips "es" maps "closes" to "clos" while leaving "close" as "close",
    so the two never match and the gate reports a word as lost that is
    sitting in the after text. "restructuring" against "restructure"
    breaks the same way.

    Matching on a set of variants sidesteps the problem entirely: two
    words match when their variant sets intersect, so "closes" and "close"
    match through the shared "close", with no need to agree on which form
    is canonical. Residues shorter than four characters are dropped,
    because a three-letter residue starts colliding with unrelated words,
    and a false MERGE hides a genuinely lost word, which is the one
    direction this script must never fail in.
    """
    out = {word}
    if len(word) < 5:
        return out
    for suffix in ("s", "es", "ed", "ing", "ly"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            out.add(word[: -len(suffix)])
    # Restore the silent "e" an inflection drops: "using" to "use",
    # "restructuring" to "restructure", "cited" to "cite".
    for suffix in ("ed", "ing"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            out.add(word[: -len(suffix)] + "e")
    return out


def _variant_pool(words) -> set:
    pool: set = set()
    for w in words:
        pool |= _variants(w)
    return pool


def _retained(word: str, pool: set) -> bool:
    return bool(_variants(word) & pool)


def _is_carrier(raw: str, normalized: str, first_in_unit: bool) -> bool:
    """A carrier word must survive exactly; an ordinary word is budgeted.

    Carrier when any of: it is long (12+ characters, so a domain term
    rather than a connective), it contains a digit, it is a hyphenated
    compound, or it is capitalized somewhere other than the start of its
    unit, which in running prose means a proper noun.
    """
    if len(normalized) >= 12:
        return True
    if any(ch.isdigit() for ch in normalized):
        return True
    if "-" in raw.strip("-"):
        return True
    if raw[:1].isupper() and not first_in_unit:
        return True
    return False


# --------------------------------------------------------------------------
# Tokenization
# --------------------------------------------------------------------------


def tokenize(text: str) -> list[Atom]:
    """One left-to-right pass. Every character is claimed by at most one
    atom, with precedence fixed by the order of alternatives in TOKEN_RE.
    """
    atoms: list[Atom] = []
    seen_word = False
    for m in TOKEN_RE.finditer(text):
        group = m.lastgroup
        raw = m.group(group)
        if group == "url":
            atoms.append(Atom(CAT_URL, _norm_url(raw)))
        elif group == "btick":
            # Anything the author chose to mark as code is an identifier,
            # preserved exactly. This is where flags, env vars, function
            # names, and `key: value` pairs land.
            atoms.append(Atom(CAT_IDENT, raw.strip()))
        elif group == "ticket":
            atoms.append(Atom(CAT_IDENT, _norm_ident(raw)))
        elif group in ("date_iso", "date_mdy", "date_dmy"):
            atoms.append(Atom(CAT_DATE, _norm_date(raw, group)))
        elif group == "path":
            atoms.append(Atom(CAT_PATH, _norm_path(raw)))
        elif group == "ident":
            atoms.append(Atom(CAT_IDENT, _norm_ident(raw)))
        elif group == "num":
            atoms.append(Atom(CAT_NUM, _norm_num(raw)))
        elif group == "word":
            normalized = _norm_word(raw)
            if not normalized:
                continue
            if normalized in WORD_NUMBERS:
                atoms.append(Atom(CAT_NUM, WORD_NUMBERS[normalized]))
                seen_word = True
                continue
            # Negations are checked before the stopword filter, because
            # "no" and "not" are stopword-shaped and dropping them would
            # make a flipped claim invisible.
            if normalized in NEGATIONS:
                atoms.append(Atom(CAT_LEXO, normalized))
                seen_word = True
                continue
            if (normalized in STOPWORDS or normalized in CONNECTIVES
                    or normalized in LIGHT_VERBS):
                seen_word = True
                continue
            if _is_carrier(raw, normalized, not seen_word):
                atoms.append(Atom(CAT_LEXC, normalized))
            else:
                atoms.append(Atom(CAT_LEXO, normalized))
            seen_word = True
    return atoms


# --------------------------------------------------------------------------
# Segmentation into claim units
# --------------------------------------------------------------------------


def _fence_spans(lines: list[str]) -> list[tuple[int, int, str]]:
    """(start, end, lang) for every fenced block, end exclusive. An unclosed
    fence runs to end of file, per CommonMark."""
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


def _mask_protected(text: str) -> str:
    """Replace inline code, URLs, and decimal numbers with same-length
    filler so sentence splitting cannot break inside them."""
    out = list(text)
    for m in re.finditer(r"`[^`\n]*`|[a-zA-Z][a-zA-Z0-9+.\-]*://\S+|\d+\.\d+", text):
        for k in range(m.start(), m.end()):
            out[k] = " "
    return "".join(out)


def split_sentences(text: str) -> list[tuple[int, str]]:
    """(offset, sentence) pairs. Splits on terminal punctuation followed by
    whitespace and an opening character, never inside inline code, a URL,
    a decimal, or after a known abbreviation."""
    masked = _mask_protected(text)
    cuts = [0]
    for m in re.finditer(r"[.!?]+[\"')\]]?\s+", masked):
        head = masked[: m.start()]
        last = re.search(r"([A-Za-z.]+)$", head)
        if last:
            token = last.group(1).rstrip(".").lower()
            if token in ABBREVIATIONS or len(token) == 1:
                continue
        nxt = masked[m.end(): m.end() + 1]
        if nxt and not (nxt.isupper() or nxt in "\"'(`[ " or nxt.isdigit()):
            continue
        cuts.append(m.end())
    cuts.append(len(text))
    out: list[tuple[int, str]] = []
    for a, b in zip(cuts, cuts[1:]):
        chunk = text[a:b].strip()
        if chunk:
            out.append((a, chunk))
    return out


def segment(text: str) -> list[Unit]:
    """Split a markdown document into claim units and tokenize each."""
    lines = text.splitlines()
    spans = _fence_spans(lines)
    in_fence = {}
    for start, end, lang in spans:
        for k in range(start, end):
            in_fence[k] = (start, lang)

    units: list[Unit] = []
    i = 0
    while i < len(lines):
        if i in in_fence:
            start, lang = in_fence[i]
            end = next((e for s, e, _ in spans if s == start), i + 1)
            body = lines[start + 1: end - 1] if end - 1 > start else []
            if lang in PROSE_FENCE_LANGS:
                # Prose inside a fence: a Mermaid label carrying a fact is
                # a legitimate home for that fact.
                joined = " ".join(ln.strip() for ln in body if ln.strip())
                if joined:
                    u = Unit("fence", start + 1, joined)
                    u.atoms = tokenize(joined)
                    units.append(u)
            else:
                # Real code. Every non-blank line is one CODELINE atom,
                # whitespace-collapsed. Code is never legitimately
                # restructured, so exact-line containment is correct and
                # cheap here.
                for off, ln in enumerate(body):
                    collapsed = " ".join(ln.split())
                    if not collapsed:
                        continue
                    u = Unit("fence", start + 2 + off, collapsed)
                    u.atoms = [Atom(CAT_CODELINE, collapsed)]
                    units.append(u)
            i = end
            continue

        raw = lines[i]
        stripped = raw.strip()
        if not stripped:
            i += 1
            continue

        if stripped.startswith("#"):
            u = Unit("heading", i + 1, stripped.lstrip("#").strip())
            u.atoms = tokenize(u.text)
            units.append(u)
            i += 1
            continue

        if stripped.startswith("|"):
            # One unit per cell, not per row. A restructure legitimately
            # moves a cell into another row or reorders columns, and
            # per-cell units let that pass while still requiring every
            # cell's content to survive somewhere.
            if set(stripped) <= set("|-: "):
                i += 1
                continue
            for cell in stripped.strip("|").split("|"):
                cell = cell.strip()
                if not cell:
                    continue
                u = Unit("table", i + 1, cell)
                u.atoms = tokenize(cell)
                units.append(u)
            i += 1
            continue

        bullet = re.match(r"^(\s*)(?:[-*+]|\d+\.)\s+(.*)$", raw)
        if bullet:
            body = [bullet.group(2)]
            indent = len(bullet.group(1))
            j = i + 1
            while j < len(lines) and j not in in_fence:
                nxt = lines[j]
                if not nxt.strip():
                    break
                if re.match(r"^\s*(?:[-*+]|\d+\.)\s+", nxt):
                    break
                if nxt.startswith("#") or nxt.strip().startswith("|"):
                    break
                if len(nxt) - len(nxt.lstrip()) <= indent:
                    break
                body.append(nxt.strip())
                j += 1
            joined = " ".join(body).strip()
            for _, sentence in split_sentences(joined) or [(0, joined)]:
                u = Unit("bullet", i + 1, sentence)
                u.atoms = tokenize(sentence)
                units.append(u)
            i = j
            continue

        para = [stripped]
        j = i + 1
        while j < len(lines) and j not in in_fence:
            nxt = lines[j]
            if not nxt.strip() or nxt.startswith("#") or nxt.strip().startswith("|"):
                break
            if re.match(r"^\s*(?:[-*+]|\d+\.)\s+", nxt):
                break
            para.append(nxt.strip())
            j += 1
        joined = " ".join(para)
        for _, sentence in split_sentences(joined):
            u = Unit("prose", i + 1, sentence)
            u.atoms = tokenize(sentence)
            units.append(u)
        i = j

    return units


# --------------------------------------------------------------------------
# The three arms
# --------------------------------------------------------------------------


def _atom_line_index(units: list[Unit]) -> dict:
    """First line where each atom appears, so a finding can point at the
    before-line where the lost fact actually lived."""
    index: dict = {}
    for u in units:
        for a in u.atoms:
            index.setdefault((a.category, a.value), u.line)
    return index


def arm_hard_containment(before: list[Unit], after: list[Unit],
                         path: str) -> list[Finding]:
    """Arm 1, in two halves that differ in HOW they match, not in how much
    they tolerate. Both are zero tolerance.

    Half one, the counted categories, is exact multiset containment.
    Counter subtraction keeps only positive residues, so it is
    one-directional by construction: an atom appearing more often after
    than before produces nothing.

    Half two, carrier words, matches through variants. A carrier can
    legitimately inflect when a sentence becomes a heading or a table
    cell, and an exact-match arm would report a loss every time it did.
    """
    findings = []
    lines = _atom_line_index(before)

    b_counted = Counter()
    for u in before:
        b_counted.update(a for a in u.atoms if a.category in COUNTED_CATEGORIES)
    a_counted = Counter()
    for u in after:
        a_counted.update(x for x in u.atoms if x.category in COUNTED_CATEGORIES)
    missing = b_counted - a_counted
    for atom, count in sorted(missing.items(),
                              key=lambda kv: (kv[0].category, kv[0].value)):
        line = lines.get((atom.category, atom.value), 1)
        times = "" if count == 1 else f" ({count} occurrences)"
        findings.append(Finding(
            "atom", path, line,
            f'{atom.category} "{atom.value}" present in before, '
            f'absent in after{times}',
        ))

    b_carriers: set = set()
    for u in before:
        b_carriers |= u.carrier_types()
    after_pool = _variant_pool(w for u in after for w in u.word_types())
    for word in sorted(b_carriers):
        if not _retained(word, after_pool):
            findings.append(Finding(
                "atom", path, lines.get((CAT_LEXC, word), 1),
                f'{CAT_LEXC} "{word}" present in before, absent in after',
            ))

    return findings


def arm_soft_retention(before: list[Unit], after: list[Unit], path: str,
                       threshold: float) -> tuple[list[Finding], float, int]:
    """Arm 2. Distinct types, not tokens: a restructure freely collapses
    repetition, so a token-level count would fire on every legitimate
    edit."""
    b_types = set()
    for u in before:
        b_types |= u.lexo_types()
    if not b_types:
        return [], 1.0, 0
    # Matched against the FULL after word pool, carriers included: a word
    # that was ordinary in the before version can become a carrier in the
    # after version simply by being capitalized as a bullet label, and
    # that is a formatting change rather than a loss.
    after_pool = _variant_pool(w for u in after for w in u.word_types())
    missing = sorted(w for w in b_types if not _retained(w, after_pool))
    retention = (len(b_types) - len(missing)) / len(b_types)
    if retention >= threshold:
        return [], retention, len(missing)
    lines = _atom_line_index(before)
    shown = missing[:MAX_LISTED_TYPES]
    findings = [Finding(
        "retention", path, 1,
        f"ordinary-word retention {retention:.3f} below threshold {threshold:.3f}, "
        f"{len(missing)} distinct content words lost",
    )]
    for word in shown:
        findings.append(Finding(
            "retention", path, lines.get((CAT_LEXO, word), 1),
            f'content word "{word}" present in before, absent in after',
        ))
    if len(missing) > len(shown):
        findings.append(Finding(
            "retention", path, 1,
            f"... and {len(missing) - len(shown)} more lost content words not listed",
        ))
    return findings, retention, len(missing)


def _build_index(units: list[Unit]) -> dict:
    index: dict = {}
    for idx, u in enumerate(units):
        for key in u.all_keys():
            index.setdefault(key, set()).add(idx)
    return index


def _covers(before_unit: Unit, counted_pool: Counter, word_pool: set,
            coverage: float) -> bool:
    """An after-unit, or a union of them, covers a before-unit when it
    holds every counted atom exactly and enough of its words by variant."""
    if before_unit.counted() - counted_pool:
        return False
    b_words = before_unit.word_types()
    if not b_words:
        return True
    hit = sum(1 for w in b_words if _retained(w, word_pool))
    return hit / len(b_words) >= coverage


def _greedy_anchor(bu: Unit, after: list[Unit], pool_ids: list[int],
                   coverage: float) -> list[int]:
    """Greedy set cover over candidate after-units.

    Ranking by RAW shared-atom count does not work here, and the failure
    is worth naming because it looks correct until it is measured. A long
    after-unit wins on raw overlap simply by being long, so a Mermaid
    fence carrying fifteen stage numbers outranked the three short bullets
    a sentence had actually been split into, consumed every union slot,
    and left the sentence reported as an orphan claim. Measured on
    docs/build/Build_workflow_cadence.md: three legitimate splits failed
    that way.

    Gain is therefore counted only over what the before-unit still NEEDS,
    never over everything the candidate happens to contain.
    """
    need_words = bu.word_types()
    need_counted = bu.counted()
    chosen: list[int] = []
    pool_hard: Counter = Counter()
    pool_lexo: set = set()

    for _ in range(MAX_UNION_UNITS):
        best, best_gain = None, 0
        for idx in pool_ids:
            if idx in chosen:
                continue
            au = after[idx]
            au_words = _variant_pool(au.word_types())
            gain = sum(
                1 for w in need_words
                if not _retained(w, pool_lexo) and _retained(w, au_words)
            )
            # Intersect with what is needed. Without this, an unrelated
            # atom-dense unit outbids the unit that actually carries the
            # missing fact.
            gain += sum(((au.counted() & need_counted) - pool_hard).values())
            if gain > best_gain:
                best, best_gain = idx, gain
        if best is None:
            break
        chosen.append(best)
        pool_hard.update(after[best].counted())
        pool_lexo |= _variant_pool(after[best].word_types())
        if _covers(bu, pool_hard, pool_lexo, coverage):
            return chosen
    return chosen if _covers(bu, pool_hard, pool_lexo, coverage) else []


def arm_claim_anchoring(before: list[Unit], after: list[Unit], path: str,
                        coverage: float) -> tuple[list[Finding], int]:
    """Arm 3. Catches the sentence that vanished while carrying no number.

    An inverted index restricts scoring to after-units that share at least
    one atom, so this is near-linear rather than the naive product. When no
    single after-unit anchors a before-unit, a greedy set cover over the
    candidates is tried, which is what lets one sentence legitimately
    become three bullets.
    """
    index = _build_index(after)
    findings: list[Finding] = []
    skipped = 0

    for bu in before:
        b_hard = bu.counted()
        b_lexo = bu.word_types()
        if not b_hard and len(b_lexo) < MIN_CLAIM_TYPES:
            skipped += 1
            continue

        candidates: Counter = Counter()
        for key in bu.all_keys():
            for idx in index.get(key, ()):
                candidates[idx] += 1
        if not candidates:
            findings.append(Finding(
                "claim", path, bu.line,
                f"no after-unit anchors this before-unit: \"{_excerpt(bu.text)}\"",
            ))
            continue

        # Rank-truncating the candidate pool drops short units, and a
        # short unit is exactly where a restructure parks a bare
        # identifier: a sentence naming `Phase_6_execution_flow.html`
        # became a three-item bullet list whose third bullet is only that
        # identifier, so it shared one atom, ranked below 24 other units,
        # and was cut. The claim then failed for a fact that was sitting
        # in the document. Counted atoms are mandatory, so every unit that
        # supplies one is always considered, whatever its overlap rank.
        pool_ids = [idx for idx, _ in candidates.most_common(CANDIDATE_POOL)]
        must_have: set = set()
        for atom in b_hard:
            must_have |= index.get((atom.category, atom.value), set())
        for idx in sorted(must_have):
            if idx not in pool_ids:
                pool_ids.append(idx)

        anchor_ids: list[int] = []
        for idx in pool_ids:
            au = after[idx]
            if _covers(bu, au.counted(), _variant_pool(au.word_types()),
                       coverage):
                anchor_ids = [idx]
                break

        if not anchor_ids:
            anchor_ids = _greedy_anchor(bu, after, pool_ids, coverage)

        if not anchor_ids:
            findings.append(Finding(
                "claim", path, bu.line,
                f"no after-unit anchors this before-unit: \"{_excerpt(bu.text)}\"",
            ))
            continue

        b_neg = bu.negations()
        a_neg = sum(after[i].negations() for i in anchor_ids)
        if b_neg > a_neg:
            # A single after-unit can clear the coverage bar while holding
            # only half of a sentence that legitimately split in two, and
            # the other half is where the second negation went. Widening
            # to the greedy cover is not enough, because that also stops
            # as soon as coverage is met.
            #
            # Count instead over every FRAGMENT of the original sentence:
            # an after-unit whose own words are almost entirely contained
            # in this before-unit is a piece of it, wherever it now sits.
            # That is a deliberately narrow widening. It cannot scavenge a
            # negation from an unrelated sentence, because an unrelated
            # sentence carries words this before-unit does not have.
            before_pool = _variant_pool(bu.word_types())
            fragment_ids = set(anchor_ids)
            for idx in pool_ids:
                words = after[idx].word_types()
                if not words:
                    continue
                hit = sum(1 for w in words if _retained(w, before_pool))
                if hit / len(words) >= FRAGMENT_COVERAGE:
                    fragment_ids.add(idx)
            a_neg = max(a_neg, sum(after[i].negations() for i in fragment_ids))
        if b_neg > a_neg:
            findings.append(Finding(
                "negation", path, bu.line,
                f"negation dropped, before carries {b_neg} and the anchoring "
                f"after-text carries {a_neg}: \"{_excerpt(bu.text)}\"",
            ))

    return findings, skipped


def _excerpt(text: str, width: int = 96) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= width else flat[: width - 3] + "..."


# --------------------------------------------------------------------------
# Additions manifest, the allowed direction
# --------------------------------------------------------------------------


def compute_additions(before: list[Unit], after: list[Unit]) -> list[dict]:
    """After-units whose content is mostly absent from the before document.

    Read in the opposite direction from the findings arms, and never able
    to change the exit code. Novelty is measured against the whole before
    document rather than a matched unit, so a bullet that legitimately
    regroups existing content scores low and is not reported, while a
    genuinely new explanation scores high and is.
    """
    before_keys: set = set()
    for u in before:
        before_keys |= u.all_keys()

    rows: list[dict] = []
    for u in after:
        keys = u.all_keys()
        if not keys:
            continue
        novel = {k for k in keys if k not in before_keys}
        novelty = len(novel) / len(keys)
        if novelty < 0.5:
            continue
        if len(keys) < 3:
            continue
        rows.append({
            "line": u.line,
            "kind": u.kind,
            "novelty": novelty,
            "text": _excerpt(u.text, 120),
        })
    rows.sort(key=lambda r: r["line"])
    return rows


# --------------------------------------------------------------------------
# Comparison driver
# --------------------------------------------------------------------------


@dataclass
class Result:
    findings: list[Finding]
    additions: list[dict]
    before_atoms: int
    after_atoms: int
    retention: float
    lost_types: int
    claims_skipped: int
    claims_total: int


def compare(before_text: str, after_text: str, path: str,
            lex_threshold: float, claim_coverage: float) -> Result:
    before = segment(before_text)
    after = segment(after_text)

    findings: list[Finding] = []
    findings.extend(arm_hard_containment(before, after, path))
    soft, retention, lost_types = arm_soft_retention(
        before, after, path, lex_threshold)
    findings.extend(soft)
    claims, skipped = arm_claim_anchoring(before, after, path, claim_coverage)
    findings.extend(claims)

    return Result(
        findings=findings,
        additions=compute_additions(before, after),
        before_atoms=sum(len(u.atoms) for u in before),
        after_atoms=sum(len(u.atoms) for u in after),
        retention=retention,
        lost_types=lost_types,
        claims_skipped=skipped,
        claims_total=len(before),
    )


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------


def _self_test_cases() -> list[tuple]:
    """(name, before, after, should_fail). One true positive and one true
    negative per arm, so every arm proves it can fail as well as pass."""
    wall = (
        "The judge round runs first, and then the adversary round runs, and "
        "the phase closes on 2026-08-21 after 4107 tests pass in "
        "`harness/harness.py`.\n"
    )
    restructured = (
        "Rounds:\n\n"
        "- Judge round: runs first\n"
        "- Adversary round: runs second\n"
        "- Phase close: 2026-08-21, after 4107 tests pass in `harness/harness.py`\n"
    )
    return [
        ("arm1 true negative, wall becomes bullets", wall, restructured, False),
        ("arm1 true positive, number deleted", wall,
         restructured.replace("4107 ", ""), True),
        ("arm1 true positive, path deleted", wall,
         restructured.replace(" in `harness/harness.py`", ""), True),
        ("arm1 true positive, date changed", wall,
         restructured.replace("2026-08-21", "2026-08-22"), True),
        ("arm2 true negative, connectives dropped",
         "The gate blocks the phase, and additionally, however, it also logs.\n",
         "- Gate: blocks the phase\n- Gate: logs\n", False),
        ("arm3 true positive, qualitative sentence deleted",
         "The gate blocks the phase. A feeling that a role seems important "
         "is not the measured bar for dispatching it.\n",
         "The gate blocks the phase.\n", True),
        ("arm3 true negative, sentence becomes three bullets",
         "The harness probes the model provider, the graph, and the "
         "transport before dispatch.\n",
         "The harness probes these before dispatch:\n\n"
         "- Model provider\n- Graph\n- Transport\n",
         False),
        ("negation true positive, not removed",
         "Reasoning effort is a latency setting, not just a quality setting.\n",
         "Reasoning effort is a latency setting, just a quality setting.\n",
         True),
        ("additions never fail the gate",
         "The gate blocks the phase.\n",
         "The gate blocks the phase.\n\nWhy does the gate exist? Before it, a "
         "phase could ship code nobody had exercised against reality.\n",
         False),
        ("identical documents pass",
         wall, wall, False),
    ]


def run_self_test() -> int:
    failures = 0
    cases = _self_test_cases()
    for name, before, after, should_fail in cases:
        res = compare(before, after, "self-test",
                      DEFAULT_LEX_THRESHOLD, DEFAULT_CLAIM_COVERAGE)
        failed = bool(res.findings)
        ok = failed == should_fail
        expect = "findings" if should_fail else "clean"
        got = "findings" if failed else "clean"
        print(f"{'PASS' if ok else 'FAIL'}  {name} (expected {expect}, got {got})")
        if not ok:
            failures += 1
            for f in res.findings[:3]:
                print(f"        {f.format()}")
    print()
    print(f"{'ok' if failures == 0 else 'error'}: {len(cases)} self-test cases, "
          f"{failures} failed")
    return failures


# --------------------------------------------------------------------------
# Mutation harness
# --------------------------------------------------------------------------

GOLDEN_BEFORE = """# Build workflow cadence

The premise gate is mandatory and blocking for any phase whose deliverable
is model-generated, and it was added on 2026-07-31 after a phase shipped
with 3 of 9 arms unrun, which cost 27x the review budget it saved. The
harness lives in `harness/harness.py` and writes its report to
`tracker/phase_N.M.md`, and the measured pass rate was 84.3 percent across
the 12 stages. A feeling that a role seems important is not that bar.

Run the probe first:

```bash
python3 tracker/preflight.py --check
python3 tracker/render_board.py
```

| Stage | Owner | Effort |
|---|---|---|
| Premise gate | Lead | high |
| Dispatch | Builder | none |

Documentation for the loop is at https://example.invalid/cadence and the
loop does not permit a third review round without an escalation.
"""

GOLDEN_AFTER = """# Build workflow cadence

## Table of contents

- [Why the premise gate exists](#why-the-premise-gate-exists)
- [Running the probe](#running-the-probe)

## Why the premise gate exists

The premise gate is mandatory and blocking for any phase whose deliverable
is model-generated.

- Added: 2026-07-31, after a phase shipped with 3 of 9 arms unrun
- Cost avoided: 27x the review budget it saved
- Harness: `harness/harness.py`
- Report target: `tracker/phase_N.M.md`
- Measured pass rate: 84.3 percent across the 12 stages

A feeling that a role seems important is not that bar.

```mermaid
flowchart TD
  probe[Run preflight] --> gate[Premise gate]
  gate --> dispatch[Dispatch builders]
```

## Running the probe

```bash
python3 tracker/preflight.py --check
python3 tracker/render_board.py
```

| Stage | Owner | Effort |
|---|---|---|
| Premise gate | Lead | high |
| Dispatch | Builder | none |

Documentation for the loop is at https://example.invalid/cadence and the
loop does not permit a third review round without an escalation.
"""


def _mutations() -> list[tuple]:
    """(name, mutated_after, catchable). Known misses are ASSERTED to pass,
    not merely documented: if one starts being caught, this harness fails
    and forces the coverage statement above to be rewritten. That is what
    makes `goal-contracts.md`'s "a verify surface must state its own
    coverage" executable rather than a paragraph nobody rereads."""
    a = GOLDEN_AFTER
    return [
        ("delete a number", a.replace("84.3 percent", "a high rate"), True),
        ("change 84.3 to 84.5", a.replace("84.3", "84.5"), True),
        ("delete a date", a.replace("2026-07-31, ", ""), True),
        ("drop a file path", a.replace("- Harness: `harness/harness.py`\n", ""), True),
        ("drop a URL", a.replace("https://example.invalid/cadence", "the docs site"), True),
        ("drop a backticked identifier",
         a.replace("- Report target: `tracker/phase_N.M.md`\n", ""), True),
        ("delete a line inside a bash fence",
         a.replace("python3 tracker/render_board.py\n", ""), True),
        ("delete a table row", a.replace("| Dispatch | Builder | none |\n", ""), True),
        ("delete a qualitative sentence carrying no hard atom",
         a.replace("A feeling that a role seems important is not that bar.\n", ""), True),
        ("reword so distinct content words vanish",
         a.replace(
             "The premise gate is mandatory and blocking for any phase whose "
             "deliverable\nis model-generated.",
             "The premise gate applies."), True),
        ("remove not from a claim",
         a.replace("does not permit", "does permit"), True),
        ("swap two numbers ACROSS claim units",
         a.replace("with 3 of 9 arms unrun", "with 12 of 9 arms unrun")
          .replace("across the 12 stages", "across the 3 stages"), False),
        ("swap two numbers WITHIN one claim unit",
         a.replace("with 3 of 9 arms unrun", "with 9 of 3 arms unrun"), False),
        ("reverse a dependency direction",
         a.replace("probe[Run preflight] --> gate[Premise gate]",
                   "gate[Premise gate] --> probe[Run preflight]"), False),
        ("reorder an ordered list",
         a.replace(
             "- Added: 2026-07-31, after a phase shipped with 3 of 9 arms unrun\n"
             "- Cost avoided: 27x the review budget it saved\n",
             "- Cost avoided: 27x the review budget it saved\n"
             "- Added: 2026-07-31, after a phase shipped with 3 of 9 arms unrun\n"),
         False),
    ]


def run_mutation_test() -> int:
    failures = 0

    base = compare(GOLDEN_BEFORE, GOLDEN_AFTER, "golden",
                   DEFAULT_LEX_THRESHOLD, DEFAULT_CLAIM_COVERAGE)
    if base.findings:
        print("FAIL  golden pair, a legitimate restructure must pass cleanly")
        for f in base.findings[:10]:
            print(f"        {f.format()}")
        failures += 1
    else:
        print(f"PASS  golden pair, legitimate restructure passes clean "
              f"({base.before_atoms} atoms, retention {base.retention:.3f}, "
              f"{len(base.additions)} additions)")
    print()

    for name, mutated, catchable in _mutations():
        res = compare(GOLDEN_BEFORE, mutated, "mutant",
                      DEFAULT_LEX_THRESHOLD, DEFAULT_CLAIM_COVERAGE)
        caught = bool(res.findings)
        ok = caught == catchable
        label = "Catchable" if catchable else "Known miss"
        detail = res.findings[0].kind if res.findings else "-"
        print(f"{'PASS' if ok else 'FAIL'}  [{label}] {name} "
              f"(expected {'caught' if catchable else 'not caught'}, "
              f"got {'caught' if caught else 'not caught'}, arm {detail})")
        if not ok:
            failures += 1
    print()
    total = len(_mutations()) + 1
    print(f"{'ok' if failures == 0 else 'error'}: {total} mutation cases, "
          f"{failures} failed")
    return failures


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _flag_value(argv: list[str], name: str) -> str | None:
    if name in argv:
        idx = argv.index(name)
        if idx + 1 < len(argv):
            return argv[idx + 1]
    for arg in argv:
        if arg.startswith(name + "="):
            return arg.split("=", 1)[1]
    return None


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _rel(path: str) -> str:
    try:
        return os.path.relpath(os.path.abspath(path), _repo_root())
    except ValueError:
        return path


def _read(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return None


def _git_show(rel: str) -> str | None:
    proc = subprocess.run(
        ["git", "show", f"HEAD:{rel}"],
        cwd=_repo_root(), capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        print(f"error: git show HEAD:{rel} failed: {proc.stderr.strip()}",
              file=sys.stderr)
        return None
    return proc.stdout


def _resolve_threshold(argv: list[str], flag: str, default: float) -> float | None:
    raw = _flag_value(argv, flag)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        print(f"error: {flag} expects a number, got {raw!r}", file=sys.stderr)
        return None
    if value < default:
        # A threshold may only be tightened. Loosening a check so the check
        # passes is a failed run, per .claude/rules/goal-contracts.md, so
        # the loosened value is unreachable through the CLI rather than
        # merely forbidden in prose.
        print(f"error: {flag} may only be tightened. Default is {default}, "
              f"got {value}. See .claude/rules/goal-contracts.md: changing "
              f"the check so the check passes is a failed run.", file=sys.stderr)
        return None
    return value


def _print_additions(rows: list[dict]) -> None:
    print("| After line | Kind | Classification | First 120 characters |")
    print("|---|---|---|---|")
    if not rows:
        print("| - | - | - | no additions detected |")
        return
    for row in rows:
        text = row["text"].replace("|", "\\|")
        print(f"| {row['line']} | {row['kind']} | TO BE CLASSIFIED | \"{text}\" |")


# Every flag this script accepts. An unrecognized flag is an error rather
# than a silent no-op, because the tighten-only guarantee on the two
# thresholds depends on the flag actually being READ: a typo such as
# `--lex-threshhold 0.5` would otherwise be ignored, the gate would run at
# its default, and the operator would believe they had tightened it. A
# gate that quietly ignores what you told it is a gate that lies.
KNOWN_FLAGS = {
    "--self-test", "--mutation-test", "--check", "--verbose", "--additions",
    "--before", "--after", "--git", "--lex-threshold", "--claim-coverage",
}

# Flags that consume the following argv item as their value.
VALUE_FLAGS = {"--before", "--after", "--git", "--lex-threshold",
               "--claim-coverage"}


def _unknown_flags(argv: list[str]) -> list[str]:
    unknown, skip = [], False
    for arg in argv:
        if skip:
            skip = False
            continue
        if not arg.startswith("--"):
            continue
        name = arg.split("=", 1)[0]
        if name not in KNOWN_FLAGS:
            unknown.append(name)
        elif name in VALUE_FLAGS and "=" not in arg:
            skip = True
    return unknown


def main(argv: list[str]) -> int:
    unknown = _unknown_flags(argv)
    if unknown:
        print(f"error: unrecognized flag(s): {', '.join(unknown)}. "
              f"Known flags: {', '.join(sorted(KNOWN_FLAGS))}", file=sys.stderr)
        return 2

    if "--self-test" in argv:
        return 1 if run_self_test() else 0
    if "--mutation-test" in argv:
        return 1 if run_mutation_test() else 0

    lex = _resolve_threshold(argv, "--lex-threshold", DEFAULT_LEX_THRESHOLD)
    cov = _resolve_threshold(argv, "--claim-coverage", DEFAULT_CLAIM_COVERAGE)
    if lex is None or cov is None:
        return 2

    git_target = _flag_value(argv, "--git")
    before_path = _flag_value(argv, "--before")
    after_path = _flag_value(argv, "--after")

    if git_target:
        after_path = git_target
        rel = _rel(git_target)
        if rel in LOCKED_DOCS:
            print(f"error: {rel} is locked until the Step 6.2 reconciliation "
                  f"and must not be restructured", file=sys.stderr)
            return 3
        before_text = _git_show(rel)
        after_text = _read(git_target)
    elif before_path and after_path:
        rel = _rel(after_path)
        if rel in LOCKED_DOCS:
            print(f"error: {rel} is locked until the Step 6.2 reconciliation "
                  f"and must not be restructured", file=sys.stderr)
            return 3
        before_text = _read(before_path)
        after_text = _read(after_path)
    else:
        print(__doc__.split("USAGE")[-1].strip(), file=sys.stderr)
        return 2

    if before_text is None or after_text is None:
        return 2

    result = compare(before_text, after_text, _rel(after_path), lex, cov)

    if "--additions" in argv:
        _print_additions(result.additions)
        return 0

    atom_findings = sum(1 for f in result.findings if f.kind == "atom")
    claim_findings = sum(1 for f in result.findings if f.kind == "claim")
    neg_findings = sum(1 for f in result.findings if f.kind == "negation")
    ret_findings = sum(1 for f in result.findings if f.kind == "retention")

    if "--verbose" in argv:
        before_units = segment(before_text)
        counts: Counter = Counter()
        for u in before_units:
            counts.update(a.category for a in u.atoms)
        print(f"Before: {result.before_atoms} atoms in {result.claims_total} claim units")
        for category in (CAT_NUM, CAT_DATE, CAT_PATH, CAT_URL, CAT_IDENT,
                         CAT_CODELINE, CAT_LEXC, CAT_LEXO):
            print(f"  {category}: {counts.get(category, 0)}")
        print(f"After: {result.after_atoms} atoms")
        print(f"Ordinary-word retention: {result.retention:.3f} "
              f"(threshold {lex:.3f}, {result.lost_types} types lost)")
        print(f"Claim units skipped by Arm 3: {result.claims_skipped} "
              f"(no hard atom and fewer than {MIN_CLAIM_TYPES} content words)")
        print()

    for finding in result.findings:
        print(finding.format())

    status = "ok" if not result.findings else "error"
    print(f"{status}: {result.before_atoms} atoms | {atom_findings} lost | "
          f"{claim_findings} orphan claims | {neg_findings} negation drops | "
          f"{ret_findings} retention | {len(result.additions)} additions | "
          f"{result.claims_skipped} claims skipped | "
          f"lex retention {result.retention:.3f} (>= {lex:.3f})")
    return 1 if result.findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
