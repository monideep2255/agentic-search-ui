"""Sequential driver for the writer-tier bench, card 10, 2026-09-25.

Runs every (model, question) pair one at a time via run_bench.py as a
subprocess, checking cumulative spend after each run and stopping early if
total spend passes 2.50 dollars, per the goal contract for this bench.
"""
import json
import subprocess
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
RESULTS = OUT_DIR / "results.jsonl"
SPEND_CAP = 2.50

MODELS = [
    "z-ai/glm-5.2",
    "moonshotai/kimi-k2.5",
    "deepseek/deepseek-v4-pro",
    "anthropic/claude-sonnet-5",
]

QUESTIONS = [
    ("G-016", "What are the known orthologs of TP53 in other species?"),
    ("G-031", "What molecular activity does the KRAS gene product have?"),
    ("G-026", "Which genes are associated with cystic fibrosis?"),
    ("G-022", "What phenotypic features are associated with Marfan syndrome?"),
    ("G-024", "What is rs334 and what condition is it associated with?"),
    ("G-023", "Which clinically significant variants have been reported in CFTR?"),
    ("G-019", "What MeSH terms are assigned to PMID 11237011?"),
    ("G-021", "Which papers in the graph mention the CFTR gene, and what do they cover?"),
    ("G-012", "Find clinical trials for carcinoma not otherwise specified."),
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


def main() -> None:
    for model in MODELS:
        for qid, qtext in QUESTIONS:
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
                timeout=600,
            )
            print(proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "[no stdout]")
            if proc.returncode != 0:
                print(f"[WARN] non-zero exit for {model}/{qid}: rc={proc.returncode}")
                print(proc.stderr[-2000:])
    print(f"[FINISHED] total spend ${total_spend():.4f}")


if __name__ == "__main__":
    main()
