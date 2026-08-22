# Graph query service

The read-only HTTPS graph query service, build phase 4.11 (T-4.11-02). One
authenticated endpoint that fronts the Layer 1 AGE graph over HTTPS, so
`cypher_query` can reach the graph without an SSH tunnel. Full spec:
`requirements/Technical_specification.md` Section 24. Full phase context:
`tracker/phase_4.11.md`.

## What it is

A FastAPI application, `services/graph_query_service/app.py`, built by the
`build_app()` factory. It runs co-located with the graph's Postgres
instance, reaching it on localhost with the existing read-only `kg_reader`
role. It reuses this repository's own `cypher_validator.validate_cypher`
and `graph_connection.execute_cypher` rather than re-implementing either.

Deployment (the systemd unit, the reverse proxy, the runbook) is T-4.11-04,
a separate ticket, and is not covered here.

## Endpoints

`GET /healthz`

Unauthenticated. Returns `200 {"status": "ok"}`. Reveals nothing else, so a
reverse proxy or `tracker/preflight.py` can probe reachability without a
credential.

`POST /v1/cypher`

Authenticated with a bearer token (`Authorization: Bearer <token>`), read
from the `GRAPH_QUERY_TOKEN` environment variable and compared with
`hmac.compare_digest`.

Request body:

```json
{
  "cypher": "MATCH (g:Gene {id: $seed}) RETURN g.name",
  "params": {"seed": "NCBIGene:7157"},
  "row_limit": 25,
  "timeout_s": 30.0,
  "as_clause": "(result agtype)"
}
```

Extra fields are rejected.

Success response, `200`:

```json
{"rows": [{"result": "..."}], "total_available": 1}
```

Every cell is transmitted exactly as `execute_cypher` produced it: a
string stays a string, `None` stays `null`. See `app.py`'s module
docstring, "Wire encoding", for why this is the phase's central property.

Error response, every failure:

```json
{"error": {"code": "unauthorized", "message": "...", "retry_after": null}}
```

| Code | Status | Meaning |
|------|--------|---------|
| `unauthorized` | 401 | Missing, malformed, or wrong bearer credential |
| `invalid_payload` | 422 | Malformed body, or a field outside its sane band (see below) |
| `cypher_rejected` | 422 | `validate_cypher` rejected the query server-side |
| `rate_limited` | 429 | Caller exceeded `RATE_LIMIT_PER_MINUTE`; `retry_after` is set |
| `timeout` | 504 | The query exceeded its per-call timeout budget |
| `graph_unavailable` | 502 | The graph connection or the graph's own credential failed |
| `graph_wire_encoding` | 502 | The graph returned a value the wire contract forbids |

## The clamp-versus-reject boundary

`row_limit` has a sane band, `[1, MAX_ROW_LIMIT * 10]`. Inside the band but
above `MAX_ROW_LIMIT`, it is clamped down silently. Outside the band (the
motivating case is `row_limit=10_000_000`), it is rejected as
`invalid_payload` rather than clamped, because a value that far off is a
caller defect worth surfacing, not absorbing. `timeout_s` is clamped
unconditionally to `CYPHER_QUERY_TIMEOUT_SECONDS` with no reject band,
since an over-large requested timeout is not a structurally impossible
request the way an absurd row_limit is. Full reasoning in `app.py`'s
module docstring.

## Configuration this service reads

| Variable | Purpose |
|----------|---------|
| `GRAPH_QUERY_TOKEN` | The bearer credential every caller must present. Required, non-empty, or the service refuses to start |
| `GRAPH_QUERY_URL` | Must be UNSET in this service's own environment. This service reuses `execute_cypher`, which dispatches to the HTTP transport when this variable is set; setting it here would make the service call itself, so `build_app()` refuses to start if it is set |
| `GRAPH_PG_HOST`, `GRAPH_PG_PORT`, `GRAPH_PG_USER`, `GRAPH_PG_PASSWORD`, `GRAPH_PG_DBNAME` | Read by `execute_cypher`'s default connection factory, since this service runs with `GRAPH_QUERY_URL` unset and therefore always takes the psycopg2 path against the graph's own localhost Postgres |

## Running it locally for development or tests

```bash
export GRAPH_QUERY_TOKEN=dev-token-not-a-real-secret
export GRAPH_PG_HOST=127.0.0.1
export GRAPH_PG_PORT=5432
export GRAPH_PG_USER=kg_reader
export GRAPH_PG_PASSWORD=...
export GRAPH_PG_DBNAME=...
./venv/bin/uvicorn services.graph_query_service.app:build_app --factory --host 127.0.0.1 --port 8080
```

Tests under `tests/services/graph_query_service/` use a fake
`execute_cypher` and do not require a live graph. The premise gate,
`tests/system_03_search_agent/tools/test_graph_query_service_premise.py`,
covers the live half and needs `RUN_PREMISE_GATE=1` plus a reachable graph
or deployed service.
