---
name: testing-standards
description: Testing standards for the agentic-search-data-engineering project. Adapted from the ncbi_ai_agents reference repo. Focused on ETL pipelines, BioLink validation, and KGX export, not on agent or API testing.
---

# Testing standards

These standards apply to all tests in this repo. The work here is ETL and graph load - tests should verify pipeline correctness, BioLink compliance, and graph integrity.

## Coverage requirements

Minimum 70% line coverage on `system-01-data-pipelines/` and `system-02-knowledge-graph/`. Critical paths (assembly, validation, export) target 90%.

```bash
pytest --cov=system-01-data-pipelines --cov=system-02-knowledge-graph --cov-report=term-missing
```

| Priority | Module type | Target |
|---|---|---|
| 1 | Validation, assembly, dedup | 90%+ |
| 2 | Per-database parsers (gene, clinvar, medgen) | 80%+ |
| 3 | Utilities, helpers, config | 70%+ |

## Directory structure

```
tests/
├── unit/                   # No external services - mocks only
│   ├── test_assembly.py
│   ├── test_biolink_validator.py
│   ├── test_clinvar_parser.py
│   └── test_gene_parser.py
├── integration/            # Requires real PostgreSQL + AGE
│   ├── test_age_loader.py
│   └── test_kgx_roundtrip.py
├── fixtures/               # Test data: tiny gzipped samples, BioLink stubs
│   ├── clinvar_sample.tsv.gz
│   └── gene_info_sample.gz
└── conftest.py             # Pytest configuration, shared fixtures
```

## Naming convention

Format: `test_<function_name>_<scenario>_<expected_result>`

```python
def test_parse_clinvar_chunk_with_pathogenic_filter_returns_only_pathogenic():
    pass

def test_assemble_kg_with_dangling_mondo_edge_creates_stub_node():
    pass

def test_biolink_validate_node_missing_category_raises_validation_error():
    pass

def test_download_file_when_cached_skips_network_call():
    pass
```

Test classes use `Test<Subject>`:

```python
class TestClinVarParser:
    """Test suite for ClinVar variant_summary parsing."""

class TestAssembly:
    """Test suite for KG assembly: dedup, dangling edges, MONDO stubs."""
```

## Mocking strategies

### Mock NCBI APIs and FTP

Tests must never hit real NCBI servers. Use fixtures with sample bytes.

```python
@pytest.fixture
def mock_entrez(mocker):
    """Mock NCBI Entrez calls."""
    return mocker.patch("data_pipelines.shared.entrez.entrez_esearch")

def test_fetch_disease_genes_calls_entrez(mock_entrez):
    mock_entrez.return_value = ["672", "675", "5728"]
    result = fetch_disease_genes("breast cancer")
    assert result == ["672", "675", "5728"]
    mock_entrez.assert_called_once_with("gene", "breast cancer")
```

### Mock FTP downloads with sample files

Keep tiny gzipped samples in `tests/fixtures/`. Each should be under 50KB.

```python
@pytest.fixture
def clinvar_sample_path():
    """Path to a 100-row ClinVar sample file."""
    return Path(__file__).parent / "fixtures" / "clinvar_sample.tsv.gz"

def test_parse_clinvar_chunk_pathogenic_filter(clinvar_sample_path):
    config = PipelineConfig(clinvar_significance="Pathogenic")
    chunks = list(parse_clinvar(clinvar_sample_path, config))
    assert all(chunk["ClinicalSignificance"].eq("Pathogenic").all() for chunk in chunks)
```

### Mock PostgreSQL + AGE for unit tests

Use `psycopg2`'s test fixtures or `pytest-mock`. Real AGE goes in integration tests only.

```python
@pytest.fixture
def mock_age_cursor(mocker):
    cursor = mocker.MagicMock()
    cursor.fetchall.return_value = [("Gene", "NCBIGene:672")]
    return cursor

def test_load_nodes_executes_cypher_create(mock_age_cursor):
    load_nodes(mock_age_cursor, [{"id": "NCBIGene:672", "category": "biolink:Gene"}])
    assert mock_age_cursor.execute.called
```

## Fixtures and parametrize

### Fixtures for canonical test data

```python
@pytest.fixture
def sample_gene_node():
    return {
        "id": "NCBIGene:672",
        "category": "biolink:Gene",
        "name": "BRCA1",
        "symbol": "BRCA1",
        "source": "NCBI Gene",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
    }

@pytest.fixture
def sample_disease_node():
    return {
        "id": "MONDO:0007254",
        "category": "biolink:Disease",
        "name": "breast cancer",
        "source": "MONDO",
        "source_url": "https://monarchinitiative.org/MONDO:0007254",
    }
```

### Parametrize for predicate validation

```python
@pytest.mark.parametrize("predicate,expected", [
    ("biolink:gene_associated_with_condition", True),
    ("biolink:causes", True),
    ("biolink:is_sequence_variant_of", True),
    ("causes", False),  # missing prefix
    ("biolink:nonsense_predicate", False),  # not in vocabulary
    ("", False),
])
def test_validate_predicate(predicate, expected):
    assert is_valid_biolink_predicate(predicate) == expected
```

## Integration tests

Use the `@pytest.mark.integration` marker. Skip in CI unless `RUN_INTEGRATION=1`.

```python
@pytest.mark.integration
def test_age_kgx_roundtrip(age_connection):
    """Load a tiny KGX file into AGE and query it back."""
    nodes = [{"id": "NCBIGene:672", "category": "biolink:Gene", "name": "BRCA1"}]
    edges = [
        {"subject": "NCBIGene:672", "predicate": "biolink:gene_associated_with_condition",
         "object": "MONDO:0007254"}
    ]
    loader = AGELoader(age_connection, graph_name="test_kg")
    loader.load_nodes(nodes)
    loader.load_edges(edges)

    result = age_connection.cypher("test_kg", "MATCH (g:Gene)-->(d:Disease) RETURN g.name, d.name")
    assert result == [("BRCA1", "breast cancer")]
```

```python
# conftest.py
@pytest.fixture
def age_connection():
    """Real PostgreSQL + AGE connection. Skipped if RUN_INTEGRATION not set."""
    if not os.getenv("RUN_INTEGRATION"):
        pytest.skip("set RUN_INTEGRATION=1 to run integration tests")
    conn = psycopg2.connect(host="localhost", dbname="ncbi_kg_test", user="postgres")
    conn.set_session(autocommit=True)
    yield conn
    conn.close()
```

## BioLink-specific test patterns

### Validate every fixture against BioLink

Tests should not pass with malformed BioLink data. Use the validator on every fixture at test setup.

```python
@pytest.fixture(autouse=True)
def validate_fixtures(sample_gene_node, sample_disease_node):
    validate_biolink_node(sample_gene_node)
    validate_biolink_node(sample_disease_node)
```

### Test the zero-dangling-edges policy

```python
def test_assemble_kg_dangling_mondo_creates_stub():
    nodes = [{"id": "NCBIGene:672", "category": "biolink:Gene"}]
    edges = [{
        "subject": "NCBIGene:672",
        "predicate": "biolink:causes",
        "object": "MONDO:0007254",  # not in nodes!
    }]
    final_nodes, final_edges = assemble_kg(nodes, edges)
    assert any(n["id"] == "MONDO:0007254" for n in final_nodes)
    assert all(
        e["subject"] in {n["id"] for n in final_nodes}
        and e["object"] in {n["id"] for n in final_nodes}
        for e in final_edges
    )
```

## Test markers

```python
# Unit tests (default, fast, no external deps)
@pytest.mark.unit
def test_parse_gene_info(): pass

# Integration tests (real PG + AGE, slow)
@pytest.mark.integration
def test_age_loader(): pass

# Smoke tests (real NCBI FTP, very slow, only run before release)
@pytest.mark.smoke
def test_real_ncbi_gene_download(): pass
```

```ini
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "unit: fast unit tests with mocks",
    "integration: requires PostgreSQL + AGE",
    "smoke: requires real NCBI FTP, very slow",
]
```

## Usage

When writing or reviewing tests in this repo, use this skill to ensure proper coverage, naming, mocking discipline (no real NCBI calls in unit tests), and BioLink validation discipline.
