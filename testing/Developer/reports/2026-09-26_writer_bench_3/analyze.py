"""Writer bench 3 analysis: per-model measures for one stage, as markdown.

Reads results.jsonl and raw/*.json in this folder. Writes nothing but
stdout, so a table in results.md is pasted from this script's output.

Usage:
    analyze.py <runs> [models]
      runs:   comma-separated run indexes, e.g. "0" for the probes, "1" for
              stage 1, "1,2,3" for stage 2's three runs
      models: optional comma-separated model ids, default every model

Definitions, stated so a reader can check them:
- answered: the golden consistency run's own rule (at least one citation
  and a trust outcome other than refuse)
- withdrawn: an answered run whose answer carries the structured-fallback
  note, "could not be verified against them"
- prose kept: sentences of the writer's own reply that survived grounding
  in the draft that shipped (0 on a withdrawn run), counting only sentences
  of four or more words once citation markers are removed, so a heading the
  pass keeps as "KRAS [1]." is not counted as prose
- first sentence answers: read by hand, from grades.json, where present
- writer seconds: `LLMResponse.elapsed_s` of every writer call that
  returned; output tokens per second divides that call's completion tokens
  (reasoning tokens included, which is what the reader waits for) by it
- repair fired: a second writer call was sent, whether or not it returned
- write step: seconds from the write step event to the done event
- cost: the product's metered cost per question (the `cost` event, which
  bills cached tokens at the full input price and a timed-out call at its
  full output ceiling, so it reads high) and OpenRouter's reported cost
  for the same calls (which applies its cache discounts; Jev is not in it)
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def med(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def fmt(value, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def load(runs: set[int], models: set[str] | None) -> list[dict]:
    rows = []
    for line in (HERE / "results.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["run"] not in runs or (models and row["model"] not in models):
            continue
        raw = HERE / "raw" / f"{row['model'].replace('/', '_')}__{row['question_id']}__r{row['run']}.json"
        detail = json.loads(raw.read_text()) if raw.exists() else {}
        events = detail.get("events") or []
        write_t = next((e["emitted"] for e in events if e["type"] == "step" and e.get("step") == "write"), None)
        done_t = next((e["emitted"] for e in events if e["type"] == "done"), None)
        row["write_step_s"] = None if write_t is None or done_t is None else round(done_t - write_t, 3)
        rec = detail.get("rec") or {}
        row["_writer_calls"] = [c for c in rec.get("call_tier", []) if c["tier"] == "synth"]
        llm = [c for c in rec.get("llm", []) if c.get("synth")]
        row["cut_at_ceiling"] = sum(1 for c in llm if c.get("finish") == "length")
        row["reasoning_retries"] = sum(1 for c in llm if not c.get("ok") and "mandatory" in (c.get("message") or ""))
        # Prose kept, counted as whole sentences: a heading the pass keeps as
        # "KRAS [1]." is not a sentence a reader reads as prose.
        grounds = rec.get("grounding") or []
        shipped = row.get("shipped_draft")
        sentences = [] if row["withdrawn"] or shipped is None else grounds[shipped]["sentences"]
        row["kept"] = [s for s in sentences if len(re.sub(r"\[\d+\]", "", s).split()) >= 4]
        rows.append(row)
    return rows


def grades() -> dict:
    path = HERE / "grades.json"
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    runs = {int(r) for r in sys.argv[1].split(",")}
    models = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    rows = load(runs, models)
    graded = grades()
    by_model: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_model[row["model"]].append(row)

    print("| Model | Runs | Answered | Withdrawn of answered | Prose sentences kept, total | Mean kept per answered run "
          "| Runs keeping any prose | First sentence answers | Jev sent / approved | Repair fired | Repair returned "
          "| Must-cite hits |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for model, group in sorted(by_model.items()):
        answered = [r for r in group if r["outcome"] == "answered"]
        withdrawn = [r for r in answered if r["withdrawn"]]
        kept = sum(len(r["kept"]) for r in answered)
        with_prose = sum(1 for r in answered if r["kept"])
        keys = [f"{r['model']}|{r['question_id']}|{r['run']}" for r in answered if r["kept"]]
        yes = sum(1 for k in keys if graded.get(k) == "yes")
        read = sum(1 for k in keys if k in graded)
        fired = [r for r in group if r["repair_fired"]]
        returned = sum(1 for r in fired if r["writer_calls_ok"] >= 2)
        hits = sum(r["must_cite_hits"] for r in group)
        total = sum(r["must_cite_total"] for r in group)
        first = f"{yes} of {read} read" if read else "not read"
        print(
            f"| {model} | {len(group)} | {len(answered)} | {len(withdrawn)} | {kept} | "
            f"{fmt(kept / len(answered) if answered else None, 2)} | {with_prose} | {first} | "
            f"{sum(r['jev_sent'] for r in group)} / {sum(r['jev_approved'] for r in group)} | "
            f"{len(fired)} of {len(group)} | {returned} of {len(fired)} | {hits} of {total} |"
        )
    print()
    print("| Model | Writer calls returned | Writer s per call, median | p90 | First reply s, median | Output tokens, median "
          "| Tokens per s, median | Reasoning tokens, median | Write step s, median | Whole question s, median | p90 "
          "| Replies cut at the ceiling | Reasoning-block refusals | Metered $ per question | OpenRouter $ per question "
          "| Writer share of OpenRouter $ |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for model, group in sorted(by_model.items()):
        elapsed, first_s, tokens, rates, reasoning = [], [], [], [], []
        for r in group:
            for i, c in enumerate(r["_writer_calls"]):
                if not c.get("ok"):
                    continue
                elapsed.append(c["elapsed_s"])
                tokens.append(c["completion_tokens"])
                if c["elapsed_s"]:
                    rates.append(c["completion_tokens"] / c["elapsed_s"])
                if i == 0:
                    first_s.append(c["elapsed_s"])
            reasoning.extend(t for t in r.get("writer_reasoning_tokens") or [] if t is not None)
        write_s = [r["write_step_s"] for r in group if r["write_step_s"] is not None]
        whole = [r["done_elapsed_s"] for r in group if r["done_elapsed_s"]]
        metered = [float(r.get("done_cost_usd") or r["metered_cost_usd"] or 0) for r in group]
        billed = [float(r["openrouter_cost_usd"] or 0) for r in group]
        writer_billed = [float(r["writer_openrouter_cost_usd"] or 0) for r in group]
        share = sum(writer_billed) / sum(billed) if sum(billed) else None
        print(
            f"| {model} | {len(elapsed)} | {fmt(med(elapsed))} | {fmt(pct(elapsed, 0.9))} | {fmt(med(first_s))} | "
            f"{fmt(med(tokens), 0)} | {fmt(med(rates), 0)} | {fmt(med(reasoning), 0)} | {fmt(med(write_s))} | "
            f"{fmt(med(whole))} | {fmt(pct(whole, 0.9))} | {sum(r['cut_at_ceiling'] for r in group)} | "
            f"{sum(r['reasoning_retries'] for r in group)} | {fmt(statistics.mean(metered) if metered else None, 4)} | "
            f"{fmt(statistics.mean(billed) if billed else None, 4)} | {fmt(share * 100 if share else None, 0)}% |"
        )
    print()
    total_metered = sum(float(r.get("done_cost_usd") or r["metered_cost_usd"] or 0) for r in rows)
    total_billed = sum(float(r["openrouter_cost_usd"] or 0) for r in rows)
    print(f"Runs: {len(rows)}. Metered spend: ${total_metered:.4f}. OpenRouter-reported spend: ${total_billed:.4f}.")


if __name__ == "__main__":
    main()
