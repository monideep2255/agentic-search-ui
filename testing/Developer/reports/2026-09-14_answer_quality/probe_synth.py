"""Call the synth tier N times with a captured prompt and print, per call:
wall time, content words, prompt/completion tokens as the harness saw them,
and the raw litellm response's reasoning length and finish reason.

Usage: python probe_synth.py after1_gck_researcher.json 6
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

root = Path("<repo-root>")
for line in (root / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
os.environ["LANGCHAIN_TRACING_V2"] = "false"
sys.path.insert(0, str(root / "src"))

from system_03_search_agent.core.graph import _STABLE_PREFIX
from system_03_search_agent.harness import harness as harness_module

raw_seen: list[dict] = []
_orig = harness_module.litellm.acompletion


async def _spy(*args, **kwargs):
    response = await _orig(*args, **kwargs)
    try:
        choice = response.choices[0]
        message = choice.message
        reasoning = getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None)
        provider = getattr(message, "provider_specific_fields", None)
        raw_seen.append({
            "finish_reason": getattr(choice, "finish_reason", None),
            "content_words": len((message.content or "").split()),
            "reasoning_chars": len(reasoning) if isinstance(reasoning, str) else None,
            "provider_fields": list(provider.keys()) if isinstance(provider, dict) else None,
            "usage": {k: getattr(response.usage, k, None) for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
            "details": str(getattr(response.usage, "completion_tokens_details", None))[:200],
            "max_tokens_sent": kwargs.get("max_tokens"),
            "reasoning_sent": kwargs.get("reasoning"),
        })
    except Exception as exc:  # noqa: BLE001
        raw_seen.append({"spy_error": repr(exc)})
    return response


harness_module.litellm.acompletion = _spy
if os.environ.get("PROBE_EFFORT"):
    harness_module._TIER_REASONING["synth"] = {"effort": os.environ["PROBE_EFFORT"]}


def _load_capture(path: str) -> dict:
    with open(path) as handle:
        return json.load(handle)


async def main(path: str, runs: int) -> None:
    captured = _load_capture(path)
    messages = captured["synth_calls"][0]["messages"]
    harness = harness_module.Harness(trace_id="probe")
    for _ in range(runs):
        raw_seen.clear()
        started = time.monotonic()
        try:
            response = await harness.call_tier("synth", messages, cache_prefix=_STABLE_PREFIX)
            wall = round(time.monotonic() - started, 1)
            print(json.dumps({"wall_s": wall, "content_words": len(response.content.split()),
                              "prompt_tokens": response.prompt_tokens, "completion_tokens": response.completion_tokens,
                              "raw": raw_seen}))
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"wall_s": round(time.monotonic() - started, 1), "exception": repr(exc)[:300], "raw": raw_seen}))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], int(sys.argv[2])))
