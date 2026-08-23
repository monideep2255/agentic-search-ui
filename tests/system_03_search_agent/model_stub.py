"""One shared stub for `litellm.acompletion`, dispatching per tier.

## Why this module exists

Every test fixture that mocks the model used to hand back ONE fixed response
for every call in the loop. That is correct exactly as long as no tier
actually reads its response, and it has now broken twice for the same reason:

- Build phase 2.2 gave the Write step a real narrative. Ten tests across two
  files failed, two of them blaming the graph. `LEARNINGS.md`, 2026-08-03.
- Build phase 3.0 gave the guardrail a real classification to parse. 41 tests
  across four files failed, none of them about the guardrail.

Both times the mock was silently answering for a tier whose response had just
become load-bearing. Both times the fix was the same: dispatch on something
only that tier's prompt carries.

Fixing it in four separate fixtures would leave four copies to update the
next time a tier starts reading its response, which is the failure mode
rather than a fix for it. This module is the single place that changes.

## What it models

A COMPLIANT model: one that answers each tier the way a working provider
would for a legitimate query.

- Guard: a valid JSON classification saying "not injection".
- Think: a valid JSON classification and gene-symbol extraction (build
  phase 4.7, T-4.7-04/T-4.7-05: `think_node`'s response is now READ, not
  discarded, so this is the third tier that broke the same way build
  phase 3.0's guardrail and build phase 2.2's synth did).
- Synth: a narrative built from the findings it was actually given, so the
  grounding pass runs for real and a defect in it still fails a test.
- Everything else: whatever the caller configured, unchanged.

It deliberately does NOT model a hostile or broken model. Refusal paths,
malformed responses, and injection live in `tests/system_03_search_agent/
guardrail/` and in the phase 3.0 premise gate against a real model. This file
models a good model; those model a bad one and an attacker.
"""

from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any

__all__ = [
    "COMPLIANT_GUARD_CLASSIFICATION",
    "KNOWN_GENE_SYMBOL_CURIES",
    "compliant_synth_narrative",
    "compliant_think_classification",
    "fake_response",
    "install_dispatching_acompletion",
]

# What a working Guard tier returns for an ordinary biomedical question.
# Must satisfy `guardrail.classifier.InjectionClassification`, which forbids
# extra fields, so this is not free-form.
COMPLIANT_GUARD_CLASSIFICATION = (
    '{"is_injection": false, "is_off_topic": false, "confidence": 0.02, '
    '"reason": "an ordinary biomedical question"}'
)

# The gene symbols every caller of this module already stubs live
# resolution for (`resolve_symbol_to_curie`), by hand, in each test file's
# own `_stub_symbol_resolution`-shaped fixture. Named here too so the
# compliant Think stand-in extracts exactly the symbols those fixtures can
# actually resolve, never a symbol whose live-lookup stub does not exist.
KNOWN_GENE_SYMBOL_CURIES: dict[str, str] = {
    "BRCA1": "NCBIGene:672",
    "TP53": "NCBIGene:7157",
}

# Matches the findings block the Synth prompt carries, so the stub can restate
# what it was given rather than inventing content the grounding pass would
# correctly strip.
_FINDING_LINE = re.compile(r"^\[(\d+)\]\s*(.+)$", re.MULTILINE)


def fake_response(
    content: str = "ok", prompt_tokens: int = 10, completion_tokens: int = 5
) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        ),
    )


def compliant_synth_narrative(messages: list[dict[str, Any]]) -> str:
    """A narrative that cites exactly the findings it was handed."""
    prompt = "\n".join(message.get("content", "") for message in messages)
    clauses = [
        f"{body.strip()} [{index}]" for index, body in _FINDING_LINE.findall(prompt)
    ]
    if not clauses:
        return "ok"
    return ". ".join(clauses) + "."


def compliant_think_classification(messages: list[dict[str, Any]]) -> str:
    """A Think reply: a real Section 17 shape, plus known gene extraction.

    Build phase 4.7 (T-4.7-04/T-4.7-05). `query_class` defaults to
    "exploratory", Section 17's catch-all shape: harmless for a no-tool
    query (`plan_node` selects nothing regardless of class) and a real,
    schema-valid value otherwise. Entities are limited to
    `KNOWN_GENE_SYMBOL_CURIES`'s keys, scanned only in the USER-role
    content (`think_node`'s `_THINK_SYSTEM_INSTRUCTION` itself names BRCA1
    and TP53 as worked examples of a gene symbol, so scanning the full
    joined prompt would match those example mentions on every call
    regardless of the actual query text).
    """
    user_text = "\n".join(
        message.get("content", "") for message in messages if message.get("role") == "user"
    )
    entities = [
        {"text": symbol, "entity_type": "gene"}
        for symbol in KNOWN_GENE_SYMBOL_CURIES
        if re.search(rf"\b{re.escape(symbol)}\b", user_text)
    ]
    return json.dumps(
        {
            "query_class": "exploratory",
            "narrative": "stand-in classification for tests",
            "entities": entities,
        }
    )


def install_dispatching_acompletion(monkeypatch: Any, harness_module: Any) -> Any:
    """Patch `litellm.acompletion` with the per-tier dispatcher.

    Returns the mock, so a test can still assert on call count and arguments,
    and can still override the default non-guard, non-think, non-synth
    response with `monkeypatch.setattr(mock, "return_value", ...)`.

    That override keeps working because the dispatcher reads `return_value`
    back off the mock at call time rather than closing over it. `side_effect`
    takes precedence over `return_value` on a `Mock`, so a dispatcher that
    ignored it would silently disable every such override in the suite. That
    trap is recorded in `LEARNINGS.md` (2026-08-03) as the second half of the
    same fixture failure.
    """
    from unittest.mock import AsyncMock

    from system_03_search_agent.core.graph import _THINK_SYSTEM_INSTRUCTION
    from system_03_search_agent.guardrail.classifier import GUARD_SYSTEM_INSTRUCTION
    from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION

    async def _dispatch(*args: object, **kwargs: object) -> Any:
        messages = kwargs.get("messages") or []
        joined = "\n".join(
            message.get("content") or ""
            for message in messages  # type: ignore[union-attr]
        )
        if GUARD_SYSTEM_INSTRUCTION in joined:
            return fake_response(COMPLIANT_GUARD_CLASSIFICATION)
        if _THINK_SYSTEM_INSTRUCTION in joined:
            return fake_response(compliant_think_classification(messages))  # type: ignore[arg-type]
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            return fake_response(compliant_synth_narrative(messages))  # type: ignore[arg-type]
        return mock_acompletion.return_value

    mock_acompletion = AsyncMock(side_effect=_dispatch)
    mock_acompletion.return_value = fake_response()
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )
    return mock_acompletion
