"""Card 23 adversary: mixed groups, MedGen outage, and the 25-id lookup cap. Throwaway."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path.cwd() / "src"))
sys.path.insert(0, str(Path.cwd() / "tests" / "system_03_search_agent" / "core"))

import pytest
import test_write_answer_structure as T

from system_03_search_agent.core import graph as G
from system_03_search_agent.harness.coordinator_worker import Finding
from system_03_search_agent.synthesis import disease_names as D
from system_03_search_agent.synthesis.answer_layout import (
    VARIANT_TO_DISEASE_SOURCE_NOTE as NOTE,
)
from system_03_search_agent.tools import ncbi_eutils_actions as A


def env(mp):
    for k, v in {"GUARD_MODEL": "test-provider/guard-model", "PLAN_MODEL": "test-provider/plan-model",
                 "SYNTH_MODEL": "test-provider/synth-model", "PER_QUERY_COST_CAP_USD": "1.0",
                 "SYSTEM_DAILY_CAP_USD": "1000000"}.items():
        mp.setenv(k, v)


def summarize(name, result):
    toks = T._tokens(result)
    heads = [t["text"].strip() for t in toks if t["kind"] == "heading"]
    tables = T._tables(toks)
    print(f"\n=== {name}")
    print("  headings:", heads)
    for hdr, rows in tables:
        print("  table", hdr, "rows:", [r["cells"] for r in rows][:6])
    print("  source note count:", sum(1 for t in toks if t["kind"] == "note" and t["text"] == NOTE))
    print("  other notes:", [t["text"][:90] for t in toks if t["kind"] == "note" and t["text"] != NOTE])


async def mixed():
    mp = pytest.MonkeyPatch()
    try:
        env(mp)
        mp.setattr(G, "resolve_concept_ids", T._fake_resolve_concept_ids)
        T._install(mp, lambda lines: f"{lines[1]} [1].")
        state = T._state("researcher", rows=T._FOLDED_VARIANT_ROWS)
        extra = Finding(
            call_id="cq-second", tool="cypher_query", layer="layer_1_graph", source="structured_pass_through",
            structured_fields={"status": "ok", "row_count": 1, "total_available": 1, "truncated": False,
                               "rows": [{"node_or_edge_type": "SequenceVariant", "curie": "ClinVar:9",
                                         "fields": {"name": "variant nine, no fold"},
                                         "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/9",
                                         "graph_snapshot_version": "v1"}], "error": None},
            extracted_entities=None, normalized_ids=None, evidence_summary=None)
        state["findings"] = [*state["findings"], extra]
        state["findings_count"] = 2
        summarize("M1 folded variants plus a non-fold variant from a second graph call", await G.write_node(state))
    finally:
        mp.undo()


async def real_resolver(name, rows, titles, fail=False):
    calls = {"search_terms": 0}

    async def fake_search(inp):
        calls["search_terms"] = inp.term.count("[ConceptId]")
        if fail:
            raise TimeoutError("NCBI down")
        ids = [c.split("[")[0] for c in inp.term.split(" OR ")]
        return SimpleNamespace(status="ok", records=[SimpleNamespace(fields={"idlist": [str(1000 + i) for i, _ in enumerate(ids)]})])

    async def fake_summary(inp):
        return SimpleNamespace(status="ok", records=[
            SimpleNamespace(fields={"conceptid": cid, "title": t}) for cid, t in titles.items()])

    mp = pytest.MonkeyPatch()
    try:
        env(mp)
        D.reset_cache_for_tests()
        mp.setattr(A, "search", fake_search)
        mp.setattr(A, "summary", fake_summary)
        T._install(mp, lambda lines: f"{lines[1]} [1].")
        summarize(name, await G.write_node(T._state("researcher", rows=rows)))
        print("  ids sent to NCBI in the one search:", calls["search_terms"])
    finally:
        mp.undo()


async def main():
    await mixed()
    await real_resolver("M2 MedGen down", T._FOLDED_VARIANT_ROWS,
                        {"C0342276": "Maturity-onset diabetes of the young"}, fail=True)
    # 30 distinct CURIEs on one variant row; titles exist for all of them.
    curies = [f"MedGen:C{1000000 + i}" for i in range(30)]
    titles = {c.split(":")[1]: f"Real disease {i}" for i, c in enumerate(curies)}
    rows = [
        {"node_or_edge_type": "SequenceVariant", "curie": "ClinVar:1",
         "fields": {"name": "variant one", "clinvar_condition_ids": curies[:12]},
         "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/1", "graph_snapshot_version": "v1"},
        {"node_or_edge_type": "SequenceVariant", "curie": "ClinVar:2",
         "fields": {"name": "variant two", "clinvar_condition_ids": curies[12:24]},
         "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/2", "graph_snapshot_version": "v1"},
        {"node_or_edge_type": "SequenceVariant", "curie": "ClinVar:3",
         "fields": {"name": "variant three", "clinvar_condition_ids": curies[24:30]},
         "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/3", "graph_snapshot_version": "v1"},
    ]
    await real_resolver("M3 30 distinct linked diseases (lookup cap is 25)", rows, titles)


asyncio.run(main())
