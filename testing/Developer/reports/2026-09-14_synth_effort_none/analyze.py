"""Read every *.jsonl run file in this folder and print:
- the markdown live-run table
- per-step median/worst over guard/think/plan/act/write
- aggregate stats: errors, worst synth call, median/worst elapsed
"""
import json
import statistics
from collections import defaultdict

CASE_LABELS = {
    "smoke_test.jsonl": "BRCA1 diseases",
    "r2.jsonl": "BRCA1 variants (disease-cause)",
    "r3.jsonl": "GCK MODY variants",
    "r4.jsonl": "BRCA1 and BRCA2 diseases",
    "r5.jsonl": "BRCA1 diseases (lowercase phrasing)",
    "p1.jsonl": "BRCA1 diseases",
    "p2.jsonl": "GCK MODY variants",
}


def load(path):
    with open(path) as handle:
        return [json.loads(line) for line in handle if line.strip()]


_ORDER = ["guard", "think", "plan", "act", "write"]


def _fixed_step_seconds(run):
    """Re-attribute a step-scoped error's trailing delta to the step that
    actually failed, not to "write".

    `_step_seconds` in measure_write2.py skips updating its `prev_ts`
    anchor whenever a step's own event never fired (the step errored
    before emitting one), so the NEXT bucket that does have a real
    timestamp (the crash-fallback `error`/`done` pair, always present)
    absorbs the whole gap. Two runs in this batch hit exactly this: a
    plan-step timeout (r2 run 1, `source: plan`) landed as `write: 45.2`,
    and a guard-step timeout (p2 run 2, `source: guardrail`) landed as
    `write: 15.083`. Both numbers are real wall time, correctly summed,
    just filed under the wrong step name. This corrects the label using
    the run's own recorded error `source`, so the per-step breakdown does
    not overstate Write's worst case with a Guard or Plan timeout.
    """
    ss = dict(run.get("step_seconds") or {})
    errors = run.get("errors") or []
    if not errors:
        return ss
    source = errors[0].get("source")
    step_name = {"guardrail": "guard"}.get(source, source)
    if step_name not in _ORDER:
        return ss
    idx = _ORDER.index(step_name)
    if ss.get(step_name) is not None:
        return ss  # the step's own event did fire; no gap to fix
    # Find the first non-None bucket at or after idx: it holds the
    # carried-forward cumulative delta.
    carried = None
    carried_idx = None
    for j in range(idx, len(_ORDER)):
        if ss.get(_ORDER[j]) is not None:
            carried = ss[_ORDER[j]]
            carried_idx = j
            break
    if carried is None:
        return ss
    fixed = dict(ss)
    for j in range(idx, carried_idx + 1):
        fixed[_ORDER[j]] = None
    fixed[step_name] = carried
    return fixed


FILES = ["smoke_test.jsonl", "r2.jsonl", "r3.jsonl", "r4.jsonl", "r5.jsonl", "p1.jsonl", "p2.jsonl"]


def main():
    all_runs = []
    for path in FILES:
        for run in load(path):
            run["_file"] = path
            all_runs.append(run)

    print(f"Total runs loaded: {len(all_runs)}")
    n_errors = sum(1 for r in all_runs if r.get("errors"))
    print(f"Runs with an error event: {n_errors}")
    for r in all_runs:
        if r.get("errors"):
            print("  ", r["_file"], r["question"][:40], r["depth"], r["errors"])

    worst_synth = 0.0
    worst_synth_run = None
    elapsed_all = []
    for r in all_runs:
        elapsed_all.append(r["elapsed_s"])
        for sc in r.get("synth_calls", []):
            if sc.get("wall_s", 0) > worst_synth:
                worst_synth = sc["wall_s"]
                worst_synth_run = (r["_file"], r["question"][:40])
    print(f"\nWorst single Synth call: {worst_synth}s ({worst_synth_run})")
    print(f"Median elapsed: {statistics.median(elapsed_all)}s, worst: {max(elapsed_all)}s, best: {min(elapsed_all)}s")

    # per-step breakdown
    step_vals = defaultdict(list)
    for r in all_runs:
        ss = _fixed_step_seconds(r)
        for step in ("guard", "think", "plan", "act", "write"):
            v = ss.get(step)
            if v is not None:
                step_vals[step].append(v)
    print("\nPer-step seconds (median / worst / n):")
    for step in ("guard", "think", "plan", "act", "write"):
        vals = step_vals[step]
        if vals:
            print(f"  {step:6s} median={statistics.median(vals):.2f} worst={max(vals):.2f} n={len(vals)}")
        else:
            print(f"  {step:6s} no data")

    print("\n| Case | Mode | Run | Outcome | First sentence | Words | Headings | List rows | Sources | Synth1 s/w | Repair s/w | Elapsed | step_seconds | Errors |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for path in FILES:
        label = CASE_LABELS.get(path, path)
        for i, r in enumerate(load(path), 1):
            synth = r.get("synth_calls", [])
            first = next((s for s in synth if not s.get("repair")), None)
            repair = next((s for s in synth if s.get("repair")), None)
            s1 = f"{first['wall_s']}/{first.get('reply_words')}" if first else "none"
            s2 = f"{repair['wall_s']}/{repair.get('reply_words')}" if repair else "none"
            src = f"{r['source_count']}"
            ss = _fixed_step_seconds(r)
            ss_str = " ".join(f"{k[0]}{v}" for k, v in ss.items() if v is not None)
            print(f"| {label} | {r['depth']} | {i} | {r.get('outcome')} | {r.get('first_sentence','')[:70]} | "
                  f"{r.get('words')} | {len(r.get('headings') or [])} | {r.get('list_rows')} | {src} | "
                  f"{s1} | {s2} | {r['elapsed_s']} | {ss_str} | {r.get('errors') or 'none'} |")


if __name__ == "__main__":
    main()
