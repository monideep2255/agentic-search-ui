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
        return True, ""
    except OSError as exc:
        return False, f"{host}:{port_raw} not reachable ({type(exc).__name__}); no SSH tunnel open"
    finally:
        sock.close()


_REACHABLE, _SKIP_REASON = _graph_reachable()

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _REACHABLE, reason="live graph unavailable: " + _SKIP_REASON),
]

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

    return Query(text=text, trace_id=trace_id, session_id="e2e-live-session")


def _context() -> Any:
    from system_03_search_agent.contracts.query import RequestContext

    return RequestContext(user_id="00000000-0000-0000-0000-000000000001")


async def _run(monkeypatch: pytest.MonkeyPatch, cypher: str, **input_kwargs: Any) -> Any:
    from system_03_search_agent.tools.cypher_query import cypher_query
    from system_03_search_agent.tools.cypher_schemas import CypherQueryInput

    _mock_generation(monkeypatch, cypher)
    tool_input = CypherQueryInput(**input_kwargs)
    return await cypher_query(_harness(), tool_input)


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
        "MATCH (g:Gene {id: $gene_id}) RETURN g",
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
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $gene_id}) RETURN v",
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
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $gene_id}) "
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
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $gene_id}) RETURN v",
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
        "MATCH (g:Gene {id: $gene_id}) RETURN g",
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
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $gene_id}) RETURN v",
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

    _mock_generation(monkeypatch, "MATCH (g:Gene {id: $gene_id}) RETURN g")

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
async def test_full_loop_refuses_when_the_graph_returns_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Findings A5 and F-02: zero rows must not terminate as an answer.

    trust_outcome="answer" on a query that found nothing is the fluent wrong
    answer this system's whole trust story exists to prevent. status="empty"
    being merely represented, with nothing downstream reading it, is not
    enforcement.
    """
    from system_03_search_agent.core.run import run

    _mock_generation(monkeypatch, "MATCH (g:Gene {id: $gene_id}) RETURN g")

    events = [
        event
        async for event in run(
            _query("What is known about the gene ZZZFAKE9?", "e2e-live-2"), _context()
        )
    ]

    done = [e for e in events if e.type == "done"]
    assert done, "the loop produced no done event"
    outcome = done[0].payload.get("trust_outcome")
    assert outcome == "refuse", (
        f"trust_outcome was {outcome!r} for a query that found nothing; "
        "a zero-row result must refuse, not answer"
    )
