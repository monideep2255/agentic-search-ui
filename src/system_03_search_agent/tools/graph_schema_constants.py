"""Static Layer 1 graph schema: labels, predicates, and CURIE prefixes.

The graph is a periodic snapshot produced by Systems 1 and 2, so its label
set does not change between re-ingestions. These constants are therefore
hardcoded rather than queried at runtime: they sit inside the stable prompt
prefix (`.claude/rules/prompt-cache-discipline.md`), and a per-request read
of a live source would defeat that prefix's byte-stability.

Source of truth: `docs/data-engineering/Knowledge_graph_on_server_reference.md`
sections D (vertex labels), E (edge labels), and F (CURIE prefixes). Verified
against the live graph on 2026-07-29.

Known discrepancy, tracked as F-2.1-01 in `tracker/phase_2.1.md`:
Technical_specification.md Section 6.1 says "10 concept labels", while the
reference doc and the live graph both carry 11 vertex labels. The eleventh,
NamedThing, is the dangling-endpoint stub label from the five-database merge.
It is included here because a generator that cannot name it cannot query it.
The spec wording is a Step 6.2 reconciliation item; both documents are locked
until then.

Depends on:
    - Nothing. Pure constants, no imports beyond typing.

Reads:
    - Nothing at import time.

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.tools.schema_slice
    - system_03_search_agent.tools.cypher_validator
    - system_03_search_agent.tools.cypher_provenance
"""

from __future__ import annotations

from typing import Final

# The AGE graph name. Every cypher() call names it explicitly.
GRAPH_NAME: Final[str] = "ncbi_kg"

# Section D. Ordered by row count descending, as documented.
VERTEX_LABELS: Final[tuple[str, ...]] = (
    "Article",
    "Gene",
    "SequenceVariant",
    "OrganismTaxon",
    "Disease",
    "BiologicalProcess",
    "MolecularActivity",
    "CellularComponent",
    "OntologyClass",
    "PhenotypicFeature",
    "NamedThing",
)

# Section E. Ordered by row count descending, as documented.
EDGE_LABELS: Final[tuple[str, ...]] = (
    "has_mesh_annotation",
    "mentioned_in",
    "in_taxon",
    "actively_involved_in",
    "participates_in",
    "located_in",
    "orthologous_to",
    "has_phenotype",
    "is_sequence_variant_of",
    "cited_in",
    "subclass_of",
    "close_match",
    "gene_associated_with_condition",
    "exact_match",
)

# Section E's "Endpoints (typical)" column. A generator that knows the
# endpoint pair cannot invent a relationship the graph has no label for.
# "mixed" means the edge genuinely spans several label pairs.
EDGE_ENDPOINTS: Final[dict[str, tuple[str, str] | None]] = {
    "has_mesh_annotation": ("Article", "OntologyClass"),
    "mentioned_in": ("Gene", "Article"),
    "in_taxon": ("Gene", "OrganismTaxon"),
    "actively_involved_in": ("Gene", "MolecularActivity"),
    "participates_in": ("Gene", "BiologicalProcess"),
    "located_in": ("Gene", "CellularComponent"),
    "orthologous_to": ("Gene", "Gene"),
    "has_phenotype": ("Disease", "PhenotypicFeature"),
    "is_sequence_variant_of": ("SequenceVariant", "Gene"),
    "cited_in": ("Article", "Article"),
    "subclass_of": ("OntologyClass", "OntologyClass"),
    "close_match": None,
    "gene_associated_with_condition": ("Gene", "Disease"),
    "exact_match": None,
}

# Section F. The prefix set the graph actually uses.
CURIE_PREFIXES: Final[tuple[str, ...]] = (
    "NCBIGene",
    "ClinVar",
    "MedGen",
    "PMID",
    "NCBITaxon",
    "GO",
    "MeSH",
    "HP",
    "MONDO",
)

# Section D's "Typical CURIE prefix" column, inverted: which prefixes a given
# vertex label is expected to carry.
LABEL_CURIE_PREFIXES: Final[dict[str, tuple[str, ...]]] = {
    "Article": ("PMID",),
    "Gene": ("NCBIGene",),
    "SequenceVariant": ("ClinVar",),
    "OrganismTaxon": ("NCBITaxon",),
    "Disease": ("MedGen", "MONDO"),
    "BiologicalProcess": ("GO",),
    "MolecularActivity": ("GO",),
    "CellularComponent": ("GO",),
    "OntologyClass": ("MeSH",),
    "PhenotypicFeature": ("HP", "MedGen"),
    "NamedThing": (),
}

# Cypher clauses that mutate. Layer 1 access is read-only by credential
# (the kg_reader role carries default_transaction_read_only), so these are
# defense in depth at the tool layer, not the only control.
FORBIDDEN_CYPHER_CLAUSES: Final[tuple[str, ...]] = (
    "CREATE",
    "MERGE",
    "DELETE",
    "DETACH",
    "SET",
    "REMOVE",
    "DROP",
    "LOAD",
)

# Section 6.1's row_limit bounds.
DEFAULT_ROW_LIMIT: Final[int] = 100
MAX_ROW_LIMIT: Final[int] = 500

# Section 6.1's per-call budget, matching `.claude/rules/tool-call-budgets.md`.
CYPHER_QUERY_TIMEOUT_SECONDS: Final[float] = 30.0

# Section 9.3's strict host-pinned citation pattern. Never the looser
# any-subdomain form: a citation resolves to the human-facing record page,
# never the eutils. or api. fetch host.
NCBI_RECORD_URL_PATTERN: Final[str] = r"^https://(www\.|pubmed\.)?ncbi\.nlm\.nih\.gov/"
