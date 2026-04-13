---
name: architecture-patterns
description: Architectural patterns for the agentic-search-data-engineering ETL + KG repo. Adapted from the ncbi_ai_agents reference. Strips out async API, MCP, and Neo4j-specific content - this is a data pipeline + AGE graph repo, not a search agent API.
---

# Architecture patterns

These patterns apply to all System 1 (ETL) and System 2 (graph load) code. The core principle: **the pipeline is the product**. Quality of the data, not cleverness of the code, is what matters.

## Core principles

### 1. Idempotent pipeline steps

Every step must be safe to re-run. Cache downloads, skip work that's been done, write to temp files and atomic-rename. A pipeline run that crashes halfway should resume cleanly.

```python
# CORRECT
def download_file(url: str, dest: Path, force: bool = False) -> Path:
    if dest.exists() and not force:
        logger.info("Cache hit: %s", dest.name)
        return dest
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(dest)  # atomic
    return dest

# INCORRECT
def download_file(url: str, dest: Path) -> Path:
    urllib.request.urlretrieve(url, dest)  # no cache, no atomicity
    return dest
```

### 2. Provenance on every node and edge (non-negotiable)

Every node needs `id`, `category`, `name`, `source`, `source_url`. Every edge needs `subject`, `predicate`, `object`, `source`, `source_url`, plus evidence fields when available. No exceptions. This is the trust moat.

```python
# CORRECT
node = {
    "id": "NCBIGene:672",
    "category": "biolink:Gene",
    "name": "BRCA1",
    "source": "NCBI Gene",
    "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
    "xrefs": ["HGNC:1100"],
}

# INCORRECT
node = {"id": "NCBIGene:672", "name": "BRCA1"}  # no provenance
```

### 3. Validate, don't silently discard

Every record that fails validation must be logged with the reason and counted. Never use a silent filter.

```python
# CORRECT
rejected = 0
for record in records:
    try:
        validate_biolink_node(record)
        yield record
    except ValidationError as exc:
        logger.warning("rejected %s: %s", record.get("id"), exc)
        rejected += 1
logger.info("validation: %d kept, %d rejected", kept, rejected)

# INCORRECT
yield from (r for r in records if is_valid(r))  # how many got dropped? unknown.
```

### 4. Zero dangling edges policy

Every edge's `subject` and `object` must reference a node that exists in the graph. Reference pipeline pattern: detect dangling edges, inject MONDO/ontology stubs to repair them, never silently drop.

```python
# CORRECT (from reference assembly.py pattern)
def repair_dangling_edges(nodes_df, edges_df):
    node_ids = set(nodes_df["id"])
    dangling_subjects = set(edges_df["subject"]) - node_ids
    dangling_objects = set(edges_df["object"]) - node_ids
    stubs = make_stub_nodes(dangling_subjects | dangling_objects)
    return pd.concat([nodes_df, stubs]), edges_df
```

### 5. CURIE-first identifiers

Every `id` must be a CURIE (`prefix:local_id`). Canonical prefixes: `NCBIGene`, `NCBIProtein`, `ClinVar`, `MONDO`, `UMLS`, `GO`, `Reactome`, `MeSH`. See DECISIONS.md.

```python
# CORRECT
{"id": "NCBIGene:672"}

# INCORRECT
{"id": "672"}                # no prefix
{"id": "Gene:672"}           # not canonical
{"id": "ncbigene:672"}       # wrong case
```

## Pipeline pattern (5 steps every ETL follows)

```
Step 1: Download  → idempotent FTP/HTTP cache
Step 2: Parse     → database-specific reader, output Python objects
Step 3: Map       → assign BioLink categories, predicates, canonical CURIEs
Step 4: Validate  → LinkML validator, log rejections
Step 5: Export    → KGX TSV with provenance on every row
```

Shared utilities live in `system-01-data-pipelines/shared/`. Never duplicate.

## BioLink 4.x constants (verbatim from reference)

8 node categories:

- `biolink:Gene`
- `biolink:Protein`
- `biolink:SequenceVariant`
- `biolink:Disease`
- `biolink:BiologicalProcess`
- `biolink:MolecularActivity`
- `biolink:CellularComponent`
- `biolink:Pathway`

15 edge predicates (commonly used subset):

- `biolink:gene_associated_with_condition`
- `biolink:causes`
- `biolink:is_sequence_variant_of`
- `biolink:has_gene_product`
- `biolink:participates_in`
- `biolink:enables`
- `biolink:located_in`
- `biolink:part_of`
- `biolink:has_phenotype`
- `biolink:contributes_to`
- `biolink:treats`
- `biolink:has_input`
- `biolink:has_output`
- `biolink:regulates`
- `biolink:interacts_with`

## Apache AGE patterns

### Always wrap Cypher in `cypher()` SQL function

AGE has no native Cypher driver. You execute Cypher inside a SQL `SELECT` that calls `ag_catalog.cypher('graph_name', $$ ... $$)`.

```python
# CORRECT - parameterized via JSON ag_param
import json, psycopg2

cur.execute(
    """
    SELECT * FROM ag_catalog.cypher('ncbi_kg', $$
        MATCH (n:Gene {id: $gene_id}) RETURN n
    $$, %s) AS (n agtype);
    """,
    (json.dumps({"gene_id": gene_id}),),
)

# INCORRECT - string interpolation, injection risk
cur.execute(
    f"""
    SELECT * FROM ag_catalog.cypher('ncbi_kg', $$
        MATCH (n:Gene {{id: '{gene_id}'}}) RETURN n
    $$) AS (n agtype);
    """,
)
```

### Set search_path before every connection

AGE requires `ag_catalog` on the search path. Do this in your connection helper, not in every query.

```python
def connect_age():
    conn = psycopg2.connect(...)
    conn.set_session(autocommit=True)
    cur = conn.cursor()
    cur.execute("LOAD 'age';")
    cur.execute('SET search_path = ag_catalog, "$user", public;')
    return conn
```

### Batch loads, never row-by-row

AGE inserts are slow individually. Use multi-row Cypher `UNWIND` or COPY-style loads.

```python
# CORRECT
cur.execute(
    """
    SELECT * FROM ag_catalog.cypher('ncbi_kg', $$
        UNWIND $nodes AS n
        CREATE (g:Gene {id: n.id, name: n.name, source: n.source})
    $$, %s) AS (v agtype);
    """,
    (json.dumps({"nodes": batch_of_500}),),
)
```

## KGX export shape

Every pipeline writes two TSVs:

```
data/kgx/<database>/nodes.tsv
data/kgx/<database>/edges.tsv
```

Required node columns: `id`, `category`, `name`, `source`, `source_url`, `xrefs` (pipe-separated).
Required edge columns: `subject`, `predicate`, `object`, `source`, `source_url`, plus evidence-specific columns.

## Error handling

Specific exception types:

- `DownloadError` - FTP/HTTP failure after retries
- `ValidationError` - record fails BioLink schema
- `CrossReferenceError` - cross-database identifier resolution failed

Retry NCBI calls with exponential backoff. Pattern: `reference/ncbi_ai_agents-ncbi-kg/KG/pipeline/src/glucose_metabolism_kg/utils.py:35-86`.

## Performance targets

| Stage | Target | How |
|---|---|---|
| FTP download (cache hit) | <1s | Idempotent skip |
| Parse 1M rows ClinVar | <2 min | Chunked pandas read_csv (chunksize=200_000) |
| BioLink validate 100k records | <30s | LinkML compiled validators |
| AGE node load 100k | <1 min | UNWIND batches of 500 |
| KGX export 100k rows | <10s | Stream to TSV, no full materialization |

## Anti-patterns

- Loading large files entirely into memory (`pd.read_csv` without `chunksize`)
- Writing nodes/edges without `source` and `source_url`
- Silent record dropping
- String interpolation into Cypher inside `cypher()`
- Hardcoding `ncbi_kg` graph name in module-level constants - take it from config
- Adding async/FastAPI/LLM code to this repo - that's System 3, separate repo

## Quick checklist

Before committing pipeline code:

- [ ] Every step is idempotent (re-run is safe)
- [ ] Every node and edge has source + source_url
- [ ] Validation logs rejections, doesn't silently drop
- [ ] No dangling edges in output
- [ ] AGE Cypher is parameterized via `cypher(..., %s)` JSON params
- [ ] Large files are processed in chunks
- [ ] Module follows the 5-step pattern
