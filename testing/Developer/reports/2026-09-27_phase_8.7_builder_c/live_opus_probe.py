"""Build phase 8.7, T-8.7-02: one live Opus writer call through the product harness.

Proves, against the real provider, that the synth tier's new default answers
through `Harness.call_tier` with `effort: minimal`: no refusal, no retry
without the reasoning block, a reply, and a metered cost. One call, a
one-sentence question, a 200-token ceiling: well under a cent. The lead's
limit for this ticket's live calls is one dollar in all.

What it does, and what it never does:

- Loads the nearest `.env` above this file without printing any value.
- Unsets GUARD_MODEL, PLAN_MODEL and SYNTH_MODEL in this process only, so the
  code defaults answer, as on develop, which sets no synth override.
- Wraps `litellm.acompletion` to record what the harness sent (model,
  reasoning block, ceiling) and the usage that came back. It calls through
  unchanged.
- Reads the account's remaining balance before and after from OpenRouter's
  credits endpoint, printing the figures only.
- Writes `live_opus_probe.json` beside this file: figures and flags, no key,
  no path, no reply text beyond its length.

Usage: live_opus_probe.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[3]


def _load_env() -> None:
    for folder in HERE.parents:
        candidate = folder / ".env"
        if candidate.is_file():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            return


_load_env()
os.environ["LANGCHAIN_TRACING_V2"] = "false"
sys.path.insert(0, str(TREE / "src"))

import litellm

from system_03_search_agent.harness.harness import Harness

# After the imports, not before: importing litellm calls `load_dotenv()`,
# which finds the checkout's `.env` and would set SYNTH_MODEL again. The
# first run of this script, before this move, called glm-5.2 for that reason.
for _name in ("GUARD_MODEL", "PLAN_MODEL", "SYNTH_MODEL"):
    os.environ.pop(_name, None)

#: The one model this probe may call. Anything else resolving means the probe
#: is measuring the wrong thing, so it stops before spending.
_EXPECTED_SYNTH = "anthropic/claude-opus-5.5"


def _balance_usd() -> float | None:
    """OpenRouter's remaining credit, or None when it cannot be read."""
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/credits",
        headers={"Authorization": "Bearer " + os.environ.get("OPENROUTER_API_KEY", "")},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read())["data"]
        return round(float(data["total_credits"]) - float(data["total_usage"]), 4)
    except Exception:  # noqa: BLE001
        # The balance is optional; its absence is reported as None.
        return None


class _Warnings(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


async def main() -> None:
    sent: list[dict[str, Any]] = []
    real_acompletion = litellm.acompletion

    async def _recording(**kwargs: Any) -> Any:
        entry: dict[str, Any] = {
            "model": kwargs.get("model"),
            "reasoning": kwargs.get("reasoning"),
            "max_tokens": kwargs.get("max_tokens"),
        }
        sent.append(entry)
        response = await real_acompletion(**kwargs)
        usage = response.usage
        details = getattr(usage, "completion_tokens_details", None)
        headers = (getattr(response, "_hidden_params", {}) or {}).get("additional_headers") or {}
        entry.update(
            {
                "finish": response.choices[0].finish_reason,
                "reasoning_tokens": getattr(details, "reasoning_tokens", None)
                if details
                else None,
                "openrouter_cost_usd": headers.get("llm_provider-x-litellm-response-cost"),
            }
        )
        return response

    litellm.acompletion = _recording
    warnings = _Warnings()
    logging.getLogger("system_03_search_agent").addHandler(warnings)

    harness = Harness(trace_id="trace-8.7-live-opus-probe")
    if harness.model_for("synth") != _EXPECTED_SYNTH:
        raise SystemExit("the synth tier does not resolve to Opus 5.5 here; nothing was sent")
    before = _balance_usd()
    started = time.monotonic()
    error: str | None = None
    result = None
    try:
        result = await harness.call_tier(
            "synth",
            [{"role": "user", "content": "In one sentence: what does the BRCA1 gene product do?"}],
            max_tokens=200,
        )
    except Exception as exc:  # noqa: BLE001
        # A failure is the result being measured, so it is kept, bounded.
        error = f"{type(exc).__name__}: {str(exc)[:300]}"
    seconds = round(time.monotonic() - started, 2)
    await asyncio.sleep(2)
    after = _balance_usd()

    report = {
        "resolved_synth_model": harness.model_for("synth"),
        "requests_sent": sent,
        "request_count": len(sent),
        "reasoning_refusal_fallback_logged": any(
            "refused the reasoning block" in m for m in warnings.messages
        ),
        "succeeded": result is not None,
        "error": error,
        "seconds": seconds,
        "harness_elapsed_s": round(result.elapsed_s, 2) if result and result.elapsed_s else None,
        "prompt_tokens": result.prompt_tokens if result else None,
        "completion_tokens": result.completion_tokens if result else None,
        "reply_chars": len(result.content or "") if result else None,
        "harness_metered_cost_usd": round(result.call_cost_usd, 6) if result else None,
        "balance_before_usd": before,
        "balance_after_usd": after,
    }
    (HERE / "live_opus_probe.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
