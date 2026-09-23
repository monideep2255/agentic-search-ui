"""One live G-019 run against THIS working tree, so the answer can be read.

Not against deployed develop, which does not carry the fix. This drives
`core.run.run` in process: the real graph over the live AGE database, the
real models, the real E-utilities calls, the real grounding pass.

Prints what a person sees, assembled from the TYPED tokens rather than by
joining `text`, since a table row's visible content lives in `cells` and a
text join loses it (worker B1, 2026-09-22).

Usage, from the repository root:

    venv/bin/python testing/Developer/reports/2026-09-23_mesh_terms/run_g019_local.py
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path("src").resolve()))

for line in pathlib.Path(".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run

QUESTION = "What MeSH terms are assigned to PMID 11237011?"


def visible(payload: dict) -> str:
    parts = [str(payload.get("text") or "").rstrip()]
    cells = payload.get("cells") or []
    if cells:
        parts.append(" | ".join(str(c) for c in cells))
    return " ".join(p for p in parts if p)


async def main() -> None:
    query = Query(
        text=QUESTION,
        session_id="g019-local-" + str(int(time.time())),
        trace_id="g019-local-" + str(int(time.time())),
        user_id=None,
        audience_depth="researcher",
    )
    context = RequestContext(surface="rest_sse")
    started = time.time()
    events = [event async for event in run(query, context)]
    print(f"question : {QUESTION}")
    print(f"seconds  : {round(time.time() - started, 1)}")
    print("=" * 74)
    print("WHAT THE PERSON SEES")
    print("-" * 74)
    for event in events:
        if event.type == "token":
            line = visible(event.payload)
            if line:
                print(line)
    print("=" * 74)
    print("CITATIONS")
    print("-" * 74)
    for event in events:
        if event.type == "citation":
            payload = event.payload
            print(f"  [{payload.get('display_index')}] {payload.get('layer'):<14} "
                  f"{payload.get('source_id')}  {payload.get('source_url')}")
    terminal = [e for e in events if e.type in {"error", "done"}]
    print("=" * 74)
    for event in terminal:
        print(event.type, event.payload)


if __name__ == "__main__":
    asyncio.run(main())
