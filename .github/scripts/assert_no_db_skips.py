#!/usr/bin/env python3
"""Fail CI when a test stood down for a reason nobody sanctioned.

Build phase 4.14, finding F-4.14-03, REWRITTEN in the same phase after
F-4.14-A-01 and F-4.14-A-02 showed the first version did not work.

The problem this exists to solve. Test files in this repository stand down
politely when a dependency is missing, rather than failing:

    pytest.skip("... set USER_DB_URL and ensure the server is running ...")

On a developer machine with PostgreSQL running those tests EXECUTE and are
counted inside "3947 passed". A GitHub Actions runner has no PostgreSQL, so the
identical `pytest -m "not integration"` prints an identical, confident green
having executed none of them. Nothing in pytest's summary line distinguishes
"passed" from "was never run". So the workflow runs a PostgreSQL service, and
this script proves the service was actually REACHED rather than assuming it.

WHY THIS IS AN ALLOWLIST, AND WHY THE FIRST VERSION WAS WRONG.

The first version of this script listed the phrasings a database skip might
use and failed when it saw one. That is the enumerate-the-instances shape
`bossman-mode`'s Rule 2 forbids, its docstring claimed it was not that shape,
and it was wrong in the most embarrassing way available: it MISSED a skip live
in this repository at the time it was written.

    tests/system_03_search_agent/adapters/web_sse/test_phase_4_10_premise.py

skips with "user database unreachable at ...", which matched none of the six
listed phrasings. Pointed at a dead database, 36 tests vanished and the script
printed "ok: 36 skipped test(s) ... none of them for a database reason" and
exited 0. The entire guest-allowance premise gate disappeared behind a green
check. Every attempt to fix that by adding a seventh phrasing loses to the
eighth.

So the direction is inverted. This script now DENIES BY DEFAULT: every skip
must match a reason someone deliberately sanctioned, and anything else fails
the build. A new skip phrasing cannot evade it, because it is not trying to
recognise bad skips. It recognises the small, closed, deliberately-curated set
of good ones.

That means this gate fails when someone adds a legitimate new kind of skip.
That is the intended direction, not a defect: the correct response is to add
it to `_SANCTIONED_SKIPS` below on purpose, in a commit someone reviews, which
is exactly the decision that should not happen silently.

Usage:
    python .github/scripts/assert_no_db_skips.py <junit-xml-path>

Exit codes:
    0  every skip in the report was a sanctioned one
    1  at least one was not, or the report could not be read, or it was empty

Depends on:
    - Nothing outside the standard library, so it runs regardless of whether
      any install step succeeded.

Reads:
    - The JUnit XML written by `pytest --junitxml`.

Writes:
    - Nothing. Prints to stdout and stderr only.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET

# A report with fewer than this many test cases is not a real unit run, and the
# absence of unsanctioned skips in it means nothing. This is the populate-check:
# without it, a truncated or empty report exits 0 saying "ok" (F-4.14-A-11).
# Set well below the real figure (about 4100) so an ordinary addition or
# deletion never trips it, and well above zero so a collection failure does.
_MINIMUM_TESTCASES = 500

# The sanctioned skips, each a (reason, pattern) pair matched case-insensitively
# against the skip message. Deny-by-default: anything not matched here fails.
#
# Adding a row is a deliberate act. Do not add one to make a red build go green
# without establishing that the skip is genuinely a sanctioned opt-in rather
# than a dependency CI was supposed to provide and did not.
_SANCTIONED_SKIPS: tuple[tuple[str, str], ...] = (
    (
        "the live premise-gate opt-in",
        # The ~104 arms that need a real model key, real money, and live network
        # reach. Deliberately out of CI: a gate that spends real budget on every
        # pull request is a gate somebody switches off.
        r"RUN_PREMISE_GATE",
    ),
    (
        "a live Layer 1 graph or model credential CI does not hold",
        # Section 24 makes the integration suite a network-gated job precisely
        # because this credential cannot be given to a fork's pull request.
        r"live graph|layer 1 graph|graph tunnel|graph service|real model key",
    ),
    (
        "a known open finding, deliberately skipped and tracked",
        r"F-2\.2-T-01-residual",
    ),
)

# Purely to make the failure message useful. Matching this changes nothing about
# the verdict, which is already decided by the allowlist above.
_LIKELY_DATABASE = re.compile(
    r"database|postgres|user_db_url|psycopg|sqlalchemy", re.IGNORECASE
)


def _parse_report(report_path: str) -> ET.Element:
    """Parse the JUnit report, rejecting entity declarations before parsing.

    This mirrors the reasoning already established in
    `src/system_03_search_agent/tools/ncbi_transport.py`, and it is applied here
    even though the input is this job's own pytest output written seconds
    earlier rather than anything untrusted. The two facts that matter:

      - Classic XXE: stdlib ElementTree does not resolve external entities or
        fetch external DTDs, so it is not vulnerable the way an unconfigured
        `lxml.etree.XMLParser` is.
      - Billion laughs: stdlib ElementTree does NOT defend against this, and it
        needs an `<!ENTITY` declaration to exist at all. Rejecting that
        substring before the parser sees the body closes it.

    Neither `lxml` nor `defusedxml` is a dependency of this project, and this
    script deliberately does not add one.
    """
    with open(report_path, "rb") as handle:
        raw = handle.read()
    if b"<!ENTITY" in raw.upper():
        raise ValueError("the pytest report declares an XML entity, which pytest never emits")
    return ET.fromstring(raw)


def sanctioned_reason(message: str) -> str | None:
    """Return the name of the sanctioning rule, or None if nothing sanctions it."""
    for reason, pattern in _SANCTIONED_SKIPS:
        if re.search(pattern, message, re.IGNORECASE):
            return reason
    return None


def classify(report: ET.Element) -> tuple[int, list[tuple[str, str]], dict[str, int]]:
    """Return (testcase count, unsanctioned skips, sanctioned counts by reason)."""
    total = 0
    unsanctioned: list[tuple[str, str]] = []
    sanctioned: dict[str, int] = {}
    for case in report.iter("testcase"):
        total += 1
        for skipped in case.findall("skipped"):
            test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
            message = ((skipped.get("message") or "") + " " + (skipped.text or "")).strip()
            reason = sanctioned_reason(message)
            if reason is None:
                unsanctioned.append((test_id, message))
            else:
                sanctioned[reason] = sanctioned.get(reason, 0) + 1
    return total, unsanctioned, sanctioned


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <junit-xml-path>", file=sys.stderr)
        return 1

    report_path = argv[1]
    try:
        report = _parse_report(report_path)
    except (OSError, ET.ParseError, ValueError) as exc:
        # A missing or unparseable report is a FAILURE, never a pass. If the
        # report is not there, this script verified nothing, and "I could not
        # verify X" is a fail.
        print(f"error: cannot read the pytest report at {report_path}: {exc}", file=sys.stderr)
        return 1

    total, unsanctioned, sanctioned = classify(report)

    # The populate-check, before any verdict. An empty report has no
    # unsanctioned skips in it, and that fact is worth nothing.
    if total < _MINIMUM_TESTCASES:
        print(
            f"FAIL: the report contains {total} test cases, fewer than the "
            f"{_MINIMUM_TESTCASES} expected of a real unit run. Collection failed, "
            f"the report is truncated, or the wrong file was passed. This script "
            f"verified nothing, which is a failure and not a pass.",
            file=sys.stderr,
        )
        return 1

    if unsanctioned:
        looks_like_db = [item for item in unsanctioned if _LIKELY_DATABASE.search(item[1])]
        print(
            f"FAIL: {len(unsanctioned)} test(s) skipped for a reason nothing "
            f"sanctions. The gate cannot certify what it did not run.",
            file=sys.stderr,
        )
        for test_id, message in unsanctioned[:20]:
            print(f"  {test_id}\n    {message}", file=sys.stderr)
        if len(unsanctioned) > 20:
            print(f"  ... and {len(unsanctioned) - 20} more", file=sys.stderr)
        if looks_like_db:
            print(
                f"\n{len(looks_like_db)} of these mention a database. Check that the "
                f"`postgres` service in .github/workflows/ci.yml is healthy, that "
                f"USER_DB_URL points at it, and that `alembic upgrade head` ran.",
                file=sys.stderr,
            )
        print(
            "\nIf one of these is genuinely a sanctioned opt-in rather than a "
            "dependency CI should have provided, add it to _SANCTIONED_SKIPS in "
            "this file deliberately, in a commit someone reviews.",
            file=sys.stderr,
        )
        return 1

    summary = ", ".join(f"{count} {reason}" for reason, count in sorted(sanctioned.items()))
    print(
        f"ok: {total} test cases, every skip sanctioned"
        + (f" ({summary})" if summary else " (no skips at all)")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
