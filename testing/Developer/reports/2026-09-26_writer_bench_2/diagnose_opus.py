"""One-off diagnostic, not part of the bench rows: call the REAL harness
`Harness.call_tier("synth", ...)` for anthropic/claude-opus-5.5 directly, and
print the internal HarnessCallError text verbatim (harness.py's own
f"call_tier failed for tier {tier!r} (model {model_id!r}) after "
f"{attempt} attempt(s): {error_class} error ({type(exc).__name__}): {exc}"),
which core/graph.py deliberately never surfaces to the end user
(F-2.0-12). No product file is modified; this only imports and calls
existing functions.

Prints the step, the exception class, and the exception message. Never
prints an .env value.
"""
import asyncio
import os
import sys
from pathlib import Path

MAIN_REPO = Path(__file__).resolve().parents[4]

for line in (MAIN_REPO / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

os.environ["SYNTH_MODEL"] = "anthropic/claude-opus-5.5"
os.environ["GUARD_MODEL"] = "deepseek/deepseek-v4-flash"
os.environ["PLAN_MODEL"] = "deepseek/deepseek-v4-flash"
os.environ["PER_QUERY_COST_CAP_USD"] = "0.75"

sys.path.insert(0, str(MAIN_REPO / "src"))

from system_03_search_agent.harness.harness import Harness, HarnessCallError


async def main() -> None:
    harness = Harness(trace_id="diagnose-opus-5.5")
    try:
        resp = await harness.call_tier(
            "synth",
            [{"role": "user", "content": "Say hello in one word."}],
        )
        print("SUCCEEDED, unexpectedly:", resp)
    except HarnessCallError as exc:
        print("step=synth")
        print("exception_class=HarnessCallError")
        print("error_class attribute:", exc.error_class)
        print("internal message (never shown to the end user):")
        print(str(exc))
        # The __cause__ is the raw provider/litellm exception `call_tier`
        # wrapped with `raise ... from exc`.
        print("raw cause type:", type(exc.__cause__).__name__)
        print("raw cause message:", str(exc.__cause__))
    except Exception as exc:  # noqa: BLE001 - diagnostic script, report whatever surfaces
        print("UNEXPECTED non-HarnessCallError exception:", type(exc).__name__, exc)


asyncio.run(main())
