"""Resolve MedGen concept ids to human-readable disease names, over Layer 2.

Build phase 6.2, ticket T-6.2-02. This module exists because of a data
defect it deliberately does not fix.

## The problem, measured rather than assumed

Disease nodes in the Layer 1 graph carry the SOURCE VOCABULARY in `name`,
not a disease name. Sampled across 25 nodes on 2026-08-31 it takes three
distinct values, `MedGen`, `MeSH` and `SNOMEDCT_US`; Gene nodes are fine,
23 distinct values across 23 nodes. `core.graph._is_vocabulary_token_artifact`
already detects those corrupted values and refuses to state them, which is
correct and stays exactly as it is. What the graph offers instead is the
CURIE, so an answer about BRCA1's associated diseases read:

    The knowledge graph associates the gene BRCA1 with four disease
    records: MedGen:C0346153, MedGen:C2676676, MedGen:C3280442, and
    MedGen:C4554406.

Grounded, cited, trust-gated, and useless to a researcher.

The upstream fix is a MedGen ETL re-ingest in the System 1 and 2
repository. It is not this repository's to make (`file-protection.md`) and
is not scheduled. This module is the query-time workaround: it reads the
name from the live MedGen record and lets the answer state it as the
Layer 2 fact that it is.

## Two calls, not one, and not two per id

`docs/build/UI_feedback.md` and the phase 6 continuation prompt both said `ncbi_efetch`
already resolves these, so the fix was "closer to wiring than to building",
and both told the reader to verify before promising it. Verified 2026-09-01:

    ESummary keyed on a concept id is REJECTED outright.
    {"error":"Invalid uid C0346153 at position= 0","result":{"uids":[]}}

Resolution needs ESearch on `<id>[ConceptId]` to get a numeric UID, then
ESummary on that UID. The naive shape is 2N calls for N diseases, which on
a path already taking 12 to 14 seconds is not acceptable.

This module issues TWO calls TOTAL regardless of N, verified live before it
was written:

- One ESearch whose term ORs every `[ConceptId]` clause together.
- One ESummary over every returned UID at once.

The mapping back from UID to concept id does NOT rely on result ordering,
which would be a silent correctness bug the day NCBI reorders: MedGen's
own ESummary payload carries `conceptid` alongside `title`, and it is
already on this repository's `medgen` field allowlist
(`tools/ncbi_eutils_actions.py`), so each title is matched to the id it
belongs to by reading the record.

## What this module will not do

It NEVER invents a name. An id MedGen does not hold, an ESearch that finds
nothing, an ESummary missing a title, a transport failure, a rate-limit
refusal: every one of them maps that id to `None`, and the caller keeps the
identifier. Under-resolution is cheap and a wrong disease name is not,
which is `production-standards.md`'s cite-or-refuse ethos applied one layer
down. `test_answer_readability_premise.py`'s arm A4 pins exactly this.

It also never raises into the agent loop. A failure here must degrade an
answer from readable to unreadable, never from readable to absent: the
previous behaviour, four CURIEs, is this module's failure mode by
construction.

## Caching, and the honest limit of it

The cache is a bounded in-process TTL map. It is NOT the Section 4.3 Redis
response cache, which is specified and not yet built, and it is deliberately
not a second implementation of one: when that cache lands, this map should
be deleted rather than kept alongside it.

So the guarantee is per-process and per-deployment-instance. A repeated
question in one process pays nothing; the same question on a cold process
pays the two calls again. Stated rather than implied, because "resolution
is cached" reads stronger than what this actually provides.

TTL is one week. A MedGen concept's preferred title is about as stable as a
gene name, and this is the "stable field" class the three-layer
architecture already assigns a long TTL.

## Budgets

Every call goes through `tools.ncbi_eutils_actions`, so it inherits the
`eutils` token bucket, the bounded wait queue, and build phase 6.0's
per-query Layer 2/3 call ceiling with no code here. That is the reason this
module calls the tool actions rather than reaching for `urllib`: a private
HTTP path would be invisible to all three, and to the audit log.

Depends on:
    - system_03_search_agent.tools.ncbi_eutils_actions (search, summary)
    - system_03_search_agent.tools.ncbi_efetch_schemas (the two input models)

Reads:
    - Live MedGen over E-utilities, through the shared rate pool.

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
    "MEDGEN_CONCEPT_ID",
    "readable_disease_name",
    "reset_cache_for_tests",
    "resolve_concept_ids",
]

# A MedGen local id: `C` or `CN` then digits. Deliberately the same shape
# `tools/cypher_provenance.py` already enforces for this prefix, derived
# there from an exhaustive census of all 200,845 Disease rows rather than
# from a sample. Anything else is not sent to NCBI at all: an id this
# pattern rejects cannot be a MedGen concept, so a lookup for it would
# spend a shared rate-pool slot to learn nothing.
MEDGEN_CONCEPT_ID = re.compile(r"^CN?\d+$", re.ASCII)

# Bounds. `_MAX_IDS_PER_CALL` caps how many ids one resolution may ask
# about, so a query that somehow reached hundreds of Disease rows cannot
# build an unbounded ESearch term. It sits under the `retmax` ceiling of
# 500 the tool's own schema enforces, with room to spare, because the term
# grows with N too and `term` is capped at 500 characters.
_MAX_IDS_PER_CALL = 25
_MAX_TITLE_CHARS = 300

# One week, the stable-field TTL class. See the module docstring.
_CACHE_TTL_S = 7 * 24 * 60 * 60
_MAX_CACHE_ENTRIES = 2048

# concept id -> (title or None, monotonic expiry). A NEGATIVE result is
# cached too, deliberately: an id MedGen does not hold will not start
# existing within the TTL, and not caching it means every repeat of the
# same question pays two calls to re-learn the same nothing.
_cache: dict[str, tuple[str | None, float]] = {}


def reset_cache_for_tests() -> None:
    """Clear the resolution cache. Test-only; production never calls this."""
    _cache.clear()


def _cache_get(concept_id: str) -> tuple[bool, str | None]:
    """Return `(hit, title)`. `hit` distinguishes a cached None from a miss.

    Returning a bare `None` for both would make a cached negative result
    indistinguishable from an absent entry, so every repeat of an
    unresolvable id would re-issue the lookup the cache exists to avoid.
    """
    entry = _cache.get(concept_id)
    if entry is None:
        return False, None
    title, expires_at = entry
    if time.monotonic() >= expires_at:
        _cache.pop(concept_id, None)
        return False, None
    return True, title


def _cache_put(concept_id: str, title: str | None) -> None:
    if len(_cache) >= _MAX_CACHE_ENTRIES:
        # Evict the entry closest to expiry rather than clearing the map.
        # A blunt clear on a busy process throws away every warm entry at
        # once and turns a bounded cache into a periodic stall.
        oldest = min(_cache, key=lambda key: _cache[key][1])
        _cache.pop(oldest, None)
    _cache[concept_id] = (title, time.monotonic() + _CACHE_TTL_S)


def _normalize(raw: str) -> str | None:
    """Reduce `MedGen:C0346153` or `C0346153` to the bare local id.

    Returns None for anything that is not a MedGen concept id, including
    another vocabulary's CURIE. A MeSH or MONDO id is a real identifier
    this module simply cannot resolve, and treating it as a MedGen id would
    send a lookup guaranteed to miss.
    """
    text = raw.strip()
    if not text:
        return None
    if ":" in text:
        prefix, _, local = text.partition(":")
        if prefix.strip() != "MedGen":
            return None
        text = local.strip()
    return text if MEDGEN_CONCEPT_ID.match(text) else None


async def _search_uids(concept_ids: list[str]) -> list[str]:
    """One ESearch over every concept id at once. Never raises."""
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchSearchInput
    from system_03_search_agent.tools.ncbi_eutils_actions import search

    term = " OR ".join(f"{cid}[ConceptId]" for cid in concept_ids)
    try:
        result = await search(
            NcbiEfetchSearchInput(
                action="search",
                db="medgen",
                term=term,
                retmax=min(len(concept_ids) * 2, 500),
            )
        )
    except Exception as exc:  # noqa: BLE001
        # Deliberately broad, and deliberately not re-raised. This module's
        # contract is that a resolution failure degrades the answer to the
        # identifiers it already had. Letting any exception class escape
        # here would turn a cosmetic shortfall into a failed query, which
        # is strictly worse than the defect being fixed.
        logger.warning("MedGen concept search failed: %s", type(exc).__name__)
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


async def _summary_titles(uids: list[str]) -> dict[str, str]:
    """One ESummary over every UID at once, keyed by concept id.

    Keyed on the payload's own `conceptid` rather than on the position of
    the record in the list. Order is not a documented property of an
    ESummary response, and a resolver that assumed it would attach the
    wrong disease name to the right identifier the day NCBI reordered,
    which is the worst failure available to this module: a confident,
    citable, wrong answer.
    """
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchSummaryInput
    from system_03_search_agent.tools.ncbi_eutils_actions import summary

    try:
        result = await summary(
            NcbiEfetchSummaryInput(action="summary", db="medgen", ids=uids)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("MedGen summary failed: %s", type(exc).__name__)
        return {}

    if result.status != "ok":
        return {}

    titles: dict[str, str] = {}
    for record in result.records:
        concept_id = _normalize(str(record.fields.get("conceptid") or ""))
        title = record.fields.get("title")
        if concept_id and isinstance(title, str) and title.strip():
            titles[concept_id] = title.strip()[:_MAX_TITLE_CHARS]
    return titles


async def resolve_concept_ids(
    concept_ids: Sequence[str],
) -> dict[str, str | None]:
    """Map each MedGen concept id to its disease name, or to None.

    Accepts bare local ids (`C0346153`) or full CURIEs
    (`MedGen:C0346153`), and keys the result by whatever form was passed
    in, so a caller never has to normalize twice.

    EVERY id passed in appears in the returned mapping. An id that could
    not be resolved maps to `None` rather than being dropped: a dropped id
    disappears from the answer with no disclosure, which is the silent
    version of the defect this module exists to fix.
    """
    resolved: dict[str, str | None] = {}
    pending: dict[str, list[str]] = {}

    for raw in concept_ids:
        if raw in resolved or raw in pending:
            continue
        local = _normalize(str(raw))
        if local is None:
            resolved[raw] = None
            continue
        hit, title = _cache_get(local)
        if hit:
            resolved[raw] = title
            continue
        pending.setdefault(local, []).append(raw)

    if not pending:
        return resolved

    # The cap applies to what is actually LOOKED UP, after the cache has
    # answered what it can, so a warm process is never throttled by a
    # ceiling it is not spending anything against. Ids beyond the cap
    # resolve to None and keep their identifiers, which is this module's
    # ordinary degradation rather than a special case.
    lookup_ids = sorted(pending)[:_MAX_IDS_PER_CALL]
    over_cap = sorted(pending)[_MAX_IDS_PER_CALL:]
    for local in over_cap:
        for raw in pending[local]:
            resolved[raw] = None

    uids = await _search_uids(lookup_ids)
    titles = await _summary_titles(uids) if uids else {}

    for local in lookup_ids:
        title = titles.get(local)
        _cache_put(local, title)
        for raw in pending[local]:
            resolved[raw] = title

    return resolved


# UI fix set 9, item 9.8 (2026-09-13). MedGen carries many titles in the
# inverted OMIM form, "Breast-ovarian cancer, familial, susceptibility to, 1",
# which a reader sees in prose as "susceptibility to, 1". The product owner
# asked for names that read naturally, and the brief bounds how: a readable
# form is allowed only as a DETERMINISTIC transformation of the record's own
# title, never a model's rewording.
#
# So this is a closed set of reorderings, and every word of the result is a
# word of the title. A title with any comma-separated part this table does not
# recognise is returned UNCHANGED, because guessing at an unknown inversion is
# how a disease name would acquire a meaning its record does not give it.
_PREFIX_QUALIFIERS = frozenset(
    {
        "familial",
        "hereditary",
        "juvenile",
        "congenital",
        "autosomal dominant",
        "autosomal recessive",
        "x-linked",
        "early-onset",
        "late-onset",
        "adult-onset",
    }
)
_SUSCEPTIBILITY_PART = "susceptibility to"
_SUSCEPTIBILITY_NUMBER = re.compile(r"^\d{1,3}[A-Za-z]?$")
_SUFFIX_PART = re.compile(r"^(?:type|complementation group|group)\s+\S{1,8}$", re.IGNORECASE)


def readable_disease_name(title: str) -> str:
    """Reorder an inverted MedGen title into reading order, or return it as is.

    "Breast-ovarian cancer, familial, susceptibility to, 1" becomes
    "Familial breast-ovarian cancer susceptibility 1";
    "Pancreatic cancer, susceptibility to, 4" becomes
    "Pancreatic cancer susceptibility 4";
    "Fanconi anemia, complementation group S" becomes
    "Fanconi anemia complementation group S". A title with no comma, or with
    any part outside the recognised qualifiers, comes back unchanged.
    """
    parts = [part.strip() for part in title.split(",")]
    if len(parts) < 2 or any(not part for part in parts):
        return title
    base, rest = parts[0], parts[1:]
    prefixes: list[str] = []
    suffixes: list[str] = []
    for part in rest:
        lowered = part.lower()
        if lowered in _PREFIX_QUALIFIERS:
            prefixes.append(lowered)
        elif lowered == _SUSCEPTIBILITY_PART:
            suffixes.append("susceptibility")
        elif (
            _SUSCEPTIBILITY_NUMBER.match(part)
            and suffixes
            and suffixes[-1] == "susceptibility"
        ) or _SUFFIX_PART.match(part):
            suffixes.append(part)
        else:
            return title
    head = base
    if prefixes:
        # Lower-case the base's first letter only when it reads as an ordinary
        # capitalised word, so an acronym such as "MODY" keeps its case.
        if len(base) > 1 and base[0].isupper() and base[1].islower():
            head = base[0].lower() + base[1:]
        head = " ".join(prefixes) + " " + head
    readable = " ".join([head, *suffixes])
    if base[:1].isupper():
        readable = readable[:1].upper() + readable[1:]
    return readable
