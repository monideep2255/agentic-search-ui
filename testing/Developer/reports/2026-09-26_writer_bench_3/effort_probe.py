"""Which lowest reasoning effort does each mandatory-reasoning writer accept?

The lead's instruction of 2026-09-26: for each candidate that refuses the
product's `effort: none`, bench one labelled variant at the lowest effort its
provider accepts. This asks each model a one-line question at "minimal",
then "low", through the same litellm and OpenRouter path the harness uses,
and prints whether the request was accepted, its reasoning tokens, its
seconds and OpenRouter's reported cost. A few cents in all.

Loads the repository's .env without printing a value.

Usage: effort_probe.py <model_id> [<model_id> ...]
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import litellm

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
for line in (REPO / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

MESSAGES = [{"role": "user", "content": "In one sentence: what does a GTPase do?"}]


async def ask(model: str, effort: str) -> dict:
    started = time.monotonic()
    try:
        response = await litellm.acompletion(
            model=f"openrouter/{model}", messages=MESSAGES, reasoning={"effort": effort}, max_tokens=512
        )
    except Exception as exc:  # noqa: BLE001 - a refusal is the answer being measured
        return {"model": model, "effort": effort, "accepted": False, "error": str(exc)[:200]}
    usage = response.usage
    details = getattr(usage, "completion_tokens_details", None)
    headers = (getattr(response, "_hidden_params", {}) or {}).get("additional_headers") or {}
    return {
        "model": model,
        "effort": effort,
        "accepted": True,
        "seconds": round(time.monotonic() - started, 2),
        "completion_tokens": usage.completion_tokens,
        "reasoning_tokens": getattr(details, "reasoning_tokens", None) if details else None,
        "finish": response.choices[0].finish_reason,
        "cost_usd": headers.get("llm_provider-x-litellm-response-cost"),
    }


async def main() -> None:
    out = []
    for model in sys.argv[1:]:
        for effort in ("minimal", "low"):
            row = await ask(model, effort)
            out.append(row)
            print(json.dumps(row), flush=True)
            if row["accepted"]:
                break
    with open(HERE / "effort_probe.jsonl", "a") as f:  # noqa: ASYNC230 - one small append at the end
        f.writelines(json.dumps(row) + "\n" for row in out)


asyncio.run(main())
