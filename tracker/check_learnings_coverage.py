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
_COVERED_STATUSES = {"confirmed", "closed"}


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
