"""BioLink node and edge mapping with category and predicate registries.

Maps raw parsed records into BioLink-compliant node and edge dicts that
match the schema defined in schema/biolink_ncbi.yaml.

Depends on:
    - schema/biolink_ncbi.yaml (canonical category and predicate definitions)

Provides:
    - VALID_CATEGORIES: frozenset of the 10 biolink category strings
    - VALID_PREDICATES: frozenset of the 14 biolink predicate strings
    - map_node: build and validate a BioLink node dict
    - map_edge: build and validate a BioLink edge dict
    - validate_curie: check that a string is a valid CURIE

Called by:
    - system-01-data-pipelines/gene/mapper.py
    - system-01-data-pipelines/clinvar/mapper.py
    - system-01-data-pipelines/medgen/mapper.py
"""

import logging

logger = logging.getLogger(__name__)

# 10 node categories from schema/biolink_ncbi.yaml
VALID_CATEGORIES: frozenset[str] = frozenset(
    [
        "biolink:Gene",
        "biolink:SequenceVariant",
        "biolink:Disease",
        "biolink:PhenotypicFeature",
        "biolink:Article",
        "biolink:OrganismTaxon",
        "biolink:BiologicalProcess",
        "biolink:MolecularActivity",
        "biolink:CellularComponent",
        "biolink:OntologyClass",
    ]
)

# 14 predicates from schema/biolink_ncbi.yaml
VALID_PREDICATES: frozenset[str] = frozenset(
    [
        "biolink:gene_associated_with_condition",
        "biolink:is_sequence_variant_of",
        "biolink:has_phenotype",
        "biolink:participates_in",
        "biolink:actively_involved_in",
        "biolink:located_in",
        "biolink:mentioned_in",
        "biolink:has_mesh_annotation",
        "biolink:in_taxon",
        "biolink:subclass_of",
        "biolink:close_match",
        "biolink:exact_match",
        "biolink:orthologous_to",
        "biolink:cited_in",
    ]
)


def validate_curie(curie: str) -> bool:
    """Check that a string is a valid CURIE.

    A valid CURIE has exactly one colon, a non-empty prefix, and a non-empty
    local ID. Examples: "NCBIGene:672", "OMIM:143100", "biolink:Gene".

    Args:
        curie: The string to validate.

    Returns:
        True if the string is a valid CURIE, False otherwise.
    """
    if not isinstance(curie, str):
        return False
    parts = curie.split(":")
    if len(parts) != 2:
        return False
    prefix, local_id = parts
    return bool(prefix) and bool(local_id)


def map_node(
    id: str,
    category: str,
    name: str,
    source: str,
    source_url: str,
    **extra: object,
) -> dict:
    """Build a BioLink-compliant node dict.

    Validates that category is in VALID_CATEGORIES and that all required
    provenance fields are present and non-empty.

    Args:
        id: CURIE-formatted node identifier (e.g. "NCBIGene:672").
        category: BioLink category string (e.g. "biolink:Gene").
        name: Human-readable name for the node.
        source: Source database name (e.g. "NCBI Gene").
        source_url: URL of the source record. Must be non-empty.
        **extra: Additional fields added verbatim to the returned dict
                 (e.g. xrefs, description, synonyms).

    Returns:
        Dict with id, category, name, source, source_url, and any extra fields.

    Raises:
        ValueError: If category is not in VALID_CATEGORIES, or if any required
                    field is empty or None.
    """
    required_fields = {
        "id": id,
        "category": category,
        "name": name,
        "source": source,
        "source_url": source_url,
    }
    for field_name, value in required_fields.items():
        if not value:
            raise ValueError(
                f"map_node: required field '{field_name}' is empty or None"
            )

    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"map_node: invalid category '{category}'. "
            f"Must be one of: {sorted(VALID_CATEGORIES)}"
        )

    node: dict = {
        "id": id,
        "category": category,
        "name": name,
        "source": source,
        "source_url": source_url,
    }
    node.update(extra)

    logger.debug("mapped node id=%s category=%s", id, category)
    return node


def map_edge(
    subject: str,
    predicate: str,
    object: str,
    source: str,
    source_url: str,
    **extra: object,
) -> dict:
    """Build a BioLink-compliant edge dict.

    Validates that predicate is in VALID_PREDICATES and that all required
    provenance fields are present and non-empty.

    Args:
        subject: CURIE-formatted subject node identifier.
        predicate: BioLink predicate string (e.g. "biolink:gene_associated_with_condition").
        object: CURIE-formatted object node identifier.
        source: Source database name (e.g. "ClinVar").
        source_url: URL of the source record. Must be non-empty.
        **extra: Additional fields added verbatim to the returned dict
                 (e.g. evidence_type, pmids, clinical_significance).

    Returns:
        Dict with subject, predicate, object, source, source_url, and any extra fields.

    Raises:
        ValueError: If predicate is not in VALID_PREDICATES, or if any required
                    field is empty or None.
    """
    required_fields = {
        "subject": subject,
        "predicate": predicate,
        "object": object,
        "source": source,
        "source_url": source_url,
    }
    for field_name, value in required_fields.items():
        if not value:
            raise ValueError(
                f"map_edge: required field '{field_name}' is empty or None"
            )

    if predicate not in VALID_PREDICATES:
        raise ValueError(
            f"map_edge: invalid predicate '{predicate}'. "
            f"Must be one of: {sorted(VALID_PREDICATES)}"
        )

    edge: dict = {
        "subject": subject,
        "predicate": predicate,
        "object": object,
        "source": source,
        "source_url": source_url,
    }
    edge.update(extra)

    logger.debug(
        "mapped edge subject=%s predicate=%s object=%s",
        subject,
        predicate,
        object,
    )
    return edge
