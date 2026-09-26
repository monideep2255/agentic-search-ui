"""Summarize a consistency run's runs.jsonl into summary.md.

Reads <dir>/runs.jsonl, written by run_consistency.py (one JSON record per
run), joins it against eval/golden/golden_dataset.json for expected_outcome
and acceptable_outcomes, and writes <dir>/summary.md. Deterministic: the
same runs.jsonl always produces byte-identical output, since nothing in this
script reads the wall clock or iterates an unordered collection without
sorting first.

Usage:
    python3 summarize.py <dir> [<baseline_runs_jsonl>]

<dir> must contain runs.jsonl. summary.md is written into <dir>. The
baseline path defaults to the sibling 2026-09-12_consistency_baseline
report's runs.jsonl.

A failed-run record (outcome transport_error or http_<code>) carries only
the header fields plus stage, exception and seconds: no citations, no
tools, no done-derived fields. Every accessor below tolerates that shape
with .get(...) and an explicit default, never a bare key lookup.

Build phase 8.6, T-8.6-09: the summary also reports the run's UTC start
time and the time to the first word, read from each record's
`first_word_s` (client clock, from submitting the question to the first
answer word arriving; see run_consistency.py). Both are additions: every
line the summary wrote before is written exactly as before, and a
runs.jsonl recorded before the field existed reports it as not recorded.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GOLDEN_PATH = SCRIPT_DIR.parents[3] / "eval" / "golden" / "golden_dataset.json"
DEFAULT_BASELINE = (
    SCRIPT_DIR.parent / "2026-09-12_consistency_baseline" / "runs.jsonl"
)

CATEGORY_ORDER = ["kiss", "kisses", "discovery"]

OUTCOME_MEANING_FIXED = {
    "answered": "at least one citation with a non-refuse trust outcome",
    "refused_no_evidence": "a completed run with zero citations",
    "capped": "a daily-cap decline",
    "timeout": "the client giving up on a stream",
    "error": "a fatal error event",
    "transport_error": "the client failing to reach the API at all",
}

TOC = [
    ("Summary", "summary"),
    ("Outcome by category", "outcome-by-category"),
    ("Outcome by query class", "outcome-by-query-class"),
    ("Expected versus observed", "expected-versus-observed"),
    ("Per question", "per-question"),
    ("Stability", "stability"),
    ("Latency", "latency"),
    ("L-01, graph rows vanishing", "l-01-graph-rows-vanishing"),
    ("Rate-limit contamination check", "rate-limit-contamination-check"),
    ("Comparison with the 2026-09-12 baseline", "comparison-with-the-2026-09-12-baseline"),
    ("Method", "method"),
]


def load_jsonl(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        return records
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def load_golden() -> dict[str, dict]:
    data = json.loads(GOLDEN_PATH.read_text())
    return {row["id"]: row for row in data["queries"]}


def outcome_bucket(outcome: str) -> str:
    """Fold every observed outcome label into one of four report buckets.

    answered and refused_no_evidence are their own buckets. Every other
    refused_* label (the guardrail, and refused_with_sources) buckets as
    refused. Everything else, error, timeout, transport_error, http_<code>,
    capped, no_done, and any future label this script has not seen, buckets
    as error_timeout_transport, so the four bucket counts always sum to the
    row's run count with nothing silently dropped.
    """
    if outcome == "answered":
        return "answered"
    if outcome == "refused_no_evidence":
        return "refused_no_evidence"
    if outcome.startswith("refused_"):
        return "refused"
    return "error_timeout_transport"


def outcome_meaning(outcome: str) -> str:
    if outcome in OUTCOME_MEANING_FIXED:
        return OUTCOME_MEANING_FIXED[outcome]
    if outcome == "refused_offtopic" or (
        outcome.startswith("refused_") and outcome != "refused_with_sources"
    ):
        return "the guardrail refused it (off-topic or another guard category)"
    if outcome == "refused_with_sources":
        return (
            "not named in the client's docstring; from classify() this is a "
            "completed run that returned citations but whose trust_outcome "
            "was refuse"
        )
    if outcome == "no_done":
        return (
            "not named in the client's docstring; from classify() this is a "
            "completed stream with no done event"
        )
    if outcome.startswith("http_"):
        return (
            "not named in the client's docstring; from run_once() this is "
            "an HTTP error status returned while creating or streaming the run"
        )
    return "not named in the client's docstring and not otherwise recognized by this script"


def pct(n: int, d: int) -> str:
    if d == 0:
        return "0%"
    return f"{round(100 * n / d)}%"


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, math.ceil(p * len(ordered)) - 1)
    idx = min(idx, len(ordered) - 1)
    return ordered[idx]


def fmt_seconds(values: list[float]) -> str:
    return f"{round(statistics.median(values), 1)} / {round(percentile(values, 0.9), 1)} / {round(max(values), 1)}"


def first_word_seconds(runs: list[dict]) -> list[float]:
    """Every recorded time to the first word, in seconds (T-8.6-09).

    A run with no first word (a refusal, an error, a timeout) or recorded
    before the field existed has none, and is left out rather than counted
    as zero.
    """
    values = []
    for r in runs:
        value = r.get("first_word_s")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return values


def first_word_summary(runs: list[dict]) -> str:
    values = first_word_seconds(runs)
    if not values:
        return "not recorded: no run in this file carries first_word_s"
    return f"{round(statistics.median(values), 1)} seconds, over {len(values)} of {len(runs)} runs"


def run_start_utc(runs: list[dict]) -> str:
    """The earliest started_at, written as a UTC time (T-8.6-09)."""
    starts = sorted(r.get("started_at") for r in runs if r.get("started_at"))
    if not starts:
        return "n/a"
    first = starts[0]
    try:
        moment = datetime.fromisoformat(first)
    except ValueError:
        return first
    if moment.tzinfo is None:
        return f"{first} (no time zone recorded)"
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def esc(text: str | None) -> str:
    if text is None:
        return ""
    return text.replace("|", "/").replace("\n", " ")


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def section1_summary(runs: list[dict]) -> str:
    ids = sorted({r["id"] for r in runs})
    by_id: dict[str, list[dict]] = {i: [] for i in ids}
    for r in runs:
        by_id[r["id"]].append(r)

    answered_every_time = 0
    answered_some = 0
    never_answered = 0
    for i in ids:
        outcomes = [r.get("outcome") for r in by_id[i]]
        n_answered = sum(1 for o in outcomes if o == "answered")
        if n_answered == 0:
            never_answered += 1
        elif n_answered == len(outcomes):
            answered_every_time += 1
        else:
            answered_some += 1

    outcome_counts: dict[str, int] = {}
    for r in runs:
        o = r.get("outcome", "unknown")
        outcome_counts[o] = outcome_counts.get(o, 0) + 1

    total_rate_limit = sum(r.get("rate_limit_signals", 0) or 0 for r in runs)
    runs_with_tool_error = sum(1 for r in runs if r.get("tool_errors"))

    commits = sorted({r.get("deployed_commit") for r in runs if r.get("deployed_commit")})
    commit_str = ", ".join(commits) if commits else "unknown"

    starts = sorted(r.get("started_at") for r in runs if r.get("started_at"))
    first_start = starts[0] if starts else "n/a"
    last_start = starts[-1] if starts else "n/a"

    rows = [
        ["Questions run", str(len(ids))],
        ["Searches run", str(len(runs))],
        ["Answered every time", str(answered_every_time)],
        ["Answered some of the time", str(answered_some)],
        ["Never answered", str(never_answered)],
    ]
    for label in sorted(outcome_counts):
        rows.append([f"Outcome: {label}", str(outcome_counts[label])])
    rows.append(["Total rate-limit signals", str(total_rate_limit)])
    rows.append(["Runs with a tool error", str(runs_with_tool_error)])
    rows.append(["Deployed commit", commit_str])
    rows.append(["First started_at", first_start])
    rows.append(["Last started_at", last_start])
    rows.append(["Run started (UTC)", run_start_utc(runs)])
    rows.append(["Median time to the first word", first_word_summary(runs)])

    meaning_lines = []
    for label in sorted(outcome_counts):
        meaning_lines.append(f"{label}: {outcome_meaning(label)}.")

    return (
        "## Summary\n\n"
        + md_table(["Measure", "Value"], rows)
        + "\n\nOutcome meanings, one sentence per label seen in this run, copied "
        "from the client's docstring where the docstring names the label:\n\n"
        + "\n".join(f"- {line}" for line in meaning_lines)
    )


def category_query_class_table(runs: list[dict], key: str, row_labels: list[str]) -> str:
    counts = {label: {"runs": 0, "answered": 0, "refused_no_evidence": 0, "refused": 0, "error_timeout_transport": 0} for label in row_labels}
    for r in runs:
        label = r.get(key, "unknown")
        if label not in counts:
            counts[label] = {"runs": 0, "answered": 0, "refused_no_evidence": 0, "refused": 0, "error_timeout_transport": 0}
        bucket = outcome_bucket(r.get("outcome", ""))
        counts[label]["runs"] += 1
        counts[label][bucket] += 1

    ordered_labels = list(row_labels) + sorted(set(counts) - set(row_labels))
    rows = []
    for label in ordered_labels:
        c = counts[label]
        rows.append(
            [
                label,
                str(c["runs"]),
                str(c["answered"]),
                str(c["refused_no_evidence"]),
                str(c["refused"]),
                str(c["error_timeout_transport"]),
                pct(c["answered"], c["runs"]),
            ]
        )
    return md_table(
        ["Label", "Runs", "Answered", "Refused no evidence", "Refused (guard)", "Error, timeout or transport", "Answered percent"],
        rows,
    )


def section2_by_category(runs: list[dict]) -> str:
    return (
        "## Outcome by category\n\n"
        + category_query_class_table(runs, "category", CATEGORY_ORDER)
        + "\n\nBucketing: answered and refused_no_evidence are their own outcome "
        "labels. Refused (guard) is every other refused_* label. Error, timeout "
        "or transport folds in error, timeout, transport_error, http_<code>, "
        "capped and no_done, so the four count columns always sum to Runs."
    )


def section3_by_query_class(runs: list[dict], golden: dict[str, dict]) -> str:
    query_classes = sorted({row.get("query_class", "unknown") for row in golden.values()})
    return (
        "## Outcome by query class\n\n"
        + category_query_class_table(runs, "query_class", query_classes)
        + "\n\nSame bucketing as outcome by category above. Rows are every "
        "query_class value present in the golden dataset, even one with zero "
        "runs so far."
    )


def section4_expected_vs_observed(runs: list[dict], golden: dict[str, dict]) -> str:
    expected_values = sorted({row.get("expected_outcome", "unknown") for row in golden.values()})
    counts = {e: {"runs": 0, "inside": 0, "outside": 0} for e in expected_values}
    per_id_outside: dict[str, list[bool]] = {}

    for r in runs:
        row = golden.get(r["id"])
        if row is None:
            continue
        expected = row.get("expected_outcome", "unknown")
        acceptable = row.get("acceptable_outcomes") or []
        trust = r.get("trust_outcome")
        inside = trust in acceptable
        counts.setdefault(expected, {"runs": 0, "inside": 0, "outside": 0})
        counts[expected]["runs"] += 1
        counts[expected]["inside" if inside else "outside"] += 1
        per_id_outside.setdefault(r["id"], []).append(not inside)

    rows = []
    for e in sorted(counts):
        c = counts[e]
        rows.append([e, str(c["runs"]), str(c["inside"]), str(c["outside"]), pct(c["inside"], c["runs"])])

    all_outside_ids = sorted(
        i for i, flags in per_id_outside.items() if flags and all(flags)
    )

    out = [
        "## Expected versus observed",
        "",
        md_table(["expected_outcome", "Runs", "Inside acceptable_outcomes", "Outside acceptable_outcomes", "Inside percent"], rows),
        "",
        (
            "Ids where every recorded run's trust_outcome fell outside that id's "
            "acceptable_outcomes:"
        ),
    ]
    if all_outside_ids:
        out.append("")
        out.extend(f"- {i} ({len(per_id_outside[i])} run(s))" for i in all_outside_ids)
    else:
        out.append("")
        out.append("None. Every id had at least one run inside its acceptable_outcomes.")
    return "\n".join(out)


def section5_per_question(runs: list[dict], golden: dict[str, dict]) -> str:
    ids = sorted({r["id"] for r in runs})
    by_id: dict[str, list[dict]] = {i: [] for i in ids}
    for r in runs:
        by_id[r["id"]].append(r)

    rows = []
    for i in ids:
        recs = sorted(by_id[i], key=lambda r: r.get("pass", r.get("run", 0)))
        n = len(recs)
        n_answered = sum(1 for r in recs if r.get("outcome") == "answered")
        outcomes = ", ".join(r.get("outcome", "unknown") for r in recs)
        seconds = ", ".join(str(round(r.get("seconds", 0) or 0)) for r in recs)
        sources = ", ".join(str(r.get("distinct_sources", "-")) for r in recs)
        layers_union: set[str] = set()
        for r in recs:
            layers_union.update(r.get("layers") or [])
        layers_str = ", ".join(sorted(layers_union)) if layers_union else "none"
        l1_segments = []
        for r in recs:
            l1 = r.get("l1_row_counts") or []
            l1_segments.append("+".join(str(x) for x in l1) if l1 else "-")
        l1_str = " / ".join(l1_segments)
        must_segments = []
        for r in recs:
            hits = r.get("must_cite_hits")
            total = r.get("must_cite_total")
            if hits is None or total is None:
                must_segments.append("-")
            else:
                must_segments.append(f"{hits}/{total}")
        must_str = " ".join(must_segments)
        category = recs[0].get("category") or golden.get(i, {}).get("search_category", "unknown")
        question = esc((recs[0].get("question") or golden.get(i, {}).get("question") or "")[:90])
        rows.append([i, category, f"{n_answered} of {n}", outcomes, seconds, sources, layers_str, l1_str, must_str, question])

    return (
        "## Per question\n\n"
        + md_table(
            ["ID", "Category", "Answered", "Outcomes", "Seconds", "Sources", "Layers seen", "L1 rows", "Must-cite", "Question"],
            rows,
        )
    )


def section6_stability(runs: list[dict]) -> str:
    ids = sorted({r["id"] for r in runs})
    by_id: dict[str, list[dict]] = {i: [] for i in ids}
    for r in runs:
        by_id[r["id"]].append(r)

    stable = 0
    unstable_rows = []
    variance_rows = []
    for i in ids:
        recs = sorted(by_id[i], key=lambda r: r.get("pass", r.get("run", 0)))
        outcomes = [r.get("outcome", "unknown") for r in recs]
        if len(set(outcomes)) <= 1:
            stable += 1
        else:
            unstable_rows.append([i, ", ".join(outcomes)])

        answered_sources = [
            r.get("distinct_sources") for r in recs if r.get("outcome") == "answered" and r.get("distinct_sources") is not None
        ]
        if len(answered_sources) >= 2:
            best = max(answered_sources)
            worst = min(answered_sources)
            if best > 0:
                diff_pct = 100 * (best - worst) / best
                if diff_pct > 20:
                    variance_rows.append([i, str(worst), str(best), f"{round(diff_pct)}%"])

    unstable_count = len(unstable_rows)
    out = [
        "## Stability",
        "",
        md_table(
            ["Measure", "Count"],
            [["Questions with identical outcomes across all runs", str(stable)], ["Questions with differing outcomes", str(unstable_count)]],
        ),
        "",
        "Unstable questions:",
        "",
    ]
    if unstable_rows:
        out.append(md_table(["ID", "Outcomes"], unstable_rows))
    else:
        out.append("None.")
    out.extend(
        [
            "",
            (
                "Questions whose distinct_sources count differs by more than 20 "
                "percent between its best and worst answered run (among ids with "
                "2 or more answered runs):"
            ),
            "",
        ]
    )
    if variance_rows:
        out.append(md_table(["ID", "Worst distinct_sources", "Best distinct_sources", "Difference"], variance_rows))
    else:
        out.append("None.")
    return "\n".join(out)


def section7_latency(runs: list[dict]) -> str:
    all_seconds = [r.get("seconds", 0) or 0 for r in runs]
    overall = fmt_seconds(all_seconds) if all_seconds else "n/a"

    by_outcome: dict[str, list[float]] = {}
    for r in runs:
        by_outcome.setdefault(r.get("outcome", "unknown"), []).append(r.get("seconds", 0) or 0)
    outcome_rows = [[label, fmt_seconds(vals)] for label, vals in sorted(by_outcome.items())]

    by_category: dict[str, list[float]] = {}
    for r in runs:
        by_category.setdefault(r.get("category", "unknown"), []).append(r.get("seconds", 0) or 0)
    category_rows = [[label, fmt_seconds(vals)] for label, vals in sorted(by_category.items())]

    over_60 = sorted(
        (r for r in runs if (r.get("seconds", 0) or 0) > 60),
        key=lambda r: (r["id"], r.get("pass", r.get("run", 0))),
    )
    over_60_rows = [
        [r["id"], str(r.get("pass", r.get("run", "-"))), str(round(r.get("seconds", 0) or 0, 1)), r.get("outcome", "unknown")]
        for r in over_60
    ]

    first_words = first_word_seconds(runs)
    first_word_line = (
        "Time to the first word, on the client's clock from submitting the question to the "
        "first answer word arriving: "
        + (
            f"{fmt_seconds(first_words)}, over {len(first_words)} of {len(runs)} runs."
            if first_words
            else "not recorded, no run in this file carries first_word_s."
        )
    )

    out = [
        "## Latency",
        "",
        "Median, p90 and max seconds, formatted as median / p90 / max.",
        "",
        "Overall: " + overall,
        "",
        first_word_line,
        "",
        "By outcome:",
        "",
        md_table(["Outcome", "Median / p90 / max seconds"], outcome_rows) if outcome_rows else "None.",
        "",
        "By category:",
        "",
        md_table(["Category", "Median / p90 / max seconds"], category_rows) if category_rows else "None.",
        "",
        "Runs over 60 seconds:",
        "",
    ]
    out.append(md_table(["ID", "Pass", "Seconds", "Outcome"], over_60_rows) if over_60_rows else "None.")
    return "\n".join(out)


def section8_l01(runs: list[dict]) -> str:
    ids = sorted({r["id"] for r in runs})
    by_id: dict[str, list[dict]] = {i: [] for i in ids}
    for r in runs:
        by_id[r["id"]].append(r)

    l1_questions = []
    empty_calls_count = 0
    inconsistent = []
    identical_count = 0
    for i in ids:
        recs = sorted(by_id[i], key=lambda r: r.get("pass", r.get("run", 0)))
        l1_lists = [r.get("l1_row_counts") or [] for r in recs]
        made_l1_call = any(l1_lists)
        empty_calls_count += sum(1 for r in recs if (r.get("l1_empty_calls") or 0) > 0)
        if not made_l1_call:
            continue
        l1_questions.append([i, " / ".join("+".join(str(x) for x in lst) if lst else "-" for lst in l1_lists)])
        if len({tuple(lst) for lst in l1_lists}) <= 1:
            identical_count += 1
        else:
            inconsistent.append(i)

    out = [
        "## L-01, graph rows vanishing",
        "",
        f"Questions that made at least one Layer 1 call: {len(l1_questions)}.",
        f"Of those, questions with identical Layer 1 row counts across all recorded passes: {identical_count}.",
        f"Runs with l1_empty_calls greater than zero: {empty_calls_count}.",
        "",
        (
            "Layer 1 row counts per question, one segment per pass, each segment "
            "a plus-joined list of call result counts:"
        ),
        "",
    ]
    out.append(md_table(["ID", "L1 rows per pass"], l1_questions) if l1_questions else "None.")
    out.extend(["", "Questions whose Layer 1 row counts are not identical across all recorded passes:", ""])
    if inconsistent:
        out.extend(f"- {i}" for i in sorted(inconsistent))
    else:
        out.append("None.")
    return "\n".join(out)


def section9_rate_limit(runs: list[dict]) -> str:
    total = sum(r.get("rate_limit_signals", 0) or 0 for r in runs)
    error_counts: dict[str, int] = {}
    for r in runs:
        for te in r.get("tool_errors") or []:
            summary = te.get("summary") or ""
            error_counts[summary] = error_counts.get(summary, 0) + 1

    out = ["## Rate-limit contamination check", "", f"Total rate_limit_signals across all runs: {total}."]
    if total == 0:
        out.append(
            "Zero rate-limit signals is the run's own self-check that its "
            "concurrency did not trip the NCBI pool."
        )
    out.extend(["", "Distinct tool_errors summaries and their counts:", ""])
    if error_counts:
        rows = [[esc(summary), str(count)] for summary, count in sorted(error_counts.items())]
        out.append(md_table(["Summary", "Count"], rows))
    else:
        out.append("None.")
    return "\n".join(out)


def section10_baseline(runs: list[dict], baseline_runs: list[dict]) -> str:
    now_by_id: dict[str, int] = {}
    for r in runs:
        now_by_id.setdefault(r["id"], 0)
        if r.get("outcome") == "answered":
            now_by_id[r["id"]] += 1

    old_by_id: dict[str, int] = {}
    for r in baseline_runs:
        old_by_id.setdefault(r["id"], 0)
        if r.get("outcome") == "answered":
            old_by_id[r["id"]] += 1

    all_ids = sorted(set(now_by_id) | set(old_by_id))
    improved = held = worsened = 0
    changed_rows = []
    full_rows = []
    for i in all_ids:
        old = old_by_id.get(i, 0)
        new = now_by_id.get(i, 0)
        full_rows.append([i, str(old), str(new)])
        if new > old:
            improved += 1
            changed_rows.append([i, str(old), str(new), "improved"])
        elif new < old:
            worsened += 1
            changed_rows.append([i, str(old), str(new), "worsened"])
        else:
            held += 1

    out = [
        "## Comparison with the 2026-09-12 baseline",
        "",
        md_table(
            ["Measure", "Count"],
            [
                ["Ids improved (more answered runs now)", str(improved)],
                ["Ids held (same answered count)", str(held)],
                ["Ids worsened (fewer answered runs now)", str(worsened)],
            ],
        ),
        "",
        "Ids whose answered count changed:",
        "",
    ]
    out.append(md_table(["ID", "Answered then (of 3)", "Answered now", "Direction"], changed_rows) if changed_rows else "None.")
    out.extend(["", "Answered count per id, then versus now:", "", md_table(["ID", "Answered then", "Answered now"], full_rows)])
    return "\n".join(out)


def section11_method(argv: list[str]) -> str:
    command = "python3 " + " ".join(argv)
    return (
        "## Method\n\n"
        "Every run signed in before it ran, one of two accounts per worker "
        "thread, so the per-user daily query cap of 100 was never shared "
        "across workers. Concurrency was two, partitioned by question (odd "
        "and even golden ids), never by run, to stay under the E-utilities "
        "queue depth the tool-call budget rule bounds. Each worker asked its "
        "questions in three passes, minutes apart, rather than three "
        "back-to-back tries, and audience_depth was omitted on every call so "
        "it resolved to the account's stored default (researcher for a fresh "
        "account). Every run used a fresh session_id, so no session memory "
        "carried between runs of the same question.\n\n"
        "Command that produced this file:\n\n"
        f"    {command}\n"
    )


def build_summary(runs: list[dict], golden: dict[str, dict], baseline_runs: list[dict], argv: list[str]) -> str:
    intro = (
        "# Consistency run summary\n\n"
        "Item 10.3: every golden question asked three times against the "
        "develop API, two worker threads partitioned by question, three "
        "passes. Generated by summarize.py from runs.jsonl.\n"
    )
    toc = "## Table of contents\n\n" + "\n".join(f"- [{title}](#{anchor})" for title, anchor in TOC) + "\n"

    parts = [
        intro,
        toc,
        section1_summary(runs),
        section2_by_category(runs),
        section3_by_query_class(runs, golden),
        section4_expected_vs_observed(runs, golden),
        section5_per_question(runs, golden),
        section6_stability(runs),
        section7_latency(runs),
        section8_l01(runs),
        section9_rate_limit(runs),
        section10_baseline(runs, baseline_runs),
        section11_method(argv),
    ]
    return "\n\n".join(parts) + "\n"


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: summarize.py <dir> [<baseline_runs_jsonl>]")
    out_dir = Path(sys.argv[1])
    baseline_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BASELINE

    runs = load_jsonl(out_dir / "runs.jsonl")
    golden = load_golden()
    baseline_runs = load_jsonl(baseline_path)

    summary = build_summary(runs, golden, baseline_runs, sys.argv[1:])
    (out_dir / "summary.md").write_text(summary)


if __name__ == "__main__":
    main()
