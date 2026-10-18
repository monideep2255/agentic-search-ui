"""Cards 103 and 104, reproduced offline with the real table builder.

No network, no graph, no model. Calls `core.graph._answer_tokens` (the
function that turns grounded sentences into the answer's tables) on
findings shaped like the evidence:

- Card 103: five HNF1A variants whose only ClinVar conditions are the
  placeholders "not provided" / "not specified" (read-only graph probe,
  `probe_card103_graph.py`), beside one variant with a real condition.
- Card 104, case A: the BRCA1 gene record cited once through the graph
  (`.../gene/672`, no slash) and once through live Datasets
  (`.../gene/672/`, slash), both labelled "BRCA1" (query 107 evidence).
- Card 104, case B: the same page cited twice with two labels, "BRCA1 DNA
  repair associated" and "BRCA1" (the saved gene answer evidence).

Usage, from the worktree root:

    <venv>/bin/python testing/Developer/reports/2026-10-08_card103_104/raw/repro_offline.py
"""
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path("src").resolve()))

from system_03_search_agent.contracts.events import CitationPayload, source_page_key
from system_03_search_agent.core.graph import _answer_tokens
from system_03_search_agent.harness.coordinator_worker import Finding
from system_03_search_agent.synthesis.answer_layout import (
    placeholder_link_count,
    placeholder_links_note,
)
from system_03_search_agent.synthesis.findings import SynthFinding


def finding(call_id: str, tool: str, layer: str, rows: list[dict]) -> Finding:
    return Finding(
        call_id=call_id,
        tool=tool,
        layer=layer,
        source="structured_pass_through",
        structured_fields={
            "status": "ok",
            "row_count": len(rows),
            "total_available": len(rows),
            "truncated": False,
            "rows": rows,
            "error": None,
        },
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
    )


def citation(index: int, cid: str, url: str, layer: str, source: str, source_id: str) -> CitationPayload:
    return CitationPayload(
        citation_id=cid,
        display_index=index,
        source=source,
        source_id=source_id,
        source_url=url,
        layer=layer,  # type: ignore[arg-type]
        field="name",
        claim_text="claim",
        evidence_kind="database_record",
        assertion_confidence="asserted",
        license="public domain",
    )


def run(rows_by_call, synth, cites, sentences, condition_names=None):
    findings = [finding(c, t, layer, rows) for c, t, layer, rows in rows_by_call]
    tokens = _answer_tokens(
        audience_depth="researcher",
        question="question",
        model_grounding=None,
        model_layout=SimpleNamespace(sentence_paragraph=[], heading_before={}),  # type: ignore[arg-type]
        fallback_sentences=tuple(sentences),
        tail_sentences=(),
        tail_is_listing=False,
        citations=cites,
        synth_findings=synth,
        findings=findings,
        mentions=[],
        notes=[],
        condition_names=condition_names,
    )
    return findings, tokens


def show(title: str, tokens) -> None:
    print("=" * 72)
    print(title)
    for t in tokens:
        if t.kind in ("heading", "table_header", "table_row", "list_item", "note"):
            cells = t.cells if t.cells is not None else t.text.strip()[:110]
            print(f"  {t.kind:13} {cells}  markers={t.marker_ids}")


# ---------------------------------------------------------------- card 103
TITLES = {
    "MedGen:C3661900": "not provided",
    "MedGen:CN169374": "not specified",
    "MedGen:C0342276": "Maturity-onset diabetes of the young",
}
variants = [
    ("ClinVar:1048822", ["MedGen:C3661900"]),
    ("ClinVar:1051750", ["MedGen:C3661900"]),
    ("ClinVar:1098821", ["MedGen:CN169374"]),
    ("ClinVar:1104934", ["MedGen:C3661900"]),
    ("ClinVar:1105252", ["MedGen:C3661900"]),
    ("ClinVar:2000001", ["MedGen:C0342276", "MedGen:C3661900"]),
]
v_rows = [
    {
        "node_or_edge_type": "SequenceVariant",
        "curie": curie,
        "fields": {"name": f"variant {curie}", "clinvar_condition_ids": conds},
        "source_url": f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{curie.split(':')[1]}/",
        "graph_snapshot_version": "v1",
    }
    for curie, conds in variants
]
v_synth = [
    SynthFinding(
        ref_index=i + 1,
        citation_id=f"cq-1-{i + 1}",
        layer="layer_1_graph",
        tool="cypher_query",
        field="name",
        field_value=row["fields"]["name"],
        source_url=row["source_url"],
        entity_type="SequenceVariant",
        curie=row["curie"],
        call_id="cq-1",
    )
    for i, row in enumerate(v_rows)
]
v_cites = [
    citation(i + 1, s.citation_id, s.source_url, "layer_1_graph", "ClinVar", s.curie)
    for i, s in enumerate(v_synth)
]
_, tokens = run(
    [("cq-1", "cypher_query", "layer_1_graph", v_rows)],
    v_synth,
    v_cites,
    [f"{s.field_value} [{s.ref_index}]." for s in v_synth],
    condition_names=TITLES,
)
show("Card 103: variant-to-disease table, placeholder-only variants", tokens)
note = placeholder_links_note(
    placeholder_link_count([("SequenceVariant", r["fields"]) for r in v_rows], TITLES)
)
print("  Notes-list line built later in write_node:", note)
unresolved = placeholder_link_count(
    [("SequenceVariant", {"clinvar_condition_ids": ["MedGen:C9999999"]})], {"MedGen:C9999999": None}
)
print("  A link whose name lookup failed is counted by the note as:", unresolved)

# ---------------------------------------------------------------- card 104
graph_gene = {
    "node_or_edge_type": "Gene",
    "curie": "NCBIGene:672",
    "fields": {"name": "BRCA1", "symbol": "BRCA1"},
    "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
    "graph_snapshot_version": "v1",
}
live_gene = {
    "curie": "NCBIGene:672",
    "fields": {"symbol": "BRCA1"},
    "source_url": "https://www.ncbi.nlm.nih.gov/gene/672/",
}


def gene_case(label_a: str, label_b: str, url_b: str):
    a = dict(graph_gene, fields={"name": label_a})
    b = dict(live_gene, fields={"symbol": label_b}, source_url=url_b)
    synth = [
        SynthFinding(
            ref_index=8, citation_id="cq-g-8", layer="layer_1_graph", tool="cypher_query",
            field="name", field_value=label_a, source_url=a["source_url"], entity_type="Gene",
            curie="NCBIGene:672", call_id="cq-g",
        ),
        SynthFinding(
            ref_index=12, citation_id="nd-g-12", layer="layer_2_api", tool="ncbi_efetch",
            field="symbol", field_value=label_b, source_url=b["source_url"], entity_type="gene",
            curie="NCBIGene:672", call_id="nd-g",
        ),
    ]
    cites = [
        citation(8, "cq-g-8", a["source_url"], "layer_1_graph", "NCBIGene", "NCBIGene:672"),
        citation(12, "nd-g-12", b["source_url"], "layer_2_api", "gene", "672"),
    ]
    _, toks = run(
        [("cq-g", "cypher_query", "layer_1_graph", [a]), ("nd-g", "ncbi_efetch", "layer_2_api", [b])],
        synth,
        cites,
        ["BRCA1 [8].", "BRCA1 [12]."],
    )
    pages = {source_page_key(c.source_url) for c in cites}
    return toks, pages


toks, pages = gene_case("BRCA1", "BRCA1", "https://www.ncbi.nlm.nih.gov/gene/672/")
show(f"Card 104 case A: graph link + live link with slash; Sources page keys = {sorted(pages)}", toks)
toks, pages = gene_case("BRCA1 DNA repair associated", "BRCA1", "https://www.ncbi.nlm.nih.gov/gene/672")
show(f"Card 104 case B: one exact link, two labels; Sources page keys = {sorted(pages)}", toks)
toks, pages = gene_case("BRCA1", "BRCA1", "https://www.ncbi.nlm.nih.gov/gene/672")
show(f"Control: one exact link, one label; Sources page keys = {sorted(pages)}", toks)
