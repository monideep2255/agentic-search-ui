#!/usr/bin/env python3
"""Fail CI when a test skipped because it could not reach the database.

Build phase 4.14, finding F-4.14-03. This is the half of gate 4 that makes
gate 4 mean anything.

The problem it solves, measured rather than imagined. Every database-backed
test in this repository probes the connection and skips when it fails, for
example `tests/system_03_search_agent/auth/test_router.py`:

    pytest.skip("set USER_DB_URL and ensure the server is running to run
                 this suite")

On the machine where build phase 4.14 was written, PostgreSQL was running, so
those tests RAN and were counted inside "3947 passed". A GitHub Actions runner
has no PostgreSQL. The identical `pytest -m "not integration"` command there
would print an identical, confident green while silently skipping every one of
them, and nothing in its summary line distinguishes "passed" from "was never
executed".

So the workflow runs a PostgreSQL service, and this script proves the service
is actually being reached instead of trusting that it is. Without it the
service block is an assumption; with it, a broken service URL fails the job
loudly and names itself.

Deliberately NOT a check on the total skip count. The suite has 136 skips that
are correct and wanted: the `RUN_PREMISE_GATE=1` arms that need a real model
key, real money, and live network reach. Pinning a total would fail every time
someone legitimately adds one, which is how a gate earns being switched off.
This matches on the REASON instead, so it stays quiet about the skips that are
supposed to be there and loud about the ones that are not.

Usage:
    python .github/scripts/assert_no_db_skips.py <junit-xml-path>

Exit codes:
    0  no test skipped for a database reason
    1  at least one did, or the report could not be read

Depends on:
    - Nothing outside the standard library, so it runs before any install step
      would have to succeed.

Reads:
    - The JUnit XML written by `pytest --junitxml`.

Writes:
    - Nothing. Prints to stdout and stderr only.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET

# Matched against the skip MESSAGE, lowercased. Each substring is a phrase that
# only appears when a test stood down because a database was unreachable.
#
# Substrings rather than exact strings on purpose: the reasons are written by
# hand in a dozen test files and none of them is obliged to phrase it the same
# way as the next. An exact-match list would be the enumerate-the-instances
# shape `bossman-mode`'s Rule 2 rejects, and it would go quiet the first time
# somebody wrote the same skip in slightly different words.
_DB_SKIP_MARKERS = (
    "user_db_url",
    "ensure the server is running",
    "database is not reachable",
    "could not connect to the database",
    "postgres is not running",
    "postgresql is not running",
)


def _parse_report(report_path: str) -> ET.Element:
    """Parse the JUnit report, rejecting entity declarations before parsing.

    This mirrors the reasoning already established in
    `src/system_03_search_agent/tools/ncbi_transport.py`, and it is applied
    here even though the input is this job's own pytest output written seconds
    earlier rather than anything untrusted. The two facts that matter:

      - Classic XXE: stdlib ElementTree does not resolve external entities or
        fetch external DTDs, so it is not vulnerable the way an unconfigured
        `lxml.etree.XMLParser` is.
      - Billion laughs: stdlib ElementTree does NOT defend against this, and it
        needs an `<!ENTITY` declaration to exist at all. Rejecting that
        substring before the parser sees the body closes it.

    Neither `lxml` nor `defusedxml` is a dependency of this project, and this
    script deliberately does not add one: it runs before the install step in
    some contexts, and a new dependency is a supply-chain review, never a
    silent pull-in from one parsing helper.
    """
    with open(report_path, "rb") as handle:
        raw = handle.read()
    if b"<!ENTITY" in raw.upper():
        raise ValueError(
            "the pytest report declares an XML entity, which pytest never emits"
        )
    return ET.fromstring(raw)


def _skip_messages(report_path: str) -> list[tuple[str, str]]:
    """Return (test id, skip message) for every skipped test in the report."""
    tree = _parse_report(report_path)
    found: list[tuple[str, str]] = []
    for case in tree.iter("testcase"):
        for skipped in case.findall("skipped"):
            test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
            message = (skipped.get("message") or "") + " " + (skipped.text or "")
            found.append((test_id, message.strip()))
    return found


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <junit-xml-path>", file=sys.stderr)
        return 1

    report_path = argv[1]
    try:
        skips = _skip_messages(report_path)
    except (OSError, ET.ParseError, ValueError) as exc:
        # A missing or unparseable report is a FAILURE, never a pass. If the
        # report is not there, this script verified nothing, and "I could not
        # verify X" is a fail.
        print(f"error: cannot read the pytest report at {report_path}: {exc}", file=sys.stderr)
        return 1

    offenders = [
        (test_id, message)
        for test_id, message in skips
        if any(marker in message.lower() for marker in _DB_SKIP_MARKERS)
    ]

    if offenders:
        print(
            f"FAIL: {len(offenders)} test(s) skipped because the database was "
            f"unreachable. The unit gate cannot certify what it did not run.",
            file=sys.stderr,
        )
        for test_id, message in offenders[:20]:
            print(f"  {test_id}\n    {message}", file=sys.stderr)
        if len(offenders) > 20:
            print(f"  ... and {len(offenders) - 20} more", file=sys.stderr)
        print(
            "\nCheck that the `postgres` service in .github/workflows/ci.yml is "
            "healthy and that USER_DB_URL points at it.",
            file=sys.stderr,
        )
        return 1

    print(
        f"ok: {len(skips)} skipped test(s) in the report, none of them for a "
        f"database reason."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
