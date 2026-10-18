"""Sequential driver for the second writer-tier bench, 2026-09-26.

Runs every (model, question) pair one at a time via run_bench.py as a
subprocess, checking cumulative spend after each run and stopping
immediately if total spend passes 3.50 dollars, per the goal contract for
this bench (stop and report, do not keep spending).

Two question sets: PHASE1 is one question per category (5 total), run for
every model first so a spend check can happen before committing to the
full 10. PHASE2 is the remaining 5, run only if the bench runner decides
budget allows it after reading PHASE1's actual spend.

Usage:
    python3 driver.py phase1
    python3 driver.py phase2
    python3 driver.py all      # phase1 then phase2, no pause between
    python3 driver.py phase2 <model_id>   # one model only, for a short
                                           # foreground call per model
"""
import json
import subprocess
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
RESULTS = OUT_DIR / "results.jsonl"
SPEND_CAP = 3.50

MODELS = [
    "z-ai/glm-5.2",
    "moonshotai/kimi-k2.5",
    "anthropic/claude-opus-5.5",
    "openai/gpt-5.6-sol-pro",
]

# One question per category, run first so a spend check can happen before
# the remaining 5.
PHASE1 = [
    ("G-016", "What are the known orthologs of TP53 in other species?"),
    ("G-026", "Which genes are associated with cystic fibrosis?"),
    ("G-024", "What is rs334 and what condition is it associated with?"),
    ("G-019", "What MeSH terms are assigned to PMID 11237011?"),
    ("G-012", "Find clinical trials for carcinoma not otherwise specified."),
]

PHASE2 = [
    ("G-031", "What molecular activity does the KRAS gene product have?"),
    ("G-022", "What phenotypic features are associated with Marfan syndrome?"),
    ("G-023", "Which clinically significant variants have been reported in CFTR?"),
    ("G-021", "Which papers in the graph mention the CFTR gene, and what do they cover?"),
    ("G-030", "What is known about EGFR mutations in non-small cell lung cancer, and what trials are recruiting?"),
]


def total_spend() -> float:
    if not RESULTS.exists():
        return 0.0
    total = 0.0
    for line in RESULTS.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        total += float(row.get("cost_usd") or 0.0)
    return total


def already_run(model: str, qid: str) -> bool:
    if not RESULTS.exists():
        return False
    for line in RESULTS.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("model") == model and row.get("question_id") == qid:
            return True
    return False


def run_questions(questions: list[tuple[str, str]], only_model: str | None = None) -> None:
    models = [only_model] if only_model else MODELS
    for model in models:
        for qid, qtext in questions:
            spend = total_spend()
            if spend >= SPEND_CAP:
                print(f"[STOP] cumulative spend ${spend:.4f} >= cap ${SPEND_CAP:.2f}, stopping early")
                sys.exit(1)
            if already_run(model, qid):
                print(f"[SKIP] {model} / {qid} already has a result")
                continue
            print(f"[RUN] {model} / {qid}")
            proc = subprocess.run(
                [sys.executable, str(OUT_DIR / "run_bench.py"), model, qid, qtext],
                cwd=str(OUT_DIR.parents[3]),
                capture_output=True,
                text=True,
                check=False,
                timeout=600,
            )
            print(proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "[no stdout]")
            if proc.returncode != 0:
                print(f"[WARN] non-zero exit for {model}/{qid}: rc={proc.returncode}")
                print(proc.stderr[-2000:])
    print(f"[FINISHED phase] total spend so far: ${total_spend():.4f}")


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    only_model = sys.argv[2] if len(sys.argv) > 2 else None
    if which == "phase1":
        run_questions(PHASE1, only_model)
    elif which == "phase2":
        run_questions(PHASE2, only_model)
    elif which == "all":
        run_questions(PHASE1, only_model)
        run_questions(PHASE2, only_model)
    else:
        print(f"unknown arg {which!r}, expected phase1, phase2, or all")
        sys.exit(2)


if __name__ == "__main__":
    main()
