"""Item 11.31 (2026-09-21): the mutation harness for the depth directives.

This repository's standard is that every control carries a populate-check
AND a mutation arm, because an arm that cannot go red is not an arm. Build
phases 4.3, 4.7, 4.11, 4.15 and 4.16 each shipped a vacuous assertion that
reading did not catch and mutation did, so the mutation arm is the control
that catches the control.

The arms in `test_answer_quality.py` assert properties of
`_DEPTH_DIRECTIVES["plain_language"]`. This module proves those arms fail
when the directive loses the property, by running them against the exact
directive item 11.31 replaced.

Why the old directive rather than an invented broken one: a mutation whose
input never existed proves only that the assertion reads its argument. This
one proves the arms would have caught a REVERT, which is the change most
likely to happen by accident when someone resolves a merge conflict in this
dict.

This file was briefly named `conftest_mutation.py`, which pytest does not
collect, so the arm would have existed and never run. That is this
repository's most-recorded failure shape, a confident sentence describing a
check that is not there, and it is written down rather than quietly renamed.
The name is now `test_*` so the mutation runs in CI like any other arm.

It mutates a module global the neighbouring arms read, so `run_mutation`
restores the real directive in a `finally` block and the collected test
asserts the restore happened. Without that assertion a failure here would
poison every arm that runs after it.

Depends on:
    - system_03_search_agent.synthesis.findings (_DEPTH_DIRECTIVES)
    - tests/system_03_search_agent/synthesis/test_answer_quality.py
"""

from __future__ import annotations

import importlib.util
import pathlib

from system_03_search_agent.synthesis import findings as findings_module

# The `plain_language` directive exactly as it stood before item 11.31, with
# its 120-word cap and its three fixed paragraphs. Kept verbatim: the point
# is to mutate to a real previous state, not to a plausible one.
_DIRECTIVE_BEFORE_11_31 = (
    "AUDIENCE DEPTH: plain_language. Write for a reader with no biology "
    "background, about 120 words, in three short paragraphs separated by "
    "a blank line: first the direct answer, then what it means, then one "
    "or two sentences of background. Use everyday words. Every sentence "
    "must restate a finding and end with that finding's marker, because "
    "a sentence without one is deleted. No headings, no lists, no tables."
)

#: The arms that must go red when the directive is reverted. Named rather
#: than discovered by prefix, so deleting an arm makes this list wrong and
#: visible instead of silently shrinking what gets mutated.
ARMS_THAT_MUST_GO_RED = (
    "test_plain_language_is_bounded_by_shape_rather_than_by_a_word_count",
    "test_plain_language_keeps_every_sentence_sourced_and_asks_for_no_paraphrase",
    "test_the_two_depths_ask_for_materially_different_shapes",
)


def _load_answer_quality_module():
    """Load the sibling test module by path.

    By path rather than by import, because inserting the tests directory on
    `sys.path` makes `system_03_search_agent` resolve to the test package of
    the same name and the real module then fails to import. That happened
    while writing this harness and is recorded so it is not repeated.
    """
    path = pathlib.Path(__file__).with_name("test_answer_quality.py")
    spec = importlib.util.spec_from_file_location("_answer_quality_for_mutation", path)
    assert spec and spec.loader, f"could not load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_mutation() -> dict[str, bool]:
    """Revert the directive, run each named arm, report which went red.

    Returns a mapping of arm name to "went red". Restores the real directive
    in a `finally` block, so a failing arm cannot leave the module global
    mutated for whatever pytest runs next.
    """
    module = _load_answer_quality_module()
    directives = findings_module._DEPTH_DIRECTIVES
    real = directives["plain_language"]
    went_red: dict[str, bool] = {}
    try:
        directives["plain_language"] = _DIRECTIVE_BEFORE_11_31
        for name in ARMS_THAT_MUST_GO_RED:
            arm = getattr(module, name)
            try:
                arm()
                went_red[name] = False
            except AssertionError:
                went_red[name] = True
    finally:
        directives["plain_language"] = real
    return went_red


def test_every_named_arm_goes_red_when_the_directive_is_reverted() -> None:
    """The one collected test here, and the whole point of the module."""
    results = run_mutation()

    assert set(results) == set(ARMS_THAT_MUST_GO_RED), (
        "populate-check: an arm named here was not run, so this harness "
        f"would pass while covering less than it claims: {sorted(results)}"
    )
    vacuous = [name for name, red in results.items() if not red]
    assert not vacuous, (
        "these arms still passed against the pre-11.31 directive, so they do "
        f"not actually pin what item 11.31 changed: {vacuous}"
    )

    # And the real directive must be back, or this harness has poisoned
    # every arm that runs after it.
    assert "as much as they need to understand it and no more" in (
        findings_module._DEPTH_DIRECTIVES["plain_language"]
    ), "the real directive was not restored after mutation"
