"""Mutation harness for the build phase 5.3 premise gate.

Every arm in `test_phase_5_3_premise.py` is paired here with a mutation that
deletes the control it names. The harness APPLIES each mutation to the real
source, runs the arms that should notice, asserts they go RED, and restores
from a verified backup.

## Why this file exists rather than a comment beside each arm

Build phase 4.3 wrote 42 gate arms with the mutation that should turn each one
red named in a comment beside it. All 42 passed. Nobody had RUN those
mutations, and five arms turned out to be vacuous: each stayed green with the
very control it names deleted. Naming a mutation is not applying one.

Build phase 4.15 turned that into the rule this file follows: ADD THE MUTATION
CASE IN THE SAME EDIT AS THE ARM. That rule replaced three separate
completeness claims ("every arm is covered") that were each false when written,
one of them written inside the fix for the previous one. So this file makes NO
completeness claim. It lists the mutations it applies. Whether an arm is
missing from that list is answered by reading it, not by trusting a sentence.

## The harness's own failure mode, guarded

A string replacement that matches nothing is a silent no-op, and build phase
4.8 shipped a vacuous gate exactly that way: the `.replace()` meant to insert
an assertion had the wrong indentation, matched nothing, reported no error, and
the gate passed unconditionally. So `_mutate` asserts the match count before
writing, and `test_harness_rejects_a_mutation_that_does_not_apply` proves that
guard fires.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LOADER = REPO_ROOT / "src" / "system_03_search_agent" / "eval" / "dataset.py"
BUILDER = REPO_ROOT / "eval" / "golden" / "build_dataset.py"
GATE = "tests/system_03_search_agent/eval/test_phase_5_3_premise.py"


@dataclass(frozen=True)
class Mutation:
    """One deleted control, and the arms that must notice it is gone."""

    name: str
    path: Path
    old: str
    new: str
    expect_red: tuple[str, ...]


MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        name="M1: hardcode the tool roster instead of deriving it",
        path=LOADER,
        old="ALLOWED_MUST_REACH = frozenset(\n    schema[\"name\"] for schema in REGISTERED_TOOL_SCHEMAS\n)",
        new="ALLOWED_MUST_REACH = frozenset({\"cypher_query\", \"ncbi_efetch\"})",
        expect_red=(
            "test_p1_tool_roster_is_derived_from_the_registry_not_retyped",
            "test_p2_every_registered_tool_is_accepted_in_must_reach",
        ),
    ),
    Mutation(
        name="M2: accept any tool name in must_reach",
        path=LOADER,
        old="    unknown = [name for name in raw if name not in ALLOWED_MUST_REACH]",
        new="    unknown = []",
        expect_red=("test_p2_unknown_tool_in_must_reach_is_refused",),
    ),
    Mutation(
        name="M3: stop type-checking must_reach",
        path=LOADER,
        old="    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):",
        new="    if False:",
        expect_red=("test_p2_must_reach_must_be_a_list_of_strings",),
    ),
    Mutation(
        name="M4: stop requiring live_only's keys",
        path=LOADER,
        old="    for name in _REQUIRED_LIVE_ONLY_FIELDS:",
        new="    for name in ():",
        expect_red=("test_p3_live_only_missing_any_required_key_is_refused",),
    ),
    Mutation(
        name="M5: let a live_only fact come from the agent under test",
        path=LOADER,
        old="    if any(token in observed_from.lower() for token in _REFUSED_AUTHORED_FROM):",
        new="    if False:",
        expect_red=("test_p3_live_only_may_not_be_authored_from_agent_output",),
    ),
    Mutation(
        name="M6: make must_reach mandatory, breaking every v1 row",
        path=LOADER,
        old="    if raw is None:\n        return []",
        new="    if raw is None:\n        raise DatasetValidationError(f\"row {row_id}: must_reach is required\")",
        expect_red=(
            "test_p4_both_fields_are_optional_so_every_existing_row_stays_valid",
            "test_p4_the_shipped_dataset_loads_at_schema_version_2",
        ),
    ),
    Mutation(
        # Filed as a BAD MUTATION first and kept rather than deleted. It
        # originally named an arm that never reads the version, so it stayed
        # green for a reason that had nothing to do with the control. The
        # diagnosis found a real gap: no arm read the builder's constant at
        # all, only its output. The repair was a NEW ARM, not a retargeted
        # assertion, which is why this case now names one that did not exist
        # when the mutation was written.
        name="M7: revert the builder's schema version, desyncing it from the file",
        path=BUILDER,
        old="_SCHEMA_VERSION = 2",
        new="_SCHEMA_VERSION = 1",
        expect_red=(
            "test_p4_the_builder_and_the_shipped_file_agree_on_the_schema_version",
        ),
    ),
    Mutation(
        name="M8: make the graph absence check a no-op",
        path=BUILDER,
        old="    if value.casefold() in haystack:",
        new="    if False:",
        expect_red=("test_p5_a_graph_satisfiable_fact_is_refused_by_the_builder",),
    ),
    Mutation(
        name="M9: make the graph absence check refuse everything",
        path=BUILDER,
        old="    if value.casefold() in haystack:",
        new="    if True:",
        expect_red=("test_p5_control_a_fact_the_graph_lacks_is_accepted",),
    ),
    Mutation(
        name="M10: import the agent under test into the dataset builder",
        path=BUILDER,
        old="from eval.golden.question_set import QUESTION_SPECS",
        new=(
            "from eval.golden.question_set import QUESTION_SPECS\n"
            "from system_03_search_agent.eval.dataset import GOLDEN_DATASET_PATH  "
            "# noqa: F401"
        ),
        expect_red=("test_p6_the_dataset_builder_does_not_import_the_agent_it_grades",),
    ),
    Mutation(
        name="M11: drop must_reach on its way into the row",
        path=BUILDER,
        old='    must_reach = list(spec.get("must_reach") or [])',
        new="    must_reach = []",
        expect_red=("test_p7_the_builder_carries_must_reach_into_the_row",),
    ),
    Mutation(
        name="M12: emit a missing key instead of an empty list",
        path=BUILDER,
        old='        "must_reach": must_reach,',
        new='        "must_reach": must_reach or None,',
        expect_red=(
            "test_p7_a_spec_without_must_reach_builds_an_empty_list_not_a_missing_key",
        ),
    ),
)


def _collect_count(node_names: tuple[str, ...]) -> int:
    """How many arms the selector actually matches, MEASURED not assumed.

    Closes F-5.3-A-11. The case below decided on a non-zero exit code, and
    pytest exits 5 when `-k` matches NOTHING, so a mutation naming a
    misspelled, renamed or deleted arm passed while asserting nothing about
    any control. The adversary demonstrated it against this harness with a
    real deleted control and a one-letter typo: "HARNESS VERDICT: PASSED,
    proving nothing". Arm renames are ordinary maintenance, so that was a live
    decay path in the instrument whose whole job is proving other arms are not
    vacuous.
    """
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest", GATE,
            "-k", " or ".join(node_names), "--collect-only", "-q", "--no-header",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r"^(\d+)/?\d* tests? collected", result.stdout, re.MULTILINE)
    return int(match.group(1)) if match else 0


def _all_selected_arms_skipped(result: subprocess.CompletedProcess) -> bool:
    """True when every arm the selector matched SKIPPED rather than ran.

    A skip is not a pass and it is not a red either: it is NOT MEASURABLE HERE.
    Conflating skip with pass made this harness report a FALSE DIAGNOSIS on CI,
    where no graph credential exists: the live P5 arms skipped, pytest exited
    0, and the harness announced the arms "stayed GREEN with the control they
    name deleted, so they are vacuous". They had not stayed green. They had not
    run. CI caught it; no local run could, because the graph is reachable here.
    """
    return bool(re.search(r"^\d+ skipped", result.stdout, re.MULTILINE)) and not (
        re.search(r"\d+ passed", result.stdout) or re.search(r"\d+ failed", result.stdout)
    )


def _run_arms(node_names: tuple[str, ...]) -> subprocess.CompletedProcess:
    selector = " or ".join(node_names)
    return subprocess.run(
        [sys.executable, "-m", "pytest", GATE, "-k", selector, "-q", "--no-header"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda m: m.name.split(":")[0])
def test_each_arm_goes_red_under_its_own_mutation(mutation: Mutation) -> None:
    original = mutation.path.read_text()

    occurrences = original.count(mutation.old)
    assert occurrences == 1, (
        f"{mutation.name}: expected its target text exactly once in "
        f"{mutation.path.name}, found {occurrences}. A replacement that matches "
        "nothing is a silent no-op and would make this whole case vacuous."
    )

    # Checked PER NAME rather than against the total. A parametrized arm is one
    # name and several collected tests (M4's target is one name over four keys),
    # so an equality check on the total is wrong. What must hold is that no name
    # matches nothing: that is the exit-5 hole, and one dead name hiding behind
    # a sibling's four collected cases is exactly what a total would miss.
    for name in mutation.expect_red:
        assert _collect_count((name,)) > 0, (
            f"{mutation.name}: expect_red names {name!r}, which matches NO test. "
            "pytest exits 5 when `-k` selects nothing, and 5 is non-zero, so this "
            "case would PASS while covering no control at all. Arm renames are "
            "ordinary maintenance, so this is a live decay path."
        )

    try:
        mutation.path.write_text(original.replace(mutation.old, mutation.new))
        result = _run_arms(mutation.expect_red)

        if _all_selected_arms_skipped(result):
            pytest.skip(
                f"{mutation.name}: every arm it targets SKIPPED, so this case is "
                "not measurable in this environment (the live-graph arms need a "
                "graph credential CI does not hold). Skipped rather than passed, "
                "and never reported as vacuity: the arms did not stay green, "
                "they did not run."
            )

        # Exit 1 SPECIFICALLY, a real assertion failure. Non-zero also covers
        # exit 5 (nothing collected) and exit 4 (usage error), neither of which
        # is evidence that a control fired.
        assert result.returncode == 1, (
            f"{mutation.name}: expected exit 1, a real assertion failure, from "
            f"arms {list(mutation.expect_red)} with the control they name "
            f"deleted; got exit {result.returncode}. Exit 0 means those arms are "
            "vacuous; any other code means the run never reached an assertion.\n"
            f"{result.stdout[-2000:]}"
        )
    finally:
        mutation.path.write_text(original)

    # Restoration is verified, not assumed. A harness that leaves a mutated
    # file behind turns one failing case into a corrupted working tree.
    assert mutation.path.read_text() == original


def test_harness_rejects_a_mutation_that_does_not_apply() -> None:
    """The guard against the silent no-op that made build phase 4.8's gate
    unconditionally green. Without this, a mutation whose target text drifts
    would report a pass while changing nothing."""
    stale = Mutation(
        name="M0: a target that no longer exists",
        path=LOADER,
        old="this text is deliberately not present in the loader",
        new="irrelevant",
        expect_red=("test_p1_tool_roster_is_derived_from_the_registry_not_retyped",),
    )
    with pytest.raises(AssertionError, match="found 0"):
        test_each_arm_goes_red_under_its_own_mutation(stale)


def test_harness_rejects_a_mutation_naming_an_arm_that_does_not_exist() -> None:
    """The guard for F-5.3-A-11, proven rather than asserted.

    Before it, this exact case PASSED: the arm name carries one extra letter,
    `-k` matches nothing, pytest exits 5, and `returncode != 0` was satisfied
    while no control was exercised.
    """
    bogus = Mutation(
        name="MX: a real control deleted, but the named arm is a typo",
        path=LOADER,
        old="    unknown = [name for name in raw if name not in ALLOWED_MUST_REACH]",
        new="    unknown = []",
        expect_red=("test_p2_unknown_tool_in_must_reach_is_refusedd",),
    )
    with pytest.raises(AssertionError, match="matches NO test"):
        test_each_arm_goes_red_under_its_own_mutation(bogus)

    # The control was never written to disk, because the guard runs BEFORE the
    # mutation is applied. Proven, not assumed.
    assert "unknown = [name for name in raw" in LOADER.read_text()


def test_control_the_gate_is_green_before_any_mutation() -> None:
    """The populate-check. Every case above asserts a RED result, and red is
    also what a broken gate, a syntax error or a missing fixture produces. This
    proves the arms are green when nothing is mutated, so the reds above are
    attributable to the mutations rather than to a gate that never worked."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", GATE, "-q", "--no-header"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout[-2000:]
