"""Fix-and-verify round, phase 8.1: one instrumented live run.

Modeled on `builder_a_live_run.py` in this folder: it loads environment
variables from the main repository's `.env` without printing any value, and
puts THIS WORKTREE's `src/` first on `sys.path` so the code under test is the
code that runs.

What it adds, all read-only observation of the run:

- Every call to `synthesis.findings.render_findings_block` is recorded: how
  many findings the writing model was handed, how many lines the block
  actually rendered, and the block's length. The same finding list is then
  re-rendered offline at 12,000 and 18,000 characters, so one live run shows
  what the old and the new block cap put in front of the model.
- The answer as the reader sees it, from the `token` events: each prose
  sentence (`kind == "claim"`), with the source and field of every citation
  its markers point at, so a sentence citing a MedGen clinical feature is
  visible as such.
- The code-built listing's headings and rows.

Usage: python3 fix_round_live_run.py "<question>" [--depth=plain_language]
Depth defaults to researcher, no session memory.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

MAIN_REPO = Path("/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui")  # local-refs: allow
WORKTREE_SRC = Path(__file__).resolve().parents[4] / "src"

for line in (MAIN_REPO / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"

sys.path.insert(0, str(WORKTREE_SRC))

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run
from system_03_search_agent.synthesis import findings as findings_module

assert str(WORKTREE_SRC) in findings_module.__file__, findings_module.__file__

_original_render = findings_module.render_findings_block
_render_calls: list[dict] = []


def _recording_render(synth_findings, max_chars=findings_module.MAX_FINDINGS_BLOCK_CHARS):
    block = _original_render(synth_findings, max_chars)
    at_12k = _original_render(synth_findings, 12_000)
    at_18k = _original_render(synth_findings, 18_000)
    _render_calls.append(
        {
            "handed": len(synth_findings),
            "rendered": block.count("\n") + 1 if block else 0,
            "block_chars": len(block),
            "rendered_at_12000": at_12k.count("\n") + 1 if at_12k else 0,
            "rendered_at_18000": at_18k.count("\n") + 1 if at_18k else 0,
            "clinical_feature_lines": sum(
                1 for line in block.splitlines() if " clinical_features: " in line
            ),
            "fields": [f.field for f in synth_findings],
            "value_lengths": [len(f.field_value) for f in synth_findings],
        }
    )
    return block


findings_module.render_findings_block = _recording_render

# The grounding pass's inputs and verdicts, so a model sentence the gate
# stripped is visible as such. Wrapped where `write_node` looks it up, in
# `core.graph`'s namespace; the gate itself is called unchanged.
from system_03_search_agent.core import graph as graph_module

_original_grounding = graph_module.run_grounding_pass
_grounding_calls: list[dict] = []


def _recording_grounding(narrative, synth_findings, *args, **kwargs):
    result = _original_grounding(narrative, synth_findings, *args, **kwargs)
    _grounding_calls.append(
        {
            "narrative": narrative,
            "claims": len(result.claims),
            "stripped": result.stripped_count,
            "feature_claims": sum(
                1 for claim in result.claims if claim.finding.field == "clinical_features"
            ),
        }
    )
    return result


graph_module.run_grounding_pass = _recording_grounding

args = [a for a in sys.argv[1:] if not a.startswith("--")]
text = args[0] if args else "What phenotypic features are associated with Marfan syndrome?"
depth = "researcher"
for arg in sys.argv[1:]:
    if arg.startswith("--depth="):
        depth = arg.split("=", 1)[1]
query = Query(
    text=text,
    session_id="fix-round-local",
    trace_id="trace-fix-round-local",
    user_id=None,
    audience_depth=depth,
)
context = RequestContext(surface="rest_sse", session_memory=None)


def _dump(payload):
    return payload if isinstance(payload, dict) else payload.model_dump()


async def main() -> None:
    citations: dict[str, dict] = {}
    tokens: list[dict] = []
    outcome = None
    cost = None
    errors: list[str] = []
    started = time.monotonic()
    async for event in run(query, context):
        payload = _dump(event.payload)
        if event.type == "citation":
            citations[payload["citation_id"]] = payload
        elif event.type == "token":
            tokens.append(payload)
        elif event.type == "cost":
            cost = payload.get("query_cost_usd")
        elif event.type == "error":
            errors.append(str(payload.get("message")))
        elif event.type == "done":
            outcome = payload.get("trust_outcome")
    elapsed = round(time.monotonic() - started, 1)

    print("[QUESTION]", text, "| depth:", depth)
    print("[OUTCOME]", outcome, "| cost:", cost, "| elapsed_s:", elapsed, "| errors:", errors)
    for index, call in enumerate(_render_calls, start=1):
        summary = {k: v for k, v in call.items() if k not in ("fields", "value_lengths")}
        print(f"[PROMPT_BLOCK {index}]", json.dumps(summary))
    if _render_calls:
        first = _render_calls[0]
        print("[PROMPT_FIELDS 1]", json.dumps(list(zip(first["fields"], first["value_lengths"]))))
    for index, call in enumerate(_grounding_calls, start=1):
        print(
            f"[GROUNDING {index}] claims={call['claims']} stripped={call['stripped']} "
            f"feature_claims={call['feature_claims']}"
        )
        print("   in:", repr(call["narrative"][:2500]))

    print("[PROSE] sentences the writing model wrote that survived the gate:")
    medgen_feature_sentences = 0
    features_named: list[str] = []
    for token in tokens:
        if token.get("kind") not in ("claim", None):
            continue
        cited = [citations.get(marker, {}) for marker in token.get("marker_ids") or []]
        cited_desc = [f"{c.get('source')}/{c.get('field')}" for c in cited]
        feature_hits = [c for c in cited if c.get("field") == "clinical_features"]
        if feature_hits:
            medgen_feature_sentences += 1
            for c in feature_hits:
                features_named.append(c.get("claim_text", "")[:120])
        print("   ", repr(token.get("text", "")[:400]), "->", cited_desc)
    print("[PROSE_FEATURE_SENTENCES]", medgen_feature_sentences)
    print("[PROSE_FEATURE_CLAIMS]", len(features_named), json.dumps(features_named))

    print("[LISTING] headings and rows:")
    for token in tokens:
        kind = token.get("kind")
        if kind == "heading":
            print("  #", token.get("text", "").strip())
        elif kind in ("list_item", "table_row", "table_header"):
            print("   -", kind, json.dumps(token.get("cells")))
        elif kind == "note":
            print("  note:", token.get("text", "").strip()[:300])
    print("[CITATIONS]", len(citations))


asyncio.run(main())
