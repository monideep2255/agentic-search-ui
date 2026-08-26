#!/usr/bin/env python3
"""Fail phase close if a phase had confirmed findings and zero LEARNINGS.md rows.

Depends on:
    - tracker/phase_N.M.md (parsed; the Findings section's Status lines)
    - LEARNINGS.md (parsed; the Lessons table's "Applies to" column)

Writes:
    - Nothing. Exits non-zero and prints a message naming the uncovered
      findings; writes no file.

This exists because "write to LEARNINGS.md the moment something breaks" was
a standing instruction in bossman-mode's own protocol with no mechanical
check behind it, so it depended entirely on the lead remembering to follow
it every phase. Build phase 2.0 shipped with real, judge-and-adversary-
confirmed findings and zero LEARNINGS.md entries until the gap was noticed
after the fact and backfilled. This script is the backstop: it does not
replace writing learnings in real time, it catches the case where that
didn't happen before the phase is allowed to close.

A finding counts as needing a LEARNINGS.md entry once its Status is
"confirmed" or "closed" (a judge has verified it is real), never "filed"
(unverified) or "rejected" (verified NOT real). Coverage is checked at the
phase level, not one row per finding: at least one LEARNINGS.md row whose
"Applies to" column names this phase (its number, e.g. "build phase 2.0",
or its branch name) is enough to pass, since a single entry can legitimately
cover a recurring pattern behind several findings.

Usage:
    python3 tracker/check_learnings_coverage.py 2.0
    python3 tracker/check_learnings_coverage.py 2.0 --phase-file tracker/phase_2.0.md

Exits non-zero, with the uncovered finding ids listed, when confirmed or
closed findings exist and no LEARNINGS.md row mentions the phase.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEARNINGS_MD = ROOT / "LEARNINGS.md"

_FINDING_HEADER_RE = re.compile(r"^###\s+(F-[\w.\-]+):")
_STATUS_LINE_RE = re.compile(r"Severity:.*?Status:\s*([a-zA-Z]+)", re.IGNORECASE | re.DOTALL)

#: A finding written as a TABLE ROW rather than a narrative block. Added
#: 2026-08-21 (R-02) because this script returned a FALSE PASS, "ok: no
#: confirmed or closed findings, nothing to cover", against build phase 4.6's
#: ledger of THIRTY findings including two criticals. It recognised only the
#: `### F-x:` narrative form, and that ledger is a table. Build phase 3.3
#: flagged this exact gap and it stayed open, so the gate whose whole job is
#: to force a learnings entry had been passing without reading anything.
#:
#: A false pass is worse than a false alarm here: an alarm gets investigated,
#: a green result stops anyone looking.
_FINDING_ROW_RE = re.compile(r"^\|\s*(F-[\w.\-]+)\s*\|")

#: States meaning a reviewer has verified the finding is real, so it needs a
#: learning. Widened from {"confirmed", "closed"} for the same reason: no
#: ledger in this repository actually writes those two words alone. The real
#: vocabulary is "fixed, re-verified", "RESOLVED by revert", "fixed, pending
#: judge" and similar.
#:
#: Deliberately EXCLUDED, and each exclusion is a judgement rather than an
#: oversight: "open" and "filed" (not yet verified), "rejected" (verified NOT
#: real), and "withdrawn" (filed then disproven, as build phase 4.5's budget
#: finding and build phase 4.6's F-4.6-05 both were). A withdrawn finding
#: taught something, but it is not the phase's defect and forcing a learning
#: for it would train the gate to be ignored.
_COVERED_STATUSES = {"confirmed", "closed", "fixed", "resolved"}


def _leading_word(cell: str) -> str:
    """The first alphabetic token of a table cell, lowercased.

    Only the LEADING word counts, never a substring search across the cell.
    That distinction is load-bearing: build phase 4.6's ledger contains the
    phrase "NOT FIXED and not reachable" inside a reason cell, and a
    substring search for "fixed" would read that as fixed and count a
    genuinely open finding as covered, which is the same false pass this
    change exists to remove.
    """
    match = re.match(r"\s*([A-Za-z]+)", cell)
    return match.group(1).lower() if match else ""


def _phase_file_path(phase: str) -> Path:
    return ROOT / "tracker" / f"phase_{phase}.md"


def find_covered_findings(phase_text: str) -> list[str]:
    """Return the ids of findings whose Status is confirmed or closed.

    A finding's header (`### F-x-y: title`) and its Status line (`Severity:
    ... Status: <word> ...`) are not always adjacent (an intervening blank
    line or a wrapped severity clause is common), so this scans forward
    from each header to the next header or end of file, taking the first
    Status line found in between, rather than assuming a fixed line offset.
    """
    lines = phase_text.splitlines()
    header_indices = [
        (i, m.group(1)) for i, line in enumerate(lines) if (m := _FINDING_HEADER_RE.match(line))
    ]
    covered: list[str] = []
    for idx, (start, finding_id) in enumerate(header_indices):
        end = header_indices[idx + 1][0] if idx + 1 < len(header_indices) else len(lines)
        block = "\n".join(lines[start:end])
        status_match = _STATUS_LINE_RE.search(block)
        if status_match and status_match.group(1).lower() in _COVERED_STATUSES:
            covered.append(finding_id)

    # The table form (R-02). Scanned independently of the narrative form above
    # rather than instead of it, because a phase file may legitimately carry
    # both: build phase 4.6's does not, but build phase 3.3's mixes narrative
    # tickets with table findings, which is how that phase's gap was missed.
    #
    # Column ORDER is not assumed. Different phase files order their columns
    # differently, so every cell is offered to `_leading_word` and the row
    # counts if any cell BEGINS with a covered state. That is more robust than
    # indexing a fixed column and stricter than searching the whole row.
    for line in lines:
        row_match = _FINDING_ROW_RE.match(line)
        if row_match is None:
            continue
        finding_id = row_match.group(1)
        if finding_id in covered:
            continue
        cells = line.split("|")
        if any(_leading_word(cell) in _COVERED_STATUSES for cell in cells):
            covered.append(finding_id)
    return covered


def phase_mentioned_in_learnings(phase: str, learnings_text: str) -> bool:
    """Return whether any LEARNINGS.md row names this phase.

    Matches "build phase 2.0" (the convention every existing row uses) or
    the phase's branch-shaped name (e.g. "phase/2.0-"), so a row that
    references the branch instead of the prose phrase still counts.
    """
    patterns = [
        rf"build phase {re.escape(phase)}\b",
        rf"phase/{re.escape(phase)}-",
    ]
    return any(re.search(pattern, learnings_text, re.IGNORECASE) for pattern in patterns)


def main(argv: list[str]) -> int:
    """CLI entry point. See the module docstring for usage and exit codes."""
    if not argv:
        print("usage: check_learnings_coverage.py <phase> [--phase-file PATH]", file=sys.stderr)
        return 2
    phase = argv[0]
    phase_file = _phase_file_path(phase)
    if "--phase-file" in argv:
        phase_file = ROOT / argv[argv.index("--phase-file") + 1]

    if not phase_file.exists():
        print(f"error: {phase_file} does not exist", file=sys.stderr)
        return 2
    if not LEARNINGS_MD.exists():
        print(f"error: {LEARNINGS_MD} does not exist", file=sys.stderr)
        return 2

    phase_text = phase_file.read_text(encoding="utf-8")
    learnings_text = LEARNINGS_MD.read_text(encoding="utf-8")

    covered_findings = find_covered_findings(phase_text)
    if not covered_findings:
        print(f"ok: no confirmed or closed findings in {phase_file.name}, nothing to cover")
        return 0

    if phase_mentioned_in_learnings(phase, learnings_text):
        print(
            f"ok: {len(covered_findings)} confirmed/closed finding(s) in "
            f"{phase_file.name} ({', '.join(covered_findings)}), and "
            f"LEARNINGS.md has an entry for build phase {phase}"
        )
        return 0

    print(
        f"FAIL: {len(covered_findings)} confirmed/closed finding(s) in {phase_file.name} "
        f"({', '.join(covered_findings)}), but LEARNINGS.md has no entry mentioning "
        f"'build phase {phase}' or 'phase/{phase}-'.\n"
        "Write at least one LEARNINGS.md row for this phase before closing it. "
        "A confirmed or closed finding that cost real time to diagnose is exactly "
        "what this file exists to capture.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
