#!/usr/bin/env python3
"""Builder D's acceptance probe: three real decisions through decide()
with CLASSIFIER_PROVIDER=jev, against the real OpenRouter decisions
endpoint. Loads OPENROUTER_API_KEY from the main repo's .env, never
prints it. Run from the repo root with PYTHONPATH=src.
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, "src")

ENV_PATH = "/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui/.env"  # local-refs: allow


def load_api_key() -> str:
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("OPENROUTER_API_KEY not found in .env")


async def main() -> None:
    os.environ["CLASSIFIER_PROVIDER"] = "jev"
    os.environ["OPENROUTER_API_KEY"] = load_api_key()
    os.environ.setdefault("PER_QUERY_COST_CAP_USD", "0.10")

    from system_03_search_agent.harness.decide import decide
    from system_03_search_agent.harness.harness import Harness

    cases = [
        (
            "guardrail.relevancy",
            "Question: 'what genes are associated with cystic fibrosis?' "
            "Is this relevant to biomedical genetics research?",
            ["relevant", "not_relevant"],
        ),
        (
            "think.ask_back",
            "The user asked: 'tell me about the gene'. No gene was named. "
            "Should a short clarifying question be asked, or should the "
            "system proceed anyway?",
            ["ask", "proceed"],
        ),
        (
            "plan.resource",
            "Question: 'which gene is associated with cystic fibrosis?' "
            "Decide which resource best answers it.",
            [
                "cypher_query",
                "ncbi_efetch",
                "ncbi_dbsnp",
                "pubtator_annotate",
                "litvar2_lookup",
                "pathogen_detection",
                "clinicaltrials_search",
            ],
        ),
    ]

    harness = Harness(trace_id="probe-2026-09-25")
    for point, state, options in cases:
        record = await decide(harness, "probe-2026-09-25", point, state, options)
        print(f"--- {point} ---")
        print(record.model_dump_json(indent=2))
    print(f"\ntotal metered cost this trace: ${harness.get_query_cost_usd('probe-2026-09-25'):.6f}")


if __name__ == "__main__":
    asyncio.run(main())
