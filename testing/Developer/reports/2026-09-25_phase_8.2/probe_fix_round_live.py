"""The fix round's live probes: real Jev, real guard model, no tools, no answer.

Two modes, each one line of output per question:

    guardrail <text> [--memory]   the real `guardrail_node`; with --memory the
                                  session remembers a BRCA1 question first
    recent <text>                 the real `decide()` for `think.recent_years`,
                                  then whether Think would ask "How far back?"
    literature <text>             the real `decide()` for `plan.literature`

Run from the repository root with `PYTHONPATH=src`. The environment file is
read from `ENV_FILE` (default `.env`), and only the named keys below are
loaded; no value is ever printed. `CLASSIFIER_PROVIDER=jev` is set in this
process only. The two daily caps are stubbed so no database is needed; the
per-query cap stays on at $0.05.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from datetime import UTC, datetime

_KEYS = {"OPENROUTER_API_KEY", "GUARD_MODEL", "PLAN_MODEL", "SYNTH_MODEL", "JEV_MODEL"}


def _load_env() -> None:
    path = os.environ.get("ENV_FILE", ".env")
    loaded = 0
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if "=" not in line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            if key in _KEYS:
                os.environ[key] = value.strip().strip('"').strip("'")
                loaded += 1
    os.environ["CLASSIFIER_PROVIDER"] = "jev"
    os.environ["PER_QUERY_COST_CAP_USD"] = "0.05"
    os.environ["PER_USER_DAILY_QUERY_CAP"] = "100"
    os.environ["SYSTEM_DAILY_CAP_USD"] = "1000000"
    os.environ["USER_DB_URL"] = "postgresql://localhost:5432/none"
    print(f"loaded {loaded} named keys (values not shown)")


_load_env()

from system_03_search_agent.contracts.query import (
    CompressedFinding,
    Query,
    RequestContext,
    ResolvedEntity,
    SessionMemorySummary,
)
from system_03_search_agent.core import graph as g
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as hm
from system_03_search_agent.harness.decide import decide

cost_control.check_user_daily_query_cap = lambda *a, **k: None  # type: ignore[assignment]
cost_control.check_system_daily_cost_cap = lambda *a, **k: None  # type: ignore[assignment]

_MEMORY = SessionMemorySummary(
    session_id="fix-round-probe",
    last_updated=datetime.now(UTC),
    resolved_entities=[ResolvedEntity(mention="BRCA1", curie="NCBIGene:672", entity_type="Gene")],
    compressed_findings=[
        CompressedFinding(
            claim_summary="BRCA1 is associated with hereditary breast and ovarian cancer",
            trace_id="t-earlier",
            citation_ids=["c1"],
        )
    ],
    open_threads=["Which diseases are associated with BRCA1?"],
)


def _record_line(record) -> str:  # type: ignore[no-untyped-def]
    if record is None:
        return "not asked"
    return (
        f"jev={record.jev_choice}({record.jev_confidence}) guard={record.guard_choice} "
        f"by={record.decided_by} note={record.fallback_reason}"
    )


async def _guardrail(text: str, with_memory: bool) -> None:
    trace_id = f"fix-{uuid.uuid4().hex[:10]}"
    harness = hm.Harness(trace_id)
    state = {
        "query": Query(text=text, session_id="fix-round-probe", trace_id=trace_id),
        "context": RequestContext(
            surface="rest_sse", session_memory=_MEMORY if with_memory else None
        ),
        "harness": harness,
        "seq": 0,
        "start_monotonic": time.monotonic(),
    }
    started = time.monotonic()
    result = await g.guardrail_node(state)  # type: ignore[arg-type]
    elapsed = time.monotonic() - started
    guard = next((e.payload for e in result.get("events", []) if e.type == "guard"), None)
    entry = g._RUN_DECISIONS.get(harness)
    record = next(
        (d for d in (entry.records if entry else []) if d.name == "guardrail.relevancy"), None
    )
    verdict = f"passed={guard['passed']} {guard['category']}" if guard else "no guard event"
    print(
        f"{verdict} | relevancy {_record_line(record)} | "
        f"${harness.get_query_cost_usd(trace_id):.5f} {elapsed:.1f}s | "
        f"memory={'BRCA1' if with_memory else 'none'} | {text}"
    )


async def _recent(text: str) -> None:
    harness = hm.Harness("fix-round-recent")
    spec = g._RECENT_YEARS
    started = time.monotonic()
    record = await decide(
        harness,
        "fix-round-recent",
        spec.point,
        text,
        spec.options,
        instructions=spec.instructions,
        criteria=spec.criteria,
        default=spec.fail_open,
    )
    elapsed = time.monotonic() - started
    asks = g._asks_for_unbounded_recent_work(record, text)
    print(
        f"asks_how_far_back={asks} | {_record_line(record)} | "
        f"${harness.get_query_cost_usd('fix-round-recent'):.5f} {elapsed:.1f}s | {text}"
    )


async def _literature(text: str) -> None:
    harness = hm.Harness("fix-round-literature")
    spec = g._LITERATURE
    started = time.monotonic()
    record = await decide(
        harness,
        "fix-round-literature",
        spec.point,
        text,
        spec.options,
        instructions=spec.instructions,
        criteria=spec.criteria,
        default=spec.fail_open,
    )
    elapsed = time.monotonic() - started
    print(
        f"used={g._usable_choice(record)} | {_record_line(record)} | "
        f"${harness.get_query_cost_usd('fix-round-literature'):.5f} {elapsed:.1f}s | {text}"
    )


def main() -> None:
    mode, text = sys.argv[1], sys.argv[2]
    if mode == "guardrail":
        asyncio.run(_guardrail(text, "--memory" in sys.argv[3:]))
    elif mode == "recent":
        asyncio.run(_recent(text))
    elif mode == "literature":
        asyncio.run(_literature(text))
    else:
        raise SystemExit(f"unknown mode {mode!r}")


if __name__ == "__main__":
    main()
