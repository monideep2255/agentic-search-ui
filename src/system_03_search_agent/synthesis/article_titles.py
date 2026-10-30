"""Name a graph paper by its PubMed title, read live over EFetch.

The sibling of `synthesis/mesh_terms.py` and `synthesis/disease_names.py`,
for the same kind of defect: a record the knowledge graph found that the
reader sees only as an identifier.

## The problem

A gene question that asks for papers ("Which papers in the graph mention
CFTR, and what do they cover?", golden question G-021) reaches dozens of
`Article` rows. An `Article` row's `name` is the paper's title, and the
title is untrusted free text from a publication, so `core.graph`'s
`_sanitized_citeable_row` empties the row's `fields` before it becomes a
finding. That quarantine is a security control and stays exactly as it is.
Its cost is that each paper becomes a `curie_fallback` finding whose only
citable value is `PMID:10075921`: Researcher lists 54 bare PMIDs and Plain
language lists 54 rows that each read "Published paper".

## What this module does

It reads each title from PubMed's own record, through the `ncbi_efetch`
tool's PubMed EFetch (`rettype` abstract, `retmode` xml), the one verified
per-id path, and rewrites the finding the way phase 6.2 rewrote a MedGen
name: the finding becomes a live Layer 2 fact named "title", still cited to
the same PubMed page. The title is untrusted text all over again, so it is
cleaned to one printable line, a marker-shaped bracket is defused, and a
title the fetch cut or one over the cap is withheld rather than clipped.

## What it will not do

- It NEVER invents a title. A transport error, a rate-limit refusal, the
  20-call ceiling, a timeout, a malformed body, a missing record and an
  empty title each map the paper to `None`, and the finding keeps its PMID
  exactly as before.
- It never raises into the agent loop.
- It joins by the PMID on the returned record (`NcbiEfetchRecord.id`),
  never by position. A record that is not one of the requested PMIDs is
  ignored, and a PMID returned twice with different titles is withheld.
- It never turns the abstract into anything. EFetch returns it and this
  module discards it.

## Retracted papers (card 146)

The same EFetch carries PubMed's own publication type. A record PubMed
types "Retracted Publication" (`ncbi_eutils_actions.record_is_retracted`)
is remembered as retracted beside its title, at no extra request.
`publication_curies_to_check` adds the PubTator3 papers whose PubMed record
this question did not read to the same lookup, and `mark_retracted_papers`
sets `SynthFinding.retracted` on every paper finding on a retracted paper's
page. A paper whose record could not be read is never marked: its status is
unknown, and unknown is not retracted.

## Calls, timing and budget

At most two requests of at most 50 PMIDs run concurrently, covering the
display list in `ref_index` order. Every call goes through
`tools.ncbi_eutils_actions.fetch`, so it inherits the shared rate pool, the
per-query Layer 2 and 3 ceiling (a request at the ceiling is never made)
and the audit log. The whole lookup waits at most 15 seconds, the tool's
own per-call budget.

The result is cached per process, so a lookup started during Act is found
by Write with no second request.

Depends on:
    - system_03_search_agent.tools.ncbi_eutils_actions (fetch)
    - system_03_search_agent.tools.ncbi_efetch_schemas (the input model)
    - system_03_search_agent.harness.call_budget (calls_made, the ceiling)
    - system_03_search_agent.synthesis.findings (SynthFinding)

Reads:
    - Live PubMed over E-utilities, through the shared rate pool.

Writes:
    - Nothing. An in-process cache only.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Sequence
from dataclasses import replace

from system_03_search_agent.contracts.events import source_page_key
from system_03_search_agent.synthesis.findings import SynthFinding

logger = logging.getLogger(__name__)

__all__ = [
    "ARTICLE_CURIE",
    "PAPER_ENTITY_TYPES",
    "apply_resolved_article_titles",
    "article_curies_to_name",
    "clean_article_title",
    "mark_retracted_papers",
    "publication_curies_to_check",
    "reset_cache_for_tests",
    "resolve_article_titles",
    "retracted_article_curies",
]

# `PMID:` then ASCII digits, the exact shape the graph's Article CURIE has.
# `re.ASCII` is load-bearing, as in `mesh_terms.MESH_DESCRIPTOR_ID`: without
# it `\d` accepts every Unicode decimal digit.
ARTICLE_CURIE = re.compile(r"^PMID:(\d{1,10})$", re.ASCII)

_ARTICLE_ENTITY_TYPE = "Article"
#: Card 146: a PubTator3 paper row (`core.graph`, card 134) and the field
#: holding its PMID.
_PUBLICATION_ENTITY_TYPE = "Publication"
_PUBLICATION_PMID_FIELD = "pmid"
#: Card 146: the record types that ARE a paper: a graph `Article`, a
#: PubTator3 `Publication` and a live PubMed record (`pubmed`). Only these
#: are marked retracted; an edge or gene row citing the same page is not.
PAPER_ENTITY_TYPES: frozenset[str] = frozenset(
    {_ARTICLE_ENTITY_TYPE, _PUBLICATION_ENTITY_TYPE, "pubmed"}
)
_PMID_DIGITS = re.compile(r"^\d{1,10}$", re.ASCII)
_GRAPH_LAYER = "layer_1_graph"

# The layer, tool and field a named paper carries, the same pair a resolved
# MedGen name carries (`findings._RESOLVED_NAME_*`), so the layer authority
# gate holds: the title was read live, so the finding says layer 2.
_TITLE_LAYER = "layer_2_api"
_TITLE_TOOL = "ncbi_efetch"
_TITLE_FIELD = "title"

#: The PMIDs one EFetch request carries (`NcbiEfetchFetchInput.ids`) and the
#: requests one lookup makes at most.
_IDS_PER_REQUEST = 50
_MAX_REQUESTS = 2

#: The tool's own per-call wait, from `tool-call-budgets.md`.
_LOOKUP_TIMEOUT_S = 15.0

#: A title over this is withheld, never clipped: half a title is not the
#: paper's name. Real PubMed titles measured at most 214 characters.
_MAX_TITLE_CHARS = 500

#: What `ncbi_eutils_actions._cap_text` appends to a value it cut.
_CUT_SUFFIX = " [truncated]"

# A bracket pair that reads as a citation marker: `[3]`, `[3#1]` or
# `[3: "words"]`, the shapes `synthesis.grounding` treats as markers. A real
# bracketed title ("[Gene therapy in 2019]") does not match.
_MARKER_SHAPED = re.compile(r"\[(\s*\d{1,3}\s*(?:[#:][^\]]{0,620})?)\]")

# A title that is only a bracketed placeholder, with or without a full stop:
# PubMed's "[Not Available]." and "[In Process Citation]" stand where a title
# is missing. A real title that merely starts with a bracketed translation
# ("[Translated title] Fibrose kystique") does not match.
_BRACKETED_ONLY = re.compile(r"^\[[^\[\]]*\]\s?\.?$")

_ONE_WEEK_S = 7 * 24 * 60 * 60
#: A failure is remembered briefly, so Write does not repeat in full the
#: wait that Act's lookup just spent, and a later question retries soon.
_FAILURE_TTL_S = 60.0
_MAX_CACHE_ENTRIES = 4096

# pmid -> (title or None, monotonic expiry).
_cache: dict[str, tuple[str | None, float]] = {}
# Card 146: pmid -> monotonic expiry, for a record that was read and that
# PubMed types a retracted publication, and no other. It expires with the
# title entry read in the same request.
_retracted: dict[str, float] = {}


def reset_cache_for_tests() -> None:
    """Clear the cache. Test-only; production never calls this."""
    _cache.clear()
    _retracted.clear()


def _cache_get(pmid: str) -> tuple[bool, str | None]:
    entry = _cache.get(pmid)
    if entry is None:
        return False, None
    title, expires_at = entry
    if time.monotonic() >= expires_at:
        _cache.pop(pmid, None)
        return False, None
    return True, title


def _cache_put(pmid: str, title: str | None, ttl_s: float, retracted: bool = False) -> None:
    if len(_cache) >= _MAX_CACHE_ENTRIES:
        oldest = min(_cache, key=lambda key: _cache[key][1])
        _cache.pop(oldest, None)
        _retracted.pop(oldest, None)
    expires_at = time.monotonic() + ttl_s
    _cache[pmid] = (title, expires_at)
    if retracted:
        _retracted[pmid] = expires_at
    else:
        _retracted.pop(pmid, None)


def clean_article_title(raw: object) -> str | None:
    """A PubMed title as one printable line, or None when it must be withheld.

    Untrusted text (`ai-security-standards.md`). Every non-printable
    character (newline, tab, control character, a bidi override, a
    zero-width space) becomes a space and whitespace collapses, the rule of
    `ncbi_eutils_actions.clean_clinical_feature_name`, so a newline cannot
    forge a numbered line in the findings block. A marker-shaped bracket
    pair becomes parentheses, so a title cannot carry `[3]` into prose where
    it would read as a citation of finding 3.

    Apart from those two rules, every character is kept as PubMed writes
    it, angle brackets included: "c.3140-26A>G", "<5 years", "Lep <ob>"
    and a tag-shaped "</question>" alike (card 125, 2026-10-17). A title cannot close or open
    a block of the writer prompt because `findings.build_synth_messages`
    names every block tag with a random suffix drawn per prompt, not
    because this function rewrites the title.

    None for a non-string, a blank, a title the fetch already cut, a title
    over `_MAX_TITLE_CHARS`, and a title that is only a bracketed
    placeholder ("[Not Available]."). A title is never truncated here.
    """
    if not isinstance(raw, str) or raw.endswith(_CUT_SUFFIX):
        return None
    printable = "".join(ch if ch.isprintable() else " " for ch in raw)
    collapsed = " ".join(printable.split())
    if not collapsed or len(collapsed) > _MAX_TITLE_CHARS:
        return None
    if _BRACKETED_ONLY.match(collapsed):
        return None
    return _MARKER_SHAPED.sub(r"(\1)", collapsed)


def article_curies_to_name(synth_findings: Sequence[SynthFinding]) -> list[str]:
    """The `PMID:<n>` CURIEs of the graph papers shown only by their number.

    A finding qualifies only when it is a graph `Article` row that fell back
    to its identifier. In `ref_index` order, deduplicated, so a request
    covers the prompt slice first.
    """
    curies: list[str] = []
    for finding in sorted(synth_findings, key=lambda f: f.ref_index):
        if (
            finding.curie_fallback
            and finding.entity_type == _ARTICLE_ENTITY_TYPE
            and finding.layer == _GRAPH_LAYER
            and ARTICLE_CURIE.match(finding.curie)
            and finding.curie not in curies
        ):
            curies.append(finding.curie)
    return curies


def _requests_allowed() -> int:
    """How many requests this query can still afford, at most `_MAX_REQUESTS`.

    `calls_made()` is None when no query scope is bound (a unit test, or any
    path outside a run): no ceiling to respect, never "no headroom".
    """
    from system_03_search_agent.harness.call_budget import (
        MAX_LAYER_2_3_CALLS_PER_QUERY,
        calls_made,
    )

    made = calls_made()
    if made is None:
        return _MAX_REQUESTS
    return max(0, min(_MAX_REQUESTS, MAX_LAYER_2_3_CALLS_PER_QUERY - made))


async def _fetch_titles(pmids: list[str]) -> dict[str, tuple[str | None, bool]] | None:
    """One EFetch request for up to 50 PMIDs, keyed by the record's own PMID.

    Each PMID maps to its title (or None) and whether PubMed types the
    record a retracted publication (card 146). None when the request
    failed, so the caller can tell a failure from a PMID PubMed did not
    return. Never raises.
    """
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchFetchInput
    from system_03_search_agent.tools.ncbi_eutils_actions import fetch, record_is_retracted

    try:
        result = await fetch(
            NcbiEfetchFetchInput(
                action="fetch",
                db="pubmed",
                ids=pmids,
                rettype="abstract",
                retmode="xml",
            )
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        # Deliberately broad and not re-raised: a lookup failure degrades a
        # paper from titled to numbered, never from listed to absent.
        # `CallBudgetExceededError` arrives through exactly this path.
        logger.warning("PubMed title fetch failed: %s", type(exc).__name__)
        return None

    if result.status not in ("ok", "empty"):
        logger.warning("PubMed title fetch returned status %s", result.status)
        return None

    wanted = set(pmids)
    seen: dict[str, str | None] = {}
    retracted: set[str] = set()
    conflicted: set[str] = set()
    for record in result.records:
        pmid = (record.id or "").strip()
        if pmid not in wanted:
            continue
        title = clean_article_title(record.fields.get("title"))
        if pmid in seen and seen[pmid] != title:
            conflicted.add(pmid)
        seen.setdefault(pmid, title)
        if record_is_retracted(record.fields):
            retracted.add(pmid)
    for pmid in conflicted:
        seen[pmid] = None
    return {pmid: (title, pmid in retracted) for pmid, title in seen.items()}


async def resolve_article_titles(curies: Sequence[str]) -> dict[str, str | None]:
    """Map each `PMID:<n>` CURIE to its PubMed title, or to None.

    EVERY CURIE passed in appears in the result: one that could not be named
    maps to None rather than being dropped, so the caller keeps the PMID.
    A CURIE that is not `PMID:<digits>` maps to None without a request.
    Never raises.
    """
    resolved: dict[str, str | None] = {}
    pending: list[str] = []
    for curie in curies:
        if curie in resolved or curie in pending:
            continue
        match = ARTICLE_CURIE.match(str(curie))
        if match is None:
            resolved[curie] = None
            continue
        hit, title = _cache_get(match.group(1))
        if hit:
            resolved[curie] = title
            continue
        pending.append(curie)

    if not pending:
        return resolved

    # The ceiling is checked AFTER the cache has answered what it can, so a
    # warm process is never declined for a budget it is not about to spend.
    allowed = _requests_allowed()
    batches = [
        pending[start : start + _IDS_PER_REQUEST]
        for start in range(0, len(pending), _IDS_PER_REQUEST)
    ][: min(_MAX_REQUESTS, allowed)]
    looked_up = {curie for batch in batches for curie in batch}
    for curie in pending:
        if curie not in looked_up:
            resolved[curie] = None
    if not batches:
        logger.info("PubMed title lookup skipped: no Layer 2 call remains")
        return resolved

    async def _one(batch: list[str]) -> dict[str, tuple[str | None, bool]] | None:
        ids = [ARTICLE_CURIE.match(curie).group(1) for curie in batch]  # type: ignore[union-attr]
        try:
            return await asyncio.wait_for(_fetch_titles(ids), timeout=_LOOKUP_TIMEOUT_S)
        except TimeoutError:
            logger.warning("PubMed title fetch timed out")
            return None

    outcomes = await asyncio.gather(*(_one(batch) for batch in batches))
    for batch, outcome in zip(batches, outcomes, strict=True):
        for curie in batch:
            pmid = curie.split(":", 1)[1]
            if outcome is None:
                resolved[curie] = None
                _cache_put(pmid, None, _FAILURE_TTL_S)
                continue
            title, retracted = outcome.get(pmid, (None, False))
            resolved[curie] = title
            _cache_put(pmid, title, _ONE_WEEK_S if title else _FAILURE_TTL_S, retracted)
    return resolved


def publication_curies_to_check(
    synth_findings: Sequence[SynthFinding], pages_read: frozenset[str] | set[str]
) -> list[str]:
    """Card 146: `PMID:<n>` for each PubTator3 paper whose PubMed record this
    question did not read, so `resolve_article_titles` reads its publication
    type in the lookup it already makes.

    PubTator3's response carries no publication type. A paper's PubMed record
    is normally read beside it (`breadth_plan.plan_literature_follow_up`
    plans both on one id list), so a page in `pages_read` (keyed by
    `source_page_key`) needs no lookup. In `ref_index` order, deduplicated.
    """
    curies: list[str] = []
    for finding in sorted(synth_findings, key=lambda f: f.ref_index):
        if (
            finding.entity_type != _PUBLICATION_ENTITY_TYPE
            or finding.field != _PUBLICATION_PMID_FIELD
            or not _PMID_DIGITS.match(finding.field_value.strip())
            or source_page_key(finding.source_url) in pages_read
        ):
            continue
        curie = f"PMID:{finding.field_value.strip()}"
        if curie not in curies:
            curies.append(curie)
    return curies


def retracted_article_curies(curies: Sequence[str]) -> frozenset[str]:
    """Card 146: of `curies`, the ones whose PubMed record, as this module last
    read it, PubMed types a retracted publication. Reads the cache only and
    makes no request: call it after `resolve_article_titles` on the same
    CURIEs. A record never read, or whose read failed, is not in the result.
    """
    retracted: set[str] = set()
    for curie in curies:
        match = ARTICLE_CURIE.match(str(curie))
        if match is None:
            continue
        expires_at = _retracted.get(match.group(1))
        if expires_at is not None and time.monotonic() < expires_at:
            retracted.add(curie)
    return frozenset(retracted)


def _paper_curie(finding: SynthFinding) -> str:
    """The `PMID:<n>` a paper finding names, or "" for any other finding."""
    if finding.entity_type == _ARTICLE_ENTITY_TYPE and ARTICLE_CURIE.match(finding.curie):
        return finding.curie
    if (
        finding.entity_type == _PUBLICATION_ENTITY_TYPE
        and finding.field == _PUBLICATION_PMID_FIELD
        and _PMID_DIGITS.match(finding.field_value.strip())
    ):
        return f"PMID:{finding.field_value.strip()}"
    return ""


def mark_retracted_papers(
    synth_findings: list[SynthFinding],
    retracted_pages: frozenset[str] | set[str],
    retracted_curies: frozenset[str] | set[str],
) -> list[SynthFinding]:
    """Card 146: mark every paper finding on a retracted paper's page.

    A page is retracted when it is in `retracted_pages` (the live PubMed
    records this question read, keyed by `source_page_key`), when a finding
    on it already carries the flag, or when a paper finding on it names a
    CURIE in `retracted_curies` (the lookup's own read). Every finding of a
    `PAPER_ENTITY_TYPES` type on such a page is marked, so a paper the graph,
    PubTator3 and PubMed each found shows the tag however its row folds.
    Every other finding, and every finding when nothing is retracted, is
    returned unchanged.
    """
    pages = set(retracted_pages)
    for finding in synth_findings:
        if finding.entity_type not in PAPER_ENTITY_TYPES:
            continue
        if finding.retracted or (_paper_curie(finding) in retracted_curies):
            pages.add(source_page_key(finding.source_url))
    pages.discard("")
    if not pages:
        return synth_findings
    return [
        replace(finding, retracted=True)
        if (
            not finding.retracted
            and finding.entity_type in PAPER_ENTITY_TYPES
            and source_page_key(finding.source_url) in pages
        )
        else finding
        for finding in synth_findings
    ]


def apply_resolved_article_titles(
    synth_findings: list[SynthFinding],
    titles: dict[str, str | None],
) -> list[SynthFinding]:
    """Replace a bare-PMID graph paper with its title, as a Layer 2 fact.

    Only a finding `article_curies_to_name` would pick is rewritten, and
    only when `titles` holds a title for its CURIE. The finding keeps its
    `curie`, `source_url`, `ref_index`, `citation_id`, `entity_type` and
    `call_id`: the join keys the grounding pass and the citation layer use.
    The layer changes to `layer_2_api` and the tool to `ncbi_efetch`
    because the title was read live (the layer authority gate), so the
    paper's citation moves from the knowledge graph group to the live APIs
    group in Sources, as MedGen names did in phase 6.2.

    A paper that did not resolve is returned UNCHANGED, hedge and all.
    """
    if not titles:
        return synth_findings
    targets = set(article_curies_to_name(synth_findings))
    # A paper that already has a live PubMed title row on the same page stays
    # on its PMID: `one_finding_per_record` folds a page's rows only when
    # their field names differ, so two `title` rows would list it twice.
    # Left as `curie` beside the live `title`, develop's fold shows it once.
    live_title_pages = {
        (f.source_url or "").strip()
        for f in synth_findings
        if f.field == _TITLE_FIELD and f.layer != _GRAPH_LAYER and f.source_url
    }
    rewritten: list[SynthFinding] = []
    for finding in synth_findings:
        title = titles.get(finding.curie)
        if (
            finding.curie not in targets
            or not title
            or (finding.source_url or "").strip() in live_title_pages
        ):
            rewritten.append(finding)
            continue
        rewritten.append(
            replace(
                finding,
                layer=_TITLE_LAYER,
                tool=_TITLE_TOOL,
                field=_TITLE_FIELD,
                field_value=title,
                value_is_suspect=False,
                curie_fallback=False,
                name_resolved=True,
            )
        )
    return rewritten
