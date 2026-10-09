"""Adversary round 2 offline probe, card 56. Mocked model, classifier and NCBI.
Throwaway; not a test. Run from the worktree root with the main venv python."""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import pytest

from system_03_search_agent.core import graph as g
from tests.system_03_search_agent.core import test_think_empty_extraction as T


async def think(question, replies, picks, taxonomy=None, genes=None, medgen=None):
    mp = pytest.MonkeyPatch()
    try:
        if taxonomy:
            mp.setattr(T, "TAXONOMY", {**T.TAXONOMY, **taxonomy})
        if genes:
            mp.setattr(T, "GENES", {**T.GENES, **genes})
        searched, genes_asked = T._install_ncbi(mp)
        if medgen:
            orig = g.resolve_disease_mention_to_curies

            async def _dis(mention, *a, **k):
                if mention in medgen:
                    searched.append(("medgen-mention", mention))
                    return medgen[mention], len(medgen[mention])
                return await orig(mention, *a, **k)

            mp.setattr(g, "resolve_disease_mention_to_curies", _dis)
        asked = T._install_decisions(mp, picks)
        calls = T._install_replies(mp, replies)
        result = await g.think_node(T._state(question))
        think_ev = next((e for e in result.get("events", []) if e.type == "think"), None)
        recs = result.get("organism_records")
        return {
            "model_calls": len(calls),
            "decisions": [(p, s) for p, s in asked if p == "think.gene_or_condition"],
            "resolved": [(e.text, e.curie) for e in result.get("resolved_entities", [])],
            "organism_records": None if recs is None else (recs.organism.mention, recs.organism.taxid, recs.record_type, recs.conditions_not_applied),
            "note": g._organism_conditions_note(result),
            "unresolved": result.get("unresolved_entity_symbols"),
            "clarification": result.get("clarification_needed"),
            "narrative": think_ev.payload["narrative"] if think_ev else None,
            "searched": searched,
            "genes_asked": genes_asked,
        }
    finally:
        mp.undo()


def reply(entities, record_type="sra", narrative="Asks for sequencing records."):
    return T._reply(entities, record_type, narrative)


def show(label, out, keys=None):
    keys = keys or list(out)
    print("==", label)
    print(json.dumps({k: out[k] for k in keys}, indent=1, default=str))


async def main(which):
    if which == "illumina_org_bypass":
        q = "Find SRA runs sequenced on Illumina from clinical respiratory samples"
        out = await think(
            q,
            [reply([]), reply([("Illumina", "organism"), ("Homo sapiens", "organism")])],
            {},
            taxonomy={"homo sapiens": ["9606"], "illumina": []},
        )
        show(q, out, ["model_calls", "resolved", "organism_records", "clarification", "narrative", "searched"])
    elif which == "substring":
        cases = [
            ("Find SRA runs sequenced on Illumina from clinical respiratory samples", "rat", {"rat": ["10116"]}),
            ("SRA runs of humanized immune system samples", "human", {}),
            ("Genome assemblies of the pigmented isolates from the outbreak", "pig", {"pig": ["9823"]}),
            ("SRA runs of the variant strains from the hospital", "ant", {"ant": ["7393"]}),
        ]
        for q, org, tax in cases:
            out = await think(q, [reply([]), reply([(org, "organism")])], {}, taxonomy=tax)
            show(f"{q} | retry names {org!r}", out, ["model_calls", "resolved", "organism_records", "clarification"])
    elif which == "renamed":
        cases = [
            ("SRA runs of E. coli from hospital wastewater", "Escherichia coli", {"escherichia coli": ["562"], "e. coli": ["562"]}),
            ("Find SRA runs of SARS CoV 2 sequenced on Illumina", "SARS-CoV-2", {}),
            ("Genome assemblies of M. tuberculosis lineage 2", "Mycobacterium tuberculosis", {"mycobacterium tuberculosis": ["1773"]}),
        ]
        for q, org, tax in cases:
            out = await think(q, [reply([]), reply([(org, "organism")])], {}, taxonomy=tax)
            show(f"{q} | retry names {org!r}", out, ["model_calls", "resolved", "organism_records", "clarification"])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))


async def note_presence():
    variants = {
        "illumina_gene_condition": [("SARS-CoV-2", "organism"), ("Illumina", "gene")],
        "illumina_organism": [("SARS-CoV-2", "organism"), ("Illumina", "organism")],
        "run12": [("SARS-CoV-2", "organism"), ("Illumina", "organism"), ("clinical respiratory samples", "disease")],
        "organism_only": [("SARS-CoV-2", "organism")],
    }
    for name, ents in variants.items():
        out = await think(T.QUESTION, [reply(ents)], {"Illumina": "condition"}, taxonomy={"illumina": []})
        show(name, out, ["organism_records", "note", "narrative"])


if __name__ == "__main__" and sys.argv[1] == "note_presence":
    asyncio.run(note_presence())


async def long_clauses():
    org = "Severe acute respiratory syndrome coronavirus 2"
    c1 = "Illumina NovaSeq 6000 paired-end whole genome sequencing platform runs"
    c2 = "clinical nasopharyngeal and oropharyngeal respiratory swab samples collected"
    c3 = "hospitalized adult intensive care unit patients from the 2021 winter wave"
    q = f"Find SRA runs of {org} from {c1} using {c2} of {c3}"
    out = await think(q, [reply([(org, "organism"), (c1, "gene"), (c2, "gene"), (c3, "gene")])],
                      {g._condition_span_text(c): "condition" for c in (c1, c2, c3)},
                      taxonomy={org.casefold(): ["2697049"]})
    show("long clauses", out, ["organism_records", "note", "narrative"])
    print("narrative len", len(out["narrative"] or ""), "has 'not applied':", "not applied" in (out["narrative"] or ""))


if __name__ == "__main__" and sys.argv[1] == "long_clauses":
    asyncio.run(long_clauses())


async def long_name():
    cases = [
        ("Severe acute respiratory syndrome coronavirus 2 SRA runs", "Severe acute respiratory syndrome coronavirus 2", "2697049"),
        ("Salmonella enterica subsp. enterica serovar Typhimurium genome assemblies", "Salmonella enterica subsp. enterica serovar Typhimurium", "90371"),
        ("Klebsiella pneumoniae SRA runs", "Klebsiella pneumoniae", "573"),
    ]
    for q, org, taxid in cases:
        rt = "assembly" if "assemblies" in q else "sra"
        out = await think(q, [reply([(org, "organism")], record_type=rt)], {}, taxonomy={org.casefold(): [taxid]})
        show(q, out, ["model_calls", "organism_records", "clarification", "searched"])


if __name__ == "__main__" and sys.argv[1] == "long_name":
    asyncio.run(long_name())
