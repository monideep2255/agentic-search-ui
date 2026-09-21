"""P15: the other two properties, current and consistent (T-5.2-12, T-5.2-14).

The product owner's framing, 2026-08-30: the answer is non-deterministic, but
the content pulled must be CONSISTENT, CURRENT and USED. Grounding covered
"used". These two cover the rest.

## The split inside "current", which is the part worth reading

The rubric criterion and the staleness verdict are DIFFERENT QUESTIONS, and
collapsing them is what produced the last dead check.

- The criterion asks whether the answer STATES its date, version and
  assembly context. The playbook's own wording for a 2 is "clear date,
  version, assembly context". That is measurable from any trace.
- The staleness verdict asks whether the underlying record is actually FRESH
  ENOUGH, which needs the per-field-class thresholds in Section 7.4. Finding
  F-3.4-T06-01 records that this graph returns only generic properties, so
  the field class is absent and the verdict cannot be reached.

Product-owner decision, 2026-08-30: build it, and report NOT MEASURABLE
rather than a score whenever the data cannot support a verdict. A check that
silently scores 2 in that situation is the dead-check defect this phase has
now produced three separate times.

## Why consistency is not a rubric criterion

It is a property of a SET of runs, not of one. The same question asked three
times should retrieve the same core records; whether it did cannot be seen
from any single run. So it lives beside pass@k and pass^k, and touches no
locked text.
"""

from __future__ import annotations

from system_03_search_agent.eval.aggregate import retrieval_consistency
from system_03_search_agent.eval.hard_fails import staleness_verdict
from system_03_search_agent.eval.trace_source import RunRecord


def _record(**overrides) -> RunRecord:
    base = {
        "trace_id": "t",
        "query_id": "G-001",
        "question": "q",
        "outcome": "answer",
        "answer_text": "An answer [1].",
        "citations": [
            {
                "source": "ncbi_gene",
                "source_id": "672",
                "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
                "layer": 1,
                "entity_name": "BRCA1",
                "snapshot_date": "2026-04-22",
            }
        ],
        "claims": [{"text": "c", "citation_ids": ["1"]}],
    }
    base.update(overrides)
    return RunRecord(**base)


def test_p15a_staleness_is_not_measurable_without_a_field_class():
    """The state the product owner asked for, rather than an invented score.

    F-3.4-T06-01: this graph's vertices carry only generic BioLink
    properties, so the per-field-class thresholds never match. Saying so is
    the honest answer.
    """
    verdict, reason = staleness_verdict(_record())
    assert verdict == "not_measurable"
    assert "field class" in reason.lower()


def test_p15b_staleness_is_measurable_when_the_field_class_is_present():
    """The populate-check. Without it, an always-unmeasurable stub passes P15a.

    This is the arm that will start doing real work the day the graph carries
    richer properties, and it fails today if the verdict logic is a stub.
    """
    fresh = _record(
        citations=[
            {
                "source": "ncbi_gene",
                "source_id": "672",
                "source_url": "u",
                "layer": 1,
                "entity_name": "BRCA1",
                "snapshot_date": "2026-08-25",
                "field_class": "volatile",
            }
        ]
    )
    verdict, _ = staleness_verdict(fresh, today="2026-08-30")
    assert verdict == "fresh"

    stale = _record(
        citations=[
            {
                "source": "ncbi_gene",
                "source_id": "672",
                "source_url": "u",
                "layer": 1,
                "entity_name": "BRCA1",
                "snapshot_date": "2026-01-01",
                "field_class": "volatile",
            }
        ]
    )
    verdict, reason = staleness_verdict(stale, today="2026-08-30")
    assert verdict == "stale", reason


def test_p15c_consistency_is_one_when_every_sample_retrieves_the_same_records():
    a = _record(trace_id="a")
    b = _record(trace_id="b")
    c = _record(trace_id="c")
    assert retrieval_consistency([a, b, c]) == 1.0


def test_p15d_consistency_falls_when_samples_disagree():
    """The property that makes flaky retrieval visible.

    The open flag this phase exists to measure is that the agent grounds
    nothing on a single finding in about half of live runs. That is a
    consistency failure, and no per-run check can see it.
    """
    a = _record(trace_id="a")
    b = _record(
        trace_id="b",
        citations=[
            {
                "source": "ncbi_gene",
                "source_id": "675",
                "source_url": "https://www.ncbi.nlm.nih.gov/gene/675",
                "layer": 1,
                "entity_name": "BRCA2",
            }
        ],
    )
    assert retrieval_consistency([a, b]) == 0.0

    partial = retrieval_consistency([a, a, b])
    assert 0.0 < partial < 1.0, partial


def test_p15e_consistency_of_a_single_sample_is_not_reported_as_perfect():
    """One sample cannot demonstrate consistency, and must not claim to.

    Returning 1.0 for a single run would report perfect agreement from a
    set that never disagreed with anything, which is the same class of lie
    as a coverage metric reporting 0 percent for something unobservable.
    """
    assert retrieval_consistency([_record()]) is None
    assert retrieval_consistency([]) is None
