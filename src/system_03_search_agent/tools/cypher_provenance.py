"""Layer 1 provenance and source URL mapping, T-2.1-05.

Maps a graph CURIE to its human-facing NCBI record page and shapes a raw
graph row into the `CypherQueryRow` dict shape (Section 6.1, Section 9).
This module never fabricates a URL: a CURIE prefix with no verified,
host-pinned NCBI record page returns None rather than a guessed path, and
every URL this module emits, whether newly derived or an existing stored
value, is checked against `NCBI_RECORD_URL_PATTERN` before it is returned.

Five of the nine CURIE prefixes in `graph_schema_constants.CURIE_PREFIXES`
map to a documented NCBI record page and are handled below: NCBIGene,
ClinVar, MedGen, PMID, NCBITaxon. The remaining four, GO, MeSH, HP, and
MONDO, are not NCBI-hosted databases. Gene Ontology, the Human Phenotype
Ontology, and Mondo are maintained outside NCBI entirely (the OBO Foundry
and the Monarch Initiative), so no host-pinned `ncbi.nlm.nih.gov` record
page exists for them at all; inventing one would be exactly the fabricated
citation this module exists to prevent. `source_url_for_curie` returns
None for all four, not a guessed external host and not a loosened pattern.
This is a documented, deliberate gap, not an oversight: if a verified
NCBI-hosted or otherwise host-pinned record page for one of these four is
confirmed later, add it here as a new mapping entry, never by loosening
`NCBI_RECORD_URL_PATTERN` itself.

Depends on:
    - system_03_search_agent.tools.graph_schema_constants
      (NCBI_RECORD_URL_PATTERN)

Reads:
    - Nothing at import time. Pure functions over their arguments.

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.tools.cypher_query (T-2.1-07, the integration
      ticket, not written by this builder)
"""

from __future__ import annotations

import re
import urllib.parse

from system_03_search_agent.tools.graph_schema_constants import (
    NCBI_RECORD_URL_PATTERN,
)

_HOST_PATTERN = re.compile(NCBI_RECORD_URL_PATTERN)

# One URL-building function per documented prefix. Each receives the
# already-quoted local id (the part of the CURIE after the first colon)
# and returns a URL string. Kept as callables, not an f-string template
# dict, so each prefix's path shape is explicit and independently
# reviewable.


def _ncbigene_url(local_id: str) -> str:
    return "https://www.ncbi.nlm.nih.gov/gene/" + local_id


def _clinvar_url(local_id: str) -> str:
    return "https://www.ncbi.nlm.nih.gov/clinvar/variation/" + local_id + "/"


def _medgen_url(local_id: str) -> str:
    return "https://www.ncbi.nlm.nih.gov/medgen/" + local_id


def _pmid_url(local_id: str) -> str:
    return "https://pubmed.ncbi.nlm.nih.gov/" + local_id + "/"


def _ncbitaxon_url(local_id: str) -> str:
    return "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=" + local_id


# GO, MeSH, HP, and MONDO are intentionally absent from this table. See the
# module docstring for why: no verified NCBI-hosted record page exists for
# any of the four, so they fall through to the None-returning default in
# `source_url_for_curie` rather than appearing here with a guessed path.
_CURIE_URL_BUILDERS: dict[str, "callable[[str], str]"] = {
    "NCBIGene": _ncbigene_url,
    "ClinVar": _clinvar_url,
    "MedGen": _medgen_url,
    "PMID": _pmid_url,
    "NCBITaxon": _ncbitaxon_url,
}


def _matches_host_pattern(url: str) -> bool:
    return bool(_HOST_PATTERN.match(url))


def source_url_for_curie(curie: str) -> str | None:
    """Map a graph CURIE to its NCBI record page, or None.

    Args:
        curie: a compact identifier of the form `prefix:local_id`, e.g.
            `NCBIGene:672`. A string with no colon, an empty prefix, or an
            empty local id is treated as malformed and returns None.

    Returns:
        The record page URL when the prefix is one of the five documented
        mappings and the resulting URL matches `NCBI_RECORD_URL_PATTERN`.
        None for every other prefix, including all nine CURIE_PREFIXES
        entries this module does not map (GO, MeSH, HP, MONDO) and any
        prefix outside the nine entirely. Never a guessed or malformed URL.
    """
    if not curie or ":" not in curie:
        return None
    prefix, _, local_id = curie.partition(":")
    if not prefix or not local_id:
        return None

    builder = _CURIE_URL_BUILDERS.get(prefix)
    if builder is None:
        return None

    quoted_local_id = urllib.parse.quote(local_id, safe="")
    url = builder(quoted_local_id)

    if not _matches_host_pattern(url):
        # Defense in depth: a builder that ever produced a URL outside the
        # host-pinned pattern would be a bug in this module, not a valid
        # citation. Never pass such a URL through.
        return None
    return url


def _resolve_source_url(curie: str, stored_url: object) -> str | None:
    """Resolve the source_url for one row: keep a valid stored URL, else derive.

    A stored URL already on the node or edge (data carried over from
    Systems 1 and 2) is kept only when it matches the host-pinned pattern.
    A stored URL on a foreign host is discarded, never passed through, and
    this function then falls back to deriving a URL from the CURIE, the
    same path taken when no stored URL was present at all.
    """
    if isinstance(stored_url, str) and stored_url and _matches_host_pattern(stored_url):
        return stored_url
    return source_url_for_curie(curie)


def to_output_row(raw_row: dict, snapshot_version: str) -> dict:
    """Shape one raw graph row into the `CypherQueryRow` dict shape.

    `raw_row` is read defensively rather than assumed to carry one exact
    key set, since the graph connection module (T-2.1-06, a different
    builder's file) owns the raw row shape and this ticket is scoped to
    pure transforms only. Recognized keys, in lookup order:

    - node_or_edge_type: `node_or_edge_type`, then `label`, then `type`
    - curie: `curie`, then `id`
    - fields: `fields`, then `properties`, defaulting to an empty dict
    - source_url: `source_url`, an already-stored value if present

    Args:
        raw_row: one row as read from the graph, before output mapping.
        snapshot_version: the graph snapshot version string to stamp onto
            every row, e.g. from `docs/data-engineering/
            Knowledge_graph_on_server_reference.md`'s recorded snapshot.

    Returns:
        A dict with exactly the keys `node_or_edge_type`, `curie`,
        `fields`, `source_url`, `graph_snapshot_version`. `source_url` is
        None, never a fabricated link, when no valid URL could be
        resolved for the row's CURIE.
    """
    node_or_edge_type = (
        raw_row.get("node_or_edge_type")
        or raw_row.get("label")
        or raw_row.get("type")
        or ""
    )
    curie = raw_row.get("curie") or raw_row.get("id") or ""
    fields = raw_row.get("fields")
    if fields is None:
        fields = raw_row.get("properties", {})

    resolved_source_url = _resolve_source_url(curie, raw_row.get("source_url"))

    return {
        "node_or_edge_type": node_or_edge_type,
        "curie": curie,
        "fields": fields,
        "source_url": resolved_source_url,
        "graph_snapshot_version": snapshot_version,
    }
