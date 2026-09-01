"""Build phase 6.2, T-6.2-08: an answer may offer an honest next step.

Product-owner decision, 2026-09-01. The offer is DERIVED from what
retrieval actually returned and the answer did not report, never generated,
because an offer to go deeper is a claim that there is something deeper and
a model asked to write one will propose topics the graph does not hold.

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
    offer = _build_next_step_offer(_omitted(3), trust_outcome="ask", refused=False)

    assert offer is not None
    assert "3" in offer, offer
    assert "disease" in offer.lower(), offer
    assert offer.endswith("?"), f"an offer is a question: {offer!r}"


def test_singular_and_plural_are_both_grammatical() -> None:
    """A visible grammar slip in an offer undermines the offer.

    The same reasoning the incompleteness note already carries: this text is
    shown to a reader in a clinical context.
    """
    one = _build_next_step_offer(_omitted(1), trust_outcome="ask", refused=False)
    many = _build_next_step_offer(_omitted(4), trust_outcome="ask", refused=False)

    assert one is not None and "1 further disease record" in one, one
    assert many is not None and "4 further disease records" in many, many


def test_nothing_omitted_means_no_offer() -> None:
    """The commonest decline. A complete answer has nowhere deeper to go."""
    assert _build_next_step_offer([], trust_outcome="answer", refused=False) is None


def test_a_refusal_never_offers() -> None:
    """Two routes to the same decline, and both are covered.

    A refusal has no answer to go deeper FROM, so an offer attached to one
    would invite the user to explore something that was never found. The
    `refused` flag and a `refuse` trust outcome are different signals and
    either alone must be enough.
    """
    assert _build_next_step_offer(_omitted(3), trust_outcome="ask", refused=True) is None
    assert (
        _build_next_step_offer(_omitted(3), trust_outcome="refuse", refused=False) is None
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
    assert _build_next_step_offer(mixed, trust_outcome="ask", refused=False) is None


def test_rows_with_no_entity_type_decline() -> None:
    """An omitted row carrying no type cannot be described, so it is not
    offered. Silence beats "would you like to see more of the 3 things?"."""
    untyped = _omitted(3, "")
    assert _build_next_step_offer(untyped, trust_outcome="ask", refused=False) is None


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
