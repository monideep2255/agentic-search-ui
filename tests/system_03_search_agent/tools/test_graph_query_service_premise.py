"""Premise gate for build phase 4.11, the read-only HTTPS graph query service.

This gate exists because of what this phase can actually ship: a transport
that works and is not the same transport. Every request succeeds, every
response parses, every test that mocks the socket stays green, and the rows
reaching `cypher_provenance` are subtly not the rows psycopg2 produced. That
is build phase 2.1's defect exactly (716 passing tests over a tool that
discarded real graph rows, because `execute_cypher` returns RAW agtype wire
text and every test mocked it), and swapping the wire underneath that same
function is the most direct way this project has ever had to re-create it.

So the central premise of this gate is not "the endpoint answers". It is:

    Swapping the transport changes NOTHING observable about what
    `cypher_query` returns, while adding a server-side barrier that holds
    against a caller which bypasses the client entirely.

Both halves are load-bearing and they fail in opposite directions. A service
that is faithful but trusting is a hole in front of the graph. A service that
is strict but lossy is a silent corruption of every citation in the product.

What this gate exercises:

- Byte-equality between the two transports for the same Cypher on the same
  live graph, compared on the RAW agtype strings, never on parsed values,
  because parsing is the step that hid the defect last time.
- The real `cypher_query` pipeline end to end over HTTPS against the real
  graph, asserted on the citations it produced, never on the absence of an
  exception.
- Server-side rejection driven by a RAW HTTP client that never touches the
  client-side validator, one case per rejection class. This is the only
  shape that can distinguish real defense in depth from a service that
  merely re-states what the client already refused to send.
- Auth, including a correctly-shaped but wrong bearer, so the check cannot
  be passing on shape alone.
- The budget controls this service owes per
  `.claude/rules/tool-call-budgets.md`: the hard row limit, the per-call
  timeout clamp (asserted on the value the service actually hands to the
  executor, not on a query that happens to be slow), the per-caller rate
  limit, the pre-auth source bound, and the bound on concurrent in-flight
  queries, each asserted at the SERVICE rather than at the client.
- Concurrency at the service: the unauthenticated health probe stays
  responsive while a slow query is in flight, which is the property
  `tracker/preflight.py` depends on to tell "busy" from "down".
- Transport dispatch observed directly: which transport was used, not
  whether the call succeeded.
- Both startup refusals, since a service that starts with auth effectively
  off is worse than one that does not start.
- The exposure property: the Postgres port is still refused from the public
  internet while 443 answers.
- The audit trail's COMPLETENESS as a universal rather than as a list of
  cases: every request to the endpoint leaves a record whatever its
  outcome, including the outcomes refused before the main logging step.
- Timeout classification across the transport swap, including the
  downstream consequence in the KGX export path, since a timeout that
  arrives under the wrong type turns a graceful partial export into a
  total failure.

How an arm is gated, stated as a rule rather than left to per-arm habit
(finding F-4.11-J-01, where twelve arms were gated on the psycopg2 socket
this phase retired and seven of them never needed a graph at all):

- An arm that reaches the DEPLOYED service over HTTPS carries
  `requires_service`.
- An arm that genuinely needs the psycopg2 transport carries
  `requires_psycopg2_graph`. Exactly one property needs it, byte-equality
  between the two transports, and that arm does not skip when the
  transport is missing: see P1.
- Every other arm carries NO live marker, builds the service in process,
  and runs on any machine and any checkout with no live dependency. An arm
  that would otherwise reach a database on that path installs a tripwire
  rather than relying on the database being absent, so it cannot pass
  because a socket happened to be shut.

The test applied to each arm while re-gating: could this arm still pass
while the thing it names is broken? Where the answer was yes, the arm was
rebuilt rather than relabelled.

What this gate deliberately OMITS, stated so the gap is arguable rather than
discovered later, per `.claude/rules/goal-contracts.md`:

- Certificate validation behaviour against a hostile or expired certificate.
  The client trusts the system trust store, and nothing here presents a bad
  certificate to prove the client would refuse it.
- A genuinely slow query against the DEPLOYED service. The timeout clamp
  and the timeout response are both asserted in process, on the value the
  service hands its executor and on a raised `GraphTimeoutError`; no arm
  sends production a query engineered to burn a 90-second budget.
- Reboot survival. T-4.11-04 requires it and it is verified operationally in
  the runbook, not by an arm in this file.
- Multi-hop and multi-column result shapes beyond the two pinned below. This
  is the same one-hop blind spot that let F-2.1-A5-03 through in build phase
  2.1, and it is named here rather than left to be found.
- The MCP, GraphQL and CLI surfaces. They reach the graph through
  `cypher_query`, so P2 covers them transitively and nothing here
  exercises them directly. The KGX export path is no longer on this list:
  P14 exercises it directly over the HTTPS transport, because F-4.11-09
  found the consequence of a mis-typed timeout landing exactly there.
- Caddy's own behaviour. The forwarded-address handling this gate asserts
  is the SERVICE half; that the deployed proxy actually sends the header is
  a deployment property, verified by the runbook, not by an arm here.

Ground truth: TP53 and its 12 `gene_associated_with_condition` edges to
Disease vertices, and BRCA1's name, both already pinned by build phase 2.1's
and 4.4's gates from live reads and re-used here rather than re-derived, so
this file cannot disagree with them.

Depends on:
    - services.graph_query_service.app (the service under test)
    - system_03_search_agent.tools.graph_http_transport (the client)
    - system_03_search_agent.tools.graph_connection (the psycopg2 baseline)
    - A live AGE graph, reached on localhost by the service
    - GRAPH_QUERY_URL and the service bearer credential, for the deployed arms

Writes:
    - Nothing to the graph. Layer 1 access is read-only by credential.
    - `fixtures/phase_4_11_byte_equality.json`, and only when the psycopg2
      transport actually answered AND the operator set
      GRAPH_BYTE_EQUALITY_CAPTURE=1. See P1.
"""

from __future__ import annotations

import os
import socket
from datetime import UTC
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

_TOKEN_VAR = "GRAPH_QUERY_" + "TOKEN"

# Ground truth carried from build phase 2.1's and 4.4's gates rather than
# re-derived, so this file cannot drift from them.
TP53 = "NCBIGene:7157"
TP53_DISEASES = 12
BRCA1 = "NCBIGene:672"
BRCA1_NAME = "BRCA1 DNA repair associated"

GRAPH_HOST_PUBLIC = "46.225.128.133"
GRAPH_PG_PUBLIC_PORT = 5432

# The two pinned query shapes. One vertex return, one scalar return, so the
# wire format is exercised on more than a single column type.
CYPHER_VERTEX = (
    "MATCH (g:Gene {id: $seed})-[r:gene_associated_with_condition]->(d:Disease) "
    "RETURN d"
)
CYPHER_SCALAR = "MATCH (g:Gene {id: $seed}) RETURN g.name"


def _load_env_explicitly() -> None:
    """Populate graph and service variables from .env.

    F-2.1-04: nothing in this repository calls load_dotenv(), so these reach
    os.environ only as a side effect of importing litellm. F-4.5-01 is the
    same defect in preflight. Loading here keeps this file's behaviour its
    own rather than dependent on an unrelated import.
    """
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if "=" not in stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _psycopg2_is_reachable() -> bool:
    """Whether the graph answers on the psycopg2 path right now.

    F-2.1-B12: checked fresh per test rather than once at import, because
    the transport can drop mid-session and an import-time guard cannot see
    that.

    RENAMED 2026-08-22, finding F-4.11-J-01. It used to be
    `_graph_is_reachable`, and that name is what made the critical
    plausible: twelve arms were gated on "the graph", which reads as "this
    arm needs data", when what it actually tests is one specific socket,
    the SSH local port forward this phase retired. Seven of those arms
    never touched a database at all. The name now says which transport it
    probes, so gating an in-process arm on it reads as the mistake it is.
    """
    _load_env_explicitly()
    host = os.environ.get("GRAPH_PG_HOST")
    port = os.environ.get("GRAPH_PG_PORT")
    if not host or not port:
        return False
    try:
        with socket.create_connection((host, int(port)), timeout=3):
            return True
    except OSError:
        return False


def _service_is_reachable() -> bool:
    """Whether the DEPLOYED HTTPS service answers right now."""
    _load_env_explicitly()
    url = os.environ.get("GRAPH_QUERY_URL")
    if not url or not os.environ.get(_TOKEN_VAR):
        return False
    try:
        import httpx

        response = httpx.get(url.rstrip("/") + "/healthz", timeout=5.0)
        return response.status_code == 200
    except Exception:  # noqa: BLE001 - reachability probe, any failure is "no"
        return False


_RUN_LIVE = os.environ.get("RUN_PREMISE_GATE") == "1"

# A gate run without RUN_PREMISE_GATE=1 finishes in seconds and LOOKS like a
# pass. The two markers below keep "not run" distinguishable from "passed",
# which is the property F-4.5-01 restored and build phase 4.6 depended on.
#
# There are exactly two live markers, and neither is a general "this arm
# needs the graph" marker any more. See the module docstring's "How an arm
# is gated" section for the rule and for what F-4.11-J-01 measured.
requires_service = pytest.mark.skipif(
    not _RUN_LIVE or not _service_is_reachable(),
    reason="needs RUN_PREMISE_GATE=1 and the deployed HTTPS service",
)
requires_psycopg2_graph = pytest.mark.skipif(
    not _RUN_LIVE or not _psycopg2_is_reachable(),
    reason="needs RUN_PREMISE_GATE=1 and the psycopg2 transport",
)

# Where the byte-equality baseline lives once it has been minted from the
# psycopg2 transport. See P1 for why a file exists at all.
_BASELINE_PATH = Path(__file__).with_name("fixtures") / "phase_4_11_byte_equality.json"
_CAPTURE_BASELINE = os.environ.get("GRAPH_BYTE_EQUALITY_CAPTURE") == "1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def configured_token(monkeypatch: pytest.MonkeyPatch) -> str:
    """Guarantee the service has a credential, without needing a deployment.

    Added 2026-08-22, finding F-4.11-05, raised by the builder of the
    service. Before it, every arm using the app in process ERRORED at
    fixture setup on a machine with no configured credential, because
    `build_app()` correctly refuses to start without one. Five arms that
    test auth and the startup refusals themselves were therefore unrunnable
    exactly where they are cheapest to run, and five errors that look like
    defects is how a gate stops being read.

    Skipping them was the other option and it is the worse one: these arms
    need SOME credential, not the deployed one, so skipping would trade a
    confusing error for a silent hole. The fixture supplies a synthetic
    value instead, and the arms then run everywhere.
    """
    existing = os.environ.get(_TOKEN_VAR)
    if existing:
        return existing
    synthetic = "premise-gate-synthetic-credential-not-a-real-one"
    monkeypatch.setenv(_TOKEN_VAR, synthetic)
    return synthetic


@pytest.fixture()
def service_client(configured_token: str, monkeypatch: pytest.MonkeyPatch) -> Any:
    """A raw HTTP client bound to the service app IN PROCESS.

    Deliberately raw. Every server-side rejection arm below must reach the
    endpoint without passing through the client-side validator, because a
    payload the client would have refused to send proves nothing about
    whether the SERVER would have refused it.
    """
    from fastapi.testclient import TestClient

    from services.graph_query_service.app import build_app

    # The service refuses to start when this is set in its own environment,
    # which is the recursion guard P12b pins. A developer machine that has
    # cut over to the HTTPS transport has it set, so it is cleared for the
    # in-process app rather than letting the guard fire on a caller's config.
    monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)
    return TestClient(build_app())


@pytest.fixture()
def valid_token(configured_token: str) -> str:
    return configured_token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


def _payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "cypher": CYPHER_VERTEX,
        "params": {"seed": TP53},
        "row_limit": 25,
        "timeout_s": 30.0,
        "as_clause": "(result agtype)",
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# P1: the central premise. Byte-equality between the two transports.
# ---------------------------------------------------------------------------


_P1_CASES: list[tuple[str, str, dict[str, Any]]] = [
    ("vertex", CYPHER_VERTEX, {"seed": TP53}),
    ("scalar", CYPHER_SCALAR, {"seed": BRCA1}),
]


def _read_baseline(case: str) -> dict[str, Any] | None:
    """The psycopg2 side of the byte-equality comparison, if it was minted."""
    if not _BASELINE_PATH.exists():
        return None
    import json

    try:
        document = json.loads(_BASELINE_PATH.read_text())
    except ValueError:
        return None
    entry = document.get("cases", {}).get(case)
    return entry if isinstance(entry, dict) else None


def _write_baseline(case: str, cypher: str, rows: Any, total: int) -> None:
    """Mint or update one case of the psycopg2 baseline.

    Only ever called when the psycopg2 transport actually answered and the
    operator asked for a capture. A baseline written from anything else
    would make the comparison circular.
    """
    import json
    from datetime import datetime

    _BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    document: dict[str, Any] = {"cases": {}}
    if _BASELINE_PATH.exists():
        try:
            existing = json.loads(_BASELINE_PATH.read_text())
            if isinstance(existing, dict) and isinstance(existing.get("cases"), dict):
                document = existing
        except ValueError:
            document = {"cases": {}}
    document["cases"][case] = {
        "cypher": cypher,
        "rows": rows,
        "total_available": total,
        "transport": "psycopg2",
        "captured_at": datetime.now(UTC).isoformat(),
    }
    _BASELINE_PATH.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


@requires_service
@pytest.mark.parametrize(("case", "cypher", "params"), _P1_CASES, ids=[c[0] for c in _P1_CASES])
def test_p1_https_rows_are_byte_identical_to_psycopg2_rows(
    case: str, cypher: str, params: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The transport swap changes nothing about what the caller receives.

    Compared on the raw agtype strings. `cypher_provenance` parses these
    downstream, and build phase 2.1 proved a whole phase can pass its suite
    while these strings are being discarded, so a comparison after parsing
    would be testing the wrong layer.

    REBUILT 2026-08-22, finding F-4.11-J-02, and the way it was wrong is
    the reusable part. This arm carries the phase's central premise, and it
    used to carry `requires_graph` as well as `requires_service`. The
    cutover in T-4.11-05 retired the psycopg2 socket, so the arm began
    SKIPPING on the exact configuration the phase ships, and a skip is
    indistinguishable from a pass in a run's headline. The premise stopped
    being re-checkable at the moment the phase succeeded, and nothing said
    so out loud.

    It does not skip any more. In a live run it does one of three things,
    and only the first two can be green:

    - Both transports available: the comparison runs for real, and with
      GRAPH_BYTE_EQUALITY_CAPTURE=1 the psycopg2 side is also written to
      `fixtures/phase_4_11_byte_equality.json` so the next person does not
      need the transport.
    - Only HTTPS available, baseline present: the live HTTPS read is
      compared against the committed psycopg2 rows, byte for byte. The
      graph is a pinned snapshot, so a mismatch is a real signal rather
      than noise.
    - Only HTTPS available, no baseline: the arm FAILS, loudly, naming the
      one command that mints the baseline. A red arm is the point. The
      alternative was a green run that quietly means "nobody checked".
    """
    from system_03_search_agent.tools.graph_connection import execute_cypher

    _load_env_explicitly()
    monkeypatch.setenv("GRAPH_QUERY_URL", os.environ["GRAPH_QUERY_URL"])
    http_rows, http_total = execute_cypher(cypher, params, row_limit=25)

    for row in http_rows:
        for value in row.values():
            assert value is None or isinstance(value, str), (
                "the wire format must carry agtype text unchanged; a coerced "
                "value here is the build phase 2.1 defect returning"
            )

    if _psycopg2_is_reachable():
        monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)
        pg_rows, pg_total = execute_cypher(cypher, params, row_limit=25)
        if _CAPTURE_BASELINE:
            _write_baseline(case, cypher, pg_rows, pg_total)
        assert http_total == pg_total
        assert http_rows == pg_rows
        return

    baseline = _read_baseline(case)
    if baseline is None:
        pytest.fail(
            "THE CENTRAL PREMISE OF BUILD PHASE 4.11 WAS NOT RE-VERIFIED IN "
            "THIS RUN. Byte-equality between the psycopg2 and HTTPS "
            "transports needs both transports, the cutover retired the "
            "psycopg2 one, and no committed baseline exists to compare "
            "against. This arm fails rather than skipping because a skip "
            "reads as a pass in the run headline, which is finding "
            "F-4.11-J-02. To close it once and for all: open the forward "
            "(ssh -N -L 15432:127.0.0.1:5432 root@" + GRAPH_HOST_PUBLIC + "), "
            "then run this gate once with GRAPH_BYTE_EQUALITY_CAPTURE=1 and "
            "commit " + str(_BASELINE_PATH.relative_to(_REPO_ROOT)) + ". "
            "Every later run then re-verifies the premise with no forward "
            "open at all."
        )

    assert http_total == baseline["total_available"], (
        "total_available diverged from the psycopg2 baseline for case " + case
    )
    assert http_rows == baseline["rows"], (
        "the HTTPS transport's raw agtype rows diverged from the psycopg2 "
        "baseline for case " + case
    )


@requires_service
def test_p1b_pinned_ground_truth_survives_the_http_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The HTTPS path returns the 12 TP53 disease edges, not merely 12 rows."""
    _load_env_explicitly()
    monkeypatch.setenv("GRAPH_QUERY_URL", os.environ["GRAPH_QUERY_URL"])
    from system_03_search_agent.tools.graph_connection import execute_cypher

    rows, total = execute_cypher(CYPHER_VERTEX, {"seed": TP53}, row_limit=25)
    assert total == TP53_DISEASES
    assert all("Disease" in str(row["result"]) for row in rows)


# ---------------------------------------------------------------------------
# P2: the real pipeline, end to end, over HTTPS.
# ---------------------------------------------------------------------------


@requires_service
@pytest.mark.asyncio()
async def test_p2_cypher_query_produces_citations_over_https(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real tool, the real graph, the new transport, asserted on output.

    F-4.5-09's lesson: when a gate supplies the thing under test it cannot
    tell you the thing exists. Every other arm in this file constructs a
    payload. This one constructs nothing and asks the product for an answer.
    """
    _load_env_explicitly()
    monkeypatch.setenv("GRAPH_QUERY_URL", os.environ["GRAPH_QUERY_URL"])

    from system_03_search_agent.harness.harness import Harness
    from system_03_search_agent.tools.cypher_query import cypher_query
    from system_03_search_agent.tools.cypher_schemas import CypherQueryInput

    result = await cypher_query(
        Harness(trace_id="premise-4.11-https"),
        CypherQueryInput(
            query_intent="Which diseases are associated with TP53?",
            query_class="lookup",
            target_entities=[TP53],
            row_limit=25,
        ),
    )

    # `cypher_query` never raises: every failure folds into status="error"
    # with a message. So asserting on the status is asserting on the real
    # outcome, where asserting that no exception escaped would assert
    # nothing at all.
    assert result.status == "ok", (
        "the HTTPS transport did not produce a result: status="
        + result.status
        + ", error="
        + str(result.error)
    )
    assert result.rows, "the HTTPS transport produced no rows"
    assert result.row_count == len(result.rows)
    for row in result.rows:
        assert row.curie, "a row crossed the wire without its identity"
        assert row.graph_snapshot_version, "a row crossed the wire without provenance"
        if row.source_url is not None:
            assert row.source_url.startswith("https://")


# ---------------------------------------------------------------------------
# P3: server-side rejection, reached by a caller that bypasses the client.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("cypher", "MATCH (g:Gene) DELETE g RETURN g", "cypher_rejected"),
        (
            "cypher",
            "MATCH (g:Gene)-[r:not_a_real_predicate]->(d:Disease) RETURN d",
            "cypher_rejected",
        ),
        ("cypher", "MATCH (g:Gene)--(d:Disease) RETURN d", "cypher_rejected"),
        ("row_limit", 10_000_000, "invalid_payload"),
        ("as_clause", "(result agtype); DROP TABLE users", "invalid_payload"),
    ],
    ids=[
        "write_clause",
        "unknown_edge_label",
        "missing_edge_label",
        "row_limit_over_max",
        "malformed_as_clause",
    ],
)
def test_p3_server_rejects_what_a_bypassed_client_would_send(
    service_client: Any,
    valid_token: str,
    field: str,
    value: Any,
    expected_code: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defense in depth is only depth if the client is out of the path.

    Section 24 asks for these checks server-side precisely so a bug in the
    client-side validator is not the only thing standing between a request
    and the database. Every payload here is posted raw.

    UNGATED 2026-08-22, finding F-4.11-J-01. These five arms carried
    `requires_graph` and never touched a database: every one of them is
    refused before the endpoint reaches its executor. They were therefore
    the five arms proving Section 24's whole defense-in-depth clause, and
    they went dark the moment the phase retired the psycopg2 socket. The
    judge demonstrated they pass against a socket that is not even
    Postgres, which is the proof that the gate was never the reason they
    were green.

    The tripwire replaces the marker rather than nothing replacing it. A
    marker made the arm's correctness depend on a database being absent;
    the tripwire makes it depend on the rejection happening, which is what
    the arm claims. If a future change lets one of these payloads through
    to execution, this arm goes red on any machine instead of turning into
    a connection error on some machines and a skip on others.
    """
    import services.graph_query_service.app as app_module

    def _tripwire(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "the graph was reached for a payload the service must refuse "
            "before execution"
        )

    monkeypatch.setattr(app_module, "execute_cypher", _tripwire)
    response = service_client.post(
        "/v1/cypher", json=_payload(**{field: value}), headers=_auth(valid_token)
    )
    assert response.status_code >= 400
    assert response.json()["error"]["code"] == expected_code


def test_p3b_a_rejected_payload_never_reached_the_database(
    service_client: Any, valid_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rejection happens before execution, not after it.

    A service that runs the query and then decides it should not have is
    still a service that ran the query.
    """
    import services.graph_query_service.app as app_module

    calls: list[Any] = []

    def _tripwire(*args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        raise AssertionError("the graph was reached for a payload that must be rejected")

    monkeypatch.setattr(app_module, "execute_cypher", _tripwire)
    response = service_client.post(
        "/v1/cypher",
        json=_payload(cypher="MATCH (g:Gene) DETACH DELETE g RETURN g"),
        headers=_auth(valid_token),
    )
    assert response.status_code >= 400
    assert calls == []


# ---------------------------------------------------------------------------
# P4: auth.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("headers", "case"),
    [
        ({}, "no_header"),
        ({"Authorization": "Bearer "}, "empty_bearer"),
        ({"Authorization": "not-a-bearer-at-all"}, "wrong_scheme"),
    ],
)
def test_p4_unauthenticated_callers_are_refused(
    service_client: Any, headers: dict[str, str], case: str
) -> None:
    response = service_client.post("/v1/cypher", json=_payload(), headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_p4b_a_correctly_shaped_wrong_token_is_refused(
    service_client: Any, valid_token: str
) -> None:
    """The check must be on the value, not on the shape.

    A wrong credential of the right length and alphabet is the case that
    separates a real comparison from a regex that only sees shape. Build
    phase 4.3 spent four attempts learning that a proxy for a property is
    not the property.
    """
    filler = "a" if valid_token[0] != "a" else "b"
    wrong = filler * len(valid_token)
    assert wrong != valid_token
    response = service_client.post("/v1/cypher", json=_payload(), headers=_auth(wrong))
    assert response.status_code == 401


def test_p4c_a_refusal_discloses_nothing_about_the_credential(
    service_client: Any, valid_token: str
) -> None:
    response = service_client.post(
        "/v1/cypher", json=_payload(), headers=_auth("clearly-wrong")
    )
    body = response.text
    assert valid_token not in body
    assert str(len(valid_token)) not in body


# ---------------------------------------------------------------------------
# P5, P6: the budget controls, asserted at the service.
# ---------------------------------------------------------------------------


def test_p5_rate_limit_fires_with_an_actionable_retry_after(
    service_client: Any, valid_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A saturated caller fails fast rather than joining an unbounded queue.

    `.claude/rules/tool-call-budgets.md` requires the error carry a
    retry_after estimate and the saturated family name, because the Act step
    reads this error and decides its next move. "Rate limited" alone is not
    actionable.

    DECOUPLED FROM THE LIVE GRAPH 2026-08-22, finding F-4.11-06. This arm
    was marked `requires_graph` and it FAILED against the live graph while
    the control it grades was working correctly. The limiter is a sliding
    60 second window with a limit of 60, and each live query takes roughly
    two seconds, so sending 62 of them takes over two minutes and the
    window empties from the front faster than the loop fills it from the
    back. The arm was measuring how fast the graph answers, not whether the
    limiter fires.

    The downstream execution is stubbed so the loop runs in milliseconds.
    That is isolation of the control under test, not the gate supplying its
    own answer: the limiter runs entirely unmodified, and what is replaced
    is the graph behind it, which this arm never had any reason to exercise.
    The consequence worth stating is that the arm now runs everywhere, on
    any machine, with no live dependency at all.
    """
    import services.graph_query_service.app as app_module
    from services.graph_query_service.app import RATE_LIMIT_PER_MINUTE

    monkeypatch.setattr(
        app_module, "execute_cypher", lambda *a, **k: ([{"result": "stub"}], 1)
    )

    last = None
    for _ in range(RATE_LIMIT_PER_MINUTE + 2):
        last = service_client.post(
            "/v1/cypher", json=_payload(), headers=_auth(valid_token)
        )
    assert last is not None
    assert last.status_code == 429
    error = last.json()["error"]
    assert error["code"] == "rate_limited"
    assert isinstance(error["retry_after"], (int, float))
    assert error["retry_after"] > 0


def test_p6_the_service_clamps_the_per_call_timeout_it_actually_uses(
    service_client: Any, valid_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caller cannot raise the per-call budget past the tool's own.

    REBUILT 2026-08-22, findings F-4.11-J-01 and F-4.11-J-09. The previous
    form posted the ordinary pinned query with an absurd `timeout_s` and
    then did `if response.status_code == 200: pytest.skip(...)`. Against a
    graph that answers promptly, which is every run this repository has
    recorded for this query, the arm reached `pytest.skip` and asserted
    nothing at all; it also carried `requires_graph`, so on the shipped
    configuration it did not even get that far. Removing the clamp
    entirely left the whole gate green (mutation M5).

    The property is not "a slow query times out". It is "the value the
    service hands its executor is the clamped one, never the caller's".
    That is observable directly, on any machine, by reading what the
    executor was called with, so this arm asserts the clamp itself rather
    than a slow query as a proxy for it. P6b covers the other half, that
    an executor timeout comes back actionable rather than as a bare 500.
    """
    import services.graph_query_service.app as app_module
    from system_03_search_agent.tools.graph_schema_constants import (
        CYPHER_QUERY_TIMEOUT_SECONDS,
    )

    seen: list[dict[str, Any]] = []

    def _capture(*args: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        seen.append(kwargs)
        return [{"result": "stub"}], 1

    monkeypatch.setattr(app_module, "execute_cypher", _capture)
    response = service_client.post(
        "/v1/cypher",
        json=_payload(timeout_s=CYPHER_QUERY_TIMEOUT_SECONDS * 100, row_limit=1),
        headers=_auth(valid_token),
    )
    assert response.status_code == 200
    assert seen, "the service never reached its executor; this arm proved nothing"
    assert seen[0]["timeout_s"] == CYPHER_QUERY_TIMEOUT_SECONDS, (
        "the caller's timeout_s reached the executor unclamped: "
        + str(seen[0]["timeout_s"])
    )


def test_p6b_a_query_that_outruns_the_budget_returns_an_actionable_timeout(
    service_client: Any, valid_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A query that outruns its budget comes back actionable, not as a 500.

    Carries the assertions the old P6 would have made if it had ever
    reached them: the status is not 500, the code is `timeout`, and the
    message tells the Act step what to do next rather than only what
    failed, per `.claude/rules/tool-call-budgets.md`.
    """
    import services.graph_query_service.app as app_module
    from system_03_search_agent.tools.graph_connection import GraphTimeoutError

    def _slow(*args: Any, **kwargs: Any) -> Any:
        raise GraphTimeoutError(
            "graph query exceeded its budget, retry with a narrower "
            "query_intent or a smaller query_class"
        )

    monkeypatch.setattr(app_module, "execute_cypher", _slow)
    response = service_client.post(
        "/v1/cypher", json=_payload(row_limit=1), headers=_auth(valid_token)
    )
    assert response.status_code != 500
    assert response.status_code == 504
    error = response.json()["error"]
    assert error["code"] == "timeout"
    assert "narrower" in error["message"] or "smaller" in error["message"]


# ---------------------------------------------------------------------------
# P7, P8: dispatch, observed rather than inferred.
# ---------------------------------------------------------------------------


def test_p7_dispatch_uses_http_when_the_url_is_set_and_never_opens_psycopg2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Which transport ran, not whether the call succeeded."""
    import system_03_search_agent.tools.graph_connection as gc

    def _no_pg() -> Any:
        raise AssertionError("psycopg2 was opened while GRAPH_QUERY_URL was set")

    seen: list[dict[str, Any]] = []

    def _fake_http(**kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        seen.append(kwargs)
        return [{"result": "x"}], 1

    monkeypatch.setenv("GRAPH_QUERY_URL", "https://example.invalid")
    monkeypatch.setenv(_TOKEN_VAR, "t")
    monkeypatch.setattr(gc, "_default_connection_factory", _no_pg)
    monkeypatch.setattr(gc, "execute_cypher_over_http", _fake_http)

    rows, total = gc.execute_cypher(CYPHER_VERTEX, {"seed": TP53})
    assert seen, "the HTTP transport was not called"
    assert (rows, total) == ([{"result": "x"}], 1)


def test_p7b_dispatch_uses_psycopg2_when_the_url_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import system_03_search_agent.tools.graph_connection as gc

    def _no_http(**kwargs: Any) -> Any:
        raise AssertionError("the HTTP transport ran while GRAPH_QUERY_URL was unset")

    closed: list[bool] = []

    class _Cur:
        description = (("result",),)

        def __enter__(self) -> _Cur:  # noqa: PYI034 - a fake cursor, not a protocol
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def execute(self, *a: Any, **k: Any) -> None:
            return None

        def fetchall(self) -> list[tuple[str]]:
            return [("row",)]

    class _Conn:
        def cursor(self) -> _Cur:
            return _Cur()

        def close(self) -> None:
            closed.append(True)

    monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)
    monkeypatch.setattr(gc, "execute_cypher_over_http", _no_http)
    rows, _ = gc.execute_cypher(CYPHER_VERTEX, None, connection_factory=_Conn)
    assert closed == [True]
    assert rows == [{"result": "row"}]


def test_p8_a_connection_factory_with_the_url_set_raises_rather_than_being_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two transports named in one call is a caller defect, not a preference.

    Silently honouring one and discarding the other is how a test suite goes
    on passing against a transport nobody is shipping.

    TIGHTENED 2026-08-22, finding F-4.11-04, raised by the builder of the
    code this arm grades rather than by the arm's author. The original body
    was only:

        with pytest.raises(gc.GraphError):
            gc.execute_cypher(CYPHER_VERTEX, None, connection_factory=...)

    and that passes for the wrong reason. Delete the conflict check
    entirely and the call proceeds to a real HTTPS attempt against
    `example.invalid`, whose DNS failure is classified into
    `GraphConnectionError`, which IS a `GraphError`. So the arm stayed green
    with the control it exists to prove removed, which is the definition of
    a vacuous arm and the single most repeated defect in this repository.

    Two tripwires make the assertion mean what it says: neither transport
    may be entered at all, so the only way to reach the raise is the
    conflict check itself.
    """
    import system_03_search_agent.tools.graph_connection as gc

    def _no_http(**kwargs: Any) -> Any:
        raise AssertionError("the HTTP transport ran instead of refusing the conflict")

    def _no_pg() -> Any:
        raise AssertionError("psycopg2 was opened instead of refusing the conflict")

    monkeypatch.setenv("GRAPH_QUERY_URL", "https://example.invalid")
    monkeypatch.setenv(_TOKEN_VAR, "t")
    monkeypatch.setattr(gc, "execute_cypher_over_http", _no_http)
    monkeypatch.setattr(gc, "_default_connection_factory", _no_pg)

    with pytest.raises(gc.GraphError):
        gc.execute_cypher(CYPHER_VERTEX, None, connection_factory=_no_pg)


# ---------------------------------------------------------------------------
# P9: every HTTPS failure still arrives as a typed GraphError.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        (401, "unauthorized", "GraphAuthError"),
        (403, "unauthorized", "GraphAuthError"),
        (504, "timeout", "GraphTimeoutError"),
        (429, "rate_limited", "GraphRateLimitedError"),
        (500, "internal", "GraphConnectionError"),
        (400, "cypher_rejected", "GraphConnectionError"),
    ],
)
def test_p9_http_failures_map_into_the_existing_error_family(
    status: int, code: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`cypher_query` already handles GraphError. It must keep handling everything.

    The Act step reads the error type to decide whether to retry, wait, or
    move on with partial results. An unclassified exception escaping the
    transport removes that decision.
    """
    import system_03_search_agent.tools.graph_http_transport as t

    class _Response:
        status_code = status
        text = "m"

        @staticmethod
        def json() -> dict[str, Any]:
            return {"error": {"code": code, "message": "m", "retry_after": 1.0}}

    monkeypatch.setattr(t, "_post", lambda **kwargs: _Response())
    monkeypatch.setenv("GRAPH_QUERY_URL", "https://example.invalid")
    monkeypatch.setenv(_TOKEN_VAR, "t")
    with pytest.raises(getattr(t, expected)) as caught:
        t.execute_cypher_over_http(
            cypher=CYPHER_VERTEX,
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )
    assert str(caught.value)


def test_p9b_a_connection_refusal_is_a_connection_error_not_a_bare_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import system_03_search_agent.tools.graph_http_transport as t

    def _boom(**kwargs: Any) -> Any:
        raise OSError("connection refused")

    monkeypatch.setattr(t, "_post", _boom)
    monkeypatch.setenv("GRAPH_QUERY_URL", "https://example.invalid")
    monkeypatch.setenv(_TOKEN_VAR, "t")
    with pytest.raises(t.GraphConnectionError):
        t.execute_cypher_over_http(
            cypher=CYPHER_VERTEX,
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )


# ---------------------------------------------------------------------------
# P10: the exposure property.
# ---------------------------------------------------------------------------


@requires_service
def test_p10_the_database_port_is_still_closed_to_the_internet() -> None:
    """Section 24's whole point: the database port never opens to the internet.

    A service that fronts the graph while the graph itself stays directly
    reachable has added a door without closing one.

    REBUILT 2026-08-22, finding F-4.11-01, and the original is worth stating
    because the way it was wrong is the reusable part. It read:

        with pytest.raises(OSError):
            socket.create_connection((GRAPH_HOST_PUBLIC, 5432), timeout=5)

    which is vacuous in the environment it runs in. Measured that day: a
    connection to `github.com:12345`, a port GitHub plainly neither serves
    nor drops, ALSO times out here, because this sandbox answers any
    unreachable destination with a timeout rather than a refusal. A
    TimeoutError is an OSError, so that arm passed on a sandbox denial and
    would have gone on passing with the database port wide open. This is
    `.claude/rules/sandbox-diagnosis.md`'s own warning arriving as a test
    defect: a denial and an outage look identical at this layer.

    The rebuild makes the two outcomes distinguishable inside ONE run, which
    is the property the original lacked. The service's own port must CONNECT
    from this same machine first. That establishes the path to this host is
    open here, so a timeout on 5432 from the same host in the same seconds
    is attributable to the host rather than to the sandbox. Under the old
    form both ports timing out was a pass. Under this one it is a failure.
    """
    with socket.create_connection((GRAPH_HOST_PUBLIC, 443), timeout=8):
        pass

    with pytest.raises(OSError):
        socket.create_connection((GRAPH_HOST_PUBLIC, GRAPH_PG_PUBLIC_PORT), timeout=8)


@requires_service
def test_p10c_postgres_is_bound_to_loopback_on_the_box_itself() -> None:
    """The same property read where a network probe cannot be fooled at all.

    P10's rebuild is sound and still infers from outside. This one observes
    the binding directly on the host, so the two arms fail for independent
    reasons and no single environmental quirk can make both green.
    """
    import subprocess

    listeners = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "root@" + GRAPH_HOST_PUBLIC,
            "ss -lnt sport = :5432",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    ).stdout

    assert "5432" in listeners, "no Postgres listener found; this arm proved nothing"
    for line in listeners.splitlines()[1:]:
        if not line.strip():
            continue
        local_address = line.split()[3]
        assert local_address.startswith(("127.0.0.1:", "[::1]:")), (
            "Postgres is listening on " + local_address + ", not on loopback only"
        )


@requires_service
def test_p10b_the_service_answers_over_real_tls() -> None:
    """TLS is terminated by a certificate the system trust store accepts."""
    import httpx

    _load_env_explicitly()
    url = os.environ["GRAPH_QUERY_URL"]
    assert url.startswith("https://"), "the transport must be HTTPS, not plaintext"
    response = httpx.get(url.rstrip("/") + "/healthz", timeout=10.0, verify=True)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# P11: the credential never leaks.
# ---------------------------------------------------------------------------


def test_p11_the_credential_never_appears_in_a_response_body(
    service_client: Any, valid_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No response body ever carries the credential, on any outcome.

    UNGATED 2026-08-22, finding F-4.11-J-01. This arm carried
    `requires_graph` and never needed one: two of its three payloads are
    refused before execution, and the third only reached a database
    because nothing stopped it. With the socket retired it went dark, and
    with the socket present-but-wrong it passed for the wrong reason,
    since a failed connection also produces a body with no credential in
    it. Stubbing the executor makes the SUCCESS path a real case here
    rather than an accident of whether a database answered.
    """
    import services.graph_query_service.app as app_module

    monkeypatch.setattr(
        app_module, "execute_cypher", lambda *a, **k: ([{"result": "stub"}], 1)
    )

    bodies = []
    for payload in (
        _payload(),
        _payload(cypher="MATCH (g:Gene) DELETE g RETURN g"),
        _payload(row_limit=10_000_000),
    ):
        bodies.append(
            service_client.post(
                "/v1/cypher", json=payload, headers=_auth(valid_token)
            ).text
        )
    for body in bodies:
        assert valid_token not in body


def test_p11c_a_refused_call_is_logged_too(
    service_client: Any, valid_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    """The audit log is COMPLETE, not merely clean.

    Added 2026-08-22 with the fix for finding F-4.11-03. The service logged
    only calls that got past auth and past the rate limit, so a credential
    being guessed and a caller being throttled, the two classes of call an
    operator most needs to see, left no trace at all. Section 24 asks for
    every call logged.

    P11b could not catch this and never will: it asserts the credential
    does not appear in the log, which stays true when whole categories of
    call are missing from it. A clean log and a complete log are different
    properties and each needs its own arm.
    """
    with caplog.at_level("WARNING"):
        service_client.post("/v1/cypher", json=_payload(), headers=_auth("wrong"))

    messages = [record.getMessage() for record in caplog.records]
    assert any("auth rejected" in message for message in messages), (
        "a rejected credential left no audit trail"
    )
    assert all("wrong" not in message for message in messages), (
        "the rejected credential itself was written to the log"
    )


def test_p11b_the_credential_never_appears_in_the_audit_log(
    service_client: Any, valid_token: str, caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every call is logged. None of those lines carries the credential.

    UNGATED 2026-08-22, finding F-4.11-J-01, for the same reason as P11:
    the log line this arm reads is emitted before the executor runs, so a
    database was never needed and the marker only made the arm skip on the
    configuration the phase ships.
    """
    import services.graph_query_service.app as app_module

    monkeypatch.setattr(
        app_module, "execute_cypher", lambda *a, **k: ([{"result": "stub"}], 1)
    )
    with caplog.at_level("INFO"):
        service_client.post("/v1/cypher", json=_payload(), headers=_auth(valid_token))
    assert caplog.records, (
        "the service logged nothing; Section 24 requires every call logged"
    )
    for record in caplog.records:
        assert valid_token not in record.getMessage()


# ---------------------------------------------------------------------------
# P12: the two startup refusals.
# ---------------------------------------------------------------------------


def test_p12_the_service_refuses_to_start_without_a_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Starting with auth effectively off is worse than not starting."""
    from services.graph_query_service.app import build_app

    monkeypatch.delenv(_TOKEN_VAR, raising=False)
    with pytest.raises(RuntimeError):
        build_app()


def test_p12b_the_service_refuses_to_start_if_it_would_call_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The recursion hazard, closed at startup rather than discovered live.

    The service reuses `execute_cypher`, which dispatches on GRAPH_QUERY_URL.
    If that variable is ever set in the service's own environment, the
    service calls itself.
    """
    from services.graph_query_service.app import build_app

    monkeypatch.setenv(_TOKEN_VAR, "x" * 32)
    monkeypatch.setenv("GRAPH_QUERY_URL", "https://example.invalid")
    with pytest.raises(RuntimeError):
        build_app()


# ---------------------------------------------------------------------------
# P13: concurrency. The gate's own coverage statement named this as a
# deliberate omission, and the omission is exactly where F-4.11-08 lived.
# ---------------------------------------------------------------------------


_SLOW_QUERY_SECONDS = 1.5


@pytest.mark.asyncio()
async def test_p13_a_slow_query_does_not_stall_the_health_probe(
    configured_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One slow query must not freeze every other caller.

    Added 2026-08-22 for finding F-4.11-08, and written to fail against the
    code as it stood before that fix. The endpoint was `async def` and
    called the BLOCKING `execute_cypher` directly on the event loop, on a
    single-worker uvicorn, so one legal slow query serialized every other
    request. The adversary measured the unauthenticated `/healthz` taking
    10.97 seconds while a 12 second query was in flight.

    That matters beyond latency. `tracker/preflight.py` reads `/healthz` to
    decide whether the graph transport is up, so during any slow query
    preflight reports the graph DOWN while it is merely busy, which is the
    exact "the transport looks down" failure this whole phase was pulled
    forward to eliminate.

    The assertion is an ORDERING, not a duration, because a duration
    measured from the test's own side can be taken after the block has
    already ended and read as fast. The probe must complete while the slow
    query is still running: `slow_started < health_done < slow_finished`.
    The first half is what stops this arm passing when the probe simply
    got in first, and it is satisfied on both the blocking and the
    non-blocking implementation because of the head start below.
    """
    import asyncio
    import time

    import httpx

    import services.graph_query_service.app as app_module
    from services.graph_query_service.app import build_app

    monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)
    timings: dict[str, float] = {}

    def _slow(*args: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        timings["slow_started"] = time.monotonic()
        time.sleep(_SLOW_QUERY_SECONDS)
        timings["slow_finished"] = time.monotonic()
        return [{"result": "stub"}], 1

    monkeypatch.setattr(app_module, "execute_cypher", _slow)
    app = build_app()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://service") as client:
        slow = asyncio.create_task(
            client.post(
                "/v1/cypher",
                json=_payload(),
                headers=_auth(configured_token),
                timeout=_SLOW_QUERY_SECONDS * 10,
            )
        )
        # A head start, so the slow query is genuinely in flight before the
        # probe is issued. On the blocking implementation this sleep does
        # not resume until the block ends, which is itself the defect.
        await asyncio.sleep(0.1)
        health = await client.get("/healthz", timeout=_SLOW_QUERY_SECONDS * 10)
        timings["health_done"] = time.monotonic()
        slow_response = await slow

    assert slow_response.status_code == 200
    assert health.status_code == 200
    assert "slow_started" in timings, "the slow query never ran; this arm proved nothing"
    assert timings["slow_started"] < timings["health_done"], (
        "the health probe completed before the slow query even started, so "
        "this arm measured nothing about concurrency"
    )
    assert timings["health_done"] < timings["slow_finished"], (
        "the unauthenticated health probe did not complete until the slow "
        "query had finished, so one slow query stalls the probe "
        "tracker/preflight.py uses to decide the transport is up"
    )


@pytest.mark.asyncio()
async def test_p13b_concurrent_in_flight_queries_are_bounded_and_fail_fast(
    configured_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Moving work off the event loop must not make it unbounded.

    `.claude/rules/tool-call-budgets.md` allows a bounded FIFO wait and
    requires a fail-fast `rate_limited` carrying `retry_after` and the
    saturated family name once the bound is reached. It forbids an
    unbounded queue. Running the blocking executor in a threadpool without
    a cap would trade one defect for another: the adversary's own "what I
    would attack next" names exhausting the graph's connection pool with
    concurrent long-running-but-legal queries.

    The bound is exercised at 1 rather than at its shipped value so the arm
    stays fast; the control under test is the bound itself, not the number.
    """
    import asyncio

    import httpx

    import services.graph_query_service.app as app_module
    from services.graph_query_service.app import build_app

    monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)
    monkeypatch.setattr(app_module, "MAX_CONCURRENT_QUERIES", 1)
    monkeypatch.setattr(app_module, "MAX_CONCURRENCY_WAIT_SECONDS", 0.2)

    def _slow(*args: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        import time

        time.sleep(_SLOW_QUERY_SECONDS)
        return [{"result": "stub"}], 1

    monkeypatch.setattr(app_module, "execute_cypher", _slow)
    app = build_app()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://service") as client:
        first = asyncio.create_task(
            client.post(
                "/v1/cypher",
                json=_payload(),
                headers=_auth(configured_token),
                timeout=_SLOW_QUERY_SECONDS * 10,
            )
        )
        await asyncio.sleep(0.1)
        second = await client.post(
            "/v1/cypher",
            json=_payload(),
            headers=_auth(configured_token),
            timeout=_SLOW_QUERY_SECONDS * 10,
        )
        await first

    assert second.status_code == 429, (
        "a second in-flight query was admitted past the concurrency bound "
        "instead of failing fast"
    )
    error = second.json()["error"]
    assert error["code"] == "rate_limited"
    assert isinstance(error["retry_after"], (int, float))
    assert error["retry_after"] > 0
    assert "concurren" in error["message"], (
        "the error must name the saturated family so the Act step can act "
        "on it, per tool-call-budgets"
    )


# ---------------------------------------------------------------------------
# P14: the downstream consequence of a mis-typed timeout, in the KGX export
# path. Formerly a deliberate omission of this gate.
# ---------------------------------------------------------------------------


def test_p14_a_slow_hop_over_https_still_writes_a_partial_kgx_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A slow hop degrades gracefully on the HTTPS transport, as on psycopg2.

    Added 2026-08-22 for finding F-4.11-09, and written to fail against the
    code as it stood before that fix. `export/traversal.py` catches
    `GraphTimeoutError` to mean "budget exhausted, stop and return what we
    have", and deliberately lets `GraphConnectionError` propagate as a hard
    transport failure that `export/cli.py` turns into an exit code with no
    output. The client's HTTP timeout equalled the service's own budget, so
    a genuinely slow query always tripped the client's read timeout first
    and arrived as `GraphConnectionError`. The transport swap therefore
    turned a graceful partial KGX export into a total failure, which is
    `.claude/rules/production-standards.md`'s degradation gate, defeated by
    the transport rather than by the export code.

    This arm drives the REAL dispatch: `GRAPH_QUERY_URL` is set, so
    `execute_cypher` goes over HTTP, and only the network seam `_post` is
    replaced. The seed lookup answers; every hop after it read-times-out.
    """
    import httpx

    import system_03_search_agent.tools.graph_http_transport as transport_module
    from system_03_search_agent.export.traversal import traverse_subgraph

    seed_row = (
        '{"id": 1, "label": "Gene", "properties": '
        '{"id": "' + TP53 + '", "name": "TP53"}}::vertex'
    )

    class _SeedResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, Any]:
            return {"rows": [{"n": seed_row}], "total_available": 1}

    calls: list[int] = []

    def _fake_post(**kwargs: Any) -> Any:
        calls.append(1)
        if len(calls) == 1:
            return _SeedResponse()
        raise httpx.ReadTimeout("the graph query service did not answer in time")

    monkeypatch.setenv("GRAPH_QUERY_URL", "https://example.invalid")
    monkeypatch.setenv(_TOKEN_VAR, "t")
    monkeypatch.setattr(transport_module, "_post", _fake_post)

    result = traverse_subgraph(
        [TP53], hops=1, edge_labels=("gene_associated_with_condition",)
    )

    assert result.seeds_resolved == [TP53], (
        "the traversal did not even keep the seed it had already collected"
    )
    assert result.truncated, "a hop that outran its budget was not recorded as a stop"
    assert len(calls) >= 2, "no hop query was issued; this arm proved nothing"


# ---------------------------------------------------------------------------
# P15, P16, P17: the audit trail and the pre-auth bound.
# ---------------------------------------------------------------------------


def test_p15_every_request_leaves_an_audit_record_whatever_its_outcome(
    service_client: Any, valid_token: str, caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The audit trail is COMPLETE across every outcome, not two of them.

    Added 2026-08-22 for finding F-4.11-J-03. F-4.11-03 found that TWO
    classes of call left no trace, a rejected credential and a rate-limited
    caller, and its fix added a log line for each. Only the auth half got
    an arm, so mutation M16, deleting the rate-limit log line, left both
    suites green. That is `.claude/skills/bossman-mode/SKILL.md`'s Rule 2
    failing in the smallest possible way: the fix enumerated instances of
    a category instead of naming the category.

    The category is not "auth and rate limiting". It is: EVERY request the
    service handles leaves a record, including the ones refused before the
    main logging step. So this arm asserts that as a universal over every
    outcome class the endpoint can produce, rather than over the two
    someone happened to think of. A new refusal path added without logging
    fails here the moment its outcome class is exercised.
    """
    import services.graph_query_service.app as app_module

    monkeypatch.setattr(
        app_module, "execute_cypher", lambda *a, **k: ([{"result": "stub"}], 1)
    )

    # The volume bound is switched OFF for this arm, deliberately, and the
    # reason is the whole distinction between this arm and P16. Audit
    # COMPLETENESS (does every outcome class have a logging path at all?)
    # and audit VOLUME (can a flood grow the journal without bound?) are
    # different properties that pull in opposite directions, and a single
    # arm testing both tests neither: with the bound on, several of the
    # outcomes below collapse into one emitted line and this arm reports a
    # missing logging path that is in fact present and working. So this arm
    # isolates completeness, P16 isolates the bound, and each fails for one
    # reason. The interval is read from the module global on every call
    # precisely so this separation is possible.
    monkeypatch.setattr(app_module, "REFUSAL_LOG_INTERVAL_SECONDS", 0.0)

    def _request(headers: dict[str, str], body: Any, raw: bool = False) -> None:
        if raw:
            service_client.post("/v1/cypher", content=body, headers=headers)
        else:
            service_client.post("/v1/cypher", json=body, headers=headers)

    outcomes: list[tuple[str, Any]] = [
        ("success", lambda: _request(_auth(valid_token), _payload())),
        ("auth_rejected", lambda: _request(_auth("wrong-credential"), _payload())),
        ("no_credential", lambda: _request({}, _payload())),
        (
            "malformed_json",
            lambda: _request(
                _auth(valid_token) | {"Content-Type": "application/json"},
                b"{not json",
                True,
            ),
        ),
        ("schema_violation", lambda: _request(_auth(valid_token), {"cypher": 1})),
        (
            "cypher_rejected",
            lambda: _request(
                _auth(valid_token),
                _payload(cypher="MATCH (g:Gene) DELETE g RETURN g"),
            ),
        ),
    ]

    for name, send in outcomes:
        caplog.clear()
        with caplog.at_level("INFO"):
            send()
        messages = [record.getMessage() for record in caplog.records]
        assert messages, (
            "outcome '" + name + "' left no audit record at all; Section 24 "
            "requires every call logged, and a log that is missing whole "
            "categories of call is clean rather than complete"
        )
        assert any("caller=" in message for message in messages), (
            "outcome '" + name + "' was logged without a caller identity"
        )
        assert all(valid_token not in message for message in messages)

    # The rate-limited outcome needs its own budget, so it is driven last
    # and separately rather than being folded into the loop above.
    caplog.clear()
    with caplog.at_level("INFO"):
        for _ in range(app_module.RATE_LIMIT_PER_MINUTE + 2):
            _request(_auth(valid_token), _payload())
    messages = [record.getMessage() for record in caplog.records]
    assert any("rate limited" in message for message in messages), (
        "a rate-limited caller left no audit record, which is exactly the "
        "half of the F-4.11-03 fix that shipped with no verify surface"
    )


def test_p16_a_flood_of_refusals_cannot_drive_unbounded_log_growth(
    service_client: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """Refusal logging is bounded, and nothing is silently lost.

    Added 2026-08-22 for findings F-4.11-J-05 and F-4.11-10. Since the
    F-4.11-03 fix every failed authentication writes a warning, and the
    box holding the graph was measured at 92 percent full. journald applies
    its own rate limiting and DROPS messages once a service exceeds its
    burst, so an unbounded refusal flood does not merely grow a file, it
    suppresses the INFO call records the audit trail exists to keep. That
    inverts the purpose of the fix that added the line.

    Bounding the request rate alone does not fix it, because the rejection
    of a bounded request is itself a log line. So the emitter is bounded
    too, per key and per event, and it carries the suppressed count forward
    rather than discarding it: the operator still learns that a credential
    is being guessed and how often, from a number of lines that does not
    grow with the attack.
    """
    from services.graph_query_service.app import SOURCE_RATE_LIMIT_PER_MINUTE

    attempts = SOURCE_RATE_LIMIT_PER_MINUTE + 40
    with caplog.at_level("WARNING"):
        for _ in range(attempts):
            service_client.post(
                "/v1/cypher", json=_payload(), headers=_auth("wrong-credential")
            )

    records = [r for r in caplog.records if "graph_query_service" in r.getMessage()]
    assert records, "a flood of refusals left no audit record at all"
    assert len(records) < attempts / 4, (
        "refusal logging grows one line per refused request: "
        + str(len(records))
        + " records for "
        + str(attempts)
        + " attempts"
    )
    assert any("suppressed=" in r.getMessage() for r in records), (
        "the suppressed count was never reported, so the bound loses the "
        "very signal an operator needs"
    )


def test_p17_the_unauthenticated_path_is_bounded_before_identity_is_known(
    service_client: Any,
) -> None:
    """A caller with no credential is bounded, not unlimited.

    Added 2026-08-22 for findings F-4.11-J-05 and F-4.11-10, reached
    independently by the judge and the adversary from separate briefs.
    Auth ran first and raised, so the rate limiter was never consulted for
    a failed credential, and the population the limiter bound was the one
    that needed it least: callers who already hold the credential.

    The ordering is the category. What must be bounded before identity is
    established is every request that reaches the endpoint, so the bound
    that runs first is keyed on the SOURCE rather than on a credential the
    caller may not have. The per-caller limit still exists behind auth and
    still binds an authenticated caller; this one binds everyone.
    """
    from services.graph_query_service.app import SOURCE_RATE_LIMIT_PER_MINUTE

    statuses = []
    for _ in range(SOURCE_RATE_LIMIT_PER_MINUTE + 5):
        statuses.append(
            service_client.post(
                "/v1/cypher", json=_payload(), headers=_auth("wrong-credential")
            ).status_code
        )

    assert 429 in statuses, (
        "an unauthenticated caller was never rate limited, so the "
        "unauthenticated path is unbounded"
    )
    last = service_client.post(
        "/v1/cypher", json=_payload(), headers=_auth("wrong-credential")
    )
    assert last.status_code == 429
    error = last.json()["error"]
    assert error["code"] == "rate_limited"
    assert isinstance(error["retry_after"], (int, float))
    assert error["retry_after"] > 0


# ---------------------------------------------------------------------------
# P18, P19: the unauthenticated surface.
# ---------------------------------------------------------------------------


def test_p18_every_auth_failure_returns_a_byte_identical_body(
    service_client: Any,
) -> None:
    """The auth failure path is uniform, which the docstring already claimed.

    Added 2026-08-22 for findings F-4.11-J-08 and F-4.11-10. The module
    docstring said a missing header, an empty bearer, a wrong scheme and a
    wrong value "all take the same path so the response cannot leak which
    kind of failure occurred", and the code returned two different
    messages, both of which are in the response body. A caller could tell
    "your credential is the wrong SHAPE" from "your credential is the
    wrong VALUE".

    `.claude/skills/bossman-mode/SKILL.md` says a comment claiming a
    security property is a claim to be tested or deleted. The claim was
    the better half here, so the code was made to hold it and this arm is
    the test. The bodies are compared byte for byte against each other
    rather than against a literal copied from the source, so the arm
    cannot go green by being updated alongside a change that reintroduces
    the oracle.
    """
    cases = {
        "no_header": {},
        "empty_bearer": {"Authorization": "Bearer "},
        "wrong_scheme": {"Authorization": "not-a-bearer-at-all"},
        "wrong_value": {"Authorization": "Bearer " + "z" * 40},
        "wrong_value_other_length": {"Authorization": "Bearer " + "q" * 9},
    }
    bodies: dict[str, str] = {}
    for case, headers in cases.items():
        response = service_client.post("/v1/cypher", json=_payload(), headers=headers)
        assert response.status_code == 401, "case " + case + " was not refused"
        bodies[case] = response.text

    distinct = set(bodies.values())
    assert len(distinct) == 1, (
        "auth failures return "
        + str(len(distinct))
        + " distinguishable bodies, so a caller can tell one kind of failure "
        "from another: "
        + str(sorted(bodies.items()))
    )


def test_p19_the_openapi_document_is_not_served_unauthenticated(
    service_client: Any,
) -> None:
    """Disabling the docs pages must also disable the schema they render.

    Added 2026-08-22 for findings F-4.11-J-07 and F-4.11-12. `docs_url` and
    `redoc_url` were set to None and `openapi_url` was left at its default,
    so `/openapi.json` answered 200 unauthenticated on the public internet
    and enumerated the endpoint inventory. The disclosure is small; the
    shape is not, and the shape is a control that looks complete and is
    not.
    """
    assert service_client.get("/openapi.json").status_code == 404
    assert service_client.get("/docs").status_code == 404
    assert service_client.get("/redoc").status_code == 404
    assert service_client.get("/healthz").status_code == 200


def test_p20_a_forwarded_client_address_is_trusted_only_from_the_local_proxy(
    monkeypatch: pytest.MonkeyPatch, configured_token: str
) -> None:
    """The rate-limit key and the audit identity get a real source component.

    Added 2026-08-22 for finding F-4.11-11. Behind Caddy the service's
    immediate peer is always loopback, so `request.client.host` was
    `127.0.0.1` for every caller on earth: the per-caller rate-limit key
    and the audit log's caller identity had no source component at all,
    and the log could never distinguish two sources.

    Reading a forwarded header is the fix and it is also how a rate-limit
    BYPASS gets built, so the header is honoured only when the immediate
    peer is the local proxy, and only its RIGHTMOST element is used, which
    is the value the proxy itself appended rather than anything the caller
    sent ahead of it. A caller that is not behind the proxy is identified
    by its own peer address and its header is ignored entirely.
    """
    from services.graph_query_service.app import client_source

    class _Client:
        def __init__(self, host: str) -> None:
            self.host = host

    class _Request:
        def __init__(self, host: str | None, forwarded: str | None) -> None:
            self.client = _Client(host) if host else None
            self.headers = {"x-forwarded-for": forwarded} if forwarded else {}

    assert client_source(_Request("127.0.0.1", "203.0.113.7")) == "203.0.113.7"
    assert client_source(_Request("::1", "203.0.113.7")) == "203.0.113.7"
    # Spoof ahead of the proxy's own appended value: the rightmost wins.
    assert (
        client_source(_Request("127.0.0.1", "198.51.100.9, 203.0.113.7"))
        == "203.0.113.7"
    )
    # Not the local proxy: the header is data, not identity.
    assert client_source(_Request("203.0.113.99", "127.0.0.1")) == "203.0.113.99"
    # Junk in the header falls back to the peer rather than becoming a key.
    assert client_source(_Request("127.0.0.1", "not-an-address")) == "127.0.0.1"
    assert client_source(_Request(None, None)) == "unknown"


# ---------------------------------------------------------------------------
# P21, P22: the client's budget against the service's, and the classification
# of a client-side timeout.
# ---------------------------------------------------------------------------


def test_p21_the_client_gives_the_service_time_to_answer_its_own_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The service's own timeout answer must be able to win the race.

    Added 2026-08-22 for findings F-4.11-09 and F-4.11-J-06. The client
    passed the SAME `timeout_s` to httpx that it sent the service as its
    budget, and the service needs that full duration plus TLS and HTTP
    overhead before it can emit its 504. So the client's read timeout fired
    first essentially every time and the service's `timeout -> 504 ->
    GraphTimeoutError` mapping was dead code in production.

    Two things are asserted, and the second is the one a comment cannot be
    trusted to carry: the read timeout the client actually passes exceeds
    the budget it sends, and the headroom constant exceeds the worst-case
    extra delay the SERVICE can add before answering. The two constants
    live in different modules, so the relationship between them is checked
    here rather than asserted in prose in either.
    """
    import system_03_search_agent.tools.graph_http_transport as t
    from services.graph_query_service.app import MAX_CONCURRENCY_WAIT_SECONDS

    seen: list[dict[str, Any]] = []

    class _Response:
        status_code = 200

        @staticmethod
        def json() -> dict[str, Any]:
            return {"rows": [], "total_available": 0}

    def _capture(**kwargs: Any) -> Any:
        seen.append(kwargs)
        return _Response()

    monkeypatch.setattr(t, "_post", _capture)
    monkeypatch.setenv("GRAPH_QUERY_URL", "https://example.invalid")
    monkeypatch.setenv(_TOKEN_VAR, "t")

    t.execute_cypher_over_http(
        cypher=CYPHER_VERTEX,
        params=None,
        row_limit=25,
        timeout_s=30.0,
        as_clause="(result agtype)",
    )

    assert seen, "the transport never posted; this arm proved nothing"
    assert seen[0]["json"]["timeout_s"] == 30.0, (
        "the budget sent to the service must stay the caller's budget"
    )
    read_timeout = seen[0]["timeout"].read
    assert read_timeout > 30.0, (
        "the client's read timeout equals or undercuts the budget it sent "
        "the service, so the service can never answer its own timeout"
    )
    assert t.CLIENT_TIMEOUT_HEADROOM_SECONDS > MAX_CONCURRENCY_WAIT_SECONDS, (
        "the client's headroom does not cover the longest the service can "
        "wait before it even starts a query, so a queued call still races "
        "the client's deadline"
    )


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        ("ReadTimeout", "GraphTimeoutError"),
        ("WriteTimeout", "GraphTimeoutError"),
        ("ConnectTimeout", "GraphConnectionError"),
        ("PoolTimeout", "GraphConnectionError"),
        ("ConnectError", "GraphConnectionError"),
    ],
)
def test_p22_a_client_side_timeout_is_classified_as_a_timeout(
    raised: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A budget burned at the client is still a budget burned.

    Added 2026-08-22 for findings F-4.11-09 and F-4.11-J-06. Every
    transport-level exception was classified as `GraphConnectionError`
    with "verify GRAPH_QUERY_URL is reachable and retry", so the one
    failure the Act step most needs to distinguish, a query that burned
    its whole budget, was presented as a connectivity blip worth retrying
    immediately. On psycopg2 the same query raised `GraphTimeoutError`.

    The split is by MEANING rather than by an enumerated list: a timeout
    that happened after the request reached an established connection is a
    budget timeout, and a timeout that means no connection was ever
    obtained is a connection failure. `ConnectError` is included here to
    pin that a plain connection failure did not accidentally move.
    """
    import httpx

    import system_03_search_agent.tools.graph_http_transport as t

    def _boom(**kwargs: Any) -> Any:
        raise getattr(httpx, raised)("simulated " + raised)

    monkeypatch.setattr(t, "_post", _boom)
    monkeypatch.setenv("GRAPH_QUERY_URL", "https://example.invalid")
    monkeypatch.setenv(_TOKEN_VAR, "t")

    with pytest.raises(getattr(t, expected)) as caught:
        t.execute_cypher_over_http(
            cypher=CYPHER_VERTEX,
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )
    assert str(caught.value)
    if expected == "GraphTimeoutError":
        assert not isinstance(caught.value, t.GraphConnectionError), (
            "a budget timeout must not also be a connection error, or "
            "export/traversal.py cannot tell them apart"
        )
