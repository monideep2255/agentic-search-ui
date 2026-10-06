"""Run one scenario against this branch's graph.py or develop's (argv[1] = branch|develop).
Throwaway adversary probe; mocked model, classifier and NCBI."""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

if sys.argv[1] == "develop":
    import system_03_search_agent.core as core_pkg

    spec = importlib.util.spec_from_file_location("system_03_search_agent.core.graph", HERE / "develop_graph.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["system_03_search_agent.core.graph"] = mod
    spec.loader.exec_module(mod)
    core_pkg.graph = mod

import pytest

from system_03_search_agent.core import graph as g
from tests.system_03_search_agent.core import test_think_empty_extraction as T

MEDGEN = {}


async def think(question, replies, picks=None, taxonomy=None, genes=None, medgen=None):
    mp = pytest.MonkeyPatch()
    try:
        if taxonomy:
            mp.setattr(T, "TAXONOMY", {**T.TAXONOMY, **taxonomy})
        if genes:
            mp.setattr(T, "GENES", {**T.GENES, **genes})
        searched, genes_asked = T._install_ncbi(mp)
        medgen = medgen or {}

        async def _dis(mention, *a, **k):
            searched.append(("medgen-mention", mention))
            hit = medgen.get(mention.upper())
            return (list(hit), len(hit)) if hit else ([], 0)

        mp.setattr(g, "resolve_disease_mention_to_curies", _dis)
        if hasattr(g, "_GENE_OR_CONDITION"):
            T._install_decisions(mp, picks or {})
        else:
            async def _decide(harness, trace_id, point, state, options, **kw):
                from system_03_search_agent.contracts.events import DecisionRecord
                return DecisionRecord(name=point, options=list(options), chosen=kw.get("default") or options[0],
                                      decided_by="guard", fallback_reason="no_usable_pick")
            mp.setattr(g, "decide", _decide)
        calls = T._install_replies(mp, replies)
        result = await g.think_node(T._state(question))
        recs = result.get("organism_records")
        try:
            plan = await g.plan_node({**T._state(question), **result})
            planned = [repr(tc)[:160] for tc in plan.get("tool_calls") or []]
        except Exception as exc:  # noqa: BLE001
            planned = f"plan error {type(exc).__name__}: {exc}"[:200]
        return {
            "planned": planned,
            "model_calls": len(calls),
            "resolved": [(e.text, e.curie) for e in result.get("resolved_entities", [])],
            "organism_records": None if recs is None else (recs.organism.mention, recs.organism.taxid, recs.record_type),
            "unresolved": result.get("unresolved_entity_symbols"),
            "clarification": (result.get("clarification_needed") or "")[:110] or None,
            "searched": [s for s in searched if s[0] != "taxonomy"],
            "genes_asked": genes_asked,
        }
    finally:
        mp.undo()


def reply(entities, record_type="sra"):
    return json.dumps({"query_class": "exploratory", "narrative": "n",
                       "entities": [{"text": t, "entity_type": k} for t, k in entities], "record_type": record_type})


SCENARIOS = {
    "retry_flips_record_type": ("Find SRA runs of SARS-CoV-2 sequenced on Illumina", [reply([]), reply([("SARS-CoV-2", "organism")], "assembly")], {}),
    "host_and_pathogen": ("SARS-CoV-2 SRA runs from human clinical samples", [reply([("SARS-CoV-2", "organism"), ("human", "organism")])], {}),
    "retry_two_orgs": ("Find SRA runs of SARS-CoV-2 sequenced on Illumina", [reply([]), reply([("SARS-CoV-2", "organism"), ("Homo sapiens", "organism")])], {"taxonomy": {"homo sapiens": ["9606"]}}),
    "covid_patients_empty": ("SRA runs from COVID-19 patients", [reply([])], {"medgen": {"COVID": ["MedGen:C5203670"]}}),
    "mody_empty": ("SRA runs from MODY patients", [reply([])], {"medgen": {"MODY": ["MedGen:C0342276"]}}),
    "cf_empty": ("Sequencing runs from CF patients in SRA", [reply([])], {"medgen": {"CF": ["MedGen:C0010674"]}}),
    "brca1_empty": ("SRA runs of BRCA1 knockout cells", [reply([])], {}),
    "brca9_noorg": ("SRA runs of BRCA9 knockouts", [reply([("BRCA9", "gene")])], {}),
    "tp53_assembly_empty": ("Genome assemblies of TP53 mutant cell lines", [reply([], "assembly")], {"genes": {"TP53": "NCBIGene:7157"}}),
    "orf8_gene_kept": ("E. coli SRA runs carrying mcr-1", [reply([("E. coli", "organism"), ("mcr-1", "gene")])], {"taxonomy": {"e. coli": ["562"]}, "picks": {"mcr-1": "gene"}}),
}


async def main():
    for name in sys.argv[2:]:
        q, replies, kw = SCENARIOS[name]
        out = await think(q, replies, **kw)
        print(sys.argv[1], name, json.dumps(out, default=str))


asyncio.run(main())
