"""Card 23 live check: one question through `core.run.run` with the real
models, tools and graph, recording every token (kind, text, cells, marker
ids), every citation (id, number, source, URL) and the done event.

The approach of `testing/Developer/reports/2026-10-06_card101/raw/
check_every/trace_run.py`, without its sentence-check spies: card 23 only
needs to see the answer's structure and the records behind each row.

Secrets are read from ENV_FILE into this process only and are never printed
or written. Raw answers carry record text, so they go to OUT_DIR, a folder
outside the repository.

Usage: python3 live_run.py <label> <plain_language|researcher>
Environment: REPO_ROOT (the checkout whose `src` runs), ENV_FILE (the main
checkout's .env), OUT_DIR, USER_DB_URL (the throwaway database).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(os.environ["REPO_ROOT"])
OUT_DIR = Path(os.environ["OUT_DIR"])
USER_DB_URL = os.environ["USER_DB_URL"]
for line in Path(os.environ["ENV_FILE"]).read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
# The throwaway database, never the one the .env names.
os.environ["USER_DB_URL"] = USER_DB_URL
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
os.environ["CLASSIFIER_PROVIDER"] = "jev"
sys.path.insert(0, str(ROOT / "src"))

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run

QUESTION = "What diseases are caused by variants in the HNF1A gene?"
LABEL, DEPTH = sys.argv[1], sys.argv[2]


async def main() -> None:
    out = OUT_DIR / f"{LABEL}.jsonl"
    query = Query(
        text=QUESTION,
        session_id=f"card23-{LABEL}",
        trace_id=f"card23-local-{LABEL}",
        user_id=None,
        audience_depth=DEPTH,  # type: ignore[arg-type]
    )
    context = RequestContext(surface="rest_sse", session_memory=None)
    started = time.time()
    with out.open("w") as handle:
        async for event in run(query, context):
            payload = event.payload if isinstance(event.payload, dict) else event.payload.model_dump()
            if event.type == "token":
                record = {
                    "kind": payload.get("kind"),
                    "text": payload.get("text"),
                    "cells": payload.get("cells"),
                    "marker_ids": payload.get("marker_ids"),
                }
            elif event.type == "citation":
                record = {
                    key: payload.get(key)
                    for key in ("citation_id", "display_index", "source", "source_id", "source_url", "layer")
                }
            elif event.type in ("done", "error"):
                record = {
                    key: payload.get(key)
                    for key in ("trust_outcome", "trust_line", "elapsed_ms", "total_cost_usd", "message")
                }
            else:
                continue
            handle.write(json.dumps({"type": event.type, **record}, default=str) + "\n")
        handle.write(json.dumps({"type": "elapsed_s", "value": round(time.time() - started, 1)}) + "\n")


asyncio.run(main())
