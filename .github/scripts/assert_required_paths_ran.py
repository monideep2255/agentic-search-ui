#!/usr/bin/env python3
"""Fail CI unless the required-path tests actually executed.

Build phase 4.14, gate 9. Section 24 calls these two paths out separately from
the unit suite for one reason, in its own words: they are "never skippable".

A `pytest <file>` invocation exits 0 in three different situations, and only
one of them is the one gate 9 exists to certify:

  1. Every test in the file ran and passed.          <- the only acceptable one
  2. Every test in the file was skipped.
  3. The file collected NOTHING, because it was renamed, moved, or its tests
     were renamed out of the collection pattern.

Case 3 is the dangerous one and it is not hypothetical. Section 24 names these
tests as `test_cite_or_refuse_compliance` and `test_zero_retrieval_refusal`;
build phase 4.14 found that NEITHER name exists as a function anywhere in the
suite (finding F-4.14-02). They live as sections of a file. A gate pointed at
a name that has already drifted once is a gate that will silently certify an
empty run, and `production-standards`'s AI-answer-grounding gate is the single
highest-leverage correctness control in this system.

So this asserts the positive: tests ran, none skipped, none failed, and at
least one of them was about each of the two required paths.

Usage:
    python .github/scripts/assert_required_paths_ran.py <junit-xml-path>

Exit codes:
    0  the required paths ran and passed
    1  anything else, including a report that could not be read

Depends on:
    - Nothing outside the standard library.

Reads:
    - The JUnit XML written by `pytest --junitxml`.

Writes:
    - Nothing. Prints to stdout and stderr only.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET

# The two required paths of Section 23, matched against test names. Each entry
# is (label, substrings that identify a test as covering that path). A test
# matches the path if ANY substring appears in its name.
#
# Substrings, not exact function names, because F-4.14-02 is precisely the
# lesson that the exact names in the specification do not exist in the code.
# What must not drift is that BOTH PROPERTIES are still being exercised, and
# that is what this matches on.
_REQUIRED_PATHS = (
    ("cite-or-refuse compliance", ("cite_or_refuse", "grounded", "ground_claim", "citation")),
    ("zero-retrieval refusal", ("refus", "zero_retrieval", "no_source", "abstain")),
)

_MINIMUM_CASES = 2


def _parse_report(report_path: str) -> ET.Element:
    """Parse the JUnit report, rejecting entity declarations before parsing.

    Same reasoning as `assert_no_db_skips.py`'s copy of this helper, and the
    duplication is deliberate: these two scripts must run with nothing
    installed, so neither imports the other and neither introduces a package.
    """
    with open(report_path, "rb") as handle:
        raw = handle.read()
    if b"<!ENTITY" in raw.upper():
        raise ValueError(
            "the pytest report declares an XML entity, which pytest never emits"
        )
    return ET.fromstring(raw)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <junit-xml-path>", file=sys.stderr)
        return 1

    report_path = argv[1]
    try:
        tree = _parse_report(report_path)
    except (OSError, ET.ParseError, ValueError) as exc:
        print(f"error: cannot read the pytest report at {report_path}: {exc}", file=sys.stderr)
        return 1

    cases = list(tree.iter("testcase"))
    names = [case.get("name", "") for case in cases]

    if len(cases) < _MINIMUM_CASES:
        print(
            f"FAIL: gate 9 collected {len(cases)} test(s). The required-path file "
            f"has been renamed, moved, or emptied. `pytest` exits 0 on an empty "
            f"collection, so this gate would otherwise have certified nothing.",
            file=sys.stderr,
        )
        return 1

    skipped = [case.get("name", "") for case in cases if case.find("skipped") is not None]
    if skipped:
        print(
            f"FAIL: {len(skipped)} required-path test(s) SKIPPED. Section 23 states "
            f"these are never skippable:",
            file=sys.stderr,
        )
        for name in skipped:
            print(f"  {name}", file=sys.stderr)
        return 1

    broken = [
        case.get("name", "")
        for case in cases
        if case.find("failure") is not None or case.find("error") is not None
    ]
    if broken:
        print(f"FAIL: {len(broken)} required-path test(s) failed:", file=sys.stderr)
        for name in broken:
            print(f"  {name}", file=sys.stderr)
        return 1

    missing = [
        label
        for label, markers in _REQUIRED_PATHS
        if not any(marker in name.lower() for marker in markers for name in names)
    ]
    if missing:
        print(
            "FAIL: the collected tests cover no test for: " + ", ".join(missing) + ".\n"
            "Both of Section 23's required paths must be exercised by this gate.",
            file=sys.stderr,
        )
        return 1

    print(f"ok: {len(cases)} required-path tests ran, none skipped, both paths covered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
