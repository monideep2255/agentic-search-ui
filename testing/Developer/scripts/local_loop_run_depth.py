"""Run one question at one answer mode locally with the real models and graph,
and print the set 9 measurements for that run as one JSON line.

UI fix set 9 (2026-09-13). A sibling of `local_loop_run.py`, parametrised by
`--depth`, with no session memory, so the question is answered cold. Usage:

    python testing/Developer/scripts/local_loop_run_depth.py \
        --depth plain_language "Which diseases are associated with BRCA1?"

Add `--print` to also print the answer as a reader would see it.

Measured per run, from the run's own event stream only:
- words: prose and listing words, markers removed, notes and headings excluded
- paragraphs: prose paragraphs (claim tokens grouped by paragraph breaks)
- headings, list_items, table_rows: counts by token kind
- unmarked_claims: claim-like tokens that carry no marker (must be 0)
- trust_line: the answer-scope signal's `summary`
- sources: the sorted cited source ids
- notes: every note token, in order
"""
import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
for line in (root / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
sys.path.insert(0, str(root / "src"))

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run

_MARKER = re.compile(r"\s*\[\d{1,3}\]")
_CLAIM_KINDS = {"claim", "list_item", "table_row", None}


async def measure(question: str, depth: str, show: bool) -> dict:
    query = Query(
        text=question,
        session_id=f"set9-{depth}",
        trace_id=f"set9-{os.urandom(4).hex()}",
        user_id=None,
        audience_depth=depth,
    )
    tokens: list[dict] = []
    sources: list[str] = []
    trust_line = None
    outcome = None
    errors: list[str] = []
    async for event in run(query, RequestContext(surface="rest_sse")):
        payload = event.payload if isinstance(event.payload, dict) else event.payload.model_dump()
        if event.type == "token":
            tokens.append(payload)
        elif event.type == "citation":
            sources.append(payload["source_id"])
        elif event.type == "done":
            outcome = payload.get("trust_outcome")
            trust_line = payload.get("trust_line")
        elif event.type == "error":
            errors.append(f"{payload.get('scope')}/{payload.get('source')}: {payload.get('message', '')[:120]}")

    words = 0
    paragraphs = 0
    in_paragraph = False
    unmarked = 0
    lines: list[str] = []
    for token in tokens:
        kind = token.get("kind")
        text = token["text"]
        if kind == "paragraph_break" or kind == "heading" or kind == "note":
            in_paragraph = False
            if show and kind == "heading":
                lines.append(f"\n## {text.strip()}\n")
            elif show and kind == "note":
                lines.append(f"\n({text.strip()})")
            elif show:
                lines.append("\n")
            continue
        if kind not in _CLAIM_KINDS:
            continue
        if not token["marker_ids"]:
            unmarked += 1
        shown = " / ".join(token.get("cells") or []) if kind in ("list_item", "table_row") else _MARKER.sub("", text)
        words += len(shown.split())
        if kind in ("claim", None) and not in_paragraph:
            paragraphs += 1
            in_paragraph = True
        if kind in ("list_item", "table_row"):
            in_paragraph = False
        if show:
            lines.append(f"\n- {shown}" if kind in ("list_item", "table_row") else text)
    result = {
        "depth": depth,
        "question": question,
        "outcome": outcome,
        "words": words,
        "paragraphs": paragraphs,
        "headings": sum(1 for t in tokens if t.get("kind") == "heading"),
        "list_items": sum(1 for t in tokens if t.get("kind") == "list_item"),
        "table_rows": sum(1 for t in tokens if t.get("kind") == "table_row"),
        "unmarked_claims": unmarked,
        "trust_line": trust_line,
        "sources": sorted(set(sources)),
        "notes": [t["text"] for t in tokens if t.get("kind") == "note"],
        "errors": errors,
    }
    if show:
        print("".join(lines))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument(
        "--depth",
        required=True,
        choices=["plain_language", "researcher", "clinical_brief", "deep_technical"],
    )
    parser.add_argument("--print", dest="show", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(measure(args.question, args.depth, args.show))))


if __name__ == "__main__":
    main()
