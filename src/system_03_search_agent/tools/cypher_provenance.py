"""Layer 1 provenance and source URL mapping, T-2.1-05.

Maps a graph CURIE to its human-facing NCBI record page and shapes a raw
graph row into the `CypherQueryRow` dict shape (Section 6.1, Section 9).
This module never fabricates a URL: a CURIE prefix with no verified,
host-pinned NCBI record page returns None rather than a guessed path, and
every URL this module emits, whether newly derived or an existing stored
value, is checked against `NCBI_RECORD_URL_PATTERN` before it is returned.

Six of the nine CURIE prefixes in `graph_schema_constants.CURIE_PREFIXES`
map to a documented NCBI record page and are handled below: NCBIGene,
ClinVar, MedGen, PMID, NCBITaxon, MeSH. MeSH (Medical Subject Headings)
is an NCBI-hosted controlled vocabulary in its own right, listed in
`docs/ncbi/NCBI_databases_and_APIs_reference.md`, so a `MeSH:D012345`
CURIE maps to `https://www.ncbi.nlm.nih.gov/mesh/?term=D012345`.

The remaining three, GO, HP, and MONDO, are not NCBI-hosted databases.
Gene Ontology, the Human Phenotype Ontology, and Mondo are maintained
outside NCBI entirely (the OBO Foundry and the Monarch Initiative), so no
host-pinned `ncbi.nlm.nih.gov` record page exists for them at all;
inventing one would be exactly the fabricated citation this module exists
to prevent. `source_url_for_curie` returns None for all three, not a
guessed external host and not a loosened pattern. This is a documented,
deliberate gap, not an oversight: if a verified NCBI-hosted or otherwise
host-pinned record page for one of these three is confirmed later, add it
here as a new mapping entry, never by loosening `NCBI_RECORD_URL_PATTERN`
itself.

`to_output_rows` (plural), added for finding F-2.1-A1/F-01/A2's fix, is the
real integration path: it takes one raw AGE result row keyed by column name
(`c0`, `c1`, ... or `result`), each value the unparsed agtype wire text
`graph_connection.execute_cypher` read off the socket, parses every column
with `agtype.parse_agtype`, and shapes each column that decodes to a
vertex or an edge into its own output row. `to_output_row` (singular)
stays as the pure, already-parsed-entity shaping function it always was,
used directly by this module's own unit tests and by any caller that has
already turned a raw agtype value into a plain dict.

Finding F-2.1-B06: a real AGE edge carries no `properties["id"]`, so it has
no CURIE and no record page of its own. A live probe of five edge labels
(`is_sequence_variant_of`, `gene_associated_with_condition`,
`has_mesh_annotation`, `in_taxon`, `orthologous_to`) found every edge still
carries a `source_url` property, and in every sampled case that URL was
the same page its start endpoint's own CURIE derives, not a citation the
edge earns on its own. Before this fix, an empty CURIE did not stop
`_resolve_source_url` from keeping that stored URL whenever it matched
the host pattern, so the row shipped `source_id="unknown"` next to a
link that resolves to a real but different record, a citation that
survives inspection while pointing at the wrong thing. `to_output_rows`
now collects every vertex and edge entity across all of a raw row's
columns first, so an edge with no CURIE of its own can be attributed to
a genuine endpoint vertex's CURIE when that vertex is present in the
same row (a sibling column, or an adjacent path element), verified from
data already in hand, never fabricated and never fetched. When no
endpoint vertex is present in the row, the honest outcome is no citation:
`source_url` is None, and the caller's cite-or-refuse gate drops the row.
See `_shape_entity`, `_endpoint_curies_by_internal_id`, and
`_attributed_endpoint_curie`.

Findings F-2.1-C02, C04, C05, C06, C09 (third adversary pass, unreviewed
rework): five more defects in what this module cites.

- F-2.1-C09: `source_url_for_curie` mapped a prefix to a builder but never
  checked the local id's shape, so an unverified string after the colon
  (`672.`, `672-related`, `../../etc/passwd`) built a syntactically valid,
  host-pinned URL that 404s live. Fixed by `_CURIE_LOCAL_ID_SHAPES`: a
  local id that does not match its prefix's verified shape now returns
  None, the same outcome as an unmapped prefix.

Finding F-2.1-J4-05 (fourth judge pass): the C09 fix's shape table was a
regression. It was derived from a roughly 40-row live sample rather than
each prefix's real format, and the resulting single-letter-plus-digits
shape (one letter, then digits, nothing else) was too narrow for MedGen:
it rejected `MedGen:CN517202`, a genuine two-letter MedGen concept id
(MedGen assigns its own `CN`-prefixed ids when a concept has no UMLS CUI,
alongside the UMLS-standard `C`-prefixed CUI), stripping the citation from
a real Disease record and dropping it from any answer under cite-or-refuse.
The judge measured the blast radius at 4,401 of 200,845 Disease nodes.

`_CURIE_LOCAL_ID_SHAPES` is now derived per prefix as follows, not from a
further, larger sample:

- NCBIGene, ClinVar, PMID, NCBITaxon: NCBI's own documented external id
  conventions state these are plain positive integers (an Entrez Gene ID, a
  ClinVar Variation ID, a PubMed ID, and an NCBI Taxonomy id are each
  defined as numeric), cross-checked against an unfiltered 15-row `LIMIT`
  sample per label read straight off the live graph
  (`Gene`, `SequenceVariant`, `Article`, `OrganismTaxon`) on 2026-07-31.
  A 15-row `LIMIT` is a bounded read, never a full scan of these
  multi-million-row labels.
- MedGen, MeSH: no external numeric convention applies, since both use
  letter-prefixed ids, so the shape is instead derived from an EXHAUSTIVE,
  bounded aggregate query grouping every row of the `Disease` (200,845
  rows) and `OntologyClass` (30,790 rows) tables by their digit-collapsed
  id shape, run directly against the small per-label SQL tables on
  2026-07-31 (both labels are small enough that a full read carries no OOM
  risk, unlike the multi-million-row labels above). This is complete
  coverage of every Disease and OntologyClass row in the graph, not a
  sample: MedGen ids are exactly `C` followed by digits (196,444 rows) or
  `CN` followed by digits (4,401 rows), never a third shape; MeSH ids are
  exactly `D` followed by digits, in either a 6-digit legacy length
  (27,177 rows) or a 9-digit length NLM introduced for newer descriptors
  (3,613 rows), never a third shape. `_MEDGEN_LOCAL_ID` and
  `_MESH_LOCAL_ID` accept any digit count after the letter prefix rather
  than hardcoding 6, 7, or 9 digits specifically, since the exhaustive scan
  already shows the digit count is not fixed within a single prefix and a
  future MeSH or MedGen id one digit longer must not be treated as an
  attack string the way `NCBIGene:672-VALIDATED-BY-FDA` genuinely is.
  Unlike the old single-letter shape, the letter itself is now pinned
  (uppercase `C`/`CN` for MedGen, uppercase `D` for MeSH) rather than "any
  single letter", because the exhaustive scan leaves no evidence any other
  letter is real for either prefix.
- F-2.1-A5-07 (fifth adversary pass): J4-05 pinned each shape's letters to
  specific uppercase ASCII characters, but left every `\\d` in the same
  shapes unrestricted, and Python's `\\d` matches any Unicode decimal
  digit, not only ASCII 0-9. An Arabic-Indic, Devanagari, or fullwidth
  digit therefore fullmatched a shape exactly as a real digit would,
  quoted cleanly, and built a syntactically valid, host-pinned URL for a
  record that cannot exist, F-2.1-C09's citation-spoofing class reopened
  through a character class instead of a shape. Every pattern in
  `_CURIE_LOCAL_ID_SHAPES` now compiles with `re.ASCII`, so `\\d` in each
  one matches only `[0-9]`.
- F-2.1-C04/C05: an edge with no CURIE of its own used to be attributed
  only to whichever sibling endpoint vertex the query happened to also
  RETURN, so the identical edge got a different citation depending on the
  projection, and the more precise endpoint (for example the ClinVar
  variation page for `is_sequence_variant_of`) was lost whenever the query
  stopped projecting that vertex. Fixed by `_curie_for_source_url`,
  reverse-deriving a verified CURIE from the edge's own stored
  `source_url` first (edge-intrinsic, independent of projection), falling
  back to sibling-vertex attribution only when that fails.
- F-2.1-C02: a derived/projected value that is itself a resolvable CURIE
  (`d.id AS disease_id`) used to be cited to the entity the query was
  computed from, discarding the real record the fact is actually about.
  Fixed by `_first_resolvable_curie`: a projected identifier is now cited
  to its own record; only a genuine non-identifier scalar (a count, a
  name) falls back to the computed-from entity.
- F-2.1-C06: an edge attributed to a sibling vertex's CURIE, and that
  vertex's own row in the same raw row, used to produce two output rows
  citing the identical record. Fixed by `_dedupe_rows_by_record_identity`,
  applied to every list `to_output_rows` returns.

Depends on:
    - system_03_search_agent.tools.graph_schema_constants
      (NCBI_RECORD_URL_PATTERN)
    - system_03_search_agent.tools.agtype (parse_agtype, is_vertex_or_edge)

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
from collections.abc import Callable
from typing import Any

from system_03_search_agent.tools.agtype import is_vertex_or_edge, parse_agtype
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


def _mesh_url(local_id: str) -> str:
    return "https://www.ncbi.nlm.nih.gov/mesh/?term=" + local_id


# GO, HP, and MONDO are intentionally absent from this table. See the
# module docstring for why: no verified NCBI-hosted record page exists for
# any of the three, so they fall through to the None-returning default in
# `source_url_for_curie` rather than appearing here with a guessed path.
_CURIE_URL_BUILDERS: dict[str, Callable[[str], str]] = {
    "NCBIGene": _ncbigene_url,
    "ClinVar": _clinvar_url,
    "MedGen": _medgen_url,
    "PMID": _pmid_url,
    "NCBITaxon": _ncbitaxon_url,
    "MeSH": _mesh_url,
}


def _matches_host_pattern(url: str) -> bool:
    return bool(_HOST_PATTERN.match(url))


# Finding F-2.1-C09: a CURIE prefix having a documented URL builder never
# meant the text after the colon was checked against the SHAPE real ids
# for that prefix actually take, only that a builder existed at all.
# `NCBIGene:672.`, `NCBIGene:672-related`, `NCBIGene:not_a_number`,
# `NCBIGene:672 OR 1=1`, and `MedGen:../../etc/passwd` all pass the prefix
# lookup and quote cleanly into a syntactically valid, host-pinned URL,
# and the adversary verified live that every one of those exact URLs
# 404s: the host is genuine, only the path is attacker-controlled, so the
# cite-or-refuse gate was satisfied by a citation to a dead page. A CURIE
# whose local id does not match the real shape for its prefix is not a
# record this module can stand behind, so it must return None, the same
# outcome as an unmapped prefix, not a plausible-looking guess.
#
# Finding F-2.1-J4-05: the shapes below replace a table derived from a
# roughly 40-row live sample, which was too narrow. It rejected
# `MedGen:CN517202`, a genuine two-letter MedGen id, stripping 4,401 of
# 200,845 real Disease nodes of their citation. See the module docstring
# for the full derivation, restated briefly here:
#
# - NCBIGene, ClinVar, PMID, NCBITaxon: NCBI's own documented id
#   conventions (Entrez Gene ID, ClinVar Variation ID, PubMed ID, NCBI
#   Taxonomy id are all plain positive integers), cross-checked against a
#   bounded 15-row `LIMIT` sample per label, never a full scan of these
#   multi-million-row labels.
# - MedGen, MeSH: an EXHAUSTIVE aggregate over every row of the `Disease`
#   and `OntologyClass` tables (small labels, a full read is safe), not a
#   sample. MedGen ids are `C` or `CN` followed by digits, never a third
#   shape, and never a lowercase or any other letter. MeSH ids are `D`
#   followed by digits, never a third shape or another letter. Neither
#   shape hardcodes a digit count: the exhaustive scan itself found two
#   different digit counts live for each prefix (MedGen: 7 after `C`, 6
#   after `CN`; MeSH: 6 and 9 after `D`, the 9-digit form being newer
#   descriptors NLM introduced once 6 digits ran out), so a real id one
#   digit longer than anything sampled must not be treated the way
#   `NCBIGene:672-VALIDATED-BY-FDA` genuinely should be.
#
# Finding F-2.1-A5-07: Python's `\d` matches every Unicode decimal digit,
# not only ASCII 0-9, so without `re.ASCII` an Arabic-Indic, Devanagari, or
# fullwidth digit fullmatched these shapes as cleanly as a real digit and
# quoted straight into a syntactically valid, host-pinned URL for a record
# that cannot exist: F-2.1-C09's exact failure mode, reopened through a
# character class rather than a shape. Every pattern below now carries
# `re.ASCII`, so `\d` in each one matches only `[0-9]` and a non-ASCII
# digit is rejected the same way `NCBIGene:672-related` already was.
_NUMERIC_LOCAL_ID = re.compile(r"^\d+$", re.ASCII)
_MEDGEN_LOCAL_ID = re.compile(r"^CN?\d+$", re.ASCII)
_MESH_LOCAL_ID = re.compile(r"^D\d+$", re.ASCII)

_CURIE_LOCAL_ID_SHAPES: dict[str, re.Pattern[str]] = {
    "NCBIGene": _NUMERIC_LOCAL_ID,
    "ClinVar": _NUMERIC_LOCAL_ID,
    "MedGen": _MEDGEN_LOCAL_ID,
    "PMID": _NUMERIC_LOCAL_ID,
    "NCBITaxon": _NUMERIC_LOCAL_ID,
    "MeSH": _MESH_LOCAL_ID,
}


def source_url_for_curie(curie: str) -> str | None:
    """Map a graph CURIE to its NCBI record page, or None.

    Args:
        curie: a compact identifier of the form `prefix:local_id`, e.g.
            `NCBIGene:672`. A string with no colon, an empty prefix, or an
            empty local id is treated as malformed and returns None.

    Returns:
        The record page URL when the prefix is one of the six documented
        mappings, the local id matches the verified shape for that prefix
        (finding F-2.1-C09, corrected by F-2.1-J4-05), and the resulting
        URL matches
        `NCBI_RECORD_URL_PATTERN`. None for every other prefix, including
        the three CURIE_PREFIXES entries this module does not map (GO,
        HP, MONDO) and any prefix outside the nine entirely. Never a
        guessed or malformed URL, and never a URL built from a local id
        this module cannot verify the shape of.
    """
    if not curie or ":" not in curie:
        return None
    prefix, _, local_id = curie.partition(":")
    if not prefix or not local_id:
        return None

    builder = _CURIE_URL_BUILDERS.get(prefix)
    if builder is None:
        return None

    shape = _CURIE_LOCAL_ID_SHAPES.get(prefix)
    if shape is not None and not shape.fullmatch(local_id):
        # F-2.1-C09: a shape mismatch means this local id cannot be
        # verified against the graph's own id format for this prefix.
        # Treated the same as an unmapped prefix: no URL, never a guessed
        # one that happens to be syntactically well-formed.
        return None

    # Findings F-2.1-J4-05 and F-2.1-A5-07: every shape in
    # `_CURIE_LOCAL_ID_SHAPES` restricts its letters to specific uppercase
    # ASCII characters (J4-05) and, since A5-07, compiles with `re.ASCII` so
    # its `\d` classes match only ASCII digits too. Together those two make
    # the following true: no local id that reaches this line ever contains
    # a character `quote` needs to escape. Before the A5-07 fix this
    # comment asserted that property while `\d` still matched every Unicode
    # decimal digit, so a local id built from Arabic-Indic or fullwidth
    # digits reached this line and DID need escaping; `quote` silently
    # escaped it into a syntactically valid, host-pinned, and dead URL
    # instead of the shape check catching it. The call stays as defense in
    # depth for a shape added later that does admit an encodable character,
    # not because today's shapes exercise it; see
    # `test_no_documented_prefix_url_ever_contains_a_percent_encoded_local_id`
    # and `test_curie_local_id_shapes_reject_non_ascii_digits`.
    quoted_local_id = urllib.parse.quote(local_id, safe="")
    url = builder(quoted_local_id)

    if not _matches_host_pattern(url):
        # Defense in depth: a builder that ever produced a URL outside the
        # host-pinned pattern would be a bug in this module, not a valid
        # citation. Never pass such a URL through.
        return None
    return url


# Finding F-2.1-C04/C05: an edge's own stored `source_url` is data already
# in hand on the edge itself (F-2.1-B06's own probe found every sampled
# edge carries one), never dependent on which sibling endpoint vertex a
# query happens to also RETURN. Reverse-deriving the CURIE that produced
# it, rather than only matching it against whichever vertex is present in
# this particular row, makes the citation a property of the edge, not of
# the projection: the same edge resolves to the same record whether the
# query returned its start endpoint, its end endpoint, both, or neither.
_CURIE_URL_PATTERNS: dict[str, re.Pattern[str]] = {
    "NCBIGene": re.compile(r"^https://www\.ncbi\.nlm\.nih\.gov/gene/(?P<local_id>[^/?#]+)/?$"),
    "ClinVar": re.compile(
        r"^https://www\.ncbi\.nlm\.nih\.gov/clinvar/variation/(?P<local_id>[^/?#]+)/?$"
    ),
    "MedGen": re.compile(r"^https://www\.ncbi\.nlm\.nih\.gov/medgen/(?P<local_id>[^/?#]+)/?$"),
    "PMID": re.compile(r"^https://pubmed\.ncbi\.nlm\.nih\.gov/(?P<local_id>[^/?#]+)/?$"),
    "NCBITaxon": re.compile(
        r"^https://www\.ncbi\.nlm\.nih\.gov/Taxonomy/Browser/wwwtax\.cgi\?id="
        r"(?P<local_id>[^&#]+)$"
    ),
    "MeSH": re.compile(r"^https://www\.ncbi\.nlm\.nih\.gov/mesh/\?term=(?P<local_id>[^&#]+)$"),
}


def _curie_for_source_url(url: str) -> str | None:
    """Reverse-derive a verified CURIE from a URL this module could have
    built itself, or None.

    Tries each documented prefix's own path pattern, decodes the extracted
    local id, and accepts the candidate only when feeding it back through
    `source_url_for_curie` succeeds, i.e. only when it is a shape this
    module recognizes as a real id for that prefix. This is never a guess
    from regex shape alone: `source_url_for_curie` applies the exact same
    per-prefix shape check finding F-2.1-C09 added, so a URL that is
    host-valid and even path-shaped like one of the six documented
    templates, but whose local id does not match that prefix's real id
    shape, still correctly yields None here.
    """
    for prefix, pattern in _CURIE_URL_PATTERNS.items():
        match = pattern.match(url)
        if match is None:
            continue
        local_id = urllib.parse.unquote(match.group("local_id"))
        candidate = f"{prefix}:{local_id}"
        if source_url_for_curie(candidate) is not None:
            return candidate
    return None


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


def _is_edge_entity(entity: dict[str, Any]) -> bool:
    """Return True when `entity` is an AGE edge, per `agtype.is_vertex_or_edge`'s
    own convention: a vertex carries only `label`, an edge additionally
    carries `start_id` and/or `end_id`.
    """
    return "start_id" in entity or "end_id" in entity


def _endpoint_curies_by_internal_id(entities: list[dict[str, Any]]) -> dict[Any, str]:
    """Map every vertex's own AGE-internal id to its own CURIE, for one raw row.

    Built once per raw graph row from every vertex entity that row's
    columns actually parsed (a plain multi-column `RETURN v, e, g`, or a
    path's flattened elements), never from a separate graph lookup: this
    module is a pure transform over its arguments and never queries the
    graph on its own (see the module docstring). This mapping is the
    input finding F-2.1-B06's fix depends on: it lets an edge with no
    CURIE of its own (`_shape_entity`, below) attribute its citation to a
    genuine endpoint vertex that is actually present in the same row,
    verified from data already in hand, never to a guessed or freshly
    fetched one.

    An edge entity never contributes to this mapping, only a vertex does,
    so an edge can never be attributed to another edge's identity.
    """
    mapping: dict[Any, str] = {}
    for entity in entities:
        if _is_edge_entity(entity):
            continue
        properties = entity.get("properties")
        if not isinstance(properties, dict):
            continue
        curie = str(properties.get("id") or "")
        internal_id = entity.get("id")
        if curie and internal_id is not None:
            mapping[internal_id] = curie
    return mapping


def _attributed_endpoint_curie(
    entity: dict[str, Any],
    endpoint_curies: dict[Any, str] | None,
    stored_url: object = None,
) -> str | None:
    """Find a verified citation CURIE for an edge entity with no CURIE of
    its own.

    Finding F-2.1-C04/C05: this used to check only `entity`'s `start_id`
    then `end_id` against `endpoint_curies`, so an edge's citation
    depended on which sibling endpoint vertex the query happened to also
    RETURN in the same row. `RETURN e, d` cited the end endpoint,
    `RETURN e, g` cited the start endpoint, and the identical edge in the
    graph got two different citations across two differently-projected
    queries of it, and the more precise of the two (for example the
    ClinVar variation page for `is_sequence_variant_of`) was lost the
    moment the query stopped projecting that specific vertex. Provenance
    for a fact must not be a property of which column a model chose to
    project.

    Priority 1: reverse-derive a verified CURIE from the edge's own stored
    `source_url` (`_curie_for_source_url`), when that URL is host-pinned.
    This is edge-intrinsic data, always present on the edge itself
    regardless of which sibling columns the query returned (F-2.1-B06's
    own probe found every sampled edge carries a `source_url` property),
    so it is what makes the citation deterministic for the same edge and
    what restores the precision F-2.1-C05 found lost.

    Priority 2 (fallback, only when priority 1 finds nothing verifiable):
    the original F-2.1-B06 mechanism, checking `start_id` then `end_id`
    against `endpoint_curies`, built from whichever vertex entities this
    row's own columns actually parsed. Kept for edges whose own stored URL
    is missing, malformed, or on a foreign host, so such an edge is not
    made uncitable just because this row happens to include a genuine
    sibling endpoint vertex it could otherwise be attributed to.

    Returns None when neither priority finds anything: an edge queried
    alone (`RETURN e`), with no valid stored URL of its own and no sibling
    vertex in the row, is the honest "cannot attribute" case, and nothing
    here is invented to fill it.
    """
    if isinstance(stored_url, str) and stored_url and _matches_host_pattern(stored_url):
        own_curie = _curie_for_source_url(stored_url)
        if own_curie:
            return own_curie

    if not endpoint_curies:
        return None
    for key in ("start_id", "end_id"):
        internal_id = entity.get(key)
        if internal_id is None:
            continue
        candidate = endpoint_curies.get(internal_id)
        if candidate:
            return candidate
    return None


def _shape_entity(
    entity: dict[str, Any],
    snapshot_version: str,
    endpoint_curies: dict[Any, str] | None = None,
    traversed_edge_type: str | None = None,
) -> dict:
    """Shape one parsed AGE vertex or edge dict into the output row shape.

    `entity` is the dict `agtype.parse_agtype` decoded from one `::vertex`
    or `::edge` payload: `label`, the graph-internal `id` (an integer AGE
    assigns, never the CURIE), `properties`, and for an edge, `start_id`
    and `end_id`. The CURIE this system cites lives inside
    `properties["id"]`, the identifier Systems 1 and 2 stamped onto every
    node and edge at ingest time. The top-level `id` on the entity itself
    is AGE's own internal graph id and is never treated as a CURIE.

    Finding F-2.1-B06: a real AGE edge carries no `properties["id"]` at
    all (verified live: `source`, `agent_type`, `source_url`, and
    `knowledge_level`, never `id`). Before this fix, an edge's empty
    `curie` still let `_resolve_source_url` pass through the edge's own
    stored `source_url` whenever it matched the host pattern, so the row
    shipped `source_id="unknown"` next to a URL for a genuine but
    different record, a citation that survives inspection while pointing
    at the wrong thing.

    An edge with no CURIE of its own (`is_edge` and `not curie`, below)
    never keeps its raw stored `source_url` as-is, unverified. Finding
    F-2.1-C04/C05: `_attributed_endpoint_curie` first tries to
    reverse-derive a verified CURIE from the edge's own stored
    `source_url` itself, edge-intrinsic data that does not depend on
    which sibling columns the query returned, and falls back to a sibling
    endpoint vertex's CURIE (`endpoint_curies`, built by
    `_endpoint_curies_by_internal_id` from every column of the row) only
    when that fails. Either way, both `curie` and `source_url` are set
    together from the same verified CURIE so the two always agree, and
    the canonical URL is re-derived from that CURIE rather than the raw
    stored string passed through, so a stored value's own formatting
    quirks never leak into the citation;
    `fields["_cited_via_endpoint_curie"]` marks the row as an edge citing
    an endpoint's record, never presented as the edge's own identity.
    When neither the edge's own stored URL nor a sibling vertex verifies,
    `source_url` is None: the honest "no citation" outcome, which the
    caller's cite-or-refuse gate (`cypher_query._run_pipeline`) drops
    rather than emitting an uncited or misattributed row.

    T-3.4-03, closing F-2.2-A-05: `traversed_edge_type` is an opaque hint
    the caller (`cypher_query._traversed_edge_type_by_column`) derives by
    parsing the already-validated Cypher text, never computed here. This
    module stays a pure shaping transform over what it is handed: it never
    inspects the raw Cypher itself and never guesses the edge from the
    entity's own label. When the caller supplies a value, it is carried
    onto the shaped row unchanged; when it does not (a bare identifier
    lookup, an ambiguous or multi-hop pattern), the row carries None here,
    same as before this ticket, so a plain `Disease` lookup is unaffected.
    """
    node_or_edge_type = str(entity.get("label") or "")
    properties = entity.get("properties")
    if not isinstance(properties, dict):
        properties = {}
    curie = str(properties.get("id") or "")
    is_edge = _is_edge_entity(entity)

    fields = dict(properties)
    if "start_id" in entity:
        fields.setdefault("_edge_start_id", entity["start_id"])
    if "end_id" in entity:
        fields.setdefault("_edge_end_id", entity["end_id"])

    if is_edge and not curie:
        attributed_curie = _attributed_endpoint_curie(
            entity, endpoint_curies, properties.get("source_url")
        )
        if attributed_curie:
            curie = attributed_curie
            fields["_cited_via_endpoint_curie"] = attributed_curie
            # Always re-derive the canonical URL from the verified CURIE,
            # never pass the raw stored string through as-is: a stored
            # value's own formatting (a missing trailing slash, stray
            # whitespace) must never leak into the citation, or two
            # differently-formatted stored URLs for the same record would
            # defeat F-2.1-C04's determinism guarantee.
            resolved_source_url = source_url_for_curie(attributed_curie)
        else:
            # Neither the edge's own stored source_url nor a sibling
            # endpoint vertex in this row could be verified against a
            # real CURIE. Nothing here is invented to fill the gap.
            resolved_source_url = None
    else:
        resolved_source_url = _resolve_source_url(curie, properties.get("source_url"))

    return {
        "node_or_edge_type": node_or_edge_type,
        "curie": curie,
        "fields": fields,
        "source_url": resolved_source_url,
        "graph_snapshot_version": snapshot_version,
        "traversed_edge_type": traversed_edge_type,
    }


def _iter_entities(parsed: Any) -> list[dict[str, Any]]:
    """Flatten one parsed agtype value into zero or more vertex/edge dicts.

    A vertex or an edge parses to a single dict and yields itself. A path
    parses to a list and yields every vertex/edge element it contains,
    since a path is a sequence of alternating vertices and edges. Any
    other shape, a bare scalar such as a count or a name, or a value that
    failed to parse, yields nothing: it carries no label and no
    properties, so no CURIE and no citation can be derived from it, and
    it must never be turned into a guessed content row.
    """
    if isinstance(parsed, dict):
        return [parsed] if is_vertex_or_edge(parsed) else []
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict) and is_vertex_or_edge(item)]
    return []



def _first_resolvable_curie(derived: dict[str, Any]) -> str | None:
    """Return the first value in `derived` that is itself a citable CURIE.

    Finding F-2.1-C02: a projected identifier column (`d.id AS
    disease_id`) already IS the record a derived row's fact is about. The
    original F-2.1-B05/J01 fix cited every derived row to the entity the
    query was computed FROM, which is correct for a genuine scalar (a
    count, a name) but wrong for a projected identifier: four distinct
    MedGen disease ids all cited to one Gene page, the record the query
    started from, while the real identifiers each fact is actually about
    sat unused in the row's own fields.

    Iterates `derived` in its own insertion order, which mirrors the
    RETURN clause's own column order, so the choice is deterministic
    rather than a further coincidence of dict ordering. Only a string
    value that `source_url_for_curie` itself accepts counts: this reuses
    the exact same prefix and shape checks finding F-2.1-C09 added, so an
    ordinary string that merely contains a colon is never mistaken for an
    identifier.
    """
    for value in derived.values():
        if isinstance(value, str) and source_url_for_curie(value) is not None:
            return value
    return None


def _shape_derived_value(
    derived: dict[str, Any],
    snapshot_version: str,
    source_curie: str | None,
    column_labels: dict[str, str] | None = None,
) -> dict:
    """Shape a scalar or projection result into one citable output row.

    Finding F-2.1-B05: a count, a projected property, or a `collect()` list
    is a real answer that carried no label, so it produced no row at all and
    the tool reported `status="empty"` for a query the graph had answered
    correctly.

    Finding F-2.1-C02: provenance for a derived value is preferentially the
    value's own record, when the projected value is itself a resolvable
    CURIE (`_first_resolvable_curie`). Only when nothing projected is
    itself an identifier, a genuine scalar such as a count or a name, does
    provenance fall back to the entity the query was computed FROM:
    `source_curie` carries that entity down from the caller, which is the
    only place that knows it, and citing BRCA1's own record for the count
    of BRCA1's variants is a claim this system can stand behind.

    `node_or_edge_type` is "derived" rather than a graph label, so a
    downstream consumer can tell a computed value from a retrieved record
    and never present one as the other. Without a projected identifier or
    a `source_curie`, the row still carries no citation and the caller's
    cite-or-refuse gate drops it, which is the correct outcome: an
    uncitable computed number is exactly the fluent-but-ungrounded output
    this system must not emit.
    """
    # F-2.1-J09: key each value by its RETURN alias where the query gave
    # one, so `count(v) AS variant_count` reaches the Write step as
    # `variant_count` rather than the positional `c0`. A column with no
    # alias keeps its positional name; see `cypher_query.column_labels_for`
    # for why an unaliased expression is not paraphrased into a label.
    labels = column_labels or {}
    fields = {labels.get(column, column): value for column, value in derived.items()}

    projected_curie = _first_resolvable_curie(derived)
    if projected_curie:
        citation_curie = projected_curie
        resolved_source_url = source_url_for_curie(projected_curie)
    else:
        citation_curie = source_curie or ""
        resolved_source_url = source_url_for_curie(source_curie) if source_curie else None

    return {
        "node_or_edge_type": "derived",
        "curie": citation_curie,
        "fields": fields,
        "source_url": resolved_source_url,
        "graph_snapshot_version": snapshot_version,
    }

def to_output_rows(
    raw_row: dict[str, Any],
    snapshot_version: str,
    derived_source_curie: str | None = None,
    column_labels: dict[str, str] | None = None,
    traversed_edge_type_by_column: dict[str, str] | None = None,
) -> list[dict]:
    """Shape one raw AGE result row into zero or more output row shapes.

    `raw_row` is a dict keyed by the AGE output column name(s) declared in
    `execute_cypher`'s `as_clause` (for example `result` for a single
    column, or `c0`, `c1`, ... for a multi-column `RETURN`), with each
    value the raw agtype wire text `graph_connection.execute_cypher` read
    off the socket, unparsed.

    Each column value is parsed independently with `agtype.parse_agtype`.
    A multi-column `RETURN v, g` therefore yields one output row per
    column that decodes to a vertex or an edge, not one row per raw graph
    row: `CypherQueryRow` has no shape for merging two distinct entities
    into a single row, so a `v`-and-`g` pair becomes two output rows, each
    carrying its own type, CURIE, and citation, which is more faithful to
    "every fact links back to its source" than collapsing them into one
    row that could only cite one of the two.

    A column whose parsed value is not a vertex, an edge, or a path
    containing one, a bare scalar such as a count, or a value that failed
    to parse, contributes no output row. That omission is deliberate, not
    a bug: such a value has no label and no CURIE, so it has no citation,
    and CLAUDE.md's citation rule means it must never be emitted as an
    empty content row instead. The caller, `cypher_query._run_pipeline`,
    applies the matching cite-or-refuse gate at the row level: an
    entity that does parse but still resolves no `source_url` (an
    unmapped CURIE prefix such as GO, HP, or MONDO, or an edge with no
    CURIE of its own and no endpoint vertex in the same row, finding
    F-2.1-B06) is also dropped there, for the same reason.

    Finding F-2.1-B06: entities are collected from every column of `raw_row`
    before any of them is shaped, specifically so that an edge column
    (which never carries its own CURIE on the live graph) can be
    attributed to a genuine endpoint vertex's CURIE when that vertex was
    also returned in this same row, whether as a sibling column
    (`RETURN v, e, g`) or as an adjacent element of the same path
    (`RETURN p`). See `_shape_entity` and `_endpoint_curies_by_internal_id`.

    Args:
        raw_row: one row as read from the graph connection, keyed by
            output column name, each value unparsed agtype wire text (or
            already a parsed dict/list/scalar, never double-parsed).
        snapshot_version: the graph snapshot version string to stamp onto
            every shaped row.

    Finding F-2.1-C06: the returned list is deduplicated by cited record
    (`_dedupe_rows_by_record_identity`) before it reaches the caller. An
    edge attributed to a sibling endpoint vertex's CURIE, and that same
    vertex returned as its own column in the same row, used to produce
    two output rows citing the identical record, halving the caller's
    fixed citation budget with no signal that a duplicate was dropped.

    T-3.4-03, closing F-2.2-A-05: `traversed_edge_type_by_column` is an
    optional map from a raw-row column key (`c0`, `c1`, ...) to the single
    edge label the caller determined, from the Cypher text alone, is the
    relationship that traversal returned that column's entity through
    (`cypher_query._traversed_edge_type_by_column`). It is applied only to
    a column whose parsed value is exactly one vertex or edge, never to a
    path column (`_iter_entities` can return more than one entity for a
    single path column, and which of them the traversed label describes is
    ambiguous, so no attachment is made there). A column absent from the
    map, or one with no entry, leaves that row's `traversed_edge_type` at
    its default of None, identical to this function's behavior before this
    ticket.

    Returns:
        A list of dicts, each with exactly the keys `node_or_edge_type`,
        `curie`, `fields`, `source_url`, `graph_snapshot_version`,
        `traversed_edge_type`, with at most one row per distinct cited
        record. Empty when no column in `raw_row` decoded to a citable
        vertex or edge.
    """
    all_entities: list[dict[str, Any]] = []
    entity_traversed_edge_types: list[str | None] = []
    derived: dict[str, Any] = {}

    for column, value in raw_row.items():
        parsed = parse_agtype(value)
        entities = _iter_entities(parsed)
        if entities:
            # Only a column that decoded to exactly one entity has an
            # unambiguous "this is the entity the traversed edge touches"
            # reading; a path column can decode to several, and attaching
            # one label to all of them would be a guess this ticket's own
            # constraint (never widen beyond what the Cypher text actually
            # says) forbids.
            edge_type = (
                (traversed_edge_type_by_column or {}).get(column)
                if len(entities) == 1
                else None
            )
            all_entities.extend(entities)
            entity_traversed_edge_types.extend([edge_type] * len(entities))
        elif parsed is not None:
            # F-2.1-B05. A scalar or a list is a real answer, not an absence.
            # `count(sv)`, `d.name`, `collect(m.id)` all parse to something
            # that is not a vertex, so every one of them used to contribute
            # zero rows and the tool reported `status="empty"` while
            # `total_available` sat non-zero: it knew the graph had answered
            # and said nothing was found. Five of the six query shapes the
            # real plan model actually produced were projections or scalars,
            # so this refused the correct answer most of the time, including
            # every "how many" question.
            #
            # These are collected per column and emitted as ONE derived row
            # below, rather than one row each, because a projection's columns
            # are fields of a single result, not separate findings.
            derived[column] = parsed

    endpoint_curies = _endpoint_curies_by_internal_id(all_entities)
    shaped_rows = [
        _shape_entity(entity, snapshot_version, endpoint_curies, edge_type)
        for entity, edge_type in zip(all_entities, entity_traversed_edge_types, strict=True)
    ]

    if derived:
        # F-2.1-J03: this used to read `if derived and not shaped_rows`, so a
        # row mixing an entity and a scalar, `RETURN g, count(v)`, emitted the
        # gene and silently discarded the count. The result reported
        # `status="ok"` with a valid citation while the number the user
        # actually asked for was gone, which is worse than F-2.1-B05's
        # original symptom: that refused, this answers with the answer
        # removed.
        #
        # A derived value is emitted whether or not entities share the row.
        # It still carries a citation only when one can be stood behind, and
        # `cypher_query`'s cite-or-refuse gate still drops it otherwise.
        shaped_rows.append(
            _shape_derived_value(
                derived, snapshot_version, derived_source_curie, column_labels
            )
        )

    return _dedupe_rows_by_record_identity(shaped_rows)


def _dedupe_rows_by_record_identity(rows: list[dict]) -> list[dict]:
    """Keep only the first ENTITY output row per cited record, by
    `source_url`.

    Finding F-2.1-C06: an edge attributed to an endpoint's CURIE and that
    same endpoint's own vertex, parsed from separate columns of one raw
    graph row (`RETURN e, d`), used to become two separate output rows
    citing the identical record, one from each code path (`_shape_entity`'s
    edge branch and its ordinary vertex branch). Two output rows for one
    record become two citations for one record downstream, silently
    halving the caller's fixed citation budget with no signal that a
    duplicate was ever dropped. This dedup only ever applies among rows
    `_shape_entity` produced, both genuinely redundant restatements of the
    same underlying record.

    A "derived" row (`_shape_derived_value`) is never deduplicated away,
    and never counted toward another row's identity, even when it shares
    a `source_url` with an entity row in the same call: finding F-2.1-C03
    (`RETURN g, count(v)`) established that a derived value is new
    information (a count, a projection) the entity row does not itself
    carry, and citing it to its computed-from entity, when it has no more
    specific identifier of its own, means it will legitimately share that
    entity's URL. Dropping it as a "duplicate" in that case would silently
    remove the very number the user asked for, which is F-2.1-C03's
    original symptom reborn through this fix.

    A row with no resolvable `source_url` is never deduplicated against
    another: it carries no citation for the caller's cite-or-refuse gate
    to drop in the first place, so there is no record identity to compare
    it against, and it must not be collapsed with an unrelated uncitable
    row just because both happen to have `source_url is None`.
    """
    seen_urls: set[str] = set()
    deduped: list[dict] = []
    for row in rows:
        if row.get("node_or_edge_type") == "derived":
            deduped.append(row)
            continue
        source_url = row.get("source_url")
        if source_url:
            if source_url in seen_urls:
                continue
            seen_urls.add(source_url)
        deduped.append(row)
    return deduped
