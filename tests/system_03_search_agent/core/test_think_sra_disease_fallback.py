"""Card 56 follow-up (2026-10-06): on a question that asks for SRA runs or
genome assemblies, a disease is never bound from a piece of a hyphen-joined
name.

Drives the real `think_node` with only the Plan-tier model, NCBI's `search`
and `summary` actions and the gene resolver faked. No network.

Measured live before this file (testing/Developer/reports/2026-10-06_card56/
findings.md): on develop's plan model, 5 of 26 valid runs of the SARS-CoV-2
SRA question returned no entity at all, the token fallback cut "SARS" out of
"SARS-CoV-2", and MedGen bound three records about the disease SARS. The
product owner chose the smallest safe fix: skip such a piece in the disease
fallback on an SRA or assembly question, and change nothing else.

Each arm names the one mutation of the change that turns it red
(testing/Developer/reports/2026-10-06_card56/build_r3.md, "Tests"):

- The SRA and assembly arms: the piece is no longer skipped, or skipped on
  SRA only, or only for the ASCII hyphen.
- The MODY arm: every candidate is skipped on an SRA question, not only a
  piece of a name.
- The paper arm: the skip ignores the record type.
- The follow-up arms: the whole disease fallback is skipped on an SRA
  question.
- The parse-retry arms: the retry message or the narrative repair goes back
  to a hand-kept key list without `record_type`.

The arms that say "as on develop" were also run against develop's
`graph.py` (fcfc6827) and passed there unchanged; the SRA and assembly arms
went red there.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from system_03_search_agent.contracts.query import (
    Query,
    RequestContext,
    ResolvedEntity,
    SessionMemorySummary,
)
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools import ncbi_eutils_actions

#: The question develop was asked on 2026-10-05 and answered about SARS.
SRA_QUESTION = (
    "Find SRA runs of SARS{h}CoV{h}2 sequenced on Illumina from clinical "
    "respiratory samples, and explain why each one matched."
)
ASSEMBLY_QUESTION = "Which SARS-CoV-2 genome assemblies exist, and how do I get each one?"
MODY_QUESTION = "SRA runs from MODY patients"
PAPER_QUESTION = "papers on SARS-CoV-2"

TAXONOMY = {
    "sars-cov-2": ["2697049"],
    "mycobacterium tuberculosis": ["1773"],
}
#: MedGen as faked here: "SARS[title]" binds the three records it bound live
#: on 2026-10-05, "MODY[title]" binds one MODY record, everything else none
#: ("SRA[title]" is 0 hits live, judge round 1).
MEDGEN = {
    "SARS[title]": ["1001", "1002", "1003"],
    "MODY[title]": ["2001"],
}
MEDGEN_TITLES = {
    "1001": ("C1519126", "SARS Coronavirus Protease Pathway"),
    "1002": ("C4302012", "Probable SARS"),
    "1003": ("C4302019", "SARS (severe acute respiratory syndrome) confirmed"),
    "2001": ("C1833382", "Impaired glucose tolerance in MODY"),
}
SARS_CURIES = ["MedGen:C1519126", "MedGen:C4302012", "MedGen:C4302019"]


class _Record:
    def __init__(self, fields: dict[str, Any]) -> None:
        self.fields = fields


def _install_ncbi(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Fake ESearch and ESummary; returns every (db, term) searched."""
    searched: list[tuple[str, str]] = []

    async def _search(params: Any) -> Any:
        searched.append((params.db, params.term))
        if params.db == "taxonomy":
            ids = TAXONOMY.get(params.term.split("[")[0].strip().casefold(), [])
        elif params.db == "medgen":
            ids = MEDGEN.get(params.term, [])
        else:
            ids = []
        return SimpleNamespace(
            status="ok" if ids else "empty",
            records=[_Record({"idlist": ids})] if ids else [],
        )

    async def _summary(params: Any) -> Any:
        return SimpleNamespace(
            status="ok",
            records=[
                _Record({"conceptid": MEDGEN_TITLES[uid][0], "title": MEDGEN_TITLES[uid][1]})
                for uid in params.ids
                if uid in MEDGEN_TITLES
            ],
        )

    async def _gene(symbol: str, *, taxon: str = "human") -> str | None:
        return "NCBIGene:672" if symbol.upper() == "BRCA1" else None

    monkeypatch.setattr(ncbi_eutils_actions, "search", _search)
    monkeypatch.setattr(ncbi_eutils_actions, "summary", _summary)
    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _gene)
    graph_module._DISEASE_CURIE_CACHE.clear()
    graph_module._ORGANISM_KNOWN_CACHE.clear()
    return searched


def _set_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")


def _install_model(
    monkeypatch: pytest.MonkeyPatch, record_type: str, entities: list[tuple[str, str]] = ()
) -> None:
    """Every model call gets the same Think reply, as in test_think_organisms."""
    classification = graph_module._ThinkClassification(
        query_class="exploratory",
        entities=[graph_module._ThinkExtractedEntity(text=t, entity_type=k) for t, k in entities],
        narrative="Asks for records.",
        record_type=record_type,
    )

    async def _fake_dispatch(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(content=classification.model_dump_json())

    monkeypatch.setattr(graph_module, "_dispatch_tier_call", _fake_dispatch)
    _set_models(monkeypatch)


def _memory(mention: str, curie: str, entity_type: str) -> SessionMemorySummary:
    return SessionMemorySummary(
        session_id="s-sra-fallback",
        last_updated=datetime.now(UTC),
        resolved_entities=[ResolvedEntity(mention=mention, curie=curie, entity_type=entity_type)],
    )


def _state(text: str, memory: SessionMemorySummary | None = None) -> dict[str, Any]:
    return {
        "query": Query(text=text, session_id="s-sra-fallback", trace_id="t-sra", user_id=None),
        "context": RequestContext(surface="rest_sse", session_memory=memory),
        "harness": harness_module.Harness(trace_id="t-sra"),
        "seq": 0,
        "findings": [],
        "findings_count": 0,
    }


def _outcome(result: dict[str, Any]) -> dict[str, Any]:
    """What the person meets after Think: the records bound, the question
    asked back, the organism route and any refusal by name."""
    organism_records = result.get("organism_records")
    return {
        "resolved": [
            (entity.text, entity.curie) for entity in result.get("resolved_entities") or []
        ],
        "clarification": result.get("clarification_needed"),
        "organism_records": (
            (organism_records.organism.curie, organism_records.record_type)
            if organism_records is not None
            else None
        ),
        "unresolved": result.get("unresolved_entity_symbols"),
    }


# ---------------------------------------------------------------------------
# An SRA or assembly question never binds a disease from a piece of a name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hyphen",
    ["-", "\u2010", "\u2011", "\u2013"],
    ids=["ascii-hyphen", "unicode-hyphen", "non-breaking-hyphen", "dash"],
)
async def test_sra_question_with_no_entity_binds_no_medgen_record(
    monkeypatch: pytest.MonkeyPatch, hyphen: str
) -> None:
    searched = _install_ncbi(monkeypatch)
    _install_model(monkeypatch, "sra")
    result = await graph_module.think_node(_state(SRA_QUESTION.format(h=hyphen)))
    outcome = _outcome(result)
    assert not any(curie.startswith("MedGen:") for _, curie in outcome["resolved"]), outcome
    assert ("medgen", "SARS[title]") not in searched, searched
    # Populate check: the run ends where develop ends when nothing resolved,
    # with develop's own question asked back ("each one" refers back).
    assert outcome["clarification"] == graph_module.CLARIFICATION_QUESTION, outcome
    # The whole word "SRA" is still tried, as on develop.
    assert ("medgen", "SRA[title]") in searched, searched


@pytest.mark.asyncio
async def test_assembly_question_with_no_entity_binds_no_medgen_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    searched = _install_ncbi(monkeypatch)
    _install_model(monkeypatch, "assembly")
    result = await graph_module.think_node(_state(ASSEMBLY_QUESTION))
    outcome = _outcome(result)
    assert not any(curie.startswith("MedGen:") for _, curie in outcome["resolved"]), outcome
    assert ("medgen", "SARS[title]") not in searched, searched
    assert outcome["clarification"] == graph_module.CLARIFICATION_QUESTION, outcome


# ---------------------------------------------------------------------------
# Everything else behaves exactly as on develop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_whole_word_on_an_sra_question_still_binds_as_on_develop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    searched = _install_ncbi(monkeypatch)
    _install_model(monkeypatch, "sra")
    result = await graph_module.think_node(_state(MODY_QUESTION))
    assert _outcome(result) == {
        "resolved": [("MODY", "MedGen:C1833382")],
        "clarification": None,
        "organism_records": None,
        "unresolved": None,
    }
    assert [term for db, term in searched if db == "medgen"] == ["SRA[title]", "MODY[title]"]


@pytest.mark.asyncio
async def test_a_paper_question_is_unchanged_from_develop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Record type "none": the piece is still tried, exactly as develop
    tries it, SARS records included. This change is fenced to SRA and
    assembly questions by the owner's decision."""
    searched = _install_ncbi(monkeypatch)
    _install_model(monkeypatch, "none")
    result = await graph_module.think_node(_state(PAPER_QUESTION))
    assert _outcome(result) == {
        "resolved": [("SARS", curie) for curie in SARS_CURIES],
        "clarification": None,
        "organism_records": None,
        "unresolved": None,
    }
    assert ("medgen", "SARS[title]") in searched, searched


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "memory", "entities", "expected"),
    [
        (
            "What SRA runs are there for it?",
            ("BRCA1", "NCBIGene:672", "Gene"),
            [],
            {"resolved": [], "clarification": None, "organism_records": None, "unresolved": None},
        ),
        (
            "And its SRA runs?",
            ("Mycobacterium tuberculosis", "NCBITaxon:1773", "Organism"),
            [],
            {"resolved": [], "clarification": None, "organism_records": None, "unresolved": None},
        ),
        (
            "And its SRA runs?",
            ("Mycobacterium tuberculosis", "NCBITaxon:1773", "Organism"),
            [("Mycobacterium tuberculosis", "organism")],
            {
                "resolved": [("Mycobacterium tuberculosis", "NCBITaxon:1773")],
                "clarification": None,
                "organism_records": ("NCBITaxon:1773", "sra"),
                "unresolved": None,
            },
        ),
    ],
    ids=["brca1-no-entity", "tuberculosis-no-entity", "tuberculosis-tagged"],
)
async def test_a_follow_up_with_session_memory_is_unchanged_from_develop(
    monkeypatch: pytest.MonkeyPatch,
    question: str,
    memory: tuple[str, str, str],
    entities: list[tuple[str, str]],
    expected: dict[str, Any],
) -> None:
    """With nothing extracted, the disease fallback still runs on the whole
    word "SRA" (nothing binds, as live), and memory supplies the subject, so
    nothing is asked back; Plan binds the remembered entity afterwards."""
    searched = _install_ncbi(monkeypatch)
    _install_model(monkeypatch, "sra", entities)
    result = await graph_module.think_node(_state(question, _memory(*memory)))
    assert _outcome(result) == expected
    medgen_terms = [term for db, term in searched if db == "medgen"]
    assert medgen_terms == ([] if entities else ["SRA[title]"]), searched


# ---------------------------------------------------------------------------
# #173's parse retry keeps the record type (round 1 judge, J-56-04)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_parse_retry_asks_for_every_schema_key(monkeypatch: pytest.MonkeyPatch) -> None:
    replies = [
        "not json",
        json.dumps(
            {
                "query_class": "exploratory",
                "narrative": "Asks for SRA runs.",
                "entities": [{"text": "SARS-CoV-2", "entity_type": "organism"}],
                "record_type": "sra",
            }
        ),
    ]
    sent: list[list[dict[str, Any]]] = []

    async def _fake_dispatch(*args: Any, **kwargs: Any) -> Any:
        sent.append(list(args[4]))
        return SimpleNamespace(content=replies[len(sent) - 1])

    monkeypatch.setattr(graph_module, "_dispatch_tier_call", _fake_dispatch)
    _set_models(monkeypatch)
    harness = harness_module.Harness(trace_id="t-retry")
    outcome = await graph_module._run_think_classification(
        harness, "t-retry", [{"role": "user", "content": "q"}]
    )
    assert isinstance(outcome, graph_module._ThinkClassification), outcome
    assert outcome.record_type == "sra"
    assert len(sent) == 2
    retry_text = sent[1][-1]["content"]
    for key in ("query_class", "narrative", "entities", "record_type"):
        assert f'"{key}"' in retry_text, retry_text
    assert set(graph_module._ThinkClassification.model_fields) == {
        "query_class",
        "narrative",
        "entities",
        "record_type",
    }


def test_the_narrative_repair_counts_record_type_as_a_known_key() -> None:
    """A well-formed SRA reply that wrote "why" for "narrative" is repaired
    in place, not sent to the parse retry where it could lose its record
    type."""
    reply = json.dumps(
        {
            "query_class": "exploratory",
            "why": "Asks for SRA runs.",
            "entities": [{"text": "SARS-CoV-2", "entity_type": "organism"}],
            "record_type": "sra",
        }
    )
    classification = graph_module._parse_think_classification(reply)
    assert classification.record_type == "sra"
    assert classification.narrative == "Asks for SRA runs."
    # Populate check: a genuinely unknown key beside the alias still fails.
    with pytest.raises(graph_module.ThinkClassificationUnavailableError):
        graph_module._parse_think_classification(
            json.dumps({"query_class": "exploratory", "why": "x", "entities": [], "bogus": 1})
        )
