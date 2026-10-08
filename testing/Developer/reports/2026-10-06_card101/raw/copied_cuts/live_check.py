"""Card 101 round 3: the copied clauses this round moves, through the shipped check.

Each item is built by the real first grounding pass (`run_grounding_pass` with
a candidate sink), so the check reads exactly what the app would send: the
sentence up to the copied clause, and the record sentence(s) or value behind
it. Then the shipped `check_reworded_sentences` judges them in Jev mode (item
call plus card 99's pair calls), as develop runs it.

- 4 attacks: synthetic records, from round 2's adversary (A2-101-01 to 03).
- 5 recorded cuts: the copied cuts the offline scan found on screen in the
  recorded answers. Their record text is read at run time from the trace
  files (outside the repository) and is never written out.

Credentials come from the main checkout's `.env` into this process only and
are never printed. Output: one JSON line per repetition, labels only.

Usage: python live_check.py <rep|dry> <wave3_develop_control> <fix_round>
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ["MAIN_CHECKOUT"])
for raw in (ROOT / ".env").read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
os.environ["CLASSIFIER_PROVIDER"] = "jev"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
os.environ["PER_QUERY_COST_CAP_USD"] = "0.05"

from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import (
    SynthesisCandidate,
    run_grounding_pass,
)


def _finding(ref: int, value: str, field: str = "abstract") -> SynthFinding:
    return SynthFinding(
        ref_index=ref,
        citation_id=f"c-{ref}",
        layer="layer_2_ncbi_api",
        tool="ncbi_efetch",
        field=field,
        field_value=value,
        source_url=f"https://pubmed.ncbi.nlm.nih.gov/{ref}/",
        entity_type="Publication",
    )


ATTACKS = [
    (
        "attack_aspirin_head_cut",
        "Aspirin prevents colorectal cancer in adults [1].",
        [_finding(1, "There is no evidence that aspirin prevents colorectal cancer in adults.")],
        "Does aspirin prevent colorectal cancer?",
    ),
    (
        "attack_antibiotics_tail_cut",
        "Antibiotics are effective [1].",
        [_finding(1, "Antibiotics are effective only when a bacterial infection is confirmed.")],
        "Are antibiotics effective for bronchiolitis?",
    ),
    (
        "attack_joined_clauses",
        "Drug X reduces mortality [1] in men [1].",
        [_finding(1, "Drug X reduces mortality in women but not in men.")],
        "Does drug X reduce mortality?",
    ),
    (
        "attack_ribavirin_wrap",
        "Ribavirin can cure bronchiolitis in babies [3].",
        [_finding(3, "Ribavirin", field="name")],
        "Which drugs can cure bronchiolitis in babies?",
    ),
    # Not an attack: a correct gene answer of the same wrapped shape, the
    # graph row naming a disease linked to the gene asked about. Asked to show
    # what sending every wrapped value to the check does to gene answers.
    (
        "probe_gene_association_wrap",
        "BRCA1 is associated with familial cancer of breast [2].",
        [_finding(2, "Familial cancer of breast", field="name")],
        "What diseases is BRCA1 associated with?",
    ),
]

RECORDED = [
    ("recorded_r202q_genotype", "The most common co-variant was the R202Q/M694V genotype"),
    ("recorded_218_genes_borderline", "Deleterious variants were identified in 218 distinct genes"),
    ("recorded_gerd_quality_of_life", "GERD affects quality of life"),
    ("recorded_hfnc_children", "A high-flow nasal cannula is becoming common for children with severe bronchiolitis"),
    ("recorded_goal_of_therapy", "The goal of therapy is to maintain adequate oxygenation and hydration"),
]


def _recorded_items(folders: list[Path]) -> list[tuple[str, str, list[SynthFinding], str]]:
    """Each recorded cut with the one recorded finding whose text holds it."""
    out = []
    for label, sentence in RECORDED:
        found = None
        for folder in folders:
            for path in sorted(folder.glob("*.jsonl")):
                for line in path.read_text().splitlines():
                    row = json.loads(line) if line.strip() else {}
                    if not isinstance(row, dict) or row.get("tag") != "FINDINGS":
                        continue
                    for f in row["data"]:
                        if sentence.lower() in (f["text"] or "").lower():
                            found = _finding(1, f["text"], f["field"])
                            break
                    break
                if found:
                    break
            if found:
                break
        if found is None:
            sys.exit(f"recorded cut not found: {label}")
        out.append((label, f"{sentence} [1].", [found], ""))
    return out


def build(folders: list[Path]) -> list[tuple[str, SynthesisCandidate]]:
    items: list[tuple[str, SynthesisCandidate]] = []
    for label, narrative, findings, question in ATTACKS + _recorded_items(folders):
        sink: list[SynthesisCandidate] = []
        run_grounding_pass(narrative, findings, question=question, candidate_sink=sink)
        if not sink:
            sys.exit(f"not a check candidate: {label}")
        for number, candidate in enumerate(sink):
            items.append((f"{label}#{number}" if len(sink) > 1 else label, candidate))
    return items


async def _never_guard(_messages, _budget):
    raise AssertionError("Jev mode never asks the guard tier")


async def main(rep: str, items: list[tuple[str, SynthesisCandidate]]) -> dict:
    candidates = [candidate for _, candidate in items]
    pair_calls, not_asked = sc.build_pair_calls(candidates)
    trace = f"card101r3-{rep}"
    harness = Harness(trace_id=trace)
    try:
        approved = await sc.check_reworded_sentences(
            candidates, harness=harness, trace_id=trace, budget_s=11.0, ask_guard=_never_guard
        )
        error = None
    except Exception as exc:  # noqa: BLE001  measurement: record and go on
        approved, error = frozenset(), type(exc).__name__
    return {
        "rep": rep,
        "approved": sorted(label for label, c in items if c.key in approved),
        "held": sorted(label for label, c in items if c.key not in approved),
        "not_asked": len(not_asked),
        "error": error,
        "jev_calls": 1 + len(pair_calls),
        "cost_usd": harness.get_query_cost_usd(trace),
    }


if __name__ == "__main__":
    items = build([Path(p) for p in sys.argv[2:]])
    if sys.argv[1] == "dry":
        for label, candidate in items:
            print(label, "| quotes", len(candidate.quotes), "| sentence chars", len(candidate.sentence))
        sys.exit(0)
    result = asyncio.run(main(sys.argv[1], items))
    print(json.dumps(result))
    with open(Path(__file__).with_name("live_check.jsonl"), "a") as out:
        out.write(json.dumps(result) + "\n")
