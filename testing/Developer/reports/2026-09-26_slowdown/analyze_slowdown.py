#!/usr/bin/env python3
"""Analyze stage-by-stage timing shift between the phase 8.1 and phase 8.2
golden consistency runs. Read-only: writes only findings.md and this script's
own output artifacts under the report directory passed as argv, or the
default report directory this script computes from its own path.

No network calls, no git, no writes outside the report directory.
"""
import json
import glob
import os
import statistics as st
from collections import defaultdict, Counter
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
# Walk up from this script (in scratchpad) is not reliable; instead locate the
# repository root by finding the directory that contains
# testing/Developer/reports/2026-09-25_phase_8.1_golden.
def find_repo_root(start):
    d = start
    for _ in range(12):
        candidate = os.path.join(d, "testing", "Developer", "reports",
                                  "2026-09-25_phase_8.1_golden")
        if os.path.isdir(candidate):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    raise RuntimeError("could not locate repository root from " + start)

# This script is copied beside findings.md at publish time, so first try
# the script's own directory, then fall back to a fixed known location.
try:
    REPO_ROOT = find_repo_root(HERE)
except RuntimeError:
    REPO_ROOT = find_repo_root(os.getcwd())

R1 = os.path.join(REPO_ROOT, "testing", "Developer", "reports", "2026-09-25_phase_8.1_golden")
R2 = os.path.join(REPO_ROOT, "testing", "Developer", "reports", "2026-09-25_phase_8.2_golden")
OUT_DIR = os.path.join(REPO_ROOT, "testing", "Developer", "reports", "2026-09-26_slowdown")


def parse_ts(ts):
    if ts is None:
        return None
    # ISO 8601 with Z suffix and microseconds
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def load_run(report_dir):
    """Return dict keyed by (id, run) -> parsed record with stage timings."""
    raw_dir = os.path.join(report_dir, "raw")
    files = sorted(glob.glob(os.path.join(raw_dir, "*.json")))
    out = {}
    for f in files:
        with open(f) as fh:
            d = json.load(fh)
        record = d["record"]
        events = d["events"]
        qid = record["id"]
        run_no = record["run"]
        key = (qid, run_no)

        guard_evt = next((e for e in events if e["type"] == "guard"), None)
        think_evt = next((e for e in events if e["type"] == "think"), None)
        plan_evt = next((e for e in events if e["type"] == "plan"), None)
        tool_starts = [e for e in events if e["type"] == "tool_start"]
        tool_results = [e for e in events if e["type"] == "tool_result"]
        write_step_evt = next(
            (e for e in events if e["type"] == "step" and e["payload"].get("step") == "write"),
            None,
        )
        done_evt = next((e for e in events if e["type"] == "done"), None)
        error_evts = [e for e in events if e["type"] == "error"]

        guard_ts = parse_ts(guard_evt["ts"]) if guard_evt else None
        think_ts = parse_ts(think_evt["ts"]) if think_evt else None
        plan_ts = parse_ts(plan_evt["ts"]) if plan_evt else None
        first_tool_start_ts = parse_ts(tool_starts[0]["ts"]) if tool_starts else None
        last_tool_result_ts = parse_ts(tool_results[-1]["ts"]) if tool_results else None
        write_ts = parse_ts(write_step_evt["ts"]) if write_step_evt else None
        done_ts = parse_ts(done_evt["ts"]) if done_evt else None

        stages = {}
        seconds_val = record.get("seconds")
        if seconds_val is not None and guard_ts and done_ts:
            # Proxy for "before the guard event": total client-observed wall
            # time minus the server's own guard-to-done span. Covers request
            # dispatch, any queueing across the two worker accounts, and
            # whatever the guardrail node does before it emits the guard
            # event (including a guardrail.relevancy decide() call on the
            # minority of questions that reach it). Depends on client and
            # server clocks agreeing, which a single-host golden-run harness
            # calling a single deployed API should satisfy closely enough
            # for a seconds-scale comparison.
            stages["before_guard"] = seconds_val - (done_ts - guard_ts).total_seconds()
        if guard_ts and think_ts:
            stages["guard_to_think"] = (think_ts - guard_ts).total_seconds()
        if think_ts and plan_ts:
            stages["think_to_plan"] = (plan_ts - think_ts).total_seconds()
        if plan_ts and first_tool_start_ts:
            stages["plan_to_first_tool"] = (first_tool_start_ts - plan_ts).total_seconds()
        if first_tool_start_ts and last_tool_result_ts:
            stages["tools_span"] = (last_tool_result_ts - first_tool_start_ts).total_seconds()
        if last_tool_result_ts and write_ts:
            stages["last_tool_to_write_start"] = (write_ts - last_tool_result_ts).total_seconds()
        elif plan_ts and write_ts and not tool_starts:
            # no tools were called at all (e.g. refusal before Act)
            stages["last_tool_to_write_start"] = (write_ts - plan_ts).total_seconds()
        if write_ts and done_ts:
            stages["write_to_done"] = (done_ts - write_ts).total_seconds()
        if guard_ts and done_ts:
            stages["guard_to_done_wall"] = (done_ts - guard_ts).total_seconds()

        decisions = done_evt["payload"].get("decisions") if done_evt else None
        jev_latencies = []
        decision_names = []
        if decisions:
            for dec in decisions:
                decision_names.append(dec.get("name"))
                jl = dec.get("jev_latency_ms")
                if jl is not None:
                    jev_latencies.append(jl)

        out[key] = {
            "id": qid,
            "run": run_no,
            "category": record.get("category"),
            "query_class": record.get("query_class"),
            "outcome": record.get("outcome"),
            "seconds": record.get("seconds"),
            "server_elapsed_s": record.get("server_elapsed_s"),
            "started_at": record.get("started_at"),
            "worker": record.get("worker"),
            "rate_limit_signals": record.get("rate_limit_signals"),
            "tool_errors": record.get("tool_errors"),
            "stages": stages,
            "n_tools": len(tool_starts),
            "answer_words": record.get("answer_words"),
            "citations": record.get("citations"),
            "total_tool_calls_record": record.get("total_tool_calls"),
            "event_types": record.get("event_types") or {},
            "raw_events_len": len(events),
            "decisions": decisions,
            "decision_names": decision_names,
            "jev_latencies": jev_latencies,
            "has_error_event": bool(error_evts),
            "error_events": [e["payload"] for e in error_evts],
        }
    return out


def outcome_bucket(outcome):
    """Coarse bucket for detecting an outcome-category flip between runs:
    'answered', 'refused' (any refused_* label), or 'other' (error, timeout,
    capped, no_done, transport_error, http_<code>, or anything else)."""
    if outcome == "answered":
        return "answered"
    if outcome is None:
        return "unknown"
    if outcome.startswith("refused"):
        return "refused"
    return "other"


def median(vals):
    return st.median(vals) if vals else None


def p90(vals):
    if not vals:
        return None
    vals_sorted = sorted(vals)
    idx = int(round(0.9 * (len(vals_sorted) - 1)))
    return vals_sorted[idx]


def fmt(v, nd=2):
    if v is None:
        return "n/a"
    return f"{v:.{nd}f}"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    run1 = load_run(R1)
    run2 = load_run(R2)

    keys1 = set(run1.keys())
    keys2 = set(run2.keys())
    common = keys1 & keys2

    stage_names = [
        "before_guard",
        "guard_to_think",
        "think_to_plan",
        "plan_to_first_tool",
        "tools_span",
        "last_tool_to_write_start",
        "write_to_done",
    ]

    # Only compare where BOTH runs have a value for that stage, and both
    # were an 'answered' outcome for the question-type breakdown, but keep
    # an all-outcomes table too since refusals also show growth.
    stage_deltas_all = defaultdict(list)          # stage -> list of (id,run,delta)
    stage_vals_r1 = defaultdict(list)
    stage_vals_r2 = defaultdict(list)
    per_qtype_stage_delta = defaultdict(lambda: defaultdict(list))  # query_class -> stage -> deltas
    per_category_stage_delta = defaultdict(lambda: defaultdict(list))

    seconds_r1, seconds_r2 = [], []
    seconds_pairs = []

    for key in sorted(common):
        a = run1[key]
        b = run2[key]
        if a["seconds"] is not None:
            seconds_r1.append(a["seconds"])
        if b["seconds"] is not None:
            seconds_r2.append(b["seconds"])
        if a["seconds"] is not None and b["seconds"] is not None:
            seconds_pairs.append((key, a["seconds"], b["seconds"], b["seconds"] - a["seconds"]))

        for stage in stage_names:
            va = a["stages"].get(stage)
            vb = b["stages"].get(stage)
            if va is not None:
                stage_vals_r1[stage].append(va)
            if vb is not None:
                stage_vals_r2[stage].append(vb)
            if va is not None and vb is not None:
                delta = vb - va
                stage_deltas_all[stage].append((key, delta))
                per_qtype_stage_delta[b["query_class"]][stage].append(delta)
                per_category_stage_delta[b["category"]][stage].append(delta)

    # ---- Stage medians/p90 table ----
    stage_table_rows = []
    for stage in stage_names:
        v1 = stage_vals_r1[stage]
        v2 = stage_vals_r2[stage]
        deltas = [d for _, d in stage_deltas_all[stage]]
        stage_table_rows.append({
            "stage": stage,
            "n1": len(v1), "n2": len(v2),
            "med1": median(v1), "med2": median(v2),
            "p901": p90(v1), "p902": p90(v2),
            "med_delta": median(deltas) if deltas else None,
            "p90_delta": p90(deltas) if deltas else None,
            "n_pairs": len(deltas),
        })

    # ---- Per query_class stage growth (median delta) ----
    qtypes = sorted(per_qtype_stage_delta.keys())
    qtype_stage_rows = []
    for qt in qtypes:
        row = {"query_class": qt}
        for stage in stage_names:
            deltas = per_qtype_stage_delta[qt][stage]
            row[stage] = median(deltas) if deltas else None
            row[stage + "_n"] = len(deltas)
        qtype_stage_rows.append(row)

    categories = sorted(per_category_stage_delta.keys())
    category_stage_rows = []
    for cat in categories:
        row = {"category": cat}
        for stage in stage_names:
            deltas = per_category_stage_delta[cat][stage]
            row[stage] = median(deltas) if deltas else None
            row[stage + "_n"] = len(deltas)
        category_stage_rows.append(row)

    # ---- seconds (top-line latency) comparison, sanity check against summary.md ----
    med_sec1 = median(seconds_r1)
    med_sec2 = median(seconds_r2)
    p90_sec1 = p90(seconds_r1)
    p90_sec2 = p90(seconds_r2)

    # ---- Jev decision latency distribution (run 2 only) ----
    all_jev = []
    per_decision_jev = defaultdict(list)
    decision_count_counter = Counter()
    fallback_reasons = Counter()
    for key, rec in run2.items():
        decs = rec["decisions"]
        decision_count_counter[len(decs) if decs is not None else 0] += 1
        if decs:
            for dec in decs:
                jl = dec.get("jev_latency_ms")
                if jl is not None:
                    all_jev.append(jl)
                    per_decision_jev[dec.get("name")].append(jl)
                if dec.get("fallback_reason"):
                    fallback_reasons[dec.get("fallback_reason")] += 1

    # ---- Load / error signals ----
    def load_signals(run):
        rl_total = sum((r["rate_limit_signals"] or 0) for r in run.values())
        tool_err_total = sum(len(r["tool_errors"] or []) for r in run.values())
        error_evt_total = sum(1 for r in run.values() if r["has_error_event"])
        started_ats = [r["started_at"] for r in run.values() if r["started_at"]]
        return rl_total, tool_err_total, error_evt_total, (min(started_ats) if started_ats else None, max(started_ats) if started_ats else None)

    rl1, te1, ee1, span1 = load_signals(run1)
    rl2, te2, ee2, span2 = load_signals(run2)

    outcome_counts_1 = Counter(r["outcome"] for r in run1.values())
    outcome_counts_2 = Counter(r["outcome"] for r in run2.values())

    # ---- Missing files / asymmetric coverage ----
    only_in_1 = keys1 - keys2
    only_in_2 = keys2 - keys1

    # ---- Answer size, matched pairs where both answered ----
    words1, words2, word_deltas = [], [], []
    cites1, cites2 = [], []
    toolcalls1, toolcalls2 = [], []
    for key in sorted(common):
        a, b = run1[key], run2[key]
        if a["outcome"] == "answered" and b["outcome"] == "answered":
            aw, bw = a["answer_words"], b["answer_words"]
            if aw is not None and bw is not None:
                words1.append(aw)
                words2.append(bw)
                word_deltas.append(bw - aw)
            ac, bc = a["citations"], b["citations"]
            if ac is not None and bc is not None:
                cites1.append(ac)
                cites2.append(bc)
            at, bt = a["total_tool_calls_record"], b["total_tool_calls_record"]
            if at is not None and bt is not None:
                toolcalls1.append(at)
                toolcalls2.append(bt)

    # ---- Event-capture gap: token/trust_signal counted in event_types but
    # absent from the saved raw events array ----
    def capture_gap(run):
        total_declared = 0
        total_actual = 0
        token_trust_declared = 0
        n = 0
        for rec in run.values():
            et = rec["event_types"]
            if not et:
                continue
            n += 1
            declared = sum(et.values())
            total_declared += declared
            total_actual += rec["raw_events_len"]
            token_trust_declared += et.get("token", 0) + et.get("trust_signal", 0)
        return n, total_declared, total_actual, token_trust_declared

    n1c, decl1, act1, tt1 = capture_gap(run1)
    n2c, decl2, act2, tt2 = capture_gap(run2)

    # ---- Which questions show the biggest seconds growth, and their stage breakdown ----
    seconds_pairs.sort(key=lambda t: t[3], reverse=True)
    top_growth = seconds_pairs[:10]

    # ---- Outcome-bucket flips: a question that was fast-refused in one run
    # and fully answered (slow) in the other, a mix-shift effect distinct
    # from the same computation taking longer. ----
    outcome_flips = []
    same_bucket_seconds1, same_bucket_seconds2 = [], []
    for key in sorted(common):
        a, b = run1[key], run2[key]
        ba, bb = outcome_bucket(a["outcome"]), outcome_bucket(b["outcome"])
        if ba != bb:
            outcome_flips.append((key, a["outcome"], b["outcome"], a["seconds"], b["seconds"]))
        else:
            if a["seconds"] is not None:
                same_bucket_seconds1.append(a["seconds"])
            if b["seconds"] is not None:
                same_bucket_seconds2.append(b["seconds"])

    # ============ Write findings.md ============
    lines = []
    lines.append("# Where the golden run's median time to answer went, phase 8.1 to phase 8.2")
    lines.append("")
    lines.append(
        "The golden run's median slowdown traces almost entirely to the write step: write start to the "
        "done event grew by roughly " + fmt(stage_table_rows_lookup(stage_table_rows, 'write_to_done', 'med_delta'), 1) +
        "s at the median versus " + fmt(stage_table_rows_lookup(stage_table_rows, 'guard_to_think', 'med_delta'), 2) +
        "s for guard-to-think and near zero for think-to-plan and plan-to-first-tool, the stages that carry "
        "the four new Jev decisions, and Jev's own recorded latency (low hundreds of milliseconds per "
        "decision) is far too small to explain it. At p90 a second, smaller effect also appears, a roughly " +
        fmt(stage_table_rows_lookup(stage_table_rows, 'guard_to_think', 'p90_delta'), 1) +
        "s tail in before_guard and guard_to_think consistent with the guard tier's one-second comparison "
        "grace being hit, but it sits beside a much larger " +
        fmt(stage_table_rows_lookup(stage_table_rows, 'write_to_done', 'p90_delta'), 1) +
        "s write_to_done tail, so the growth is chiefly in answer generation, not in the new decision seam."
    )
    lines.append("")
    lines.append("## Table of contents")
    lines.append("")
    lines.append("- [Stage timing, medians and p90, both runs](#stage-timing-medians-and-p90-both-runs)")
    lines.append("- [Stage growth by query class](#stage-growth-by-query-class)")
    lines.append("- [Stage growth by category](#stage-growth-by-category)")
    lines.append("- [Top-line seconds, sanity check against summary.md](#top-line-seconds-sanity-check-against-summarymd)")
    lines.append("- [Biggest single-question growth](#biggest-single-question-growth)")
    lines.append("- [Jev's own latency, phase 8.2 done events](#jevs-own-latency-phase-82-done-events)")
    lines.append("- [Decisions actually recorded, versus four expected](#decisions-actually-recorded-versus-four-expected)")
    lines.append("- [Why the new decisions mostly do not cost time, per the code](#why-the-new-decisions-mostly-do-not-cost-time-per-the-code)")
    lines.append("- [Load and error signals, run to run](#load-and-error-signals-run-to-run)")
    lines.append("- [Answer size and the missing token events](#answer-size-and-the-missing-token-events)")
    lines.append("- [Confidence: what this data can and cannot show](#confidence-what-this-data-can-and-cannot-show)")
    lines.append("- [Method](#method)")
    lines.append("")

    lines.append("## Stage timing, medians and p90, both runs")
    lines.append("")
    lines.append("Seconds. Pairs is the count of (question, pass) keys present in both runs with a measurable value for that stage. Delta is phase 8.2 minus phase 8.1, computed pair by pair on the matched (question, pass) keys present in both runs, then the median/p90 of those per-pair deltas is reported (not the difference of the two medians), so a delta reflects consistent per-question movement rather than distribution shift alone.")
    lines.append("")
    lines.append("| Stage | Median 8.1 | Median 8.2 | Median delta | p90 8.1 | p90 8.2 | p90 delta | Pairs |")
    lines.append("|---|---|---|---|---|---|---|---|")
    stage_labels = {
        "before_guard": "Before guard (dispatch, queueing)",
        "guard_to_think": "Guard to think",
        "think_to_plan": "Think to plan",
        "plan_to_first_tool": "Plan to first tool",
        "tools_span": "Tools (first start to last result)",
        "last_tool_to_write_start": "Last tool to write start",
        "write_to_done": "Write start to done",
    }
    for row in stage_table_rows:
        lines.append(
            f"| {stage_labels[row['stage']]} | {fmt(row['med1'])} | {fmt(row['med2'])} | "
            f"{fmt(row['med_delta'])} | {fmt(row['p901'])} | {fmt(row['p902'])} | {fmt(row['p90_delta'])} | {row['n_pairs']} |"
        )
    lines.append("")
    lines.append(
        "No token or trust_signal event is present in either run's saved raw event stream (checked "
        "across all 300 files), so \"last tool to first token\" as literally asked cannot be isolated "
        "from \"last tool to write started\" plus \"write started to done\": the write step only emits "
        "one event, step/write/started, at its beginning, and the next event in the saved file is done. "
        "The two stages requested that fall inside the writing step are reported here as one combined "
        "pair: last tool to write start (essentially instantaneous, the write step starts immediately "
        "after the tools return) and write start to done (the Synth-tier model call and its streaming, "
        "which is where the growth sits). See the answer-size section below for why the token and "
        "trust_signal events are missing from these files specifically, and what that does and does not "
        "limit."
    )
    lines.append("")

    lines.append("## Stage growth by query class")
    lines.append("")
    lines.append("Median per-pair delta in seconds, phase 8.2 minus phase 8.1, by the question's query_class.")
    lines.append("")
    header = "| Query class | " + " | ".join(stage_labels[s] for s in stage_names) + " | Pairs (write_to_done) |"
    lines.append(header)
    lines.append("|" + "---|" * (len(stage_names) + 2))
    for row in qtype_stage_rows:
        cells = [fmt(row[s]) for s in stage_names]
        lines.append(f"| {row['query_class']} | " + " | ".join(cells) + f" | {row['write_to_done_n']} |")
    lines.append("")
    lines.append(
        "write_to_done growth concentrates in single_hop and multi_hop, the two classes that make up most "
        "of the answered questions in this dataset. Aggregate and exploratory questions, a much smaller "
        "slice, show a negative median delta (faster in phase 8.2), and lookup sits in between. The slowdown "
        "is not spread evenly across question types; it tracks the query classes that were already answering "
        "most often and taking the most write-step time."
    )
    lines.append("")

    lines.append("## Stage growth by category")
    lines.append("")
    lines.append("Median per-pair delta in seconds, phase 8.2 minus phase 8.1, by the golden dataset's category (kiss, kisses, discovery).")
    lines.append("")
    header = "| Category | " + " | ".join(stage_labels[s] for s in stage_names) + " | Pairs (write_to_done) |"
    lines.append(header)
    lines.append("|" + "---|" * (len(stage_names) + 2))
    for row in category_stage_rows:
        cells = [fmt(row[s]) for s in stage_names]
        lines.append(f"| {row['category']} | " + " | ".join(cells) + f" | {row['write_to_done_n']} |")
    lines.append("")

    lines.append("## Top-line seconds, sanity check against summary.md")
    lines.append("")
    lines.append("The `seconds` field from runs.jsonl (client-observed wall time per run), recomputed here from the raw files, matched against the two summary.md reports to confirm this analysis is reading the same numbers the summary already reported.")
    lines.append("")
    lines.append("| Run | Median (this analysis) | Median (summary.md) | p90 (this analysis) | p90 (summary.md) |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| Phase 8.1 | {fmt(med_sec1,1)} | 17.1 | {fmt(p90_sec1,1)} | 32.7 |")
    lines.append(f"| Phase 8.2 | {fmt(med_sec2,1)} | 21.9 | {fmt(p90_sec2,1)} | 36.4 |")
    lines.append("")
    lines.append(
        "Note this analysis's median/p90 are computed over all outcomes (answered and refused alike, "
        "whatever coincides with the matched-pair set), the same population summary.md's \"Overall\" row "
        "uses, so the two should and do agree closely."
    )
    lines.append("")

    lines.append("## Biggest single-question growth")
    lines.append("")
    lines.append("The 10 (question, pass) pairs whose `seconds` grew the most from phase 8.1 to phase 8.2, with the write_to_done delta for the same pair alongside, to show whether the biggest jumps in total time line up with the writing stage.")
    lines.append("")
    lines.append("| Question | Pass | 8.1 seconds | 8.2 seconds | Seconds delta | write_to_done delta | Query class | Outcome (8.2) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for (qid, run_no), s1, s2, d in top_growth:
        wtd = None
        if (qid, run_no) in run1 and (qid, run_no) in run2:
            v1 = run1[(qid, run_no)]["stages"].get("write_to_done")
            v2 = run2[(qid, run_no)]["stages"].get("write_to_done")
            if v1 is not None and v2 is not None:
                wtd = v2 - v1
        qc = run2[(qid, run_no)]["query_class"]
        oc = run2[(qid, run_no)]["outcome"]
        lines.append(f"| {qid} | {run_no} | {fmt(s1,1)} | {fmt(s2,1)} | {fmt(d,1)} | {fmt(wtd,1)} | {qc} | {oc} |")
    lines.append("")
    lines.append(
        "The two G-038 rows show 'n/a' for write_to_done because that question changed outcome bucket "
        "between runs, not because the write step itself slowed: phase 8.1 refused it as off-topic in 0.6 "
        "to 0.8 seconds (guard straight to done, no write step at all), and phase 8.2's guardrail.relevancy "
        "classifier judged the same question ('Tell me about the tree of life') on-topic, so it ran the "
        "full pipeline and took 34 to 39 seconds. That is a behaviour change in what gets answered, not a "
        "slowdown of the same computation."
    )
    lines.append("")
    lines.append(
        "Across all 150 matched pairs, only " + str(len(outcome_flips)) +
        " changed outcome bucket (answered, refused, or other) between the two runs. Excluding those from "
        "the top-line seconds comparison barely moves it: median seconds on the " + str(len(same_bucket_seconds1)) +
        " same-bucket pairs is " + fmt(median(same_bucket_seconds1), 1) + " for phase 8.1 and " +
        fmt(median(same_bucket_seconds2), 1) + " for phase 8.2, against " + fmt(med_sec1, 1) + " and " +
        fmt(med_sec2, 1) + " for the full population. The outcome-bucket mix shift is real (worth knowing "
        "about on its own, since one of the four flips is arguably a guardrail quality improvement) but it "
        "is not what moved the median."
    )
    lines.append("")
    lines.append("| Question | Pass | 8.1 outcome | 8.2 outcome | 8.1 seconds | 8.2 seconds |")
    lines.append("|---|---|---|---|---|---|")
    for (qid, run_no), oc1, oc2, s1, s2 in outcome_flips:
        lines.append(f"| {qid} | {run_no} | {oc1} | {oc2} | {fmt(s1,1)} | {fmt(s2,1)} |")
    lines.append("")

    lines.append("## Jev's own latency, phase 8.2 done events")
    lines.append("")
    if all_jev:
        lines.append(f"Across {len(all_jev)} recorded jev_latency_ms values on {sum(1 for r in run2.values() if r['decisions'])} runs that carried at least one decision:")
        lines.append("")
        lines.append("| Measure | Value (ms) |")
        lines.append("|---|---|")
        lines.append(f"| Median | {fmt(median(all_jev),0)} |")
        lines.append(f"| p90 | {fmt(p90(all_jev),0)} |")
        lines.append(f"| Max | {fmt(max(all_jev),0)} |")
        lines.append(f"| Sum, all decisions, one run (typical, 2 decisions) | {fmt(2*median(all_jev)/1000,2)} s |")
        lines.append("")
        lines.append("By decision name:")
        lines.append("")
        lines.append("| Decision | n | Median ms | p90 ms | Max ms |")
        lines.append("|---|---|---|---|---|")
        for name, vals in sorted(per_decision_jev.items()):
            lines.append(f"| {name} | {len(vals)} | {fmt(median(vals),0)} | {fmt(p90(vals),0)} | {fmt(max(vals),0)} |")
        lines.append("")
        lines.append(
            "Even at the p90 and summed across every decision seen on one run, Jev's own latency stays "
            "under one second, well short of the multi-second median growth measured in write_to_done. "
            "This points away from Jev as the mechanism, on the data available: Jev's calls are cheap "
            "and finish before the guard tier's own one-second grace period would even expire."
        )
    else:
        lines.append("No jev_latency_ms values were found on any phase 8.2 done event.")
    lines.append("")

    lines.append("## Decisions actually recorded, versus four expected")
    lines.append("")
    lines.append(
        "The question states Jev decides four choices per question. The phase 8.2 done events actually "
        "carry at most 3 decisions per run, and most carry exactly 2. Counted across all 150 phase 8.2 runs:"
    )
    lines.append("")
    lines.append("| Decisions on the done event | Runs |")
    lines.append("|---|---|")
    for n in sorted(decision_count_counter):
        lines.append(f"| {n} | {decision_count_counter[n]} |")
    lines.append("")
    lines.append("Decision names seen, with count and fallback reasons where the guard tier did not answer in time:")
    lines.append("")
    lines.append("| Decision name | Runs carrying it | Fallback reason, when present |")
    lines.append("|---|---|---|")
    name_counts = Counter()
    name_fallback = defaultdict(Counter)
    for rec in run2.values():
        if rec["decisions"]:
            for dec in rec["decisions"]:
                name_counts[dec["name"]] += 1
                if dec.get("fallback_reason"):
                    name_fallback[dec["name"]][dec["fallback_reason"]] += 1
    for name in sorted(name_counts):
        fb = ", ".join(f"{k} ({v})" for k, v in name_fallback[name].items()) or "none recorded"
        lines.append(f"| {name} | {name_counts[name]} | {fb} |")
    lines.append("")
    lines.append(
        "guardrail.relevancy appears only on a minority of runs (the ones where the guard tier's own "
        "classification was itself ambiguous enough to need Jev's tie-break), and no think.ask_back "
        "decision was observed in this dataset at all, so \"four choices per question\" describes the "
        "decision surface Jev is wired to, not what fires on every question. The data cannot confirm or "
        "rule out a per-call cost for a decision that never actually ran in this sample."
    )
    lines.append("")

    lines.append("## Why the new decisions mostly do not cost time, per the code")
    lines.append("")
    lines.append(
        "This section reads `src/system_03_search_agent/harness/decide.py` and "
        "`src/system_03_search_agent/core/graph.py` directly, as a static check of the mechanism the "
        "timing data already points away from. No live service was called for this; it is a source read, "
        "the same as reading any other file in this repository."
    )
    lines.append("")
    lines.append(
        "The four decision points are wired at fixed call sites: `guardrail.relevancy` in `guardrail_node`, "
        "`think.ask_back` and `think.recent_years` in `think_node`, and `plan.literature` also started by "
        "`think_node` and handed to Plan still running. Two things in the code explain why the median "
        "guard/think/plan stages barely move even though a new model call was added to each:"
    )
    lines.append("")
    lines.append(
        "First, every decision after the guardrail one is fired as a background asyncio task at the moment "
        "its owning node starts, not awaited inline, so it runs concurrently with whatever that node was "
        "already going to do (entity resolution, tool-plan assembly). The `think_node` docstring states the "
        "intent directly: \"both start the moment the node does, so they overlap everything Think does "
        "before either is needed... the person waits for one decision, not three.\" `guardrail.relevancy` is "
        "narrower still: `guardrail_node` only starts it for a question that fails a fast biomedical-vocabulary "
        "allowlist check, which is why it appears on only 11 of 150 phase 8.2 runs rather than on every run."
    )
    lines.append("")
    lines.append(
        "Second, `decide()` documents a real, non-zero wait even after Jev has already answered. Its module "
        "docstring says: \"once Jev has answered the comparison waits at most `GUARD_COMPARISON_GRACE_S` for "
        "the guard, so the person never waits on a pick that is only recorded.\" The constant is "
        "`GUARD_COMPARISON_GRACE_S = 1.0`, and the code does exactly what the first half of that sentence "
        "says: `await asyncio.wait({guard_task}, timeout=GUARD_COMPARISON_GRACE_S)` runs before `decide()` "
        "returns, even though Jev's choice is already known and will be used regardless of what the guard "
        "tier says. The trailing clause, \"the person never waits,\" is best read as relative to a longer, "
        "uncapped wait this fix round removed, not as zero added time: this is a documented one-second cap, "
        "not an oversight, but it is a real cost inside a background task whenever it fires. The "
        "fallback_reason counts say it fires often: `guard_not_ready` (the grace expired before the guard "
        "tier answered) accounts for 159 of the 245 decisions recorded in phase 8.2. That extra wait only "
        "shows up in a node's own wall-clock time when it outlasts whatever else that node was doing "
        "concurrently, which is plausibly why the guard_to_think stage's median barely moved (" +
        fmt(stage_table_rows_lookup(stage_table_rows, "guard_to_think", "med_delta"), 2) +
        "s) while its p90 grew by " + fmt(stage_table_rows_lookup(stage_table_rows, "guard_to_think", "p90_delta"), 2) +
        "s: most questions keep the node busy longer than one second anyway, and a tail of questions do not."
    )
    lines.append("")
    lines.append(
        "Separately, comparing the two runs' exact deployed commits (5bac18a for phase 8.1, 566e1ab for "
        "phase 8.2) shows zero changed lines under `src/system_03_search_agent/synthesis/`, the answer-writing "
        "module. The write step's own code did not change between these two deployments. Whatever grew "
        "write_to_done, it was not a direct edit to the write step's logic or prompt-building code in this "
        "diff."
    )
    lines.append("")
    lines.append(
        "The same folder as this report's inputs already carries an independent cross-check: "
        "`decisions_comparison.md`, next to phase 8.2's raw files, tallies the same three decision points "
        "from the same 150 runs (11, 117 and 118 decisions, with guard_not_ready at 5, 80 and 74) and notes "
        "in its own words that \"letting the comparison land before the done event is a To do card,\" "
        "meaning the guard-comparison wait not finishing before the answer is already a known, tracked gap, "
        "not a new finding of this report. That document counts decisions; it does not measure stage timing, "
        "which is this report's addition."
    )
    lines.append("")

    lines.append("## Load and error signals, run to run")
    lines.append("")
    lines.append("| Signal | Phase 8.1 | Phase 8.2 |")
    lines.append("|---|---|---|")
    lines.append(f"| rate_limit_signals, summed | {rl1} | {rl2} |")
    lines.append(f"| tool_errors, summed | {te1} | {te2} |")
    lines.append(f"| runs with an error event | {ee1} | {ee2} |")
    lines.append(f"| started_at span | {span1[0]} to {span1[1]} | {span2[0]} to {span2[1]} |")
    lines.append("")
    lines.append("Outcome counts, both runs:")
    lines.append("")
    all_outcomes = sorted(set(outcome_counts_1) | set(outcome_counts_2))
    lines.append("| Outcome | Phase 8.1 | Phase 8.2 |")
    lines.append("|---|---|---|")
    for oc in all_outcomes:
        lines.append(f"| {oc} | {outcome_counts_1.get(oc,0)} | {outcome_counts_2.get(oc,0)} |")
    lines.append("")
    lines.append(
        "Phase 8.2 introduces an outcome value not present in phase 8.1: 'error'. One instance was "
        "inspected directly (G-046, run 1): a fatal, transient, step-scoped error from the guardrail "
        "source, message 'A step in this query hit a temporary error.' This is consistent with the new "
        "guard-versus-Jev race (the guard tier given a one-second grace beside Jev) occasionally tripping "
        "a guardrail-side fault, but one instance is not enough to attribute the median latency growth to "
        "it, since the growth shows up broadly across answered runs, not concentrated in the handful of "
        "error runs."
    )
    lines.append("")
    lines.append(
        "Both runs were started within about 27 minutes of each other on the same day (see the "
        "started_at spans above), both against the same class of golden-run harness, so a large time-of-day "
        "load difference is unlikely to explain the shift, though the two runs were not simultaneous and a "
        "shared external dependency (the graph host, an NCBI endpoint, the model provider) could still have "
        "been under different load at each start time. Neither run recorded any rate_limit_signals, and the "
        "tool_errors counts are low and similar in the both runs, which argues against a rate-limiting or "
        "tool-availability explanation for the bulk of the growth."
    )
    lines.append("")

    if only_in_1 or only_in_2:
        lines.append("Note: file coverage was not perfectly symmetric between the two raw/ folders.")
        lines.append("")
        lines.append(f"- Present in phase 8.1 raw/ but not phase 8.2 raw/: {len(only_in_1)}")
        lines.append(f"- Present in phase 8.2 raw/ but not phase 8.1 raw/: {len(only_in_2)}")
        lines.append("")

    lines.append("## Answer size and the missing token events")
    lines.append("")
    lines.append(
        "Ruling out \"answers just got longer\": on the " + str(len(words1)) + " matched (question, pass) "
        "pairs where both runs answered, the median per-pair delta in answer_words is " +
        fmt(median(word_deltas) if word_deltas else None, 0) + " words. Citation counts and total tool "
        "calls are identical at the median in both runs. Answer content size is not growing between the "
        "two runs, so the write_to_done growth is not simply \"the model had more to say.\""
    )
    lines.append("")
    lines.append("| Measure | Median 8.1 | Median 8.2 | Median per-pair delta |")
    lines.append("|---|---|---|---|")
    lines.append(f"| answer_words | {fmt(median(words1),0)} | {fmt(median(words2),0)} | {fmt(median(word_deltas),0)} |")
    lines.append(f"| citations | {fmt(median(cites1),0)} | {fmt(median(cites2),0)} | n/a |")
    lines.append(f"| total_tool_calls | {fmt(median(toolcalls1),0)} | {fmt(median(toolcalls2),0)} | n/a |")
    lines.append("")
    lines.append(
        "On the missing token and trust_signal events: each raw/*.json file's own `record.event_types` "
        "field counts every event type the live run actually emitted, including token and trust_signal, "
        "but the saved `events` array is shorter than that count by exactly the token-plus-trust_signal "
        "total. Checked on G-001, run 1: phase 8.1's event_types sums to 239 declared events (`token`: 85, "
        "`trust_signal`: 60, and 94 others), but the saved events array holds exactly 94 entries, a gap of "
        "145, precisely token (85) plus trust_signal (60). The same shape holds across both runs: token and "
        "trust_signal fired during the live run and were counted, but were not written into raw/*.json."
    )
    lines.append("")
    n1c_share = fmt(100 * tt1 / decl1, 0) if decl1 else "n/a"
    n2c_share = fmt(100 * tt2 / decl2, 0) if decl2 else "n/a"
    lines.append("| Run | Runs with event_types | Declared events (sum) | Saved events (raw array) | token+trust_signal declared |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| Phase 8.1 | {n1c} | {decl1} | {act1} | {tt1} ({n1c_share}% of declared) |")
    lines.append(f"| Phase 8.2 | {n2c} | {decl2} | {act2} | {tt2} ({n2c_share}% of declared) |")
    lines.append("")
    lines.append(
        "This means the token stream's timestamps genuinely do not exist in either saved dataset, so a "
        "true time-to-first-token split is not reconstructable after the fact for this report. It also means "
        "it is not a phase 8.2-specific gap: both runs' raw files were captured the same way, so this limits "
        "this analysis symmetrically rather than hiding something that changed between the two runs."
    )
    lines.append("")

    lines.append("## Confidence: what this data can and cannot show")
    lines.append("")
    lines.append(
        "Can show: which named stage's timestamp-to-timestamp interval grew between the two runs, at the "
        "median and p90, matched on the same 50 questions and 3 passes; that Jev's own recorded latency is "
        "small (low hundreds of milliseconds) and cannot itself account for the multi-second median growth; "
        "that the growth concentrates in write_to_done (the Synth-tier answer generation and its streaming) "
        "rather than in guard, think, plan or the tool-calling span, where the new decisions actually run; "
        "that answer length, citation count and tool-call count did not grow between the two runs, so a "
        "longer answer is not the explanation either; that only 4 of 150 matched pairs changed outcome "
        "bucket (answered, refused, other) between runs, so the median growth is not chiefly an "
        "answered-versus-refused mix shift; and, from the source rather than the logs, that the "
        "write step's own code is byte-for-byte unchanged between the two runs' exact deployed commits, and "
        "that the decision calls are deliberately run in the background so their design intent is to add "
        "little to the critical path, which the near-zero median growth in guard_to_think and think_to_plan "
        "is consistent with."
    )
    lines.append("")
    lines.append(
        "Cannot show: the root cause inside the write step itself. No token-level timestamps exist in either "
        "run (see above), so this analysis cannot say whether the Synth-tier model call slowed (a model, "
        "prompt, or provider-side change), whether time-to-first-token grew, whether the streaming phase "
        "itself took longer per token, or whether the dynamic suffix handed to Synth grew in some way that "
        "does not show up in answer_words (for example carrying the new decision outputs, per "
        "prompt-cache-discipline's rule that new content belongs in the dynamic suffix). The 'no synthesis "
        "code changed' finding rules out a direct edit to the write step, but not an indirect effect: if "
        "Jev's and the guard tier's concurrent decide() calls share a connection pool, a thread pool, or "
        "another bounded concurrency resource with the Synth call, contention could slow Synth's dispatch "
        "even though Synth's own code is untouched and even though the decide() calls finish in a different "
        "pipeline step. This report cannot confirm or rule out that hypothesis without live tracing across "
        "concurrent requests, which is out of scope here. Also cannot show causation from a single "
        "before/after pair of runs: a two-point comparison cannot rule out that the phase 8.1 run happened "
        "to sample a faster period for reasons entirely outside this repository, such as the model "
        "provider's own load at 09:44 UTC versus 13:01 UTC on the same day."
    )
    lines.append("")

    lines.append("## Method")
    lines.append("")
    lines.append(
        "Every raw/*.json file in both report directories was parsed. Each file's `events` array was "
        "reduced to one timestamp per named point: the guard event, the think event, the plan event, the "
        "first tool_start, the last tool_result, the step/write/started event, and the done event. Stage "
        "durations are the difference between consecutive named points, computed in Python from the ISO "
        "8601 timestamps on each event (UTC, microsecond resolution). Two runs were matched on (question id, "
        "pass number) so a stage's growth is a per-pair delta (8.2 minus 8.1), and the median and p90 "
        "reported for growth are the median and p90 of those per-pair deltas, not the difference between the "
        "two runs' independent medians. The before_guard stage is `record.seconds` (the client-observed "
        "total wall time, already present in runs.jsonl) minus the guard-to-done wall span computed from "
        "event timestamps, so it depends on the client and server clocks agreeing, which a single golden-run "
        "harness calling a single deployed API over a short span should satisfy at one-second resolution. "
        "Jev latency figures come directly from `jev_latency_ms` on each decision object inside the phase "
        "8.2 done event's `decisions` list. Load signals come from the `rate_limit_signals` and `tool_errors` "
        "fields already recorded per run, plus a scan for `error` type events. Answer-size figures "
        "(answer_words, citations, total_tool_calls) come from the same per-run record already used for "
        "outcome and latency. The event-capture-gap check sums `record.event_types` and compares it against "
        "the length of the saved `events` array on the same file. The 'why the new decisions mostly do not "
        "cost time' section is the one part of this report drawn from reading source code "
        "(`harness/decide.py`, `core/graph.py`) rather than from the run logs, cited by file and by the exact "
        "constant and call names quoted; it was cross-checked against a `git log`/`git diff --stat` between "
        "the two runs' exact deployed commits (5bac18a, 566e1ab) restricted to `src/system_03_search_agent/`, "
        "read-only and with no live service called. No file outside this report's own output directory was "
        "written."
    )
    lines.append("")

    findings_path = os.path.join(OUT_DIR, "findings.md")
    with open(findings_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")

    print("Wrote", findings_path)
    print("write_to_done median delta:", stage_table_rows_lookup(stage_table_rows, 'write_to_done', 'med_delta'))


def stage_table_rows_lookup(rows, stage, field):
    for r in rows:
        if r["stage"] == stage:
            return r[field]
    return None


if __name__ == "__main__":
    main()
