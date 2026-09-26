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
    # Corrected 2026-09-23 (Worker F, overnight run). The reference doc's
    # "typical endpoints" column read Disease to PhenotypicFeature, and this
    # table repeated it uncorrected. Two independent read-only probes against
    # the live graph found ZERO `has_phenotype` edges out of any Disease
    # vertex, graph-wide, with no filter, and every `PhenotypicFeature` vertex
    # sampled is an unpopulated `[stub] HP:...` placeholder with `source` =
    # "stub". The pair the edge actually carries, measured live 2026-09-14
    # (HNF1A: 2075 rows over 1158 variants and 36 diseases) and confirmed
    # again here, is SequenceVariant to Disease, ClinVar-sourced. See
    # `testing/Developer/reports/2026-09-23_overnight/findings.md`,
    # "Worker F", and `testing/Developer/reports/2026-09-23_overnight/
    # probe_g022.py` / `probe_disease_names.py` for the read-only probes.
    "has_phenotype": ("SequenceVariant", "Disease"),
    "is_sequence_variant_of": ("SequenceVariant", "Gene"),
    "cited_in": ("Article", "Article"),
    "subclass_of": ("OntologyClass", "OntologyClass"),
    "close_match": None,
    "gene_associated_with_condition": ("Gene", "Disease"),
    "exact_match": None,
}

# Endpoint pairs the live graph carries under a label BESIDE the primary
# pair in `EDGE_ENDPOINTS`. Empty since 2026-09-23: the one entry this table
# ever held, `has_phenotype`'s SequenceVariant-to-Disease pair, was promoted
# to `EDGE_ENDPOINTS` itself once the pair it had been sitting beside
# (Disease to PhenotypicFeature) was found not to exist in the graph at all.
# The comment that used to live here said widening the primary pair "would
# silently drop the Disease-to-PhenotypicFeature expansion". That expansion
# does not exist; the comment was defending a query shape the graph cannot
# answer. See the note on `EDGE_ENDPOINTS["has_phenotype"]` above. Templates
# still consult both tables (`cypher_templates._assert_templates_name_real_labels`),
# so a future genuinely-additional pair for another edge still has somewhere
# to go.
ADDITIONAL_EDGE_ENDPOINTS: Final[dict[str, tuple[tuple[str, str], ...]]] = {}

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

# The whole tool call's budget: generate, validate, execute, map.
#
# Section 6.1 and `.claude/rules/tool-call-budgets.md` both state 30
# seconds, and both describe it as the GRAPH query's budget. The graph is
# not the expensive part. Measured on the live graph, an indexed CURIE
# lookup returns in roughly 110 ms and a labelled multi-hop traversal in
# roughly 130 ms. What actually consumes the budget is the plan-tier
# generation call that writes the Cypher, which Section 3.1 budgets at
# "1 to a few seconds" and which, in build phase 2.1, measured nothing
# like that.
#
# Six real generation calls across lookup, single-hop, multi-hop and
# aggregate shapes: 13169, 20083, and up to 39378 ms, mean 25472 ms. Two
# of the six exceeded 30 seconds on generation ALONE, before the graph was
# touched at all, so the tool could not complete. Finding F-2.1-B02
# measured 8 of 10 real-model queries timing out before the guard-tier and
# off-thread fixes narrowed the distribution.
#
# Those figures are history. Commit 9a3f50a widened the budget from 30 to
# 90 seconds for them, and the next measurement showed the widening bought
# only a slower failure: the cause was the plan tier's reasoning effort,
# `high`, spending nearly its whole output reasoning over one line of
# Cypher. DECISIONS.md, 2026-07-31, "Dropped the plan tier's reasoning
# effort from `high` to `none`, and left the tool budget where commit
# 9a3f50a widened it": effort `none` wrote the same five query shapes in
# 6.1 seconds in total, 2.2 at worst, and the budget was left at 90 only
# because tightening it then would have been a second change measured
# against nothing.
#
# Back to 30.0, Section 6.1's and the rule's figure, on the product
# owner's decision of 2026-09-26 ("Back to 30 seconds"; phase 8.6's re-land
# follow-up, R-09), now that it is measured. The plan tier still runs at
# effort `none` (`harness._TIER_REASONING`). Across phase 8.6's two golden
# runs of 2026-09-26, 290 `cypher_query` calls took a median of 0.71
# seconds and a 90th percentile of 3.58, and no call that ran past 30
# seconds succeeded: all four ran the full 90 and ended in an error
# (G-005 once, G-006 three times). So 90 only made a question that was
# going to fail wait a minute longer to fail. The per-query COST cap still
# bounds spend independently of this wall-clock budget.
CYPHER_QUERY_TIMEOUT_SECONDS: Final[float] = 30.0

# Section 9.3's strict host-pinned citation pattern. Never the looser
# any-subdomain form: a citation resolves to the human-facing record page,
# never the eutils. or api. fetch host.
NCBI_RECORD_URL_PATTERN: Final[str] = r"^https://(www\.|pubmed\.)?ncbi\.nlm\.nih\.gov/"

# UI fix set 11 (search breadth, 2026-09-14). Of the nine CURIE prefixes,
# three (GO, HP, MONDO) name ontologies hosted outside NCBI, so no record
# page of their own exists on the pinned host and `cypher_provenance`
# returns None for a bare CURIE of any of them. A GO term is different from
# the other two in one respect that makes it citeable after all: the graph's
# Gene-to-GO edges are NCBI's own gene2go annotations, and NCBI's Gene record
# page (`https://www.ncbi.nlm.nih.gov/gene/<id>`) renders that record's Gene
# Ontology table. Live-verified the same day through E-utilities: the Entrez
# Gene record for gene 672 carries 117 GO cross-references (the human page
# itself sits behind a browser check for non-browser clients, so the record
# the page renders was read instead). So a GO vertex returned in the same
# row as a Gene vertex, or by a query anchored on one, is attributed to that
# gene's page, the page that carries the annotation, never to a fabricated
# GO page. This table names which prefixes' record pages carry GO
# annotations: today exactly one. HP and MONDO stay uncitable.
GO_ANNOTATION_HOST_PREFIXES: Final[tuple[str, ...]] = ("NCBIGene",)
GO_PREFIX: Final[str] = "GO"

# Review F-02 (2026-09-14): the vertex labels the graph carries GO terms
# under, derived from `LABEL_CURIE_PREFIXES` rather than retyped, so a
# label added to that table with the `GO` prefix is a GO-term label here
# too. A `GO:` id on any other label (a `Gene`, a `NamedThing` stub) is not
# a GO term this system can attribute to a gene page.
GO_TERM_LABELS: Final[tuple[str, ...]] = tuple(
    label for label, prefixes in LABEL_CURIE_PREFIXES.items() if prefixes == (GO_PREFIX,)
)
