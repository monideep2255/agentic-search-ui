"""Tests for the BioLink NCBI schema definition.

Validates that schema/biolink_ncbi.yaml defines all expected node categories,
edge predicates, and required fields for nodes and edges.

The schema uses LinkML structure:
    - Node categories are enum values in enums.CategoryEnum.permissible_values
    - Predicates are enum values in enums.PredicateEnum.permissible_values
    - Required fields are enforced via slot_usage on base classes (Node, Association)

Depends on:
    - schema/biolink_ncbi.yaml
    - tests/conftest.py (schema_path fixture)
    - pyyaml
"""

from pathlib import Path
from typing import Any

import pytest
import yaml


# Categories use the biolink: prefix as they appear in the CategoryEnum
EXPECTED_CATEGORIES: set[str] = {
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
}

# Predicates use the biolink: prefix as they appear in the PredicateEnum
EXPECTED_PREDICATES: set[str] = {
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
}

NODE_REQUIRED_FIELDS: set[str] = {"id", "category", "name", "source", "source_url"}
EDGE_REQUIRED_FIELDS: set[str] = {"subject", "predicate", "object", "source", "source_url"}


def _load_schema(schema_path: Path) -> dict[str, Any]:
    """Load and return the YAML schema as a dict."""
    with open(schema_path) as f:
        return yaml.safe_load(f)


def test_schema_file_exists(schema_path: Path) -> None:
    """The schema file must exist on disk."""
    assert schema_path.exists(), f"Schema file not found at {schema_path}"


def test_schema_has_all_node_categories(schema_path: Path) -> None:
    """The CategoryEnum must define all 10 node categories."""
    if not schema_path.exists():
        pytest.skip("Schema file does not exist yet")

    schema = _load_schema(schema_path)
    category_enum = schema.get("enums", {}).get("CategoryEnum", {})
    defined_categories = set(category_enum.get("permissible_values", {}).keys())

    missing = EXPECTED_CATEGORIES - defined_categories
    assert not missing, f"Missing node categories in CategoryEnum: {missing}"


def test_schema_has_all_predicates(schema_path: Path) -> None:
    """The PredicateEnum must define all 12+ predicates."""
    if not schema_path.exists():
        pytest.skip("Schema file does not exist yet")

    schema = _load_schema(schema_path)
    predicate_enum = schema.get("enums", {}).get("PredicateEnum", {})
    defined_predicates = set(predicate_enum.get("permissible_values", {}).keys())

    missing = EXPECTED_PREDICATES - defined_predicates
    assert not missing, f"Missing predicates in PredicateEnum: {missing}"


def test_schema_node_required_fields(schema_path: Path) -> None:
    """The base Node class must require id, category, name, source, source_url."""
    if not schema_path.exists():
        pytest.skip("Schema file does not exist yet")

    schema = _load_schema(schema_path)
    classes = schema.get("classes", {})

    # Find the base node class (Node or NamedThing)
    base_class_name = None
    for candidate in ("Node", "NamedThing"):
        if candidate in classes:
            base_class_name = candidate
            break

    assert base_class_name is not None, (
        "No base node class found (expected Node or NamedThing)"
    )

    base_class = classes[base_class_name]

    # In LinkML, fields are declared via slots (list of slot names) and
    # required status is set in slot_usage or in the top-level slots section.
    declared_slots = set(base_class.get("slots", []))
    slot_usage = base_class.get("slot_usage", {})

    # Also check top-level slots for required status
    top_level_slots = schema.get("slots", {})

    missing_slots = NODE_REQUIRED_FIELDS - declared_slots
    assert not missing_slots, (
        f"Base node class missing slots: {missing_slots}"
    )

    # Check each required field is marked required in slot_usage or top-level slots
    not_required: set[str] = set()
    for field in NODE_REQUIRED_FIELDS:
        usage_required = slot_usage.get(field, {}).get("required", False)
        top_required = top_level_slots.get(field, {}).get("required", False)
        if not (usage_required or top_required):
            not_required.add(field)

    assert not not_required, (
        f"These node fields should be required but are not: {not_required}"
    )


def test_schema_edge_required_fields(schema_path: Path) -> None:
    """The base Association class must require subject, predicate, object, source, source_url."""
    if not schema_path.exists():
        pytest.skip("Schema file does not exist yet")

    schema = _load_schema(schema_path)
    classes = schema.get("classes", {})

    # Find the base edge class (Association or Edge)
    base_class_name = None
    for candidate in ("Association", "Edge"):
        if candidate in classes:
            base_class_name = candidate
            break

    assert base_class_name is not None, (
        "No base edge class found (expected Association or Edge)"
    )

    base_class = classes[base_class_name]

    declared_slots = set(base_class.get("slots", []))
    slot_usage = base_class.get("slot_usage", {})
    top_level_slots = schema.get("slots", {})

    missing_slots = EDGE_REQUIRED_FIELDS - declared_slots
    assert not missing_slots, (
        f"Base edge class missing slots: {missing_slots}"
    )

    not_required: set[str] = set()
    for field in EDGE_REQUIRED_FIELDS:
        usage_required = slot_usage.get(field, {}).get("required", False)
        top_required = top_level_slots.get(field, {}).get("required", False)
        if not (usage_required or top_required):
            not_required.add(field)

    assert not not_required, (
        f"These edge fields should be required but are not: {not_required}"
    )
