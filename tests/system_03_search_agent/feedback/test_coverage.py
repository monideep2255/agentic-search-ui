"""Unit tests for `feedback.coverage.coverage_tags_for` (T-4.6-05).

`coverage.py`'s own module docstring records the history in full: the
traversed-edge-label pairing `synthesis/trust.py` computes internally has
never reached any `CitationPayload` field on this branch. An attempt to
close that gap (T-4.6-04, adding `CitationPayload.node_or_edge_type`) broke
build phase 4.1's blocking MCP premise gate and widened a payload guarded by
`_ALLOWED_RESPONSE_KEYS` without the required product-owner approval
(finding F-4.6-J-02), and the product owner ordered it reverted on
2026-08-21 rather than repaired. This module therefore emits `concept:`
tags only; `predicate:<edge_type>` is deferred. These tests exercise the
derivation against citation-shaped dicts directly (the same shape
`feedback/capture.py` passes: `event.payload` for each `citation`-type
event), not against a live run.
"""

from __future__ import annotations

from system_03_search_agent.feedback.coverage import coverage_tags_for


def _citation(**overrides: object) -> dict[str, object]:
    """A minimal citation-payload-shaped dict, only the keys this module reads."""
    base: dict[str, object] = {
        "source": "NCBIGene",
        "field": "symbol",
        "claim_text": "BRCA1 is a gene.",
    }
    base.update(overrides)
    return base


def test_no_citations_produces_no_tags() -> None:
    """A query that traversed nothing gets an empty list, never a fabricated tag.

    Mutation run: changed the final `return sorted(tags)` to
    `return sorted(tags) or ["concept:Gene"]`. The assertion below went red
    (`coverage_tags_for([])` returned `["concept:Gene"]` instead of `[]`).
    Reverted after confirming the failure.
    """
    assert coverage_tags_for([]) == []


def test_an_unambiguous_curie_prefix_produces_its_concept_tag() -> None:
    """`NCBIGene` maps to exactly one label in `LABEL_CURIE_PREFIXES`: `Gene`.

    Mutation run: changed `_PREFIX_TO_LABELS[_prefix] = ...` inside the
    module-level inversion loop to always assign `()` (an empty tuple)
    instead of appending the label. The assertion below went red
    (`coverage_tags_for` returned `[]` instead of `["concept:Gene"]`, since
    the prefix-to-label table was empty for every prefix). Reverted after
    confirming the failure.
    """
    tags = coverage_tags_for([_citation(source="NCBIGene", claim_text="x", field="y")])
    assert tags == ["concept:Gene"]


def test_an_ambiguous_curie_prefix_produces_every_candidate_label() -> None:
    """`MedGen` names both `Disease` and `PhenotypicFeature`; both tags fire.

    Mutation run: changed the inversion loop's assignment to overwrite
    rather than accumulate (`_PREFIX_TO_LABELS[_prefix] = (_label,)` instead
    of appending). The assertion below went red (only one of the two
    concept tags was present, since the second vertex label that also
    claims the `MedGen` prefix silently overwrote the first rather than
    joining it). Reverted after confirming the failure.
    """
    tags = coverage_tags_for(
        [_citation(source="MedGen", claim_text="x", field="y")]
    )
    assert tags == ["concept:Disease", "concept:PhenotypicFeature"]


def test_an_unknown_prefix_produces_no_concept_tag() -> None:
    """A prefix outside the graph's own nine produces no `concept:` tag.

    Mutation run: changed `_PREFIX_TO_LABELS.get(source, ())`'s default from
    `()` to `("Gene",)`. The assertion below went red (`tags` carried
    `["concept:Gene"]` instead of `[]` for a prefix the graph's own schema
    does not use). Reverted after confirming the failure.
    """
    tags = coverage_tags_for(
        [_citation(source="NotARealPrefix", claim_text="x", field="y")]
    )
    assert tags == []


def test_output_is_sorted() -> None:
    """A deterministic column value: two runs with the same tag SET produce
    the identical list, regardless of citation order.

    Mutation run: changed the final `return sorted(tags)` to
    `return list(tags)`. The assertion below went red (`tags` came back in
    set-iteration order, `["concept:Gene", "concept:Disease"]`, not sorted
    order). Reverted after confirming the failure.
    """
    tags = coverage_tags_for(
        [
            _citation(source="MONDO", claim_text="x", field="y"),
            _citation(source="NCBIGene", claim_text="x", field="y"),
        ]
    )
    assert tags == sorted(tags)


def test_an_edge_label_in_claim_text_or_field_produces_no_predicate_tag() -> None:
    """Pins the deliberate absence: `predicate:` tags are not emitted at all.

    This is the direct replacement for the retired prose-matching
    derivation's own test. `field` and `claim_text` here both carry a real
    graph edge label verbatim (`gene_associated_with_condition`), the exact
    shape the old heuristic searched for and the exact shape a future
    reader might be tempted to reintroduce as a stopgap. This test exists
    so that temptation fails loudly: as long as `predicate:<edge_type>` is
    deferred (see the module docstring), no input shape may produce one.

    Mutation run: changed `coverage_tags_for` to also search
    `citation.get("claim_text", "")` and `citation.get("field", "")` for a
    known edge label and add a `predicate:` tag on a match (reintroducing
    the retired heuristic). The assertion below went red (`tags` carried
    `"predicate:gene_associated_with_condition"`). Reverted after
    confirming the failure.
    """
    tags = coverage_tags_for(
        [
            {
                "source": "NotARealPrefix",
                "field": "gene_associated_with_condition",
                "claim_text": "gene_associated_with_condition",
            }
        ]
    )
    assert tags == []
    assert not any(tag.startswith("predicate:") for tag in tags)
