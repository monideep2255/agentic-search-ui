#!/usr/bin/env python3
"""Check tracked documentation for structural defects and wrong references.

WHAT `--check` CHECKS

Every tracked markdown file, for the structural defects that have actually
broken this repository's documents, plus two kinds of reference that git and
the build board can settle:

  - Table of contents: the list under "## Table of contents" matches the
    file's `##` headings, in body order.
  - Duplicate phase headings: no two `##` headings name the same build phase.
  - Stale "Last updated" lines: a file's first "Last updated:" date is not
    older than the latest date written anywhere else in the file, outside
    fenced code.
  - The two append-only tables, DECISIONS.md and LEARNINGS.md: no blank line
    inside the table (markdown ends a table there), every dated row has the
    header's column count, and every row carries its `<details>` wrappers.
  - Phase and pull request references: a sentence of the shape "phase X.Y
    ... PR #N" names the pull request that actually merged that phase.
  - "Next" references: no document calls a build phase "next" when
    `tracker/BOARD.md` marks it done.

WHAT IT STOPPED CHECKING ON 2026-09-25: COUNTS

Until 2026-09-25 this script computed the test, decision, learning, premise
gate and Playwright counts from source, running the whole pytest collection
and the vitest suite to do it, and failed whenever a document stated a stale
copy. That made the check go red because time passed rather than because a
document was wrong, and the fix each time was an edit that only moved a
number or a date: 87 of the 92 commits to CLAUDE.md in the two weeks before
changed nothing else (`testing/Developer/reports/2026-09-25_harness_review/
build_harness.md`, items D1 and D2). The product owner delegated the harness
fixes to the lead on 2026-09-25 (DECISIONS.md, "The lead implements both
harness reviews' takeaways"), so the documents stopped stating counts and this
check stopped comparing them.

The counts are still computed, on demand, by `--counts`, which prints them
and checks no document against them.

The "Last updated:" check was removed with the counts on 2026-09-25 and
restored on 2026-09-26, because review item D1 keeps stale dates among the
structural checks. It compares a file with itself, never with the calendar:
an edit that adds a dated line without moving the file's "Last updated:"
line fails it, and time passing never does.

NEVER A SILENT OK

A run that could not compute what it needs says so and exits 1; it never
prints "ok" over a gap (build harness review item S3). The measured failure:
in an agent worktree with no `venv/bin/python`, this script skipped the
Python test count, still printed "ok" and exited 0, while the count it
tracked was stale (F-8.5-J04 and F-8.5-V05, `tracker/phase_8.5.md`). So:

  - `--check`: a fact the checks read that could not be computed (the
    board's phase statuses, the merged pull request per phase) is a failure
    line naming the reason, and so is a failure to list the tracked files.
  - `--counts`: a count that could not be computed is a failure line naming
    the reason, and so is a pytest collection that reports errors. When a
    test module fails to import, pytest prints "N tests collected, M errors"
    and N silently leaves out that module's tests, so N reads as a smaller
    true count. Pytest 9 prints exactly that line, and exits 2, measured on
    2026-09-25 with two modules that import a missing name.

THE HISTORICAL-VERSUS-CURRENT RULE

A reference in a document is only wrong if it is being asserted as CURRENT. A
sentence that quotes a past state, an example of an error, or an unrelated
phase is not a finding even when it disagrees with git or the board. The two
reference checks tell the two apart with the following rule, applied to every
regex match before it is reported:

A match is treated as HISTORICAL, and skipped, when any one of these holds:

  1. Dated record row. The line is a data row of a dated table or a dated
     bullet: it matches `^\\|\\s*\\d{4}-\\d{2}-\\d{2}\\s*\\|` (a DECISIONS.md or
     LEARNINGS.md row) or `^-\\s*\\d{4}-\\d{2}-\\d{2}\\b` (a Plan.md Revision
     history bullet). A reference attached to a past date is a record of what
     was true then, not a claim about now.
  2. Historical section. The nearest preceding heading (any line starting
     with `#`) contains a literal date, or the word "retrospective",
     "session", or the phrase "revision history" (case-insensitive). These
     headings mark an entire section as a past snapshot, for example a
     tracker phase file's dated review-round sections or Plan.md's
     "## Revision history".
  3. Hedge or correction cue near the match, not merely on the line. A word
     within 50 characters of the match marks it as an example of an error
     rather than a live claim: "was", "wrong", "stale", "outdated",
     "incorrect", "previously", "used to", "prior to", "superseded",
     "corrected", "instead of", "as measured", "as of", or "at the". The
     window is deliberate: this repository often puts a full paragraph inside
     one markdown table cell (one line), so a whole-line hedge check would let
     an unrelated "was" fifty words away exempt a live claim it has nothing to
     do with. The measured case that set the window, from when this script
     still checked counts: CLAUDE.md's Priority-2 row stated a current test
     count in the same line as "the cause WAS a composition defect", a
     genuinely historical clause about a different topic entirely.

A match that survives all three is a CURRENT assertion. If it disagrees with
git or the board, it is reported.

THE FALSE-NEGATIVE TRADE-OFF

Every rule above is written to exempt generously. A check that cries wolf on
legitimate historical text gets disabled, which loses all of its detection
value; a check that misses one wrong sentence loses only that one instance.
When a borderline case comes up, this script exempts it.

WHAT THIS SCRIPT DOES NOT CHECK

A green run here is evidence about the specific checks listed at the top, not
a certification that the documentation is correct. Per this repository's own
`goal-contracts` rule, a verify surface has to state its own coverage.

  - No count, anywhere. A document may state a test, decision or learning
    count and this script will not compare it with anything. The documents
    that used to carry counts (CLAUDE.md, AGENTS.md, requirements/Plan.md)
    point at `--counts` instead.
  - No date against the calendar. Nothing requires any document to carry
    today's date or a "Last updated:" line at all. The one date check reads
    a file's "Last updated:" line against the dates in the same file, and a
    future date written in the body, such as a planned one, counts as later.
  - No prose. A narrative claim, an architectural description, or a "why"
    explanation can be entirely wrong and this script will not notice,
    because it never reads for meaning, only for the anchored patterns above.
  - The two locked documents, `requirements/PRD.md` and
    `requirements/Technical_specification.md`. Both are frozen until the Step
    6.2 reconciliation and are allowed to disagree with the live system on
    purpose, so flagging them would produce a finding nobody may act on.
  - A reference that is MISSING. This script proves "no document states a
    wrong phase-to-pull-request pairing", not "every document that should
    name a pull request still does".
  - The reverse ordering "PR #N ... phase X.Y". `PHASE_THEN_PR_RE` matches
    only "phase X.Y ... PR #N", by design, because no reverse-ordered
    phrasing exists in this repository today. A document that starts using
    one is unchecked until a pattern is added.
  - A phase `tracker/BOARD.md` does not list. The phase and pull request
    check, and the "next" check, read the board's Build phases table, so a
    phase that is not on the board is not checked at all.

Depends on:
    - tracker/BOARD.md (parsed for build-phase statuses, each phase's branch
      and, for `--counts`, the Open flags table, via tracker/render_board.py's
      own parser)
    - tracker/render_board.py (`parse_board`, `find_table`, `BoardError`;
      reused rather than re-implemented so the two scripts never disagree
      about what BOARD.md says)
    - git log --merges (merged pull request numbers per phase branch)
    - git ls-files '*.md' (the set of tracked markdown files to check)
    - `--counts` only: venv/bin/python (to run pytest), frontend/node_modules
      (to run vitest), frontend/e2e/*.spec.ts, DECISIONS.md, LEARNINGS.md,
      tests/system_03_search_agent/tools/test_cypher_query_premise.py

Depended on by:
    - .claude/skills/doc-readability/scripts/check_style.py, which imports
      `fenced_line_mask`, `heading_index`, `slugify`, `dedupe_slugs` and
      `check_toc` rather than re-implementing them. Keep their signatures.

Reads:
    `--counts` runs `pytest --collect-only -q` and `npx vitest run` as
    read-only measurement subprocesses. Neither mutates repository or test
    state. `--check` runs neither.

Writes:
    Nothing. Stdout only. This script never edits a file.

Usage:
    python3 tracker/check_doc_drift.py             print a full report
    python3 tracker/check_doc_drift.py --check     exit 0 clean / 1 on any
                                                    finding, one line per
                                                    finding, a fact it could
                                                    not compute included
    python3 tracker/check_doc_drift.py --verbose   also print every fact the
                                                    checks read and how it
                                                    was computed
    python3 tracker/check_doc_drift.py --counts    print-only: the test,
                                                    decision, learning, flag,
                                                    premise gate and
                                                    Playwright counts computed
                                                    from source. Checks no
                                                    document against them.
                                                    Exit 1 when a count could
                                                    not be computed or pytest
                                                    reported collection errors
    python3 tracker/check_doc_drift.py --self-test run the historical-versus-
                                                    current classifier's
                                                    fixtures; exit 0 only if
                                                    every case passes. Does
                                                    not touch source facts,
                                                    pytest, vitest, or git.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

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
import render_board

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
    kind: str               # "stale" | "structural" | "unmeasured"
    path: str               # "" for an unmeasured finding: it is about the run, not a file
    line: int
    message: str

    def format(self) -> str:
        if not self.path:
            return self.message
        return f"{self.path}:{self.line}: {self.message}"


def unmeasured_findings(facts: dict[str, Fact]) -> list[Finding]:
    """One failure line per fact that could not be computed. A skipped fact
    means every check that reads it checked nothing, so the run cannot say
    ok; see "NEVER A SILENT OK" in the module docstring.
    """
    return [
        Finding("unmeasured", "", 0, f"could not compute {fact.label}: {fact.skip_reason}")
        for fact in facts.values()
        if fact.skipped
    ]


# --------------------------------------------------------------------------
# Fact computation
# --------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


# The summary line `pytest --collect-only -q` ends with. Measured with pytest
# 9.1.1 on 2026-09-25: "2 tests collected in 0.00s" when every module imports,
# "2 tests collected, 1 error in 0.11s" and "2 tests collected, 2 errors in
# 0.12s" when one or two modules fail to import (exit 2, after a line reading
# "Interrupted: N errors during collection"), and "no tests collected" when
# nothing is found. "N/M tests collected (K deselected)" appears only under a
# marker filter, which this script never passes, and is accepted anyway.
#
# Both patterns are anchored to the START of a line, and that is load-bearing:
# `--collect-only -q` lists every test id first, and a parametrized id can
# carry any text. Measured on 2026-09-25: this script's own tests have ids
# containing "Interrupted: 1 error during collection", and an unanchored
# search read that id as a collection error in a clean run. A test id starts
# with its file path, never with a digit, "no" or "!", so anchoring excludes
# every id while still matching pytest's own lines.
COLLECTED_RE = re.compile(
    r"^=*[ \t]*(?P<collected>\d+|no)(?:/\d+)?[ \t]+tests?[ \t]+collected\b(?P<rest>.*)$",
    re.MULTILINE,
)
COLLECTION_ERRORS_RE = re.compile(r"\b(\d+)[ \t]+errors?\b")
INTERRUPTED_RE = re.compile(
    r"^!+[ \t]*Interrupted:[ \t]+(\d+)[ \t]+errors?[ \t]+during collection\b",
    re.MULTILINE,
)


def parse_collection_summary(output: str) -> tuple[int | None, int]:
    """Return (tests collected, collection errors) from `pytest
    --collect-only -q` output. The collected count is None when no summary
    line is present. The error count is read from the summary line itself
    and from pytest's "Interrupted: N errors during collection" line, taking
    the larger, so an error is never missed because one of the two lines is
    absent. It is 0 only when neither line reports an error.
    """
    errors = 0
    interrupted = INTERRUPTED_RE.search(output)
    if interrupted:
        errors = int(interrupted.group(1))
    summaries = list(COLLECTED_RE.finditer(output))
    if not summaries:
        return None, errors
    last = summaries[-1]
    collected = 0 if last.group("collected") == "no" else int(last.group("collected"))
    on_summary = COLLECTION_ERRORS_RE.search(last.group("rest"))
    if on_summary:
        errors = max(errors, int(on_summary.group(1)))
    return collected, errors


def _pytest_collected_count(target: str | None) -> tuple[int | None, str]:
    """Run `pytest --collect-only -q` (optionally scoped to one file) and
    parse its summary line. Returns (count, reason); count is None and reason
    explains why when it could not be measured honestly, which includes a
    collection that reported errors: its count leaves out every test in the
    modules that failed to import.
    """
    if not VENV_PYTHON.exists():
        try:
            shown = VENV_PYTHON.relative_to(REPO_ROOT)
        except ValueError:
            shown = VENV_PYTHON
        return None, (
            f"{shown} not found, so pytest could not run. Run this from a checkout "
            "that has the repository venv, or create it there"
        )
    cmd = [str(VENV_PYTHON), "-m", "pytest", "--collect-only", "-q"]
    if target:
        cmd.append(target)
    proc = _run(cmd, cwd=REPO_ROOT, timeout=PYTEST_TIMEOUT_S)
    if proc is None:
        return None, "pytest invocation failed or timed out"
    combined = proc.stdout + "\n" + proc.stderr
    collected, errors = parse_collection_summary(combined)
    if errors:
        return None, (
            f"pytest reported {errors} collection error{'s' if errors != 1 else ''}, so the "
            f"{collected if collected is not None else 'unknown number of'} tests it did collect "
            "leave out every test in the modules that failed to import. Run "
            "`python -m pytest --collect-only -q` to see which modules failed"
        )
    if collected is None:
        return None, (
            "could not parse a 'N tests collected' line from pytest output "
            f"(pytest exited {proc.returncode})"
        )
    if proc.returncode not in (0, 5):
        return None, (
            f"pytest exited {proc.returncode} while collecting, which is not a clean "
            "collection even though it reported no error count"
        )
    return collected, ""


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


def compute_check_facts() -> dict[str, Fact]:
    """The facts `--check` reads: the board's phase statuses, for the "next"
    check, and the merged pull request per phase, for the reference check.
    Deliberately no count: `--check` runs neither pytest nor vitest.
    """
    return {
        "build_phase_statuses": compute_build_phase_statuses(),
        "merged_prs": compute_merged_pr_numbers(),
    }


def compute_count_facts() -> dict[str, Fact]:
    """The counts `--counts` prints. No document is checked against them."""
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
# standalone files deleted.) A reference inside one of these files is what
# that session reported at the time, never a claim about the document's
# current state.
# Real case this caught, from when this script still checked counts:
# `requirements/phase_1/Session_May_07.md` says "5 decisions logged to
# DECISIONS.md from Step 1.3", a per-step delta from 2026-05-07, which a
# line-level check alone still matched as a current claim because its heading
# text carries no date, "session", or "retrospective" token.
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
    reference regex should not treat a phase inside one as a live claim, and
    neither should this script.

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
    return bool(current_heading and HISTORICAL_HEADING_RE.search(current_heading))


def has_nearby_hedge(line: str, start: int, end: int, window: int = 50) -> bool:
    """Rule 3, scoped to a character window around one match.

    This has to be per-match, not per-line, because this repo routinely
    puts an entire paragraph inside one markdown table cell, one line. The
    measured case, from when this script still checked counts: CLAUDE.md's
    Priority-2 row stated a current test count ("968 Python tests") in the
    same line as "the cause WAS a composition defect", a genuinely historical
    clause describing build phase 2.1's root cause, hundreds of characters
    away. A whole-line hedge check reads that "was" and exempts the live
    claim too, silently defeating the case the check exists for. A window
    keeps the hedge word tied to the claim it is actually hedging, as in
    "968 AT THE 2026-08-01 merge", where the hedge sits right next to it.
    """
    lo = max(0, start - window)
    hi = min(len(line), end + window)
    return bool(HEDGE_WORD_RE.search(line[lo:hi]))


# Directional by design: "phase X.Y (..., PR #N)" is the phrasing this repo
# uses everywhere it was found (CLAUDE.md, AGENTS.md). The reverse order is
# not scanned for; see the module docstring's "WHAT THIS SCRIPT DOES NOT
# CHECK" section, which names this ordering gap, left as-is because no
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


def tracked_markdown_files() -> list[Path] | None:
    """Every tracked markdown file except the locked documents, or None when
    git could not list them. None is not an empty list: an empty list checks
    nothing and would print "ok", which is the silent pass `main` refuses.
    """
    proc = _run(["git", "ls-files", "*.md"], cwd=REPO_ROOT, timeout=GIT_TIMEOUT_S)
    if proc is None or proc.returncode != 0:
        return None
    paths = []
    for rel in proc.stdout.splitlines():
        rel = rel.strip()
        if not rel or rel in SKIP_FILES:
            continue
        paths.append(REPO_ROOT / rel)
    return paths


# --------------------------------------------------------------------------
# Reference check: "phase X.Y ... PR #N"
# --------------------------------------------------------------------------


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
    r"""Split a markdown table row into cells, respecting escaped pipes.

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
        # narrating what was next AT THE TIME is not one. The TOC, duplicate
        # heading, last-updated staleness and append-only table checks are
        # structural hygiene that still applies to a capture file, so only
        # this one is skipped.
        if not is_historical_file(rel):
            findings.extend(check_next_phase(rel, lines, headings, phase_statuses, mask))

    return findings


# --------------------------------------------------------------------------
# Self-test: proves the historical-versus-current classifier itself, not
# just that the script runs. See `--self-test` in Usage and the "WHAT THIS
# SCRIPT DOES NOT CHECK" section of the module docstring. The fixture lines
# still read as count sentences because that is where the classifier's
# measured cases came from; the classifier is agnostic about what it is
# classifying, and it now guards the phase and pull request reference checks.
# --------------------------------------------------------------------------


def _classify(lines: list[str], idx: int, match_start: int, match_end: int) -> str:
    """Classify one match as "historical" (skip) or "current" (flag if it
    disagrees with git or the board), replicating the exact decision sequence
    `scan_pr_assertions` applies to a real match: fence membership, then the
    whole-line/whole-section rules, then the proximity-windowed hedge check.
    This calls the production functions directly rather than re-implementing
    the rule, so a self-test pass proves those functions, not a parallel copy
    of them.
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
    needle: str            # the exact substring whose span is the match under test
    expected: str           # "historical" | "current"


def _self_test_cases() -> list[SelfTestCase]:
    # Case C, the CLAUDE.md regression: a hedge word roughly 300 characters
    # before the match under test, well outside the 50-character window,
    # so the match must NOT be exempted.
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
            name="a match inside a fenced code block is historical",
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
            name="a match inside an UNCLOSED fence is historical",
            lines=[
                "Here is an example with no closing fence:",
                "```markdown",
                "968 Python tests, never closed",
            ],
            idx=2,
            needle="968",
            expected="historical",
        ),
        SelfTestCase(
            name="a phase and pull request reference in a dated table row is historical",
            lines=[
                "## Lessons",
                "| 2026-07-26 | some topic | build phase 3.1 merged as PR #22 that day | fixed by X |",
            ],
            idx=1,
            needle="PR #22",
            expected="historical",
        ),
        SelfTestCase(
            name="a phase and pull request reference inside a fenced code block is historical",
            lines=[
                "Here is an example status line:",
                "```markdown",
                "Build phase 3.1 merged as PR #22.",
                "```",
                "That was only an example.",
            ],
            idx=2,
            needle="PR #22",
            expected="historical",
        ),
    ]


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


def run_counts() -> int:
    """`--counts`: print every count computed from source. Print-only: no
    document is read for a stated count and none is compared with anything.
    Exits 1 when a count could not be computed, including a pytest
    collection that reported errors, and says why for each one.
    """
    facts = compute_count_facts()
    print("Counts computed from source (print-only, no document is checked against them):")
    for fact in facts.values():
        status = "could not compute, see below" if fact.skipped else fact.display
        print(f"  {fact.label}: {status}")
        print(f"    via: {fact.source}")
    failures = unmeasured_findings(facts)
    computed_count = len(facts) - len(failures)
    print()
    for failure in failures:
        print(failure.format())
    if failures:
        print(f"error: {computed_count} counts computed | {len(failures)} could not be computed")
        return 1
    print(f"ok: {computed_count} counts computed")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return 1 if run_self_test() else 0
    if "--counts" in argv:
        return run_counts()

    check_only = "--check" in argv
    verbose = "--verbose" in argv

    facts = compute_check_facts()
    listed = tracked_markdown_files()
    files = listed if listed is not None else []

    findings: list[Finding] = unmeasured_findings(facts)
    if listed is None:
        findings.append(Finding(
            "unmeasured", "", 0,
            "could not list the tracked markdown files: `git ls-files '*.md'` failed or timed "
            "out, so no document was checked",
        ))
    findings.extend(scan_pr_assertions(files, facts))
    findings.extend(scan_structural(files, facts))

    computed_count = sum(1 for f in facts.values() if not f.skipped)
    unmeasured_count = sum(1 for f in findings if f.kind == "unmeasured")
    stale_count = sum(1 for f in findings if f.kind == "stale")
    structural_count = sum(1 for f in findings if f.kind == "structural")

    status_word = "ok" if not findings else "error"
    summary = (
        f"{status_word}: {computed_count} facts computed | {unmeasured_count} could not be "
        f"computed | {stale_count} stale | {structural_count} structural"
    )

    if verbose:
        print(f"Facts the checks read ({len(files)} tracked markdown files scanned, "
              f"{len(SKIP_FILES)} locked file(s) excluded):")
        for fact in facts.values():
            status = "could not compute, see the findings" if fact.skipped else fact.display
            print(f"  {fact.label}: {status}")
            print(f"    via: {fact.source}")
        print()

    if check_only:
        for finding in findings:
            print(finding.format())
        print(summary)
        return 1 if findings else 0

    print("Facts the checks read, computed from source:")
    for fact in facts.values():
        status = "could not compute, see the findings" if fact.skipped else fact.display
        print(f"  {fact.label}: {status}")
    print()

    if findings:
        print("Findings:")
        for finding in findings:
            print(f"  [{finding.kind}] {finding.format()}")
    else:
        print("No drift found.")
    print()

    print(summary)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
