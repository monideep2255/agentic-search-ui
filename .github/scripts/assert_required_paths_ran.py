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

import ast
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# The module the required paths live in. Anchoring on IDENTITY rather than on
# test names is the correction F-4.14-A-06 forced.
#
# The first version matched test NAMES against substrings like "citation" and
# "refus", and the adversary satisfied it completely with two `assert True`
# tests called `test_the_citation_widget_renders_a_blue_border` and
# `test_the_settings_page_refuses_to_scroll_horizontally`. It reported
# "both paths covered". A name is not evidence of what a test does, and a
# substring of a name is not even evidence of the name.
_REQUIRED_MODULE = "test_required_paths"

# The file must still exercise the two properties, checked by reading the SOURCE
# for the symbols that make the assertions real, not by reading test names. If
# the file stopped importing the refusal text or the grounding entry point, its
# tests cannot be testing cite-or-refuse whatever they are called.
_REQUIRED_SYMBOLS = (
    ("the refusal text", "REFUSAL_TEXT"),
    ("the grounding entry point", "ground_claim"),
)

# The file carried 27 tests when this gate was written. A floor well below that
# still catches a file gutted to a couple of stubs, while leaving room for
# ordinary deletion. Raise it if the file grows substantially; never lower it to
# make a red build green.
_MINIMUM_CASES = 15


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


def _symbol_is_used(source: str, symbol: str) -> bool:
    """Is `symbol` genuinely imported or referenced in CODE, not just mentioned?

    F-4.14-RV-09. The first version asked `if symbol not in source`, a plain
    substring test over the whole file. A re-verifier replaced the required-path
    file with sixteen `assert True` tests whose DOCSTRING happened to name
    `REFUSAL_TEXT` and `ground_claim`, and this script reported "the source still
    exercises both required paths".

    A docstring is text. Parsing the module and looking for the name as an
    imported alias or a loaded identifier asks the question that was meant:
    does the code touch this symbol. A comment, a string, or a docstring cannot
    satisfy an `ast.Name` or an `ast.alias`.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # An unparseable required-path file is a failure, never a pass.
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == symbol:
            return True
        if isinstance(node, ast.Attribute) and node.attr == symbol:
            return True
        if isinstance(node, ast.alias) and symbol in (node.name, node.asname):
            return True
    return False


def _module_source_path(cases: list[ET.Element]) -> Path | None:
    """Map the JUnit `classname` back to the file on disk.

    pytest writes `classname` as a dotted module path, for example
    `tests.system_03_search_agent.synthesis.test_required_paths`, so the file is
    that path with the dots turned into separators. Derived from the report
    rather than hardcoded, so moving the file cannot leave this check pointed at
    a stale path while the gate keeps passing.
    """
    for case in cases:
        classname = case.get("classname", "")
        if _REQUIRED_MODULE in classname:
            parts = classname.split(".")
            # Trim any trailing class name, which pytest appends for tests
            # defined inside a class. The module is the segment named for the
            # file itself.
            while parts and parts[-1] != _REQUIRED_MODULE:
                parts.pop()
            if parts:
                return Path(*parts).with_suffix(".py")
    return None


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

    # Identity, not naming. Every case must come from the required-paths module,
    # so a gate accidentally (or deliberately) pointed at some other file fails
    # instead of certifying it.
    foreign = sorted(
        {
            case.get("classname", "")
            for case in cases
            if _REQUIRED_MODULE not in case.get("classname", "")
        }
    )
    if foreign:
        print(
            f"FAIL: this gate ran tests from outside the required-path module "
            f"({_REQUIRED_MODULE}): " + ", ".join(foreign[:5]) + ".\n"
            "Gate 9 certifies Section 23's two required paths, not whatever file "
            "it happens to have been pointed at.",
            file=sys.stderr,
        )
        return 1

    # The properties themselves, read out of the SOURCE rather than inferred
    # from test names. A file whose tests no longer reach the refusal text or the
    # grounding entry point is not testing cite-or-refuse, whatever it calls its
    # functions.
    source_path = _module_source_path(cases)
    if source_path is None or not source_path.exists():
        print(
            f"FAIL: cannot locate the source of {_REQUIRED_MODULE} to confirm it "
            f"still exercises both required paths. Looked for: {source_path}",
            file=sys.stderr,
        )
        return 1
    source = source_path.read_text(encoding="utf-8")
    absent = [label for label, symbol in _REQUIRED_SYMBOLS if not _symbol_is_used(source, symbol)]
    if absent:
        print(
            f"FAIL: {source_path} no longer references " + ", ".join(absent) + ".\n"
            "Its tests cannot be exercising Section 23's required paths without "
            "them, regardless of how many of them pass.",
            file=sys.stderr,
        )
        return 1

    print(
        f"ok: {len(cases)} required-path tests ran from {_REQUIRED_MODULE}, none "
        f"skipped, and the source still exercises both required paths."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
