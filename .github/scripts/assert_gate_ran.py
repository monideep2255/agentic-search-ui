#!/usr/bin/env python3
"""Fail a gate that exited 0 having executed nothing.

Build phase 4.14, finding F-4.14-A-03.

`pytest` exits 0 in three situations and only one of them is a pass:

  1. Tests ran and passed.
  2. Every test was skipped.
  3. Nothing was collected at all.

On GitHub all three render identically: a green check. That is the single
confusion this whole phase exists to remove, so any gate whose verdict depends
on tests having actually executed pipes its report through here.

The case that forced this into existence is worth stating, because it is the
opposite of what anyone would predict. Gate 5's integration suite is
network-gated: with NO credential it reports NOT RUN honestly, with a warning.
With a credential present but pointing at anything that does not answer, its
arms skip, `pytest` exits 0 with zero passed, and the honest warning is skipped
because the credential exists. Adding the secret would have made the gate
QUIETER instead of stricter, permanently.

Usage:
    python .github/scripts/assert_gate_ran.py <junit-xml> [--min-passed N]
                                              [--label TEXT]

Exit codes:
    0  at least `--min-passed` tests passed
    1  fewer did, or the report could not be read

Depends on:
    - Nothing outside the standard library.

Reads:
    - The JUnit XML written by `pytest --junitxml`.

Writes:
    - Nothing. Prints to stdout and stderr, and emits a GitHub `::warning`
      annotation on failure so the reason is visible without opening the log.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET


def _parse_report(report_path: str) -> ET.Element:
    """Parse the JUnit report, rejecting entity declarations before parsing.

    Same reasoning as the sibling scripts in this directory: stdlib
    ElementTree does not resolve external entities, and rejecting `<!ENTITY`
    before parsing closes the internal-expansion vector that remains. Neither
    `lxml` nor `defusedxml` is a dependency of this project and this script
    does not add one.
    """
    with open(report_path, "rb") as handle:
        raw = handle.read()
    if b"<!ENTITY" in raw.upper():
        raise ValueError("the pytest report declares an XML entity, which pytest never emits")
    return ET.fromstring(raw)


def tally(report: ET.Element) -> tuple[int, int, int]:
    """Return (passed, skipped, total) for the report."""
    total = skipped = 0
    for case in report.iter("testcase"):
        total += 1
        if case.find("skipped") is not None:
            skipped += 1
    broken = sum(
        1
        for case in report.iter("testcase")
        if case.find("failure") is not None or case.find("error") is not None
    )
    return total - skipped - broken, skipped, total


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    parser.add_argument("--min-passed", type=int, default=1)
    parser.add_argument("--label", default="this gate")
    args = parser.parse_args(argv[1:])

    try:
        report = _parse_report(args.report)
    except (OSError, ET.ParseError, ValueError) as exc:
        print(f"error: cannot read the pytest report at {args.report}: {exc}", file=sys.stderr)
        return 1

    passed, skipped, total = tally(report)

    if passed < args.min_passed:
        message = (
            f"{args.label} exited without executing anything: {passed} passed, "
            f"{skipped} skipped, {total} collected. A green check here would mean "
            f"'could not run', not 'verified'."
        )
        print(f"FAIL: {message}", file=sys.stderr)
        print(f"::warning title=Gate ran nothing::{message}")
        return 1

    print(f"ok: {args.label} executed {passed} test(s) ({skipped} skipped, {total} collected).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
