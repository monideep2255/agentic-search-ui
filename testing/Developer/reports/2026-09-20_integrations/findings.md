# Integrations page live verification, 2026-09-20

UI fix 11.30: every printed snippet on the Integrations page
(`https://search-agent-web-develop-2aeb.up.railway.app/integrations`)
executed as printed against develop
(`https://search-agent-api-develop-43b3.up.railway.app`), not merely
probed for reachability. Reachability of every surface was already
established separately (see the task brief): `/health`, `/openapi.json`
and `/docs` return 200, `/graphql` and `/v1/history` correctly return 401
unauthenticated, and `/mcp` returns 307. This report is about whether the
snippet PRINTED ON THE PAGE actually does what the page claims when run
as written.

Snippets were read directly from `frontend/src/components/screens/InfoScreens.tsx`
(`REST_EXAMPLE`, `GRAPHQL_EXAMPLE`, `MCP_CONFIG`, `CLI_EXAMPLE`,
`KGX_EXAMPLE`, `EVENT_STREAM_EXAMPLE`), which is exactly what the "Copy"
buttons on the page put on the clipboard. No snippet was retyped from
memory of what it should say.

Two throwaway credentials were minted for this check, by name only:

- A guest session token, minted from `POST /auth/guest`, used for the REST
  and SSE example (the Access section on the page says guest access is
  allowed there).
- A throwaway registered account, created with `POST /auth/signup` and
  exchanged for an access token with `POST /auth/login`, used for the
  GraphQL and MCP examples (the Access section says both require an
  account). No token value appears anywhere in this file or in any script
  output kept from this session.

## Results table

| Integration | What the page prints | What happened | Verdict |
|---|---|---|---|
| REST and SSE, "Copy curl" | `REST_EXAMPLE`: `curl -X POST $API/v1/query -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"text": "Which diseases are associated with BRCA1?", "session_id": "demo-1"}'` | Run once (a mutation, spends model budget). With `$TOKEN` substituted for a guest token: `HTTP 202`, a `run_id` returned. Subscribing to `/v1/query/{run_id}/events` produced a full stream ending in a `done` event with `trust_outcome: ask`, `total_tool_calls: 8`, five citations, a real synthesized answer. The snippet does exactly what the page claims. | WORKS |
| GraphQL, "Copy query" | `GRAPHQL_EXAMPLE`: `curl -X POST $API/graphql -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"query": "mutation { ask(input: { text: \"Which diseases are associated with BRCA1?\", sessionId: \"demo-1\" }) { answer citations { source sourceUrl } } }"}'` | Run once (a mutation). With `$TOKEN` substituted for the throwaway account's access token: `HTTP 200`, a real `answer` field with a full multi-paragraph cited answer (four disease records, gene, ClinVar, literature, clinical trial and publication citations) and a populated `citations` array. Matches the page's claim of one round trip returning the whole answer. | WORKS |
| MCP server, "Copy config" | `MCP_CONFIG`: `{"mcpServers": {"ncbi-search": {"url": "$API/mcp"}}}` | A POST to `$API/mcp` (no trailing slash, exactly the URL the config names) returns `HTTP 307` with `Location: http://search-agent-api-develop-43b3.up.railway.app/mcp/`. That Location header downgrades the scheme from https to plain http. Following it literally, over http, returns `HTTP 301` back to `https://.../mcp/`, and a 301 causes a compliant client to drop the POST body/method, which reproduces as a JSON-RPC parse error (`"Parse error: EOF while parsing a value"`) when curl follows both hops. The Python MCP SDK's own `streamable_http_client` (the same client this repo's own transport-security test suite uses), pointed at the printed URL and configured to follow redirects, never completes `initialize()`: it hangs until timeout, with and without an Authorization header, because the client is being handed off through an insecure hop mid-handshake. Hitting `$API/mcp/` directly (trailing slash, https, bypassing the broken redirect) works fine: `HTTP 200`, a valid `initialize` response naming the server. So the tool itself works; the URL printed in the copyable config does not, because of the broken 307. | BROKEN |
| Command line tools, "Copy command" | `CLI_EXAMPLE`: `s3 login` then `s3 ask "diseases linked to BRCA1"` | The `s3` console command (from `system3-cli`, build phase 4.2) is not installed in this environment: no `s3` on `PATH`, no `agentic-search-ui` package importable, no entry point in the project's `venv/bin`. There is no live client here to run the snippet against develop. | BLOCKED, no `s3` client installed in this environment |
| Command line tools, "Copy KGX command" | `KGX_EXAMPLE`: `s3-kgx-export NCBIGene:672 --hops 1 --output-dir ./kgx-out` | Same missing CLI as above; `s3-kgx-export` is the second console script from the same uninstalled package. | BLOCKED, no `s3-kgx-export` client installed in this environment |
| API documentation, "Copy frame" (event stream sample) | `EVENT_STREAM_EXAMPLE`: `id: 1` / `event: guard` / `data: {"type":"guard","version":"v1","trace_id":"7c1e2a","seq":1,"ts":"2026-09-13T09:00:00Z","payload":{"passed":true,"category":"ok","reason":null}}` | This is a sample frame, not a request, so it was checked for shape against a real stream rather than executed. The REST run above produced a live first frame: `id: 0` / `event: guard` / `data: {"type":"guard","version":"v1","trace_id":"<real trace id>","seq":0,"ts":"<real timestamp>","payload":{"passed":true,"category":"ok","reason":null}}`. Same field set, same nesting, same SSE framing (`id:`/`event:`/`data:`). The only differences are the example's illustrative values (a 6-character trace id, `seq`/`id` starting at 1 instead of 0), which is expected of a sample and not a defect. | WORKS |

## Counts

WORKS: 3 (REST and SSE, GraphQL, the event stream sample)
BROKEN: 1 (the MCP server config)
BLOCKED: 2 (both CLI commands, no client installed here)

## The single most important finding

The MCP server integration is broken exactly where nothing but literal
execution would catch it. Every reachability probe already run against
`/mcp` (a bare POST, a bare GET) reports the 307 and stops there, reading
it as "the documented redirect." Executed as a real client actually
would, following that redirect, the 307's `Location` header hands the
caller off from `https://` to plain `http://`, and the plain-http hop then
301s back to `https://` in a way that drops the POST body, so the
handshake never completes. The `mcp` Python SDK's own streamable HTTP
client, pointed at the exact URL printed in the page's copyable config,
never gets past `initialize()`, with or without a bearer token: it hangs
until timeout rather than erroring, which would read as a network problem
if nobody traced the redirect chain. The MCP tool itself is not the
defect: hitting `$API/mcp/` (trailing slash) directly over https works
immediately, 200, a valid `initialize` response. The one-line config the
page tells a user to paste into their MCP client is the thing that is
wrong, because it names the URL without the trailing slash and nothing
downstream of that URL can complete a handshake that starts by leaving
https.

## Constraints observed

No credential value was written to this file or to any script or log kept
from this session; credentials are referenced by name only ("a throwaway
develop account's access token", "a guest session token"). The Python and
frontend test suites were not run. Live requests were paced by hand, one
request at a time, with the two mutating snippets (REST and GraphQL) each
run exactly once. Nothing was committed or pushed. All working files from
this investigation (guest and account tokens, raw HTTP dumps, the MCP test
script) live under the session scratchpad, not under this repository.
