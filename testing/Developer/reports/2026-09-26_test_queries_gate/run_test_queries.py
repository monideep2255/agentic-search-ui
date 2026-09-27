"""Card 55 prototype: the test queries document as the gate for done.

The product owner's decision of 2026-09-26 (DECISIONS.md): the test queries
document, `testing/Test_queries_and_workflows.md`, decides whether work is
done. This script is the prototype of the runner that does it. The design is
`design.md` beside this file.

HOW IT READS THE DOCUMENT. Every run parses the document afresh. Nothing about
what an answer should say is written in this file:

- Each `### N. Title` under a numbered `## N.` section is one entry.
- "Queries to try:" (or "Where to try it:") says what to ask: every backticked
  question, its depth, how many times, follow-ups in the same conversation and
  a choice to pick when the answer asks back.
- "What you should see:" gives the checks, one line per bullet. A bullet is
  classified by what can decide it:
    exact         a script over the saved events and answer text decides it
    graded        a model reads the bullet's own words beside the answer
    screen        the running web app has to be looked at, through /verify
    person        only a person can judge it
    not runnable  nothing can check it today, and the reason is printed
    context       not a check: "Why it matters", "Known:", history
  A screen, person or graded bullet can also carry exact checks for the part a
  script can decide, such as a limit in seconds inside a line about the screen.
- The section trailer "What the answer must never do ... applies to every
  query in this section" is attached to every entry of that section, and binds
  every answer of those entries.

What this file does hold is the vocabulary: HOW a kind of claim is checked
(a link host, a count against a list, a quoted phrase, a number of seconds).
The words and numbers each check uses are read out of the bullet every run, so
editing a bullet changes its check, and deleting one deletes it. A bullet the
vocabulary does not recognise is never dropped: it goes to the model grader.

Where a quoted phrase lives decides its class, read from the code base each
run: a phrase the web app's source writes is screen text, one the backend's
source writes is answer text (exact), and one in neither was written by a model
or comes from a record: it is only checked when the bullet forbids it.

MODES

  --dry-run      parse, classify and list every entry, its class, its asks and
                 its checks; send nothing. --markdown prints the inventory table
                 and --summary-json the counts and the cost estimate.
  --replay N=F   apply entry N's exact checks to saved event files F (comma
                 separated; F#i picks run i of a list file, F#* all of them),
                 with no network. A saved answer goes to the ask with its
                 question and depth, else to the next ask in order. Reads the shapes saved by run_consistency.py, the
                 2026-09-26 answer-speed timeline and the 2026-09-24 no-hardcoding
                 runs.
  --self-test    prove each check kind can fail as well as pass, on fixed
                 inputs, with no network.
  (default)      ask every question against --api, save every event, and run the
                 exact checks. Graded, screen and person lines are listed as not
                 run: this prototype runs the exact class only.

EXIT CODES: 0 nothing failed; 1 at least one exact check failed; 2 bad
arguments, an unreachable API, or a target whose /health is not the expected
app_env.

WHAT IT DOES NOT DO, stated so a gap is arguable:
  - It does not grade, capture screens or judge anything a person must judge.
  - It does not decide the gate: no baseline, no confirmation rerun. Those are
    tickets in design.md.
  - An exact check can cover only part of a bullet's words. The dry run prints
    what each check tests, in words, so the gap is visible.
  - It never opens a cited link: host and path only.
  - It sends a question only as the document words it. A follow-up the
    document does not anchor to a named question is listed, not guessed.

The live mode is untested: this prototype was exercised with --dry-run,
--replay and --self-test only, since a golden run was live on develop.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
DOC = REPO_ROOT / "testing" / "Test_queries_and_workflows.md"
BACKEND_SRC = REPO_ROOT / "src" / "system_03_search_agent"
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
VERIFY_SPECS = REPO_ROOT / ".claude" / "skills" / "verify" / "specs" / "test_queries"

# Measured, never assumed. Each constant names the file it was read from.
# 8 local questions metered at $0.146 in total, "about 2 cents each" on develop:
# testing/Developer/reports/2026-09-26_answer_speed/report.md, "Method, files and spend".
COST_PER_QUESTION_USD = 0.146 / 8
# Median client seconds per run, phase 8.6 re-land golden run, 150 runs:
# testing/Developer/reports/2026-09-26_phase_8.6-reland_golden/runs.jsonl.
MEDIAN_SECONDS = 14.3
# Median answer_text length in characters and median citations per run, same run.
MEDIAN_ANSWER_CHARS = 1866
MEDIAN_CITATIONS = 19
# The grader's tier, balance, at its list price per million tokens (2026-06-24).
GRADER_USD_PER_M_IN = 2.00
GRADER_USD_PER_M_OUT = 10.00
GRADER_PROMPT_TOKENS = 700  # the fixed instruction drafted in design.md
GRADER_TOKENS_PER_SOURCE_ROW = 30
GRADER_OUT_TOKENS_PER_BULLET = 60
CHARS_PER_TOKEN = 4
WORKERS = 2  # the E-utilities queue allows two concurrent runs (run_consistency.py)

WEB_DEFAULT_DEPTH = "plain_language"  # frontend/src/App.tsx: useState<AudienceDepth>(...)
STREAM_LINE_TIMEOUT_S = 200
RUN_DEADLINE_S = 420
STOP_AFTER_S = 4.0
PAUSE_BETWEEN_RUNS_S = 2.0

EXACT, GRADED, SCREEN, PERSON, NOT_RUNNABLE, CONTEXT = (
    "exact", "graded", "screen", "person", "not runnable", "context",
)
CLASS_ORDER = [EXACT, GRADED, SCREEN, PERSON]

# Mirrors contracts/events.py NCBI_SOURCE_URL_PATTERN's hosts, as
# integrations_smoke.py does.
CITATION_HOST = re.compile(
    r"^https://(?:([A-Za-z0-9-]+\.)*ncbi\.nlm\.nih\.gov/"
    r"|(?:www\.)?clinicaltrials\.gov/study/|(?:www\.)?omim\.org/)"
)

# Where each kind of record lives, read from the citation URLs the golden runs of
# 2026-09-22 to 2026-09-26 saved. Knowledge of the sites, not of any answer.
RESOURCES: dict[str, str] = {
    "gene_summary": r"ncbi\.nlm\.nih\.gov/gene/",
    "gene": r"ncbi\.nlm\.nih\.gov/gene/",
    "omim": r"omim\.org/entry/|ncbi\.nlm\.nih\.gov/omim/",
    "clinvar": r"ncbi\.nlm\.nih\.gov/clinvar/",
    "dbvar": r"ncbi\.nlm\.nih\.gov/dbvar/",
    "medgen": r"ncbi\.nlm\.nih\.gov/medgen/",
    "pubmed": r"pubmed\.ncbi\.nlm\.nih\.gov/",
    "geo": r"ncbi\.nlm\.nih\.gov/(gds|geo)/",
    "mesh": r"ncbi\.nlm\.nih\.gov/mesh/",
    "taxonomy": r"ncbi\.nlm\.nih\.gov/[Tt]axonomy/",
    "trial": r"clinicaltrials\.gov/study/",
    "sra": r"ncbi\.nlm\.nih\.gov/sra/",
    "biosample": r"ncbi\.nlm\.nih\.gov/biosample/",
    "bioproject": r"ncbi\.nlm\.nih\.gov/bioproject/",
    "assembly": r"ncbi\.nlm\.nih\.gov/(assembly|datasets/genome)/",
    "pathogens": r"ncbi\.nlm\.nih\.gov/pathogens/",
    "snp": r"ncbi\.nlm\.nih\.gov/snp/",
}
# The words a bullet uses for each kind of record.
RESOURCE_WORDS: list[tuple[str, str]] = [
    (r"gene summary|gene's own summary|gene description", "gene_summary"),
    (r"\bgene record\b", "gene"),
    (r"\bOMIM\b", "omim"),
    (r"\bClinVar\b", "clinvar"),
    (r"\bdbVar\b", "dbvar"),
    (r"\bMedGen\b", "medgen"),
    (r"\bPubMed\b|answer with papers", "pubmed"),
    (r"\bGEO\b", "geo"),
    (r"\bMeSH\b", "mesh"),
    (r"\bTaxonomy\b", "taxonomy"),
    (r"ClinicalTrials\.gov|clinicaltrials\.gov|study page|\bNCT number", "trial"),
    (r"\bSRA run", "sra"),
    (r"\bBioSample record", "biosample"),
    (r"\bproject record\b", "bioproject"),
    (r"\bassembly\b", "assembly"),
    (r"Pathogen Detection page", "pathogens"),
]
ACCESSION = re.compile(
    r"\b(SRR\d+|SAMN\d+|PRJNA\d+|GRCh38\.p\d+|NCT\d{8}|GSE\d+)\b|\bOMIM (\d{6})\b"
)
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "ten": 10, "twenty": 20}

CONTEXT_PREFIXES = (
    "Why it matters", "Known", "Before ", "Before,", "Earlier", "Measured", "Checked live",
    "When checked live", "Since 20", "Item ", "This entry is deliberately",
    "What it answers today", "The end-to-end half", "How it is checked", "Honestly stated",
    "If the answer instead", "If instead", "If you have",
)
# A permission, read in the first eight words only: "may differ", "can show", "Sometimes".
PERMISSIVE = re.compile(r"\bmay\b|\bsometimes\b|\bcan (show|differ|vary|go)\b", re.IGNORECASE)
UI_MARKERS = re.compile(
    r"\b(screen|click|clicking|clicked|hover|hovering|tap|tapping|Tab|tabbing|Escape|button|"
    r"buttons|chip|chips|badge|grey|red|bold|card|pill|pills|phone|390|pixels|scroll|"
    r"scrolls|sideways|collapsed|progress|spinner|counter|heading under|field|menu|top right|"
    r"top bar|tour|disclaimer|selector|locked|raised|styled|styling|reveal|folded|Show answer|"
    r"Hide answer|panel|rail|highlight|icon|tab title|favicon|footer|header|layout|wide box|"
    r"full width|greyed|stacked rows|pages at|opens a card|builds on screen|on screen|"
    r"Show work|copy button|home page|light grey|source list|Table cells|being written|"
    r"moving dots|status word|promised|promises|mode change|applies only to the next question|"
    r"applies to the next question|handoff lines|Integrations|About|Architecture)\b"
)
PERSON_MARKERS = re.compile(
    r"screen reader|readable|flicker|too fast|feels|feel |frozen screen|continuous motion|"
    r"looks stuck|timing scales|reveal timing|announces"
)
MISSING_STEP = [
    (re.compile(r"Wi-Fi|offline|connection drops|back online", re.IGNORECASE),
     ("the capture has no offline step (capture.mjs steps: goto, disclaimer, fill, click, "
      "press, waitFor, wait)")),
    (re.compile(r"\bpast(e|ed|ing)\b|text editor|select it all|Selecting and pasting", re.IGNORECASE),
     "the capture has no select-and-read-the-selection step"),
]
NEEDS_NUMBER = re.compile(r"No slower than|fewer answers than before")
DELEGATED = re.compile(r"Pasted as printed|drops the s from https")
SIGN_IN_WORDS = re.compile(
    r"\blog ?in\b|\blogged in\b|\blogging\b|\blogs you in\b|\blog out\b|signed[- ]in|"
    r"your searches|history|password|\baccount\b|searches button", re.IGNORECASE
)
SIGN_IN_TITLES = re.compile(r"Log in|password|history|search limit|past search", re.IGNORECASE)
# In an entry that is not about signing in, the lines that still need a signed-in screen.
SIGN_IN_BULLET = re.compile(
    r"signed[- ]in|your searches|searches button|\bhistory\b|password|\blog out\b", re.IGNORECASE
)
AUTO_PICK = re.compile(r"pick a choice|pick one\b|asked back first")
ASKED_AGAIN = re.compile(r"when asked again|on a second run")


# ----------------------------------------------------------------- the model


@dataclass
class Turn:
    text: str | None = None  # a question, or None for a pick
    pick: str | None = None  # the option phrase to pick; "first" for the first offered
    auto_pick: bool = False  # pick only if the previous turn asked back


@dataclass
class Conversation:
    turns: list[Turn]
    depth: str
    repeats: int = 1
    stop: bool = False

    def key(self) -> str:
        body = json.dumps(
            [self.depth, self.stop, [(t.text, t.pick, t.auto_pick) for t in self.turns]]
        )
        first = next((t.text for t in self.turns if t.text), "pick")
        slug = re.sub(r"[^a-z0-9]+", "-", first.lower()).strip("-")[:32]
        return f"{slug}-{self.depth[:5]}-{hashlib.sha1(body.encode()).hexdigest()[:8]}"

    def label(self) -> str:
        parts = []
        for t in self.turns:
            if t.text:
                parts.append(f"`{t.text}`")
            elif t.auto_pick:
                parts.append("[pick the first choice if asked back]")
            else:
                parts.append(f'[pick "{t.pick}"]')
        extra = f" x{self.repeats}" if self.repeats > 1 else ""
        stop = " [press Stop]" if self.stop else ""
        return " -> ".join(parts) + f" ({self.depth}){extra}{stop}"


@dataclass
class Check:
    kind: str
    params: dict
    says: str  # what the script tests, in words
    target: str = "final"  # final | every | follow | all (compare runs) | turns:<q|q>
    depth: str | None = None  # only runs at this depth
    fresh_only: bool = False  # only a question asked on a fresh page, never a follow-up turn


@dataclass
class Bullet:
    text: str
    cls: str
    checks: list[Check] = field(default_factory=list)
    reason: str = ""
    section_wide: bool = False
    bind: list[str] = field(default_factory=list)  # question texts this bullet names
    used: set[str] = field(default_factory=set)  # quotes an exact check already consumed

    def key(self, entry_no: int) -> str:
        norm = re.sub(r"\s+", " ", self.text.strip().lower())
        return f"{entry_no}:{hashlib.sha1(norm.encode()).hexdigest()[:10]}"


@dataclass
class Entry:
    number: int
    title: str
    section: int
    queries: list[str] = field(default_factory=list)
    bullets: list[Bullet] = field(default_factory=list)
    convs: list[Conversation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    ui_only: bool = False
    needs_sign_in: bool = False
    removed: bool = False

    def check_bullets(self) -> list[Bullet]:
        return [b for b in self.bullets if b.cls != CONTEXT]

    def entry_class(self) -> str:
        runnable = [b.cls for b in self.check_bullets() if b.cls in CLASS_ORDER]
        if not runnable:
            return NOT_RUNNABLE
        return max(runnable, key=CLASS_ORDER.index)

    def sign_in_centric(self) -> bool:
        return self.needs_sign_in and bool(SIGN_IN_TITLES.search(self.title))

    def asks_per_pass(self) -> int:
        return sum(len(c.turns) * c.repeats for c in self.convs)


# ------------------------------------------------------ where a phrase lives


class SourceIndex:
    """The backend's and the web app's source text, read once per run."""

    def __init__(self) -> None:
        self.backend = self._read(BACKEND_SRC, ("*.py",))
        self.frontend = self._read(FRONTEND_SRC, ("*.ts", "*.tsx"))

    @staticmethod
    def _read(root: Path, globs: tuple[str, ...]) -> str:
        chunks = []
        if root.exists():
            for pattern in globs:
                for path in root.rglob(pattern):
                    if "test" in path.name or "__tests__" in path.parts:
                        continue
                    try:
                        chunks.append(path.read_text(encoding="utf-8"))
                    except (OSError, UnicodeDecodeError):
                        continue
        return re.sub(r"\s+", " ", "\n".join(chunks))

    def origin(self, phrase: str) -> str:
        """frontend, backend or none: where the phrase's fixed words are written.

        The web app is searched first: a label it writes is screen text even when a
        backend comment happens to mention it. A templated phrase ("Clinical features
        MedGen lists for Marfan syndrome") is found by its leading words, three at least.
        """
        parts = [f.strip() for f in re.split(r"[\d,;:.()\"“”…?!]+", phrase) if f.strip()]
        frags = [f for f in parts if len(f.split()) >= 3]
        if not frags and len(phrase.split()) <= 3:
            frags = [" ".join(parts)] if parts else []

        def backend_has(frag: str) -> bool:
            words = frag.split()
            floor = min(3, len(words))
            return any(" ".join(words[:n]) in self.backend
                       for n in range(len(words), floor - 1, -1))

        front = sum(1 for f in frags if f in self.frontend)
        back = sum(1 for f in frags if f in self.backend)
        if front > back:
            return "frontend"
        if back > front:
            return "backend"
        if front:  # written in both: a short label is the web app's, a sentence the answer's
            return "frontend" if len(phrase.split()) <= 3 else "backend"
        if any(backend_has(f) for f in frags):  # a template, found by its leading words
            return "backend"
        return "none"


# ------------------------------------------------------------ the parsing


def parse_document(text: str, sources: SourceIndex | None) -> list[Entry]:
    entries: list[Entry] = []
    section: int | None = None
    current: Entry | None = None
    mode: str | None = None
    trailer: list[str] = []
    trailer_open = False

    def close_section() -> None:
        nonlocal trailer, trailer_open
        if trailer and section is not None:
            for e in entries:
                if e.section == section:
                    e.bullets.extend(Bullet(text=t, cls="", section_wide=True) for t in trailer)
        trailer, trailer_open = [], False

    for line in text.splitlines():
        m = re.match(r"^## (\d+)\. (.+)$", line)
        if m or line.startswith("## "):
            close_section()
            section = int(m.group(1)) if m else None
            current, mode = None, None
            continue
        if section is None:
            continue
        m = re.match(r"^### (\d+)\. (.+)$", line)
        if m:
            current = Entry(number=int(m.group(1)), title=m.group(2).strip(), section=section)
            entries.append(current)
            mode = None
            continue
        if re.match(r"^What the answer must never do.*applies to every query in this section",
                    line):
            trailer_open, current, mode = True, None, None
            continue
        if trailer_open:
            if line.startswith("- "):
                trailer.append(line[2:].strip())
            continue
        if current is None:
            continue
        m = re.match(r"^(Queries to try|Where to try it):\s*(.*)$", line)
        if m:
            mode = "Q"
            if m.group(2).strip():
                current.queries.append(m.group(2).strip())
            continue
        if line.startswith("What you should see:"):
            mode = "S"
            continue
        if line.startswith("- ") and mode == "Q":
            current.queries.append(line[2:].strip())
        elif line.startswith("- ") and mode == "S":
            current.bullets.append(Bullet(text=line[2:].strip(), cls=""))
    close_section()

    by_no = {e.number: e for e in entries}
    for e in entries:
        parse_queries(e, by_no)
    for e in entries:
        own = [b for b in e.bullets if not b.section_wide]
        for b in own[1:] + [b for b in e.bullets if b.section_wide]:
            classify(e, b, sources)
        if own:
            classify(e, own[0], sources, headline=True)
    return entries


def _depth_of(text: str) -> str | None:
    if re.search(
        r"once in Plain language and once in Researcher|in Plain language, then in Researcher|"
        r"in Researcher, then in Plain language|at both depths|asked twice:.*Plain language"
        r".*Researcher",
        text,
    ):
        return "both"
    if re.search(r"\b(at|in|choose) Researcher\b|researcher depth|Researcher mode", text, re.IGNORECASE):
        return "researcher"
    if re.search(r"\b(at|in) Plain language\b", text, re.IGNORECASE):
        return "plain_language"
    return None


def _repeats_of(text: str, depth: str | None) -> int:
    if re.search(r"three times", text):
        return 3
    if re.search(r"two separate", text):
        return 2
    if re.search(r"\btwice\b", text) and depth != "both":
        return 2
    return 1


def _questions(text: str) -> list[str]:
    return [q for q in re.findall(r"`([^`]+)`", text) if not q.startswith(("/", "http"))]


def _convs(turn_lists: list[list[Turn]], depth: str | None, repeats: int,
           stop: bool) -> list[Conversation]:
    depths = ["plain_language", "researcher"] if depth == "both" else [depth or WEB_DEFAULT_DEPTH]
    return [Conversation(turns=[Turn(t.text, t.pick, t.auto_pick) for t in tl], depth=d,
                         repeats=repeats, stop=stop)
            for tl in turn_lists for d in depths]


def parse_queries(entry: Entry, by_no: dict[int, Entry]) -> None:
    previous: list[list[Turn]] = []
    auto_pick = any(AUTO_PICK.search(b.text) for b in entry.bullets)
    asked_again = any(ASKED_AGAIN.search(b.text) for b in entry.bullets)
    for q in entry.queries:
        if re.match(r"^None\.", q):
            entry.removed = True
            continue
        if SIGN_IN_WORDS.search(q):
            entry.needs_sign_in = True
        if re.match(r"^(No query needed|No query of its own|No question needed|the search page|"
                    r"Any two questions|Any question:)", q, re.IGNORECASE):
            entry.ui_only = True
            continue
        if re.match(r"^(Then query|Query \d+ covers)", q):
            continue
        depth = _depth_of(q)
        repeats = _repeats_of(q, depth)
        stop = bool(re.search(r"press Stop", q))
        m = re.match(r"^The same question at (Researcher|Plain language)", q)
        if m and previous:
            d = "researcher" if m.group(1) == "Researcher" else "plain_language"
            entry.convs += _convs(previous, d, repeats, stop)
            continue
        qs = _questions(q)
        if not qs:
            continue
        turn_lists: list[list[Turn]] = []
        m = re.match(r"^After query (\d+), ask `([^`]+)`", q)
        if m:
            first = by_no.get(int(m.group(1)))
            first_qs = _questions(first.queries[0]) if first and first.queries else []
            if not first_qs:
                entry.notes.append(f"query {m.group(1)} has no question to follow")
            else:
                turn_lists.append([Turn(text=first_qs[0]), Turn(text=m.group(2))])
            turn_lists += [[Turn(text=x)] for x in qs if x != m.group(2)]
        elif "as a follow-up in the same conversation" in q:
            turn_lists.append([Turn(text=x) for x in qs])
        else:
            unresolved = re.search(r"`([^`]+)` after an? (\w+) answer", q)
            picked = re.search(r"`([^`]+)`, then pick \"([^\"]+)\"", q)
            for x in qs:
                if unresolved and x == unresolved.group(1):
                    entry.notes.append(
                        f"`{x}` follows \"a {unresolved.group(2)} answer\" but names no "
                        "question to follow: not asked. \"After query N\" would make it runnable"
                    )
                    continue
                if picked and x == picked.group(1):
                    turn_lists.append([Turn(text=x), Turn(pick=picked.group(2))])
                else:
                    turn_lists.append([Turn(text=x)])
        if auto_pick:
            for tl in turn_lists:
                if len(tl) == 1:
                    tl.append(Turn(pick="first", auto_pick=True))
        if asked_again and repeats == 1:
            repeats = 2
        previous = turn_lists
        entry.convs += _convs(turn_lists, depth, repeats, stop)
    if not entry.convs and not entry.removed:
        entry.ui_only = True


# -------------------------------------------------------- the classifying

NEGATION = re.compile(
    r"\b(no|not|never|nor|without|none|neither|rather than|instead of)\b", re.IGNORECASE
)


def _quotes(text: str) -> list[tuple[str, bool, bool, bool]]:
    """(quote, negated, is_example, qualified) for every double-quoted phrase.

    "such as" is read in the quote's own sentence and negation in its own clause, with
    other quotes' words removed, so "Based on 4 sources, not yet confirmed" does not
    negate the
    quote after it. A quote in parentheses, one holding a placeholder such as N or
    <date>, and one followed by "with no", "followed", "unless" or "when" are
    qualified: the grader reads them, since no literal match is what they mean.
    """
    out = []
    for m in re.finditer(r"\"([^\"]{3,})\"", text):
        start = max(text.rfind(". ", 0, m.start()), text.rfind("; ", 0, m.start()))
        sentence = re.sub(r"\"[^\"]*\"", "", text[start + 1: m.start()])
        clause = re.split(r"[,:;]", sentence)[-1]  # negation governs its own clause only
        negated = bool(NEGATION.search(clause))
        example = bool(re.search(r"(such as|for example|e\.g\.|\blike)\b", sentence))
        after = text[m.end(): m.end() + 30]
        in_parens = text[: m.start()].count("(") > text[: m.start()].count(")")
        qualified = bool(re.match(r"^\W*(with no|followed|unless|when|if)\b", after)) or \
            in_parens or bool(re.search(r"\b[NXY]\b|<[^>]+>|\{[^}]+\}", m.group(1)))
        out.append((m.group(1), negated, example, qualified))
    return out


def _shape(example: str) -> str:
    """A regex for an example's shape: its digits become any digits."""
    return re.sub(r"\d+", r"\\d+", re.escape(example))


def _pattern(quote: str) -> str:
    """A quote with an ellipsis matches any words where the ellipsis stands."""
    parts = re.split(r"\s*(?:\.\.\.|…)\s*", quote)
    return r"\s*.+?\s*".join(re.escape(p) for p in parts)


def _num(word: str) -> int:
    return NUMBER_WORDS.get(word.lower(), 0) or int(word.replace(",", ""))


def recognise(entry: Entry, b: Bullet, sources: SourceIndex | None) -> list[Check]:
    """The exact checks this bullet's own words support. Empty when none."""
    t = b.text
    checks: list[Check] = []
    used = b.used  # quotes a recogniser has already consumed

    def add(kind: str, params: dict, says: str, target: str = "final") -> None:
        checks.append(Check(kind, params, says, target))

    m = re.search(r"never more than (\d+)", t)
    if m:
        add("max_seconds", {"seconds": int(m.group(1))},
            f"the answer lands in at most {m.group(1)} seconds")
    elif re.search(r"(well )?under a minute", t):
        add("max_seconds", {"seconds": 60}, "the answer lands in under 60 seconds")

    m = re.search(r"An answer that lost a background search ends with \"([^\"]+)\"", t)
    if m:
        used.add(m.group(1))
        add("if_lost_search_contains", {"phrase": m.group(1)},
            "when a background search failed, the answer ends with the note")
    if re.search(r"No line saying a background search did not finish", t):
        add("no_sentence_with_words", {"words": ["background", "search", "not", "finish"]},
            "no sentence says a background search did not finish")
    m = re.search(r"trust line reads \"([^\"]+)\"", t)
    if m:
        used.add(m.group(1))
        kind = "if_lost_search_trust" if "lost" in entry.title.lower() else "trust_line_has"
        add(kind, {"phrase": m.group(1)}, f"the trust line contains \"{m.group(1)}\"")
    m = re.search(r"one plain line such as \"([^\"]+)\" or \"([^\"]+)\"", t)
    if m:
        used.update([m.group(1), m.group(2)])
        add("trust_line_shape", {"shapes": [_shape(m.group(1)), _shape(m.group(2))]},
            "the trust line has the shape of one of the two examples")
    m = re.search(r"runs past \"([^\"]+)\"", t)
    if m:
        used.add(m.group(1))
        add("runs_past", {"phrase": m.group(1)},
            f"the text continues past \"{m.group(1)}\" instead of stopping there")

    if re.search(r"opening count and the list agree|opening count matches the list|"
                 r"number an answer opens with agrees", t):
        add("count_matches_list", {}, "the number in the opening sentence equals the rows of "
            "the list or table it names")
    if re.search(r"trust line names the same number as the SOURCES|The two numbers are the same",
                 t):
        add("trust_count_matches_sources", {}, "\"Based on N\" equals the distinct links cited")
    if re.search(r"has no headings, lists or tables", t):
        add("no_structure", {}, "the answer has no heading, list or table")
    if re.search(r"Researcher mode has short topic headings", t):
        add("has_structure", {}, "the answer has a heading and a list or table")
    if re.search(r"more than one layer", t):
        add("layers_at_least", {"n": 2}, "citations come from at least two data layers")
    if re.search(r"same sources appear in both modes|list the same records|"
                 r"same set of sources|same answer content and the same sources", t):
        add("same_sources", {}, "every run of the question cites the same set of links", "all")
    if re.search(r"two answers read differently|differ in their opening sentence", t):
        add("depths_differ", {}, "the two depths' answers are not identical", "all")
    if re.search(r"is longer than the Plain language answer", t):
        add("researcher_longer", {}, "the Researcher answer has more words than the Plain "
            "language one", "all")

    if re.search(r"appears ONCE|listed once|lists each record once|each record listed once", t) \
            and "source list" not in t:
        add("rows_unique", {}, "no record is listed twice")
    if re.search(r"never three times", t):
        add("max_mentions", {"n": 2}, "no source is cited in more than two places")
    if re.search(r"No paragraph starts with a lowercase letter", t):
        add("paragraph_starts", {}, "no paragraph opens lowercase or with a stray quote mark")
    m = re.search(r"No sentence opens \"([^\"]+)\" or \"([^\"]+)\"", t)
    if m:
        used.update([m.group(1), m.group(2)])
        add("no_sentence_opens", {"openers": [m.group(1), m.group(2)]},
            f"no sentence opens \"{m.group(1)}\" or \"{m.group(2)}\"")
    if re.search(r"No request to name a gene|Not a request to name a gene|no request for a gene "
                 r"name|rather than a request to name a gene|No \"which gene", t):
        add("text_lacks", {"phrase": "which gene", "regex": r"\bwhich gene\b"},
            "the answer never asks \"which gene\"")
        used.add("which gene, variant or condition do you mean?")

    # A backticked example of a code, forbidden: nothing in the prose has its shape.
    questions = {tt.text for c in entry.convs for tt in c.turns}
    for ex in re.findall(r"`([^`]+)`", t):
        before = t[: t.find(ex)]
        if re.search(r"\d", ex) and re.search(r"\b(never|No|no)\b[^.]*$", before) and \
                ex not in questions and not re.fullmatch(r"(\[\d+\])+", ex):
            add("no_shape", {"regex": _shape(ex)},
                f"no text in the answer's prose has the shape of `{ex}`")

    # Names a gene symbol the answer must carry.
    m = re.match(r"^([A-Z][A-Z0-9-]{2,}) is named", t)
    if m:
        names = [m.group(1)]
        m2 = re.search(r"with ([A-Z][A-Z0-9-]{2,}) and ([A-Z][A-Z0-9-]{2,}) beside it", t)
        if m2:
            names += [m2.group(1), m2.group(2)]
        add("names_present", {"names": names}, "the answer names " + ", ".join(names))

    # Rows of an isolate table.
    m = re.search(r"with (\d+) rows", t)
    if m:
        add("row_count", {"n": int(m.group(1))}, f"the table has {m.group(1)} rows")
    if re.search(r"No isolate rows|no isolate rows", t):
        add("row_count", {"n": 0}, "no table rows")
    m = re.search(r"every row carries a (bla[\w-]+) gene", t)
    if m:
        add("rows_have_gene", {"prefixes": [m.group(1)]},
            f"every row lists a gene starting {m.group(1)}")
    m = re.search(r"carries a gene starting with (bla[\w-]+).*never (bla[\w-]+)", t)
    if m:
        add("rows_have_gene", {"prefixes": [m.group(1)], "exact_allele": True},
            f"every row lists {m.group(1)} itself, not {m.group(2)}")
    m = re.search(r"at least one of the \w+ families \(([^)]+)\)", t)
    if m:
        add("rows_have_gene", {"prefixes": [f.strip() for f in m.group(1).split(",")]},
            "every row lists a gene from one of the named families")
    if re.search(r"carrying an mcr gene", t):
        add("rows_have_gene", {"prefixes": ["mcr"]}, "every row lists an mcr gene")
    m = re.search(r"Never list a (bla[\w-]+) carrier as an ESBL isolate", t)
    if m:
        add("esbl_rows_not_only", {"gene": m.group(1), "needs": "blaCTX-M"},
            f"on an ESBL question, no row is listed for {m.group(1)} alone")
    if re.search(r"the answer says \"at least\" that many", t):
        used.add("at least")
        add("if_truncated_says_at_least", {},
            "when the isolate scan was cut off, the answer says \"at least\"")
    m = re.search(r"(?:The count reads|reading) (\d{1,3}(?:,\d{3})+|\d{4,})", t)
    if m:
        add("text_has", {"phrase": m.group(1)}, f"the answer states the count {m.group(1)}")
    m = re.search(r"up to (\w+) of its SRA runs", t)
    if m:
        add("max_resource", {"resource": "sra", "n": _num(m.group(1))},
            f"at most {_num(m.group(1))} SRA run records cited")
    m = re.search(r"up to (\w+) recruiting clinical trials", t)
    if m:
        add("max_resource", {"resource": "trial", "n": _num(m.group(1))},
            f"at most {_num(m.group(1))} trial records cited")
    m = re.search(r"count of sources can go past \d+, up to (\d+)", t)
    if m:
        add("max_sources", {"n": int(m.group(1))}, f"at most {m.group(1)} distinct sources")
    m = re.search(r"This paper has (\d+) of them", t)
    if m:
        add("resource_count", {"resource": "mesh", "n": int(m.group(1))},
            f"{m.group(1)} distinct MeSH records cited")
    m = re.search(r"(\d+|six|five) MODY genes", t)
    if m:
        add("resource_count", {"resource": "gene", "n": _num(m.group(1))},
            f"{_num(m.group(1))} distinct gene records cited")

    # Outcomes.
    answered = None
    for am in re.finditer(r"cited answer|answer with cited records|\bstill answers\b|"
                          r"is answered every time|\bis answered\b(?! with a request)|"
                          r"are answered, not asked back|"
                          r"answers with real|Cited papers", t):
        if not re.search(r"\b(None|Neither|not)\s+$", t[max(0, am.start() - 9): am.start()]):
            answered = am
            break
    asked = re.search(r"asked back|One question back|asks the person to name|asks which|"
                      r"asks \"|asks rather than", t)
    if re.search(r"not asked back|is answered, not asked back|are answered, not asked back", t):
        add("not_asked_back", {}, "no question back")
        asked = None
    if asked and re.search(r"asked back first", t) and not b.bind:
        asked = None  # a precondition met by picking a choice, not the expectation
    if answered:
        add("answered", {}, "an answer with at least one citation, not a refusal or a "
            "question back")
    if asked:
        params: dict = {}
        m = re.search(r"asks \"([^\"]+)\" with (the [^.]+?)\. ", t + " ")
        if m:
            used.add(m.group(1))
            params = {"question": m.group(1),
                      "options": [o.strip() for o in re.split(r",| and ", m.group(2))
                                  if o.strip()]}
        m2 = re.search(r"which assembly, (GRCh\d+) or (GRCh\d+)", t)
        if m2:
            params["words"] = [m2.group(1), m2.group(2)]
        if re.search(r"questions to pick from|with choices", t):
            params["with_options"] = True
        add("asked_back", params, "the answer is a question back"
            + (f" reading \"{params['question']}\"" if params.get("question") else "")
            + (" offering " + "; ".join(params["options"]) if params.get("options") else "")
            + (" naming " + " and ".join(params["words"]) if params.get("words") else "")
            + (" with choices" if params.get("with_options") else ""))
    if re.search(r"refuses rather than making something up|\bis refused\b", t):
        add("refused_by_guard", {}, "the guardrail turns it away")
    if re.search(r"turned away with a message saying the capability does not exist", t):
        add("refused_compute", {}, "the guardrail turns it away as a compute request")
    if re.search(r"Each is accepted and searched", t):
        add("guard_passed", {}, "the guardrail lets it through")
    if re.search(r"No citation chips|No diseases listed|no invented data", t):
        add("zero_citations", {}, "no citation at all")
    if re.search(r"NCBI search link", t):
        add("fallback_link", {}, "the refusal carries an NCBI search link")
    if re.search(r"No answer appears from the stopped search", t):
        add("no_answer_after_stop", {}, "no answer text arrives after Stop")
    if re.search(r"source count and the text must match", t):
        add("saved_answer_matches", {}, "the saved answer's text and links equal the live "
            "answer's (the runner signs in and reads the history route)")

    # Links and records.
    kinds = [k for pat, k in RESOURCE_WORDS if re.search(pat, t)]
    if re.search(r"ncbi\.nlm\.nih\.gov|links? to (its|their|each|an?|the) |linking to|linked to|"
                 r"opens (an|that|its)|working link|outside NCBI|fetched from", t):
        add("hosts_pinned", {"resources": kinds},
            "every citation link is on NCBI, ClinicalTrials.gov or OMIM"
            + (", with the " + ", ".join(kinds) + " links on their own pages" if kinds else ""))
    if re.search(r"among the sources|are among|each cited|cited to|named and linked|"
                 r"Cited papers|with sources|appears among|is among|answers with real|"
                 r"answer with papers", t):
        negated = re.search(r"\b(No|no|never|Never)\b", t.split("among")[0][-30:])
        for k in kinds:
            add("resource_cited", {"resource": k}, f"at least one {k} record is cited")
        for acc_m in ACCESSION.finditer(t):
            acc = acc_m.group(1) or acc_m.group(2)
            add("id_absent" if negated else "id_cited", {"id": acc},
                f"no citation carries {acc}" if negated else f"a citation carries {acc}")
    m = re.search(r"No other gene's OMIM record, such as ([A-Z0-9]+)", t)
    if m:
        add("id_absent", {"id": m.group(1)}, f"{m.group(1)} is neither cited nor named")

    # Quoted phrases, placed by where the code base writes them.
    for quote, negated, example, qualified in _quotes(t):
        if quote in used or qualified or len(quote.split()) < 2:
            continue
        quote = quote.rstrip(",;")
        if example and not negated:
            continue
        if any(quote.lower() in (q or "").lower() for q in questions):
            continue  # the question's own words
        origin = sources.origin(quote) if sources else "none"
        if origin == "frontend":
            continue  # screen text: the bullet's residual class takes it
        if negated:
            add("text_lacks", {"phrase": quote, "regex": _pattern(quote)},
                f"the answer never says \"{quote}\"")
        elif origin == "backend":
            add("text_has", {"phrase": quote, "regex": _pattern(quote)},
                f"the answer says \"{quote}\"")
    return checks


def classify(entry: Entry, b: Bullet, sources: SourceIndex | None,
             headline: bool = False) -> None:
    """Decide the bullet's class and the exact checks it carries."""
    t = b.text
    turn_texts = {tt.text for c in entry.convs for tt in c.turns if tt.text}
    b.bind = [q for q in re.findall(r"`([^`]+)`", t) if q in turn_texts]
    if t.startswith(CONTEXT_PREFIXES):
        b.cls, b.reason = CONTEXT, "rationale, history or a known limitation"
        return
    if entry.removed:
        b.cls, b.reason = NOT_RUNNABLE, "the feature was removed: there is nothing to ask"
        return
    if DELEGATED.search(t):
        b.cls = EXACT
        b.checks = [Check("delegated", {"script": "integrations_smoke.py", "check": "mcp"},
                          "the integrations smoke script's mcp check: /mcp never redirects to "
                          "http://, and the printed config answers")]
        return
    for pattern, why in MISSING_STEP:
        if pattern.search(t):
            b.cls, b.reason = NOT_RUNNABLE, why
            return
    if NEEDS_NUMBER.search(t):
        b.cls, b.reason = NOT_RUNNABLE, ("a comparison with no number in its words; a number "
                                         "in the document would make it exact")
        return
    asks = bool(entry.convs)
    unanchored = any("names no question" in n for n in entry.notes)
    if asks and unanchored and re.search(r"^A short follow-up|follow-up inside", t):
        b.cls, b.reason = NOT_RUNNABLE, "the follow-up it describes has no named first question"
        return
    if asks and not t.startswith("If "):
        b.checks = recognise(entry, b, sources)
        _target(entry, b)
    if not b.checks and PERMISSIVE.search(" ".join(t.split()[:8])):
        b.cls, b.reason = CONTEXT, "a permission, not a requirement"
        return
    ui_hits = len(UI_MARKERS.findall(t))
    quoted_ui = [q for q, _n, ex, qual in _quotes(t) if q not in b.used and not qual and
                 len(q.split()) >= 2 and
                 not (ex and not _n) and sources and sources.origin(q) == "frontend"]
    residual: str | None
    if PERSON_MARKERS.search(t):
        residual, b.reason = PERSON, "perception or timing on screen"
    elif ui_hits >= 2 or (ui_hits == 1 and not b.checks) or not asks:
        residual, b.reason = SCREEN, "what the web app shows"
    elif quoted_ui:
        residual, b.reason = SCREEN, f"\"{quoted_ui[0]}\" is written by the web app"
    elif b.checks:
        residual = None
    elif headline:
        residual = _headline_class(entry, b)
        if residual == CONTEXT:
            b.cls, b.reason = CONTEXT, "the headline, restated by the exact checks below it"
            return
        b.reason = "the headline, judged in the channel most of its lines need"
    else:
        residual, b.reason = GRADED, "no script can decide these words; the model reads them"
    b.cls = residual or EXACT
    if b.cls in (SCREEN, GRADED) and (entry.sign_in_centric() or
                                      (b.cls == SCREEN and SIGN_IN_BULLET.search(t))):
        b.cls = NOT_RUNNABLE
        b.reason = "a signed-in screen: the capture has no sign-in step yet (verify SKILL.md)"


def _headline_class(entry: Entry, b: Bullet) -> str:
    """The headline goes where most of its entry's own lines go."""
    others = [x.cls for x in entry.bullets if x is not b and not x.section_wide and
              x.cls in CLASS_ORDER + [NOT_RUNNABLE]]
    if not others:
        return GRADED if entry.convs else SCREEN
    count = Counter(others)
    top = max(count.values())
    order = CLASS_ORDER + [NOT_RUNNABLE]
    best = max((c for c in count if count[c] == top), key=order.index)
    if best == EXACT:
        return CONTEXT
    return best


STOPWORDS = {
    "what", "which", "with", "about", "that", "this", "there", "their", "have", "from",
    "into", "does", "each", "answer", "answers", "answered", "question", "search", "asked",
    "refused", "records", "record", "show", "tell", "known", "they", "them", "then",
    "more", "most", "gene", "genes", "associated", "diseases", "disease", "isolates",
    "pathogen", "detection", "carry", "papers", "follow",
}


def _target(entry: Entry, b: Bullet) -> None:
    """Point each check at the answers the bullet speaks about."""
    t = b.text
    depth = None
    if re.match(r"^(At |In )?Plain language\b", t):
        depth = "plain_language"
    elif re.match(r"^(At |In )?Researcher\b", t):
        depth = "researcher"
    words = set(re.findall(r"[a-z0-9]{4,}", t.lower()))
    texts = list(dict.fromkeys(tt.text for cv in entry.convs for tt in cv.turns if tt.text))
    fresh = bool(re.search(r"fresh page|no earlier answer|fresh session", t))
    for c in b.checks:
        c.depth = depth
        c.fresh_only = fresh
        if c.target == "all":
            continue
        if b.section_wide:
            c.target = "every"
        elif b.bind:
            c.target = "turns:" + "|".join(b.bind)
        elif re.match(r"^(Both|All|Each|Neither|None)\b", t):
            c.target = "final"
        elif re.match(r"^The first (two|three)", t):
            n = NUMBER_WORDS[re.match(r"^The first (two|three)", t).group(1)]
            firsts = [cv.turns[0].text for cv in entry.convs if cv.turns[0].text]
            c.target = "turns:" + "|".join(list(dict.fromkeys(firsts))[:n])
        else:
            distinct = {x: set(re.findall(r"[a-z0-9]{4,}", x.lower())) - STOPWORDS
                        for x in texts}
            common = set.intersection(*distinct.values()) if distinct else set()
            hits = [x for x, ws in distinct.items() if (ws - common) & words]
            if hits and len(hits) < len(texts):
                c.target = "turns:" + "|".join(hits)
            elif re.search(r"follow-up|second answer", t):
                c.target = "follow"


# ------------------------------------------------------ the saved answer


@dataclass
class Run:
    source: str
    question: str | None
    depth: str | None
    events: list[dict]
    tokens: list[dict] | None
    citations: list[dict]
    answer_text: str
    guard: dict | None
    think: dict | None
    done: dict | None
    trust_signals: list[dict] | None
    tool_results: list[dict]
    seconds: float | None
    stopped: bool = False
    stop_seq: int | None = None

    def text_all(self) -> str:
        bits = [self.answer_text]
        if self.think and self.think.get("clarifying_question"):
            bits.append(self.think["clarifying_question"])
            bits += self.think.get("clarifying_options") or []
        if self.done and self.done.get("trust_line"):
            bits.append(self.done["trust_line"])
        for ts in self.trust_signals or []:
            if ts.get("message"):
                bits.append(ts["message"])
        return " ".join(bits)

    def prose(self) -> str:
        """What a reader reads as words: claims, notes, headings, list text and each
        table row's first cell. Identifier columns are left out."""
        if self.tokens is None:
            return self.answer_text
        out = []
        for tk in self.tokens:
            kind = tk.get("kind")
            if kind == "table_row":
                cells = tk.get("cells") or []
                out.append(cells[0] if cells else tk.get("text", ""))
            elif kind not in ("table_header", "paragraph_break"):
                out.append(tk.get("text", ""))
        return " ".join(out)

    def rows(self) -> list[dict]:
        return [tk for tk in self.tokens or [] if tk.get("kind") in ("table_row", "list_item")]

    def clarifying(self) -> str | None:
        return (self.think or {}).get("clarifying_question")


def _payload(e: dict) -> dict:
    p = e.get("payload")
    return p if isinstance(p, dict) else {}


def load_run(path: Path, index: int = 0) -> Run:
    """Normalise the saved shapes this repository has into one Run."""
    data = json.loads(path.read_text())
    if isinstance(data, list):  # 2026-09-24_no_hardcoding all.json: a list of runs
        data = data[index]
    if "tokens" in data and "events" not in data:  # the no-hardcoding shape
        toks = data.get("tokens") or []
        think = {"clarifying_question": data.get("clarifying_question"),
                 "clarifying_options": data.get("clarifying_options")}
        cites = [{"citation_id": c} if isinstance(c, str) else c
                 for c in data.get("citations") or []]
        return Run(source=str(path), question=data.get("question"), depth=data.get("depth"),
                   events=[], tokens=toks, citations=cites,
                   answer_text="".join(t.get("text", "") for t in toks), guard=None,
                   think=think, done={"trust_line": data.get("trust_line"),
                                      "trust_outcome": data.get("outcome")},
                   trust_signals=None, tool_results=[], seconds=None)
    events = data.get("events") or []
    norm = []
    for e in events:
        if not isinstance(e, dict):
            continue
        p = e.get("payload")
        if p is None and e.get("type") == "token":  # the answer-speed timeline keeps text only
            p = {"text": e.get("text") or "", "kind": None}
        norm.append({"type": e.get("type"), "payload": p if isinstance(p, dict) else {},
                     "seq": e.get("seq")})
    token_events = [e for e in norm if e["type"] == "token"]
    record = data.get("record") or {}
    full_tokens = bool(token_events) and (len(token_events) > 1 or not data.get("answer_text"))
    tokens = [e["payload"] for e in token_events] if full_tokens else None
    answer = data.get("answer_text") or "".join(p.get("text", "") for p in tokens or [])
    ts = [e["payload"] for e in norm if e["type"] == "trust_signal"]
    return Run(
        source=str(path),
        question=data.get("question") or record.get("question"),
        depth=record.get("audience_depth") or data.get("depth"),
        events=norm,
        tokens=tokens,
        citations=[e["payload"] for e in norm if e["type"] == "citation"],
        answer_text=answer,
        guard=next((e["payload"] for e in norm if e["type"] == "guard"), None),
        think=next((e["payload"] for e in norm if e["type"] == "think" and e["payload"]), None),
        done=next((e["payload"] for e in norm if e["type"] == "done"), None),
        trust_signals=ts or None,
        tool_results=[e["payload"] for e in norm if e["type"] == "tool_result"],
        seconds=data.get("seconds") or record.get("seconds"),
        stopped=bool(data.get("stopped")),
        stop_seq=data.get("stop_seq"),
    )


# ------------------------------------------------------------- the checks

PASS, FAIL, NA, SKIP = "PASS", "FAIL", "N/A", "SKIP"
TOKENS_NEEDED = {"count_matches_list", "no_structure", "has_structure", "rows_unique",
                 "max_mentions", "row_count", "rows_have_gene", "esbl_rows_not_only",
                 "paragraph_starts"}


def _urls(run: Run) -> list[str]:
    return [c.get("source_url") or "" for c in run.citations]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _is_answered(run: Run) -> bool:
    if run.guard and run.guard.get("passed") is False:
        return False
    if run.clarifying():
        return False
    return bool(run.citations) and (run.done or {}).get("trust_outcome") != "refuse"


def _has(run: Run, p: dict) -> bool:
    hay = run.text_all()
    return bool(re.search(p.get("regex") or re.escape(p["phrase"]), hay, re.IGNORECASE)) or \
        _norm(p["phrase"]) in _norm(hay)


def check_one(kind: str, p: dict, run: Run) -> tuple[str, str]:
    """One exact check on one saved answer."""
    if not run.events and not run.answer_text and not run.citations and not run.clarifying():
        return SKIP, "the saved file holds no events"
    if kind in TOKENS_NEEDED and run.tokens is None:
        return SKIP, "this saved run kept no answer tokens"
    if kind == "max_seconds":
        if run.seconds is None:
            return SKIP, "no seconds saved"
        return (PASS if run.seconds <= p["seconds"] else FAIL), \
            f"{run.seconds} s against {p['seconds']} s"
    if kind == "answered":
        return (PASS if _is_answered(run) else FAIL), (
            f"{len(run.citations)} citations, outcome {(run.done or {}).get('trust_outcome')}, "
            f"guard {(run.guard or {}).get('category')}, asked back: {bool(run.clarifying())}")
    if kind == "asked_back":
        q = run.clarifying()
        if not q:
            return FAIL, "no question back"
        opts = (run.think or {}).get("clarifying_options") or []
        if p.get("with_options") and not opts:
            return FAIL, f"asked \"{q[:80]}\" with no choices"
        for w in p.get("words", []):
            if w.lower() not in q.lower():
                return FAIL, f"the question back does not name {w}: \"{q[:100]}\""
        if p.get("question") and _norm(p["question"]) not in _norm(q):
            return FAIL, f"asked \"{q[:100]}\", not \"{p['question']}\""
        for o in p.get("options", []):
            if not any(_norm(o) in _norm(x) for x in opts):
                return FAIL, f"no choice reads \"{o}\" among {opts}"
        return PASS, f"asked \"{q[:100]}\" with {len(opts)} choices"
    if kind == "not_asked_back":
        q = run.clarifying()
        return (FAIL, f"asked back: \"{q[:100]}\"") if q else (PASS, "no question back")
    if kind in ("refused_by_guard", "refused_compute"):
        g = run.guard or {}
        ok = g.get("passed") is False and (kind == "refused_by_guard"
                                           or g.get("category") == "compute_request")
        return (PASS if ok else FAIL), f"guard passed={g.get('passed')} {g.get('category')}"
    if kind == "guard_passed":
        g = run.guard or {}
        if not g:
            return SKIP, "no guard event saved"
        return (PASS if g.get("passed") else FAIL), f"guard {g.get('category')}"
    if kind == "zero_citations":
        return (PASS if not run.citations else FAIL), f"{len(run.citations)} citations"
    if kind == "fallback_link":
        if run.trust_signals is None:
            return SKIP, "this saved run kept no trust signals"
        links = [ts["fallback_link"] for ts in run.trust_signals if ts.get("fallback_link")]
        ok = bool(links) and all(CITATION_HOST.match(x) for x in links)
        return (PASS if ok else FAIL), f"links: {links[:2]}"
    if kind == "trust_line_has":
        line = (run.done or {}).get("trust_line") or ""
        return (PASS if _norm(p["phrase"]) in _norm(line) else FAIL), f"trust line \"{line}\""
    if kind == "trust_line_shape":
        line = (run.done or {}).get("trust_line") or ""
        ok = any(re.search(s.replace("sources", "sources?"), line) for s in p["shapes"])
        return (PASS if ok else FAIL), f"trust line \"{line}\""
    if kind in ("if_lost_search_contains", "if_lost_search_trust"):
        if not any(tr.get("status") == "error" for tr in run.tool_results):
            return NA, "no background search failed on this run"
        hay = run.answer_text if kind == "if_lost_search_contains" else \
            (run.done or {}).get("trust_line") or ""
        ok = _norm(p["phrase"]) in _norm(hay)
        return (PASS if ok else FAIL), "a background search failed; " + (
            "the line is there" if ok else f"missing \"{p['phrase']}\"")
    if kind == "no_sentence_with_words":
        for s in _sentences(run.text_all()):
            if all(w in s.lower() for w in p["words"]):
                return FAIL, f"\"{s[:120]}\""
        return PASS, "no such sentence"
    if kind == "runs_past":
        m = re.search(re.escape(p["phrase"]) + r"(\S*)", run.answer_text)
        if not m:
            return FAIL, "the record text is not in the answer"
        ok = bool(re.match(r"[A-Za-z]", m.group(1))) and not m.group(1).endswith("…")
        return (PASS if ok else FAIL), f"continues \"{p['phrase'][-12:]}{m.group(1)[:20]}\""
    if kind == "count_matches_list":
        return _count_matches_list(run)
    if kind == "trust_count_matches_sources":
        line = (run.done or {}).get("trust_line") or ""
        m = re.search(r"Based on (\d+)", line)
        if not m:
            return NA, f"no \"Based on N\" line: \"{line}\""
        urls = {u for u in _urls(run) if u}
        if not urls and run.citations:
            return SKIP, "this saved run kept no citation links"
        return (PASS if int(m.group(1)) == len(urls) else FAIL), \
            f"\"{line}\" against {len(urls)} distinct links"
    if kind == "no_structure":
        bad = [tk.get("kind") for tk in run.tokens or [] if tk.get("kind") in
               ("heading", "list_item", "table_row")]
        return (PASS if not bad else FAIL), (f"{dict(Counter(bad))}" if bad else "none")
    if kind == "has_structure":
        kinds = Counter(tk.get("kind") for tk in run.tokens or [])
        ok = kinds["heading"] >= 1 and (kinds["list_item"] + kinds["table_row"]) >= 1
        return (PASS if ok else FAIL), str(dict(kinds))
    if kind == "layers_at_least":
        layers = {c.get("layer") for c in run.citations if c.get("layer")}
        return (PASS if len(layers) >= p["n"] else FAIL), f"layers {sorted(layers)}"
    if kind == "rows_unique":
        seen: Counter = Counter()
        cites = {c.get("citation_id"): c for c in run.citations}
        for r in run.rows():
            for mid in r.get("marker_ids") or []:
                seen[(cites.get(mid) or {}).get("source_url") or mid] += 1
        if not seen:
            seen = Counter(_norm((r.get("cells") or [r.get("text", "")])[0]) for r in run.rows())
        dup = [k for k, v in seen.items() if v > 1]
        return (PASS if not dup else FAIL), (f"listed twice: {dup[:3]}" if dup else
                                             f"{len(seen)} rows, each once")
    if kind == "max_mentions":
        count: Counter = Counter()
        cites = {c.get("citation_id"): c for c in run.citations}
        for tk in run.tokens or []:
            for mid in set(tk.get("marker_ids") or []):
                count[(cites.get(mid) or {}).get("source_url") or mid] += 1
        over = [(k, v) for k, v in count.items() if v > p["n"]]
        return (PASS if not over else FAIL), (f"cited in more than {p['n']} places: {over[:2]}"
                                              if over else "within the limit")
    if kind == "paragraph_starts":
        paras = [x.strip() for x in re.split(r"\n\s*\n", run.answer_text) if x.strip()]
        bad = [x[:60] for x in paras if x[0].islower() or x[0] in "\"'“”"]
        return (PASS if not bad else FAIL), (f"{bad[:2]}" if bad else f"{len(paras)} paragraphs")
    if kind == "no_sentence_opens":
        bad = [s[:80] for s in _sentences(run.answer_text)
               if any(s.strip().startswith(o) for o in p["openers"])]
        return (PASS if not bad else FAIL), (f"{bad[:2]}" if bad else "none")
    if kind == "no_shape":
        hits = re.findall(p["regex"], run.prose())
        return (PASS if not hits else FAIL), (f"found {hits[:3]}" if hits else "none")
    if kind == "names_present":
        missing = [n for n in p["names"] if not re.search(r"\b" + re.escape(n) + r"\b",
                                                          run.answer_text)]
        return (PASS if not missing else FAIL), (f"missing {missing}" if missing else "all named")
    if kind == "text_has":
        return (PASS, "present") if _has(run, p) else (FAIL, f"missing \"{p['phrase']}\"")
    if kind == "text_lacks":
        return (FAIL, f"says \"{p['phrase']}\"") if _has(run, p) else (PASS, "absent")
    if kind == "row_count":
        rows = [tk for tk in run.tokens or [] if tk.get("kind") == "table_row"]
        return (PASS if len(rows) == p["n"] else FAIL), f"{len(rows)} table rows against {p['n']}"
    if kind == "rows_have_gene":
        return _rows_have_gene(run, p)
    if kind == "esbl_rows_not_only":
        if not re.search(r"ESBL|extended-spectrum", run.question or "", re.IGNORECASE):
            return NA, "not an ESBL question"
        bad = []
        for r in run.rows():
            text = " ".join(r.get("cells") or []) + " " + r.get("text", "")
            if re.search(re.escape(p["gene"]) + r"(?![\d-])", text) and p["needs"] not in text:
                bad.append(text[:80])
        return (PASS if not bad else FAIL), (f"{bad[:2]}" if bad else "none")
    if kind == "if_truncated_says_at_least":
        cut = [tr for tr in run.tool_results if tr.get("tool") == "pathogen_detection" and
               tr.get("truncated")]
        if not cut:
            return NA, "the isolate scan was not cut off"
        ok = "at least" in run.answer_text.lower()
        return (PASS if ok else FAIL), ("says at least" if ok else "states a bare count")
    if kind in ("max_resource", "resource_count", "resource_cited"):
        if not run.citations:
            return FAIL, "no citations"
        if not any(_urls(run)):
            return SKIP, "this saved run kept no citation links"
        pat = RESOURCES[p["resource"]]
        hits = {u for u in _urls(run) if re.search(pat, u)}
        if p["resource"] == "gene_summary":
            hits = {c.get("source_url") for c in run.citations
                    if re.search(pat, c.get("source_url") or "") and c.get("field") == "summary"}
        if kind == "resource_cited":
            return (PASS if hits else FAIL), f"{len(hits)} {p['resource']} records"
        if kind == "max_resource":
            return (PASS if len(hits) <= p["n"] else FAIL), f"{len(hits)} against {p['n']}"
        return (PASS if len(hits) == p["n"] else FAIL), f"{len(hits)} against {p['n']}"
    if kind == "max_sources":
        n = len({u for u in _urls(run) if u})
        return (PASS if n <= p["n"] else FAIL), f"{n} distinct links"
    if kind in ("id_cited", "id_absent"):
        # Citations carry NCBI's numeric ids for SRA and assembly records, so the
        # accession a person reads is looked for in the cited sentence and the answer too.
        hay = " ".join(f"{c.get('source_id')} {c.get('source_url')} {c.get('entity_name')} "
                       f"{c.get('claim_text')}" for c in run.citations) + " " + run.answer_text
        found = p["id"].lower() in hay.lower()
        ok = found if kind == "id_cited" else not found
        return (PASS if ok else FAIL), f"{p['id']} {'found' if found else 'not found'}"
    if kind == "hosts_pinned":
        urls = [u for u in _urls(run) if u]
        if not urls:
            return (SKIP, "no citation links saved") if run.citations else (NA, "no citations")
        off = [u for u in urls if not CITATION_HOST.match(u)]
        if off:
            return FAIL, f"off-host: {off[:2]}"
        missing = [k for k in p["resources"] if not any(re.search(RESOURCES[k], u)
                                                        for u in urls)]
        if missing:
            return FAIL, f"no {', '.join(missing)} link among {len(urls)}"
        return PASS, f"{len(urls)} links on pinned hosts"
    if kind == "no_answer_after_stop":
        if not run.stopped:
            return SKIP, "this run was not stopped"
        after = [e for e in run.events if e["type"] == "token" and run.stop_seq is not None and
                 (e.get("seq") or 0) > run.stop_seq]
        return (PASS if not after else FAIL), f"{len(after)} text events after Stop"
    if kind in ("saved_answer_matches", "delegated"):
        return SKIP, "not run by this prototype"
    return SKIP, f"unknown check kind {kind}"


def _count_matches_list(run: Run) -> tuple[str, str]:
    toks = run.tokens or []
    first = next((tk for tk in toks if tk.get("kind") in ("claim", None) and tk.get("text")),
                 None)
    if not first:
        return NA, "no opening sentence"
    m = re.search(r"\b[Ff]ound (\d[\d,]*)\b", first.get("text", ""))
    if not m:
        return NA, f"the opening states no count: \"{first.get('text', '')[:80]}\""
    n = int(m.group(1).replace(",", ""))
    if not any(tk.get("marker_ids") for tk in toks):
        return SKIP, "this saved run kept no citation markers"
    markers = set(first.get("marker_ids") or [])
    rows = run.rows()
    anchor = next((r for r in rows if markers & set(r.get("marker_ids") or [])), None)
    if anchor is None:
        return FAIL, f"opens with {n} but no list row carries its citations"
    if anchor.get("kind") == "table_row":  # count the table the anchor sits in
        i = toks.index(anchor)
        start = end = i
        while start > 0 and toks[start - 1].get("kind") == "table_row":
            start -= 1
        while end + 1 < len(toks) and toks[end + 1].get("kind") == "table_row":
            end += 1
        shown = end - start + 1
    else:  # list items that share the anchor's label, such as "Disease name:"
        text = anchor.get("text", "")
        label = text.split(":")[0] + ":" if ":" in text else None
        shown = sum(1 for r in rows if label and r.get("text", "").startswith(label))
    return (PASS if shown == n else FAIL), f"opens with {n}, the list shows {shown}"


def _rows_have_gene(run: Run, p: dict) -> tuple[str, str]:
    rows = [tk for tk in run.tokens or [] if tk.get("kind") == "table_row"]
    if not rows:
        return NA, "no table rows"

    def matches(gene: str, prefix: str) -> bool:
        if p.get("exact_allele"):
            return gene == prefix or (gene.startswith(prefix)
                                      and not gene[len(prefix):len(prefix) + 1].isdigit())
        return gene.startswith(prefix)

    bad = []
    for r in rows:
        text = " ".join(r.get("cells") or []) + " " + r.get("text", "")
        genes = re.findall(r"\b(bla[\w-]+|mcr[\w.-]*)", text)
        if not any(matches(g, pref) for g in genes for pref in p["prefixes"]):
            bad.append(text[:80])
    return (PASS if not bad else FAIL), (f"{len(bad)} of {len(rows)} rows lack it: {bad[:1]}"
                                         if bad else f"all {len(rows)} rows")


def _targets(c: Check, entry: Entry) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    named = c.target[6:].split("|") if c.target.startswith("turns:") else []
    for conv in entry.convs:
        if c.depth and conv.depth != c.depth:
            continue
        if c.fresh_only and len([t for t in conv.turns if not t.auto_pick]) > 1:
            continue
        if named:
            idx = [i for i, t in enumerate(conv.turns) if t.text in named]
            if c.kind not in ("asked_back", "not_asked_back"):
                # a named question answered through a picked choice: check the pick
                idx = [i + 1 if i + 1 < len(conv.turns) and conv.turns[i + 1].auto_pick else i
                       for i in idx]
        elif c.target == "follow":
            idx = list(range(1, len(conv.turns))) if len(conv.turns) > 1 else []
        elif c.target == "every":
            idx = list(range(len(conv.turns)))
        else:
            idx = [len(conv.turns) - 1]
        if idx:
            out[conv.key()] = idx
    return out


def _run_for(runs: dict, conv: Conversation, rep: int, ti: int) -> Run | None:
    run = runs.get((conv.key(), rep, ti))
    if run is None and conv.turns[ti].auto_pick:  # answered outright: nothing was picked
        run = runs.get((conv.key(), rep, ti - 1))
    return run


def evaluate(entry: Entry, runs: dict[tuple[str, int, int], Run]) -> list[dict]:
    """Every exact check of an entry over its saved runs, one line per check, answer and
    repeat. `runs` maps (conversation key, repeat, turn index) to a saved Run."""
    lines = []
    for b in entry.bullets:
        for c in b.checks:
            if c.kind == "delegated":
                lines.append(_line(entry, b, c, 0, SKIP, "run by integrations_smoke.py (mcp)"))
                continue
            if c.target == "all":
                lines += [_line(entry, b, c, rep, v, d) for rep, v, d in _cross(c, entry, runs)]
                continue
            for conv in entry.convs:
                for ti in _targets(c, entry).get(conv.key(), []):
                    for rep in range(1, conv.repeats + 1):
                        run = _run_for(runs, conv, rep, ti)
                        asked = conv.turns[ti].text or "the picked choice"
                        if run is None:
                            lines.append(_line(entry, b, c, rep, SKIP, "not asked", asked))
                            continue
                        v, d = check_one(c.kind, c.params, run)
                        lines.append(_line(entry, b, c, rep, v, d, asked))
    return lines


def _cross(c: Check, entry: Entry, runs: dict) -> list[tuple[int, str, str]]:
    """Checks that compare answers to one question: across depths or across repeats."""
    by_q: dict[str, list[tuple[Conversation, Run]]] = {}
    for conv in entry.convs:
        last = len(conv.turns) - 1
        for rep in range(1, conv.repeats + 1):
            run = _run_for(runs, conv, rep, last)
            if run is not None:
                by_q.setdefault(conv.turns[0].text or "", []).append((conv, run))
    out = []
    for q, group in by_q.items():
        if len(group) < 2:
            continue
        if any(r.clarifying() for _c, r in group) and c.kind != "same_sources":
            out.append((1, NA, f"`{q}`: an answer asked back, so there is no text to compare"))
            continue
        if c.kind == "same_sources":
            sets = [frozenset(u for u in _urls(r) if u) for _c, r in group]
            ok = len(set(sets)) == 1
            out.append((1, PASS if ok else FAIL,
                        f"`{q}`: {len(group)} answers, {len(set(sets))} distinct link sets"))
        elif c.kind == "depths_differ":
            texts = {cv.depth: r.answer_text for cv, r in group}
            if len(texts) == 2:
                ok = len(set(texts.values())) == 2
                out.append((1, PASS if ok else FAIL,
                            f"`{q}`: the two depths {'differ' if ok else 'are identical'}"))
        elif c.kind == "researcher_longer":
            words = {cv.depth: len(r.answer_text.split()) for cv, r in group}
            if {"researcher", "plain_language"} <= set(words):
                ok = words["researcher"] > words["plain_language"]
                said = (f"`{q}`: researcher {words['researcher']} words, "
                        f"plain {words['plain_language']}")
                out.append((1, PASS if ok else FAIL, said))
    return out or [(1, SKIP, "fewer than two answers to compare")]


def _line(entry: Entry, b: Bullet, c: Check, rep: int, verdict: str, detail: str,
          asked: str | None = None) -> dict:
    return {"entry": entry.number, "check_id": b.key(entry.number) + ":" + c.kind,
            "bullet": b.text, "bullet_class": b.cls, "kind": c.kind, "says": c.says,
            "repeat": rep, "asked": asked, "verdict": verdict, "detail": str(detail)[:300]}


# ------------------------------------------------------------ the dry run


def summarise(entries: list[Entry]) -> dict:
    ent_classes = Counter(e.entry_class() for e in entries)
    check_classes = Counter(b.cls for e in entries for b in e.check_bullets())
    unique: dict[str, Conversation] = {}
    for e in entries:
        for c in e.convs:
            prev = unique.get(c.key())
            if prev is None or c.repeats > prev.repeats:
                unique[c.key()] = c
    asked = sum(len([t for t in c.turns if not t.auto_pick]) * c.repeats
                for c in unique.values())
    picks = sum(len([t for t in c.turns if t.auto_pick]) * c.repeats for c in unique.values())
    graded_entries = [e for e in entries if e.convs and any(b.cls == GRADED or b.checks
                                                            for b in e.bullets)]
    grader_in = grader_out = 0
    for e in graded_entries:
        turns = sum(len(c.turns) * c.repeats for c in e.convs)
        lines = [b for b in e.check_bullets() if b.cls in (GRADED, EXACT)]
        grader_in += (GRADER_PROMPT_TOKENS + sum(len(b.text) for b in lines) // CHARS_PER_TOKEN
                      + turns * (MEDIAN_ANSWER_CHARS // CHARS_PER_TOKEN
                                 + MEDIAN_CITATIONS * GRADER_TOKENS_PER_SOURCE_ROW))
        grader_out += 50 + GRADER_OUT_TOKENS_PER_BULLET * len(lines)
    grader_usd = grader_in / 1e6 * GRADER_USD_PER_M_IN + grader_out / 1e6 * GRADER_USD_PER_M_OUT
    questions = asked + picks
    return {
        "entries": len(entries),
        "entry_classes": dict(sorted(ent_classes.items())),
        "check_bullets": sum(check_classes.values()),
        "bullet_classes": dict(sorted(check_classes.items())),
        "context_bullets": sum(1 for e in entries for b in e.bullets if b.cls == CONTEXT),
        "exact_checks": sum(len(b.checks) for e in entries for b in e.bullets),
        "non_exact_bullets_carrying_exact_checks": sum(
            1 for e in entries for b in e.bullets if b.checks and b.cls != EXACT),
        "entries_asking_questions": sum(1 for e in entries if e.convs),
        "unique_conversations": len(unique),
        "questions_per_pass_at_most": questions,
        "of_which_conditional_picks": picks,
        "questions_before_sharing": sum(e.asks_per_pass() for e in entries),
        "question_usd_per_pass": round(questions * COST_PER_QUESTION_USD, 2),
        "minutes_per_pass_two_workers": round(
            questions * (MEDIAN_SECONDS + PAUSE_BETWEEN_RUNS_S) / WORKERS / 60, 1),
        "entries_with_screen_lines": sum(1 for e in entries if any(b.cls == SCREEN
                                                                    for b in e.bullets)),
        "screen_entries_that_ask_a_question": sum(1 for e in entries if e.convs and any(
            b.cls == SCREEN for b in e.bullets)),
        "screen_capture_questions_both_widths": sum(
            2 * len({c.turns[0].text for c in e.convs}) for e in entries
            if e.convs and any(b.cls == SCREEN for b in e.bullets)),
        "entries_with_person_lines": sum(1 for e in entries if any(b.cls == PERSON
                                                                    for b in e.bullets)),
        "entries_with_not_runnable_lines": sum(1 for e in entries if any(
            b.cls == NOT_RUNNABLE for b in e.bullets)),
        "grader_calls_per_pass": len(graded_entries),
        "grader_tokens_in_per_pass": grader_in,
        "grader_tokens_out_per_pass": grader_out,
        "grader_usd_per_pass": round(grader_usd, 2),
        "accounts_for_three_passes_at_90_a_day": -(-questions * 3 // 90),
    }


def print_dry_run(entries: list[Entry]) -> None:
    for e in entries:
        per = Counter(b.cls for b in e.check_bullets())
        print(f"\n=== {e.number}. {e.title}")
        print(f"    class: {e.entry_class()}   lines: "
              + ", ".join(f"{k} {v}" for k, v in sorted(per.items())))
        for c in e.convs:
            print(f"    ask: {c.label()}")
        for n in e.notes:
            print(f"    note: {n}")
        if any(b.cls == SCREEN for b in e.bullets):
            spec = VERIFY_SPECS / f"q{e.number}.json"
            print(f"    /verify spec: {spec.relative_to(REPO_ROOT)}"
                  f" ({'present' if spec.exists() else 'not written yet'})")
        for b in e.bullets:
            tag = b.cls + (" (section)" if b.section_wide else "")
            print(f"    - [{tag}] {b.text[:110]}")
            for c in b.checks:
                where = "" if c.target == "final" else f" [on {c.target[:70]}]"
                depth = f" [{c.depth} only]" if c.depth else ""
                print(f"        check {c.kind}: {c.says}{where}{depth}")
            if b.reason and b.cls != EXACT:
                print(f"        why: {b.reason}")
    print("\n=== summary")
    for k, v in summarise(entries).items():
        print(f"{k}: {v}")


def print_markdown(entries: list[Entry]) -> None:
    print("| Entry | Feature | Class | Exact | Graded | Screen | Person | Not runnable "
          "| Exact checks | Questions a pass | Why a line is not runnable |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for e in entries:
        per = Counter(b.cls for b in e.check_bullets())
        reasons = sorted({re.split(r" \(|;", b.reason)[0] for b in e.check_bullets()
                          if b.cls == NOT_RUNNABLE})
        if any("names no question" in n for n in e.notes):
            reasons.append("a follow-up names no first question")
        title = re.sub(r"\s*\([^)]*\)\s*$", "", e.title).replace("|", "/")
        n_checks = sum(len(b.checks) for b in e.bullets)
        print(f"| {e.number} | {title} | {e.entry_class()} | {per[EXACT]} | {per[GRADED]} "
              f"| {per[SCREEN]} | {per[PERSON]} | {per[NOT_RUNNABLE]} | {n_checks} "
              f"| {e.asks_per_pass()} | {'; '.join(reasons)} |")


# ---------------------------------------------------------- the live runner


def _http(base: str, path: str, body: dict | None, bearer: str | None = None,
          timeout: int = 60, method: str = "POST") -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if bearer:
        req.add_header("Authorization", "Bearer " + bearer)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def _stream(base: str, run_id: str, bearer: str, deadline: float,
            stop_at: float | None) -> tuple[list[dict], bool, int | None]:
    req = urllib.request.Request(base + f"/v1/query/{run_id}/events")
    req.add_header("Accept", "text/event-stream")
    req.add_header("Authorization", "Bearer " + bearer)
    out: list[dict] = []
    timed_out = False
    stop_seq = None
    try:
        with urllib.request.urlopen(req, timeout=STREAM_LINE_TIMEOUT_S) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").rstrip("\n")
                if line.startswith("data:"):
                    try:
                        out.append(json.loads(line[5:].strip()))
                    except json.JSONDecodeError:
                        pass
                if stop_at is not None and stop_seq is None and time.time() >= stop_at:
                    try:
                        _http(base, f"/v1/query/{run_id}/stop", None, bearer, timeout=20)
                    except (urllib.error.URLError, TimeoutError):
                        pass
                    stop_seq = max((e.get("seq") or 0 for e in out), default=0)
                if time.time() > deadline:
                    timed_out = True
                    break
    except TimeoutError:
        timed_out = True
    return out, timed_out, stop_seq


def ask_conversation(base: str, account: dict, conv: Conversation, rep: int,
                     out_dir: Path) -> list[dict]:
    """Ask every turn of one conversation in one session; save each turn's events whole."""
    records: list[dict] = []
    session_id = "tq-" + uuid.uuid4().hex[:12]
    previous: Run | None = None
    for ti, turn in enumerate(conv.turns):
        text = turn.text
        if text is None:
            if turn.auto_pick and not (previous and previous.clarifying()):
                break  # answered outright: nothing to pick
            opts = ((previous.think or {}).get("clarifying_options") or []) if previous else []
            text = next((o for o in opts if turn.pick == "first" or
                         _norm(turn.pick or "") in _norm(o)), None)
            if text is None:
                records.append({"conv": conv.key(), "repeat": rep, "turn": ti,
                                "outcome": "pick_not_offered", "offered": opts})
                break
        bearer = _http(base, "/auth/login", account)["access_token"]
        t0 = time.time()
        try:
            created = _http(base, "/v1/query", {"text": text, "session_id": session_id,
                                                "audience_depth": conv.depth}, bearer)
        except urllib.error.HTTPError as exc:
            records.append({"conv": conv.key(), "repeat": rep, "turn": ti, "question": text,
                            "outcome": f"http_{exc.code}"})
            break
        stop_at = t0 + STOP_AFTER_S if conv.stop else None
        events, timed_out, stop_seq = _stream(base, created["run_id"], bearer,
                                              t0 + RUN_DEADLINE_S, stop_at)
        seconds = round(time.time() - t0, 1)
        answer = "".join(_payload(e).get("text", "") for e in events if e.get("type") == "token")
        raw_path = out_dir / "raw" / f"{conv.key()}_r{rep}_t{ti}.json"
        raw_path.write_text(json.dumps(
            {"record": {"question": text, "audience_depth": conv.depth, "seconds": seconds,
                        "conv": conv.key(), "repeat": rep, "turn": ti,
                        "session_id": session_id, "timed_out": timed_out},
             "question": text, "seconds": seconds, "events": events, "answer_text": answer,
             "stopped": conv.stop, "stop_seq": stop_seq}, indent=1))
        previous = load_run(raw_path)
        rate = sum(1 for tr in previous.tool_results
                   if "rate" in (tr.get("summary") or "").lower()
                   and "pool" in (tr.get("summary") or "").lower())
        records.append({"conv": conv.key(), "repeat": rep, "turn": ti, "question": text,
                        "depth": conv.depth, "seconds": seconds, "timed_out": timed_out,
                        "citations": len(previous.citations), "rate_limit_signals": rate,
                        "asked_back": bool(previous.clarifying())})
        time.sleep(PAUSE_BETWEEN_RUNS_S)
    return records


def run_live(entries: list[Entry], args: argparse.Namespace) -> int:
    base = args.api.rstrip("/")
    if not re.match(r"^https://|^http://(127\.0\.0\.1|localhost)[:/]", base + "/"):
        print("--api must be https:// or loopback", file=sys.stderr)
        return 2
    try:
        health = _http(base, "/health", None, method="GET", timeout=20)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"the API did not answer /health: {exc}", file=sys.stderr)
        return 2
    if args.expect_env and health.get("app_env") != args.expect_env:
        print(f"/health reports app_env {health.get('app_env')!r}, not {args.expect_env!r}",
              file=sys.stderr)
        return 2
    accounts = json.loads(Path(args.accounts).read_text())
    out_dir = Path(args.out)
    (out_dir / "raw").mkdir(parents=True, exist_ok=True)
    unique: dict[str, Conversation] = {}
    for e in entries:
        for c in e.convs:
            if c.key() not in unique or c.repeats > unique[c.key()].repeats:
                unique[c.key()] = c
    jobs = [(c, rep) for c in unique.values() for rep in range(1, c.repeats + 1)
            if not (out_dir / "raw" / f"{c.key()}_r{rep}_t0.json").exists()]
    lock = threading.Lock()

    def worker(i: int) -> None:
        for conv, rep in jobs[i::WORKERS]:
            recs = ask_conversation(base, accounts[i % len(accounts)], conv, rep, out_dir)
            with lock, (out_dir / "runs.jsonl").open("a") as f:
                for r in recs:
                    f.write(json.dumps(r) + "\n")
                    print(json.dumps(r)[:200], flush=True)

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(WORKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    runs: dict[tuple[str, int, int], Run] = {}
    for p in (out_dir / "raw").glob("*.json"):
        m = re.match(r"^(.+)_r(\d+)_t(\d+)\.json$", p.name)
        if m:
            runs[(m.group(1), int(m.group(2)), int(m.group(3)))] = load_run(p)
    return write_results(entries, runs, out_dir, health)


def write_results(entries: list[Entry], runs: dict, out_dir: Path, health: dict) -> int:
    lines = [ln for e in entries for ln in evaluate(e, runs)]
    (out_dir / "results.json").write_text(json.dumps(
        {"at": datetime.now(UTC).isoformat(timespec="seconds"), "health": health,
         "document_sha": hashlib.sha1(DOC.read_bytes()).hexdigest()[:12], "lines": lines},
        indent=1))
    tally = Counter(ln["verdict"] for ln in lines)
    not_run = Counter(b.cls for e in entries for b in e.check_bullets() if b.cls != EXACT)
    with (out_dir / "report.md").open("w") as f:
        f.write("# Test queries gate, exact checks\n\n")
        f.write(f"Verdicts: {dict(tally)}. Lines not run by this prototype: "
                f"{dict(not_run)}.\n\n")
        for ln in sorted(lines, key=lambda x: (x["verdict"] != FAIL, x["entry"])):
            f.write(f"- {ln['verdict']} | {ln['entry']} | {ln['kind']} | {ln['detail']} | "
                    f"{(ln['asked'] or '')[:60]}\n")
    print(f"verdicts: {dict(tally)}")
    return 1 if tally[FAIL] else 0


# ------------------------------------------------------------- the replay


def replay(entries: list[Entry], specs: list[str]) -> int:
    """Apply one entry's exact checks to saved answers, in the entry's ask order."""
    by_no = {e.number: e for e in entries}
    fails = 0
    for spec in specs:
        no, _, files = spec.partition("=")
        e = by_no[int(no)]
        runs: dict[tuple[str, int, int], Run] = {}
        slots = [(c, rep, ti) for c in e.convs for rep in range(1, c.repeats + 1)
                 for ti in range(len(c.turns)) if not c.turns[ti].auto_pick]
        loaded: list[tuple[Run, bool]] = []  # (run, may fall back to ask order)
        for path in [f for f in files.split(",") if f]:
            f, _, idx = path.partition("#")
            if idx == "*":  # a list file: only runs whose question this entry asks
                count = len(json.loads(Path(f).read_text()))
                loaded += [(load_run(Path(f), i), False) for i in range(count)]
            else:
                loaded.append((load_run(Path(f), int(idx or 0)), True))
        free = list(slots)
        for run, fallback in loaded:
            same_q = [sl for sl in free if _norm(sl[0].turns[sl[2]].text or "") ==
                      _norm(run.question or "")]
            slot = next((sl for sl in same_q if sl[0].depth == run.depth), None) or \
                (same_q[0] if same_q else None)
            if slot is None and fallback and free and not any(
                    _norm(sl[0].turns[sl[2]].text or "") == _norm(run.question or "")
                    for sl in slots):
                slot = free[0]
            if slot is not None:
                free.remove(slot)
                runs[(slot[0].key(), slot[1], slot[2])] = run
        print(f"\n=== {e.number}. {e.title}")
        for ln in evaluate(e, runs):
            if ln["detail"] == "not asked":
                continue
            print(f"  {ln['verdict']:4} {ln['kind']:27} r{ln['repeat']} "
                  f"{(ln['asked'] or '')[:34]!r:38} {ln['detail'][:110]}")
            fails += ln["verdict"] == FAIL
    return 1 if fails else 0


# ----------------------------------------------------------- the self-test


def _fixture(**kw: object) -> Run:
    base = {"source": "fixture", "question": "q", "depth": "plain_language",
            "events": [{"type": "done", "payload": {}, "seq": 1}], "tokens": [],
            "citations": [], "answer_text": "", "guard": {"passed": True, "category": "ok"},
            "think": None, "done": {"trust_outcome": "answer", "trust_line": "Based on 1 source"},
            "trust_signals": [], "tool_results": [], "seconds": 20.0}
    base.update(kw)
    return Run(**base)  # type: ignore[arg-type]


def self_test() -> int:
    """Every case is one check that must PASS on a good answer and FAIL on a bad one."""
    good = {"citation_id": "a", "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
            "source_id": "NCBIGene:672", "field": "summary", "layer": "layer_2_api"}
    off_host = {"citation_id": "b", "source_url": "https://example.org/x", "source_id": "x"}
    other = dict(good, source_url="https://www.ncbi.nlm.nih.gov/gene/675")
    rows = [{"kind": "claim", "text": "Found 2 disease records: A [1] and B [2]. ",
             "marker_ids": ["m1", "m2"]},
            {"kind": "table_row", "text": "A [1]", "cells": ["A", "MedGen:C1"],
             "marker_ids": ["m1"]},
            {"kind": "table_row", "text": "B [2]", "cells": ["B", "MedGen:C2"],
             "marker_ids": ["m2"]}]
    three = [dict(rows[0], text="Found 3 disease records: A [1] and B [2]. ")] + rows[1:]
    medgen = _shape("MedGen:C0346153")
    cases = [
        ("max_seconds", {"seconds": 90}, _fixture(seconds=30.0), _fixture(seconds=120.0)),
        ("hosts_pinned", {"resources": []}, _fixture(citations=[good]),
         _fixture(citations=[good, off_host])),
        ("resource_cited", {"resource": "gene_summary"}, _fixture(citations=[good]),
         _fixture(citations=[dict(good, field="name")])),
        ("no_shape", {"regex": medgen}, _fixture(tokens=rows),
         _fixture(tokens=[{"kind": "claim", "text": "MedGen:C0346153 is linked."}])),
        ("count_matches_list", {}, _fixture(tokens=rows), _fixture(tokens=three)),
        ("answered", {}, _fixture(citations=[good]), _fixture(citations=[])),
        ("asked_back", {"words": ["GRCh38", "GRCh37"]},
         _fixture(think={"clarifying_question": "Which assembly, GRCh38 or GRCh37?"}),
         _fixture(think={"clarifying_question": "Which gene do you mean?"})),
        ("text_lacks", {"phrase": "has a source URL of"}, _fixture(answer_text="BRCA1."),
         _fixture(answer_text="BRCA1 has a source URL of x.")),
        ("trust_count_matches_sources", {}, _fixture(citations=[good]),
         _fixture(citations=[good, other])),
        ("rows_have_gene", {"prefixes": ["blaCTX-M-15"], "exact_allele": True},
         _fixture(tokens=[{"kind": "table_row", "cells": ["x", "blaCTX-M-15, blaTEM-1"]}]),
         _fixture(tokens=[{"kind": "table_row", "cells": ["x", "blaCTX-M-155"]}])),
        ("refused_by_guard", {}, _fixture(guard={"passed": False, "category": "off_topic"}),
         _fixture()),
        ("runs_past", {"phrase": "and through the C-terminal d"},
         _fixture(answer_text="binds DNA and through the C-terminal domain it acts."),
         _fixture(answer_text="binds DNA and through the C-terminal d…")),
        ("layers_at_least", {"n": 2},
         _fixture(citations=[good, dict(off_host, layer="layer_3_enrichment")]),
         _fixture(citations=[good, other])),
    ]
    failed = total = 0
    for kind, params, ok_run, bad_run in cases:
        for run, want in ((ok_run, PASS), (bad_run, FAIL)):
            got, detail = check_one(kind, params, run)
            total += 1
            failed += got != want
            print(f"{'ok ' if got == want else 'BAD'} {kind:28} want {want:4} got {got:4} "
                  f"{detail[:60]}")
    entries = parse_document(DOC.read_text(), None)
    ok = len(entries) > 0 and all(e.number for e in entries)
    total += 1
    failed += not ok
    print(f"{'ok ' if ok else 'BAD'} the document parses into {len(entries)} entries")
    print(f"self-test: {total - failed} of {total} passed")
    return 1 if failed else 0


# ------------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--doc", default=str(DOC))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--summary-json", action="store_true")
    ap.add_argument("--replay", action="append", default=[])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--entries", default="", help="comma-separated entry numbers")
    ap.add_argument("--api", help="the API origin to ask, https:// or loopback")
    ap.add_argument("--expect-env", default="develop", help="the /health app_env to require")
    ap.add_argument("--accounts", help="JSON list of sign-in bodies; never committed")
    ap.add_argument("--out", help="output folder")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    entries = parse_document(Path(args.doc).read_text(), SourceIndex())
    if args.entries:
        wanted = {int(x) for x in args.entries.split(",")}
        entries = [e for e in entries if e.number in wanted]
    if args.replay:
        return replay(entries, args.replay)
    if args.markdown:
        print_markdown(entries)
        return 0
    if args.summary_json:
        print(json.dumps(summarise(entries), indent=1))
        return 0
    if args.dry_run:
        print_dry_run(entries)
        return 0
    if not (args.api and args.accounts and args.out):
        print("a live run needs --api, --accounts and --out, or pass --dry-run", file=sys.stderr)
        return 2
    return run_live(entries, args)


if __name__ == "__main__":
    sys.exit(main())
