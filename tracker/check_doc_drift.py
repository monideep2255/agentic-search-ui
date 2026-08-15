#!/usr/bin/env python3
"""Check tracked documentation for drifted facts and recurring structural defects.

This repository's docs drifted because the same fact (a test count, a
decision count, a phase status, a PR number) gets written into many files
and kept in sync by discipline alone. The one file pair with a mechanical
sync behind it, CLAUDE.md and AGENTS.md, is the only pair that did not
drift. This script is the mechanism for everything else: it computes each
tracked fact from source, then scans every tracked markdown file for a
stale copy of it, plus a handful of structural defects that caused the
same cleanup this script follows.

THE HISTORICAL-VERSUS-CURRENT RULE

A number in a document is only stale if it is being asserted as CURRENT. A
number that quotes a past state, an example of an error, or an unrelated
count is not a finding even when it differs from the freshly computed
value. This script tells the two apart with the following rule, applied to
every regex match before it is reported:

A matched number is treated as HISTORICAL, and skipped, when any one of
these holds:

  1. Dated record row. The line is a data row of a dated table or a dated
     bullet: it matches `^\\|\\s*\\d{4}-\\d{2}-\\d{2}\\s*\\|` (a DECISIONS.md or
     LEARNINGS.md row) or `^-\\s*\\d{4}-\\d{2}-\\d{2}\\b` (a Plan.md Revision
     history bullet). A count attached to a past date is a record of what
     was true then, not a claim about now.
  2. Historical section. The nearest preceding heading (any line starting
     with `#`) contains a literal date, or the word "retrospective",
     "session", or the phrase "revision history" (case-insensitive). These
     headings mark an entire section as a past snapshot, for example a
     tracker phase file's dated review-round sections or Plan.md's
     "## Revision history".
  3. Hedge or correction cue near the number, not merely on the line. A
     word within 50 characters of the matched number marks it as an
     example of an error rather than a live claim: "was", "wrong", "stale",
     "outdated", "incorrect", "previously", "used to", "prior to",
     "superseded", "corrected", "instead of", "as measured", "as of", or
     "at the" (the last catches "N at the 2026-08-01 merge"). The window is
     deliberate: this repo often puts a full paragraph inside one markdown
     table cell (one line), so a whole-line hedge check would let an
     unrelated "was" fifty words away exempt a live number it has nothing
     to do with. That is not hypothetical: CLAUDE.md's Priority-2 row
     states a current test count in the same line as "the cause WAS a
     composition defect", a genuinely historical clause about a different
     topic entirely. A per-line check missed the exact fact this script
     exists to catch; a windowed check does not.

A number that survives all three checks is a CURRENT assertion. If the
number it captures differs from the freshly computed canonical value, it
is reported as stale.

Deliberately absent from this rule: a generic scan for "any number that
differs from a known fact". Every fact-assertion regex below is anchored
to the specific phrasing this repository actually uses for that fact (for
example `\\d+ Python tests`, `\\d+ decisions logged`), never a bare number.
This is what keeps a line number, a port, a version, or a dollar figure
out of the findings without needing a fourth exemption rule for
"unrelated numbers": an unrelated number simply never matches an anchored
pattern in the first place.

THE FALSE-NEGATIVE TRADE-OFF

Every rule above is written to exempt generously. A check that cries wolf
on legitimate historical text gets disabled, which loses all of its
detection value; a check that misses one drifted sentence loses only that
one instance. When a borderline case comes up, this script exempts it.

WHAT THIS SCRIPT DOES NOT CHECK

A green run here is evidence about the specific facts and defects listed
below, not a certification that the documentation is correct. Per this
repo's own `goal-contracts` rule, a verify surface has to state its own
coverage, or a clean run reads as "everything is verified" when it means
"the things this script happens to compute are correct".

  - It verifies FACTS, not prose. Only the numeric and structural items
    this script actually computes (test counts, DECISIONS.md/LEARNINGS.md
    row counts, open flags, build-phase status, merged PR per phase, TOC
    structure, duplicate phase headings, Last-updated currency) are
    checked. A narrative claim, an architectural description, or a "why"
    explanation can be entirely wrong and this script will not notice,
    because it never reads for meaning, only for the specific anchored
    patterns above.
  - It never checks the two locked documents, `requirements/PRD.md` and
    `requirements/Technical_specification.md`. Both are frozen until the
    Step 6.2 reconciliation and are allowed to disagree with the live
    system on purpose (the technical specification's "10 concept labels"
    against the live graph's 11 is the recorded case). Flagging them would
    produce a finding nobody may act on.
  - It cannot detect a fact that is MISSING entirely, only one that is
    PRESENT and wrong. A document that used to state the Python test count
    and had the whole sentence deleted reports no finding here, because
    there is no assertion left to compare against the computed value. This
    script proves "no document states a stale copy of this fact"; it does
    not prove "every document that should mention this fact still does".
  - Every fact pattern is PHRASING-SPECIFIC, not meaning-specific. A fact
    written in a phrasing no pattern below covers is invisible to this
    script, full stop; it is not a lesser-confidence finding, it is no
    finding at all. The measured case: `requirements/phase_6/
    Continuation_prompt.md` stated "Learnings entries: 37, plus a
    retrospective" (label-then-number, colon separator) while every
    `learnings_entries` pattern was anchored number-first ("36 learnings
    plus a retrospective"). The script computed the correct value (36) and
    still reported 0 stale findings, because the number-first anchor never
    matched a label-first sentence. Both orderings are covered now (see
    `ASSERTION_PATTERNS` and `PREMISE_GATE_RE`), across the separators this
    repo actually uses (colon, markdown table pipe, equals sign, en dash,
    em dash, and a bulleted "Label - value" hyphen), but the fix is a
    widened set of anchors, not a general-purpose fact detector. Adding a
    new way of stating a tracked count in a document (a new label, a new
    separator, a new surrounding phrase) requires adding a matching pattern
    here, or that new phrasing is exactly as invisible as the case above
    was. `frontend_test_files` (the vitest "Test Files" count) is computed
    but has NO assertion pattern at all today, deliberately: no live
    document currently states it as a current total outside dated per-
    ticket build logs, so no real phrasing exists yet to anchor a pattern
    to. The moment a document does assert it live, it is unchecked until a
    pattern is added. `merged_prs` is the mirror case already documented at
    `PHASE_THEN_PR_RE`: it matches only "phase X.Y ... PR #N", not the
    reverse order, by design, because no reverse-ordered phrasing exists in
    this repo today. Same rule, same risk, if that ever changes.

Depends on:
    - tracker/BOARD.md (parsed for build-phase statuses and the Open flags
      table, via tracker/render_board.py's own parser)
    - tracker/render_board.py (`parse_board`, `BoardError`; reused rather
      than re-implemented so the two scripts never disagree about what
      BOARD.md says)
    - DECISIONS.md, LEARNINGS.md (row and entry counts, counted directly)
    - tests/system_03_search_agent/tools/test_cypher_query_premise.py
      (premise gate test count, via `pytest --collect-only`)
    - frontend/e2e/*.spec.ts (Playwright test count, counted directly)
    - venv/bin/python (to run pytest; SKIPPED if absent)
    - frontend/node_modules (to run vitest; SKIPPED if absent)
    - git log --merges (merged PR numbers per phase branch)
    - git ls-files '*.md' (the set of tracked markdown files to scan)

Reads:
    Runs `pytest --collect-only -q` and `npx vitest run` as read-only
    measurement subprocesses. Neither mutates repository or test state.

Writes:
    Nothing. Stdout only. This script never edits a file.

Usage:
    python3 tracker/check_doc_drift.py            print a full report
    python3 tracker/check_doc_drift.py --check     exit 0 clean / 1 on any
                                                    finding, one line per
                                                    finding
    python3 tracker/check_doc_drift.py --verbose   also print every
                                                    computed fact and how
                                                    it was computed
    python3 tracker/check_doc_drift.py --self-test run two fixture suites:
                                                    the historical-versus-
                                                    current classifier, and
                                                    pattern coverage (every
                                                    fact's ASSERTION_PATTERNS
                                                    against both a number-
                                                    then-label and a label-
                                                    then-number phrasing);
                                                    exit 0 only if every case
                                                    in both suites passes.
                                                    Does not touch source
                                                    facts, pytest, vitest, or
                                                    git.

Exits non-zero when a stale fact or a structural defect is found, or when
BOARD.md itself is malformed, because a drift checker that silently misses
a case is worse than one that says so.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
VENV_PYTHON = REPO_ROOT / "venv" / "bin" / "python"
FRONTEND_DIR = REPO_ROOT / "frontend"
E2E_DIR = FRONTEND_DIR / "e2e"
DECISIONS_MD = REPO_ROOT / "DECISIONS.md"
LEARNINGS_MD = REPO_ROOT / "LEARNINGS.md"
BOARD_MD = ROOT / "BOARD.md"
PREMISE_GATE_TEST = Path(
    "tests/system_03_search_agent/tools/test_cypher_query_premise.py"
)

sys.path.insert(0, str(ROOT))
import render_board  # noqa: E402  (reused so BOARD.md is parsed one way)

# Locked documents, frozen until Step 6.2 and allowed to disagree with the
# live system on purpose. See the module docstring's "WHAT THIS SCRIPT DOES
# NOT CHECK" section.
SKIP_FILES = {
    "requirements/PRD.md",
    "requirements/Technical_specification.md",
}

PYTEST_TIMEOUT_S = 180
VITEST_TIMEOUT_S = 240
GIT_TIMEOUT_S = 30

WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def word_or_digit(token: str) -> int:
    token = token.strip()
    if token.replace(",", "").isdigit():
        return int(token.replace(",", ""))
    return WORD_NUMBERS[token.lower()]


def digits(token: str) -> int:
    return int(token.replace(",", ""))


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


@dataclass
class Fact:
    key: str
    label: str
    value: object          # int | dict | None (None only when skipped)
    display: str
    source: str
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class Finding:
    kind: str               # "stale" | "structural"
    path: str
    line: int
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


@dataclass
class AssertionPattern:
    fact_key: str
    regex: re.Pattern
    parser: Callable[[str], int] = digits


# --------------------------------------------------------------------------
# Fact computation
# --------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _pytest_collected_count(target: str | None) -> tuple[int | None, str]:
    """Run `pytest --collect-only -q` (optionally scoped to one file) and
    parse the trailing "N tests collected" line. Returns (count, reason);
    count is None and reason explains why when it could not be measured.
    """
    if not VENV_PYTHON.exists():
        return None, f"{VENV_PYTHON.relative_to(REPO_ROOT)} not found"
    cmd = [str(VENV_PYTHON), "-m", "pytest", "--collect-only", "-q"]
    if target:
        cmd.append(target)
    proc = _run(cmd, cwd=REPO_ROOT, timeout=PYTEST_TIMEOUT_S)
    if proc is None:
        return None, "pytest invocation failed or timed out"
    combined = proc.stdout + "\n" + proc.stderr
    m = re.search(r"^(\d+)\s+tests? collected", combined, re.MULTILINE)
    if not m:
        return None, "could not parse a 'N tests collected' line from pytest output"
    return int(m.group(1)), ""


def compute_python_test_count() -> Fact:
    source = "python -m pytest --collect-only -q (repo venv, repo root)"
    count, reason = _pytest_collected_count(None)
    if count is None:
        return Fact("python_tests", "Python tests", None, "SKIPPED", source, True, reason)
    return Fact("python_tests", "Python tests", count, str(count), source)


def compute_premise_gate_count() -> Fact:
    source = f"python -m pytest --collect-only -q {PREMISE_GATE_TEST}"
    if not (REPO_ROOT / PREMISE_GATE_TEST).exists():
        return Fact(
            "premise_gate_tests", "Premise gate tests", None, "SKIPPED", source,
            True, f"{PREMISE_GATE_TEST} not found",
        )
    count, reason = _pytest_collected_count(str(PREMISE_GATE_TEST))
    if count is None:
        return Fact("premise_gate_tests", "Premise gate tests", None, "SKIPPED", source, True, reason)
    return Fact("premise_gate_tests", "Premise gate tests", count, str(count), source)


def compute_frontend_test_counts() -> tuple[Fact, Fact]:
    source = "npx vitest run --reporter=verbose (frontend/)"
    if not (FRONTEND_DIR / "node_modules").exists():
        reason = "frontend/node_modules not found"
        return (
            Fact("frontend_tests", "Frontend tests", None, "SKIPPED", source, True, reason),
            Fact("frontend_test_files", "Frontend test files", None, "SKIPPED", source, True, reason),
        )
    proc = _run(
        ["npx", "vitest", "run", "--reporter=verbose"],
        cwd=FRONTEND_DIR, timeout=VITEST_TIMEOUT_S,
    )
    if proc is None:
        reason = "vitest invocation failed or timed out"
        return (
            Fact("frontend_tests", "Frontend tests", None, "SKIPPED", source, True, reason),
            Fact("frontend_test_files", "Frontend test files", None, "SKIPPED", source, True, reason),
        )
    combined = proc.stdout + "\n" + proc.stderr
    m_tests = re.search(r"Tests\s+(\d+)\s+passed", combined)
    m_files = re.search(r"Test Files\s+(\d+)\s+passed", combined)
    if not m_tests or not m_files:
        reason = "could not parse 'Tests N passed' / 'Test Files N passed' from vitest output"
        return (
            Fact("frontend_tests", "Frontend tests", None, "SKIPPED", source, True, reason),
            Fact("frontend_test_files", "Frontend test files", None, "SKIPPED", source, True, reason),
        )
    n_tests, n_files = int(m_tests.group(1)), int(m_files.group(1))
    return (
        Fact("frontend_tests", "Frontend tests", n_tests, str(n_tests), source),
        Fact("frontend_test_files", "Frontend test files", n_files, str(n_files), source),
    )


def compute_playwright_test_count() -> Fact:
    source = "count of top-level test(...) calls in frontend/e2e/*.spec.ts"
    if not E2E_DIR.exists():
        return Fact(
            "playwright_tests", "Playwright end-to-end tests", None, "SKIPPED",
            source, True, f"{E2E_DIR.relative_to(REPO_ROOT)} not found",
        )
    test_call_re = re.compile(r"^\s*test\(\s*['\"]")
    count = 0
    for spec in sorted(E2E_DIR.glob("*.spec.ts")):
        text = spec.read_text(encoding="utf-8")
        count += sum(1 for line in text.splitlines() if test_call_re.match(line))
    return Fact("playwright_tests", "Playwright end-to-end tests", count, str(count), source)


def _dated_row_count(path: Path) -> int:
    row_re = re.compile(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|")
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if row_re.match(line))


def compute_decisions_row_count() -> Fact:
    source = f"count of dated table rows in {DECISIONS_MD.relative_to(REPO_ROOT)}"
    if not DECISIONS_MD.exists():
        return Fact("decisions_rows", "DECISIONS.md rows", None, "SKIPPED", source, True, "file not found")
    count = _dated_row_count(DECISIONS_MD)
    return Fact("decisions_rows", "DECISIONS.md rows", count, str(count), source)


def compute_learnings_entry_count() -> Fact:
    source = f"count of dated table rows in {LEARNINGS_MD.relative_to(REPO_ROOT)}"
    if not LEARNINGS_MD.exists():
        return Fact("learnings_entries", "LEARNINGS.md entries", None, "SKIPPED", source, True, "file not found")
    text = LEARNINGS_MD.read_text(encoding="utf-8")
    count = _dated_row_count(LEARNINGS_MD)
    retro_count = len(re.findall(r"^## Retrospective", text, re.MULTILINE))
    display = f"{count}" + (f" (plus {retro_count} retrospective section{'s' if retro_count != 1 else ''})" if retro_count else "")
    return Fact("learnings_entries", "LEARNINGS.md entries", count, display, source)


def compute_open_flags_count() -> Fact:
    source = "tracker/render_board.py's parser, '## Open flags' table"
    if not BOARD_MD.exists():
        return Fact("open_flags", "Open flags on tracker/BOARD.md", None, "SKIPPED", source, True, "BOARD.md not found")
    try:
        data = render_board.parse_board(BOARD_MD.read_text(encoding="utf-8"))
    except render_board.BoardError as exc:
        return Fact("open_flags", "Open flags on tracker/BOARD.md", None, "SKIPPED", source, True, f"malformed board: {exc}")
    count = len(data["open_flags"])
    return Fact("open_flags", "Open flags on tracker/BOARD.md", count, str(count), source)


def compute_build_phase_statuses() -> Fact:
    source = "tracker/render_board.py's parser, '## Build phases' table"
    if not BOARD_MD.exists():
        return Fact("build_phase_statuses", "Build phase statuses", None, "SKIPPED", source, True, "BOARD.md not found")
    try:
        data = render_board.parse_board(BOARD_MD.read_text(encoding="utf-8"))
    except render_board.BoardError as exc:
        return Fact("build_phase_statuses", "Build phase statuses", None, "SKIPPED", source, True, f"malformed board: {exc}")
    statuses = {p.id: p.status for p in data["phases"]}
    display = ", ".join(f"{k}={v}" for k, v in sorted(statuses.items()))
    return Fact("build_phase_statuses", "Build phase statuses", statuses, display, source)


def compute_phase_branches() -> dict[str, str]:
    """phase id -> its declared branch name, straight from BOARD.md's own
    Branch column. Used to disambiguate merged_prs below: this repo's `main`
    was created from `agentic-search-data-engineering` as a structural
    template (DECISIONS.md row 1) and its git history carries that sibling
    repo's own old `phase/N.M-description` merges, e.g. `phase/3.0-age-loader`
    for a completely different "phase 3.0". Matching on phase NUMBER alone
    collides with those; matching on the full declared branch STRING does not,
    since the two repos' phase branches share numbers but never descriptions.
    """
    if not BOARD_MD.exists():
        return {}
    lines = BOARD_MD.read_text(encoding="utf-8").splitlines()
    try:
        rows = render_board.find_table(lines, "## Build phases")
    except render_board.BoardError:
        return {}
    branches: dict[str, str] = {}
    for cells in rows:
        if len(cells) != 10:
            continue
        pid, branch = cells[0], cells[1]
        if pid and branch:
            branches[pid] = branch
    return branches


def compute_merged_pr_numbers() -> Fact:
    """Merged PR number per phase, taking the max across TWO branch shapes.

    A phase's declared BOARD.md branch (`phase/N.M-description`) covers the
    normal case. It misses a phase that needed a SECOND branch to fully
    close: build phase 3.1 merged as PR #22 from `phase/3.1-ncbi-efetch`,
    then its re-review debt closed separately as PR #23 from
    `fix/3.1-rereview-round1-critical-regressions`, a branch name
    `board_branches` has never heard of. `git-workflow.md`'s own naming
    convention for exactly this case is `fix/N.M-description`, phase-id
    prefixed, so it is matched directly by phase id here rather than by a
    declared branch string, and unioned with the declared-branch PR, taking
    the max of whichever fired. Found live 2026-08-08 checkpointing build
    phase 3.2, when this fact reported PR #22 for phase 3.1 while every
    other document in the repo, correctly, says PR #23.
    """
    source = (
        "git log --merges --pretty=format:%s, matched against BOARD.md's "
        "declared branch name per phase (not phase number alone, see "
        "compute_phase_branches's docstring), UNIONED with any "
        "fix/N.M-description branch matched directly by phase id"
    )
    proc = _run(
        ["git", "log", "--merges", "--pretty=format:%s"],
        cwd=REPO_ROOT, timeout=GIT_TIMEOUT_S,
    )
    if proc is None or proc.returncode != 0:
        reason = (proc.stderr.strip() if proc else "git log invocation failed or timed out") or "git log exited non-zero"
        return Fact("merged_prs", "Merged PR numbers per phase", None, "SKIPPED", source, True, reason)

    board_branches = compute_phase_branches()
    if not board_branches:
        return Fact(
            "merged_prs", "Merged PR numbers per phase", None, "SKIPPED", source,
            True, "could not read BOARD.md's Build phases branch column",
        )

    phase_pattern = re.compile(r"Merge pull request #(\d+) from \S+/(phase/\S+)")
    fix_pattern = re.compile(r"Merge pull request #(\d+) from \S+/fix/(\d+\.\d+)-\S+")
    pr_by_branch: dict[str, int] = {}
    pr_by_fix_phase: dict[str, int] = {}
    for line in proc.stdout.splitlines():
        m = phase_pattern.search(line)
        if m:
            pr, branch = int(m.group(1)), m.group(2)
            pr_by_branch[branch] = max(pr, pr_by_branch.get(branch, 0))
            continue
        m = fix_pattern.search(line)
        if m:
            pr, phase_id = int(m.group(1)), m.group(2)
            pr_by_fix_phase[phase_id] = max(pr, pr_by_fix_phase.get(phase_id, 0))

    by_phase: dict[str, int] = {}
    for phase_id, branch in board_branches.items():
        candidates = [pr_by_branch[branch]] if branch in pr_by_branch else []
        if phase_id in pr_by_fix_phase:
            candidates.append(pr_by_fix_phase[phase_id])
        if candidates:
            by_phase[phase_id] = max(candidates)
    display = ", ".join(f"{p}=#{pr}" for p, pr in sorted(by_phase.items())) or "(none found)"
    return Fact("merged_prs", "Merged PR numbers per phase", by_phase, display, source)


def compute_all_facts() -> dict[str, Fact]:
    facts: dict[str, Fact] = {}
    facts["python_tests"] = compute_python_test_count()
    facts["premise_gate_tests"] = compute_premise_gate_count()
    frontend_tests, frontend_files = compute_frontend_test_counts()
    facts["frontend_tests"] = frontend_tests
    facts["frontend_test_files"] = frontend_files
    facts["playwright_tests"] = compute_playwright_test_count()
    facts["decisions_rows"] = compute_decisions_row_count()
    facts["learnings_entries"] = compute_learnings_entry_count()
    facts["open_flags"] = compute_open_flags_count()
    facts["build_phase_statuses"] = compute_build_phase_statuses()
    facts["merged_prs"] = compute_merged_pr_numbers()
    return facts


# --------------------------------------------------------------------------
# Historical-versus-current exemption (see module docstring for the rule)
# --------------------------------------------------------------------------

DATED_TABLE_ROW_RE = re.compile(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|")
DATED_BULLET_RE = re.compile(r"^-\s*\d{4}-\d{2}-\d{2}\b")
HISTORICAL_HEADING_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}|retrospective|revision history|\bsession\b",
    re.IGNORECASE,
)
HEDGE_WORD_RE = re.compile(
    r"\b(was|wrong|stale|outdated|incorrect|previously|used to|prior to|"
    r"superseded|corrected|instead of|as measured|as of|at the|then)\b",
    re.IGNORECASE,
)


# A fourth, whole-FILE exemption, on top of the three line-level ones in the
# module docstring. `.claude/rules/writing-style.md`'s "File naming
# conventions" section names these exact filename shapes as dated capture
# files (a planning session, a meeting), and that same rule file's prose-wall
# guidance plus `.claude/rules/preserve-your-thinking.md`'s "Clarify before
# drafting substantial documents" section both already treat "meeting notes
# and session notes" as capture rather than a living document. (Those three
# topics used to live in standalone files, `file-naming.md`, `no-prose-
# walls.md`, and `clarify-before-drafting.md`; they were merged into
# `writing-style.md` and `preserve-your-thinking.md` respectively and the
# standalone files deleted.) A number inside one of these files is what that
# session reported at the time, never a claim about the document's current
# state.
# Real case this caught: `requirements/phase_1/Session_May_07.md` says
# "5 decisions logged to DECISIONS.md from Step 1.3", a per-step delta from
# 2026-05-07, which a line-level check alone still matched as a current
# 5-row claim because its heading text carries no date, "session", or
# "retrospective" token.
HISTORICAL_FILENAME_RES = [
    re.compile(r"^Session_[A-Za-z]+_\d{1,2}\.md$"),          # phase_N/Session_July_21.md
    re.compile(r"^\d{4}-\d{2}-\d{2}_.*\.md$"),                # meetings/2026-07-21_....md
    re.compile(r"^[A-Za-z]+_\d{1,2}\.md$"),                    # meetings/January_06.md
]


def is_historical_file(rel_path: str) -> bool:
    path = Path(rel_path)
    under_dated_dir = "meetings" in path.parts or any(p.startswith("phase_") for p in path.parts)
    if not under_dated_dir:
        return False
    return any(pattern.match(path.name) for pattern in HISTORICAL_FILENAME_RES)


FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})")


def fenced_line_mask(lines: list[str]) -> list[bool]:
    """Return a same-length list where True means the line sits inside (or
    is a delimiter of) a fenced code block, ``` or ~~~, including a fence
    with an info string (```markdown) and an unclosed fence, where per
    CommonMark everything after the opening delimiter to end of file is
    code.

    A template block shown to the reader (`.claude/skills/eval-harness/
    SKILL.md`'s ```markdown fence around an example `## Component: [name]`
    heading is the real case) is not a section of the document. Markdown
    renderers do not treat a `#`-line inside a fence as a heading, a
    fact-assertion regex should not treat a number inside one as a live
    claim, and neither should this script.

    Per CommonMark, a closing fence is a line consisting of the SAME
    character as the opener, repeated at least as many times as the
    opener, with nothing else on the line (an info string is only legal on
    the opening line). `set(stripped) <= {fence_char}` enforces the "nothing
    else" part; a line that starts with enough fence characters but also
    carries other content does not close the fence.
    """
    mask = [False] * len(lines)
    in_fence = False
    fence_char = ""
    fence_len = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not in_fence:
            m = FENCE_OPEN_RE.match(stripped)
            if m:
                in_fence = True
                fence_char = m.group(1)[0]
                fence_len = len(m.group(1))
                mask[i] = True
            continue
        mask[i] = True
        if (
            len(stripped) >= fence_len
            and stripped[:fence_len] == fence_char * fence_len
            and set(stripped) <= {fence_char}
        ):
            in_fence = False
    return mask


def heading_index(lines: list[str], mask: list[bool] | None = None) -> list[tuple[int, str]]:
    """(line index, heading text) for every `#`-prefixed line, skipping any
    line the fence mask marks as code so an example heading inside a fenced
    block is never mistaken for a real section.
    """
    return [
        (i, line.lstrip("#").strip())
        for i, line in enumerate(lines)
        if line.startswith("#") and not (mask and mask[i])
    ]


def is_historical_context(lines: list[str], idx: int, headings: list[tuple[int, str]]) -> bool:
    """Rules 1 and 2 of the historical-versus-current rule: the whole-line and
    whole-section exemptions. Rule 3 (a hedge word) is deliberately NOT here;
    see `has_nearby_hedge` below for why it has to be scoped per match
    instead of per line.
    """
    stripped = lines[idx].strip()
    if DATED_TABLE_ROW_RE.match(stripped) or DATED_BULLET_RE.match(stripped):
        return True
    current_heading = ""
    for h_idx, h_text in headings:
        if h_idx <= idx:
            current_heading = h_text
        else:
            break
    if current_heading and HISTORICAL_HEADING_RE.search(current_heading):
        return True
    return False


def has_nearby_hedge(line: str, start: int, end: int, window: int = 50) -> bool:
    """Rule 3, scoped to a character window around one matched number.

    This has to be per-match, not per-line, because this repo routinely
    puts an entire paragraph inside one markdown table cell, one line. A
    real, measured case: CLAUDE.md's Priority-2 row states a current test
    count ("968 Python tests", the exact fact this script exists to catch)
    in the same line as "the cause WAS a composition defect", a genuinely
    historical clause describing build phase 2.1's root cause, hundreds of
    characters away. A whole-line hedge check reads that "was" and exempts
    the test count too, silently defeating the primary case this script was
    built for. A window keeps the hedge word tied to the number it is
    actually hedging, as in "968 AT THE 2026-08-01 merge", where the hedge
    sits right next to the number it qualifies.
    """
    lo = max(0, start - window)
    hi = min(len(line), end + window)
    return bool(HEDGE_WORD_RE.search(line[lo:hi]))


# --------------------------------------------------------------------------
# Fact-assertion patterns, anchored to phrasing this repo actually uses.
# Anchoring to fact-specific phrasing (rather than a bare number) is what
# keeps line numbers, ports, versions, and dollar figures out of scope
# without a fourth exemption rule; see the module docstring.
#
# ORDERING: every fact below is stated in this repo BOTH number-first
# ("977 Python tests") and label-first ("Python tests: 977"). A pattern
# anchored to only one ordering misses the other silently, a green run with
# a stale document underneath it: `requirements/phase_6/
# Continuation_prompt.md` stated "Learnings entries: 37, plus a
# retrospective" against a computed value of 36, and every prior
# `learnings_entries` pattern was number-first only, so the drift was
# invisible. Each fact below therefore carries at least one number-then-
# label pattern AND at least one label-then-number pattern.
#
# SEPARATORS: `LABEL_NUM_SEP` covers the separators this repo actually uses
# between a label and its number: a colon ("Python tests: 977"), a markdown
# table cell pipe ("| Python tests | 977 |", where the separator is the
# pipe plus surrounding spaces), an equals sign ("Python tests = 977"), and
# a bulleted "Label - value" hyphen or en/em dash ("Decisions logged - 183",
# "Decisions logged – 183"), the same spaced-hyphen bullet form
# `writing-style.md` allows for "Label - description" bullets and table
# cells. It intentionally does NOT allow a separator-free "Python tests
# 977": without a separator character, that shape is indistinguishable from
# incidental adjacent text and would reintroduce the "any number near this
# label" false-positive risk the module docstring's opening section already
# rejects for the number-first patterns.
# --------------------------------------------------------------------------

LABEL_NUM_SEP = r"\s*[:|=–—-]\s*"


def _label_then_number(label_pattern: str) -> re.Pattern:
    """Build a label-then-number AssertionPattern regex: `label_pattern`,
    then one separator from `LABEL_NUM_SEP`, then the captured number.
    `label_pattern` is inserted as-is (already `\\b`-bounded by the caller),
    so this only assembles the shared separator-and-number tail once rather
    than repeating it at every call site.
    """
    return re.compile(label_pattern + LABEL_NUM_SEP + r"(\d[\d,]*)\b", re.IGNORECASE)


ASSERTION_PATTERNS: list[AssertionPattern] = [
    # Python tests. Number-then-label: "977 Python tests". Label-then-
    # number: "Python tests: 977", "Python tests | 977", "Python tests =
    # 977", "Python tests - 977".
    AssertionPattern("python_tests", re.compile(r"(\d[\d,]*)\s+Python tests\b")),
    AssertionPattern("python_tests", _label_then_number(r"\bPython tests\b")),

    # Frontend tests. Number-then-label: "120 frontend tests" / "120
    # frontend unit tests". Label-then-number: "Frontend tests: 120".
    AssertionPattern("frontend_tests", re.compile(r"(\d[\d,]*)\s+frontend (?:unit )?tests\b", re.IGNORECASE)),
    AssertionPattern("frontend_tests", _label_then_number(r"\bfrontend (?:unit )?tests\b")),

    # Playwright end-to-end tests. Number-then-label: "3 Playwright tests" /
    # "3 Playwright end-to-end tests". Label-then-number: "Playwright end-
    # to-end tests: 3".
    AssertionPattern("playwright_tests", re.compile(r"(\d[\d,]*)\s+Playwright(?:\s+end-to-end)?\s+tests\b", re.IGNORECASE)),
    AssertionPattern("playwright_tests", _label_then_number(r"\bPlaywright(?:\s+end-to-end)?\s+tests\b")),

    # DECISIONS.md row count. Requires one of the repo's three anchor
    # phrasings, never a bare "N decisions": the first number-then-label
    # variant also requires the "(DECISIONS.md)" suffix, matching the
    # repo's own total-count phrasing ("183 decisions logged
    # (DECISIONS.md)"), specifically to avoid matching a per-step delta
    # like "5 decisions logged to DECISIONS.md from Step 1.3", which is a
    # historical count for one planning step, not a current claim about the
    # file's total row count. The label-then-number forms below ("Decisions
    # logged: 183") are a self-contained total-count assertion by
    # construction, so they need no matching suffix requirement.
    AssertionPattern("decisions_rows", re.compile(r"(\d[\d,]*)\s+decisions logged\s*\(DECISIONS\.md\)")),
    AssertionPattern("decisions_rows", re.compile(r"(\d[\d,]*)\s+decision rows\b")),
    AssertionPattern("decisions_rows", re.compile(r"(\d[\d,]*)\s+DECISIONS\.md rows\b")),
    AssertionPattern("decisions_rows", _label_then_number(r"\bDecisions logged\b")),
    AssertionPattern("decisions_rows", _label_then_number(r"\bDecision rows\b")),
    AssertionPattern("decisions_rows", _label_then_number(r"\bDECISIONS\.md rows\b")),

    # LEARNINGS.md entry count. Same shape as DECISIONS.md rows above. The
    # label-then-number form is the one that missed the real regression:
    # "Learnings entries: 37, plus a retrospective" against a computed 36.
    AssertionPattern("learnings_entries", re.compile(r"(\d[\d,]*)\s+learnings\s+plus\s+(?:a|the)\s+retrospective\b")),
    AssertionPattern("learnings_entries", re.compile(r"(\d[\d,]*)\s+learnings entries\b")),
    AssertionPattern("learnings_entries", re.compile(r"(\d[\d,]*)\s+LEARNINGS\.md entries\b")),
    AssertionPattern("learnings_entries", _label_then_number(r"\bLearnings entries\b")),
    AssertionPattern("learnings_entries", _label_then_number(r"\bLEARNINGS\.md entries\b")),

    # Open flags. Both digit and word-number forms, both orderings.
    AssertionPattern(
        "open_flags",
        re.compile(r"(\d[\d,]*|one|two|three|four|five|six|seven|eight|nine|ten)\s+open flags?\b", re.IGNORECASE),
        parser=word_or_digit,
    ),
    AssertionPattern(
        "open_flags",
        re.compile(
            r"\bopen flags?\b" + LABEL_NUM_SEP
            + r"(\d[\d,]*|one|two|three|four|five|six|seven|eight|nine|ten)\b",
            re.IGNORECASE,
        ),
        parser=word_or_digit,
    ),
]

# Premise gate: "premise gate 9 of 9" (bare), "premise gate at 9 of 9", and
# now "Premise gate: 9 of 9" / "Premise gate | 9 of 9" / "Premise gate = 9
# of 9" / "Premise gate - 9 of 9" (the label-then-number forms, one
# `LABEL_NUM_SEP` separator in place of the space-or-" at" join). The real
# case this widened for: `requirements/phase_6/Continuation_prompt.md`
# states "Premise gate: 9 of 9", which the previous space-or-"at"-only
# pattern never matched.
PREMISE_GATE_RE = re.compile(
    r"premise gate(?:\s*[:|=–—-]|\s+at)?\s+(\d+)\s+of\s+(\d+)\b",
    re.IGNORECASE,
)

# Directional by design: "phase X.Y (..., PR #N)" is the phrasing this repo
# uses everywhere it was found (CLAUDE.md, AGENTS.md). The reverse order is
# not scanned for; see the module docstring's "WHAT THIS SCRIPT DOES NOT
# CHECK" section, which names this as the same class of ordering gap the
# fact-assertion patterns above were widened for, left as-is here because no
# reverse-ordered phrasing exists in this repo today.
#
# The window excludes both "." and "|": "." keeps the pairing inside one
# sentence, and "|" keeps it inside one markdown table cell. Without the
# pipe exclusion, a table row like "| 2.0 | ...replacing the phase 1.0
# stub... | PR #9 |" pairs "phase 1.0" (a mention in 2.0's own cell) with
# PR #9 (2.0's PR, a different table cell entirely) and reports a false
# mismatch against phase 1.0's real PR.
PHASE_THEN_PR_RE = re.compile(r"\bphase\s+(\d+\.\d+)\b[^.\n|]{0,120}?\bPR\s*#(\d+)\b", re.IGNORECASE)


# --------------------------------------------------------------------------
# File discovery
# --------------------------------------------------------------------------


def tracked_markdown_files() -> list[Path]:
    proc = _run(["git", "ls-files", "*.md"], cwd=REPO_ROOT, timeout=GIT_TIMEOUT_S)
    if proc is None or proc.returncode != 0:
        return []
    paths = []
    for rel in proc.stdout.splitlines():
        rel = rel.strip()
        if not rel or rel in SKIP_FILES:
            continue
        paths.append(REPO_ROOT / rel)
    return paths


# --------------------------------------------------------------------------
# Stale-fact scan
# --------------------------------------------------------------------------


def scan_stale_facts(files: list[Path], facts: dict[str, Fact]) -> list[Finding]:
    findings: list[Finding] = []
    premise_fact = facts.get("premise_gate_tests")
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if is_historical_file(rel):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        mask = fenced_line_mask(lines)
        headings = heading_index(lines, mask)

        for i, line in enumerate(lines):
            if mask[i] or is_historical_context(lines, i, headings):
                continue

            for ap in ASSERTION_PATTERNS:
                fact = facts.get(ap.fact_key)
                if fact is None or fact.skipped:
                    continue
                for m in ap.regex.finditer(line):
                    if has_nearby_hedge(line, m.start(), m.end()):
                        continue
                    try:
                        asserted = ap.parser(m.group(1))
                    except (KeyError, ValueError):
                        continue
                    if asserted != fact.value:
                        findings.append(Finding(
                            "stale", rel, i + 1,
                            f"says {asserted} {fact.label.lower()} (computed: {fact.value})",
                        ))

            if premise_fact is not None and not premise_fact.skipped:
                for m in PREMISE_GATE_RE.finditer(line):
                    if has_nearby_hedge(line, m.start(), m.end()):
                        continue
                    num, den = int(m.group(1)), int(m.group(2))
                    if num != premise_fact.value or den != premise_fact.value:
                        findings.append(Finding(
                            "stale", rel, i + 1,
                            f"says premise gate {num} of {den} "
                            f"(computed: {premise_fact.value} of {premise_fact.value})",
                        ))
    return findings


def scan_pr_assertions(files: list[Path], facts: dict[str, Fact]) -> list[Finding]:
    findings: list[Finding] = []
    merged_prs_fact = facts.get("merged_prs")
    if merged_prs_fact is None or merged_prs_fact.skipped:
        return findings
    merged_prs: dict[str, int] = merged_prs_fact.value  # type: ignore[assignment]

    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if is_historical_file(rel):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        mask = fenced_line_mask(lines)
        headings = heading_index(lines, mask)

        for i, line in enumerate(lines):
            if mask[i] or is_historical_context(lines, i, headings):
                continue
            for m in PHASE_THEN_PR_RE.finditer(line):
                if has_nearby_hedge(line, m.start(), m.end()):
                    continue
                phase, pr = m.group(1), int(m.group(2))
                expected = merged_prs.get(phase)
                if expected is not None and pr != expected:
                    findings.append(Finding(
                        "stale", rel, i + 1,
                        f"says build phase {phase} merged as PR #{pr} (computed: PR #{expected})",
                    ))
    return findings


# --------------------------------------------------------------------------
# Structural checks
# --------------------------------------------------------------------------


def slugify(heading_text: str) -> str:
    """Approximate GitHub's heading-to-anchor slug algorithm.

    Lowercase, strip everything but word characters/spaces/hyphens, then map
    each remaining space to a hyphen ONE FOR ONE, without collapsing runs.
    That last part matters and is easy to get wrong: GitHub does not
    collapse consecutive hyphens, so a heading like "System 1 + 2" (the "+"
    removed, leaving two adjacent spaces) slugs to "system-1--2" with a
    double hyphen, not "system-1-2". Collapsing would silently disagree with
    a correct, existing table of contents on every heading that contains a
    stripped character bordered by spaces on both sides.

    Good enough for the plain ASCII headings this repo uses; an inline code
    span or emoji in a heading can still throw it off, which is a known
    limitation, not a defect to silently work around.
    """
    text = heading_text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\t\r\n]+", " ", text).strip()
    return text.replace(" ", "-")


def dedupe_slugs(slugs: list[str]) -> list[str]:
    """Apply GitHub's duplicate-anchor suffix: the second heading that slugs
    to the same text becomes `-1`, the third `-2`, and so on. Two headings
    with the same text is a real, supported pattern in this repo (multiple
    "What is next" subsections in a session log), and without this the slug
    of the second occurrence collides with the first and never matches a
    correctly authored TOC link, which always carries the suffix.
    """
    seen: dict[str, int] = {}
    result = []
    for slug in slugs:
        if slug in seen:
            seen[slug] += 1
            result.append(f"{slug}-{seen[slug]}")
        else:
            seen[slug] = 0
            result.append(slug)
    return result


# Files whose body is one long append-only table, and the cells that must
# carry a `<details>` dropdown in every dated row. Both facts are load-bearing
# for a reader: DECISIONS.md's `Why` is a median of 538 characters and
# LEARNINGS.md's last two cells are the bulk of an entry, so an unwrapped
# append does not merely look different, it stops the table being scannable.
# A dated table row in either append-only file. LEARNINGS.md has one row dated
# as a RANGE ("2026-08-10/11"), so the day part is matched loosely on purpose.
DATED_ROW_RE = re.compile(r"^\| \d{4}-\d{2}-\d{2}")


def split_unescaped_pipes(row: str) -> list[str]:
    """Split a markdown table row into cells, respecting escaped pipes.

    Four DECISIONS.md rows contain a literal `\|` inside a cell. Splitting on
    every pipe shreds those rows and would make this check report phantom
    column-count errors on content that is perfectly correct.
    """
    parts = re.split(r"(?<!\\)\|", row)
    if parts and parts[0].strip() == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return parts


COLLAPSIBLE_TABLES = {
    "DECISIONS.md": {"header": "| Date | Decision |", "wrapped": ["Why"]},
    "LEARNINGS.md": {"header": "| Date | Applies to |", "wrapped": ["What was tried", "What fixed it"]},
}


def check_append_only_table(rel: str, lines: list[str], mask: list[bool]) -> list[Finding]:
    """Guard the two append-only tables against the two ways they actually broke.

    Both failures happened on 2026-08-14 and neither was caught by anything:

    1. A BLANK LINE inside the table. Markdown ends a table at the first blank
       line, so DECISIONS.md rendered 39 of its 311 rows and the remaining 273
       became loose text. The source still contained every row and every
       dropdown, so every source-level check passed. The product owner found it
       by looking at the rendered page.

    2. A row MISSING its `<details>` wrapper. The next append after a format
       change looks correct in isolation and quietly breaks the scan, which is
       the whole reason the format is written into `decision-logging.md` and
       the `learnings` skill. An instruction is not enforcement.

    This is deliberately a STRUCTURAL check rather than a rendered one: it needs
    no renderer and no new dependency, and it fails on exactly the two shapes
    that have actually gone wrong rather than on a general notion of validity.
    """
    spec = COLLAPSIBLE_TABLES.get(rel)
    if spec is None:
        return []

    findings: list[Finding] = []
    header_idx = next(
        (i for i, line in enumerate(lines) if not mask[i] and line.startswith(spec["header"])),
        None,
    )
    if header_idx is None:
        return [Finding("structural", rel, 1, f"expected an append-only table starting {spec['header']!r}, found none")]

    columns = [c.strip() for c in split_unescaped_pipes(lines[header_idx])]
    try:
        targets = {name: columns.index(name) for name in spec["wrapped"]}
    except ValueError as exc:
        return [Finding("structural", rel, header_idx + 1, f"table header is missing a column this check depends on: {exc}")]

    # Walk from the separator to the end of the dated rows.
    i = header_idx + 2
    seen_row = False
    while i < len(lines):
        line = lines[i]
        if DATED_ROW_RE.match(line):
            seen_row = True
            cells = split_unescaped_pipes(line)
            if len(cells) != len(columns):
                findings.append(Finding(
                    "structural", rel, i + 1,
                    f"table row has {len(cells)} columns, header has {len(columns)}",
                ))
            else:
                for name, idx in targets.items():
                    if "<details>" not in cells[idx]:
                        findings.append(Finding(
                            "structural", rel, i + 1,
                            f"the {name!r} cell is missing its <details> wrapper; see decision-logging.md "
                            f"for the row shape, an unwrapped append breaks the table's scan",
                        ))
            i += 1
            continue
        if line.strip() == "":
            # A blank line only matters if the table CONTINUES after it: that is
            # the shape that silently truncates the rendered table.
            j = i
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if seen_row and j < len(lines) and DATED_ROW_RE.match(lines[j]):
                findings.append(Finding(
                    "structural", rel, i + 1,
                    "blank line INSIDE the table: markdown ends a table here, so every row below "
                    "renders as loose text. This is how 273 of 311 rows stopped rendering on 2026-08-14",
                ))
                i = j
                continue
        break
    return findings


def check_toc(rel: str, lines: list[str], mask: list[bool]) -> list[Finding]:
    findings: list[Finding] = []
    toc_idx = None
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        if line.strip().lower() == "## table of contents":
            toc_idx = i
            break
    if toc_idx is None:
        return findings

    toc_entries: list[str] = []
    j = toc_idx + 1
    link_re = re.compile(r"^-\s*\[[^\]]+\]\(#([^)]+)\)")
    while j < len(lines) and not lines[j].startswith("#"):
        if not mask[j]:
            m = link_re.match(lines[j].strip())
            if m:
                toc_entries.append(m.group(1))
        j += 1

    # Scan every ## heading in the WHOLE file, not only those after the TOC
    # block: a doc can legitimately place a lead section (for example
    # "## Status at a glance") before its own table of contents, and that
    # heading is still a real TOC target. The one heading excluded is the
    # TOC's own, which never links to itself. A heading-looking line inside
    # a fenced code block (a ```markdown example section) is excluded too:
    # it is a template shown to the reader, not a section of this document.
    raw_body_slugs: list[str] = []
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        if line.startswith("## ") and line.strip().lower() != "## table of contents":
            raw_body_slugs.append(slugify(line[3:].strip()))
    body_slugs = dedupe_slugs(raw_body_slugs)

    if toc_entries != body_slugs:
        findings.append(Finding(
            "structural", rel, toc_idx + 1,
            "table of contents does not match the file's ## headings in body order "
            f"(toc={toc_entries}, body={body_slugs})",
        ))
    return findings


PHASE_IN_HEADING_RE = re.compile(r"\bphase\s+(\d+\.\d+)\b", re.IGNORECASE)


def check_duplicate_phase_headings(rel: str, lines: list[str], mask: list[bool]) -> list[Finding]:
    findings: list[Finding] = []
    seen: dict[str, int] = {}
    for i, line in enumerate(lines):
        if mask[i] or not line.startswith("## "):
            continue
        for m in PHASE_IN_HEADING_RE.finditer(line):
            phase = m.group(1)
            if phase in seen:
                findings.append(Finding(
                    "structural", rel, i + 1,
                    f"## heading names phase {phase} again; already used at line {seen[phase] + 1}",
                ))
            else:
                seen[phase] = i
    return findings


LAST_UPDATED_RE = re.compile(r"^Last updated:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def check_last_updated(rel: str, lines: list[str], mask: list[bool]) -> list[Finding]:
    findings: list[Finding] = []
    lu_idx = None
    lu_date = None
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        m = LAST_UPDATED_RE.match(line.strip())
        if m:
            lu_idx, lu_date = i, m.group(1)
            break
    if lu_date is None:
        return findings

    body_dates: list[str] = []
    for i, line in enumerate(lines):
        if i == lu_idx or mask[i]:
            continue
        body_dates.extend(DATE_RE.findall(line))

    if body_dates and max(body_dates) > lu_date:
        findings.append(Finding(
            "structural", rel, lu_idx + 1,
            f"'Last updated: {lu_date}' predates a later date in the body ({max(body_dates)})",
        ))
    return findings


NEXT_PHASE_RE = re.compile(
    r"\bnext(?:\s+up)?\s*:?\s*build phase\s+(\d+\.\d+)\b"
    r"|\bbuild phase\s+(\d+\.\d+)\b[^.\n]{0,40}?\(?\s*next\b",
    re.IGNORECASE,
)


def check_next_phase(
    rel: str, lines: list[str], headings: list[tuple[int, str]],
    phase_statuses: dict[str, str], mask: list[bool],
) -> list[Finding]:
    findings: list[Finding] = []
    for i, line in enumerate(lines):
        if mask[i] or is_historical_context(lines, i, headings):
            continue
        for m in NEXT_PHASE_RE.finditer(line):
            if has_nearby_hedge(line, m.start(), m.end()):
                continue
            phase = m.group(1) or m.group(2)
            status = phase_statuses.get(phase)
            if status == "done":
                findings.append(Finding(
                    "structural", rel, i + 1,
                    f"describes build phase {phase} as next, but tracker/BOARD.md marks it done",
                ))
    return findings


def scan_structural(files: list[Path], facts: dict[str, Fact]) -> list[Finding]:
    findings: list[Finding] = []
    phase_statuses_fact = facts.get("build_phase_statuses")
    phase_statuses: dict[str, str] = (
        phase_statuses_fact.value if phase_statuses_fact and not phase_statuses_fact.skipped else {}  # type: ignore[assignment]
    )

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        mask = fenced_line_mask(lines)
        headings = heading_index(lines, mask)
        rel = path.relative_to(REPO_ROOT).as_posix()

        findings.extend(check_toc(rel, lines, mask))
        findings.extend(check_duplicate_phase_headings(rel, lines, mask))
        findings.extend(check_last_updated(rel, lines, mask))
        findings.extend(check_append_only_table(rel, lines, mask))
        # "next phase" is a currency claim; a dated session/meeting capture
        # narrating what was next AT THE TIME is not one. TOC, duplicate
        # heading, and last-updated staleness are structural hygiene checks
        # that still apply to a capture file, so only this one is skipped.
        if not is_historical_file(rel):
            findings.extend(check_next_phase(rel, lines, headings, phase_statuses, mask))

    return findings


# --------------------------------------------------------------------------
# Self-test: proves the historical-versus-current classifier itself, not
# just that the script runs. See `--self-test` in Usage and the "WHAT THIS
# SCRIPT DOES NOT CHECK" section of the module docstring.
# --------------------------------------------------------------------------


def _classify(lines: list[str], idx: int, match_start: int, match_end: int) -> str:
    """Classify one matched number as "historical" (skip) or "current"
    (flag if it disagrees with the computed fact), replicating the exact
    decision sequence `scan_stale_facts` applies to a real match: fence
    membership, then the whole-line/whole-section rules, then the
    proximity-windowed hedge check. This calls the production functions
    directly rather than re-implementing the rule, so a self-test pass
    proves those functions, not a parallel copy of them.
    """
    mask = fenced_line_mask(lines)
    if mask[idx]:
        return "historical"
    headings = heading_index(lines, mask)
    if is_historical_context(lines, idx, headings):
        return "historical"
    if has_nearby_hedge(lines[idx], match_start, match_end):
        return "historical"
    return "current"


@dataclass
class SelfTestCase:
    name: str
    lines: list[str]
    idx: int
    needle: str            # the exact substring whose span is the "number" under test
    expected: str           # "historical" | "current"


def _self_test_cases() -> list[SelfTestCase]:
    # Case C, the CLAUDE.md regression: a hedge word roughly 300 characters
    # before the number under test, well outside the 50-character window,
    # so the number must NOT be exempted.
    filler = "x" * 260
    claude_md_case_line = (
        f"Build phase 2.1 closed after five reviews. {filler} "
        "the cause was a composition defect in the schema slice. "
        "Final gates at merge: 968 Python tests plus 120 frontend tests passing."
    )

    return [
        SelfTestCase(
            name="dated table row is historical",
            lines=[
                "## Lessons",
                "| 2026-07-26 | some topic | 968 things happened that day | fixed by X |",
            ],
            idx=1,
            needle="968",
            expected="historical",
        ),
        SelfTestCase(
            name="hedge word inside the 50-char window is historical",
            lines=[
                "## Notes",
                "The old figure was wrong: 968 tests failed before the fix landed.",
            ],
            idx=1,
            needle="968",
            expected="historical",
        ),
        SelfTestCase(
            name="hedge word ~300 chars away (the CLAUDE.md case) stays current",
            lines=[
                "## Current focus",
                claude_md_case_line,
            ],
            idx=1,
            needle="968",
            expected="current",
        ),
        SelfTestCase(
            name="a bare current assertion is flagged current",
            lines=[
                "## Current focus",
                "977 Python tests passing today, all green.",
            ],
            idx=1,
            needle="977",
            expected="current",
        ),
        SelfTestCase(
            name="a number inside a fenced code block is historical",
            lines=[
                "Here is an example status line:",
                "```markdown",
                "968 Python tests plus 120 frontend tests passing.",
                "```",
                "That was only an example.",
            ],
            idx=2,
            needle="968",
            expected="historical",
        ),
        SelfTestCase(
            name="a number inside an UNCLOSED fence is historical",
            lines=[
                "Here is an example with no closing fence:",
                "```markdown",
                "968 Python tests, never closed",
            ],
            idx=2,
            needle="968",
            expected="historical",
        ),
        # The two cases below use the NEW label-then-number phrasing (the
        # exact shape that missed the real Continuation_prompt.md
        # regression) to prove the historical exemptions still hold now
        # that a label-first sentence is a live assertion candidate too.
        # Widening WHICH phrasings can be flagged must not weaken WHEN a
        # flagged phrasing gets exempted.
        SelfTestCase(
            name="label-then-number phrasing in a dated table row is historical",
            lines=[
                "## Lessons",
                "| 2026-07-26 | some topic | Learnings entries: 99 that day | fixed by X |",
            ],
            idx=1,
            needle="99",
            expected="historical",
        ),
        SelfTestCase(
            name="label-then-number phrasing inside a fenced code block is historical",
            lines=[
                "Here is an example status line:",
                "```markdown",
                "Python tests: 999",
                "```",
                "That was only an example.",
            ],
            idx=2,
            needle="999",
            expected="historical",
        ),
    ]


# --------------------------------------------------------------------------
# Pattern-coverage self-test: proves each fact's ASSERTION_PATTERNS (and
# PREMISE_GATE_RE) actually match BOTH the number-then-label and the
# label-then-number phrasing this repo uses, across the separators
# `LABEL_NUM_SEP` claims to cover. The historical-versus-current classifier
# above answers "does an exemption still fire correctly"; this answers "does
# a pattern fire AT ALL for this phrasing". Both have to hold: the real
# regression this script follows needed a pattern that matched the sentence
# shape in the first place, no exemption logic was involved.
#
# This calls the ASSERTION_PATTERNS / PREMISE_GATE_RE regex objects
# directly, on a single synthetic line, with no dependency on
# compute_all_facts() (no pytest, no vitest, no git), matching the existing
# `--self-test` contract of touching no source facts.
# --------------------------------------------------------------------------


def _first_match_value(fact_key: str, line: str) -> int | None:
    """Run every ASSERTION_PATTERN registered for `fact_key` against `line`
    and return the first parsed numeric value found, or None if none match.
    Self-test only; production scanning always goes through
    `scan_stale_facts`, which additionally applies the historical exemption.
    """
    for ap in ASSERTION_PATTERNS:
        if ap.fact_key != fact_key:
            continue
        m = ap.regex.search(line)
        if m:
            try:
                return ap.parser(m.group(1))
            except (KeyError, ValueError):
                continue
    return None


@dataclass
class PatternCoverageCase:
    name: str
    fact_key: str           # ASSERTION_PATTERNS fact_key, or "premise_gate"
    line: str
    expected: object         # int, or (int, int) for premise_gate


def _pattern_coverage_cases() -> list[PatternCoverageCase]:
    return [
        # Python tests: number-then-label, then label-then-number across
        # colon, table-pipe, and equals-sign separators.
        PatternCoverageCase("python_tests number-then-label", "python_tests",
                             "977 Python tests plus 120 frontend tests passing.", 977),
        PatternCoverageCase("python_tests label-then-number, colon", "python_tests",
                             "Python tests: 977", 977),
        PatternCoverageCase("python_tests label-then-number, table pipe", "python_tests",
                             "| Python tests | 977 |", 977),
        PatternCoverageCase("python_tests label-then-number, equals sign", "python_tests",
                             "Python tests = 977", 977),

        # Frontend tests: number-then-label, then label-then-number.
        PatternCoverageCase("frontend_tests number-then-label", "frontend_tests",
                             "120 frontend tests passing.", 120),
        PatternCoverageCase("frontend_tests label-then-number, colon", "frontend_tests",
                             "Frontend tests: 120", 120),

        # Playwright end-to-end tests: number-then-label, then
        # label-then-number, both with the optional "end-to-end" span.
        PatternCoverageCase("playwright_tests number-then-label", "playwright_tests",
                             "3 Playwright end-to-end tests passing.", 3),
        PatternCoverageCase("playwright_tests label-then-number, colon", "playwright_tests",
                             "Playwright end-to-end tests: 3", 3),

        # DECISIONS.md rows: all three number-then-label anchor phrasings,
        # then label-then-number across colon, table-pipe, and a bulleted
        # hyphen separator.
        PatternCoverageCase("decisions_rows number-then-label, decisions logged", "decisions_rows",
                             "183 decisions logged (DECISIONS.md)", 183),
        PatternCoverageCase("decisions_rows number-then-label, decision rows", "decisions_rows",
                             "183 decision rows", 183),
        PatternCoverageCase("decisions_rows number-then-label, DECISIONS.md rows", "decisions_rows",
                             "183 DECISIONS.md rows", 183),
        PatternCoverageCase("decisions_rows label-then-number, colon", "decisions_rows",
                             "Decisions logged: 183", 183),
        PatternCoverageCase("decisions_rows label-then-number, table pipe", "decisions_rows",
                             "| DECISIONS.md rows | 183 |", 183),
        PatternCoverageCase("decisions_rows label-then-number, hyphen bullet", "decisions_rows",
                             "- Decisions logged - 183", 183),

        # LEARNINGS.md entries: the real Continuation_prompt.md regression
        # case is the third one below.
        PatternCoverageCase("learnings_entries number-then-label, plus a retrospective", "learnings_entries",
                             "36 learnings plus a retrospective", 36),
        PatternCoverageCase("learnings_entries number-then-label, LEARNINGS.md entries", "learnings_entries",
                             "36 LEARNINGS.md entries", 36),
        PatternCoverageCase("learnings_entries label-then-number, colon (the real regression)", "learnings_entries",
                             "Learnings entries: 37, plus a retrospective", 37),
        PatternCoverageCase("learnings_entries label-then-number, table pipe", "learnings_entries",
                             "| LEARNINGS.md entries | 36 |", 36),

        # Open flags: digit and word-number forms, both orderings.
        PatternCoverageCase("open_flags number-then-label, digit", "open_flags",
                             "2 open flags", 2),
        PatternCoverageCase("open_flags number-then-label, word", "open_flags",
                             "two open flags", 2),
        PatternCoverageCase("open_flags label-then-number, colon", "open_flags",
                             "Open flags: 2", 2),

        # A case that must NOT match anything: "test files" is a different,
        # deliberately unpatterned fact (frontend_test_files), and a bare
        # "N tests" with no qualifying label must not be mistaken for any
        # of the facts above.
        PatternCoverageCase("bare test-file count matches no ASSERTION_PATTERN", "frontend_tests",
                             "15 test files, 121 tests, all passing", None),
    ]


def _premise_gate_coverage_cases() -> list[tuple[str, str, tuple[int, int] | None]]:
    return [
        ("premise_gate number-then-label, bare", "premise gate 9 of 9", (9, 9)),
        ("premise_gate number-then-label, 'at'", "premise gate at 9 of 9", (9, 9)),
        ("premise_gate label-then-number, colon (the real regression)", "Premise gate: 9 of 9", (9, 9)),
        ("premise_gate label-then-number, table pipe", "| Premise gate | 9 of 9 |", (9, 9)),
        ("premise_gate label-then-number, hyphen bullet", "- Premise gate - 9 of 9", (9, 9)),
    ]


def run_pattern_coverage_self_test() -> int:
    """Run every fixture in `_pattern_coverage_cases` and
    `_premise_gate_coverage_cases` directly against the production regex
    objects, print PASS/FAIL per case, and return the number of failures.
    A regression to single-ordering matching on any fact shows up here as a
    FAIL on that fact's label-then-number case, not as a silent pass.
    """
    failures = 0
    for case in _pattern_coverage_cases():
        actual = _first_match_value(case.fact_key, case.line)
        ok = actual == case.expected
        print(f"{'PASS' if ok else 'FAIL'}  {case.name} (expected {case.expected!r}, got {actual!r})")
        if not ok:
            failures += 1

    for name, line, expected in _premise_gate_coverage_cases():
        m = PREMISE_GATE_RE.search(line)
        actual = (int(m.group(1)), int(m.group(2))) if m else None
        ok = actual == expected
        print(f"{'PASS' if ok else 'FAIL'}  {name} (expected {expected!r}, got {actual!r})")
        if not ok:
            failures += 1

    total = len(_pattern_coverage_cases()) + len(_premise_gate_coverage_cases())
    print()
    print(f"{'ok' if failures == 0 else 'error'}: {total} pattern-coverage cases, {failures} failed")
    return failures


def run_self_test() -> int:
    """Run every fixture in `_self_test_cases`, print PASS/FAIL per case, and
    return the number of failures (0 means every case classified correctly).
    """
    failures = 0
    for case in _self_test_cases():
        start = case.lines[case.idx].find(case.needle)
        if start < 0:
            print(f"FAIL  {case.name}: fixture bug, {case.needle!r} not found on its own line")
            failures += 1
            continue
        end = start + len(case.needle)
        actual = _classify(case.lines, case.idx, start, end)
        ok = actual == case.expected
        print(f"{'PASS' if ok else 'FAIL'}  {case.name} (expected {case.expected}, got {actual})")
        if not ok:
            failures += 1
    print()
    print(f"{'ok' if failures == 0 else 'error'}: {len(_self_test_cases())} self-test cases, {failures} failed")
    return failures


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        classifier_failures = run_self_test()
        print()
        pattern_failures = run_pattern_coverage_self_test()
        return 1 if (classifier_failures or pattern_failures) else 0

    check_only = "--check" in argv
    verbose = "--verbose" in argv

    facts = compute_all_facts()
    files = tracked_markdown_files()

    findings: list[Finding] = []
    findings.extend(scan_stale_facts(files, facts))
    findings.extend(scan_pr_assertions(files, facts))
    findings.extend(scan_structural(files, facts))

    computed_count = sum(1 for f in facts.values() if not f.skipped)
    skipped_count = sum(1 for f in facts.values() if f.skipped)
    stale_count = sum(1 for f in findings if f.kind == "stale")
    structural_count = sum(1 for f in findings if f.kind == "structural")

    if verbose:
        print(f"Computed facts ({len(files)} tracked markdown files scanned, "
              f"{len(SKIP_FILES)} locked file(s) excluded):")
        for fact in facts.values():
            status = f"SKIPPED ({fact.skip_reason})" if fact.skipped else fact.display
            print(f"  {fact.label}: {status}")
            print(f"    via: {fact.source}")
        print()

    if check_only:
        for finding in findings:
            print(finding.format())
        status_word = "ok" if not findings else "error"
        skipped_note = f" ({skipped_count} skipped)" if skipped_count else ""
        print(f"{status_word}: {computed_count} facts computed{skipped_note} | "
              f"{stale_count} stale | {structural_count} structural")
        return 1 if findings else 0

    print("Canonical facts computed from source:")
    for fact in facts.values():
        status = f"SKIPPED ({fact.skip_reason})" if fact.skipped else fact.display
        print(f"  {fact.label}: {status}")
    print()

    if findings:
        print("Findings:")
        for finding in findings:
            print(f"  [{finding.kind}] {finding.format()}")
    else:
        print("No drift found.")
    print()

    status_word = "ok" if not findings else "error"
    skipped_note = f" ({skipped_count} skipped)" if skipped_count else ""
    print(f"{status_word}: {computed_count} facts computed{skipped_note} | "
          f"{stale_count} stale | {structural_count} structural")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
