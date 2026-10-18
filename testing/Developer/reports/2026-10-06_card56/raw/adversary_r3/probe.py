"""Adversary round 3 probe: run think_node on one tree with a faked model
reply and recorder fakes, print one JSON line per scenario.

Usage: python probe.py <tree-root> <scenarios.json>
Every MedGen lookup is recorded and answered with one fake record per term,
so the output shows exactly which candidates reached MedGen.
"""

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(sys.argv[1]).resolve()

# No network at all: every socket connect fails, so no model or NCBI call
# can leave this machine (an earlier run reached live classifier calls).
import socket


def _no_net(*args, **kwargs):
    raise OSError("network disabled by adversary probe")


socket.socket.connect = _no_net
socket.socket.connect_ex = _no_net
socket.create_connection = _no_net
socket.getaddrinfo = _no_net
sys.path.insert(0, str(ROOT / "src"))

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as g
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools import ncbi_eutils_actions

TAXA = {"sars-cov-2": "2697049", "human": "9606", "hiv-1": "11676", "homo sapiens": "9606"}
GENES = {"BRCA1": "NCBIGene:672", "TP53": "NCBIGene:7157", "KRAS": "NCBIGene:3845"}


async def run(question, entities, record_type, reply_override=None):
    looked = []

    async def disease(mention):
        looked.append(mention)
        return [f"MedGen:FAKE_{mention.upper()}"], 1

    async def gene(symbol, *, taxon="human"):
        return GENES.get(symbol.upper())

    async def search(params):
        ids = []
        if params.db == "taxonomy":
            key = params.term.split("[")[0].strip().casefold()
            ids = [TAXA[key]] if key in TAXA else []
        return SimpleNamespace(
            status="ok" if ids else "empty",
            records=[SimpleNamespace(fields={"idlist": ids})] if ids else [],
        )

    async def summary(params):
        return SimpleNamespace(status="ok", records=[])

    cls = g._ThinkClassification(
        query_class="exploratory",
        narrative="x",
        entities=[g._ThinkExtractedEntity(text=t, entity_type=k) for t, k in entities],
        record_type=record_type,
    )
    replies = list(reply_override) if reply_override else None
    sent = []

    async def dispatch(*args, **kwargs):
        sent.append(args)
        if replies:
            return SimpleNamespace(content=replies.pop(0))
        return SimpleNamespace(content=cls.model_dump_json())

    g.resolve_disease_mention_to_curies = disease
    g.resolve_symbol_to_curie = gene
    g._dispatch_tier_call = dispatch
    ncbi_eutils_actions.search = search
    ncbi_eutils_actions.summary = summary
    g._ORGANISM_KNOWN_CACHE.clear()
    state = {
        "query": Query(text=question, session_id="s-adv", trace_id="t-adv", user_id=None),
        "context": RequestContext(surface="rest_sse", session_memory=None),
        "harness": harness_module.Harness(trace_id="t-adv"),
        "seq": 0,
        "findings": [],
        "findings_count": 0,
    }
    result = await g.think_node(state)
    orec = result.get("organism_records")
    return {
        "q": question,
        "ents": entities,
        "rt": record_type,
        "medgen_lookups": looked,
        "resolved": [(e.text, e.curie) for e in result.get("resolved_entities") or []],
        "clarification": (result.get("clarification_needed") or "")[:60] or None,
        "unresolved": result.get("unresolved_entity_symbols"),
        "organism_records": (orec.organism.curie, orec.record_type) if orec else None,
        "step_error": bool(result.get("step_error")),
    }


async def main():
    import os

    os.environ["GUARD_MODEL"] = "test-provider/guard-model"
    os.environ["PLAN_MODEL"] = "test-provider/plan-model"
    os.environ["SYNTH_MODEL"] = "test-provider/synth-model"
    os.environ["CLASSIFIER_PROVIDER"] = "guard"
    scenarios = json.loads(Path(sys.argv[2]).read_text())
    for s in scenarios:
        out = await run(s["q"], [tuple(e) for e in s.get("ents", [])], s["rt"], s.get("replies"))
        print(json.dumps(out, ensure_ascii=True), flush=True)


asyncio.run(main())
