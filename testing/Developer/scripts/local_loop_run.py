"""Run ONE memory-bound follow-up locally with the real model and graph, and
print every event in full, so the Cypher, the rows and the refusal reason are
visible. Memory is injected the way the premise gate injects it."""
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

root = Path("/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui")
for line in (root / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
sys.path.insert(0, str(root / "src"))

import system_03_search_agent.tools.cypher_query as _cq
from system_03_search_agent.contracts.query import (
    CompressedFinding,
    Query,
    RequestContext,
    ResolvedEntity,
    SessionMemorySummary,
)
from system_03_search_agent.core.run import run

_real = _cq.execute_cypher
def _spy(cypher, *a, **kw):
    print("[CYPHER]", " ".join(cypher.split()))
    rows, total = _real(cypher, *a, **kw)
    print(f"[ROWS] {len(rows)} rows, total={total}")
    for r in rows[:2]:
        print("[ROW]", json.dumps(r, default=str)[:400])
    print("[ROW_KEYS]", sorted(set().union(*[set(r) for r in rows])) if rows else [])
    print("[WITH_SOURCE_URL]", sum(1 for r in rows if r.get("source_url")))
    return rows, total
_cq.execute_cypher = _spy
import system_03_search_agent.core.graph as _g

_real_bsf = _g.build_synth_findings
def _bsf_spy(findings, pick, *a, **kw):
    for f in findings:
        sf = f.structured_fields or {}
        rows = sf.get("rows", [])
        print(f"[FINDING] {f.tool} status={sf.get('status')} rows={len(rows)} with_source_url={sum(1 for r in rows if r.get('source_url'))}")
        for r in rows[:2]:
            print("[SHAPED]", json.dumps(r, default=str)[:600])
    out = _real_bsf(findings, pick, *a, **kw)
    print(f"[SYNTH_FINDINGS] {len(out[0])} capped={out[1]}")
    return out
_g.build_synth_findings = _bsf_spy
_real_gp = _g.run_grounding_pass
def _gp_spy(text, findings, *a, **kw):
    print("[SYNTH_TEXT]", json.dumps(text)[:1200])
    res = _real_gp(text, findings, *a, **kw)
    try:
        print(f"[GROUNDING] claims={len(res.claims)} outcome={getattr(res,'outcome',None)} dropped={getattr(res,'dropped',None) and len(res.dropped)} attrs={[k for k in vars(res)] if hasattr(res,'__dict__') else type(res)}")
        for d in (getattr(res, "dropped", None) or [])[:5]:
            print("[DROPPED]", json.dumps(d if isinstance(d, str) else getattr(d, "__dict__", str(d)), default=str)[:300])
    except Exception as ex:  # noqa: BLE001 - a diagnostic print of an unexpected result shape, never a control path
        print("[GROUNDING?]", type(res), ex)
    return res
_g.run_grounding_pass = _gp_spy




# UI fix set 7: `--deeper` sends the go-deeper query with the records earlier
# runs showed injected into memory, the way `run.py` would have recorded them.
# `--reset` clears that record. Every run appends the citations it showed.
REPORTED = Path(__file__).with_name("reported_ids.json")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
deeper = "--deeper" in sys.argv
if "--reset" in sys.argv and REPORTED.exists():
    REPORTED.unlink()
reported_ids = json.loads(REPORTED.read_text()) if REPORTED.exists() else []
default_text = (
    "Which other sequence variant records are linked to BRCA1?" if deeper else "What variants cause it?"
)
text = args[0] if args else default_text
memory = SessionMemorySummary(
    session_id="local-repro", last_updated=datetime.now(UTC),
    resolved_entities=[ResolvedEntity(mention="BRCA1", curie="NCBIGene:672", entity_type="Gene")],
    open_threads=["Which diseases are associated with BRCA1?"],
    compressed_findings=[
        CompressedFinding(claim_summary=c, trace_id="trace-earlier", citation_ids=[f"cq-earlier-{i}"])
        for i, c in enumerate([
            "BRCA1 (gene symbol BRCA1) is associated with familial cancer of breast",
            "BRCA1 is associated with breast-ovarian cancer, familial, susceptibility to, 1",
            "BRCA1 is associated with pancreatic cancer, susceptibility to, 4",
            "BRCA1 is associated with Fanconi anemia, complementation group S",
            "BRCA1 DNA repair associated, NCBIGene:672, confirmed by a live NCBI record",
        ])
    ] if "--plain" not in sys.argv else [],
    reported_record_ids=reported_ids if deeper else [],
)
print(f"[MEMORY] reported_record_ids injected={len(memory.reported_record_ids)} text={text!r}")
query = Query(text=text, session_id="local-repro", trace_id="trace-local-repro", user_id=None, audience_depth="researcher")
# UI fix set 8: `--no-memory` runs the question as a first turn with no session
# memory at all, so a gene that fails to resolve cannot silently bind to the
# remembered BRCA1 antecedent and mask the failure. `--summary` appends one
# JSON line, `[SUMMARY] {...}`, with the tools, layers and statuses that ran,
# the elapsed seconds, the resolved entities and the citation source set with
# each source's layer, so a runner can tabulate many runs.
no_memory = "--no-memory" in sys.argv
context = RequestContext(surface="rest_sse", session_memory=None if no_memory else memory)

async def main():
    import time as _time
    shown = []
    summary = {"question": text, "tools": [], "citations": [], "resolved_entities": [], "trust_outcome": None}
    started = _time.monotonic()
    async for e in run(query, context):
        p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
        if e.type in ("guard", "think", "tool_result", "error", "token", "plan", "done"):
            print(f"[{e.type}]", json.dumps(p, default=str)[:1500])
        elif e.type == "citation":
            shown.append(p["source_url"])
            summary["citations"].append({"source_url": p["source_url"], "layer": p["layer"], "source": p["source"], "source_id": p["source_id"], "license": p["license"], "evidence_kind": p["evidence_kind"]})
            print(f"[citation] {p['display_index']} {p['source_url']} :: {p['claim_text'][:120]}")
        else:
            print(f"[{e.type}]")
        if e.type == "think":
            summary["resolved_entities"] = [r["curie"] for r in p.get("resolved_entities", [])]
        if e.type == "tool_result":
            summary["tools"].append({"tool": p["tool"], "layer": p["layer"], "status": p["status"], "count": p["result_count"], "persona": p.get("persona")})
        if e.type == "done":
            summary["trust_outcome"] = p["trust_outcome"]
        if e.type == "trust_signal" and p.get("scope") == "answer":
            summary["answer_trust"] = {k: p.get(k) for k in ("outcome", "risk_tier", "grounded", "message", "summary")}
    summary["elapsed_s"] = round(_time.monotonic() - started, 1)
    if "--summary" in sys.argv:
        print("[SUMMARY]", json.dumps(summary, default=str))
    new_ids = [u for u in shown if u not in reported_ids]
    print(f"[SHOWN] {len(shown)} citations, {len(new_ids)} not previously reported, "
          f"{len(shown) - len(new_ids)} previously reported")
    merged = reported_ids + [u for u in dict.fromkeys(new_ids)]
    REPORTED.write_text(json.dumps(merged[-100:]))
asyncio.run(main())
