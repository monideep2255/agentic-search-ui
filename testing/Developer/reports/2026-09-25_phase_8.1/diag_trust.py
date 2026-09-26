"""Diagnostic for T-8.1-05: why `trust_outcome` varies on byte-identical
evidence.

Runs the real loop in-process against MY worktree's src, with the real
model and graph. Monkeypatches `trust_for_claims` (called once per answer
in `core/graph.py`) to dump exactly which claims and findings it receives,
without editing core/graph.py (out of this builder's file fence).

Never prints an env value.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

MAIN_REPO = Path("<repo-root>")  # local-refs: allow
MY_WORKTREE = Path(__file__).resolve().parents[4]

for line in (MAIN_REPO / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"

sys.path.insert(0, str(MY_WORKTREE / "src"))

import system_03_search_agent.core.graph as _g
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run

_real_tfc = _g.trust_for_claims


def _tfc_spy(claims, all_findings, node_or_edge_type_by_citation_id=None):
    print(f"[TRUST_INPUT] n_claims={len(claims)} n_all_findings={len(all_findings)}")
    for c in claims:
        types = (node_or_edge_type_by_citation_id or {}).get(c.finding.citation_id, ("", False))
        print(
            "[CLAIM_IN]",
            json.dumps(
                {
                    "citation_id": c.finding.citation_id,
                    "field": c.finding.field,
                    "field_value": c.finding.field_value,
                    "curie": c.finding.curie,
                    "entity_type": c.finding.entity_type,
                    "node_or_edge_type": types,
                },
                default=str,
            ),
        )
    out = _real_tfc(claims, all_findings, node_or_edge_type_by_citation_id)
    for t in out:
        print(
            "[TRUST_OUT]",
            json.dumps(
                {
                    "citation_id": t.citation_id,
                    "risk_tier": t.risk_tier,
                    "grounded": t.grounded,
                    "triangulation": t.triangulation,
                    "outcome": t.outcome,
                }
            ),
        )
    return out


_g.trust_for_claims = _tfc_spy


async def main(question: str):
    query = Query(
        text=question,
        session_id="local-repro-trust",
        trace_id="trace-local-repro-trust",
        user_id=None,
        audience_depth="researcher",
    )
    context = RequestContext(surface="rest_sse", session_memory=None)
    trust_outcome = None
    async for e in run(query, context):
        if e.type == "done":
            p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
            trust_outcome = p.get("trust_outcome")
            print("[DONE]", json.dumps(p, default=str)[:800])
        elif e.type == "error":
            p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
            print("[ERROR]", json.dumps(p, default=str)[:800])
    print("[RESULT] trust_outcome=", trust_outcome)


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "What diseases are caused by variants in the HNF1A gene?"
    asyncio.run(main(q))
