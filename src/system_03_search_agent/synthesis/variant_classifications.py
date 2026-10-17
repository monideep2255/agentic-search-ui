"""Look up ClinVar's classification of each graph variant an answer lists.

Card 30, step 2b (owner decision, 2026-10-16): "one ClinVar ESummary call per
50 listed graph variants, about a second, and every listed variant shows its
ClinVar classification."

## Why this exists

A knowledge graph `SequenceVariant` row carries no classification (the graph
loads neither ClinVar's ClinicalSignificance nor its review status), so a
list under "Which BRCA1 variants are pathogenic?" cannot say which are. The
classification lives on the variant's live ClinVar record, one ESummary away.
This module reads it there, the way `disease_names` reads a MedGen title.

## What it will not do

- It shows ClinVar's own words. The value is `germline_classification.
  description` of the record, stripped and nothing else. A value it cannot
  read as one short line (missing, not text, over `_MAX_CLASSIFICATION_CHARS`,
  holding a control character) is treated as unread, never cut or tidied,
  because a clipped classification is a paraphrase of clinical text.
- It joins by record id, never by position. A CURIE whose record did not
  come back, or came back twice with different values, is absent from the
  result, and the caller keeps today's row for it.
- It never raises into the agent loop and never invents a value. Timeout,
  transport error, rate limit, a refused call: each leaves the affected
  CURIEs out of the result.
- It never spends past the per-query ceiling. At the ceiling it makes no
  request at all.

## Budgets

One request per `_IDS_PER_REQUEST` (50, the tool schema's own bound) CURIEs,
at most `_MAX_REQUESTS` requests (the display cap is 100 rows). Every call
goes through `tools.ncbi_eutils_actions`, so it inherits the shared token
bucket, the wait queue and the Layer 2/3 call ceiling.

Depends on:
    - system_03_search_agent.tools.ncbi_eutils_actions (summary)
    - system_03_search_agent.harness.call_budget (calls_made)

Reads:
    - Live ClinVar over E-utilities, through the shared rate pool.

Writes:
    - Nothing.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Sequence
from typing import Any

from system_03_search_agent.harness import call_budget

logger = logging.getLogger(__name__)

__all__ = ["CLASSIFICATION_ROW_FIELD", "resolve_variant_classifications"]

#: The row field name the layout reads a looked up classification under. It
#: is set on a copy of the row at display time, never on a stored record.
CLASSIFICATION_ROW_FIELD = "clinvar_classification"

# A graph ClinVar CURIE: `ClinVar:` then the numeric variation id, which is
# the uid of the record in ClinVar's ESummary.
_CLINVAR_CURIE = re.compile(r"^ClinVar:(\d{1,20})$", re.ASCII)

_IDS_PER_REQUEST = 50
_MAX_REQUESTS = 2
# Per request. About a second is typical (measured), so this leaves room
# for a slow reply without holding the answer for long.
_REQUEST_TIMEOUT_S = 4.0
# ClinVar's longest germline description is "Conflicting classifications of
# pathogenicity" (44 characters).
_MAX_CLASSIFICATION_CHARS = 100
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _local_id(curie: str) -> str | None:
    match = _CLINVAR_CURIE.match(curie.strip())
    return match.group(1) if match else None


def _classification_of(fields: Any) -> str | None:
    """The record's germline classification text, or None if unreadable."""
    if not isinstance(fields, dict):
        return None
    block = fields.get("germline_classification")
    if not isinstance(block, dict):
        return None
    text = block.get("description")
    if not isinstance(text, str):
        return None
    text = text.strip()
    if not text or len(text) > _MAX_CLASSIFICATION_CHARS or _CONTROL.search(text):
        return None
    return text


def _requests_allowed(wanted: int) -> int:
    """How many requests the query's call ceiling still permits."""
    made = call_budget.calls_made()
    if made is None:
        return wanted
    return max(0, min(wanted, call_budget.MAX_LAYER_2_3_CALLS_PER_QUERY - made))


async def _summary_classifications(ids: list[str]) -> dict[str, str | None]:
    """One ESummary over `ids`, keyed by the record's own id. Never raises.

    A uid seen twice with different values maps to None (ambiguous).
    """
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchSummaryInput
    from system_03_search_agent.tools.ncbi_eutils_actions import summary

    try:
        result = await asyncio.wait_for(
            summary(NcbiEfetchSummaryInput(action="summary", db="clinvar", ids=ids)),
            timeout=_REQUEST_TIMEOUT_S,
        )
    except Exception as exc:  # noqa: BLE001
        # Deliberately broad: a failed lookup leaves the list as it was.
        logger.warning("ClinVar classification lookup failed: %s", type(exc).__name__)
        return {}
    if result.status != "ok":
        return {}
    found: dict[str, str | None] = {}
    for record in result.records:
        uid = str(record.id).strip()
        value = _classification_of(record.fields)
        if uid in found and found[uid] != value:
            value = None
        found[uid] = value
    return found


async def resolve_variant_classifications(curies: Sequence[str]) -> dict[str, str]:
    """Map each `ClinVar:` CURIE to ClinVar's classification of it.

    Only CURIEs whose classification was read appear in the result. A CURIE
    of another vocabulary, a duplicate, or one whose record could not be
    read is simply absent. No request is made when there is nothing to ask
    or the per-query call ceiling is spent.
    """
    by_local: dict[str, list[str]] = {}
    for curie in curies:
        local = _local_id(str(curie))
        if local is not None and str(curie) not in by_local.get(local, []):
            by_local.setdefault(local, []).append(str(curie))
    if not by_local:
        return {}
    locals_sorted = sorted(by_local)
    chunks = [
        locals_sorted[i : i + _IDS_PER_REQUEST]
        for i in range(0, len(locals_sorted), _IDS_PER_REQUEST)
    ][:_MAX_REQUESTS]
    chunks = chunks[: _requests_allowed(len(chunks))]
    if not chunks:
        return {}
    replies = await asyncio.gather(*(_summary_classifications(chunk) for chunk in chunks))
    resolved: dict[str, str] = {}
    for chunk, reply in zip(chunks, replies, strict=True):
        for local in chunk:
            value = reply.get(local)
            if value:
                for curie in by_local[local]:
                    resolved[curie] = value
    return resolved
