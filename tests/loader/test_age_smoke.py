"""test_age_smoke.py - Docker smoke test for the AGE loader end-to-end.

Requires Docker Desktop running with apache/age:latest pulled.
Skip entirely with: pytest -m "not docker"

Test flow:
    1. Start apache/age:latest container on port 15432.
    2. Wait for PostgreSQL to be ready (poll pg_isready, 60s timeout).
    3. Connect via psycopg2, call run_age_load with the KGX fixtures.
    4. Assert three Cypher queries return expected results:
         a. Point lookup: find BRCA1 gene by id.
         b. 1-hop: diseases associated with BRCA1 via gene_associated_with_condition.
         c. 1-hop: taxon of BRCA1 via in_taxon.
    5. Tear down: docker stop + docker rm.

Depends on:
    - system-02-knowledge-graph/loader/pipeline.py
    - tests/loader/conftest.py (kgx_dir fixture)
    - docker CLI (subprocess)
    - psycopg2
    - stdlib: subprocess, time

Reads:
    - {kgx_dir}/nodes.tsv
    - {kgx_dir}/edges.tsv

Writes:
    - AGE graph 'smoke_test' in the ephemeral container (torn down after test)
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import psycopg2
import pytest

# Make the loader package importable from test context.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "system-02-knowledge-graph"))

from loader.pipeline import run_age_load

CONTAINER_NAME = "age_smoke_test_ph3"
AGE_IMAGE = "apache/age:latest"
PG_PORT = 15432  # non-standard port avoids conflicts with local Postgres
PG_PASSWORD = "smoke_test_pw"
DSN = (
    f"host=localhost port={PG_PORT} dbname=postgres "
    f"user=postgres password={PG_PASSWORD}"
)
_STARTUP_TIMEOUT_SECS = 60


# ---------------------------------------------------------------------------
# Container lifecycle fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def age_container(kgx_dir: Path):  # type: ignore[override]
    """Start Apache AGE container, yield DSN, then stop and remove it.

    Scope is module-level so all smoke tests share one container startup.
    """
    # Start container
    subprocess.run(
        [
            "docker", "run", "-d",
            "--name", CONTAINER_NAME,
            "-e", f"POSTGRES_PASSWORD={PG_PASSWORD}",
            "-p", f"{PG_PORT}:5432",
            AGE_IMAGE,
        ],
        check=True,
        capture_output=True,
    )

    # Poll pg_isready until container is accepting connections
    deadline = time.monotonic() + _STARTUP_TIMEOUT_SECS
    ready = False
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "docker", "exec", CONTAINER_NAME,
                "pg_isready", "-U", "postgres",
            ],
            capture_output=True,
        )
        if result.returncode == 0:
            ready = True
            break
        time.sleep(1)

    if not ready:
        subprocess.run(["docker", "stop", CONTAINER_NAME], capture_output=True)
        subprocess.run(["docker", "rm", CONTAINER_NAME], capture_output=True)
        pytest.fail(
            f"Apache AGE container did not become ready within {_STARTUP_TIMEOUT_SECS}s"
        )

    # Small grace period: pg_isready returns 0 before AGE extension is available
    time.sleep(2)

    # Load the AGE extension in the postgres database
    subprocess.run(
        [
            "docker", "exec", CONTAINER_NAME,
            "psql", "-U", "postgres", "-c", "CREATE EXTENSION IF NOT EXISTS age;",
        ],
        check=True,
        capture_output=True,
    )

    yield DSN

    # Teardown
    subprocess.run(["docker", "stop", CONTAINER_NAME], capture_output=True)
    subprocess.run(["docker", "rm", CONTAINER_NAME], capture_output=True)


# ---------------------------------------------------------------------------
# Load fixture — runs run_age_load once, shared across all smoke tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def loaded_graph(age_container: str, kgx_dir: Path) -> dict:
    """Call run_age_load once and return the result dict."""
    result = run_age_load(
        kgx_dir=kgx_dir,
        graph_name="smoke_test",
        dsn=age_container,
        drop_existing=True,
    )
    return result


# ---------------------------------------------------------------------------
# Helper: run a Cypher query and return rows
# ---------------------------------------------------------------------------


def _cypher(dsn: str, graph_name: str, query: str) -> list:
    """Execute an openCypher query via AGE and return all result rows.

    Security note: AGE requires the graph name to appear as a SQL identifier
    inside the cypher() function call itself (e.g. cypher('graph_name', ...)).
    psycopg2 %s parameterization cannot be used for identifiers in DDL or in
    the AGE cypher() graph-name argument — it is reserved for value parameters.
    graph_name here is always the hardcoded constant 'smoke_test' from this
    test file, never user-supplied input, so f-string interpolation is safe.
    query strings are likewise hardcoded test literals, not user input.
    """
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("LOAD 'age';")
        cur.execute('SET search_path = ag_catalog, "$user", public;')
        # graph_name and query are hardcoded test constants — safe to interpolate.
        cypher_sql = (
            f"SELECT * FROM ag_catalog.cypher('{graph_name}', $$ {query} $$)"
            " AS (result agtype);"
        )
        cur.execute(cypher_sql)
        rows = cur.fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.docker
def test_smoke_load_counts(loaded_graph: dict) -> None:
    """run_age_load returns the expected node and edge counts."""
    assert loaded_graph["nodes"] == 5
    assert loaded_graph["edges"] == 3


@pytest.mark.docker
def test_smoke_brca1_point_lookup(age_container: str, loaded_graph: dict) -> None:
    """Point lookup: BRCA1 gene is reachable by id in the smoke_test graph."""
    rows = _cypher(
        age_container,
        "smoke_test",
        "MATCH (g {id: 'NCBIGene:672'}) RETURN g.name",
    )
    assert len(rows) == 1
    # AGE returns agtype strings; decode the JSON value
    name_raw = rows[0][0]
    name = json.loads(name_raw) if isinstance(name_raw, str) else name_raw
    assert name == "BRCA1"


@pytest.mark.docker
def test_smoke_brca1_associated_disease(age_container: str, loaded_graph: dict) -> None:
    """1-hop: BRCA1 is connected to breast cancer via gene_associated_with_condition."""
    rows = _cypher(
        age_container,
        "smoke_test",
        (
            "MATCH (g {id: 'NCBIGene:672'})"
            "-[:gene_associated_with_condition]->(d) "
            "RETURN d.id"
        ),
    )
    assert len(rows) == 1
    disease_id_raw = rows[0][0]
    disease_id = (
        json.loads(disease_id_raw)
        if isinstance(disease_id_raw, str)
        else disease_id_raw
    )
    assert disease_id == "MONDO:0007254"


@pytest.mark.docker
def test_smoke_brca1_taxon(age_container: str, loaded_graph: dict) -> None:
    """1-hop: BRCA1 is connected to Homo sapiens via in_taxon."""
    rows = _cypher(
        age_container,
        "smoke_test",
        "MATCH (g {id: 'NCBIGene:672'})-[:in_taxon]->(t) RETURN t.id",
    )
    assert len(rows) == 1
    taxon_id_raw = rows[0][0]
    taxon_id = (
        json.loads(taxon_id_raw) if isinstance(taxon_id_raw, str) else taxon_id_raw
    )
    assert taxon_id == "NCBITaxon:9606"
