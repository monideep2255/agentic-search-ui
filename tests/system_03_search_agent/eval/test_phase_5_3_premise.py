"""The build phase 5.3 premise gate: golden dataset schema v2.

Written at cadence stage 5, BEFORE any implementation, and watched failing.

## What this phase is, in one line

Build phase 5.1's 50 rows can pin an identifier and a citation URL. They
cannot pin that answering the question REQUIRED a live Layer 2 or Layer 3
call, and that is what this phase makes expressible.

## Why a citation URL is not enough, which is the premise these arms defend

A `must_cite` of `https://www.ncbi.nlm.nih.gov/gene/672` is satisfiable
straight from the Layer 1 graph node's own `source_url` field, with no live
call ever made. Measured on the merged dataset: `litvar2_lookup` and
`pubtator_annotate` are required by ZERO of the 50 rows, and the eight rows
citing PubMed plus the four citing dbSNP can all be passed by an agent that
read the graph and stopped. The dataset could not tell the two apart.

Two mechanisms, deliberately independent, because they fail differently:

- `must_reach` names the tools a row requires. Grades the retrieval PATH.
  Countable per tool, easy to author, and it breaks whenever routing
  legitimately changes.
- `live_only` names a fact the Layer 1 graph does not contain. Grades the
  ANSWER. Cannot be faked by a graph-only agent, needs no trace to check at
  authoring time, and it ages as the graph snapshot moves.

A row satisfying the path while failing the fact means the tool WAS called
and its result was discarded. That is a distinct defect, and keeping both
mechanisms is what makes it visible.

## The independence rule P6 defends, and why it has its own arm

`eval/golden/build_dataset.py` verifies every constraint against live
E-utilities over raw HTTP, touching none of the agent's own tool layer. Its
docstring explains why at length. Build phase 5.2 then rebuilt the identical
circularity one file over and it is the root defect that parked that phase:
a grounding check compared the agent's prose against the agent's own
citation payload, so an answer about a gene that does not exist, citing a
record that does not exist, scored 16 of 16.

`LEARNINGS.md`, 2026-08-30, states the general form: when you build an
independent verification path for one component, write down what made it
independent, then check every neighbouring component against that same
definition. Knowing the principle did not transfer. P6 is that check made
structural, so it cannot depend on anyone remembering.

## Coverage: what this gate does NOT cover

Per `.claude/rules/goal-contracts.md`, stated here rather than discovered
later, because a green gate reads as "this class is covered" when it may
only mean "the cases someone thought of are covered".

- NOTHING HERE CHECKS `must_reach` AT GRADING TIME. Proving that
  `litvar2_lookup` was actually called means reading tool calls out of a
  trace, which is `replay()`'s job, and `replay()` refuses to run without
  `acknowledge_parked=True`. These arms prove the constraint's SHAPE is
  enforced, never that any agent satisfied it.
- NO SHIPPED ROW USES EITHER NEW FIELD. This phase authors no questions, by
  product-owner decision of 2026-08-31: the 50 are a data-derived v1 and the
  settled set needs SME input. Both fields are exercised by fixtures here,
  not by production rows, so a green run says the language works and says
  nothing about coverage.
- THE `live_only` SHELF LIFE IS CHECKED AT BUILD TIME ONLY. P5 proves the
  builder refuses a fact the graph already holds, at the moment it runs. A
  System 1/2 re-ingest between two builder runs makes a shipped row
  graph-satisfiable and nothing re-checks it. This repository does not
  control or observe a re-ingest.
- P5 IS THE ONLY ARM THAT TOUCHES THE LIVE GRAPH, and it skips when the
  graph is unreachable. A skip is NOT a pass: the phase file's blocked-stop
  says so, and date arithmetic against `GRAPH_SNAPSHOT_VERSION` is
  explicitly not an acceptable substitute, because that value is a
  hand-maintained env fallback that nothing re-reads from the graph and so
  can be stale in exactly the case the check exists to catch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DIR = REPO_ROOT / "eval" / "golden"


# ---------------------------------------------------------------------------
# P1: the seven-tool roster is DERIVED, never re-typed
#
# F-3.0-01 is the recorded instance of the failure this defends: a second
# hand-maintained copy of a vocabulary lived in the frontend, and it silently
# rejected a value the backend had just added. The loader already takes
# `QueryClass` from the enum for exactly this reason; `must_reach` must take
# its roster from `REGISTERED_TOOL_SCHEMAS` the same way.
# ---------------------------------------------------------------------------


def test_p1_tool_roster_is_derived_from_the_registry_not_retyped() -> None:
    from system_03_search_agent.eval.dataset import ALLOWED_MUST_REACH
    from system_03_search_agent.harness.cache import REGISTERED_TOOL_SCHEMAS

    registry_names = {schema["name"] for schema in REGISTERED_TOOL_SCHEMAS}

    # Equality, not containment. A subset would let the roster silently drop
    # a tool; a superset would let it invent one.
    assert ALLOWED_MUST_REACH == registry_names, (
        "must_reach's allowed set must equal the registered tool roster exactly"
    )
    assert len(ALLOWED_MUST_REACH) == 7, (
        f"expected the seven-tool roster, got {len(ALLOWED_MUST_REACH)}"
    )


# ---------------------------------------------------------------------------
# P2: must_reach is validated, and an unknown tool is REFUSED
#
# The populate-check matters here (build phase 4.11's durable fix): an arm
# that cannot distinguish "the control held" from "nothing happened" is not
# an arm. So each negative arm asserts the SPECIFIC message, not merely that
# some error arrived. A row has many independent reasons to be refused.
# ---------------------------------------------------------------------------


def _valid_row(**overrides: object) -> dict:
    """A minimal row that PASSES validation, so a negative arm's failure is
    attributable to the one field it varies and to nothing else."""
    row = {
        "id": "G-TEST",
        "question": "Which diseases are associated with BRCA1?",
        "wedge_type": "gene-variant-literature",
        "query_class": "single_hop",
        "search_category": "kiss",
        "follow_ups": [],
        "personas": [1],
        "expected_outcome": "answer",
        "acceptable_outcomes": ["answer"],
        "must_resolve": ["NCBIGene:672"],
        "must_cite": ["https://www.ncbi.nlm.nih.gov/gene/672"],
        "forbidden": [],
        "hard_fails_applicable": ["provenance"],
        "notes": "",
        "provenance": {
            "authored_from": "live_source",
            "source": "E-utilities esummary db=gene id=672",
            "read_on": "2026-08-31",
            "signed_off_by": "product owner",
            "sign_off_bound": "not an external clinical review",
        },
    }
    row.update(overrides)
    return row


def test_p2_control_the_baseline_row_validates() -> None:
    """The populate-check. Without this, every negative arm below could be
    passing because the fixture is broken rather than because the control
    fired."""
    from system_03_search_agent.eval.dataset import _validate_row

    query = _validate_row(_valid_row())
    assert query.id == "G-TEST"


def test_p2_unknown_tool_in_must_reach_is_refused() -> None:
    from system_03_search_agent.eval.dataset import (
        DatasetValidationError,
        _validate_row,
    )

    with pytest.raises(DatasetValidationError) as excinfo:
        _validate_row(_valid_row(must_reach=["blastn"]))

    assert "must_reach" in str(excinfo.value)
    assert "blastn" in str(excinfo.value)


def test_p2_every_registered_tool_is_accepted_in_must_reach() -> None:
    from system_03_search_agent.eval.dataset import _validate_row
    from system_03_search_agent.harness.cache import REGISTERED_TOOL_SCHEMAS

    for schema in REGISTERED_TOOL_SCHEMAS:
        query = _validate_row(_valid_row(must_reach=[schema["name"]]))
        assert query.must_reach == [schema["name"]]


def test_p2_must_reach_must_be_a_list_of_strings() -> None:
    from system_03_search_agent.eval.dataset import (
        DatasetValidationError,
        _validate_row,
    )

    # "got a bare str" is the TYPE CHECK's own fingerprint. Matching only
    # "must_reach" passed under mutation M3, because deleting the type check
    # lets a bare string reach the roster check, which iterates it letter by
    # letter and raises its own must_reach error. Found by mutation, not by
    # reading, which is this repository's most repeated finding.
    with pytest.raises(DatasetValidationError, match="got a bare str"):
        _validate_row(_valid_row(must_reach="litvar2_lookup"))


# ---------------------------------------------------------------------------
# P3: live_only is validated, and an incomplete block is REFUSED
#
# A live_only block that cannot say WHERE its value came from is exactly the
# circular authoring the dataset was built to prevent, so `observed_from` is
# required rather than optional.
# ---------------------------------------------------------------------------


def _live_only(**overrides: object) -> dict:
    block = {
        "fact": "clinvar_last_evaluated",
        "value": "2026-08-01",
        "observed_from": "E-utilities esummary db=clinvar id=17677",
        "observed_on": "2026-08-31",
    }
    block.update(overrides)
    return block


def test_p3_control_a_complete_live_only_block_validates() -> None:
    from system_03_search_agent.eval.dataset import _validate_row

    query = _validate_row(_valid_row(live_only=_live_only()))
    assert query.live_only is not None
    assert query.live_only.fact == "clinvar_last_evaluated"


@pytest.mark.parametrize(
    "missing", ["fact", "value", "observed_from", "observed_on"]
)
def test_p3_live_only_missing_any_required_key_is_refused(missing: str) -> None:
    from system_03_search_agent.eval.dataset import (
        DatasetValidationError,
        _validate_row,
    )

    block = _live_only()
    del block[missing]

    with pytest.raises(DatasetValidationError) as excinfo:
        _validate_row(_valid_row(live_only=block))

    assert missing in str(excinfo.value)


def test_p3_live_only_may_not_be_authored_from_agent_output() -> None:
    """The same refusal `authored_from` already enforces on provenance, applied
    to the new field. A live_only fact observed from the agent under test is
    the 5.2 circularity wearing a new field name."""
    from system_03_search_agent.eval.dataset import (
        DatasetValidationError,
        _validate_row,
    )

    with pytest.raises(DatasetValidationError, match="agent"):
        _validate_row(
            _valid_row(live_only=_live_only(observed_from="agent_output"))
        )


# ---------------------------------------------------------------------------
# P4: schema v2 is backward compatible, proven row by row rather than by a
# green suite total
#
# Build phase 4.15's lesson: a confident sentence describing a check that is
# not there. "The 50 rows still load" is that sentence unless something
# actually compares them field by field.
# ---------------------------------------------------------------------------


def test_p4_both_fields_are_optional_so_every_existing_row_stays_valid() -> None:
    from system_03_search_agent.eval.dataset import _validate_row

    query = _validate_row(_valid_row())
    assert query.must_reach == []
    assert query.live_only is None


def test_p4_the_shipped_dataset_loads_at_schema_version_2() -> None:
    from system_03_search_agent.eval.dataset import load_golden_dataset

    dataset = load_golden_dataset()
    assert dataset.version == 2
    assert len(dataset.queries) == 50


def test_p4_the_builder_and_the_shipped_file_agree_on_the_schema_version() -> None:
    """The only arm that reads the BUILDER's constant rather than its output.

    Without it, the shipped file's `version` can say 2 while the builder still
    writes 1, so the next rebuild silently reverts the schema and every other
    arm here stays green because they all read the file. Added because mutation
    M7 reverted the constant and nothing noticed.
    """
    from eval.golden.build_dataset import _SCHEMA_VERSION

    shipped = json.loads((GOLDEN_DIR / "golden_dataset.json").read_text())
    assert shipped["version"] == _SCHEMA_VERSION, (
        f"the shipped dataset is at version {shipped['version']} but the "
        f"builder writes {_SCHEMA_VERSION}; the next rebuild would change it"
    )


def test_p4_no_shipped_row_changed_meaning_under_the_schema_bump() -> None:
    """Field-by-field against the v1 payload recorded at the branch point.

    Not `len(queries) == 50`, which stays true if every question were
    replaced. The v1 fields must be byte-identical; only `version` and the
    two additive fields may differ.
    """

    baseline = json.loads(
        (GOLDEN_DIR / "golden_dataset_v1_baseline.json").read_text()
    )
    shipped = json.loads((GOLDEN_DIR / "golden_dataset.json").read_text())

    # Compared as raw JSON rather than through `as_dict()`, which drops
    # `notes` and `provenance`. A comparison that cannot see provenance
    # cannot notice provenance changing, which is the field that matters most.
    assert len(baseline["queries"]) == len(shipped["queries"]) == 50

    added = {"must_reach", "live_only"}
    by_id = {row["id"]: row for row in baseline["queries"]}
    moved_forward = 0

    for after in shipped["queries"]:
        before = by_id[after["id"]]
        assert set(after) - set(before) <= added, (
            f"row {after['id']} gained an unexpected field: "
            f"{set(after) - set(before) - added}"
        )

        for name, old in before.items():
            if name == "provenance":
                continue
            assert after[name] == old, (
                f"row {after['id']} field {name!r} changed under the schema "
                f"bump: {old!r} -> {after[name]!r}"
            )

        # Provenance is compared field by field rather than skipped. Only
        # `read_on` may move, and it may only move FORWARD: rebuilding the
        # dataset re-reads every constraint from live NCBI, so a fresh
        # `read_on` is the provenance doing its job. Every other provenance
        # field, including the sign-off bound, must be identical.
        before_prov, after_prov = before["provenance"], after["provenance"]
        assert set(before_prov) == set(after_prov)
        for name, old in before_prov.items():
            if name == "read_on":
                assert after_prov[name] >= old, (
                    f"row {after['id']} provenance.read_on went BACKWARDS "
                    f"({old} -> {after_prov[name]}), which means the shipped "
                    "row is older than the baseline it is compared against"
                )
                moved_forward += after_prov[name] > old
                continue
            assert after_prov[name] == old, (
                f"row {after['id']} provenance.{name} changed: "
                f"{old!r} -> {after_prov[name]!r}"
            )

    # The populate-check for the loop above. Without it, a shipped file
    # identical to the baseline satisfies every assertion while proving the
    # rebuild never ran, which is the hollow measurement LEARNINGS.md records
    # on 2026-08-30: ask what ELSE would produce this same green.
    assert moved_forward == 50, (
        f"only {moved_forward} of 50 rows were re-verified against live NCBI "
        "during the schema bump; the rest carry the baseline's own read_on"
    )


# ---------------------------------------------------------------------------
# P5: the builder REFUSES a live_only fact the graph already contains
#
# This is the arm that makes live_only mean anything. Without it the field is
# an author's assertion, and an author's assertion that the graph lacks a
# value is exactly the kind of claim build phase 4.15 found wrong four times.
#
# It is a MEASUREMENT against the live graph, not date arithmetic against
# GRAPH_SNAPSHOT_VERSION. See this file's coverage statement for why the date
# is not an acceptable substitute.
# ---------------------------------------------------------------------------


def test_p5_a_graph_satisfiable_fact_is_refused_by_the_builder() -> None:
    from eval.golden.build_dataset import (
        VerificationFailed,
        assert_absent_from_graph,
        graph_is_reachable,
    )

    if not graph_is_reachable():
        pytest.skip(
            "graph query service unreachable; this arm is a live measurement "
            "and a skip is NOT a pass (see the phase file's blocked-stop)"
        )

    # BRCA1's symbol is in the graph by construction, so a live_only block
    # claiming the graph lacks it must be refused. This is the planted
    # graph-satisfiable fact the goal contract requires.
    with pytest.raises(VerificationFailed, match="graph already"):
        assert_absent_from_graph(
            fact="gene_symbol",
            value="BRCA1",
            curie="NCBIGene:672",
        )


def test_p5_control_a_fact_the_graph_lacks_is_accepted() -> None:
    """Without this control, P5 above passes for a broken reason: a checker
    that refuses EVERYTHING satisfies it. The paired-probe repair from
    LEARNINGS.md 2026-08-30, applied here rather than rediscovered."""
    from eval.golden.build_dataset import assert_absent_from_graph, graph_is_reachable

    if not graph_is_reachable():
        pytest.skip("graph query service unreachable; a skip is NOT a pass")

    assert_absent_from_graph(
        fact="gene_symbol",
        value="ZZQXFAKE1-not-a-real-symbol",
        curie="NCBIGene:672",
    )


# ---------------------------------------------------------------------------
# P6: eval/golden/ imports nothing from the agent under test
#
# Structural, so it cannot depend on anyone remembering the rule. This is the
# 5.2 circularity made impossible rather than documented.
# ---------------------------------------------------------------------------


def test_p6_the_dataset_builder_does_not_import_the_agent_it_grades() -> None:
    offenders: list[str] = []
    for path in sorted(GOLDEN_DIR.glob("*.py")):
        source = path.read_text()
        for lineno, line in enumerate(source.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) and (
                "system_03_search_agent" in stripped
            ):
                offenders.append(f"{path.name}:{lineno}: {stripped}")

    assert not offenders, (
        "eval/golden/ must verify constraints independently of the agent's own "
        "tool layer; found:\n" + "\n".join(offenders)
    )


def test_p6_control_the_scan_actually_reads_the_builder() -> None:
    """The populate-check for P6. An empty glob makes P6 pass vacuously, which
    is the eleventh-instance failure LEARNINGS.md counts."""
    scanned = sorted(path.name for path in GOLDEN_DIR.glob("*.py"))
    assert "build_dataset.py" in scanned
    assert "question_set.py" in scanned


# ---------------------------------------------------------------------------
# P7: must_reach survives the builder
#
# A field the loader validates but the builder drops is a field that exists
# only in tests. This arm reads the built row, not the spec.
# ---------------------------------------------------------------------------


def test_p7_the_builder_carries_must_reach_into_the_row() -> None:
    from eval.golden.build_dataset import build_row_fields

    spec = {
        "id": "G-TEST",
        "question": "q",
        "wedge_type": "gene-variant-literature",
        "query_class": "lookup",
        "search_category": "kiss",
        "personas": [1],
        "expected_outcome": "answer",
        "must_reach": ["litvar2_lookup"],
        "origin_source": "test",
    }
    row = build_row_fields(spec, must_resolve=[], must_cite=["https://x"], sources=[])
    assert row["must_reach"] == ["litvar2_lookup"]


def test_p7_a_spec_without_must_reach_builds_an_empty_list_not_a_missing_key() -> None:
    """A missing key and an empty list are different to every consumer. The
    loader requires the field to be absent-or-list; the builder must not emit
    a third state."""
    from eval.golden.build_dataset import build_row_fields

    spec = {
        "id": "G-TEST",
        "question": "q",
        "wedge_type": "gene-variant-literature",
        "query_class": "lookup",
        "search_category": "kiss",
        "personas": [1],
        "expected_outcome": "answer",
        "origin_source": "test",
    }
    row = build_row_fields(spec, must_resolve=[], must_cite=["https://x"], sources=[])
    assert row["must_reach"] == []
