"""Run card 130's measured set as one batch, one process per run, in order.

Usage: ASU_ENV_FILE=<path to the .env> python run_batch.py <batch>

Six questions, both depths, two repeats: 24 runs. Reads the key's usage
before and after the batch and stops early if this batch passes the
budget given in CARD130_BATCH_BUDGET_USD (default 1.10).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
BATCH = sys.argv[1]
BUDGET = float(os.environ.get("CARD130_BATCH_BUDGET_USD", "1.10"))
KEYS = [
    "q116_orthologs",
    "q022_cftr_variants",
    "q078_mody_genes",
    "q104_pmid_data",
    "rs334_rs6025",
    "q037_colistin",
]


def usage() -> float:
    out = subprocess.run(
        [PY, str(HERE / "key_usage.py")], capture_output=True, text=True, check=True
    ).stdout
    return float(json.loads(out)["usage_usd"])


start = usage()
print(f"usage at start: {start:.4f}", flush=True)
for repeat in ("1", "2"):
    for key in KEYS:
        for depth in ("researcher", "plain_language"):
            subprocess.run(
                [PY, str(HERE / "measure.py"), BATCH, key, depth, repeat],
                cwd=str(HERE.parents[4]),
                timeout=180,
                check=False,
            )
            print(f"done {key} {depth} {repeat}", flush=True)
        spent = usage() - start
        print(f"batch spend so far: {spent:.4f}", flush=True)
        if spent > BUDGET:
            print("STOP: batch budget passed", flush=True)
            sys.exit(2)
print(f"usage at end: {usage():.4f}; batch spend {usage() - start:.4f}", flush=True)
