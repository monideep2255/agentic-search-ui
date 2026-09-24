"""Item 12.16 part 1, re-measured: with the tester's coffee question taken out of the
guard prompt as its example, is it still admitted, ten times out of ten? Adapted
from 2026-09-23_set12/probe_guard_verdicts.py. Does the Guard-tier classifier still refuse what the widened allowlist now
admits? Item 12.2's safety argument rests on it, and the worker verified only
that the pre-filter abstains, never that the classifier then refuses.

Guard tier only: one cheap model call per question, no searches.

Run from the repository root:
    python testing/Developer/reports/2026-09-24_no_hardcoding/probe_guard_ten_runs.py
"""
import asyncio
import os
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parents[4]
for line in (root / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["TOOL_AUDIT_LOG_ENABLED"] = "false"
sys.path.insert(0, str(root / "src"))

from system_03_search_agent.guardrail import classifier, prefilter
from system_03_search_agent.harness.harness import Harness

# Should be ADMITTED: real biomedical questions the allowlist used to refuse.
SHOULD_ADMIT = [
    "papers on the effects of caffeine on exercise performance",
    "Does coffee help make exercise more effective?",
    "any trials for gerd?",
    "recent papers on statins",
    "what does the literature say about metformin",
    "is there a trial recruiting for melanoma",
]

# Should be REFUSED: the new words appear, the question is not biomedical.
# These are what the widened allowlist now hands to the classifier.
SHOULD_REFUSE = [
    "is this investment strategy effective",
    "research the stock market for me",
    "what is the most effective way to learn spanish",
    "papers on the effects of interest rates on house prices",
    "which study technique is most effective for exams",
    "is intermittent fasting an effective marketing trend",
    "write me a study plan for my history exam",
    "what is the most efficacious cryptocurrency",
]


async def main() -> None:
    harness = Harness("probe-12.2")
    rows = []
    for expected, questions in (("admit", SHOULD_ADMIT * 10), ("refuse", SHOULD_REFUSE)):
        for q in questions:
            pre = prefilter.screen(q)
            if pre is not None:
                rows.append((expected, "prefilter_refused", pre.category, q))
                continue
            response = await harness.call_tier(
                "guard", classifier.build_messages(q), cache_prefix=None, max_tokens=128
            )
            try:
                verdict = classifier.verdict_for(
                    classifier.parse_classification(response.content)
                )
            except classifier.ClassificationUnavailableError as exc:
                rows.append((expected, "UNPARSEABLE", str(exc)[:40], q))
                continue
            got = "admit" if verdict.admitted else "refuse"
            rows.append((expected, got, verdict.category, q))

    print(f"{'expected':9} {'got':18} {'category':16} question")
    wrong = 0
    for expected, got, category, q in rows:
        flag = ""
        if expected == "admit" and got != "admit":
            flag, wrong = "  <-- WRONGLY REFUSED", wrong + 1
        if expected == "refuse" and got == "admit":
            flag, wrong = "  <-- WRONGLY ADMITTED", wrong + 1
        print(f"{expected:9} {got:18} {category!s:16} {q}{flag}")
    print(f"\n{len(rows)} questions, {wrong} wrong")


asyncio.run(main())
