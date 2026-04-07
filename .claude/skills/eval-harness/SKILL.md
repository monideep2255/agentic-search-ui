---
name: eval-harness
description: Evaluation harness for the data pipelines and knowledge graph. Defines pass criteria for BioLink validation, dangling-edge zero-policy, KGX shape, and provenance coverage. Adapted from personal-os-work eval-harness for ETL context (no AI bot pass@k metrics).
---

# Eval harness: pipeline + KG quality gates

Define what "good" means BEFORE running a pipeline. Then measure whether the run meets those criteria. Without explicit gates, regressions go unnoticed.

## When to use

- Before first end-to-end run of a new pipeline
- After modifying assembly, validation, or export logic
- Before merging KGX files into the AGE graph
- When promoting a pipeline from dev to "ready" status

## Quality gates (System 1: pipeline output)

### Gate 1: BioLink schema compliance

| Check | Pass condition | How |
|---|---|---|
| Every node has `id`, `category`, `name`, `source`, `source_url` | 100% of rows | LinkML validator |
| Every `category` matches `biolink:*` | 100% | Regex check |
| Every `id` is a CURIE | 100% | `prefix:local_id` pattern |
| Every edge has `subject`, `predicate`, `object`, `source` | 100% | Schema check |
| Every `predicate` matches `biolink:*` | 100% | Regex check |

Target: zero validation errors. Any failure blocks the run.

### Gate 2: Dangling edges zero-policy

```python
def assert_no_dangling_edges(nodes_df, edges_df):
    node_ids = set(nodes_df["id"])
    dangling = (set(edges_df["subject"]) | set(edges_df["object"])) - node_ids
    assert not dangling, f"{len(dangling)} dangling edges: {list(dangling)[:10]}"
```

Target: 0 dangling edges. Repair via stub injection (see architecture-patterns), never drop.

### Gate 3: Provenance coverage

| Check | Pass condition |
|---|---|
| Nodes with non-empty `source_url` | 100% |
| Edges with non-empty `source_url` | 100% |
| Nodes with at least 1 xref | >= 80% (xrefs are nice-to-have, not required) |

### Gate 4: Deduplication

```python
def assert_unique_node_ids(nodes_df):
    dupes = nodes_df[nodes_df["id"].duplicated()]
    assert dupes.empty, f"{len(dupes)} duplicate node ids"

def assert_unique_edges(edges_df):
    key = ["subject", "predicate", "object"]
    dupes = edges_df[edges_df.duplicated(subset=key)]
    assert dupes.empty, f"{len(dupes)} duplicate (subject, predicate, object) triples"
```

### Gate 5: KGX shape

| Check | Pass condition |
|---|---|
| `nodes.tsv` has required columns | `id, category, name, source, source_url, xrefs` |
| `edges.tsv` has required columns | `subject, predicate, object, source, source_url` |
| TSV is valid (no embedded tabs/newlines in fields) | 100% rows parse |
| Files load via the kgx library | `kgx.transform` succeeds |

## Quality gates (System 2: graph load)

### Gate 6: Round-trip parity

After loading KGX into AGE, query it back and confirm counts match:

```python
def assert_load_parity(kgx_dir: Path, conn):
    expected_nodes = sum(1 for _ in open(kgx_dir / "nodes.tsv")) - 1  # minus header
    expected_edges = sum(1 for _ in open(kgx_dir / "edges.tsv")) - 1
    cur = conn.cursor()
    cur.execute("SELECT * FROM ag_catalog.cypher('ncbi_kg', $$ MATCH (n) RETURN count(n) $$) AS (c agtype);")
    actual_nodes = int(str(cur.fetchone()[0]))
    cur.execute("SELECT * FROM ag_catalog.cypher('ncbi_kg', $$ MATCH ()-[r]->() RETURN count(r) $$) AS (c agtype);")
    actual_edges = int(str(cur.fetchone()[0]))
    assert actual_nodes == expected_nodes
    assert actual_edges == expected_edges
```

### Gate 7: Sanity queries (smoke test)

After load, run 3 canonical queries. All must return non-empty:

1. `MATCH (g:Gene {name: 'BRCA1'}) RETURN g`
2. `MATCH (g:Gene)-[:gene_associated_with_condition]->(d:Disease) WHERE d.name CONTAINS 'cancer' RETURN g.name LIMIT 5`
3. `MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {name: 'BRCA1'}) RETURN v LIMIT 5`

## How to run

```bash
# 1. Run pipeline
python -m data_pipelines.gene.run

# 2. Run gates
pytest tests/eval/test_gates.py -v

# 3. Print summary
python scripts/eval_summary.py data/kgx/gene/
```

The summary script prints:

```
=== Pipeline eval: gene ===
Nodes:        12,453
Edges:        37,891
BioLink validation:    PASS (0 errors)
Dangling edges:        PASS (0)
Provenance coverage:   PASS (100% nodes, 100% edges)
Deduplication:         PASS (0 duplicates)
KGX shape:             PASS
=== READY FOR LOAD ===
```

## Track over time

Append every run's gate results to `data/eval/gate_history.jsonl`. One JSON line per run with timestamp, pipeline name, gate results, counts. This is how you catch regressions.

## Anti-patterns

- "It works on my data" — gates must run on the actual run output, not a sample
- Gates that warn instead of failing — gates either pass or block
- Skipping gate 6 — load parity catches loader bugs that nothing else does
- Hand-checking sample queries instead of automating them
