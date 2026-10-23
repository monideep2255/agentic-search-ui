"""Card 130 measurement: one question through `run_streaming`, develop's settings.

Usage: ASU_ENV_FILE=<path to the .env> python measure.py <batch> <key> <plain_language|researcher> <repeat>

Settings pinned to develop's API as recorded in `docs/build/Handoff_history.md`:
CLASSIFIER_PROVIDER=jev, guard and plan deepseek/deepseek-v4-flash, synth
z-ai/glm-5.2, per-query cap 0.25 USD. The web client's settings:
`reads_placement=True`. Secrets are read into this process only and never
printed or written.

Spies record, per run, whether the restatement drop ran and how many it
removed, which no-summary note builder fired, and the findings the writer
was given (field and value, cut to 160 characters). Output:
`<batch>/<key>_<depth>_<repeat>.jsonl` beside this script.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
for line in Path(os.environ["ASU_ENV_FILE"]).read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ.update(
    {
        "LANGCHAIN_TRACING_V2": "false",
        "TOOL_AUDIT_LOG_ENABLED": "false",
        "CLASSIFIER_PROVIDER": "jev",
        "GUARD_MODEL": "deepseek/deepseek-v4-flash",
        "PLAN_MODEL": "deepseek/deepseek-v4-flash",
        "SYNTH_MODEL": "z-ai/glm-5.2",
        "PER_QUERY_COST_CAP_USD": "0.25",
    }
)
sys.path.insert(0, str(ROOT / "src"))

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as g
from system_03_search_agent.core.run import run_streaming

QUESTIONS = {
    "q116_orthologs": "What are the known orthologs of TP53 in other species?",
    "q022_cftr_variants": "Which clinically significant variants have been reported in CFTR?",
    "q078_mody_genes": "What genes are associated with MODY?",
    "q104_pmid_data": "What sequence data is linked to PMID 11237011?",
    "rs334_rs6025": "What are rs334 and rs6025?",
    "q037_colistin": "Which E. coli isolates in Pathogen Detection carry colistin resistance genes?",
}

BATCH, KEY, DEPTH, REPEAT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
OUT_DIR = HERE / BATCH
OUT_DIR.mkdir(exist_ok=True)
OUT = open(OUT_DIR / f"{KEY}_{DEPTH}_{REPEAT}.jsonl", "w")  # noqa: SIM115


def log(tag: str, obj: object) -> None:
    OUT.write(json.dumps({"tag": tag, "data": obj}, default=str) + "\n")
    OUT.flush()


_real_drop = g.drop_record_restatements


def _spy_drop(grounding, findings):
    after, dropped = _real_drop(grounding, findings)
    log("RESTATEMENT_DROP", {"dropped": dropped, "claims_after": len(after.claims)})
    return after, dropped


g.drop_record_restatements = _spy_drop

for _name in ("_build_structured_fallback_note", "_build_writer_failed_note", "_build_cap_list_note"):
    _orig = getattr(g, _name)

    def _make(orig, name):
        def _spy():
            log("FALLBACK_NOTE", name)
            return orig()

        return _spy

    setattr(g, _name, _make(_orig, _name))

_real_messages = g.build_synth_messages
_messages_logged = False


def _spy_messages(question, synth_findings, *args, **kwargs):
    global _messages_logged
    if not _messages_logged:
        _messages_logged = True
        log(
            "WRITER_FINDINGS",
            [[f.ref_index, f.entity_type, f.field, f.field_value[:160]] for f in synth_findings],
        )
    return _real_messages(question, synth_findings, *args, **kwargs)


g.build_synth_messages = _spy_messages

_real_will_cite = g._code_built_lines_will_cite


def _spy_will_cite(omitted, *args, **kwargs):
    covered = _real_will_cite(omitted, *args, **kwargs)
    log("REPAIR_CHECK", {"omitted": len(omitted), "code_lines_cite_all": covered})
    return covered


g._code_built_lines_will_cite = _spy_will_cite

_real_uncitable = g._listing_uncitable


def _spy_uncitable(prompt_findings, listing_grounding):
    found = _real_uncitable(prompt_findings, listing_grounding)
    log("LISTING_UNCITABLE", {"count": len(found), "fields": sorted({f.field for f in found})})
    return found


g._listing_uncitable = _spy_uncitable

_real_start_second = g._start_second_draft


def _spy_start_second(harness, coro):
    log("SECOND_DRAFT_STARTED", True)
    return _real_start_second(harness, coro)


g._start_second_draft = _spy_start_second


async def main() -> None:
    query = Query(
        text=QUESTIONS[KEY],
        session_id=f"c130-{BATCH}-{KEY}-{DEPTH}-{REPEAT}",
        trace_id=f"c130-{BATCH}-{KEY}-{DEPTH}-{REPEAT}",
        user_id=None,
        audience_depth=DEPTH,
    )
    context = RequestContext(surface="web_ui", session_memory=None, reads_placement=True)
    started = time.monotonic()
    async for e in run_streaming(query, context):
        p = e.payload if isinstance(e.payload, dict) else e.payload.model_dump()
        elapsed = round(time.monotonic() - started, 2)
        if e.type == "token":
            log("TOKEN", {**{k: p.get(k) for k in ("kind", "text", "placement", "cells")}, "t": elapsed})
        elif e.type == "trust_signal":
            log("TRUST", {k: p.get(k) for k in ("outcome", "risk_tier", "scope", "citation_id")})
        elif e.type == "citation":
            log("CITATION", {k: p.get(k) for k in ("display_index", "source_url", "field", "claim_text")})
        elif e.type in ("done", "error"):
            log(
                e.type.upper(),
                {
                    **{k: p.get(k) for k in ("trust_outcome", "elapsed_ms", "total_cost_usd", "message", "trust_line")},
                    "t": elapsed,
                },
            )


asyncio.run(main())
OUT.close()
