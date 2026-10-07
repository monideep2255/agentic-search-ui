"""Card 23 adversary probes. Throwaway. Run from the worktree root with the
project venv: python testing/Developer/reports/2026-10-06_card23/raw/adversary/probe.py

Drives the real write_node (only the model call and the MedGen lookup faked),
then feeds the token stream to (a) a line-for-line Python port of the web
screen's note placement (frontend/src/hooks/useRunView.ts:684-821), (b) the
real CLI Renderer, (c) the real saved-answer markdown builder.
"""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "system_03_search_agent" / "core"))

import pytest
import test_write_answer_structure as T

from system_03_search_agent.core import graph as G
from system_03_search_agent.synthesis.answer_layout import (
    VARIANT_TO_DISEASE_SOURCE_NOTE as NOTE,
)

GENE_ROW = {
    "node_or_edge_type": "Gene",
    "curie": "NCBIGene:6927",
    "fields": {"name": "HNF1A", "symbol": "HNF1A"},
    "source_url": "https://www.ncbi.nlm.nih.gov/gene/6927",
    "graph_snapshot_version": "v1",
}
TITLES = dict(T._MEDGEN_TITLES)


async def fake_resolve(ids):
    return {cid: TITLES.get(cid) for cid in ids}


def frontend_place(tokens):
    """Port of useRunView.ts token loop: where does each note end up?"""
    pending, system_notes, placed = [], [], []
    pending_heading = None
    for t in tokens:
        kind = t.get("kind")
        if kind == "paragraph_break" or kind == "table_header":
            continue
        if kind == "heading":
            pending_heading = t["text"].strip()
            continue
        if kind == "note":
            n = t["text"].strip()
            if n:
                pending.append(n)
            continue
        text = t["text"].strip()
        if not text:
            continue
        if kind is not None and pending:
            placed.append(("noteBefore", " ".join(pending), "next heading=" + str(pending_heading), "next kind=" + kind))
            pending = []
        if kind is not None:
            pending_heading = None
    system_notes.extend(pending)
    return placed, system_notes


def cli_text(result):
    from system_03_search_agent.adapters.cli.render import Renderer
    out, err = io.StringIO(), io.StringIO()
    r = Renderer(out, err, operator=False)
    for e in result["events"]:
        if e.type in ("token", "citation"):
            r.handle(e)
    return out.getvalue()


def markdown(result):
    from system_03_search_agent.feedback.capture import answer_markdown_from
    return answer_markdown_from(result["events"])


async def run(name, depth, rows, reply=None, show_cli=False, show_md=False):
    mp = pytest.MonkeyPatch()
    try:
        T._env.__wrapped__(mp) if hasattr(T._env, "__wrapped__") else None
        mp.setenv("GUARD_MODEL", "test-provider/guard-model")
        mp.setenv("PLAN_MODEL", "test-provider/plan-model")
        mp.setenv("SYNTH_MODEL", "test-provider/synth-model")
        mp.setenv("PER_QUERY_COST_CAP_USD", "1.0")
        mp.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
        mp.setattr(G, "resolve_concept_ids", fake_resolve)
        T._install(mp, reply or (lambda lines: f"{lines[1]} [1]."))
        result = await G.write_node(T._state(depth, rows=rows))
    finally:
        mp.undo()
    tokens = T._tokens(result)
    kinds = [(t["kind"], (t["text"].strip() or "|".join(t.get("cells") or []))[:70]) for t in tokens]
    print(f"\n=== {name} ({depth}) ===")
    for k in kinds:
        print("  ", k)
    print("  source-note count:", sum(1 for t in tokens if t["kind"] == "note" and t["text"] == NOTE))
    placed, sysn = frontend_place(tokens)
    print("  frontend in-place notes:", placed)
    print("  frontend Notes list after answer:", sysn)
    if show_cli:
        print("  --- CLI stdout ---")
        print(cli_text(result))
    if show_md:
        print("  --- saved markdown ---")
        print(markdown(result))
    return tokens, result


async def main():
    which = sys.argv[1:] or ["all"]
    if "all" in which or "alone" in which:
        await run("P1 variant table alone", "researcher", T._FOLDED_VARIANT_ROWS, show_cli=True, show_md=True)
    if "all" in which or "gene" in which:
        await run("P2 variant table then gene", "researcher", [*T._FOLDED_VARIANT_ROWS, GENE_ROW])
    if "all" in which or "depths" in which:
        for d in ("clinical_brief", "deep_technical"):
            await run("P3 depth", d, T._FOLDED_VARIANT_ROWS)
    if "all" in which or "fallback" in which:
        await run("P4 structured fallback (model writes nothing groundable)", "researcher",
                  [*T._FOLDED_VARIANT_ROWS, GENE_ROW], reply=lambda lines: "Nothing to say.")


asyncio.run(main())
