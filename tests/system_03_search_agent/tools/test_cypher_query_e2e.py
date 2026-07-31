"""T-2.1-09: end-to-end verification of cypher_query against the live AGE graph.

This is the phase's verify surface. Every other test in phase 2.1 mocks
`execute_cypher`, so none of them crosses the seam between the modules that
generate a query and the modules that interpret what the graph sends back.
That seam is where the phase failed review: six modules each passed their own
tests while the assembled tool returned empty, uncited rows and called it
`status="ok"`.

The rule this file follows: mock the model call and nothing else. The graph
connection, the agtype interpretation, the provenance mapping, and the output
schema are all exercised for real. A test here that needs a new mock to pass
is a test that has stopped doing its job.

Skips cleanly, with a stated reason, when no tunnel to the graph is open.
Reachability is checked fresh before every single test, not once at import
(finding F-2.1-B12): the tunnel is a manual, long-lived SSH process that can
drop mid-session, and a guard evaluated once at import cannot notice that.

Depends on:
    - system_03_search_agent.tools.cypher_query (the assembled pipeline)
    - system_03_search_agent.tools.cypher_schemas (CypherQueryInput)
    - A live SSH local port-forward to the Hetzner AGE graph

Reads:
    - .env, loaded explicitly rather than inherited from litellm's import-time
      load_dotenv() side effect (finding F-2.1-04)

Writes:
    - Nothing. Layer 1 access is read-only by credential.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Finding F-2.1-B12: the exact command to reopen the tunnel, named directly in
# the skip and failure text so diagnosis is one line, not an investigation.
_REOPEN_TUNNEL_CMD = (
    "ssh -o BatchMode=yes -f -N -L 15432:127.0.0.1:5432 root@46.225.128.133"
)

# The env var holding the graph credential. Named once here so the health
# probe below reads it by name and the value never appears in this file.
_GRAPH_PASSWORD_VAR = "GRAPH_PG_PASSWORD"


def _load_env_explicitly() -> None:
    """Populate the graph variables from .env without relying on litellm.

    Finding F-2.1-04: nothing in this repo calls load_dotenv(). The variables
    reach os.environ only because importing litellm does it as a side effect,
    which makes whether this test runs depend on unrelated import order. Load
    it here so this file's behavior is its own.
    """
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def _graph_reachable() -> tuple[bool, str]:
    _load_env_explicitly()
    host = os.environ.get("GRAPH_PG_HOST")
    port_raw = os.environ.get("GRAPH_PG_PORT", "")
    if not host or not port_raw:
        return False, "GRAPH_PG_HOST or GRAPH_PG_PORT is unset"
    sock = socket.socket()
    sock.settimeout(2.0)
    try:
        sock.connect((host, int(port_raw)))
    except OSError as exc:
        return False, (
            f"{host}:{port_raw} not reachable ({type(exc).__name__}); no SSH tunnel open. "
            f"Reopen it with: {_REOPEN_TUNNEL_CMD}"
        )
    finally:
        sock.close()

    # F-2.1-C16: an open port is not a live database. An SSH local forward
    # binds the local port the moment the tunnel process starts, and keeps it
    # bound whether or not anything is alive at the far end. When the graph
    # host's postgres was OOM-killed mid-session, this guard still reported
    # "reachable" and 21 tests came back as FAILURES rather than skips, which
    # reads exactly like a code regression in whatever change is under
    # review. That false signal is expensive: it cost real time proving the
    # failures were not caused by the change being tested.
    #
    # So ask the database, not the socket. One cheap round trip, and any
    # connection-level failure is a skip rather than a failure, because a
    # dead dependency is not a defect in the code under test.
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=host,
            port=int(port_raw),
            dbname=os.environ.get("GRAPH_PG_DBNAME", ""),
            user=os.environ.get("GRAPH_PG_USER", ""),
            password=os.environ.get(_GRAPH_PASSWORD_VAR, ""),
            connect_timeout=5,
        )
    except Exception as exc:  # noqa: BLE001 - any connect failure is a skip
        return False, (
            f"{host}:{port_raw} accepts connections but the graph database did "
            f"not answer ({type(exc).__name__}). An open port only means the SSH "
            "forward is bound, not that postgres is running. Check the graph "
            f"host, then reopen the tunnel with: {_REOPEN_TUNNEL_CMD}"
        )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception as exc:  # noqa: BLE001 - any query failure is a skip
        return False, (
            "the graph database accepted a connection but failed a trivial "
            f"query ({type(exc).__name__}); it is not healthy"
        )
    finally:
        conn.close()
    return True, ""


pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True)
def _skip_if_graph_unreachable() -> None:
    """Check reachability fresh before every test, not once at import.

    Finding F-2.1-B12: a module-level `_REACHABLE` computed at import time
    freezes the answer for the whole run. The SSH tunnel is a manual,
    long-lived process that drops mid-session, so a run that started reachable
    can go unreachable partway through, and every test after that point fails
    with an opaque connection error instead of skipping with a stated reason.
    An autouse, function-scoped fixture re-evaluates reachability immediately
    before each test body runs, so a mid-run drop is caught as a skip, not
    misread as a regression.
    """
    reachable, reason = _graph_reachable()
    if not reachable:
        pytest.skip("live graph unavailable: " + reason)

# Ground truth, established during phase open and re-verified after the
# write-refusal probes. These are facts about the live graph, not fixtures.
BRCA1_CURIE = "NCBIGene:672"
BRCA1_NAME = "BRCA1 DNA repair associated"
BRCA1_VARIANT_EDGE_COUNT = 15310
KNOWN_VARIANT_CURIE = "ClinVar:17660"


def _mock_generation(monkeypatch: pytest.MonkeyPatch, cypher: str) -> AsyncMock:
    """Force the generation step to return one exact Cypher string.

    Only the model call is mocked. Everything downstream of it runs for real
    against the graph.
    """
    import litellm

    response = type(
        "Response",
        (),
        {
            "choices": [
                type(
                    "Choice",
                    (),
                    {"message": type("Msg", (), {"content": cypher, "role": "assistant"})()},
                )()
            ],
            "usage": type(
                "Usage", (), {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
            )(),
            "model": "mock-plan-tier",
        },
    )()
    mock = AsyncMock(return_value=response)
    monkeypatch.setattr(litellm, "acompletion", mock)

    # The harness prices every call from the OpenRouter map, and the tier
    # defaults resolve to a model litellm does not yet price. That is a real
    # guard and it should stay, so rather than bypass the cost path this
    # supplies a nominal price for whatever model the tiers resolve to. The
    # cost accounting itself still runs for real.
    from system_03_search_agent.harness import harness as harness_module
    from system_03_search_agent.harness import tiers as tiers_module

    priced = dict(harness_module._FALLBACK_PRICES_USD_PER_TOKEN)
    for tier in ("guard", "plan", "synth"):
        try:
            priced[tiers_module.resolve_model(tier)] = (1e-7, 1e-7)
        except Exception:  # noqa: BLE001 - a tier that will not resolve fails later, visibly
            continue
    priced["mock-plan-tier"] = (1e-7, 1e-7)
    monkeypatch.setattr(harness_module, "_FALLBACK_PRICES_USD_PER_TOKEN", priced)

    return mock


def _harness(trace_id: str = "e2e-live") -> Any:
    from system_03_search_agent.harness.harness import Harness

    return Harness(trace_id=trace_id)


def _query(text: str, trace_id: str) -> Any:
    from system_03_search_agent.contracts.query import Query

    return Query(
        text=text,
        trace_id=trace_id,
        session_id="e2e-live-session",
        user_id="00000000-0000-0000-0000-000000000001",
    )


def _context() -> Any:
    from system_03_search_agent.contracts.query import RequestContext

    # `surface` is required and RequestContext forbids extras. `user_id`
    # lives on Query, not here.
    return RequestContext(surface="rest_sse")


async def _run(monkeypatch: pytest.MonkeyPatch, cypher: str, **input_kwargs: Any) -> Any:
    from system_03_search_agent.tools.cypher_query import cypher_query
    from system_03_search_agent.tools.cypher_schemas import CypherQueryInput

    _mock_generation(monkeypatch, cypher)
    tool_input = CypherQueryInput(**input_kwargs)
    return await cypher_query(_harness(), tool_input)


# ---------------------------------------------------------------------------
# F-2.1-B01: the parameter naming contract
#
# These exist because updating the other tests in this file to use the new
# parameter names would, on its own, prove nothing. Renaming a fixture to
# match the implementation is exactly the shape of change that hides a
# defect rather than fixing one. These two assert the properties the
# contract has to deliver, against the adversary's own reproduction.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_entities_binds_the_one_the_query_asks_about_not_the_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adversary's reproduction, F-2.1-B01, as a regression test.

    "Compare NCBIGene:7157 and BRCA1: which diseases is BRCA1 linked to?"
    extracts TP53 first, because it appears first in the text. Binding used
    to be a positional zip, so the query about BRCA1 ran against TP53 and
    returned 12 real TP53 disease rows, correctly cited, with status ok and
    trust_outcome answer. A fully cited, confident answer about the wrong
    gene, every gate green.

    The model here asks for BRCA1 by its bound name while TP53 sits first
    in the entity list, which is precisely the case position gets wrong.
    """
    from system_03_search_agent.tools.cypher_query import entity_param_bindings

    tp53 = "NCBIGene:7157"
    entities = [tp53, BRCA1_CURIE]
    bindings = entity_param_bindings(entities)
    brca1_param = next(name for name, value in bindings.items() if value == BRCA1_CURIE)

    result = await _run(
        monkeypatch,
        "MATCH (g:Gene {id: $" + brca1_param + "}) RETURN g",
        query_intent="Compare TP53 and BRCA1: what is BRCA1?",
        query_class="lookup",
        target_entities=entities,
        row_limit=1,
    )

    assert result.status == "ok", f"expected ok, got {result.status}: {result.error}"
    assert result.row_count == 1
    row = result.rows[0]
    assert row.curie == BRCA1_CURIE, (
        f"bound {row.curie!r}, but the query asked about {BRCA1_CURIE!r}. "
        "Positional binding is back."
    )
    assert row.fields.get("name") == BRCA1_NAME


@pytest.mark.asyncio
async def test_a_parameter_the_model_invented_is_rejected_not_silently_unbound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A name outside the contract must fail loudly, before execution.

    Previously an unbound parameter reached AGE and failed there as an
    opaque `UndefinedParameter`, which the tool surfaced as a graph error,
    reading as though the graph were at fault. The repair retry had nothing
    actionable to work from.

    The mocked model ignores its instructions on both attempts, so this also
    proves the retry does not rescue a query that never becomes valid.
    """
    result = await _run(
        monkeypatch,
        "MATCH (g:Gene {id: $totally_made_up_name}) RETURN g",
        query_intent="Look up the gene BRCA1",
        query_class="lookup",
        target_entities=[BRCA1_CURIE],
        row_limit=1,
    )

    assert result.status == "error", f"expected error, got {result.status}"
    assert result.rows == []
    assert result.error is not None
    assert "totally_made_up_name" in result.error, (
        "the error must name the invented parameter, so the repair retry is "
        f"informed rather than blind. Got: {result.error!r}"
    )


# ---------------------------------------------------------------------------
# The premise: a real query returns cited rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_hop_lookup_returns_a_populated_cited_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The phase premise, reduced to one assertion set.

    A lookup for BRCA1 must come back with the gene's real name, its real
    CURIE, and a resolvable NCBI citation. An empty row reported as
    status="ok" is the exact failure this test exists to catch.
    """
    result = await _run(
        monkeypatch,
        "MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g",
        query_intent="Look up the gene BRCA1",
        query_class="lookup",
        target_entities=[BRCA1_CURIE],
        row_limit=1,
    )

    assert result.status == "ok", f"expected ok, got {result.status}: {result.error}"
    assert result.row_count == 1
    row = result.rows[0]

    assert row.curie == BRCA1_CURIE, f"curie was {row.curie!r}, the row did not carry its identity"
    assert row.node_or_edge_type == "Gene"
    assert row.fields, "fields was empty, the graph payload was not interpreted"
    assert row.fields.get("name") == BRCA1_NAME
    assert row.source_url == "https://www.ncbi.nlm.nih.gov/gene/672"


@pytest.mark.asyncio
async def test_multi_hop_traversal_returns_real_variant_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A labelled-edge traversal, the query class this phase exists to serve."""
    result = await _run(
        monkeypatch,
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $e_NCBIGene_672}) RETURN v",
        query_intent="What sequence variants are known in BRCA1",
        query_class="multi_hop",
        target_entities=[BRCA1_CURIE],
        row_limit=5,
    )

    assert result.status == "ok", f"expected ok, got {result.status}: {result.error}"
    assert result.row_count == 5
    for row in result.rows:
        assert row.curie.startswith("ClinVar:"), f"unexpected curie {row.curie!r}"
        assert row.node_or_edge_type == "SequenceVariant"
        assert row.fields.get("name"), "variant row carried no name"
        assert row.source_url is not None
        assert row.source_url.startswith("https://www.ncbi.nlm.nih.gov/clinvar/variation/")


@pytest.mark.asyncio
async def test_multi_column_return_is_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Finding F-01: a multi-column RETURN died with DatatypeMismatch.

    The as_clause was hardcoded to a single column while nothing constrained
    the generator to a single-column RETURN. Multi-hop queries naturally bind
    several variables, so this killed the phase's main query class.
    """
    result = await _run(
        monkeypatch,
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $e_NCBIGene_672}) "
        "RETURN v, g",
        query_intent="Variants and their gene",
        query_class="multi_hop",
        target_entities=[BRCA1_CURIE],
        row_limit=3,
    )

    assert result.status == "ok", f"multi-column RETURN failed: {result.error}"
    assert result.row_count > 0


# ---------------------------------------------------------------------------
# Counting and truncation honesty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_truncated_result_reports_the_true_total_not_the_row_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Finding A2: total_available was computed after LIMIT injection.

    BRCA1 genuinely has 15,310 variant edges. Reporting 10 with
    truncated=False is a confident wrong answer to "how many", which is worse
    than an error.
    """
    result = await _run(
        monkeypatch,
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $e_NCBIGene_672}) RETURN v",
        query_intent="How many sequence variants does BRCA1 have",
        query_class="aggregate",
        target_entities=[BRCA1_CURIE],
        row_limit=10,
    )

    assert result.status == "ok"
    assert result.row_count == 10
    assert result.truncated is True, "a capped result must declare itself truncated"
    assert result.total_available == BRCA1_VARIANT_EDGE_COUNT, (
        f"total_available was {result.total_available}, expected the true count "
        f"{BRCA1_VARIANT_EDGE_COUNT}; reporting the row limit as the total is a wrong answer"
    )


# ---------------------------------------------------------------------------
# The refusal path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_absent_entity_returns_empty_never_a_fabricated_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fabricated gene must produce status="empty", the cite-or-refuse trigger."""
    result = await _run(
        monkeypatch,
        "MATCH (g:Gene {id: $e_NCBIGene_99999999}) RETURN g",
        query_intent="Look up the gene ZZZFAKE9",
        query_class="lookup",
        target_entities=["NCBIGene:99999999"],
        row_limit=5,
    )

    assert result.status == "empty", f"expected empty, got {result.status}"
    assert result.row_count == 0
    assert result.rows == []


@pytest.mark.asyncio
async def test_every_returned_row_carries_a_host_pinned_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No row reaches a caller without a resolvable NCBI citation.

    CLAUDE.md: every fact in a response must link back to its source. A row
    with no source_url cannot be cited, so it must not be emitted as content.
    """
    result = await _run(
        monkeypatch,
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $e_NCBIGene_672}) RETURN v",
        query_intent="BRCA1 variants",
        query_class="multi_hop",
        target_entities=[BRCA1_CURIE],
        row_limit=5,
    )

    assert result.status == "ok"
    uncited = [r for r in result.rows if not r.source_url]
    assert not uncited, f"{len(uncited)} of {result.row_count} rows carried no citation"


# ---------------------------------------------------------------------------
# The full agent loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_loop_reaches_the_graph_and_returns_a_cited_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Findings A3 and F-02: the wired loop must actually reach the graph.

    plan_node hardcoded target_entities=[], so every parameterized query
    dead-ended on UndefinedParameter while every literal was rejected by the
    validator. Both branches ended in status="error", and the loop still
    emitted trust_outcome="answer".
    """
    from system_03_search_agent.core.run import run

    # The parameter name is the one the caller binds for BRCA1, per the
    # F-2.1-B01 naming contract: `entity_param_bindings` derives it from the
    # CURIE, so a mocked model that used any other name would be rejected
    # exactly as a real one would.
    _mock_generation(monkeypatch, "MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g")

    events = [
        event
        async for event in run(_query("What is the gene BRCA1?", "e2e-live-1"), _context())
    ]

    done = [e for e in events if e.type == "done"]
    assert done, "the loop produced no done event"
    errors = [e for e in events if e.type == "error"]
    assert not errors, f"the loop errored: {[e.payload for e in errors]}"

    citations = [e for e in events if e.type == "citation"]
    assert citations, "the loop reached done with no citation event"


@pytest.mark.asyncio
async def test_full_loop_works_for_a_gene_outside_the_symbol_seed_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The loop must not depend on a hardcoded symbol lookup.

    `core/graph.py._extract_target_entities` has two sources: a verbatim
    CURIE in the query text, which is general, and a gene-symbol seed
    table, which currently holds exactly one entry (BRCA1, the gene the
    other tests here query). Without this test the gate could pass on the
    seed table alone and nobody would notice that symbol resolution does
    not generalize.

    This names TP53 by CURIE, which is absent from that table, so only the
    general path can satisfy it. TP53 is NCBIGene:7157 in the live graph,
    verified 2026-07-29.
    """
    from system_03_search_agent.core.run import run

    _mock_generation(monkeypatch, "MATCH (g:Gene {id: $e_NCBIGene_7157}) RETURN g")

    events = [
        event
        async for event in run(
            _query("What is NCBIGene:7157?", "e2e-live-3"), _context()
        )
    ]

    errors = [e for e in events if e.type == "error"]
    assert not errors, f"the loop errored: {[e.payload for e in errors]}"

    done = [e for e in events if e.type == "done"]
    assert done, "the loop produced no done event"
    outcome = done[0].payload.get("trust_outcome")
    assert outcome == "answer", (
        f"trust_outcome was {outcome!r} for a gene that exists in the graph; "
        "entity extraction did not generalize beyond the symbol seed table"
    )

    citations = [e for e in events if e.type == "citation"]
    assert citations, "a real gene resolved by CURIE produced no citation"


@pytest.mark.asyncio
async def test_full_loop_refuses_when_the_graph_returns_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Findings A5, F-02, and F-2.1-08: zero rows must not terminate as an answer.

    trust_outcome="answer" on a query that found nothing is the fluent wrong
    answer this system's whole trust story exists to prevent. status="empty"
    being merely represented, with nothing downstream reading it, is not
    enforcement.

    F-2.1-08: the original version of this test named "ZZZFAKE9", a token
    that is neither a verbatim CURIE nor a seed-table entry. Entity
    extraction found nothing, so `target_entities` came back empty and
    `cypher_query` refused before ever generating or running a query,
    reaching status="error", never status="empty". The loop still reached
    trust_outcome="refuse" through that error branch, so the assertion on
    `trust_outcome` alone passed without ever exercising the empty-graph
    path it claimed to prove.

    This version names `NCBIGene:99999999` verbatim: a real-shaped CURIE
    that the general (non-seed-table) extraction path resolves, so the tool
    proceeds to generate and execute a real query against the live graph.
    The CURIE is confirmed absent from the graph, so the query genuinely
    returns zero rows and reaches the refusal through status="empty". The
    Cypher below binds the parameter name `entity_param_bindings` derives
    for that CURIE, the same naming contract F-2.1-B01 established, rather
    than a hardcoded guess.

    Evidence, not assertion, that this is the empty branch and not the
    unresolved-entity branch: `run()` does not yet emit a `tool_result`
    event carrying `cypher_query`'s own status (that instrumentation is not
    built in this phase; `write_node` folds it into `trust_outcome` without
    surfacing it), so the loop's event stream alone cannot distinguish the
    two branches by itself, which is the same gap that let the original,
    broken version of this test pass unnoticed. Proving the right branch
    therefore takes two direct checks against the actual components
    `plan_node`/`act_node` call, using this test's exact query text and
    exact CURIE, before the full-loop assertions:

    1. `_extract_target_entities` (the deterministic function `plan_node`
       calls to build `target_entities`) must resolve this query text to
       exactly `[absent_curie]`, not `[]`. An empty result is precisely
       what sent the original test down the unresolved-entity, status=
       "error" branch.
    2. `cypher_query` itself, called with that resolved entity and the same
       mocked Cypher the full loop below will use, must return
       `status="empty"` against the live graph, the exact call `act_node`
       makes internally.

    Only once both are confirmed does the full-loop run below exercise the
    same path end to end and check its externally observable outcome.
    """
    from system_03_search_agent.core.graph import _extract_target_entities
    from system_03_search_agent.core.run import run
    from system_03_search_agent.tools.cypher_query import cypher_query, entity_param_bindings
    from system_03_search_agent.tools.cypher_schemas import CypherQueryInput

    absent_curie = "NCBIGene:99999999"
    query_text = f"What is known about the gene {absent_curie}?"
    param_name = next(iter(entity_param_bindings([absent_curie])))
    generated_cypher = f"MATCH (g:Gene {{id: ${param_name}}}) RETURN g"

    # Check 1: the extraction step the loop actually calls resolves this
    # query text to the CURIE, not to nothing.
    extracted = _extract_target_entities(query_text)
    assert extracted == [absent_curie], (
        f"_extract_target_entities returned {extracted!r} for {query_text!r}, "
        f"expected [{absent_curie!r}]. An empty result here reproduces "
        "F-2.1-08: cypher_query would refuse before generating anything, "
        "reaching status='error', never status='empty'."
    )

    # Check 2: cypher_query itself, called the same way act_node calls it,
    # genuinely reaches status="empty" for this entity and this Cypher.
    _mock_generation(monkeypatch, generated_cypher)
    direct_result = await cypher_query(
        _harness(trace_id="e2e-live-2-direct"),
        CypherQueryInput(
            query_intent=query_text,
            query_class="lookup",
            target_entities=extracted,
            row_limit=5,
        ),
    )
    assert direct_result.status == "empty", (
        f"expected status='empty' from a real query against the live graph, "
        f"got {direct_result.status!r}: {direct_result.error}"
    )
    assert direct_result.rows == []

    # Now the full loop, exercising the same path end to end.
    _mock_generation(monkeypatch, generated_cypher)

    events = [
        event
        async for event in run(_query(query_text, "e2e-live-2"), _context())
    ]

    errors = [e for e in events if e.type == "error"]
    assert not errors, f"the loop errored: {[e.payload for e in errors]}"

    citations = [e for e in events if e.type == "citation"]
    assert not citations, (
        f"a zero-row result produced {len(citations)} citation(s); "
        "an empty graph result must never be cited as though it were found"
    )

    done = [e for e in events if e.type == "done"]
    assert done, "the loop produced no done event"
    outcome = done[0].payload.get("trust_outcome")
    assert outcome == "refuse", (
        f"trust_outcome was {outcome!r} for a query that found nothing; "
        "a zero-row result must refuse, not answer"
    )


# ---------------------------------------------------------------------------
# Third-judge findings J-01 through J-04
#
# J-01 is the one that matters most: the fix for F-2.1-B05 re-created
# F-2.1-B01 on the derived path. Binding was corrected to go by name, but
# the derived value's citation was still attributed by taking the first of
# the *candidate* entities rather than the one actually bound, so an
# aggregate over BRCA1 came back cited to TP53. Same class of defect as
# B01, in a code path B01's regression test does not reach, which is
# exactly why these run live rather than against a mock.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregate_over_two_entities_cites_the_one_it_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """J-01: a derived value is cited to the entity it was computed from.

    Two entities in the query text, TP53 first. The Cypher counts BRCA1's
    variants. Before the fix the count, BRCA1's real 15310, was emitted
    with `curie="NCBIGene:7157"` and a citation to TP53's gene page: a
    true number attached to the wrong record, status ok, gate green.

    The assertion is on the citation, not the number. A wrong number is
    visible; a right number under a wrong citation is the failure that
    survives review.
    """
    from system_03_search_agent.tools.cypher_query import entity_param_bindings

    tp53 = "NCBIGene:7157"
    entities = [tp53, BRCA1_CURIE]
    bindings = entity_param_bindings(entities)
    brca1_param = next(name for name, value in bindings.items() if value == BRCA1_CURIE)

    result = await _run(
        monkeypatch,
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->"
        "(g:Gene {id: $" + brca1_param + "}) RETURN count(v)",
        query_intent=f"Compare {tp53} and BRCA1: how many variants does BRCA1 have?",
        query_class="aggregate",
        target_entities=entities,
        row_limit=10,
    )

    assert result.status == "ok", f"expected ok, got {result.status}: {result.error}"
    assert result.rows, "an aggregate over a real gene returned no row"

    derived = [row for row in result.rows if row.node_or_edge_type == "derived"]
    assert derived, f"no derived row; got types {[r.node_or_edge_type for r in result.rows]}"

    for row in derived:
        assert row.curie != tp53, (
            f"the count was computed from BRCA1 but cited to {row.curie!r}, "
            "which is TP53. B01 is back on the derived path."
        )
        if row.source_url is not None:
            assert "/7157" not in row.source_url, (
                f"citation {row.source_url!r} points at TP53's record for a "
                "value computed from BRCA1"
            )


@pytest.mark.asyncio
async def test_derived_value_survives_an_entity_in_the_same_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """J-03: `RETURN g, count(v)` must not discard the count.

    The emit was guarded on `not shaped_rows`, so a row carrying both a
    vertex and a scalar emitted the vertex and dropped the scalar. The tool
    then reported `status="ok"` with a valid BRCA1 citation and the number
    the user asked for silently removed, which is worse than B05's original
    symptom: B05 refused, this answered with the answer taken out.
    """
    from system_03_search_agent.tools.cypher_query import entity_param_bindings

    bindings = entity_param_bindings([BRCA1_CURIE])
    brca1_param = next(iter(bindings))

    result = await _run(
        monkeypatch,
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->"
        "(g:Gene {id: $" + brca1_param + "}) RETURN g, count(v)",
        query_intent="What is BRCA1 and how many variants does it have?",
        query_class="aggregate",
        target_entities=[BRCA1_CURIE],
        row_limit=10,
    )

    assert result.status == "ok", f"expected ok, got {result.status}: {result.error}"

    kinds = [row.node_or_edge_type for row in result.rows]
    assert "derived" in kinds, (
        f"the count was dropped because a vertex shared its row; got {kinds}. "
        "An answer that returns everything except the number asked for is "
        "not an answer."
    )

    counts = [
        value
        for row in result.rows
        if row.node_or_edge_type == "derived"
        for value in row.fields.values()
        if isinstance(value, int)
    ]
    assert BRCA1_VARIANT_EDGE_COUNT in counts, (
        f"expected the true count {BRCA1_VARIANT_EDGE_COUNT} among {counts}"
    )


def test_a_curie_followed_by_punctuation_is_extracted_whole() -> None:
    """J-04: `NCBIGene:672:` is not a CURIE, and must not replace one.

    `:` sat inside the local-id character class, so a CURIE followed by
    ordinary sentence punctuation matched greedily through it. The bad
    match did not sit beside the good one, it *was* the extraction, so a
    valid question resolved to an id that exists nowhere and returned
    empty. `source_url_for_curie` still built a host-pinned NCBI URL for
    it, so the citation gate passed a link to a dead page: host-pinning
    proves where a URL points, never that the record is real.
    """
    from system_03_search_agent.core.graph import _extract_target_entities

    entities = _extract_target_entities(
        "Compare NCBIGene:7157 and NCBIGene:672: how many variants?"
    )

    assert "NCBIGene:672" in entities, f"BRCA1 was not extracted: {entities}"
    assert not any(e.endswith(":") for e in entities), (
        f"a trailing colon survived extraction: {entities}"
    )
    # Internal punctuation is legitimate in a local id and must be kept.
    assert _extract_target_entities("see MedGen:C0031485 today") == ["MedGen:C0031485"]


@pytest.mark.asyncio
async def test_a_model_limit_above_the_row_limit_still_reports_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """J-02: the truncation check must see both directions, not one.

    F-2.1-B04a fixed the case where the model's LIMIT is *below*
    `row_limit`, and the fix was written to that example rather than to the
    property. The ordinary case runs the other way: the validator only
    lowers a LIMIT above MAX_ROW_LIMIT, never down to `row_limit`, so
    `LIMIT 500` against a `row_limit` of 20 fetched 500 rows, the tool
    truncated to 20, and `len(rows) >= 500` was False. Twenty rows of five
    hundred, reported `truncated=False`: a partial answer presented as a
    complete one, which is the failure mode a truncation flag exists to
    prevent.
    """
    from system_03_search_agent.tools.cypher_query import entity_param_bindings

    bindings = entity_param_bindings([BRCA1_CURIE])
    brca1_param = next(iter(bindings))

    result = await _run(
        monkeypatch,
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->"
        "(g:Gene {id: $" + brca1_param + "}) RETURN v LIMIT 500",
        query_intent="List the variants of BRCA1",
        query_class="multi_hop",
        target_entities=[BRCA1_CURIE],
        row_limit=20,
    )

    assert result.status == "ok", f"expected ok, got {result.status}: {result.error}"
    assert result.row_count <= 20, f"row_limit was not honored: {result.row_count}"
    assert result.truncated, (
        f"{result.row_count} rows shipped out of a 500-row fetch, reported "
        "truncated=False. A partial answer presented as complete."
    )


@pytest.mark.asyncio
async def test_a_return_alias_reaches_the_output_as_the_field_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """J-09: `count(v) AS variant_count` must not arrive as `c0`.

    AGE's as_clause forces positional column names, so an aliased value
    reached the Write step as `{"c0": 15310}`: right number, no meaning.
    With one column that is opaque. With two it is dangerous, because
    `c0` and `c1` are indistinguishable and a synthesis step reporting
    the disease count as the variant count would look entirely
    confident.
    """
    from system_03_search_agent.tools.cypher_query import entity_param_bindings

    bindings = entity_param_bindings([BRCA1_CURIE])
    brca1_param = next(iter(bindings))

    result = await _run(
        monkeypatch,
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->"
        "(g:Gene {id: $" + brca1_param + "}) RETURN count(v) AS variant_count",
        query_intent="How many variants does BRCA1 have?",
        query_class="aggregate",
        target_entities=[BRCA1_CURIE],
        row_limit=10,
    )

    assert result.status == "ok", f"expected ok, got {result.status}: {result.error}"
    keys = [key for row in result.rows for key in row.fields]
    assert "variant_count" in keys, (
        f"the alias was dropped; the field arrived as {keys}. A number whose "
        "name is 'c0' cannot be synthesized into a sentence safely."
    )
    assert result.rows[-1].fields["variant_count"] == BRCA1_VARIANT_EDGE_COUNT


def test_an_unaliased_or_malformed_column_keeps_its_positional_name() -> None:
    """J-09's other half: never paraphrase, never sanitize into a lookalike.

    A RETURN alias is model-supplied text that becomes a key in a dict
    serialized into the synthesis prompt, so it is accepted only as an
    ordinary short identifier. Anything else keeps `c0`, which is honest
    about the query not having named that column, rather than being
    cleaned up into something that resembles a name it never had.
    """
    from system_03_search_agent.tools.cypher_query import column_labels_for

    assert column_labels_for("MATCH (g) RETURN count(g) LIMIT 1") == {}
    # A duplicate alias would collapse two columns onto one key and drop a
    # value silently, so both stay positional.
    assert column_labels_for("MATCH (g) RETURN count(a) AS n, count(b) AS n LIMIT 1") == {}
    # A comma inside a function call is not an item separator.
    assert column_labels_for("MATCH (g) RETURN coalesce(a, b) AS both LIMIT 1") == {
        "c0": "both"
    }
    # An over-long alias is refused rather than truncated.
    long_alias = "x" * 65
    assert column_labels_for(f"MATCH (g) RETURN count(g) AS {long_alias} LIMIT 1") == {}


# ---------------------------------------------------------------------------
# Third adversary pass, findings C08 and C10
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("label", "cypher"),
    [
        (
            "alias concatenation",
            (
                "WITH 'NCBIGene' AS p, '7157' AS n WITH p + ':' + n AS target "
                "MATCH (g:Gene {id: target}) RETURN g"
            ),
        ),
        (
            "name literal bound to an alias",
            (
                "WITH 'BRCA1 DNA repair associated' AS t "
                "MATCH (g:Gene) WHERE g.name = t RETURN g"
            ),
        ),
    ],
)
async def test_a_query_binding_none_of_the_callers_entities_is_refused(
    monkeypatch: pytest.MonkeyPatch, label: str, cypher: str
) -> None:
    """C08: both live bypasses of the F-2.1-B01 naming contract.

    The validator rejects an entity id written as a literal by recognising
    its shape. Binding the literal to an alias first defeats that, and both
    of these ran live: the first returned TP53 for a question about BRCA1,
    the second returned 100 non-human ortholog genes with every citation
    resolving and not one of them the gene asked about.

    Both reference zero parameters, so `_build_params` returns `{}` and the
    entire naming contract never engages. The invariant asserted here does
    not depend on spelling, which is what makes it hold against the next
    variant too: the caller supplied entities, so a query consulting none
    of them is not answering the caller's question.
    """
    result = await _run(
        monkeypatch,
        cypher,
        query_intent="Which diseases are associated with BRCA1?",
        query_class="lookup",
        target_entities=[BRCA1_CURIE],
        row_limit=10,
    )

    assert result.status == "error", (
        f"{label} was accepted with status {result.status} and "
        f"{len(result.rows)} row(s); it consults no caller entity"
    )
    assert result.rows == []
    assert result.error is not None
    # The error is read by the repair retry, so it must say what to do.
    assert "literal" in result.error.lower() or "bound entity" in result.error.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("label", "curie"),
    [
        ("well-formed but absent", "NCBIGene:99999999"),
        ("user-supplied suffix", "NCBIGene:672-VALIDATED-BY-FDA"),
    ],
)
async def test_an_aggregate_over_an_absent_entity_refuses_instead_of_citing_zero(
    monkeypatch: pytest.MonkeyPatch, label: str, curie: str
) -> None:
    """C10: a cited "0" for an identifier that is not in the graph.

    `count()` over a match that found nothing returns one row holding 0,
    so the derived path turned "we found nothing about this entity" into
    "the answer is zero, here is the source", with `trust_outcome="answer"`.
    The empty-`target_entities` refusal cannot catch it, because an entity
    was extracted; it just does not exist.

    Zero is the wrong-answer shape a clinician is least equipped to catch:
    it is a plausible biomedical result and it arrives with a citation.
    "Zero associations are recorded" and "this identifier is not in the
    graph" are different answers and must not be collapsed.
    """
    from system_03_search_agent.tools.cypher_query import entity_param_bindings

    param = next(iter(entity_param_bindings([curie])))

    result = await _run(
        monkeypatch,
        "MATCH (g:Gene)-[:gene_associated_with_condition]->(d:Disease) "
        "WHERE g.id = $" + param + " RETURN count(d) AS n",
        query_intent=f"Which diseases are associated with {curie}?",
        query_class="aggregate",
        target_entities=[curie],
        row_limit=10,
    )

    assert result.status == "empty", (
        f"{label} ({curie}) returned status {result.status} with rows "
        f"{[(r.curie, dict(r.fields)) for r in result.rows]}; an absent "
        "identifier must refuse, not answer a cited zero"
    )
    assert result.rows == []


@pytest.mark.asyncio
async def test_a_true_zero_for_a_real_entity_is_still_answerable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C10's cost side: the refusal must not swallow a real answer.

    The existence probe fires only when a derived result is entirely
    empty, and it must confirm presence for a gene that is genuinely in
    the graph, so a real aggregate still answers with its citation.
    """
    from system_03_search_agent.tools.cypher_query import entity_param_bindings

    param = next(iter(entity_param_bindings([BRCA1_CURIE])))

    result = await _run(
        monkeypatch,
        "MATCH (g:Gene)-[:gene_associated_with_condition]->(d:Disease) "
        "WHERE g.id = $" + param + " RETURN count(d) AS n",
        query_intent="How many diseases are associated with BRCA1?",
        query_class="aggregate",
        target_entities=[BRCA1_CURIE],
        row_limit=10,
    )

    assert result.status == "ok", f"a real gene refused: {result.status} {result.error}"
    assert result.rows, "no row for an aggregate over a gene that exists"
