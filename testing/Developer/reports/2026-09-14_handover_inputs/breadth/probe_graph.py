"""Read-only Layer 1 probes for the breadth audit, 2026-09-14.

Every query goes through the repository's own `graph_connection.execute_cypher`
over GRAPH_QUERY_URL with bound parameters, a 30 second timeout and a LIMIT.
Nothing is written to the repository: the audit log is redirected into this
folder. Output: `graph_probe.jsonl`, one line per sample.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path("/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui")
sys.path.insert(0, str(REPO / "src"))

for line in (REPO / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

# Keep every side effect out of the repository.
os.environ["TOOL_AUDIT_LOG_PATH"] = str(HERE / "tool_audit_probe.jsonl")
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from system_03_search_agent.tools.graph_connection import execute_cypher

OUT = HERE / "graph_probe.jsonl"
GENES = {"BRCA1": "NCBIGene:672", "GCK": "NCBIGene:2645"}
SAMPLES = 3


def _as_clause(cypher: str) -> str:
    tail = cypher.rsplit("RETURN", 1)[1]
    tail = re.split(r"\bORDER\s+BY\b", tail)[0]
    n = tail.count(",") + 1
    return "(" + ", ".join(f"c{i} agtype" for i in range(n)) + ")"


def _entities(row: dict) -> list[dict]:
    """Decode every agtype vertex in a raw row (a `::vertex` string, or a list of them)."""
    found: list[dict] = []
    for value in row.values():
        text = value if isinstance(value, str) else json.dumps(value, default=str)
        for m in re.finditer(r'\{"id": \d+, "label": "[^"]+", "properties": \{.*?\}\}(?=::vertex)', text):
            try:
                found.append(json.loads(m.group(0)))
            except json.JSONDecodeError:
                continue
    return found


def _summarise_rows(rows: list[dict]) -> dict:
    """What a citation needs: how many entities carry a real name and a source_url."""
    named = 0
    urls = 0
    total = 0
    hosts: set[str] = set()
    labels: dict[str, int] = {}
    sample_names: list[str] = []
    vocab_artifacts = 0
    for row in rows:
        for ent in _entities(row):
            total += 1
            props = ent.get("properties", {})
            labels[ent.get("label", "?")] = labels.get(ent.get("label", "?"), 0) + 1
            url = props.get("source_url") or ""
            if url:
                urls += 1
                hosts.add(url.split("/")[2])
            name = props.get("name") or ""
            if name in ("MeSH", "OMIM", "MedGen", "OMIM included", "SNOMED CT", ""):
                vocab_artifacts += 1
            else:
                named += 1
                if len(sample_names) < 3:
                    sample_names.append(name[:80])
    return {"entities": total, "labels": labels, "entities_with_source_url": urls,
            "entities_with_real_name": named, "vocabulary_artifact_names": vocab_artifacts,
            "hosts": sorted(hosts), "sample_names": sample_names}


def probe(name: str, cypher: str, params: dict, row_limit: int) -> None:
    elapsed: list[float] = []
    record: dict = {"probe": name, "cypher": cypher, "params": params, "row_limit": row_limit}
    for i in range(SAMPLES):
        started = time.monotonic()
        try:
            rows, total = execute_cypher(cypher, params, row_limit=row_limit, timeout_s=30.0,
                                         as_clause=_as_clause(cypher))
            elapsed.append(round(time.monotonic() - started, 3))
            if i == 0:
                record.update({"rows": len(rows), "total_available": total})
                record.update(_summarise_rows(rows))
                record["first_row"] = json.loads(json.dumps(rows[0], default=str))[:1] if isinstance(rows[0], list) else json.loads(json.dumps(rows[0], default=str)) if rows else None
        except Exception as exc:  # noqa: BLE001
            elapsed.append(round(time.monotonic() - started, 3))
            record["error"] = f"{type(exc).__name__}: {exc}"[:300]
            break
    record["elapsed_s"] = elapsed
    record["median_s"] = round(statistics.median(elapsed), 3) if elapsed else None
    with OUT.open("a") as fh:
        fh.write(json.dumps(record) + "\n")
    short = {k: v for k, v in record.items() if k not in ("cypher", "params", "first_row")}
    print(json.dumps(short))


SHAPES = {
    "diseases (gene_associated_with_condition)":
        ("MATCH (a:Gene {id: $e})-[:gene_associated_with_condition]->(x:Disease) RETURN x ORDER BY x.id", 100),
    "variants (is_sequence_variant_of)":
        ("MATCH (x:SequenceVariant)-[:is_sequence_variant_of]->(a:Gene {id: $e}) RETURN x ORDER BY x.id", 100),
    "variant diseases fold (T1)":
        (("MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(a:Gene {id: $e}) "
         "MATCH (v)-[:has_phenotype]->(x:Disease) WITH v, collect(DISTINCT x) AS xs RETURN v, xs ORDER BY v.id"), 100),
    "processes (participates_in)":
        ("MATCH (a:Gene {id: $e})-[:participates_in]->(x:BiologicalProcess) RETURN x ORDER BY x.id", 100),
    "activities (actively_involved_in)":
        ("MATCH (a:Gene {id: $e})-[:actively_involved_in]->(x:MolecularActivity) RETURN x ORDER BY x.id", 100),
    "components (located_in)":
        ("MATCH (a:Gene {id: $e})-[:located_in]->(x:CellularComponent) RETURN x ORDER BY x.id", 100),
    "orthologs (orthologous_to)":
        ("MATCH (a:Gene {id: $e})-[:orthologous_to]->(x:Gene) RETURN x ORDER BY x.id", 100),
    "taxon (in_taxon)":
        ("MATCH (a:Gene {id: $e})-[:in_taxon]->(x:OrganismTaxon) RETURN x ORDER BY x.id", 10),
    "articles (mentioned_in), bounded 20":
        ("MATCH (a:Gene {id: $e})-[:mentioned_in]->(x:Article) RETURN x ORDER BY x.id", 20),
    "articles count":
        ("MATCH (a:Gene {id: $e})-[:mentioned_in]->(x:Article) RETURN count(DISTINCT x) AS articles_count", 1),
    "article mesh, 2 hops bounded 20":
        (("MATCH (a:Gene {id: $e})-[:mentioned_in]->(x:Article) WITH x ORDER BY x.id LIMIT 5 "
         "MATCH (x)-[:has_mesh_annotation]->(m:OntologyClass) RETURN x, m ORDER BY x.id, m.id"), 20),
    "gene record":
        ("MATCH (a:Gene {id: $e}) RETURN a", 1),
}


if __name__ == "__main__":
    OUT.unlink(missing_ok=True)
    for symbol, curie in GENES.items():
        for shape, (cypher, limit) in SHAPES.items():
            probe(f"{symbol} {shape}", cypher, {"e": curie}, limit)
    # Pathways: probed once in the first run. `MATCH (x:Pathway)` is rejected
    # by the service's validator (422, "not one of the graph's known vertex
    # labels"), and an unanchored id-prefix scan for REACT timed out at 30 s,
    # which is the expected cost of a full scan. Not repeated.
