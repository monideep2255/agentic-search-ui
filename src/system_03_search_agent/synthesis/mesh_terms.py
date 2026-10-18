"""Resolve MeSH descriptor ids to their headings, over Layer 2.

The sibling of `synthesis/disease_names.py`, one vocabulary over, and
written deliberately as a mirror of it rather than as a generalisation of
it. See "Why this is not one shared resolver" below.

## The problem, measured rather than assumed

Golden question G-019 asks "What MeSH terms are assigned to PMID
11237011?". It reaches 26 rows through
`Article`-[:has_mesh_annotation]->`OntologyClass`, answers two passes of
three, and every instrument in this project reads it as working. It is not
working. The rows carry no terms.

Probed graph-wide on 2026-09-23
(`testing/Developer/reports/2026-09-23_overnight/probe_ontology_names.py`):

- All 30,790 `OntologyClass` vertices carry a `name` like `[MeSH] D000818`.
  That is the identifier, written into the name field.
- Zero `OntologyClass` names anywhere in the graph contain a lowercase run
  of four or more letters. Zero contain "neoplasm".
- The control that proves the graph is not generally broken: `Article.name`
  for PMID:11237011 is "Initial sequencing and analysis of the human
  genome.", and `Gene.name` for NCBIGene:2200 is "fibrillin 1".

`core.graph._is_vocabulary_token_artifact` now flags the `[MeSH] D000818`
form, so the identifier is no longer presented as a genuine name. That
stops a falsehood and gives the reader nothing. This module is what gives
them the terms.

The upstream fix is an ETL re-ingest in the System 1 and 2 repository. It is
not this repository's to make (`file-protection.md`) and is not scheduled.

## Two calls, not one, and not two per id. Verified live first

Every figure below was measured against real E-utilities on 2026-09-23,
before a line of this module was written, per this repository's standing
premise-first method.

ESummary keyed on a descriptor id is rejected outright, exactly as MedGen's
is:

    esummary.fcgi?db=mesh&id=D000818
    {"error":"Invalid uid D000818 at position= 0","result":{"uids":[]}}

So resolution needs ESearch on `<id>[MHUI]` for the UID, then ESummary on
that UID. `MHUI` is NCBI's own MeSH-unique-identifier index, the exact
counterpart of MedGen's `[ConceptId]`.

This module issues TWO calls TOTAL regardless of how many ids it is given.
One ESearch ORs every `[MHUI]` clause together; one ESummary covers every
UID that came back. G-019's full set of 26 ids was measured end to end:
ESearch returned `count=26` with all 26 UIDs, and one ESummary returned all
26 records.

## Do not delete the ESearch call

Six-digit descriptors make the UID look computable: `D000818` is UID
`68000818`, `D015894` is `68015894`. It reads as `68` plus the digits, and a
future reader will be tempted to drop ESearch and save a call.

It is not a mapping. NINE-digit descriptors are real and are in this graph
(`MeSH:D000066388`, `MeSH:D000066428`). Live, `D000066428` is UID `2009637`
and `D000066388` is UID `2009636`: no prefix, no padding, nothing derivable.
Both resolve correctly through `[MHUI]`. The ESearch call is load-bearing
for a whole class of real ids.

## The mapping back is by identifier, never by position

Each ESummary record carries `ds_meshui`, its own descriptor id, alongside
`ds_meshterms`, whose first entry is the preferred heading. That is the join
key.

This is not a precaution against a hypothetical. Measured on the same run:
ESearch returned the 26 UIDs in DESCENDING numeric order (`68030342` first,
`68000818` last) while the request listed them in the graph's own order
(`D000818` first). Position `i` of the result is not position `i` of the
request, today, on the live endpoint. A resolver that matched by order would
attach the wrong term to the right identifier, which is the worst failure
available here: a confident, citable, wrong answer.

## What this module will not do

It NEVER invents a term. An id MeSH does not hold, an ESearch that finds
nothing, an ESummary with no `ds_meshterms`, a transport failure, a
rate-limit refusal, a call-budget refusal: every one of them maps that id to
`None`, and the caller keeps the identifier, still flagged by
`_is_vocabulary_token_artifact`. Under-resolution is cheap and a wrong MeSH
heading is not.

It also never raises into the agent loop. A failure here must degrade an
answer from readable to unreadable, never from readable to absent. The
behaviour before this module existed, 26 flagged identifiers, is this
module's failure mode by construction.

## Why this is not one shared resolver with disease_names

The two look alike and are not the same. They query different databases
(`medgen` versus `mesh`), through different index tags (`[ConceptId]`
versus `[MHUI]`), read different response fields (`title` versus
`ds_meshterms[0]`), join on different keys (`conceptid` versus `ds_meshui`),
and validate different id shapes (`CN?\\d+` versus `D\\d+`). A shared
resolver would be five parameters wide and its single shared line would be
`" OR ".join`.

The real reason to keep them apart is the failure direction. A generalised
resolver invites a caller to pass a mixed list, and the natural
implementation of that is one ESearch against one db, which would silently
return nothing for the ids of the other vocabulary while looking like it
worked. Two functions cannot make that mistake.

## Caching, and the honest limit of it

A bounded in-process TTL map, the same shape and the same limit as
`disease_names`. NOT the Section 4.3 Redis response cache, which is
specified and not yet built. The guarantee is per-process and
per-deployment-instance: a repeated question in one process pays nothing, a
cold process pays the two calls again.

TTL is one week. A MeSH descriptor's preferred heading changes at most once
a year, in NLM's annual vocabulary update, so this is comfortably the
"stable field" class.

## Budgets

Every call goes through `tools.ncbi_eutils_actions`, so it inherits the
`eutils` token bucket, the bounded wait queue, build phase 6.0's per-query
Layer 2/3 ceiling and the build phase 5.0 audit log with no code here. That
is why this module calls the tool actions rather than reaching for `urllib`:
a private HTTP path would be invisible to all four.

`resolve_descriptor_ids` additionally reads `harness.call_budget.calls_made`
and declines to start when fewer than two calls remain, so it degrades to
identifiers rather than spending a query's last slot on a cosmetic
improvement. That check is belt and braces rather than the real guard: the
transport would refuse the call anyway and this module would catch the
refusal, and its one caller runs after every Act call has finished, so there
is nothing downstream for it to starve.

Depends on:
    - system_03_search_agent.tools.ncbi_eutils_actions (search, summary)
    - system_03_search_agent.tools.ncbi_efetch_schemas (the two input models)
    - system_03_search_agent.harness.call_budget (calls_made, the headroom check)

Reads:
    - Live MeSH over E-utilities, through the shared rate pool.

Writes:
    - Nothing. An in-process cache only.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Sequence

logger = logging.getLogger(__name__)

__all__ = [
    "MESH_DESCRIPTOR_ID",
    "reset_cache_for_tests",
    "resolve_descriptor_ids",
]

# A MeSH descriptor local id: `D` then digits. Deliberately the same shape
# `tools/cypher_provenance.py` already enforces for this prefix, derived
# there from an exhaustive scan of every `OntologyClass` row rather than
# from a sample, and confirmed again on 2026-09-23 (30,790 vertices, zero
# outside this shape). `re.ASCII` is load-bearing and is finding
# F-2.1-A5-07's lesson: without it, `\d` matches every Unicode decimal
# digit, so a Devanagari digit would pass this shape and be quoted into a
# search term for a record that cannot exist.
MESH_DESCRIPTOR_ID = re.compile(r"^D\d+$", re.ASCII)

#: NCBI's own MeSH-unique-identifier search index. The counterpart of
#: MedGen's `[ConceptId]`. Live-verified 2026-09-23.
_MHUI_TAG = "[MHUI]"

#: The hard ceiling on ids per resolution, and the character ceiling on the
#: assembled ESearch term.
#:
#: BOTH are needed and the character one is the real bound.
#: `NcbiEfetchSearchInput.term` is capped at 500 characters by its own
#: schema, and the term grows with the id COUNT and with each id's LENGTH.
#: A six-digit clause (`D000818[MHUI] OR `) is 17 characters and a
#: nine-digit clause is 20, so a fixed count cap that is safe for nine-digit
#: ids wastes room on six-digit ones, and one tuned for six-digit ids
#: overflows on nine. Batching by assembled length instead means G-019's 26
#: six-digit ids (438 characters, measured) all fit in one call, which is
#: the case that matters, while an all-nine-digit batch stops early rather
#: than building a term the schema rejects.
_MAX_IDS_PER_CALL = 30
_MAX_TERM_CHARS = 480

#: The cap on a heading before it reaches a prompt. MeSH headings are short
#: ("Genome, Human", "Sequence Analysis, DNA"); this bounds untrusted
#: external text, it does not expect to engage.
_MAX_TERM_TEXT_CHARS = 300

#: Two calls, so two slots of headroom. See the module docstring's Budgets
#: section for why this is belt and braces.
_CALLS_REQUIRED = 2

# One week, the stable-field TTL class. See the module docstring.
_CACHE_TTL_S = 7 * 24 * 60 * 60
_MAX_CACHE_ENTRIES = 2048

# descriptor id -> (heading or None, monotonic expiry). A NEGATIVE result is
# cached too, deliberately: an id MeSH does not hold will not start existing
# within the TTL, and not caching it means every repeat of the same question
# pays two calls to re-learn the same nothing.
_cache: dict[str, tuple[str | None, float]] = {}


def reset_cache_for_tests() -> None:
    """Clear the resolution cache. Test-only; production never calls this."""
    _cache.clear()


def _cache_get(descriptor_id: str) -> tuple[bool, str | None]:
    """Return `(hit, heading)`. `hit` distinguishes a cached None from a miss.

    Returning a bare `None` for both would make a cached negative result
    indistinguishable from an absent entry, so every repeat of an
    unresolvable id would re-issue the lookup the cache exists to avoid.
    """
    entry = _cache.get(descriptor_id)
    if entry is None:
        return False, None
    heading, expires_at = entry
    if time.monotonic() >= expires_at:
        _cache.pop(descriptor_id, None)
        return False, None
    return True, heading


def _cache_put(descriptor_id: str, heading: str | None) -> None:
    if len(_cache) >= _MAX_CACHE_ENTRIES:
        # Evict the entry closest to expiry rather than clearing the map. A
        # blunt clear on a busy process throws away every warm entry at once
        # and turns a bounded cache into a periodic stall.
        oldest = min(_cache, key=lambda key: _cache[key][1])
        _cache.pop(oldest, None)
    _cache[descriptor_id] = (heading, time.monotonic() + _CACHE_TTL_S)


def _normalize(raw: str) -> str | None:
    """Reduce `MeSH:D000818` or `D000818` to the bare descriptor id.

    Returns None for anything that is not a MeSH descriptor id, including
    another vocabulary's CURIE. A MedGen or MONDO id is a real identifier
    this module simply cannot resolve, and treating it as a descriptor would
    send a lookup guaranteed to miss while spending a shared rate-pool slot.

    The prefix comparison is case-sensitive on purpose. `MeSH` is the exact
    spelling `tools/cypher_provenance.py` maps to a record URL and the exact
    spelling every graph row carries; accepting `mesh` or `MESH` here would
    resolve a heading for a CURIE whose citation URL this system cannot
    build, which is a resolved name with no record behind it.
    """
    text = raw.strip()
    if not text:
        return None
    if ":" in text:
        prefix, _, local = text.partition(":")
        if prefix.strip() != "MeSH":
            return None
        text = local.strip()
    return text if MESH_DESCRIPTOR_ID.match(text) else None


def _batch_for_one_term(descriptor_ids: list[str]) -> list[str]:
    """The prefix of `descriptor_ids` that fits in one legal ESearch term.

    Bounded by `_MAX_IDS_PER_CALL` and by `_MAX_TERM_CHARS` on the assembled
    term, whichever binds first. See `_MAX_IDS_PER_CALL`'s comment for why
    the character bound is the one that actually matters.
    """
    chosen: list[str] = []
    length = 0
    for descriptor_id in descriptor_ids[:_MAX_IDS_PER_CALL]:
        clause = len(descriptor_id) + len(_MHUI_TAG)
        addition = clause if not chosen else clause + 4  # 4 is len(" OR ")
        if length + addition > _MAX_TERM_CHARS:
            break
        chosen.append(descriptor_id)
        length += addition
    return chosen


async def _search_uids(descriptor_ids: list[str]) -> list[str]:
    """One ESearch over every descriptor id at once. Never raises."""
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchSearchInput
    from system_03_search_agent.tools.ncbi_eutils_actions import search

    term = " OR ".join(f"{mesh_id}{_MHUI_TAG}" for mesh_id in descriptor_ids)
    try:
        result = await search(
            NcbiEfetchSearchInput(
                action="search",
                db="mesh",
                term=term,
                retmax=min(len(descriptor_ids) * 2, 500),
            )
        )
    except Exception as exc:  # noqa: BLE001
        # Deliberately broad, and deliberately not re-raised. This module's
        # contract is that a resolution failure degrades the answer to the
        # identifiers it already had. Letting any exception class escape here
        # would turn a cosmetic shortfall into a failed query, which is
        # strictly worse than the defect being fixed. `CallBudgetExceededError`
        # arrives through exactly this path.
        logger.warning("MeSH descriptor search failed: %s", type(exc).__name__)
        return []

    if result.status != "ok":
        return []
    uids: list[str] = []
    for record in result.records:
        for uid in record.fields.get("idlist") or []:
            text = str(uid).strip()
            if text.isdigit():
                uids.append(text)
    return uids


def _preferred_heading(raw: object) -> str | None:
    """The preferred heading out of a record's `ds_meshterms`, or None.

    `ds_meshterms` is a list whose FIRST entry is the descriptor's preferred
    heading and whose remaining entries are entry terms: D000818 returns
    `["Animals", "Animal", "Animalia", "Metazoa"]`, and only the first is
    what a person means by the MeSH term. Taking any other entry, or joining
    them, would state a synonym as the assigned heading.
    """
    if not isinstance(raw, list) or not raw:
        return None
    first = raw[0]
    if not isinstance(first, str):
        return None
    text = first.strip()
    return text[:_MAX_TERM_TEXT_CHARS] if text else None


async def _summary_headings(uids: list[str]) -> dict[str, str]:
    """One ESummary over every UID at once, keyed by descriptor id.

    Keyed on the payload's own `ds_meshui` rather than on the position of the
    record in the list. Order is not a documented property of an ESummary
    response, and on this endpoint it is measurably NOT the request's order:
    see the module docstring. A resolver that assumed it would attach the
    wrong heading to the right identifier.
    """
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchSummaryInput
    from system_03_search_agent.tools.ncbi_eutils_actions import summary

    try:
        result = await summary(
            NcbiEfetchSummaryInput(action="summary", db="mesh", ids=uids)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("MeSH summary failed: %s", type(exc).__name__)
        return {}

    if result.status != "ok":
        return {}

    headings: dict[str, str] = {}
    for record in result.records:
        descriptor_id = _normalize(str(record.fields.get("ds_meshui") or ""))
        heading = _preferred_heading(record.fields.get("ds_meshterms"))
        if descriptor_id and heading:
            headings[descriptor_id] = heading
    return headings


def _headroom_allows_resolution() -> bool:
    """True when this query can afford the two calls, or has no budget bound.

    `calls_made()` returns None when no query scope is bound, which is the
    case in a unit test and on any call path outside a run. That is treated
    as "no ceiling to respect", never as "no headroom": a None reading must
    not silently disable resolution everywhere off the query path.
    """
    from system_03_search_agent.harness.call_budget import (
        MAX_LAYER_2_3_CALLS_PER_QUERY,
        calls_made,
    )

    made = calls_made()
    if made is None:
        return True
    return MAX_LAYER_2_3_CALLS_PER_QUERY - made >= _CALLS_REQUIRED


async def resolve_descriptor_ids(
    descriptor_ids: Sequence[str],
) -> dict[str, str | None]:
    """Map each MeSH descriptor id to its preferred heading, or to None.

    Accepts bare descriptor ids (`D000818`) or full CURIEs
    (`MeSH:D000818`), and keys the result by whatever form was passed in, so
    a caller never has to normalize twice.

    EVERY id passed in appears in the returned mapping. An id that could not
    be resolved maps to `None` rather than being dropped: a dropped id
    disappears from the answer with no disclosure, which is the silent
    version of the defect this module exists to fix.

    Two live calls at most, whatever the input size. See the module
    docstring for the measurement.
    """
    resolved: dict[str, str | None] = {}
    pending: dict[str, list[str]] = {}

    for raw in descriptor_ids:
        if raw in resolved or raw in pending:
            continue
        local = _normalize(str(raw))
        if local is None:
            resolved[raw] = None
            continue
        hit, heading = _cache_get(local)
        if hit:
            resolved[raw] = heading
            continue
        pending.setdefault(local, []).append(raw)

    if not pending:
        return resolved

    # The headroom check sits AFTER the cache has answered what it can, so a
    # warm process is never declined for a budget it is not about to spend.
    if not _headroom_allows_resolution():
        logger.info("MeSH resolution skipped: fewer than two Layer 2 calls remain")
        for raws in pending.values():
            for raw in raws:
                resolved[raw] = None
        return resolved

    # The cap applies to what is actually LOOKED UP, for the same reason.
    # Ids beyond the batch resolve to None and keep their identifiers, which
    # is this module's ordinary degradation rather than a special case.
    ordered = sorted(pending)
    lookup_ids = _batch_for_one_term(ordered)
    for local in ordered[len(lookup_ids):]:
        for raw in pending[local]:
            resolved[raw] = None

    uids = await _search_uids(lookup_ids)
    headings = await _summary_headings(uids) if uids else {}

    for local in lookup_ids:
        heading = headings.get(local)
        _cache_put(local, heading)
        for raw in pending[local]:
            resolved[raw] = heading

    return resolved
