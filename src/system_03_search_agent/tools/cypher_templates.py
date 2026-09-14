"""Deterministic Cypher templates for the question shapes the graph answers
every day, chosen in code so the same question retrieves the same records.

UI fix set 10, item 10.1 (R34). The product owner's standard, 2026-09-13:
"the exact words can be different but a user should get exact sources which
must be consistent." Measured before this module existed, the same question
did not: "Which diseases are associated with BRCA1?" returned 4 sources on
one run and 5 on the next, and the 2026-09-13 consistency baseline showed 1
of 50 golden questions answering every time. The variance came from
`cypher_query._run_pipeline`, where a plan-tier model WROTE the Cypher for
every question. One follow-up produced `RETURN sv, sv.id`, `RETURN v, v.id,
v.name`, `RETURN s, s.id, s.name, g, g.id, g.name` and a `MATCH path = ...`
variant on different runs, with different row counts and different
citeable rows, and none of them carried an ORDER BY, so even an identical
query could return its rows in whatever order the planner chose.

This module removes the model from the path for the shapes that can be
named from the graph's own 14 edge labels (`graph_schema_constants.
EDGE_LABELS`) and the bound entities' CURIE prefixes. Selection is a pure
function of three things and nothing else: which vertex label the bound
CURIEs belong to, how many are bound, and a conservative word-boundary
keyword test on `query_intent`. Every template:

- is parameterised on the bound entity names `cypher_query.
  entity_param_bindings` already assigns, so the F-2.1-B01 naming contract
  holds on this path exactly as on the generated one;
- returns the whole vertex, never a bare property, so
  `cypher_provenance.to_output_rows` has the `id`, `name` and `source_url`
  the citation path needs;
- carries an `ORDER BY` on the record id, a stable key, so the same rows
  come back in the same order on every run, and leaves the LIMIT to
  `cypher_validator.validate_cypher`, which injects the caller's
  `row_limit` after the ORDER BY exactly as it does for a generated query.

What this module deliberately does NOT do. It does not bypass the gate:
the chosen template still passes through `validate_cypher` and every
static binding check in `cypher_query`, then the same execution and row
shaping as a generated query. And it does not guess: when the keyword test
matches two shapes at once ("the gene record, associated conditions,
clinically significant variants"), when the bound CURIEs span two vertex
labels, or when no shape matches at all, `select_template` returns None
and the model path runs exactly as before. Falling back is the honest
answer to an ambiguous question; a wrong template answered consistently
would be F-2.1-B01 with better reproducibility.

Depends on:
    - system_03_search_agent.tools.cypher_schemas (CypherQueryInput,
      QueryClass)
    - system_03_search_agent.tools.graph_schema_constants (EDGE_LABELS,
      EDGE_ENDPOINTS, LABEL_CURIE_PREFIXES, VERTEX_LABELS): every label a
      template names is asserted present at import time, so a template
      can never reference an edge the graph does not have.

Reads:
    - Nothing at import time beyond the constants above.

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.tools.cypher_query (the template path in
      `_run_pipeline`)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from system_03_search_agent.tools.cypher_schemas import CypherQueryInput, QueryClass
from system_03_search_agent.tools.graph_schema_constants import (
    EDGE_ENDPOINTS,
    EDGE_LABELS,
    LABEL_CURIE_PREFIXES,
    VERTEX_LABELS,
)

# The longest template name, bounded so `CypherQueryOutput.template` can
# carry a fixed max_length.
MAX_TEMPLATE_NAME_CHARS: Final[int] = 60


@dataclass(frozen=True)
class CypherTemplate:
    """One code-chosen query. `cypher` references only the `$e_...` names
    in the caller's `entity_bindings`; `edge_label` is the single edge the
    template traverses, or None for a bare record lookup or an aggregate.
    """

    name: str
    cypher: str
    edge_label: str | None


# --------------------------------------------------------------------------
# Which vertex label a bound CURIE belongs to. Inverted from
# LABEL_CURIE_PREFIXES so the two cannot disagree.
# --------------------------------------------------------------------------

_LABEL_BY_PREFIX: Final[dict[str, str]] = {
    prefix: label
    for label, prefixes in LABEL_CURIE_PREFIXES.items()
    for prefix in prefixes
    if label in ("Gene", "Disease", "Article")
}


def anchor_label_for(curies: list[str]) -> str | None:
    """Return the one vertex label every CURIE in `curies` belongs to, or
    None when they span labels, when any prefix is not one this module
    templates (SequenceVariant, OntologyClass and the GO labels are
    answered by the model path), or when the list is empty.
    """
    labels: set[str] = set()
    for curie in curies:
        prefix, sep, _ = curie.partition(":")
        if not sep:
            return None
        label = _LABEL_BY_PREFIX.get(prefix)
        if label is None:
            return None
        labels.add(label)
    if len(labels) != 1:
        return None
    return labels.pop()


# --------------------------------------------------------------------------
# The keyword test. Word-boundary, case-insensitive, deliberately narrow:
# a word that appears in questions about several shapes ("associated",
# "linked", "gene" in a gene-anchored question) is not a discriminator and
# is not listed. "Krankheit" is here because golden row G-050 asks the
# BRCA1 disease question in German and the entity resolves the same way.
# --------------------------------------------------------------------------

_SHAPE_KEYWORDS: Final[dict[str, str]] = {
    "diseases": r"\b(disease|diseases|condition|conditions|disorder|disorders|krankheit|krankheiten)\b",
    "variants": r"\b(variant|variants|mutation|mutations|allele|alleles|clinvar)\b",
    "orthologs": r"\b(ortholog|orthologs|orthologous|homolog|homologs|homologous)\b",
    "processes": r"\b(biological\s+process|biological\s+processes|pathway|pathways|participates?)\b",
    "activities": r"\b(molecular\s+activity|molecular\s+activities|molecular\s+function|molecular\s+functions)\b",
    "components": r"\b(cellular\s+component|cellular\s+components|subcellular|localis|localiz|located|where\s+in\s+the\s+cell)",
    "taxon": r"\b(organism|organisms|taxon|taxonomy)\b",
    "articles": r"\b(paper|papers|article|articles|publication|publications|literature|pubmed|mention|mentions|mentioned)\b",
    "genes": r"\b(gene|genes)\b",
    "phenotypes": r"\b(phenotype|phenotypes|phenotypic|symptom|symptoms|clinical\s+features?)\b",
    "mesh": r"\bmesh\b",
}
_SHAPE_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    shape: re.compile(pattern, re.IGNORECASE) for shape, pattern in _SHAPE_KEYWORDS.items()
}

# "How many" questions become a count over the same hop. "How many" is
# unambiguous and switches the template to its count form on any query
# class: the tool's premise gate sends every question as `lookup`, and a
# reader asking "how many" wants a number whatever Think called it. The
# weaker words ("count", "number of") switch only when Think also
# classified the question as an aggregate, so a lookup that happens to
# contain "number" keeps returning records.
_HOW_MANY_PATTERN: Final[re.Pattern[str]] = re.compile(r"\bhow\s+many\b", re.IGNORECASE)
_WEAK_COUNT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(count|number\s+of)\b", re.IGNORECASE
)


def _wants_count(tool_input: CypherQueryInput) -> bool:
    if _HOW_MANY_PATTERN.search(tool_input.query_intent):
        return True
    return tool_input.query_class is QueryClass.AGGREGATE and bool(
        _WEAK_COUNT_PATTERN.search(tool_input.query_intent)
    )

# --------------------------------------------------------------------------
# The hop table. One row per (anchor label, shape): the edge label, the
# other endpoint's label, and whether the anchor is the edge's source
# ("out") or its target ("in"). Every label is asserted against the graph
# constants at import time below.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Hop:
    edge_label: str
    other_label: str
    direction: str  # "out": anchor -[edge]-> other; "in": other -[edge]-> anchor


_HOPS: Final[dict[tuple[str, str], _Hop]] = {
    ("Gene", "diseases"): _Hop("gene_associated_with_condition", "Disease", "out"),
    ("Gene", "variants"): _Hop("is_sequence_variant_of", "SequenceVariant", "in"),
    ("Gene", "orthologs"): _Hop("orthologous_to", "Gene", "out"),
    ("Gene", "processes"): _Hop("participates_in", "BiologicalProcess", "out"),
    ("Gene", "activities"): _Hop("actively_involved_in", "MolecularActivity", "out"),
    ("Gene", "components"): _Hop("located_in", "CellularComponent", "out"),
    ("Gene", "taxon"): _Hop("in_taxon", "OrganismTaxon", "out"),
    ("Gene", "articles"): _Hop("mentioned_in", "Article", "out"),
    ("Disease", "genes"): _Hop("gene_associated_with_condition", "Gene", "in"),
    ("Disease", "phenotypes"): _Hop("has_phenotype", "PhenotypicFeature", "out"),
    ("Article", "mesh"): _Hop("has_mesh_annotation", "OntologyClass", "out"),
}

# Shapes a given anchor label can be asked about. A keyword from another
# anchor's shape list ("gene" in a gene-anchored question) is ignored
# rather than counted as ambiguity.
_SHAPES_BY_ANCHOR: Final[dict[str, tuple[str, ...]]] = {
    "Gene": tuple(shape for (anchor, shape) in _HOPS if anchor == "Gene"),
    "Disease": tuple(shape for (anchor, shape) in _HOPS if anchor == "Disease"),
    "Article": tuple(shape for (anchor, shape) in _HOPS if anchor == "Article"),
}

# Variable names, fixed so the ORDER BY key and the RETURN list are stable
# text and so `cypher_query`'s edge-type derivation resolves each column.
_ANCHOR_VAR: Final[str] = "a"
_OTHER_VAR: Final[str] = "x"


def _assert_templates_name_real_labels() -> None:
    """Import-time guard: a template can only ever name a label the graph
    has, with the endpoint pair the graph documents for it."""
    for (anchor, _shape), hop in _HOPS.items():
        if hop.edge_label not in EDGE_LABELS:
            raise AssertionError(f"template names unknown edge label {hop.edge_label!r}")
        if anchor not in VERTEX_LABELS or hop.other_label not in VERTEX_LABELS:
            raise AssertionError(f"template names unknown vertex label for {hop.edge_label!r}")
        endpoints = EDGE_ENDPOINTS.get(hop.edge_label)
        if endpoints is None:
            raise AssertionError(f"template uses mixed-endpoint edge {hop.edge_label!r}")
        expected = (anchor, hop.other_label) if hop.direction == "out" else (hop.other_label, anchor)
        if endpoints != expected:
            raise AssertionError(
                f"template endpoints {expected} disagree with the graph's {endpoints} "
                f"for {hop.edge_label!r}"
            )


_assert_templates_name_real_labels()


def matched_shapes(query_intent: str, anchor_label: str) -> list[str]:
    """The shapes whose keyword test fires on `query_intent`, restricted to
    the shapes `anchor_label` can be asked about, ordered by where in the
    question the first matching word appears. Exposed so a test can assert
    the ambiguity rule directly."""
    candidates = _SHAPES_BY_ANCHOR.get(anchor_label, ())
    positioned: list[tuple[int, str]] = []
    for shape in candidates:
        match = _SHAPE_PATTERNS[shape].search(query_intent)
        if match is not None:
            positioned.append((match.start(), shape))
    return [shape for _, shape in sorted(positioned)]


# Query classes on which a question naming two shapes is read as asking for
# the FIRST one named ("What variants cause disease in BRCA1?" asks for
# variants; "Which diseases are associated with BRCA1 variants?" asks for
# diseases). A multi-hop or exploratory question naming two shapes may
# genuinely want both, and the graph cannot join a gene's variants to its
# diseases in one hop, so those go to the model path.
_FIRST_SHAPE_WINS_CLASSES: Final[frozenset[QueryClass]] = frozenset(
    {QueryClass.LOOKUP, QueryClass.SINGLE_HOP, QueryClass.AGGREGATE}
)


def _resolve_shape(tool_input: CypherQueryInput, shapes: list[str]) -> str | None:
    """Pick the one shape a question asks for, or None when it is ambiguous.

    One shape: that one. Two shapes on a lookup, single-hop or aggregate
    question: the one named first. Anything else: None, the model path.
    """
    if len(shapes) == 1:
        return shapes[0]
    if len(shapes) == 2 and tool_input.query_class in _FIRST_SHAPE_WINS_CLASSES:
        return shapes[0]
    return None


def _labels_by_param(entity_bindings: dict[str, str]) -> dict[str, str | None]:
    return {
        name: _LABEL_BY_PREFIX.get(curie.partition(":")[0]) for name, curie in entity_bindings.items()
    }


def _mixed_gene_disease_template(
    tool_input: CypherQueryInput, entity_bindings: dict[str, str]
) -> CypherTemplate | None:
    """A question binding gene AND disease CURIEs together, the shape
    "Variants in GCK causing MODY" or "Is BRCA1 linked to breast cancer?"
    resolves to. Two forms only, both narrow:

    - The variants shape: the graph has no variant-to-disease edge
      (`is_sequence_variant_of` joins a variant to its gene and nothing
      else), so the answer the graph can give is the gene's variants. The
      disease binding goes unused on purpose rather than pretending a join
      exists; `cypher_query._build_params` binds only the names the query
      references.
    - No shape, or the diseases shape, with exactly one gene and one
      disease: the link between them, `gene_associated_with_condition`
      anchored at both ends. One row or none, and "none" is the honest
      answer to "is this gene linked to that disease" when the graph has
      no such edge.

    Anything else is None.
    """
    labels = _labels_by_param(entity_bindings)
    if set(labels.values()) != {"Gene", "Disease"}:
        return None
    gene_params = [name for name, label in labels.items() if label == "Gene"]
    disease_params = [name for name, label in labels.items() if label == "Disease"]
    shapes = matched_shapes(tool_input.query_intent, "Gene")
    shape = _resolve_shape(tool_input, shapes) if shapes else None
    if shapes and shape is None:
        return None
    if shape == "variants":
        if _wants_count(tool_input):
            return None
        return _hop_template("variants", _HOPS[("Gene", "variants")], "Gene", gene_params, False)
    if shape in (None, "diseases") and len(gene_params) == 1 and len(disease_params) == 1:
        return CypherTemplate(
            name="gene_disease_link",
            cypher=(
                f"MATCH ({_ANCHOR_VAR}:Gene {{id: ${gene_params[0]}}})"
                f"-[:gene_associated_with_condition]->"
                f"({_OTHER_VAR}:Disease {{id: ${disease_params[0]}}}) "
                f"RETURN {_OTHER_VAR} ORDER BY {_OTHER_VAR}.id"
            ),
            edge_label="gene_associated_with_condition",
        )
    return None


def _pattern(hop: _Hop, anchor_label: str, anchor_clause: str) -> str:
    anchor_node = f"({_ANCHOR_VAR}:{anchor_label}{anchor_clause})"
    other_node = f"({_OTHER_VAR}:{hop.other_label})"
    if hop.direction == "out":
        return f"MATCH {anchor_node}-[:{hop.edge_label}]->{other_node}"
    return f"MATCH {other_node}-[:{hop.edge_label}]->{anchor_node}"


def _hop_template(
    shape: str,
    hop: _Hop,
    anchor_label: str,
    param_names: list[str],
    count: bool,
) -> CypherTemplate:
    """Build the hop template for one or several anchors.

    One anchor: `MATCH (a:Gene {id: $e})-[:edge]->(x:Other) RETURN x ORDER
    BY x.id`. Several: the anchors are bound through an IN list and the
    anchor is returned beside each record so the answer can say which
    gene each disease belongs to, ordered by anchor id then record id. The
    count form returns only the aggregate, never a bare property beside
    it (cypher_generation rule 7: that silently groups and the count
    becomes wrong).
    """
    if len(param_names) == 1:
        match = _pattern(hop, anchor_label, f" {{id: ${param_names[0]}}}")
        where = ""
        suffix = "one"
    else:
        match = _pattern(hop, anchor_label, "")
        where = f" WHERE {_ANCHOR_VAR}.id IN [" + ", ".join(f"${n}" for n in param_names) + "]"
        suffix = "many"
    name = f"{anchor_label.lower()}_{shape}_{suffix}"
    if count:
        return CypherTemplate(
            name=name + "_count",
            cypher=f"{match}{where} RETURN count(DISTINCT {_OTHER_VAR}) AS {shape}_count",
            edge_label=hop.edge_label,
        )
    if len(param_names) == 1:
        returns = f"RETURN {_OTHER_VAR} ORDER BY {_OTHER_VAR}.id"
    else:
        returns = (
            f"RETURN {_ANCHOR_VAR}, {_OTHER_VAR} ORDER BY {_ANCHOR_VAR}.id, {_OTHER_VAR}.id"
        )
    return CypherTemplate(name=name, cypher=f"{match}{where} {returns}", edge_label=hop.edge_label)


def _record_template(anchor_label: str, param_names: list[str]) -> CypherTemplate:
    """The record itself: `MATCH (a:Gene {id: $e}) RETURN a`, or the IN-list
    form ordered by id when several are bound."""
    if len(param_names) == 1:
        cypher = f"MATCH ({_ANCHOR_VAR}:{anchor_label} {{id: ${param_names[0]}}}) RETURN {_ANCHOR_VAR}"
        suffix = "one"
    else:
        cypher = (
            f"MATCH ({_ANCHOR_VAR}:{anchor_label}) WHERE {_ANCHOR_VAR}.id IN ["
            + ", ".join(f"${n}" for n in param_names)
            + f"] RETURN {_ANCHOR_VAR} ORDER BY {_ANCHOR_VAR}.id"
        )
        suffix = "many"
    return CypherTemplate(
        name=f"{anchor_label.lower()}_record_{suffix}", cypher=cypher, edge_label=None
    )


def select_template(
    tool_input: CypherQueryInput, entity_bindings: dict[str, str]
) -> CypherTemplate | None:
    """Choose the template for `tool_input`, or None to run the model path.

    The decision, in order:

    1. Every bound CURIE must belong to one of Gene, Disease or Article, and
       all to the same one. Gene and Disease CURIEs bound together take the
       two narrow forms `_mixed_gene_disease_template` names; any other mix
       is None.
    2. The anchor's shapes are tested against the question. One match is
       the shape. Two matches on a lookup, single-hop or aggregate question
       resolve to the one named first in the question; two on a multi-hop
       or exploratory question, or three or more anywhere, are ambiguous:
       None. Zero falls through to step 3.
    3. With no shape matched, a `lookup` question about the entity is the
       record itself. Any other class with no shape is None.
    4. A matched hop on a question asking "how many" (any class), or on an
       `aggregate` question saying "count" or "number of", becomes the
       count form, for a single anchor only (a count over several anchors
       has no single record to cite it to, the same refusal
       `cypher_query._derived_source_curie` already makes, so it goes to
       the model path).
    """
    if not entity_bindings:
        return None
    param_names = list(entity_bindings)
    anchor_label = anchor_label_for(list(entity_bindings.values()))
    if anchor_label is None:
        return _mixed_gene_disease_template(tool_input, entity_bindings)

    shapes = matched_shapes(tool_input.query_intent, anchor_label)
    if not shapes:
        if tool_input.query_class is QueryClass.LOOKUP:
            return _record_template(anchor_label, param_names)
        return None
    shape = _resolve_shape(tool_input, shapes)
    if shape is None:
        return None
    hop = _HOPS[(anchor_label, shape)]
    wants_count = _wants_count(tool_input)
    if wants_count and len(param_names) > 1:
        return None
    return _hop_template(shape, hop, anchor_label, param_names, count=wants_count)


def all_template_examples() -> list[CypherTemplate]:
    """Every template this module can produce, instantiated once each with
    placeholder parameter names. For the test that proves each one passes
    `validate_cypher` and carries its ORDER BY, not for production use."""
    examples: list[CypherTemplate] = []
    one = ["e_one"]
    many = ["e_one", "e_two"]
    for (anchor, shape), hop in _HOPS.items():
        examples.append(_hop_template(shape, hop, anchor, one, count=False))
        examples.append(_hop_template(shape, hop, anchor, many, count=False))
        examples.append(_hop_template(shape, hop, anchor, one, count=True))
    for anchor in _SHAPES_BY_ANCHOR:
        examples.append(_record_template(anchor, one))
        examples.append(_record_template(anchor, many))
    link = _mixed_gene_disease_template(
        CypherQueryInput(query_intent="link", query_class="lookup", target_entities=[]),
        {"e_one": "NCBIGene:1", "e_two": "MedGen:C1"},
    )
    if link is None:
        raise AssertionError("the gene_disease_link template did not build")
    examples.append(link)
    return examples
