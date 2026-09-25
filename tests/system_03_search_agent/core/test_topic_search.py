"""Fix-plan item 12.7 (2026-09-23): a question that names no gene and no
disease still finds something.

What this file grades, offline, with every tool and the model replaced by
fakes whose bytes the test controls:

    THE DEFECT. Four of a second tester's seven questions refused. All four
    cleared the guardrail and then died at entity resolution, because the
    product has a gene resolver and a disease resolver and nothing else,
    while these questions name a chemical (caffeine, coffee) or a
    population (Mediterranean descent, Ashkenazi Jewish). The graph tool
    was dispatched with nothing to bind and answered "no entity could be
    identified in this query", and the reader was asked to name a gene,
    variant, disease or organism.

    THE FIX IS NOT A CHEMICAL RESOLVER. A LITERATURE QUESTION NEEDS NO
    ENTITY: the published record is searched with the question's own words.

    THE DETERMINISM CONSTRAINT. Item 11.21 promised that one question
    always shows one source set, which is why a model-extracted span may
    never become a search term. The term here is a pure function of the
    user's own typed words, with no model call and no network call in it.

    THE HARD LINE, named by the product owner for this set: the product may
    return papers about caffeine and exercise performance and must NEVER
    tell a person whether coffee will help them.

    THE GENE AND DISEASE PATHS ARE UNTOUCHED, asserted by comparing their
    planned calls before and after the topic arguments exist.

Every arm that asserts a value is absent is paired with a populate check
that proves the same code path produces it when it should, so an arm
cannot pass because nothing ran.

WHAT THIS GATE DOES NOT COVER, stated so the gap is arguable rather than
invisible (`.claude/rules/goal-contracts.md`): it never reaches PubMed, so
it says nothing about whether a term FINDS anything. That half was measured
live and is recorded, with hit counts and top titles, in
`testing/Developer/reports/2026-09-23_set12/worker_topic.md`. It also does
not grade the Synth model's obedience to the published-literature
directive; it asserts only that the directive is in the prompt, and the
grounding pass is what actually stops a verdict, since a verdict is not
quotable from a paper title.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from system_03_search_agent.contracts.query import (
    Query,
    RequestContext,
    ResolvedEntity,
    SessionMemorySummary,
)
from system_03_search_agent.core import breadth_plan
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.core.run import run_streaming
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.synthesis import refuse as refuse_module
from system_03_search_agent.synthesis.findings import (
    SYNTH_SYSTEM_INSTRUCTION,
    TOPIC_ANSWER_DIRECTIVE,
    SynthFinding,
    build_synth_messages,
)
from system_03_search_agent.tools.cypher_schemas import CypherQueryOutput
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput, NcbiEfetchRecord
from system_03_search_agent.tools.pubtator_annotate_schemas import (
    PubtatorAnnotateOutput,
    PubtatorPublication,
)
from tests.system_03_search_agent.model_stub import (
    COMPLIANT_GUARD_CLASSIFICATION,
    compliant_synth_narrative,
    fake_response,
)

# The tester's four questions, verbatim, and the term each one was measured
# to produce. Every one of the four terms was run against live ESearch on
# 2026-09-23 and its hit count recorded in the report named above.
Q4 = "papers on the effects of caffeine on exercise performance"
Q5 = "Does coffee help make exercise more effective?"
Q6 = "Are there any beneficial variants typically found in people of mediterranean descent?"
Q7 = "What positive and negative genes do ashkenazi jewish people have?"

MEASURED_TERMS: dict[str, str] = {
    # 1,356 hits
    Q4: "effects AND caffeine AND exercise AND performance",
    # 532 hits
    Q5: "coffee AND exercise AND effective",
    # 17 hits
    Q6: "variants AND people AND mediterranean AND descent",
    # 27 hits
    Q7: "positive AND negative AND genes AND ashkenazi AND jewish AND people",
}

_PMID = "33388079"
_PMID_URL = f"https://pubmed.ncbi.nlm.nih.gov/{_PMID}/"
_TITLE = (
    "International society of sports nutrition position stand: caffeine and "
    "exercise performance"
)


# ---------------------------------------------------------------------------
# breadth_plan: the term itself.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("question", list(MEASURED_TERMS))
def test_each_measured_question_builds_the_term_that_was_searched_live(
    question: str,
) -> None:
    assert breadth_plan.build_topic_term(question) == MEASURED_TERMS[question]


def test_the_words_describing_the_search_are_dropped() -> None:
    """`papers` translated to `"paper"[MeSH Terms]`, the physical material,
    and collapsed the caffeine search from 1,356 hits to 35."""
    assert "paper" not in (breadth_plan.build_topic_term(Q4) or "")
    assert breadth_plan.build_topic_term("find me studies about vitamin d") == (
        "vitamin AND d"
    )
    # Populate check: the same function keeps an ordinary content word, so
    # the absences above are this category being dropped rather than the
    # function dropping everything.
    assert breadth_plan.build_topic_term("studies about metformin") == "metformin"


def test_the_light_verbs_are_dropped_and_this_is_what_makes_q5_find_anything() -> None:
    """Measured live: `coffee AND help AND make AND exercise AND effective`
    returned ZERO hits, and `coffee AND exercise AND effective` returned
    532. This category is load-bearing, not tidiness."""
    term = breadth_plan.build_topic_term(Q5)
    assert term is not None
    assert "help" not in term and "make" not in term, term
    assert "coffee" in term and "exercise" in term, term


def test_the_found_verb_is_dropped_and_this_is_what_makes_q6_find_anything() -> None:
    """Measured live: `variants AND found AND mediterranean AND descent`
    returned ZERO, `variants AND mediterranean AND descent` returned 22."""
    term = breadth_plan.build_topic_term(Q6)
    assert term is not None and "found" not in term, term


def test_a_value_judgement_is_dropped_but_positive_and_negative_are_kept() -> None:
    """`beneficial` took the Mediterranean search from 17 hits to ZERO, so
    it goes. `positive` and `negative` are technical in biomedical text
    (HER2-positive, gram-negative) and q7 was measured to return 27
    relevant hits with both KEPT, so nothing needed dropping and nothing
    was."""
    q6_term = breadth_plan.build_topic_term(Q6)
    assert q6_term is not None and "beneficial" not in q6_term, q6_term
    q7_term = breadth_plan.build_topic_term(Q7)
    assert q7_term is not None
    assert "positive" in q7_term and "negative" in q7_term, q7_term


def test_no_pubmed_operator_can_ride_in_on_the_question_text() -> None:
    """Only letters, digits, apostrophes and hyphens are matched at all, so
    a bracket, a quote, a colon or an asterisk is never copied into the
    term. An injected field tag becomes two ordinary words."""
    term = breadth_plan.build_topic_term('caffeine[Title] OR "cancer"[MeSH] AND *')
    assert term == "caffeine AND title AND cancer AND mesh", term
    assert "[" not in term and '"' not in term and "*" not in term


def test_words_are_deduplicated_in_question_order() -> None:
    assert breadth_plan.build_topic_term("caffeine and caffeine and exercise") == (
        "caffeine AND exercise"
    )


def test_the_word_count_is_capped_so_a_long_chain_cannot_zero_the_search() -> None:
    """Every word in an AND chain is REQUIRED, so a long chain fails
    catastrophically: one word the literature does not use zeroes the whole
    search."""
    question = " ".join(f"word{index}" for index in range(30))
    term = breadth_plan.build_topic_term(question)
    assert term is not None
    assert len(term.split(" AND ")) == breadth_plan.TOPIC_MAX_WORDS, term
    # Populate check: a short question is not padded or truncated, so the
    # cap above is a ceiling rather than a fixed length.
    assert len((breadth_plan.build_topic_term(Q5) or "").split(" AND ")) == 3


@pytest.mark.parametrize(
    "question", ["", "   ", "((()))", "the and of it", "?!,.", None, 42, ["caffeine"]]
)
def test_a_question_with_no_content_word_plans_nothing(question: Any) -> None:
    assert breadth_plan.build_topic_term(question) is None
    assert breadth_plan.plan_topic_search(question) == ()


def test_the_term_is_a_pure_function_of_the_question_text() -> None:
    """The whole reason this approach is safe where a model-extracted span
    was not. No model call, no network call, no clock and no randomness, so
    repeating the call cannot move the answer."""
    terms = {breadth_plan.build_topic_term(Q7) for _ in range(200)}
    assert len(terms) == 1, terms
    assert terms == {MEASURED_TERMS[Q7]}


def test_the_topic_search_is_one_relevance_sorted_pubmed_esearch() -> None:
    (call,) = breadth_plan.plan_topic_search(Q4)
    assert call.tool == "ncbi_efetch" and call.layer == "layer_2_api"
    # The SAME purpose the gene and disease paths use, so the abstract
    # fetch and the PubTator3 annotation follow it with no second wiring.
    assert call.purpose == "pubmed_search"
    payload = call.tool_input.root.model_dump()
    assert payload["action"] == "search" and payload["db"] == "pubmed"
    assert payload["term"] == MEASURED_TERMS[Q4]
    assert payload["retmax"] == breadth_plan.TOPIC_RESULT_CAP
    assert payload["sort"] == "relevance"


def test_the_topic_term_is_untagged_unlike_the_gene_term() -> None:
    """Measured live: tagging each word `[Title/Abstract]` turns off
    PubMed's automatic term mapping and took q7 from 27 hits to ZERO. The
    gene path keeps its tag for the opposite reason, a symbol in All Fields
    matching author names."""
    assert "[Title/Abstract]" not in (breadth_plan.build_topic_term(Q4) or "")
    # Populate check: the gene term DOES carry the tag, so the absence
    # above is a property of this path rather than of the assertion.
    assert breadth_plan.build_pubmed_term("BRCA1", None) == "BRCA1[Title/Abstract]"


# ---------------------------------------------------------------------------
# graph.py: what a topic question plans, and what it does not.
# ---------------------------------------------------------------------------


def _shape(calls: list[Any]) -> list[tuple[str, str, str, Any]]:
    """The planned calls without their call_ids, which are fresh uuids per
    run by design and so say nothing about what was planned."""
    shaped: list[tuple[str, str, str, Any]] = []
    for call in calls:
        payload: Any = None
        for attr in ("ncbi_efetch_input", "tool_input", "cypher_input"):
            value = getattr(call, attr, None)
            if value is not None:
                payload = json.dumps(
                    value.model_dump() if hasattr(value, "model_dump") else repr(value),
                    sort_keys=True,
                    default=str,
                )
                break
        shaped.append(
            (
                call.tool_call.tool,
                call.tool_call.layer,
                getattr(call, "purpose", "") or getattr(call, "source_purpose", ""),
                payload,
            )
        )
    return shaped


def test_the_follow_ups_for_a_topic_search_are_the_same_table_as_a_genes() -> None:
    """Extracted rather than copied, so there is one table to keep in step.
    A topic search carries no symbol, which keeps no OMIM record, and plans
    no OMIM search to keep one from in the first place."""
    topic = [
        graph_module._planned_from_breadth(call)
        for call in breadth_plan.plan_topic_search(Q4)
    ]
    follow_ups = graph_module._follow_up_calls_for(topic, gene_symbol=None)
    assert [c.purpose for c in follow_ups] == [
        "pubmed_abstracts",
        "pubtator_publications",
    ], follow_ups
    assert {c.gene_symbol for c in follow_ups} == {None}
    # Populate check: the same helper returns the gene fan-out's follow-ups
    # for the gene fan-out's searches, so the two-item list above is a
    # property of what was passed rather than of the helper.
    gene = [
        graph_module._planned_from_breadth(call)
        for call in breadth_plan.plan_first_stage("BRCA1", None)
    ]
    assert [c.purpose for c in graph_module._follow_up_calls_for(gene, gene_symbol="BRCA1")] == [
        "pubmed_abstracts",
        "pubtator_publications",
        "clinvar_summary",
        "omim_summary",
    ]


def test_the_gene_fan_out_is_byte_identical_after_the_helper_was_extracted() -> None:
    """The follow-up loop moved out of `_build_breadth_calls` into
    `_follow_up_calls_for`. A refactor that changed what a gene question
    plans would be a silent regression in every gene answer."""
    calls = graph_module._build_breadth_calls("BRCA1", datasets=True)
    assert [getattr(c, "purpose", "") for c in calls] == [
        "pubmed_search",
        "clinvar_search",
        "omim_search",
        "gds_search",
        "pubmed_abstracts",
        "pubtator_publications",
        "clinvar_summary",
        "omim_summary",
        "gds_summary",
    ], calls
    assert {
        getattr(c, "gene_symbol", "BRCA1")
        for c in calls
        if isinstance(c, graph_module._PlannedFollowUpCall)
    } == {"BRCA1"}


def test_a_disease_question_plans_exactly_what_it_planned_before() -> None:
    calls = graph_module._build_breadth_calls(
        None, disease_title="gastroesophageal reflux", disease_curie="MedGen:C5563728"
    )
    assert [getattr(c, "purpose", "") for c in calls] == [
        "medgen_search",
        "pubmed_search",
        "pubmed_abstracts",
        "pubtator_publications",
        "medgen_summary",
    ], calls


def test_a_topic_question_spends_three_layer_2_and_3_calls() -> None:
    """Section 21.3 allows 20 per query and this must not raise it. A gene
    question spends 14 to 16; a topic question spends three, since it
    resolves nothing and therefore also spends none of Think's live
    confirmation lookups."""
    planned = [
        graph_module._planned_from_breadth(call)
        for call in breadth_plan.plan_topic_search(Q4)
    ]
    planned.extend(graph_module._follow_up_calls_for(planned, gene_symbol=None))
    assert len([c for c in planned if c.tool_call.layer != "layer_1_graph"]) == 3
    assert len(planned) <= 20


# ---------------------------------------------------------------------------
# synthesis/refuse.py: the refusal that says what it searched.
# ---------------------------------------------------------------------------


def test_the_topic_refusal_names_the_words_it_searched_as_words() -> None:
    message = refuse_module.topic_not_found_message(MEASURED_TERMS[Q5])
    assert "coffee, exercise, effective" in message, message
    # The machinery is not shown to the reader.
    assert " AND " not in message, message
    assert "name" not in message.lower(), message


def test_the_topic_refusal_replaces_the_name_a_gene_wording() -> None:
    """The point of the ticket. Asking a person who asked about caffeine to
    name a gene, variant, disease or organism demands a vocabulary they do
    not have."""
    topic = refuse_module.refusal_message_for([], MEASURED_TERMS[Q4])
    assert topic != refuse_module.UNRESOLVED_QUESTION_MESSAGE
    assert topic != refuse_module.REFUSE_MESSAGE
    assert "caffeine" in topic, topic
    # Populate check: with no topic term the original wording still stands,
    # so the arm above is reading the argument rather than a constant.
    assert refuse_module.refusal_message_for([], None) == refuse_module.REFUSE_MESSAGE


def test_a_failed_search_outranks_the_topic_wording() -> None:
    """"Nothing was published" and "the search did not finish" are
    different facts, and only one of them is this path's to report."""
    failed = [{"tool": "ncbi_efetch", "layer": "layer_2_api", "reason": "timed out"}]
    assert (
        refuse_module.refusal_message_for(failed, MEASURED_TERMS[Q4])
        == refuse_module.FAILED_SEARCH_MESSAGE
    )
    no_entity = [{"tool": "cypher_query", "layer": "layer_1_graph",
                  "reason": refuse_module.NO_ENTITY_REASON_MARKER + " ..."}]
    assert (
        refuse_module.refusal_message_for(no_entity, MEASURED_TERMS[Q4])
        == refuse_module.UNRESOLVED_QUESTION_MESSAGE
    )


def test_a_topic_term_of_only_separators_falls_back_rather_than_naming_nothing() -> None:
    assert refuse_module.topic_not_found_message(" AND  AND ") == refuse_module.REFUSE_MESSAGE


# ---------------------------------------------------------------------------
# synthesis/findings.py: the published-literature framing.
# ---------------------------------------------------------------------------


def _finding() -> SynthFinding:
    return SynthFinding(
        ref_index=1,
        citation_id="c1",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field="title",
        field_value=_TITLE,
        source_url=_PMID_URL,
    )


def test_the_published_literature_directive_is_present_only_for_a_topic_question() -> None:
    topic = build_synth_messages(Q5, [_finding()], topic_question=True)
    plain = build_synth_messages(Q5, [_finding()])
    assert TOPIC_ANSWER_DIRECTIVE in topic[1]["content"]
    assert TOPIC_ANSWER_DIRECTIVE not in plain[1]["content"], plain[1]["content"]


def test_the_directive_forbids_a_verdict_and_sits_in_the_dynamic_suffix() -> None:
    """`.claude/rules/prompt-cache-discipline.md`: a per-query directive in
    the SYSTEM block breaks the stable prefix and re-bills the whole prompt.
    Nothing errors when that happens, so it is asserted rather than trusted."""
    topic = build_synth_messages(Q5, [_finding()], topic_question=True)
    plain = build_synth_messages(Q5, [_finding()])
    assert topic[0]["content"] == plain[0]["content"] == SYNTH_SYSTEM_INSTRUCTION
    assert TOPIC_ANSWER_DIRECTIVE not in SYNTH_SYSTEM_INSTRUCTION
    lowered = TOPIC_ANSWER_DIRECTIVE.lower()
    assert "verdict" in lowered and "recommendation" in lowered, TOPIC_ANSWER_DIRECTIVE
    assert "published" in lowered


def test_the_directive_is_the_last_instruction_before_the_question() -> None:
    content = build_synth_messages(Q5, [_finding()], topic_question=True)[1]["content"]
    assert content.index(TOPIC_ANSWER_DIRECTIVE) < content.index("USER QUESTION")
    assert content.index("FINDINGS:") < content.index(TOPIC_ANSWER_DIRECTIVE)


# ---------------------------------------------------------------------------
# End to end: the four refusals, offline.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_API_KEY", "")


@pytest.fixture(autouse=True)
def _no_op_daily_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", lambda *a, **k: None)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", lambda *a, **k: None)


async def _resolved(curies: list[str]) -> tuple[list[str], int]:
    """A stand-in for `resolve_disease_mention_to_curies`, which is a live
    MedGen lookup. Returns the bound CURIEs and the index match count."""
    return list(curies), len(curies)


def _install_model(
    monkeypatch: pytest.MonkeyPatch, disease_mention: str | None = None
) -> list[str]:
    """A model that resolves NO entity, which is the measured condition:
    the question names a chemical or a population and the product has
    neither resolver. Returns the list the Synth prompts land in.

    With `disease_mention`, the model instead labels that span a DISEASE,
    which is the flip a live run cannot be made to produce on demand: the
    Think model does it on some runs and not others for the same text."""
    from system_03_search_agent.core.graph import _THINK_SYSTEM_INSTRUCTION
    from system_03_search_agent.guardrail.classifier import GUARD_SYSTEM_INSTRUCTION

    synth_prompts: list[str] = []

    async def _dispatch(*args: Any, **kwargs: Any) -> Any:
        messages = kwargs.get("messages") or []
        joined = "\n".join(m.get("content") or "" for m in messages)
        if GUARD_SYSTEM_INSTRUCTION in joined:
            return fake_response(COMPLIANT_GUARD_CLASSIFICATION)
        if _THINK_SYSTEM_INSTRUCTION in joined:
            entities = (
                [{"text": disease_mention, "entity_type": "disease"}]
                if disease_mention
                else []
            )
            return fake_response(
                json.dumps(
                    {
                        "query_class": "exploratory",
                        "narrative": "a topic question naming no gene or disease",
                        "entities": entities,
                    }
                )
            )
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            synth_prompts.append(joined)
            return fake_response(compliant_synth_narrative(messages))
        return fake_response("ok")

    monkeypatch.setattr(harness_module.litellm, "acompletion", _dispatch)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )
    return synth_prompts


class _TopicToolSpy:
    """Every tool faked. `cypher_query` raises if it is ever called, which
    is how the test proves the graph call is not planned rather than
    planned and ignored."""

    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, *, pubmed_ids: list[str] | None = None
    ) -> None:
        self.search_terms: list[str] = []
        self.fetched_ids: list[list[str]] = []
        self.graph_calls = 0
        self.pubmed_ids = [_PMID] if pubmed_ids is None else pubmed_ids
        spy = self

        async def _cypher(harness: Any, cypher_input: Any, **kwargs: Any) -> CypherQueryOutput:
            spy.graph_calls += 1
            return CypherQueryOutput(
                status="empty", row_count=0, total_available=0, truncated=False,
                rows=[], error=None, template=None,
            )

        async def _efetch(tool_input: Any, **kwargs: Any) -> NcbiEfetchOutput:
            root = tool_input.root
            if root.action == "search":
                spy.search_terms.append(root.term)
                return NcbiEfetchOutput(
                    status="ok" if spy.pubmed_ids else "empty",
                    action="search",
                    records=[
                        NcbiEfetchRecord(
                            db=root.db,
                            fields={
                                "idlist": list(spy.pubmed_ids),
                                "idlist_count": len(spy.pubmed_ids),
                            },
                        )
                    ],
                    record_count=1,
                    total_available=len(spy.pubmed_ids),
                    truncated=False,
                )
            if root.action == "fetch":
                spy.fetched_ids.append(list(root.ids))
                records = [
                    NcbiEfetchRecord(
                        id=pmid,
                        db="pubmed",
                        fields={"title": f"{_TITLE} {pmid}"},
                        source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    )
                    for pmid in root.ids
                ]
                return NcbiEfetchOutput(
                    status="ok", action="fetch", records=records,
                    record_count=len(records), total_available=len(records),
                    truncated=False,
                )
            return NcbiEfetchOutput(
                status="empty", action=root.action, records=[], record_count=0,
                total_available=None, truncated=False, error=None,
            )

        async def _pubtator(tool_input: Any, **kwargs: Any) -> PubtatorAnnotateOutput:
            root = tool_input.root
            if root.mode == "annotate_publications":
                return PubtatorAnnotateOutput(
                    status="ok",
                    mode="annotate_publications",
                    publications=[
                        PubtatorPublication(
                            pmid=pmid,
                            total_annotations=2,
                            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        )
                        for pmid in root.pmids
                    ],
                )
            return PubtatorAnnotateOutput(status="empty", mode="entity_lookup")

        monkeypatch.setattr(graph_module, "cypher_query", _cypher)
        monkeypatch.setattr(graph_module, "ncbi_efetch", _efetch)
        monkeypatch.setattr(graph_module, "pubtator_annotate", _pubtator)


async def _events(text: str, session_id: str) -> list[Any]:
    query = Query(
        text=text, session_id=session_id, trace_id=f"trace-{session_id}",
        user_id=None, audience_depth="researcher",
    )
    context = RequestContext(surface="web_ui", session_memory=None, operator_mode=False)
    return [event async for event in run_streaming(query, context)]


def _plan_tools(events: list[Any]) -> list[str]:
    plan = next(e for e in events if e.type == "plan")
    return [c["tool"] for c in plan.payload["tool_calls"]]


def _sources(events: list[Any]) -> set[str]:
    return {e.payload["source_url"] for e in events if e.type == "citation"}


def _text(events: list[Any]) -> str:
    return "".join(e.payload["text"] for e in events if e.type == "token")


@pytest.mark.asyncio
@pytest.mark.parametrize("index,question", list(enumerate(MEASURED_TERMS)))
async def test_each_refusing_question_now_answers_with_a_cited_paper(
    monkeypatch: pytest.MonkeyPatch, index: int, question: str
) -> None:
    _install_model(monkeypatch)
    spy = _TopicToolSpy(monkeypatch)
    events = await _events(question, session_id=f"topic-{index}")

    assert spy.search_terms == [MEASURED_TERMS[question]], spy.search_terms
    # Populate check for the arm above: with nothing resolved the narrative
    # says so, so the two wordings are read from what happened rather than
    # one of them being dead text.
    narrative = next(e for e in events if e.type == "plan").payload["narrative"]
    assert "no gene, variant or disease was named" in narrative, narrative
    done = next(e for e in events if e.type == "done")
    assert done.payload["trust_outcome"] != "refuse", done.payload
    assert _PMID_URL in _sources(events), _sources(events)
    # The reader is not asked to name a gene, variant, disease or organism.
    assert "Name one and I will search" not in _text(events), _text(events)


@pytest.mark.asyncio
async def test_the_graph_is_not_called_at_all_for_a_topic_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no CURIE, `cypher_query` can only return "no entity could be
    identified", `act_node` records that in `failed_searches`, and the
    answer then carries "One of the background searches did not finish"
    where nothing failed. A call that can only fail is not planned."""
    _install_model(monkeypatch)
    spy = _TopicToolSpy(monkeypatch)
    events = await _events(Q4, session_id="topic-nograph")
    assert spy.graph_calls == 0
    assert "cypher_query" not in _plan_tools(events), _plan_tools(events)
    assert _plan_tools(events) == [
        "ncbi_efetch", "ncbi_efetch", "pubtator_annotate",
    ], _plan_tools(events)
    done = next(e for e in events if e.type == "done")
    assert done.payload["trust_outcome"] == "answer", done.payload


@pytest.mark.asyncio
async def test_the_answer_is_framed_as_what_has_been_published(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The product owner's hard line for this set: it may return papers
    about caffeine and exercise performance and must never tell a person
    whether coffee will help them."""
    synth_prompts = _install_model(monkeypatch)
    _TopicToolSpy(monkeypatch)
    await _events(Q5, session_id="topic-framing")
    assert synth_prompts, "the synth tier was never reached"
    assert all(TOPIC_ANSWER_DIRECTIVE in prompt for prompt in synth_prompts)


@pytest.mark.asyncio
async def test_a_question_that_resolves_an_entity_never_takes_the_topic_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The populate check for the whole end-to-end set. The SAME question
    text, run with a model that resolves a gene, plans its graph call and
    no topic search, so every arm above is a property of nothing having
    resolved rather than of the question's words."""
    from system_03_search_agent.core.graph import _THINK_SYSTEM_INSTRUCTION
    from system_03_search_agent.guardrail.classifier import GUARD_SYSTEM_INSTRUCTION

    async def _dispatch(*args: Any, **kwargs: Any) -> Any:
        messages = kwargs.get("messages") or []
        joined = "\n".join(m.get("content") or "" for m in messages)
        if GUARD_SYSTEM_INSTRUCTION in joined:
            return fake_response(COMPLIANT_GUARD_CLASSIFICATION)
        if _THINK_SYSTEM_INSTRUCTION in joined:
            return fake_response(
                json.dumps(
                    {
                        "query_class": "lookup",
                        "narrative": "a gene question",
                        "entities": [{"text": "BRCA1", "entity_type": "gene"}],
                    }
                )
            )
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            return fake_response(compliant_synth_narrative(messages))
        return fake_response("ok")

    async def _symbol(symbol: str, **kwargs: Any) -> str | None:
        return {"BRCA1": "NCBIGene:672"}.get(symbol.strip().upper())

    monkeypatch.setattr(harness_module.litellm, "acompletion", _dispatch)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )
    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _symbol)
    spy = _TopicToolSpy(monkeypatch)
    events = await _events("What does BRCA1 do?", session_id="topic-gene")
    assert spy.graph_calls >= 1
    assert "cypher_query" in _plan_tools(events), _plan_tools(events)
    assert MEASURED_TERMS[Q4] not in spy.search_terms, spy.search_terms
    # The gene's own PubMed term, not a topic term built from the sentence.
    assert "BRCA1[Title/Abstract]" in spy.search_terms, spy.search_terms


def _stub_decisions(monkeypatch: pytest.MonkeyPatch, literature: str | None) -> list[str]:
    """Stub `core.graph.decide` (build phase 8.2). `plan.literature` answers
    `literature` (None: no usable pick); every other point answers its safe
    option. Returns the points asked, in order.

    Whether a question asks for the published literature has been a
    classifier's call since 2026-09-25 (card 3), never a word list, so these
    arms say what the classifier decided rather than which words were typed.
    """
    from system_03_search_agent.contracts.events import DecisionRecord

    safe = {
        "guardrail.relevancy": "on_topic",
        "think.ask_back": "proceed",
        "think.recent_years": "not_applicable",
        "plan.literature": literature,
    }
    asked: list[str] = []

    async def _decide(harness: Any, trace_id: str, point: str, state: str, options: Any, **kwargs: Any) -> Any:
        asked.append(point)
        pick = safe.get(point)
        if pick is None:
            return DecisionRecord(
                name=point, options=list(options), chosen=next(iter(options)),
                decided_by="guard", fallback_reason="timeout",
            )
        return DecisionRecord(
            name=point, options=list(options), chosen=pick, decided_by="jev",
            jev_choice=pick, guard_choice=pick, agreed=True,
        )

    monkeypatch.setattr(graph_module, "decide", _decide)
    return asked


def _memory(
    *mentions: tuple[str, str], entity_type: str = "Gene"
) -> SessionMemorySummary:
    from datetime import UTC, datetime

    return SessionMemorySummary(
        session_id="mem",
        last_updated=datetime.now(UTC),
        resolved_entities=[
            ResolvedEntity(mention=mention, curie=curie, entity_type=entity_type)
            for mention, curie in mentions
        ],
        open_threads=[],
        compressed_findings=[],
    )


async def _events_with_memory(
    text: str, session_id: str, memory: SessionMemorySummary
) -> list[Any]:
    query = Query(
        text=text, session_id=session_id, trace_id=f"trace-{session_id}",
        user_id=None, audience_depth="researcher",
    )
    context = RequestContext(
        surface="web_ui", session_memory=memory, operator_mode=False
    )
    return [event async for event in run_streaming(query, context)]


@pytest.mark.asyncio
async def test_a_new_subject_is_not_hijacked_by_the_remembered_entity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measured 2026-09-23 in a session that had already resolved BRCA1:
    the caffeine question bound `NCBIGene:672`, planned the whole gene
    fan-out and searched `BRCA1[Title/Abstract]`. A person who types a new
    question about caffeine after one about a gene got papers about the
    gene, which is worse than the refusal it replaces.

    `docs/build/Search_and_conversation_behaviour.md` already says a
    follow-up binds to the antecedent when it "names no entity of its own
    but carries a referring word", and the caffeine question carries
    none."""
    _install_model(monkeypatch)
    spy = _TopicToolSpy(monkeypatch)
    events = await _events_with_memory(
        Q4, "topic-mem-new", _memory(("BRCA1", "NCBIGene:672"))
    )
    assert spy.graph_calls == 0
    assert spy.search_terms == [MEASURED_TERMS[Q4]], spy.search_terms
    assert "cypher_query" not in _plan_tools(events), _plan_tools(events)


@pytest.mark.asyncio
async def test_a_remembered_DISEASE_does_not_hijack_the_new_subject_either(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asked explicitly at review, because the seven questions get typed in
    ONE browser session and the first three resolve a DISEASE, not a gene.
    The antecedent rule reads `memory_bound`, which is set for any bound
    antecedent whatever its type, so this is the same code path and is
    asserted rather than reasoned about."""
    _install_model(monkeypatch)
    spy = _TopicToolSpy(monkeypatch)
    events = await _events_with_memory(
        Q4,
        "topic-mem-disease",
        _memory(("GERD", "MedGen:C5563728"), entity_type="Disease"),
    )
    assert spy.graph_calls == 0
    assert spy.search_terms == [MEASURED_TERMS[Q4]], spy.search_terms
    assert "cypher_query" not in _plan_tools(events), _plan_tools(events)


@pytest.mark.asyncio
async def test_a_referring_follow_up_still_binds_the_remembered_entity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The populate check for the arm above, and the behaviour it must not
    break: a follow-up carrying a referring word is a continuation, so the
    antecedent wins and the topic path stays out of the way."""
    _install_model(monkeypatch)
    spy = _TopicToolSpy(monkeypatch)
    events = await _events_with_memory(
        "What variants cause it?", "topic-mem-ref", _memory(("BRCA1", "NCBIGene:672"))
    )
    assert spy.graph_calls >= 1
    assert "cypher_query" in _plan_tools(events), _plan_tools(events)
    assert MEASURED_TERMS[Q4] not in spy.search_terms, spy.search_terms


@pytest.mark.asyncio
async def test_a_one_word_continuation_still_binds_the_remembered_entity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A continuation with no pronoun leaves ONE content word behind, and
    one leftover word is far likelier to be a fragment than a new subject,
    so the antecedent keeps it.

    THIS ARM CALLS `plan_node` DIRECTLY, and the reason is worth stating
    because an end-to-end arm would be the natural thing to write and would
    be a lie. Measured 2026-09-23: the guardrail's biomedical allowlist
    refuses EVERY one-content-word phrasing tried ("and in women?", "and
    caffeine?", "about caffeine", "what about caffeine", seven more), so
    this branch cannot be reached through `run_streaming` at all today. The
    rule is therefore defensive rather than load-bearing, and it becomes
    reachable the moment that allowlist widens, which another worker was
    changing the same day. An arm that ran the whole loop would pass on a
    guardrail refusal while claiming to measure this."""
    from system_03_search_agent.harness.harness import Harness

    state: dict[str, Any] = {
        "harness": Harness(trace_id="trace-one-word"),
        "query": Query(
            text="and in women?", session_id="one-word", trace_id="trace-one-word",
            user_id=None, audience_depth="researcher",
        ),
        "seq": 0,
        "context": RequestContext(
            surface="web_ui",
            session_memory=_memory(("BRCA1", "NCBIGene:672")),
            operator_mode=False,
        ),
        "resolved_entities": [],
        "unresolved_entity_symbols": [],
        "query_class": "exploratory",
    }
    assert breadth_plan.topic_search_words("and in women?") == ["women"]
    _stub_decisions(monkeypatch, literature="not_literature")
    result = await graph_module.plan_node(state)  # type: ignore[arg-type]
    assert result["topic_search_term"] == "", result["topic_search_term"]
    assert next(c.tool_call.tool for c in result["tool_calls"]) == "cypher_query"

    # Populate check: the SAME state with a two-word new subject takes the
    # topic path, so the emptiness above is the one-word rule firing rather
    # than `plan_node` never planning a topic search from this state.
    state["query"] = Query(
        text="caffeine and exercise", session_id="one-word-2",
        trace_id="trace-one-word-2", user_id=None, audience_depth="researcher",
    )
    result2 = await graph_module.plan_node(state)  # type: ignore[arg-type]
    assert result2["topic_search_term"] == "caffeine AND exercise", result2


@pytest.mark.asyncio
async def test_a_question_asking_for_papers_reaches_the_papers_whatever_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The review defect. `resolve_disease_mention_to_curies("caffeine")`
    binds EIGHT MedGen concepts, every one a real disorder ("Caffeine
    dependence", "Caffeine withdrawal", "Organic mental disorder caused by
    caffeine"), because MedGen's name index matches any title CONTAINING
    the word. Whether they reach the answer depends on whether the Think
    model labels `caffeine` a disease span on that run.

    Here the model is FORCED to label it, which is the flip a live run
    cannot be made to produce on demand. The reader asked for papers, so
    papers are what runs. Who says the reader asked for papers is the
    `plan.literature` classifier since build phase 8.2, stubbed here."""
    _install_model(monkeypatch, disease_mention="caffeine")
    asked = _stub_decisions(monkeypatch, literature="wants_literature")
    spy = _TopicToolSpy(monkeypatch)
    monkeypatch.setattr(
        graph_module, "resolve_disease_mention_to_curies",
        lambda mention: _resolved(["MedGen:C1386553", "MedGen:C0521652"]),
    )
    events = await _events(Q4, session_id="topic-flip")
    assert "plan.literature" in asked, asked
    assert spy.search_terms == [MEASURED_TERMS[Q4]], spy.search_terms
    assert spy.graph_calls == 0
    assert "cypher_query" not in _plan_tools(events), _plan_tools(events)
    assert _PMID_URL in _sources(events), _sources(events)
    # The screen tells the reader what actually happened. Caught by reading
    # this line's own live output on `papers on GERD`, where a disease DID
    # resolve and the narrative still said none was named.
    narrative = next(e for e in events if e.type == "plan").payload["narrative"]
    assert "you asked for published papers" in narrative, narrative
    assert "no gene, variant or disease was named" not in narrative, narrative


@pytest.mark.asyncio
async def test_a_gene_question_that_also_asks_for_papers_keeps_the_gene_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The hard constraint on the rule above: a question that resolves a
    GENE must behave exactly as it does today, and "recent papers on
    BRCA1" both resolves a gene and names the published literature. The
    gene wins, and its own literature leg (`BRCA1[Title/Abstract]`) is what
    searches PubMed, not a topic term built from the sentence.

    Written because a mutation that let the literature request override a
    resolved gene passed every other arm in this file."""
    from system_03_search_agent.core.graph import _THINK_SYSTEM_INSTRUCTION
    from system_03_search_agent.guardrail.classifier import GUARD_SYSTEM_INSTRUCTION

    async def _dispatch(*args: Any, **kwargs: Any) -> Any:
        messages = kwargs.get("messages") or []
        joined = "\n".join(m.get("content") or "" for m in messages)
        if GUARD_SYSTEM_INSTRUCTION in joined:
            return fake_response(COMPLIANT_GUARD_CLASSIFICATION)
        if _THINK_SYSTEM_INSTRUCTION in joined:
            return fake_response(
                json.dumps(
                    {
                        "query_class": "lookup",
                        "narrative": "a gene question that also asks for papers",
                        "entities": [{"text": "BRCA1", "entity_type": "gene"}],
                    }
                )
            )
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            return fake_response(compliant_synth_narrative(messages))
        return fake_response("ok")

    async def _symbol(symbol: str, **kwargs: Any) -> str | None:
        return {"BRCA1": "NCBIGene:672"}.get(symbol.strip().upper())

    monkeypatch.setattr(harness_module.litellm, "acompletion", _dispatch)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )
    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _symbol)
    spy = _TopicToolSpy(monkeypatch)
    question = "recent papers on BRCA1"
    _stub_decisions(monkeypatch, literature="wants_literature")
    events = await _events(question, session_id="topic-gene-papers")
    assert spy.graph_calls >= 1
    assert "cypher_query" in _plan_tools(events), _plan_tools(events)
    assert "BRCA1[Title/Abstract]" in spy.search_terms, spy.search_terms
    assert (breadth_plan.build_topic_term(question) or "") not in spy.search_terms


@pytest.mark.asyncio
async def test_a_request_for_papers_beats_the_remembered_entity_even_at_one_word(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two-word rule protects a continuation, not a new subject, and a
    question that names the published literature has said what it is about.
    `papers on caffeine` leaves ONE content word, so the two-word rule
    alone would hand the turn to the remembered gene; naming the literature
    is what stops it.

    Written because a mutation removing exactly that clause passed every
    other arm in this file."""
    _install_model(monkeypatch)
    spy = _TopicToolSpy(monkeypatch)
    question = "papers on caffeine"
    assert breadth_plan.topic_search_words(question) == ["caffeine"]
    _stub_decisions(monkeypatch, literature="wants_literature")
    await _events_with_memory(
        question, "topic-mem-papers", _memory(("BRCA1", "NCBIGene:672"))
    )
    assert spy.graph_calls == 0
    assert spy.search_terms == ["caffeine"], spy.search_terms


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("literature", "takes_the_topic_path"),
    [
        # `Any trials for GERD?` must keep its disease path, its MedGen
        # record and its trials leg: a trial is the ClinicalTrials.gov
        # registry, a different source the disease path already searches.
        ("not_literature", False),
        # No usable pick is treated as not asking for papers, which is what
        # this path did before the decision existed.
        (None, False),
        # The same resolved disease with the classifier saying papers: the
        # literature search runs, whatever words were typed.
        ("wants_literature", True),
    ],
)
async def test_the_classifier_not_the_words_decides_a_disease_questions_path(
    monkeypatch: pytest.MonkeyPatch, literature: str | None, takes_the_topic_path: bool
) -> None:
    """Build phase 8.2, card 3: the word list that decided this until
    2026-09-25 is gone. One question, one resolved disease, and only the
    `plan.literature` decision differs between the three arms, so the path
    taken is the classifier's call and nothing else's.

    MUTATION PROOF: making `plan_node` ignore `literature_choice` (always
    False) turns the `wants_literature` arm red."""
    _install_model(monkeypatch, disease_mention="GERD")
    _stub_decisions(monkeypatch, literature=literature)
    spy = _TopicToolSpy(monkeypatch)
    monkeypatch.setattr(
        graph_module, "resolve_disease_mention_to_curies",
        lambda mention: _resolved(["MedGen:C5563728"]),
    )
    events = await _events("Any trials for GERD?", session_id=f"topic-disease-{literature}")
    if takes_the_topic_path:
        assert spy.graph_calls == 0
        assert "cypher_query" not in _plan_tools(events), _plan_tools(events)
    else:
        assert spy.graph_calls >= 1
        assert "cypher_query" in _plan_tools(events), _plan_tools(events)


@pytest.mark.asyncio
async def test_a_topic_question_in_a_fresh_session_needs_no_second_word_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two-word rule applies ONLY where an antecedent would otherwise
    win. With nothing remembered there is no contest, so a single-word
    question still searches. Same question as the arm above, same session
    text, and only the memory differs."""
    _install_model(monkeypatch)
    spy = _TopicToolSpy(monkeypatch)
    await _events("papers on caffeine", session_id="topic-oneword")
    assert spy.search_terms == ["caffeine"], spy.search_terms
    assert spy.graph_calls == 0


@pytest.mark.asyncio
async def test_a_topic_search_that_finds_nothing_says_what_it_searched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The done-when allows a genuine empty result to refuse, and requires
    the refusal to say what was searched rather than ask for a gene."""
    _install_model(monkeypatch)
    _TopicToolSpy(monkeypatch, pubmed_ids=[])
    events = await _events(Q6, session_id="topic-empty")
    done = next(e for e in events if e.type == "done")
    assert done.payload["trust_outcome"] == "refuse", done.payload
    text = _text(events)
    assert "I searched the published literature for" in text, text
    assert "variants, people, mediterranean, descent" in text, text
    assert "Name one and I will search" not in text, text


@pytest.mark.asyncio
async def test_three_runs_of_one_topic_question_plan_and_cite_the_same_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Item 11.21's rule. The fake returns its PMIDs in a DIFFERENT ORDER
    on each run, so an arm that passed only because the inputs never moved
    would fail here."""
    orders = [
        ["33388079", "32589582"],
        ["32589582", "33388079"],
        ["33388079", "32589582"],
    ]
    plans: list[list[str]] = []
    terms: list[list[str]] = []
    citations: list[set[str]] = []
    for index, pmids in enumerate(orders):
        _install_model(monkeypatch)
        spy = _TopicToolSpy(monkeypatch, pubmed_ids=pmids)
        events = await _events(Q7, session_id=f"topic-run{index}")
        plans.append(_plan_tools(events))
        terms.append(list(spy.search_terms))
        citations.append(_sources(events))
    assert plans[0] == plans[1] == plans[2], plans
    assert terms[0] == terms[1] == terms[2] == [MEASURED_TERMS[Q7]], terms
    assert citations[0] == citations[1] == citations[2], citations
    # Populate check: the runs actually cited something, so three identical
    # empty sets cannot pass this.
    assert _PMID_URL in citations[0], citations[0]
