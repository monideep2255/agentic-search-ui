"""Build phase 6.2, T-6.2-08: an answer may offer an honest next step.

Product-owner decision, 2026-09-01. The offer is DERIVED from what
retrieval actually returned and the answer could not show, never generated,
because an offer to go deeper is a claim that there is something deeper and
a model asked to write one will propose topics the graph does not hold.

Re-keyed by UI fix set 10, item 10.1 (2026-09-13): the findings tail now
reports every prepared finding, so "deeper" means records BEYOND the
prepared list (the list was capped, or the tool truncated the graph
result), with a count only when the total is known. The arms below pass
that signal and the prepared findings explicitly; the count they pass is
the number of prepared rows, so the wording assertions hold unchanged.

MOST OF THIS FILE IS ABOUT DECLINING, and that is the right proportion. The
decision named the failure mode explicitly: a system that always asks
something will pad. So the arms below spend more effort on the cases where
`None` is correct than on the one case where an offer is.
"""

from __future__ import annotations

from system_03_search_agent.core.graph import _build_next_step_offer
from system_03_search_agent.synthesis.findings import SynthFinding


def _omitted(count: int, entity_type: str = "Disease") -> list[SynthFinding]:
    return [
        SynthFinding(
            ref_index=i,
            citation_id=f"omitted-{i}",
            layer="layer_1_graph",
            tool="cypher_query",
            field="curie",
            field_value=f"MedGen:C{i}",
            source_url=f"https://www.ncbi.nlm.nih.gov/medgen/C{i}",
            entity_type=entity_type,
            curie=f"MedGen:C{i}",
        )
        for i in range(1, count + 1)
    ]


def test_an_offer_names_what_was_actually_left_out() -> None:
    """The one case where an offer is honest, and what it may say.

    It names the COUNT and the TYPE, both read off the omitted rows. It does
    not name the values, for the same reason the incompleteness disclosure
    does not: a Layer 1 value is full of periods and inlining one fragments
    the sentence for anything that splits on them.
    """
    offer = _build_next_step_offer(_omitted(3), True, 3, trust_outcome="ask", refused=False)

    assert offer is not None
    assert "3" in offer, offer
    assert "disease" in offer.lower(), offer
    assert offer.endswith("?"), f"an offer is a question: {offer!r}"


def test_singular_and_plural_are_both_grammatical() -> None:
    """A visible grammar slip in an offer undermines the offer.

    The same reasoning the incompleteness note already carries: this text is
    shown to a reader in a clinical context.
    """
    one = _build_next_step_offer(_omitted(1), True, 1, trust_outcome="ask", refused=False)
    many = _build_next_step_offer(_omitted(4), True, 4, trust_outcome="ask", refused=False)

    assert one is not None and "1 further disease record" in one, one
    assert many is not None and "4 further disease records" in many, many


def test_nothing_beyond_the_prepared_list_means_no_offer() -> None:
    """The commonest decline. A complete answer has nowhere deeper to go:
    neither capped nor truncated, so `more_records_exist` is False, however
    many findings were prepared. And no prepared findings means no type to
    name even when more exist."""
    assert (
        _build_next_step_offer(_omitted(5), False, None, trust_outcome="answer", refused=False)
        is None
    )
    assert _build_next_step_offer([], True, 4, trust_outcome="answer", refused=False) is None


def test_an_unknown_total_offers_without_a_number() -> None:
    """When the true total is unknown the offer names no count rather than
    inventing one, and a non-positive remainder is treated the same way."""
    offer = _build_next_step_offer(_omitted(3), True, None, trust_outcome="ask", refused=False)
    assert offer == (
        "Would you like me to go through the further disease records found for this question?"
    ), offer
    assert not any(ch.isdigit() for ch in offer)
    assert _build_next_step_offer(_omitted(3), True, 0, trust_outcome="ask", refused=False) == offer


def test_a_refusal_never_offers() -> None:
    """Two routes to the same decline, and both are covered.

    A refusal has no answer to go deeper FROM, so an offer attached to one
    would invite the user to explore something that was never found. The
    `refused` flag and a `refuse` trust outcome are different signals and
    either alone must be enough.
    """
    assert _build_next_step_offer(_omitted(3), True, 3, trust_outcome="ask", refused=True) is None
    assert (
        _build_next_step_offer(_omitted(3), True, 3, trust_outcome="refuse", refused=False) is None
    )


def test_a_mixed_bag_declines_rather_than_going_vague() -> None:
    """When the omitted rows are of several types, there is no honest short
    phrasing, and the vague one ("would you like to see more?") is worth
    less than silence.

    This arm is what stops the obvious "just say records" fallback, which
    would make the offer appear on nearly every answer and turn it into the
    padding the decision forbids.
    """
    mixed = _omitted(2, "Disease") + _omitted(2, "Gene")
    assert _build_next_step_offer(mixed, True, 4, trust_outcome="ask", refused=False) is None


def test_rows_with_no_entity_type_decline() -> None:
    """An omitted row carrying no type cannot be described, so it is not
    offered. Silence beats "would you like to see more of the 3 things?"."""
    untyped = _omitted(3, "")
    assert _build_next_step_offer(untyped, True, 3, trust_outcome="ask", refused=False) is None


def test_the_offer_is_not_model_generated() -> None:
    """A structural arm, not a behavioural one.

    The whole safety argument for this feature is that the text is built in
    code from retrieved rows. If this function ever grew a model call, the
    argument would be void and every other arm here would still pass, since
    they only inspect the string that comes back.

    So this reads the source and asserts the builder reaches no model. It is
    deliberately crude: a check that can only be satisfied by not calling a
    model is worth more here than a subtle one.
    """
    import inspect

    from system_03_search_agent.core import graph

    source = inspect.getsource(graph._build_next_step_offer)
    for forbidden in ("call_tier", "harness", "await", "_dispatch_tier_call"):
        assert forbidden not in source, (
            f"the next-step offer must be built in code, never generated. "
            f"Found {forbidden!r} in its source."
        )


# ---------------------------------------------------------------------------
# UI fix set 7, item 7.2 (2026-09-13): the query an accepted offer sends.
# ---------------------------------------------------------------------------

from system_03_search_agent.core.next_step import (
    GO_DEEPER_TEMPLATE,
    build_next_step_query,
    entity_type_noun,
    is_go_deeper_query,
)


def test_the_follow_up_query_names_the_record_type_and_the_entity() -> None:
    query = build_next_step_query(_omitted(3, "SequenceVariant"), "BRCA1")
    assert query == "Which other sequence variant records are linked to BRCA1?", query


def test_every_query_the_builder_produces_is_one_the_detector_accepts() -> None:
    """The round trip is the whole point of keeping both halves in one
    module: a wording change that breaks it is caught here.

    MUTATION PROOF: editing `GO_DEEPER_TEMPLATE` without editing the pattern
    turns this arm red.
    """
    for entity_type in ("Disease", "SequenceVariant", "Publication", "Gene"):
        for entity in ("BRCA1", "NCBIGene:672", "TP53"):
            query = build_next_step_query(_omitted(2, entity_type), entity)
            assert query is not None
            assert is_go_deeper_query(query), query
    assert "{noun}" in GO_DEEPER_TEMPLATE and "{entity}" in GO_DEEPER_TEMPLATE


def test_the_detector_rejects_the_offer_text_and_ordinary_questions() -> None:
    offer = _build_next_step_offer(_omitted(3), True, 3, trust_outcome="ask", refused=False)
    assert offer is not None
    assert not is_go_deeper_query(offer), offer
    assert not is_go_deeper_query("Which diseases are associated with BRCA1?")
    assert not is_go_deeper_query("What variants cause it?")
    assert not is_go_deeper_query("Which other disease records are linked to BRCA1")
    assert not is_go_deeper_query(
        "Tell me: which other disease records are linked to BRCA1? And more."
    )


def test_the_record_type_noun_is_plain_words() -> None:
    assert entity_type_noun("SequenceVariant") == "sequence variant"
    assert entity_type_noun("Disease") == "disease"
    assert entity_type_noun("ClinicalTrial") == "clinical trial"


def test_the_query_declines_exactly_when_the_offer_declines() -> None:
    """The two `DonePayload` fields are set together or not at all."""
    assert build_next_step_query([], "BRCA1") is None
    mixed = _omitted(2, "Disease") + _omitted(2, "Gene")
    assert build_next_step_query(mixed, "BRCA1") is None
    untyped = _omitted(2, entity_type="")
    assert build_next_step_query(untyped, "BRCA1") is None
    assert _build_next_step_offer(untyped, True, 3, trust_outcome="ask", refused=False) is None


def test_the_query_declines_with_no_entity_to_name() -> None:
    """A follow-up that names nothing is the pronoun form this replaces."""
    assert build_next_step_query(_omitted(3), "") is None
    assert build_next_step_query(_omitted(3), "   ") is None


def test_the_query_is_not_model_generated() -> None:
    import inspect

    from system_03_search_agent.core import next_step

    source = inspect.getsource(next_step)
    assert "litellm" not in source and "acompletion" not in source


def test_derived_projection_rows_do_not_count_as_a_record_type() -> None:
    """Measured live 2026-09-13: `RETURN v, v.name` yields every variant twice,
    as a `SequenceVariant` row and a `derived` projection row of the same
    record. Built from the bare type set, the offer read "10 further derived
    records" when the omitted rows were all projections, and declined when
    they mixed. Both halves are wrong about what the records are.

    MUTATION PROOF: removing the `!= _DERIVED_ROW_TYPE` clause in
    `shared_record_type` turns both assertions red (mixed gives None, all
    derived gives "derived").
    """
    from system_03_search_agent.core.next_step import shared_record_type

    mixed = _omitted(2, "SequenceVariant") + _omitted(2, "derived")
    assert shared_record_type(mixed) == "SequenceVariant"
    offer = _build_next_step_offer(mixed, True, 4, trust_outcome="ask", refused=False)
    assert offer == (
        "Would you like me to go through the 4 further sequence variant records "
        "found for this question?"
    ), offer
    assert build_next_step_query(mixed, "BRCA1") == (
        "Which other sequence variant records are linked to BRCA1?"
    )

    only_projections = _omitted(3, "derived")
    assert shared_record_type(only_projections) is None
    assert _build_next_step_offer(only_projections, True, 3, trust_outcome="ask", refused=False) is None
    assert build_next_step_query(only_projections, "BRCA1") is None
