"""The build phase 5.1 premise gate: the 50-query golden dataset.

Written at cadence stage 5, BEFORE any implementation, and watched failing.

## Scope, narrowed 2026-08-30 after review

This file used to gate the whole of build phase 5.1: the dataset AND the
grading harness. Both review rounds returned FAIL on the harness, with 41
findings between them, while the dataset itself was independently verified
clean by both. Product-owner decision the same day: SHIP THE DATASET, hold
the grading harness back as build phase 5.2.

So the arms here cover the artifact that passed review, and nothing else.
The harness arms moved verbatim to
`tests/system_03_search_agent/eval/test_phase_5_2_premise.py`, which is NOT
on this branch. None were deleted and none were weakened.

## What these arms defend

- P1: the dataset cannot be authored circularly. Structural, not a
  convention. A row whose expected answer came from the agent under test is
  refused at load, because such a row certifies the agent's current
  behaviour as correct forever, behind a green gate.
- P9: the three search categories (KISS, KISSES, discovery) are
  structurally distinct, so each can later be graded against the metric that
  actually matters for it.
- P8: the shipped 50-row file loads, every row carries provenance, and every
  row that pins a CURIE was live-verified.

## Coverage: what this gate does NOT cover

Per `.claude/rules/goal-contracts.md`, stated rather than discovered later.

- NO ARM HERE PROVES ANY EXPECTED ANSWER IS CORRECT. Correctness rests on the
  live-source provenance recorded per row and on the product owner's
  sign-off, and that sign-off is bounded: it is not an external clinical or
  human-variation review. No test can settle it.
- NO ARM CHECKS THAT A ROW IS IN THE RIGHT CATEGORY. P9 proves the categories
  are distinguishable and that the schema enforces what each requires.
  Whether G-011 is really a KISS is an editorial judgment in that row's notes.
- NO ARM GRADES ANYTHING. Grading is build phase 5.2, and its arms are not
  here. A green run of this file says the dataset is well-formed and
  honestly sourced. It says nothing about whether any answer is any good.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.eval.dataset import (
    DatasetValidationError,
    load_golden_dataset,
)

# --------------------------------------------------------------------------
# Fixtures. Built here rather than loaded, so an arm cannot pass because the
# real dataset happened to contain a convenient row.
# --------------------------------------------------------------------------

_VALID_ROW = {
    "id": "G-001",
    "search_category": "kiss",
    "question": "Which diseases are associated with BRCA1?",
    "wedge_type": "gene-variant-literature",
    "personas": [1, 3, 8],
    "query_class": "lookup",
    "expected_outcome": "answer",
    "must_resolve": ["NCBIGene:672"],
    "must_cite": ["https://www.ncbi.nlm.nih.gov/gene/672"],
    "forbidden": ["pathogenicity_verdict"],
    "hard_fails_applicable": ["provenance", "safety"],
    "provenance": {
        "authored_from": "live_source",
        "source": "NCBI E-utilities esummary, db=gene, id=672",
        "read_on": "2026-08-30",
        "signed_off_by": "product owner",
        "sign_off_bound": (
            "not reviewed by an external clinical or human-variation reviewer"
        ),
    },
}


def _row(**overrides: object) -> dict:
    """A valid row with targeted overrides, so each arm varies ONE thing.

    Build phase 5.0's F-5.0-16 was one defect wearing nine costumes because
    every probe carried the same inert prefix. Varying one field against an
    otherwise-valid row is what makes a failure attributable.
    """
    row = {**_VALID_ROW, "provenance": {**_VALID_ROW["provenance"]}}
    for key, value in overrides.items():
        if key == "provenance" and isinstance(value, dict):
            row["provenance"] = {**row["provenance"], **value}
        else:
            row[key] = value
    return row


# --------------------------------------------------------------------------
# P1: the dataset cannot be authored circularly
# --------------------------------------------------------------------------


def test_p1a_row_without_provenance_is_refused(tmp_path):
    """A row missing provenance is refused at load, not warned about.

    The product-owner decision of 2026-08-30 is only worth anything if it is
    structural. A convention that expected answers are authored independently
    is exactly the kind of thing that erodes under deadline.
    """
    row = _row()
    del row["provenance"]
    path = tmp_path / "golden.json"
    path.write_text(__import__("json").dumps({"version": 1, "queries": [row]}))

    with pytest.raises(DatasetValidationError) as excinfo:
        load_golden_dataset(path)
    assert "provenance" in str(excinfo.value)


def test_p1b_row_authored_from_the_agent_is_refused(tmp_path):
    """`authored_from: agent_output` is refused, naming the circularity.

    This is the arm that encodes the rejected option. If it ever passes, the
    dataset can certify the agent's current behaviour as correct forever.
    """
    row = _row(provenance={"authored_from": "agent_output"})
    path = tmp_path / "golden.json"
    path.write_text(__import__("json").dumps({"version": 1, "queries": [row]}))

    with pytest.raises(DatasetValidationError) as excinfo:
        load_golden_dataset(path)
    message = str(excinfo.value).lower()
    assert "circular" in message or "agent_output" in message


def test_p1c_populate_check_a_valid_row_actually_loads(tmp_path):
    """The populate-check, per build phase 4.11.

    Without this arm, P1a and P1b would both pass against a loader that
    refuses EVERY row, which is indistinguishable from a loader that refuses
    the right ones. An arm that cannot tell the control holding from nothing
    having happened is not an arm.
    """
    path = tmp_path / "golden.json"
    path.write_text(__import__("json").dumps({"version": 1, "queries": [_row()]}))

    dataset = load_golden_dataset(path)
    assert len(dataset.queries) == 1
    assert dataset.queries[0].id == "G-001"
    assert dataset.queries[0].provenance.authored_from == "live_source"
    assert dataset.queries[0].provenance.sign_off_bound


def test_p1d_sign_off_bound_is_required_not_optional(tmp_path):
    """A row may not claim sign-off without stating that sign-off's bound.

    The continuation prompt's instruction is explicit: state the bound where
    the provenance is stated. A sign-off with no stated bound reads as a
    clinical review that never happened.
    """
    row = _row(provenance={"sign_off_bound": ""})
    path = tmp_path / "golden.json"
    path.write_text(__import__("json").dumps({"version": 1, "queries": [row]}))

    with pytest.raises(DatasetValidationError) as excinfo:
        load_golden_dataset(path)
    assert "bound" in str(excinfo.value).lower()


# --------------------------------------------------------------------------
# P9: the three search categories are structurally distinct
#
# Product-owner decision, 2026-08-30. KISS, KISSES and discovery fail
# differently, so they must be gradeable differently, and that is only
# possible if the dataset can tell them apart. These arms defend the
# distinction itself, not any particular row's assignment.
# --------------------------------------------------------------------------


def _write(tmp_path, rows):
    path = tmp_path / "golden.json"
    path.write_text(__import__("json").dumps({"version": 1, "queries": rows}))
    return path


def test_p9a_a_row_with_no_search_category_is_refused(tmp_path):
    row = _row()
    del row["search_category"]
    with pytest.raises(DatasetValidationError) as excinfo:
        load_golden_dataset(_write(tmp_path, [row]))
    assert "search_category" in str(excinfo.value)


def test_p9b_a_discovery_row_with_no_follow_ups_is_refused(tmp_path):
    """One turn cannot demonstrate holding a thread across turns.

    This is the arm that stops "discovery" becoming a label someone applies
    to an ordinary single question because it felt exploratory. The category
    means multi-turn, so the schema requires more than one turn.
    """
    row = _row(search_category="discovery", follow_ups=[])
    with pytest.raises(DatasetValidationError) as excinfo:
        load_golden_dataset(_write(tmp_path, [row]))
    assert "follow_ups" in str(excinfo.value)


def test_p9c_a_kiss_row_carrying_follow_ups_is_refused(tmp_path):
    """The inverse, and it is not redundant.

    P9b stops a discovery row being under-specified. This stops turns being
    attached to a row nothing will ever run them for, which would read in the
    file as coverage that does not exist.
    """
    row = _row(search_category="kiss", follow_ups=["and then what?"])
    with pytest.raises(DatasetValidationError) as excinfo:
        load_golden_dataset(_write(tmp_path, [row]))
    assert "follow_ups" in str(excinfo.value)


def test_p9d_a_kisses_row_must_forbid_undisclosed_truncation(tmp_path):
    """The category-specific constraint, enforced rather than conventional.

    An exhaustive question answered with a silent subset is a confident wrong
    answer, not a partial one. F-2.2-06 is the recorded instance: a truncated
    answer disclosed the cut but not its scale.
    """
    row = _row(search_category="kisses", forbidden=[])
    with pytest.raises(DatasetValidationError) as excinfo:
        load_golden_dataset(_write(tmp_path, [row]))
    assert "undisclosed_truncation" in str(excinfo.value)


def test_p9e_populate_check_each_category_actually_loads(tmp_path):
    """Without this, every P9 arm passes against a loader that refuses all rows."""
    rows = [
        _row(id="K-1", search_category="kiss"),
        _row(id="K-2", search_category="kisses", forbidden=["undisclosed_truncation"]),
        _row(id="D-1", search_category="discovery", follow_ups=["and then?"]),
    ]
    dataset = load_golden_dataset(_write(tmp_path, rows))
    assert [q.search_category for q in dataset.queries] == [
        "kiss",
        "kisses",
        "discovery",
    ]
    assert dataset.queries[2].follow_ups == ["and then?"]


# --------------------------------------------------------------------------
# P8: the dataset is a versioned file
# --------------------------------------------------------------------------


def test_p8_the_shipped_dataset_loads_from_the_repository_and_is_complete():
    """The real file, not a fixture. 50 rows, every one carrying provenance.

    `.claude/rules/prompt-cache-discipline.md` forbids a live per-request
    database read for the few-shot pool for the same reason it is forbidden
    here: a changing source defeats reproducibility even when it happens to
    return the same content.
    """
    from system_03_search_agent.eval.dataset import GOLDEN_DATASET_PATH

    dataset = load_golden_dataset(GOLDEN_DATASET_PATH)
    assert len(dataset.queries) == 50

    for query in dataset.queries:
        # Never the agent's own output, for any row, under any circumstance.
        assert query.provenance.authored_from in ("live_source", "locked_requirements")
        assert query.provenance.sign_off_bound

        # THE LOAD-BEARING ONE. A row that pins a CURIE is asserting a fact
        # about a specific NCBI record, and that assertion is only worth
        # anything if a live record was actually read. A row with no
        # identifier to check (a refusal row, an out-of-scope row) draws its
        # authority from the locked requirements instead, which is a
        # different and legitimate source, not a weaker version of this one.
        if query.must_resolve:
            assert query.provenance.authored_from == "live_source", (
                f"{query.id} pins {query.must_resolve} without live verification"
            )
            assert "esummary" in query.provenance.source, (
                f"{query.id} claims live_source but names no live lookup"
            )

    # A floor, so this arm cannot pass against a dataset that quietly stopped
    # verifying anything and relabelled every row locked_requirements.
    live = [q for q in dataset.queries if q.provenance.authored_from == "live_source"]
    assert len(live) >= 30, f"only {len(live)} rows were live-verified"

    # All three search categories are actually represented, and the
    # discovery rows actually carry turns. A taxonomy with an empty class
    # is a taxonomy nobody is using.
    from collections import Counter

    counts = Counter(q.search_category for q in dataset.queries)
    assert set(counts) == {"kiss", "kisses", "discovery"}, counts
    assert all(value > 0 for value in counts.values()), counts
    discovery = [q for q in dataset.queries if q.search_category == "discovery"]
    assert all(q.follow_ups for q in discovery)
    assert sum(len(q.follow_ups) for q in discovery) >= 12
