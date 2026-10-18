"""Writer bench 3 driver: runs (model, question, run) triples through run_one.py.

The OpenRouter account's own figures are the meter, since they are what the
owner pays (the lead's decision of 2026-09-26). They are re-read from
/api/v1/credits before every run, because develop and other agents spend
from the same account. Three stops, whichever comes first:

- The account's total usage has grown by --budget dollars since
  --usage-start, the total usage read when the bench began. Usage only
  grows, so a top-up does not reset it, and it counts everyone's spend on
  the account, which errs toward stopping early.
- The account's remaining balance would fall to --floor dollars or below.
- A pause file exists (--pause-file): the driver waits, sending nothing,
  until it is removed. This is how a golden run on develop gets the
  provider's rate limits to itself.

Each check adds the next run's estimated cost first. The estimates come
from the probes, as the larger of the product's metered cost (which bills
cached tokens at full price and a call cut at the budget at its full
4,000-token ceiling) and OpenRouter's reported cost (which can be higher
when it routes to a dearer provider, as on the glm-5.2 probe).

A run whose raw file already exists is skipped, so a stopped batch resumes.
The product key is read from the repository's .env and never printed.

Usage:
    driver.py --models m1,m2 --questions G-001,G-002 --runs 1
              --usage-start 64.06 [--budget 27] [--floor 9]
              [--concurrency 1] [--pause-file PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RESULTS = HERE / "results.jsonl"

# Estimated cost per question, in dollars, used only to decide whether the
# next run could cross the floor. Set from the one-question probes; a model
# missing here gets the conservative default.
# The probe cost (the larger of metered and OpenRouter-reported) times about
# 1.5, since a longer question sends a longer prompt.
ESTIMATE_USD = {
    "z-ai/glm-5.2": 0.04,
    "moonshotai/kimi-k2.5": 0.03,
    "anthropic/claude-sonnet-5": 0.16,
    "anthropic/claude-opus-5.5": 0.37,
    "google/gemini-3.1-pro-preview": 0.18,
    "google/gemini-3.8-flash": 0.06,
    "openai/gpt-6-astra": 0.50,
}
DEFAULT_ESTIMATE_USD = 0.60


def product_key() -> str:
    name = "OPENROUTER" + "_API_KEY"
    for line in (REPO / ".env").read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("the product key is not set in .env")


def credits() -> tuple[float, float]:
    """The account's (total credits, total usage), in dollars."""
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/credits",
        headers={"Authorization": "Bearer " + product_key()},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)["data"]
    return float(data["total_credits"]), float(data["total_usage"])


def bench_spend() -> float:
    if not RESULTS.exists():
        return 0.0
    total = 0.0
    for line in RESULTS.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            metered = float(row.get("done_cost_usd") or row.get("metered_cost_usd") or 0.0)
            total += max(metered, float(row.get("openrouter_cost_usd") or 0.0))
    return total


def raw_path(model: str, qid: str, run: int) -> Path:
    return HERE / "raw" / f"{model.replace('/', '_')}__{qid}__r{run}.json"


class Stop(Exception):
    pass


def gate(model: str, args) -> None:
    pause = Path(args.pause_file) if args.pause_file else None
    while pause is not None and pause.exists():
        print("[PAUSED] pause file present, sending nothing", flush=True)
        time.sleep(20)
    total, used = credits()
    left = total - used
    grown = used - args.usage_start
    estimate = ESTIMATE_USD.get(model.partition("+effort-")[0], DEFAULT_ESTIMATE_USD)
    print(
        f"[GATE] account remaining ${left:.2f}, usage grown ${grown:.2f} since the start, "
        f"bench meter ${bench_spend():.4f}, next {model} est ${estimate:.2f}",
        flush=True,
    )
    if grown + estimate >= args.budget:
        raise Stop(f"usage grown ${grown:.2f} plus the ${estimate:.2f} estimate would reach the ${args.budget:.2f} budget")
    if left - estimate <= args.floor:
        raise Stop(f"account remaining ${left:.2f} less the ${estimate:.2f} estimate would reach the ${args.floor:.2f} floor")


def run_one(model: str, qid: str, run: int, env: dict) -> str:
    proc = subprocess.run(
        [sys.executable, str(HERE / "run_one.py"), model, qid, str(run)],
        cwd=str(HERE),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=900,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("[DONE]")]
    if lines:
        return lines[-1]
    return f"[FAIL] {model} {qid} r{run} rc={proc.returncode} {proc.stderr[-600:]}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", required=True)
    parser.add_argument("--questions", required=True)
    parser.add_argument("--runs", default="1")
    parser.add_argument("--floor", type=float, default=9.0)
    parser.add_argument("--usage-start", type=float, required=True)
    parser.add_argument("--budget", type=float, default=27.0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--pause-file", default=None)
    args = parser.parse_args()


    env = dict(os.environ)
    tree = env.get("BENCH_TREE")
    if tree:
        commit = subprocess.run(
            ["git", "-C", tree, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
        ).stdout.strip()
        env["BENCH_TREE_COMMIT"] = commit
    models = [m for m in args.models.split(",") if m]
    questions = [q for q in args.questions.split(",") if q]
    runs = [int(r) for r in args.runs.split(",") if r]
    # Question-major order: every model meets a question within minutes of
    # the others, so live tool conditions are as alike as they can be.
    plan = [(m, q, r) for r in runs for q in questions for m in models if not raw_path(m, q, r).exists()]
    print(f"[PLAN] {len(plan)} runs to do", flush=True)
    try:
        if args.concurrency <= 1:
            for model, qid, run in plan:
                gate(model, args)
                print(run_one(model, qid, run, env), flush=True)
        else:
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                pending = []
                for model, qid, run in plan:
                    while len([p for p in pending if not p.done()]) >= args.concurrency:
                        time.sleep(1)
                    for p in [p for p in pending if p.done()]:
                        print(p.result(), flush=True)
                        pending.remove(p)
                    gate(model, args)
                    pending.append(pool.submit(run_one, model, qid, run, env))
                for p in pending:
                    print(p.result(), flush=True)
    except Stop as stop:
        print(f"[STOP] {stop}", flush=True)
    print(f"[END] bench spend ${bench_spend():.4f}", flush=True)


if __name__ == "__main__":
    main()
