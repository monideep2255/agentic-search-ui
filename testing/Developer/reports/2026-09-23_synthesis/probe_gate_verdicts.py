"""Items 12.9 and 12.10: why does each sentence the model wrote survive or not?

Runs one question through the real loop and, on the FIRST grounding call (the
model's own reply), records for every marked clause which check decided it:
the strict path, or each of `synthesis_is_supported`'s four checks in order.
This answers "is the model writing the quoted form, and if so which check
rejects it" by execution rather than by reading the reply by eye.

Run from the repository root, ONE question at a time (shared NCBI rate pools):
    python testing/Developer/reports/2026-09-23_synthesis/probe_gate_verdicts.py "GERD" plain_language
"""
import asyncio
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
for line in (ROOT / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
sys.path.insert(0, str(ROOT / "src"))

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as G
from system_03_search_agent.core.run import run
from system_03_search_agent.synthesis import grounding as g

OUT = pathlib.Path(__file__).parent / "probe_gate_verdicts"
OUT.mkdir(exist_ok=True)


def verdict(claim: str, quote: str | None, finding, licensed: str) -> str:
    supporting = (
        f"{finding.field_value} {finding.field} {finding.field.replace('_', ' ')} "
        f"{finding.curie} {finding.entity_type} {licensed}"
    )
    if not g.ground_claim(claim, finding.field_value):
        strict = "strict: not contained"
    elif not g.numbers_are_supported(claim, finding.field_value, licensed, f"{finding.curie} {finding.entity_type}"):
        strict = "strict: number"
    elif not g.claim_introduces_no_new_content(claim, supporting):
        extra = g.content_tokens(claim) - g.content_tokens(supporting)
        strict = f"strict: new words {sorted(extra)[:8]}"
    else:
        return "PASS strict"
    if quote is None:
        return strict + " | no quote"
    nq = g.normalize(quote)
    if len(nq) < g._MIN_QUOTE_CHARS or len(g.content_tokens(quote)) < 2:
        return strict + " | quote too short"
    if nq not in g.normalize(finding.field_value):
        return strict + " | quote NOT in record"
    if not g.numbers_are_supported(claim, quote, licensed, f"{finding.curie} {finding.entity_type}"):
        return strict + " | number not in quote"
    if g._negates(claim) != g._negates(quote):
        return strict + " | polarity"
    support = g.content_tokens(
        f"{quote} {finding.field} {finding.field.replace('_', ' ')} {finding.curie} {finding.entity_type} {licensed}"
    )
    allowed = g._stemmed(support) | g._stemmed(set(g._SYNTHESIS_VOCABULARY))
    extra = g._stemmed(g.content_tokens(claim)) - allowed
    if extra:
        return strict + f" | words beyond quote {sorted(extra)[:8]}"
    return "PASS synthesis"


async def trace(question: str, depth: str) -> dict:
    record: dict = {"question": question, "depth": depth}
    real_ground = G.run_grounding_pass
    calls = {"n": 0}

    def wrapped(narrative, findings, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            quotes = kwargs.get("evidence_quotes") or ()
            by_ref = {f.ref_index: f for f in findings}
            licensed = g._licensed_question_content(kwargs.get("question", ""))
            rows = []
            for sentence in g._split_sentences(narrative):
                for text, marker, key in g._segments(sentence):
                    if marker is None:
                        continue
                    finding = by_ref.get(marker)
                    claim = g._clean_claim(text)
                    quote = quotes[key] if key is not None and key < len(quotes) else None
                    rows.append({
                        "marker": marker,
                        "field": finding.field if finding else None,
                        "claim": claim,
                        "quote": quote,
                        "verdict": verdict(claim, quote, finding, licensed) if finding else "unknown marker",
                    })
            # Every finding, so the verdicts can be re-derived offline against
            # the same records without spending another live run.
            record["findings"] = [
                {"ref_index": f.ref_index, "citation_id": f.citation_id, "layer": f.layer, "tool": f.tool,
                 "field": f.field, "field_value": f.field_value, "source_url": f.source_url,
                 "entity_type": f.entity_type, "curie": f.curie}
                for f in findings
            ]
            record["question_text"] = kwargs.get("question", "")
            record["reply_keyed"] = narrative
            record["quotes"] = list(quotes)
            record["clauses"] = rows
        return real_ground(narrative, findings, **kwargs)

    G.run_grounding_pass = wrapped
    try:
        query = Query(text=question, session_id=f"probe-{depth}", trace_id=f"probe1210-{os.urandom(4).hex()}", user_id=None, audience_depth=depth)
        async for _event in run(query, RequestContext(surface="rest_sse")):
            pass
    finally:
        G.run_grounding_pass = real_ground
    return record


def main() -> None:
    question, depth = sys.argv[1], sys.argv[2]
    record = asyncio.run(trace(question, depth))
    slug = "".join(c if c.isalnum() else "_" for c in question.lower())[:40]
    (OUT / f"{slug}_{depth}.json").write_text(json.dumps(record, indent=2, default=str))
    for row in record.get("clauses", []):
        print(f"[{row['marker']}] {row['verdict']}\n    claim: {row['claim'][:160]}\n    quote: {(row['quote'] or '')[:160]}")
    print(f"quotes written by the model: {len(record.get('quotes', []))}")


main()
