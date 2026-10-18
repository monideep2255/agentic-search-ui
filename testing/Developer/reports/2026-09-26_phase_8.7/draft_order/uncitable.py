"""Build phase 8.7, T-8.7-01, option B: which Opus bench runs had a prompt
finding the code-built listing cannot cite by its own id.

That set is known before any writer call, and it is the completeness
draft's whole job. No model is called. Reads writer bench 3's
`results.jsonl` and `raw/` for `anthropic/claude-opus-5.5+effort-minimal`,
runs 1 to 3, re-grounds each run's saved prompt findings through the
product's own `build_structured_fallback_narrative` and `run_grounding_pass`,
and prints one line per run: question, run, whether the completeness draft
fired, the prompt finding count, the uncitable count and up to six of their
fields.

Approximate in one respect: the saved findings carry ref, field, value and
url only, so the entity type, CURIE and resolved-name flag are unknown and a
rendered label may differ from the live one. The value text, which is what
grounds, is exact.

Usage, from the repository root:
    python testing/Developer/reports/2026-09-26_phase_8.7/draft_order/uncitable.py \
        > testing/Developer/reports/2026-09-26_phase_8.7/draft_order/uncitable_output.txt
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "src"))
from system_03_search_agent.synthesis.findings import (
    SynthFinding,
    build_structured_fallback_narrative,
)
from system_03_search_agent.synthesis.grounding import run_grounding_pass

HERE = REPO / "testing/Developer/reports/2026-09-26_writer_bench_3"
MODEL = "anthropic/claude-opus-5.5+effort-minimal"
rows = []
for line in (HERE / "results.jsonl").read_text().splitlines():
    r = json.loads(line)
    if r["model"] != MODEL or r["run"] not in (1, 2, 3):
        continue
    raw = json.loads((HERE / "raw" / f"{MODEL.replace('/', '_')}__{r['question_id']}__r{r['run']}.json").read_text())
    findings = [
        SynthFinding(
            ref_index=f["ref"],
            citation_id=f"c-{f['ref']}",
            layer="",
            tool="",
            field=f["field"],
            field_value=f["value"],
            source_url=f["url"],
        )
        for f in raw["rec"]["findings"]
    ]
    probe = run_grounding_pass(
        build_structured_fallback_narrative(findings), findings, core_ask_required=True, question=r["question"]
    )
    cited = {c.finding.citation_id for c in probe.claims}
    u = [f for f in findings if f.citation_id not in cited]
    fired = r["writer_calls"] >= 2
    rows.append((r["question_id"], r["run"], fired, len(findings), len(u), [f.field for f in u][:6]))
for row in rows:
    print(*row)
fired_u = sum(1 for q, run, fired, n, u, _ in rows if fired and u)
fired_no_u = sum(1 for q, run, fired, n, u, _ in rows if fired and not u)
single_u = sum(1 for q, run, fired, n, u, _ in rows if not fired and u)
single_no_u = sum(1 for q, run, fired, n, u, _ in rows if not fired and not u)
print(f"fired with U non-empty {fired_u}; fired with U empty {fired_no_u}; "
      f"not fired with U non-empty {single_u}; not fired with U empty {single_no_u}")
