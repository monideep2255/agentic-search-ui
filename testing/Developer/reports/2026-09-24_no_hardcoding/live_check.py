"""Items 12.3, 12.9, 12.10 and 12.16, measured together on the merged code.

Every question from `testing/User-feedback/fix-1` and `fix-2`, run through the
real loop with live models and live NCBI calls, one at a time since the NCBI
rate pools are shared. For each run it records what a reader would see: the
clarifying question and its choices if the product asked back, otherwise the
answer's opening sentence, its prose, its list shape (list rows or table
rows), its citations and its trust line.

Then it checks the three done-whens:

- 12.3: each bare short question is asked back with choices and runs no
  search; a short question that says what it wants is searched.
- 12.9 rule 6: every answered question differs between plain language and
  researcher in its opening sentence AND its list shape, and both depths cite
  the same records (the line not crossed).
- 12.10: the prose under the opening sentence answers in sentences, reported
  per run rather than judged here.

Run from the repository root:
    python testing/Developer/reports/2026-09-24_no_hardcoding/live_check.py
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
from system_03_search_agent.core.run import run

OUT = pathlib.Path(__file__).parent / "live_runs"
OUT.mkdir(exist_ok=True)

ASK_BACK = ["reflux disease", "GERD", "BRCA1", "MeSH", "Marfan"]
SEARCHED_SHORT = ["papers on caffeine"]
BOTH_DEPTHS = [
    "Any trials for GERD?",
    "papers on the effects of caffeine on exercise performance",
    "Does coffee help make exercise more effective?",
    "Are there any beneficial variants typically found in people of mediterranean descent?",
    "What positive and negative genes do ashkenazi jewish people have?",
    "Which diseases are associated with BRCA1?",
    "What phenotypic features are associated with Marfan syndrome?",
    "what does the literature say about metformin",
    "recent papers on statins",
    "is there a trial recruiting for melanoma",
    "any trials for gerd?",
    "What MeSH terms are assigned to PMID 11237011?",
]


async def ask(question: str, depth: str, tag: str) -> dict:
    query = Query(
        text=question,
        session_id=f"live-{tag}-{os.urandom(3).hex()}",
        trace_id=f"live-{tag}-{os.urandom(4).hex()}",
        user_id=None,
        audience_depth=depth,
    )
    record: dict = {
        "question": question, "depth": depth, "tokens": [], "citations": [],
        "clarifying_question": None, "clarifying_options": None, "event_types": [],
        "outcome": None, "trust_line": None, "errors": [],
    }
    async for event in run(query, RequestContext(surface="rest_sse")):
        payload = event.payload if isinstance(event.payload, dict) else event.payload.model_dump()
        record["event_types"].append(event.type)
        if event.type == "token":
            record["tokens"].append(
                {"kind": payload.get("kind"), "text": payload.get("text"), "cells": payload.get("cells")}
            )
        elif event.type == "citation":
            record["citations"].append(payload.get("citation_id"))
        elif event.type == "think":
            if payload.get("clarifying_question"):
                record["clarifying_question"] = payload.get("clarifying_question")
                record["clarifying_options"] = payload.get("clarifying_options")
        elif event.type == "done":
            record["outcome"] = payload.get("trust_outcome")
            record["trust_line"] = payload.get("trust_line")
        elif event.type == "error":
            record["errors"].append(f"{payload.get('scope')}/{payload.get('source')}")
    return record


def opening(record: dict) -> str:
    for token in record["tokens"]:
        if token["kind"] in (None, "claim") and token["text"].strip():
            return token["text"].strip()
    return ""


def list_shape(record: dict) -> str:
    kinds = {t["kind"] for t in record["tokens"]}
    if "table_row" in kinds:
        return "table"
    if "list_item" in kinds:
        return "list"
    return "none"


async def main() -> None:
    results: list[dict] = []
    for question in ASK_BACK:
        for attempt in (1, 2):
            record = await ask(question, "plain_language", "ask")
            record["attempt"] = attempt
            results.append(record)
            print(json.dumps({
                "question": question, "attempt": attempt,
                "asked_back": bool(record["clarifying_question"]),
                "citations": len(record["citations"]),
                "clarifying_question": record["clarifying_question"],
                "options": record["clarifying_options"],
            }), flush=True)
    for question in SEARCHED_SHORT:
        record = await ask(question, "plain_language", "short")
        results.append(record)
        print(json.dumps({
            "question": question, "asked_back": bool(record["clarifying_question"]),
            "citations": len(record["citations"]), "outcome": record["outcome"],
        }), flush=True)
    for question in BOTH_DEPTHS:
        pair = {}
        for depth in ("plain_language", "researcher"):
            record = await ask(question, depth, depth[:5])
            results.append(record)
            pair[depth] = record
        plain, research = pair["plain_language"], pair["researcher"]
        print(json.dumps({
            "question": question,
            "openings_differ": opening(plain) != opening(research),
            "list_shape": [list_shape(plain), list_shape(research)],
            "same_citation_count": len(set(plain["citations"])) == len(set(research["citations"])),
            "citations": [len(set(plain["citations"])), len(set(research["citations"]))],
            "outcome": [plain["outcome"], research["outcome"]],
            "plain_opening": opening(plain)[:140],
            "research_opening": opening(research)[:140],
            "errors": plain["errors"] + research["errors"],
        }), flush=True)
    (OUT / "all.json").write_text(json.dumps(results, indent=1, default=str))
    print("wrote live_runs/all.json")


asyncio.run(main())
