"""Card 37, slice A1: a dbSNP record is named by its rs id.

Measured live 2026-10-09: "Found 1 variant record record for rs334:
not-provided, protective, likely-benign, pathogenic, other." The record was
named by its clinical significance list because the dbSNP row puts that field
first on purpose (it is a high-risk claim field the trust verdict reads).

The fix is layout only, through closed tables in `answer_layout` keyed by the
exact row type `Variant record`: the label reads `rsid`, the Researcher table
gains a Gene column and a Clinical significance column, and Plain language
reads "Genetic variant (HBB)". The row's field order and what the writing
model is given do not move, and the guard arm below pins that. Every other
record type keeps develop's label, column and plain label exactly.
"""

from __future__ import annotations

import re
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.contracts.token_order import in_reading_order
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.coordinator_worker import Finding
from system_03_search_agent.synthesis.answer_layout import (
    TABLE_COLUMNS,
    plain_record_label,
    record_label,
    record_status_or_year,
    summary_label,
    table_second_cell,
)
from system_03_search_agent.synthesis.findings import (
    SYNTH_SYSTEM_INSTRUCTION,
    SynthFinding,
    build_synth_findings,
)
from system_03_search_agent.synthesis.trust import risk_tier_for

SIGNIFICANCE = "not-provided, protective, likely-benign, pathogenic, other"
RS334_URL = "https://www.ncbi.nlm.nih.gov/snp/rs334"


def _real_row(
    rsid: str = "rs334",
    *,
    significance: list[str] | None = None,
    consequence: list[str] | None = None,
    genes: list[str] | None = None,
) -> dict:
    """The dbSNP pseudo-row as the REAL builder in `core.graph` shapes it
    (V-37-04), so a reorder of that builder turns the guard arm red."""
    from system_03_search_agent.tools.ncbi_dbsnp_schemas import NcbiDbsnpGene, NcbiDbsnpOutput

    output = NcbiDbsnpOutput(
        status="ok",
        rsid=rsid,
        spdi_canonical="NC_000011.10:5227001:T:A",
        chrpos="11:5227002",
        clinical_significance=significance or [],
        functional_consequence=consequence or [],
        genes=[NcbiDbsnpGene(name=g) for g in (genes or [])],
        source_url=f"https://www.ncbi.nlm.nih.gov/snp/{rsid}",
    )
    shaped = graph_module._layer_tool_output_to_structured_fields("ncbi_dbsnp", output)
    assert shaped["rows"], "populate-check: the real builder returned no row"
    return shaped["rows"][0]


def _rs334_row() -> dict:
    return _real_row(
        significance=SIGNIFICANCE.split(", "),
        consequence=["missense variant"],
        genes=["HBB"],
    )


def _rs6025_row() -> dict:
    """dbSNP's tool withholds a significance list that is over long, so the
    row's first field is the functional consequence (V-37-01)."""
    return _real_row(
        "rs6025", consequence=["coding_sequence_variant", "missense_variant"], genes=["F5"]
    )


def _finding_for(row: dict, *, tool: str = "ncbi_dbsnp", layer: str = "layer_2_api") -> Finding:
    return Finding(
        call_id=f"call-{tool}",
        tool=tool,
        layer=layer,  # type: ignore[arg-type]
        source="structured_pass_through",
        structured_fields={
            "status": "ok",
            "row_count": 1,
            "total_available": 1,
            "truncated": False,
            "rows": [row],
            "error": None,
        },
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
    )


def _synth(row: dict, **kwargs) -> SynthFinding:
    findings, _capped = build_synth_findings(
        [_finding_for(row, **kwargs)], graph_module._pick_representative_field
    )
    assert findings, "populate-check: the row produced no finding"
    return findings[0]


# ---------------------------------------------------------------- the guard


def test_the_writers_input_and_the_trust_verdict_do_not_move() -> None:
    """The fix is in the list only. The row's one finding is still its
    clinical significance, a high-risk field, so the prompt line and the
    hedged-or-asserted label of every rs id answer are what they were."""
    finding = _synth(_rs334_row())
    assert finding.field == "clinical_significance", finding
    assert finding.field_value == SIGNIFICANCE
    assert risk_tier_for("clinical_significance", "Variant record") == "high"
    assert risk_tier_for("rsid", "Variant record") != "high"
    row = _rs334_row()
    assert list(row["fields"]) == [
        "clinical_significance",
        "functional_consequence",
        "rsid",
        "genes",
        "chrpos",
    ], list(row["fields"])
    assert _synth(_rs6025_row()).field == "functional_consequence"


# ---------------------------------------------------------------- the label


def test_the_record_is_labelled_by_its_rs_id_not_its_significance_list() -> None:
    finding = _synth(_rs334_row())
    fields = _rs334_row()["fields"]
    assert record_label(finding, fields) == "rs334"
    assert summary_label(finding, {"fields": fields}) == "rs334"


def test_a_dbsnp_row_with_no_rs_id_keeps_develops_label() -> None:
    row = graph_module._pseudo_row(
        "Variant record", {"clinical_significance": SIGNIFICANCE, "genes": "HBB"}, RS334_URL
    )
    finding = _synth(row)
    assert record_label(finding, row["fields"]) == SIGNIFICANCE


def test_the_table_row_shows_the_gene_and_the_significance_in_four_cells() -> None:
    fields = _rs334_row()["fields"]
    assert TABLE_COLUMNS["Variant record"] == ("genes", "Variant", "Gene")
    assert table_second_cell("Variant record", fields) == "HBB"
    assert record_status_or_year("Variant record", fields) == (
        "Clinical significance",
        SIGNIFICANCE,
    )
    # With the mapping column shown, the significance column still shows.
    assert record_status_or_year("Variant record", fields, mapping_shown=True) == (
        "Clinical significance",
        SIGNIFICANCE,
    )


def test_a_variant_record_without_a_gene_has_no_gene_cell() -> None:
    assert table_second_cell("Variant record", {"rsid": "rs1"}) is None
    assert record_status_or_year("Variant record", {"rsid": "rs1"}) is None


def test_the_plain_language_label_names_the_gene() -> None:
    finding = _synth(_rs334_row())
    fields = _rs334_row()["fields"]
    expected = f"Genetic variant (HBB), clinical significance: {SIGNIFICANCE}"
    assert plain_record_label(finding, fields, "rs334") == expected
    # Without an identifier passed in, the rs id still never shows.
    assert plain_record_label(finding, fields) == expected


def test_the_plain_language_label_without_a_gene_is_the_everyday_noun() -> None:
    row = graph_module._pseudo_row(
        "Variant record", {"clinical_significance": SIGNIFICANCE, "rsid": "rs334"}, RS334_URL
    )
    finding = _synth(row)
    assert plain_record_label(finding, row["fields"], "rs334") == (
        f"Genetic variant, clinical significance: {SIGNIFICANCE}"
    )
    bare = _real_row("rs1")
    assert plain_record_label(_synth(bare), bare["fields"], "rs1") == "Genetic variant"


# ------------------------------------------------- no other type moves


def _develop_label_for(finding: SynthFinding, fields: dict) -> tuple:
    return (
        record_label(finding, fields),
        plain_record_label(finding, fields, ""),
        record_status_or_year(finding.entity_type, fields),
        table_second_cell(finding.entity_type, fields),
    )


def test_a_pubtator3_publication_row_keeps_its_label_column_and_plain_label() -> None:
    row = graph_module._pseudo_row(
        "Publication",
        {"pmid": "12345678", "annotation_count": 7},
        "https://pubmed.ncbi.nlm.nih.gov/12345678/",
    )
    finding = _synth(row, tool="pubtator_annotate", layer="layer_3_enrichment")
    assert finding.entity_type == "Publication"
    assert "Publication" not in TABLE_COLUMNS
    label, plain, extra, second = _develop_label_for(finding, row["fields"])
    # Card 134: a publication row with no title is never named by its number
    # a second time beside its Identifier cell, and Plain language reads its
    # everyday noun. The row's cited fact is still its PMID.
    assert finding.field == "pmid" and finding.field_value == "12345678"
    assert label == "Title not retrieved"
    assert plain == "Published paper"
    assert extra is None
    assert second is None


def test_a_layer_2_gene_row_with_an_organism_keeps_its_label_column_and_plain_label() -> None:
    row = graph_module._pseudo_row(
        "gene",
        {"name": "HBB", "organism": "Homo sapiens", "genes": "HBB", "rsid": "rs334"},
        "https://www.ncbi.nlm.nih.gov/gene/3043",
    )
    finding = _synth(row, tool="ncbi_efetch")
    assert finding.entity_type == "gene"
    assert "gene" not in TABLE_COLUMNS
    label, plain, extra, second = _develop_label_for(finding, row["fields"])
    assert label == "HBB"
    assert plain == "HBB"
    assert extra is None
    assert second is None


def test_a_litvar2_literature_variant_row_with_a_gene_keeps_its_label_and_columns() -> None:
    row = graph_module._pseudo_row(
        "Literature variant",
        {"name": "rs334", "gene": "HBB", "clinical_significance": "pathogenic"},
        "https://www.ncbi.nlm.nih.gov/research/litvar2/rs334",
    )
    finding = _synth(row, tool="litvar2_lookup", layer="layer_3_enrichment")
    assert finding.entity_type == "Literature variant"
    assert "Literature variant" not in TABLE_COLUMNS
    label, plain, extra, second = _develop_label_for(finding, row["fields"])
    assert label == "rs334"
    assert extra is None
    assert second is None
    assert "HBB" not in plain


# ------------------------------------------------- the whole answer page

_FINDING_LINE = re.compile(r"^\[(\d+)\]\s+(.+)$", re.MULTILINE)


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")


def _install(monkeypatch: pytest.MonkeyPatch, prompts: list[str]) -> None:
    """The Synth call is faked; it records the prompt it was shown and
    returns a sentence that grounds nothing, so the code-built page stands."""

    async def _dispatch(*_args: object, **kwargs: object):
        messages = kwargs.get("messages") or []
        joined = "\n".join(m.get("content") or "" for m in messages)  # type: ignore[union-attr]
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            prompts.append(joined)
            content = "Nothing here matches any record at all."
        else:
            content = "ok"
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )

    monkeypatch.setattr(harness_module.litellm, "acompletion", AsyncMock(side_effect=_dispatch))
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )


def _state(depth: str) -> dict[str, object]:
    query = Query(
        text="What is rs334 and what condition is it associated with?",
        session_id="session-rs334",
        trace_id="trace-rs334",
        user_id=None,
        audience_depth=depth,  # type: ignore[arg-type]
    )
    return {
        "query": query,
        "harness": harness_module.Harness(trace_id=query.trace_id),
        "context": RequestContext(surface="web_ui", reads_placement=True),
        "seq": 0,
        "start_monotonic": time.monotonic(),
        "findings": [_finding_for(_rs334_row())],
        "findings_count": 1,
    }


async def _page(monkeypatch: pytest.MonkeyPatch, depth: str) -> tuple[list[dict], list[str]]:
    prompts: list[str] = []
    _install(monkeypatch, prompts)
    result = await graph_module.write_node(_state(depth))
    tokens = in_reading_order([e.payload for e in result["events"] if e.type == "token"])
    return tokens, prompts


@pytest.mark.asyncio
async def test_researcher_page_names_rs334_and_shows_gene_and_significance(monkeypatch) -> None:
    tokens, prompts = await _page(monkeypatch, "researcher")
    headers = [t["cells"] for t in tokens if t["kind"] == "table_header"]
    rows = [t["cells"] for t in tokens if t["kind"] == "table_row"]
    assert headers == [["Variant", "Identifier", "Gene", "Clinical significance"]], headers
    assert rows == [["rs334", "rs334", "HBB", SIGNIFICANCE]], rows
    assert len(rows[0]) == 4
    assert prompts, "populate-check: the writer was never shown the findings"
    assert "clinical_significance" in prompts[0] or SIGNIFICANCE in prompts[0]
    assert "HBB" not in prompts[0]


@pytest.mark.asyncio
async def test_opening_sentence_is_pinned_as_it_reads_now(monkeypatch) -> None:
    """Pins the sentence as it reads with this change. Card 131 fixed
    the doubled "record record"."""
    tokens, _ = await _page(monkeypatch, "researcher")
    first = next(t["text"] for t in tokens if t["text"].startswith("Found"))
    assert first.strip() == "Found 1 variant record: rs334 [1].", first
    assert SIGNIFICANCE not in first


@pytest.mark.asyncio
async def test_plain_language_page_reads_genetic_variant_hbb(monkeypatch) -> None:
    tokens, _ = await _page(monkeypatch, "plain_language")
    items = [t["cells"] for t in tokens if t["kind"] == "list_item"]
    assert items == [[f"Genetic variant (HBB), clinical significance: {SIGNIFICANCE}"]], items
    assert not any(t["kind"] in ("table_header", "table_row") for t in tokens)


# ------------------------------------------------- fix round (verifier A1)


def test_v37_01_a_withheld_significance_shows_the_consequence_in_its_own_column() -> None:
    row = _rs6025_row()
    finding = _synth(row)
    fields = row["fields"]
    assert "clinical_significance" not in fields
    assert record_label(finding, fields) == "rs6025"
    assert table_second_cell("Variant record", fields) == "F5"
    assert record_status_or_year("Variant record", fields) == (
        "Consequence",
        "coding_sequence_variant, missense_variant",
    )
    assert plain_record_label(finding, fields, "rs6025") == (
        "Genetic variant (F5), consequence: coding_sequence_variant, missense_variant"
    )


def test_v37_01_significance_wins_over_the_consequence_when_both_exist() -> None:
    fields = _rs334_row()["fields"]
    assert record_status_or_year("Variant record", fields)[0] == "Clinical significance"


@pytest.mark.asyncio
async def test_v37_01_researcher_page_for_a_withheld_significance_keeps_the_consequence(
    monkeypatch,
) -> None:
    prompts: list[str] = []
    _install(monkeypatch, prompts)
    state = _state("researcher")
    state["findings"] = [_finding_for(_rs6025_row())]
    result = await graph_module.write_node(state)
    tokens = in_reading_order([e.payload for e in result["events"] if e.type == "token"])
    headers = [t["cells"] for t in tokens if t["kind"] == "table_header"]
    rows = [t["cells"] for t in tokens if t["kind"] == "table_row"]
    assert headers == [["Variant", "Identifier", "Gene", "Consequence"]], headers
    assert rows == [["rs6025", "rs6025", "F5", "coding_sequence_variant, missense_variant"]], rows


def _long_terms(count: int) -> str:
    return ", ".join(f"established-risk-allele-{n:02d}-term" for n in range(count))


def test_v37_03_a_long_list_is_cut_between_terms_never_inside_one() -> None:
    value = _long_terms(30)
    assert len(value) > 500
    column = record_status_or_year("Variant record", {"clinical_significance": value})[1]
    assert len(column) <= 500
    assert column.endswith("\u2026")
    kept = column[:-1].split(", ")
    assert kept == value.split(", ")[: len(kept)]
    assert len(kept) < 30
    row = {"clinical_significance": value, "genes": "HBB", "rsid": "rs1"}
    finding = _synth(graph_module._pseudo_row("Variant record", row, RS334_URL))
    plain = plain_record_label(finding, row, "rs1")
    assert len(plain) <= 500
    assert plain.startswith("Genetic variant (HBB), clinical significance: ")
    assert set(plain[:-1].split(": ", 1)[1].split(", ")) <= set(value.split(", "))


def test_v37_03_a_list_that_fits_is_unchanged() -> None:
    assert record_status_or_year("Variant record", {"clinical_significance": SIGNIFICANCE}) == (
        "Clinical significance",
        SIGNIFICANCE,
    )


def test_v37_05_a_url_in_the_rs_id_field_is_never_the_label() -> None:
    row = graph_module._pseudo_row(
        "Variant record",
        {"clinical_significance": "benign", "rsid": "https://example.org/rs1"},
        RS334_URL,
    )
    finding = _synth(row)
    assert record_label(finding, row["fields"]) != "https://example.org/rs1"
    assert record_label(finding, row["fields"]) == "benign"


# ------------------------------------- fix round: a table mixing the two


async def _table(monkeypatch, rows: list[dict]) -> tuple[list[list[str]], list[list[str]]]:
    prompts: list[str] = []
    _install(monkeypatch, prompts)
    state = _state("researcher")
    finding = _finding_for(rows[0])
    finding.structured_fields["rows"] = rows
    finding.structured_fields["row_count"] = len(rows)
    finding.structured_fields["total_available"] = len(rows)
    state["findings"] = [finding]
    result = await graph_module.write_node(state)
    tokens = in_reading_order([e.payload for e in result["events"] if e.type == "token"])
    return (
        [t["cells"] for t in tokens if t["kind"] == "table_header"],
        [t["cells"] for t in tokens if t["kind"] == "table_row"],
    )


@pytest.mark.asyncio
async def test_a_mixed_table_names_each_value_for_what_it_is(monkeypatch) -> None:
    headers, rows = await _table(monkeypatch, [_rs334_row(), _rs6025_row()])
    assert headers == [["Variant", "Identifier", "Gene", "Clinical significance or consequence"]]
    by_id = {row[1]: row for row in rows}
    assert by_id["rs334"][3] == f"significance: {SIGNIFICANCE}"
    assert by_id["rs6025"][3] == "consequence: coding_sequence_variant, missense_variant"
    assert all(len(row) == 4 for row in rows)


@pytest.mark.asyncio
async def test_a_table_of_significance_lists_keeps_its_heading_and_plain_cells(
    monkeypatch,
) -> None:
    other = _real_row("rs7412", significance=["benign"], genes=["APOE"])
    headers, rows = await _table(monkeypatch, [_rs334_row(), other])
    assert headers == [["Variant", "Identifier", "Gene", "Clinical significance"]]
    assert {row[3] for row in rows} == {SIGNIFICANCE, "benign"}


@pytest.mark.asyncio
async def test_a_table_of_consequences_keeps_its_heading_and_plain_cells(monkeypatch) -> None:
    other = _real_row("rs429358", consequence=["missense_variant"], genes=["APOE"])
    headers, rows = await _table(monkeypatch, [_rs6025_row(), other])
    assert headers == [["Variant", "Identifier", "Gene", "Consequence"]]
    assert {row[3] for row in rows} == {
        "coding_sequence_variant, missense_variant",
        "missense_variant",
    }


def test_another_row_type_with_mixed_extras_follows_the_first_label_rule() -> None:
    from system_03_search_agent.synthesis.answer_layout import name_mixed_variant_extras

    extras = [("Status", "RECRUITING"), ("Published", "2020")]
    assert name_mixed_variant_extras("Clinical trial", extras) is extras
    mixed = [("Clinical significance", "x"), ("Consequence", "y")]
    assert name_mixed_variant_extras("Clinical trial", mixed) is mixed
