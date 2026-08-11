# Phase 4.1: outbound-only MCP server wrapping the same tool functions

Build phase 4.1 exposes System 3 outward to persona 11 (AI agents and MCP or LLM consumers) via a System 3-authored MCP server, wrapping the same core `run()` loop build phase 4.0 finalized behind `adapters/web_sse/`, never the seven internal tools directly and never a new parallel auth system.

Depends on: build phase 3.4 (done, PR #28, merged). Also draws on build phase 4.0 (done, PR #39, merged), since it wraps the same `RunRegistry`/`run_streaming` core that phase finalized, though Section 25 names only 3.4 as the hard dependency.
Branch: `phase/4.1-mcp-server`
Spec: `requirements/Technical_specification.md` Section 13.2 (the MCP server, outbound-only), Section 9.1 (`CitationPayload`, referenced not restated), Section 13.5 (per-surface summary table), Decision 24 and the 2026-07-22 Step 2.3-to-Phase-4 decision (direct Python tools, no inbound MCP; MCP is outbound delivery only)
Reference: `docs/build/Build_workflow_cadence.md`, `LEARNINGS.md` (zero entries in this phase's territory as of open: searched "mcp server", "api key", "outbound", "scoped credential", zero hits)

## New dependency, approved before this phase opened

The official `mcp` Python SDK (PyPI: `mcp`, latest `2.0.0`, MIT license, maintained by the Model Context Protocol project under LF Projects LLC, repo `github.com/modelcontextprotocol/python-sdk`). Supply-chain check run 2026-08-11 before any code: no compromise reports, no postinstall/setup.py execution risk (wheel-only), long actively-maintained version history (0.9.1 through 2.0.0), maintainer emails resolve to the project's own Anthropic-affiliated engineers. Product owner approved adding it floor-pinned (`mcp>=2.0`) matching this repo's existing convention for the rest of the stack, per `.claude/rules/ai-security-standards.md`'s "ask before adding a new dependency" gate, which stays active in bossman mode.

## Phase premise (the done-when)

An MCP client holding a valid bearer token for its own dedicated User account calls the single advertised tool, `ask_biomedical_question`, with a real biomedical question. It receives one JSON result, never a stream: no `think`, `plan`, or `tool_start` event ever reaches it, and the internal `token`/`tool_result`/`citation`/`trust_signal` events are folded into a final `answer`, `citations`, `trust_signal`, `run_id` shape matching Section 13.2's locked schema exactly, `CitationV1` read verbatim off `contracts/events.py`'s existing `CitationPayload` (Section 9.1's provenance type, not a redefinition). A query with no groundable answer gets the honest refusal string in `answer` with no fabricated citations, the identical cite-or-refuse behavior every other surface already gets, not a weaker or different rule for this one. No response the MCP surface ever returns, for any caller, in any role, carries a cost field: `operator_mode` is hard-pinned false for this surface regardless of `is_operator_user`, which is a different, stronger rule than every other adapter's role-derived filtering. A caller with a missing, malformed, or invalid bearer token never reaches the core loop at all: no run is created, no model or tool budget is spent, and the caller gets a protocol-level auth failure, not a silent empty or malformed result. `list_tools()` advertises exactly one tool; no internal tool (`cypher_query`, `ncbi_efetch`, `ncbi_dbsnp`, `pubtator_annotate`, `litvar2_lookup`, `pathogen_detection`, `clinicaltrials_search`) is ever reachable as a separate MCP tool, closing the raw-passthrough risk Section 13.2 names explicitly.

The verify surface is `tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py`, not a suite total, per `tracker/phase_3.1.md`'s standing rule.

## Scope boundary, decided rather than asked (v1-scope-boundary check)

Section 13.2 states an MCP client "gets its own cost-cap and rate-limit bucket tracked the same way as any REST API key." This repo has no first-class "API key" entity anywhere today (confirmed by pre-build read below): every surface authenticates via a bearer JWT that decodes to a `User` row, and every cost cap (`check_per_query_cap`, `check_user_daily_query_cap`, `check_system_daily_cost_cap`) already keys off `trace_id` or `user_id`, never a key-shaped identity. Building a new API-key-as-entity system to satisfy this line literally would be new architecture invented mid-phase, exactly what `.claude/rules/v1-scope-boundary.md` exists to stop, and it is not named as a fast-follow trigger anywhere. Read plainly instead: an MCP client's "own scoped API key" is a dedicated `User` account provisioned for that client, authenticating with the same bearer-JWT mechanism every other surface already uses. The existing per-user daily cap and per-query cap then apply automatically, with zero new mechanism, because they already key off `user_id`. This is the same "wraps the one core's contract, not around it" reading Section 13.2 itself states for the tool surface, applied here to auth. Flagged rather than silently substituted, per the rule's own instructions.

## Pre-build source read (done before any code, before any ticket)

Per `.claude/rules/attack-the-constraint.md` and this repo's standing pre-build-probe pattern (phases 3.2/3.3/3.5/4.0), every file this phase touches or wraps was read before scoping tickets, and the actual installed `mcp==2.0.0` SDK source was read directly rather than trusted from memory or from `context7`'s docs (which only index up to SDK `v1.12.4`, a version behind and, per the module rename found below, API-incompatible in import path).

| Read | Finding |
|------|---------|
| `adapters/web_sse/app.py` | `POST /v1/query` (line 170) calls `default_registry.create_run(query, context, run_id=run_id)`; `RequestContext` is built at line 169 with `surface="rest_sse"`; the authenticated user comes from `Depends(get_current_user)` (line 159); `is_operator_user(str(current_user.id))` is called at line 277 |
| `core/run_registry.py` | `async def subscribe(self, run_id, *, after_seq=-1) -> AsyncIterator[Event]` (line 462) yields every `Event` with `seq > after_seq` and stops on `event.type == "done"` or a fatal `error` (lines 512-515). This is the exact interface to await-until-done with no SSE framing: iterate it and stop at the terminal event |
| `core/run.py` | `async def run_streaming(query, context) -> AsyncIterator[Event]` (line 191) is the underlying generator `create_run`'s background task drives; not called directly by this phase, `RunRegistry` already owns the lifecycle |
| `contracts/query.py` | `RequestContext` (lines 65-86) carries exactly `surface: Literal["web_ui", "rest_sse", "mcp", "cli"]`, `session_memory`, `operator_mode: bool = False`. `"mcp"` is already a legal literal value, added in an earlier phase, unused until now. `query`, `audience_depth`, `session_id` live on `Query` (lines 21-63), not `RequestContext` |
| `contracts/events.py` | `CitationPayload` (lines 135-151) already carries every field Section 13.2's `CitationV1` names: `source`, `source_id`, `source_url` (host-pinned pattern), `layer`, `evidence_kind`, `assertion_confidence`, `population_ancestry_context`, `license`, plus `citation_id`, `display_index`, `field`, `claim_text`. Reused verbatim, never redefined. `DonePayload` (lines 224-230) carries `total_cost_usd`, the exact field this phase must never let reach an MCP response |
| `auth/dependencies.py` | `get_current_user(authorization: str \| None = Header(...), session=Depends(get_session)) -> User` (line 34) parses `"Bearer <token>"` (lines 46-50), decodes via `decode_access_token(token)` (line 52), looks up the `User` row (line 61). No API-key entity exists; confirms the scope-boundary reading above. `get_current_user` is a FastAPI-DI function, not directly callable from an MCP `Context`; its inner decode-then-lookup logic is what this phase's auth ticket reuses, not the DI wrapper itself |
| `harness/cost_control.py` | `is_operator_user(user_id)` (line 502) checks the `OPERATOR_USER_IDS` env allowlist. `check_per_query_cap` keys on `trace_id`; `check_user_daily_query_cap` and `check_system_daily_cost_cap` key on `user_id` via the `interactions` table. None key on an API key, confirming no per-key bucket exists to plug into even if this phase wanted one |
| `mcp==2.0.0` SDK, read from the actual downloaded wheel, not `context7` (indexed only to `v1.12.4`, a different import path) | `MCPServer` (`mcp/server/mcpserver/server.py:147`), not `FastMCP`, the pre-2.0 name. `@server.tool(...)` (`server.py:621`) and `add_tool` derive both input and output JSON Schema from the tool function's Python type hints and Pydantic return annotation via `func_metadata()`; there is no `input_schema=`/`output_schema=` literal-dict parameter. `MCPServer.streamable_http_app(stateless_http=True, ...)` (`server.py:1218`) returns a plain `starlette.applications.Starlette` app, mountable in FastAPI via `app.mount("/mcp", ...)`. A `Context` parameter injected into a tool function (detected by type annotation, `mcpserver/utilities/context_injection.py:13-46`) exposes `ctx.headers` (`mcpserver/context.py:277-285`), a read-only view of the incoming HTTP request's headers, explicitly documented as "client-supplied input, never treat one as an identity assertion". The SDK's own `auth=`/`token_verifier=`/`auth_server_provider=` OAuth machinery is entirely optional and untouched if `auth=None` is never passed to `MCPServer.__init__` (`server.py:236-242`); this phase leaves it unset and does its own auth inside the tool handler by reading `ctx.headers.get("authorization")`. `mcp.shared.exceptions.MCPError` re-raised from a tool body becomes a top-level JSON-RPC protocol error (`tools/base.py:173-179`), the right vehicle for a hard auth failure; any other exception is caught and returned as a normal `CallToolResult(is_error=True, ...)`, never a crashed transport (`server.py:423-424`) |
| `tests/system_03_search_agent/adapters/web_sse/test_phase_4_0_premise.py` | Established in-process test pattern: `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` against the real FastAPI app, no mocked transport. This phase's premise gate reuses the same pattern against the mounted MCP Starlette sub-app, driven by the real `mcp` client SDK (`mcp.client.streamable_http`), not a hand-rolled JSON-RPC payload |

## Ticket map

| Ticket | Slice | Files | Status |
|--------|-------|-------|--------|
| T-4.1-01 | The premise gate, blocking | `tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py` (new), `tests/system_03_search_agent/adapters/mcp/test_phase_4_1_production_mount.py` (new) | in-review |
| T-4.1-02 | `adapters/mcp/server.py`: `MCPServer` instantiation, `ask_biomedical_question` registered via `@server.tool(...)` against Pydantic input/output models that literally encode Section 13.2's locked schema (`Field(..., max_length=2000)` on `query`, the three-value `audience_depth` enum, `max_length=64` on `session_id` and `run_id`, `max_length=8000` on `answer`, `max_length=50` on `citations` using `contracts.events.CitationPayload` verbatim, `trust_signal` as a plain object, all four output fields required); the fold loop that iterates `RunRegistry.subscribe(run_id, after_seq=-1)` to the terminal event, discarding `think`/`plan`/`tool_start`, and assembling the final response from `token`/`tool_result`/`citation`/`trust_signal`/`done`; `streamable_http_app(stateless_http=True)` mounted into the existing FastAPI app at `/mcp` | `src/system_03_search_agent/adapters/mcp/server.py` (new), `src/system_03_search_agent/adapters/mcp/__init__.py` (new), `src/system_03_search_agent/adapters/web_sse/app.py` (mount only) | done |
| T-4.1-03 | Auth: a `Context`-parameter tool handler reads `ctx.headers.get("authorization")`, strips the `Bearer ` prefix, and resolves a `User` via the SAME decode-then-lookup logic `auth/dependencies.py`'s `get_current_user` already uses (extracted into a small callable both the FastAPI dependency and this handler call, not duplicated). Missing, malformed, or invalid token raises `MCPError` before `create_run` is ever called, so no run and no budget is spent. `RequestContext(surface="mcp", operator_mode=False)` is constructed with `operator_mode` hard-set `False` in code, never derived from `is_operator_user`, so no MCP response can ever carry a cost field regardless of the authenticated account's allowlist status | `src/system_03_search_agent/adapters/mcp/server.py`, `src/system_03_search_agent/auth/dependencies.py` (extract the decode-then-lookup helper, no behavior change to the existing FastAPI dependency) | done |
| T-4.1-04 | Dependency and wiring: add `mcp>=2.0` to `requirements.txt` and `pyproject.toml`; log the dependency-addition and the API-key-as-User-account scope-boundary reading to `DECISIONS.md`; confirm `list_tools()` advertises exactly one tool with no internal tool ever separately reachable | `requirements.txt`, `pyproject.toml`, `DECISIONS.md` | done |

Depends-on chain: T-4.1-01 blocks everything (written and watched failing first, committed on its own before any implementation, per the corrected process F-4.0-J-02 named for future phases). T-4.1-02 is the foundation; T-4.1-03 depends on it (the tool handler it adds auth to). T-4.1-04 depends on nothing but T-4.1-01, can land alongside T-4.1-02.

Dispatch plan: single-builder sub-agent, not an agent team. tmux is not available this session (checked, `tmux: ok` but not running inside one), and the work does not decompose into independent, non-overlapping pieces regardless: the fold loop, the schema models, and the auth handler all live in the same new small module and are tightly coupled by construction. Splitting this across parallel builders would create exactly the kind of overlapping-write collision `plan-then-fan-out.md` and the worktree-isolation policy exist to prevent, for no speed benefit, since there is nothing to parallelize.

## Premise gate design

Written and watched failing before `adapters/mcp/server.py` exists, per LEARNINGS.md row 43's discipline (every failure `ModuleNotFoundError`, never a network fault or a fixture bug), and per F-4.0-J-02's corrected process: the gate lands in its own commit, its failing run's real output gets pasted into this file, and only then does implementation start.

### The arms (planned)

| Arm | Cases | What it pins |
|-----|-------|---------------|
| Golden path | A real biomedical question (reusing one of the seven v1 must-pass moat questions) through a real `mcp` client session against the mounted Starlette app; assert non-empty `answer`, at least one well-formed `citations` entry matching `CitationPayload`'s shape, a present `trust_signal`, a present `run_id` | The request/response fold actually produces a grounded answer end to end |
| Refusal path | A query engineered to return zero groundable results; assert the honest refusal string in `answer`, no fabricated citations, same cite-or-refuse rule every other surface already enforces (production-standards' AI answer grounding gate), not a weaker MCP-specific rule | This surface never becomes a second, laxer path to a confident wrong answer |
| Event folding | Assert the folded response schema structurally has no field for `think`/`plan`/`tool_start`/`token`/`tool_result`, and that a run which does emit them completes without the fold loop hanging or crashing | Section 13.2's fold rule is a structural guarantee, not a hope |
| Never-cost | A caller authenticated as a `User` on the `OPERATOR_USER_IDS` allowlist still gets a response with no cost-shaped field anywhere, proving `operator_mode` is hard-pinned false for this surface and not merely defaulted false | The stronger, surface-level rule Section 13.2 states, distinct from every other adapter's role-derived filtering |
| Auth, missing token | No `Authorization` header: `MCPError`, no run created (assert via a spy/count on `RunRegistry.create_run` or an equivalent observable), no budget spent | The auth boundary fails closed before any cost is incurred |
| Auth, invalid token | A malformed or expired bearer token: same as above | Closes the "garbage token silently becomes an anonymous run" gap |
| Auth, valid token | A real test `User`'s valid bearer token succeeds and the resulting run's owner matches that user | Confirms the reused decode-then-lookup path actually works, not just that it rejects |
| Tool surface | `list_tools()` returns exactly one tool named `ask_biomedical_question`; none of the seven internal tool names are ever separately advertised or callable | Closes the raw-passthrough risk Section 13.2 names by name |
| Schema fidelity | The tool's advertised `input_schema`/`output_schema` (as `list_tools()` reports them, derived by the SDK from the Pydantic models) match Section 13.2's locked field list and constraints: `query` maxLength 2000 required, `audience_depth` three-value enum, `session_id` maxLength 64, `answer` maxLength 8000, `citations` maxItems 50, `trust_signal` object, `run_id` maxLength 64, all four output fields required | The locked spec schema is what ships, not an approximation the SDK happened to infer |

Not covered by this gate, stated per `.claude/rules/goal-contracts.md`'s coverage-declaration discipline: real interop against an external MCP host (Claude Desktop or another live MCP client), since that needs a live external tool this environment cannot drive; true multi-process behavior and load-scale concurrency across many simultaneous MCP clients, which is build phase 6.0's named rate-limiting and concurrency territory, the same carve-out build phase 4.0 already used for its own load-scale exclusion; and the OAuth 2.0/OIDC alignment the Step 6.2 new-intake note flags as a future direction, since this phase deliberately keeps the SDK's own OAuth provider machinery unwired in favor of reusing the existing bearer-JWT mechanism (see the scope-boundary note above).

## Premise gate, failing-first

`tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py` landed alone, before `adapters/mcp/server.py` existed, commit `3014dae` ("test(mcp-server): add the phase 4.1 premise gate, watched failing first"). Every arm from the design table above is present: `TestToolSurface` (2 cases plus a callability check), `TestSchemaFidelity` (2 cases), `TestGoldenPath`, `TestRefusalPath`, `TestEventFolding`, `TestNeverCost`, `TestAuth` (4 cases: missing, malformed, invalid, valid token).

An early draft imported the not-yet-existing module only inside `TestToolSurface`/`TestSchemaFidelity`, while the HTTP-driven classes (`TestGoldenPath` and the rest) imported the already-existing `adapters/web_sse/app.py` at module level and only failed once they actually tried to reach `/mcp`. Against the pre-implementation baseline that surfaced as `mcp.shared.exceptions.MCPError: Not Found` (an HTTP 404 through the not-yet-mounted app), a real and accurate signal that the endpoint does not exist, but not the uniform `ModuleNotFoundError` LEARNINGS.md row 43 requires, and shaped exactly like the "network fault" the discipline exists to rule out. Fixed with an autouse fixture (`_require_mcp_server_module`) that explicitly imports `system_03_search_agent.adapters.mcp.server` before every test in the file, so every case fails the same way regardless of which path it exercises.

Real run, against the corrected test file, before any implementation existed:

```text
$ pytest tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py -v
============================= test session starts ==============================
platform darwin -- Python 3.11.6, pytest-9.1.1, pluggy-1.6.0
plugins: cov-7.1.0, asyncio-1.4.0, anyio-4.14.2, langsmith-0.10.10
collected 13 items

TestToolSurface::test_exactly_one_tool_is_advertised ERROR                 [  7%]
TestToolSurface::test_no_internal_tool_name_is_separately_advertised ERROR [ 15%]
TestToolSurface::test_no_internal_tool_is_separately_callable ERROR        [ 23%]
TestSchemaFidelity::test_input_schema_matches_section_13_2 ERROR           [ 30%]
TestSchemaFidelity::test_output_schema_matches_section_13_2 ERROR          [ 38%]
TestGoldenPath::test_a_real_question_returns_a_grounded_cited_answer ERROR [ 46%]
TestRefusalPath::test_a_zero_groundable_result_query_refuses_honestly ERROR[ 53%]
TestEventFolding::test_folded_response_has_no_field_for_excluded_event_types ERROR [ 61%]
TestNeverCost::test_an_operator_allowlisted_caller_still_gets_no_cost_field ERROR  [ 69%]
TestAuth::test_missing_token_is_rejected_before_any_run_is_created ERROR   [ 76%]
TestAuth::test_malformed_token_is_rejected_before_any_run_is_created ERROR [ 84%]
TestAuth::test_invalid_token_is_rejected_before_any_run_is_created ERROR   [ 92%]
TestAuth::test_a_valid_token_succeeds_and_the_run_is_owned_by_that_user ERROR [100%]

==================================== ERRORS ====================================
____ ERROR at setup of TestToolSurface.test_exactly_one_tool_is_advertised _____
    @pytest.fixture(autouse=True)
    def _require_mcp_server_module() -> None:
        ...
>       import system_03_search_agent.adapters.mcp.server  # noqa: F401
E       ModuleNotFoundError: No module named 'system_03_search_agent.adapters.mcp.server'

tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py:383: ModuleNotFoundError

[... the same ModuleNotFoundError, from the same fixture, repeats for all 13 cases ...]

=========================== short test summary info ============================
ERROR (x13), same ModuleNotFoundError each time
============================== 13 errors in 4.43s ==============================
```

13 of 13 cases failed, every failure `ModuleNotFoundError: No module named 'system_03_search_agent.adapters.mcp.server'` raised from the same autouse fixture, zero passes, zero network faults, zero fixture bugs. The `search_agent_users` PostgreSQL database was reachable this run, so the HTTP-driven classes were not skipped; they failed via the same import guard before ever attempting a request. Implementation started only after this run.

### Final passing run, after implementation (commits `631ab7a`, `699cd4c`, `6665428`, `d666066`, `dccb4d0`)

Getting from 13/13 failing to 13/13 passing needed two intermediate fix rounds against the real implementation, each a genuine defect in the mount recipe or the test harness, not a premise-gate mistake: the mount needed `streamable_http_path="/"` plus an explicit `lifespan=` wiring (6 of 13 cases failed with `RuntimeError: Task group is not initialized` before this), and the test harness needed a fresh mounted app per call plus `except* MCPError` to unwrap `anyio`'s `BaseExceptionGroup` wrapping (7 of 13 cases failed for these two reasons after the mount fix). Full account of all five findings: `LEARNINGS.md`'s two 2026-08-11 entries under "Mounting the mcp==2.0.0 SDK's streamable_http_app into FastAPI silently fails three separate ways" and "Testing the mounted MCP endpoint needed two more non-obvious accommodations".

```text
$ pytest tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py -v
============================= test session starts ==============================
collected 13 items

TestToolSurface::test_exactly_one_tool_is_advertised PASSED                [  7%]
TestToolSurface::test_no_internal_tool_name_is_separately_advertised PASSED[ 15%]
TestToolSurface::test_no_internal_tool_is_separately_callable PASSED       [ 23%]
TestSchemaFidelity::test_input_schema_matches_section_13_2 PASSED          [ 30%]
TestSchemaFidelity::test_output_schema_matches_section_13_2 PASSED         [ 38%]
TestGoldenPath::test_a_real_question_returns_a_grounded_cited_answer PASSED[ 46%]
TestRefusalPath::test_a_zero_groundable_result_query_refuses_honestly PASSED [ 53%]
TestEventFolding::test_folded_response_has_no_field_for_excluded_event_types PASSED [ 61%]
TestNeverCost::test_an_operator_allowlisted_caller_still_gets_no_cost_field PASSED  [ 69%]
TestAuth::test_missing_token_is_rejected_before_any_run_is_created PASSED  [ 76%]
TestAuth::test_malformed_token_is_rejected_before_any_run_is_created PASSED[ 84%]
TestAuth::test_invalid_token_is_rejected_before_any_run_is_created PASSED  [ 92%]
TestAuth::test_a_valid_token_succeeds_and_the_run_is_owned_by_that_user PASSED [100%]

============================== 13 passed in 8.78s ==============================
```

Full repo suite (`pytest -q` from repo root): `6 failed, 2410 passed, 113 skipped, 1 xfailed in 66.00s`. The 6 failures are the exact same pre-existing, live-network-opt-in-gated set named in `requirements/phase_6/Continuation_prompt.md` (`test_citation_trust_full_premise.py`, every one a `LiveHttpCallInUnitSuiteError`), confirmed not a regression: develop's baseline is 2397 passing plus 113 skipped plus 1 xfailed plus 6 failed (2517 total); this run adds exactly the 13 new premise-gate tests (2410 = 2397 + 13) with the skip/xfail/fail counts unchanged. `ruff check` is clean on every file this phase touched or created.

## Findings

Judge round 1, verdict FAIL, ran against `62d4e76` (the full branch, `develop..HEAD`). One blocking, three non-blocking. Every finding this round is a verify-surface or dependency-hygiene defect. No shipped-behavior defect was found: every clause of Section 13.2's locked schema, the auth boundary, the hard-pinned `operator_mode`, and the single-tool surface were each independently re-verified against the running code and hold.

| Finding | Severity | Status | Description |
| --- | --- | --- | --- |
| F-4.1-J-01 | BLOCKING (major) | fix applied, awaiting judge re-verification | Two of the premise gate's nine declared arms contain an assertion that cannot fail. `TestEventFolding` (line 642) and `TestNeverCost` (line 667) each end with `assert excluded_key not in _find_all(content, excluded_key)`. `_find_all(fragment, key)` returns the list of VALUES found under `key`, so the assertion compares a key NAME against a list of values and is true for every possible input, including a response that does leak the key. Demonstrated by the judge against the test file's own helper, verbatim: a response containing `{"citations": [{"total_cost_usd": 0.99}], "trust_signal": {"think": "internal reasoning leaked"}}` yields `_find_all(content, "total_cost_usd") -> [0.99]` and `_find_all(content, "think") -> ['internal reasoning leaked']`, and both assertions evaluate `True`, so both leaks pass undetected. The correct form is `assert _find_all(content, excluded_key) == []`. What still holds: the preceding `assert set(content.keys()) == {"answer", "citations", "trust_signal", "run_id"}` in both tests is real and does catch a TOP-LEVEL leak, and the underlying properties are genuinely true, independently confirmed by the judge inspecting the whole output model tree (`AskBiomedicalQuestionOutput`, `CitationPayload`, `TrustSignalPayload` carry zero fields matching `cost` or `cap`, and `_fold_run_to_response` never reads a cost-shaped field from any event). So this is a gate-integrity defect, not a product defect. It is nonetheless blocking, because the nested arm is precisely the half that would catch a cost or internal-event field hidden one level down inside `trust_signal` or a citation, which is the only place either could realistically hide once the top-level key set is pinned, and `.claude/rules/self-eval-loop.md` names a docstring asserting a property over an assertion that does not test it as the exact liability pattern: `TestNeverCost`'s own docstring claims it is "proving the pin, not merely a default", and no assertion in it distinguishes the pinned case from the defaulted one |
| F-4.1-J-02 | moderate | fix applied, awaiting judge re-verification | The production mount is exercised by zero tests. `adapters/web_sse/app.py`'s `_mcp_asgi_app`, its `_lifespan`, and `app.mount("/mcp", _mcp_asgi_app)` are never driven by any test in the repo: `grep -rn '/mcp' tests/` outside the premise gate returns nothing, and the gate's `_build_test_mcp_app()` (line 305) builds a fresh FastAPI wrapper that HAND-COPIES the production recipe rather than importing it. The reason for a fresh app per call is legitimate and correctly documented (`StreamableHTTPSessionManager.run()` is one-shot per instance), but the consequence is that the shipped mount is an unverified duplicate of a verified one, free to drift, and this file's own LEARNINGS entry records that this exact recipe already failed three separate silent ways. A test asserting the production `app`'s route table actually contains a `Mount` at `/mcp` whose sub-app routes at `/`, and that `app.router.lifespan_context` is not FastAPI's default, would close it without re-entering the one-shot lifespan |
| F-4.1-J-03 | moderate | fix applied, awaiting judge re-verification | Four defensive branches of `adapters/mcp/server.py` are entirely uncovered, and they are the branches that carry the phase premise's "all four output fields required" clause for the run shapes that never reach `write_node`. Judge-run coverage over the premise gate: `84%`, `Missing 141, 183-191, 239-241, 249-250, 261`. Line by line: 141 is the `headers is None` path; 183-191 is the whole body of `_fallback_answer_text`; 239-241 is the fatal-`error` capture; 249-250 is the synthetic answer-scope `trust_signal` fallback; 261 is the empty-answer path that invokes the fallback. Both stream fixtures (`_golden_path_stream`, `_refusal_path_stream`) emit a `token` and an answer-scope `trust_signal`, so neither fallback can ever fire. Two consequences. First, the phase's own DECISIONS.md entry justifying the synthetic trust signal names three real run shapes (`_decline_for_guardrail`, `_decline_for_daily_cap`, `write_node`'s `no_tool` branch) and no test drives any of them through the fold. Second, `_fallback_answer_text` introduces MCP-specific refusal wording, and the phase premise explicitly forbids "a weaker or different rule for this one" surface; the wording may well be correct, but it is neither tested nor compared against what any other surface renders for the same run shape |
| F-4.1-J-04 | minor | fix applied, awaiting judge re-verification | Two packages are imported directly by shipped code and by the gate but declared nowhere. `src/system_03_search_agent/adapters/mcp/server.py:77` does `from mcp_types import INVALID_REQUEST`, and the premise gate does `import httpx2` (line 76) and `from mcp_types import CallToolResult` (line 83). Neither `mcp-types` nor `httpx2` appears in `requirements.txt` or `pyproject.toml`; both arrive only as transitive dependencies of `mcp`. Verified: `pip show mcp-types` reports version `2.0.0`, MIT, same publisher, `Required-by: mcp`. Low real risk given identical publisher and lockstep version, but a direct import of an undeclared package is a reproducibility gap under `production-standards.md`'s supply-chain gate: nothing in this repo's own dependency declaration would stop a future `mcp` release from restructuring or dropping either package, and the failure would surface as an `ImportError` in shipped code, not in a dependency resolver |

## Fix round, 2026-08-11

Fixes all four findings from judge round 1. Not the judge: this round applies fixes and self-verifies, then hands back for a fresh judge pass. No finding below is marked `closed`; only the judge closes a finding, per this repo's ticket-status convention, so every one is left `fix applied, awaiting judge re-verification` in the Findings table above. T-4.1-01 is moved back to `in-review`, never `done`, for the same reason. T-4.1-02, T-4.1-03, and T-4.1-04, which the judge already marked `done`, were not touched except where F-4.1-J-02/J-03 required new test coverage against them; no production code in `adapters/mcp/server.py` changed at all this round, only its test coverage.

F-4.1-J-01 (BLOCKING): rewrote both vacuous assertions in `test_phase_4_1_premise.py` (`TestEventFolding` and `TestNeverCost`) from `assert excluded_key not in _find_all(content, excluded_key)` to `assert _find_all(content, excluded_key) == []`, per the judge's own diagnosis and suggested fix. Verified the fix actually catches a leak, not just that it reads differently: reconstructed the judge's exact adversarial payload (`{"citations": [{"total_cost_usd": 0.99}], "trust_signal": {"think": "internal reasoning leaked"}}`) in a standalone scratch script and ran both the old and the new assertion logic against it. The old form evaluated `True` (vacuously passing) for both `total_cost_usd` and `think`; the new form evaluated `False` (correctly failing) for both. Then ran the new form against a real, clean golden-path-shaped response and confirmed every excluded key still evaluates `True` (no false positives). Full scratch script output:

```text
=== Adversarial payload (should be caught as a leak) ===
key='total_cost_usd' old_broken_assert_passes=True new_fixed_assert_passes=False
key='think' old_broken_assert_passes=True new_fixed_assert_passes=False

=== Real non-leaking golden-path-shaped response (should pass) ===
key='think' new_fixed_assert_passes=True
[... every excluded key True ...]

All checks passed: the corrected assertion catches the judge's leak and still passes on genuinely clean output.
```

Then ran the real premise gate against the real implementation: both corrected tests still pass, confirming (as the judge's own investigation already established) that the underlying properties are genuinely true in `server.py` today, only the gate's ability to detect a violation was broken.

F-4.1-J-02 (moderate): added a new file, `tests/system_03_search_agent/adapters/mcp/test_phase_4_1_production_mount.py`, that drives one real `mcp` client call through the REAL, module-level `app` singleton from `adapters/web_sse/app.py` (not `_build_test_mcp_app()`'s hand-copied rebuild), entering that singleton's own `_lifespan` directly via `app.router.lifespan_context(app)`. This is the full end-to-end option the finding named as preferred over the route-table-only fallback, made possible because the production `app` singleton's mounted MCP sub-app had never had its lifespan entered anywhere else in the repo (confirmed by reading Starlette's `routing.py` to establish that `app.router.lifespan_context` is exactly the same mechanism already proven safe on the Starlette sub-app in the premise gate, then grepping the whole test tree for any existing consumer of it before writing anything). Put in a new, separate file rather than added to the existing premise gate file, since the premise gate's whole design assumes per-call isolation via a rebuilt app (to respect the mount's one-shot session-manager constraint) and this test deliberately does the opposite, entering the one real singleton's lifespan exactly once; mixing the two patterns in one file risked a future edit accidentally violating the one-shot constraint. Decision and full LEARNINGS account logged (see DECISIONS.md and LEARNINGS.md, both 2026-08-11).

F-4.1-J-03 (moderate): added six new tests exercising every previously-uncovered line the judge named. Four are small, direct unit tests in `TestFallbackAnswerText` (new class in the premise gate file): `_extract_bearer_header` against a duck-typed context whose `.headers` is `None` (line 141), and `_fallback_answer_text` called directly for its guard-failure branch (183-188), its fatal-error branch (189-190), and its no-guard-no-error catch-all branch (191). Two are full end-to-end fold tests in `TestUngroundedRunShapesFoldCorrectly` (new class), each with a new fake event-stream fixture built to match the exact shape `core/graph.py`'s real functions emit (verified by reading `_decline_for_guardrail` and `_decline_for_daily_cap` directly, not guessed): `_guardrail_refusal_stream` (a `guard` event with `passed=False` then `done`, no `token`) and `_daily_cap_decline_stream` (a fatal `error` event then `done`, no `token`). These two close the synthetic-trust-signal fallback (248-257), the empty-answer path invoking `_fallback_answer_text` (261), and, for the daily-cap shape specifically, the fatal-error capture branch (239-241) that no direct unit test can reach since it lives inside `_fold_run_to_response`'s own event loop.

F-4.1-J-04 (minor): added `mcp-types>=2.0` and `httpx2>=2.0` to both `requirements.txt` and `pyproject.toml`, matching the repo's existing floor-pin convention. Verified both PyPI distribution names against the installed wheel before adding (`pip show mcp-types` and `pip show httpx2` both report version `2.0.0`, MIT license, `Required-by: mcp`), confirming the import name and the distribution name are identical for both packages so no name-mapping error was introduced. Ran `pip-audit -r requirements.txt` afterward: no known vulnerabilities.

### Verification

```text
$ pytest tests/system_03_search_agent/adapters/mcp/ -v
============================= test session starts ==============================
platform darwin -- Python 3.11.6, pytest-9.1.1, pluggy-1.6.0
plugins: cov-7.1.0, asyncio-1.4.0, anyio-4.14.2, langsmith-0.10.10
collected 20 items

TestToolSurface::test_exactly_one_tool_is_advertised PASSED                [  5%]
TestToolSurface::test_no_internal_tool_name_is_separately_advertised PASSED[ 10%]
TestToolSurface::test_no_internal_tool_is_separately_callable PASSED       [ 15%]
TestSchemaFidelity::test_input_schema_matches_section_13_2 PASSED          [ 20%]
TestSchemaFidelity::test_output_schema_matches_section_13_2 PASSED         [ 25%]
TestFallbackAnswerText::test_ctx_with_no_headers_attribute_value_returns_none PASSED [ 30%]
TestFallbackAnswerText::test_guard_failure_produces_guard_specific_refusal_wording PASSED [ 35%]
TestFallbackAnswerText::test_fatal_error_produces_error_specific_wording PASSED [ 40%]
TestFallbackAnswerText::test_no_guard_and_no_error_produces_the_generic_catch_all_wording PASSED [ 45%]
TestGoldenPath::test_a_real_question_returns_a_grounded_cited_answer PASSED[ 50%]
TestRefusalPath::test_a_zero_groundable_result_query_refuses_honestly PASSED [ 55%]
TestEventFolding::test_folded_response_has_no_field_for_excluded_event_types PASSED [ 60%]
TestNeverCost::test_an_operator_allowlisted_caller_still_gets_no_cost_field PASSED  [ 65%]
TestUngroundedRunShapesFoldCorrectly::test_guardrail_refusal_run_folds_to_a_fallback_answer PASSED [ 70%]
TestUngroundedRunShapesFoldCorrectly::test_daily_cap_decline_run_folds_to_a_fallback_answer PASSED [ 75%]
TestAuth::test_missing_token_is_rejected_before_any_run_is_created PASSED  [ 80%]
TestAuth::test_malformed_token_is_rejected_before_any_run_is_created PASSED[ 85%]
TestAuth::test_invalid_token_is_rejected_before_any_run_is_created PASSED  [ 90%]
TestAuth::test_a_valid_token_succeeds_and_the_run_is_owned_by_that_user PASSED [ 95%]
TestProductionMount::test_the_real_shipped_app_answers_a_real_mcp_call_end_to_end PASSED [100%]

============================== 20 passed in 6.15s ===============================
```

Coverage over `adapters/mcp/server.py`, the module the gate exists to grade:

```text
$ pytest --cov=system_03_search_agent.adapters.mcp.server --cov-report=term-missing tests/system_03_search_agent/adapters/mcp/
Name                                                Stmts   Miss  Cover   Missing
---------------------------------------------------------------------------------
src/system_03_search_agent/adapters/mcp/server.py      83      0   100%
---------------------------------------------------------------------------------
TOTAL                                                  83      0   100%
20 passed in 10.09s
```

`100%`, up from the judge's `84%`. Every line the judge named as missing (141, 183-191, 239-241, 249-250, 261) is now covered; none is left unreachable.

`ruff check` on every file touched this round (`tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py`, `tests/system_03_search_agent/adapters/mcp/test_phase_4_1_production_mount.py`, `requirements.txt`, `pyproject.toml`, `DECISIONS.md`, `LEARNINGS.md`): `All checks passed!` (Python files only; `requirements.txt` is not a Python file and was not linted with `ruff check`, matched by hand against the existing line style instead). Whole-repo `ruff check . --output-format=concise` (sorted): 17 errors, same count and same file set the judge recorded, zero introduced by this round's files.

Full repo suite (`pytest -q` from repo root): `6 failed, 2417 passed, 113 skipped, 1 xfailed in 97.19s`. The 6 failures are the identical, unchanged set the judge already confirmed as the pre-existing live-network-opt-in-gated baseline (`test_citation_trust_full_premise.py`, every one a `LiveHttpCallInUnitSuiteError`). `2417 = 2410 (the judge's own passing count) + 7` (6 new tests added to `test_phase_4_1_premise.py`, 1 new test in `test_phase_4_1_production_mount.py`); skip, xfail, and fail counts unchanged from the judge's own run.

`pip-audit -r requirements.txt`: `No known vulnerabilities found`.

`DECISIONS.md` gained one new row (the test-file-split rationale for F-4.1-J-02) and `LEARNINGS.md` gained one new row plus its detail section (verifying the production `app` singleton's lifespan was safe to enter exactly once, before doing it).

Ready for judge re-verification.

## Judge review

Round 1, 2026-08-11, against `62d4e76`: FAIL. One blocking finding (F-4.1-J-01), three non-blocking (F-4.1-J-02, F-4.1-J-03, F-4.1-J-04).

The scope of the FAIL, stated plainly so the fix round does not over-correct: nothing in the shipped module is wrong as far as this round could determine. Every clause of the phase premise was re-derived independently below, and every one holds in the code. What fails is the verify surface. Two of the gate's declared arms contain an assertion that is true for all inputs, and four branches of the module the gate exists to grade are never executed by it. Per `.claude/rules/goal-contracts.md`, a green gate that cannot fail is not evidence, and the gate is this phase's stated done-when.

### Evidence

Every number below was produced by the judge in this session, not taken from the builder's report.

| Check | Command | Result |
| --- | --- | --- |
| Premise gate | `pytest tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py -v` | `13 passed in 7.50s`, all 13 named cases PASSED, matching the run recorded above |
| Full repo suite | `pytest -q` | `6 failed, 2410 passed, 113 skipped, 1 xfailed in 60.79s` |
| Regression identity | inspected the 6 failures | All 6 in `tests/system_03_search_agent/synthesis/test_citation_trust_full_premise.py`, every one a `LiveHttpCallInUnitSuiteError` against a live host. Exactly develop's known baseline (2397 + 13 new = 2410), skip/xfail/fail counts unchanged. Zero new failures |
| Ruff, files touched or created | `ruff check` on the five changed source and test files | `All checks passed!`, exit 0 |
| Ruff, whole repo, versus develop | `ruff check . --output-format=concise` on `HEAD` and on `develop`, sorted and `comm`-diffed | 17 errors on both, byte-identical sets, zero introduced by this branch. Every one is pre-existing in `tracker/*.py`, `.claude/skills/`, and three older test files |
| Module coverage under the gate | `pytest <gate> --cov=system_03_search_agent.adapters.mcp.server --cov-report=term-missing` | `83 stmts, 13 miss, 84%`, `Missing 141, 183-191, 239-241, 249-250, 261`. Filed as F-4.1-J-03 |
| Doc drift | `python tracker/check_doc_drift.py --check` | `error: 8 facts computed (2 skipped) 10 stale`. Expected at judge time, not a finding: the stale values are the test, DECISIONS.md and LEARNINGS.md counts (`2517 -> 2530`, `275 -> 282`, `65 -> 67`), all three of which `/phase-checkpoint` refreshes after the judge round. Recorded so the checkpoint step does not skip it |

### Failing-first, verified from git rather than accepted

Verified independently, not taken from the file's own pasted output.

- `git log --follow -- tests/.../test_phase_4_1_premise.py` returns `3014dae` (2026-08-11 17:33:04) as the first commit, then `d666066` (17:45:29) as the fix.
- `git show --stat 3014dae` shows exactly two files: the test file (672 lines) and its package `__init__.py`. No source file.
- `git ls-tree -r --name-only 3014dae -- src/system_03_search_agent/adapters/` returns only `adapters/__init__.py`, `adapters/web_sse/__init__.py`, `adapters/web_sse/app.py`. The directory `src/system_03_search_agent/adapters/mcp/` did not exist at that commit.
- `git log --follow -- src/system_03_search_agent/adapters/mcp/server.py` returns a single commit, `699cd4c` (17:45:16), twelve minutes after the gate.

So the pasted `ModuleNotFoundError: No module named 'system_03_search_agent.adapters.mcp.server'` is not merely plausible, it is the only thing the autouse fixture could have raised against that tree. This closes F-4.0-J-02's carried process concern for the first time: the failing-first claim is now checkable from the repo, exactly as that finding's disposition promised.

### Schema fidelity, verified against the advertised schema rather than the passing test

Dumped `await server.list_tools()` directly and read the SDK-derived schemas, rather than trusting `TestSchemaFidelity`.

| Section 13.2 clause | Observed | Verdict |
| --- | --- | --- |
| exactly one tool | `TOOL COUNT: 1 NAMES: ['ask_biomedical_question']` | matches |
| `query` string, maxLength 2000, required | `{"maxLength": 2000, "type": "string"}`, `"required": ["query"]` | matches |
| `audience_depth` three-value enum | `"enum": ["clinical_brief", "researcher", "deep_technical"]` | matches |
| `session_id` maxLength 64 | `"anyOf": [{"maxLength": 64, "type": "string"}, {"type": "null"}]` | matches |
| `answer` maxLength 8000 | `{"maxLength": 8000, "type": "string"}` | matches |
| `citations` maxItems 50, items `CitationV1` | `{"items": {"$ref": "#/$defs/CitationPayload"}, "maxItems": 50, "type": "array"}` | matches |
| `CitationV1` is Section 9.1's type, not a redefinition | `grep -rn "class CitationPayload" src/` returns exactly one hit, `contracts/events.py:135`. `AskBiomedicalQuestionOutput.model_fields["citations"].annotation.__args__[0] is CitationPayload` evaluates `True` against the imported class object | matches, reused verbatim |
| `trust_signal` object | `{"$ref": "#/$defs/TrustSignalPayload"}`, resolving to `"type": "object"` | matches |
| `run_id` maxLength 64 | `{"maxLength": 64, "type": "string"}` | matches |
| all four output fields required | `required: ['answer', 'citations', 'trust_signal', 'run_id']`, and `[k for k, v in AskBiomedicalQuestionOutput.model_fields.items() if v.is_required()]` returns the same four | matches, none Optional |

The `ctx: Context` parameter is correctly absent from the advertised `input_schema`, so the SDK's context injection does not leak an extra property into the locked shape.

### Auth boundary, traced in code

- `adapters/mcp/server.py:303` is `user = await _authenticate_mcp_caller(ctx)`, the first statement of the tool body. `default_registry.create_run` is line 320. Auth cannot be reached out of order.
- `_authenticate_mcp_caller` (145-162) calls `resolve_user_from_bearer_token` and translates `InvalidBearerTokenError` into `MCPError(code=INVALID_REQUEST, ...)`, a protocol-level failure, never a silent empty result.
- The three `TestAuth` rejection arms are not vacuous: each installs a real spy over `default_registry.create_run` and asserts `create_calls == []`, so they pin "no run created", not merely "an error was raised".
- `get_current_user`'s behavior is unchanged. The diff moves the identical checks, in the identical order, into `resolve_user_from_bearer_token` and leaves `get_current_user` as a four-line wrapper translating one exception type into the same `HTTPException(401, _INVALID_TOKEN_DETAIL)` it always raised. Same single detail string on every failure path, so no failure mode newly leaks which check tripped. Confirmed live by the full suite: `tests/system_03_search_agent/auth/test_router.py` and every other authenticated-route test pass unchanged.
- The helper is genuinely shared, not duplicated: `resolve_user_from_bearer_token` has exactly one definition and two callers, `get_current_user` and `_authenticate_mcp_caller`. There is no second decode-then-lookup implementation to drift.

### Never-cost, and the raw-passthrough boundary

- `grep -n "operator_mode\|is_operator_user" src/system_03_search_agent/adapters/mcp/server.py` returns two hits, both on the hard-pin: the comment at 313-318 and `RequestContext(surface="mcp", operator_mode=False)` at 319. `is_operator_user` is not imported and not called anywhere in the module, so the stronger surface-level rule is what the code implements, not the weaker role-derived one.
- Defense in depth confirmed independently: `_fold_run_to_response` has no branch that reads a cost-shaped field from any event, and the entire output model tree carries zero fields matching `cost` or `cap`. So a cost field cannot reach an MCP response even if `operator_mode` were wrong.
- `is_operator_user` reads `OPERATOR_USER_IDS` fresh on every call (`harness/cost_control.py:492, 498`), so `TestNeverCost`'s `monkeypatch.setenv` does take effect and the test really does authenticate an allowlisted caller. Its weakness is the vacuous nested assertion filed as F-4.1-J-01, not a stale-env problem.
- Single-tool surface: verified at the registry, not only through the gate. `server.list_tools()` returns one tool. The module registers exactly one `@server.tool` decorator and never calls `add_tool`. None of the seven internal tool modules is imported by `adapters/mcp/server.py` at all, so no internal tool is reachable as an MCP tool by construction, not merely by omission from a list.
- The handler calls into the core, never a tool function: `default_registry.create_run(query_obj, context, run_id=run_id)` is the same entry point `adapters/web_sse/app.py:170` uses, and `default_registry` is imported from `core.run_registry`, the same module-level singleton, so the MCP surface shares one registry with the REST surface rather than standing up a second.
- Abandonment safety, checked because build phase 4.0 added it: `RunRegistry.subscribe` increments `entry.subscriber_count` on entry and decrements in `finally`, so the fold loop counts as a watcher for its whole duration and F-1.2-02's grace-period cancellation cannot kill a run an MCP caller is actively waiting on.

### Cite-or-refuse parity

Verified as far as this phase's design allows, and the gap is stated rather than papered over. `TestRefusalPath` does NOT drive the real core loop: it monkeypatches `run_streaming` at `core.run_registry` with `_refusal_path_stream`, the same seam `test_phase_4_0_premise.py` established, for the same stated reason (the live graph needs an SSH tunnel this environment cannot open). What it therefore proves is that the fold surfaces a refusal faithfully, not that the refusal rule itself is correct.

That is acceptable here, and the structural argument is stronger than the test: the MCP adapter contains no grounding logic at all. It never calls `write_node`, never assembles a citation, and never decides an outcome. Cite-or-refuse is owned by `core/graph.py` and pinned by build phases 2.2 and 3.4's own gates, and this surface can only relay it. There is exactly one place the surface introduces wording of its own, `_fallback_answer_text`, and that is filed as part of F-4.1-J-03 precisely because it is the one MCP-specific refusal string and it is untested.

### Scope boundary and dependency checks

| Check | Result |
| --- | --- |
| `v1-scope-boundary.md` out-of-scope terms across the full branch diff (`BLAST`, `VCF`, sequence-similarity, `UCSC`, distillation, ensemble, segmental) | Zero hits |
| New API-key or token entity, SQLAlchemy model, or migration | None. `git diff develop..HEAD -- src/` adds no `__tablename__`, no class inheriting `Base`, no Alembic revision. The scope-boundary decision recorded above (an MCP client is a dedicated `User` account) is what the code actually does: `resolve_user_from_bearer_token` returns a `User` row and `Query.user_id` is `str(user.id)` |
| New dependency | `mcp>=2.0` added to both `requirements.txt` and `pyproject.toml`, floor-pinned, matching this repo's convention for library dependencies. `pip show mcp` confirms `2.0.0`, MIT, published by the Model Context Protocol project under LF Projects. Product-owner approval is recorded above and in DECISIONS.md. Two undeclared direct imports filed as F-4.1-J-04 |

### DECISIONS.md and LEARNINGS.md accuracy

Read all six new DECISIONS.md rows and both new LEARNINGS.md entries against the code, rather than against the builder's narration. Every claim checks out:

- The flat-input-schema decision is confirmed by the dumped `input_schema` above: three top-level properties, no nested wrapper object.
- The `TrustSignalPayload`-as-`trust_signal` decision is confirmed by `AskBiomedicalQuestionOutput.model_fields` and by the `$ref` resolving to `"type": "object"`, so the richer type still satisfies Section 13.2's minimal documented shape.
- The `session_id`-defaults-to-`run_id` decision is confirmed at `server.py:308`.
- The synthetic-trust-signal decision is confirmed at `server.py:248-257`. Its stated justification is accurate; the branch is simply untested, which is F-4.1-J-03.
- The mount-recipe decision is confirmed at `adapters/web_sse/app.py`: `streamable_http_path="/"` and the `AsyncExitStack`-wrapped `_lifespan` are both present, and both are load-bearing exactly as described.
- Both LEARNINGS entries describe real, still-visible artifacts: the three mount fixes are in the shipped `app.py`, and the `except*` unwrap is in the gate at `_call_tool_expecting_mcp_error`.

No narrated-but-unimplemented claim was found.

### Premise re-read, clause by clause

Re-read the Phase premise paragraph after reviewing the code. Verdict per clause:

| Clause | Holds? |
| --- | --- |
| Valid bearer token for a dedicated `User` account calls the single advertised tool | Yes, verified in code and by `TestAuth`'s valid-token arm, which also asserts the created run's `user_id` matches |
| One JSON result, never a stream | Yes. `_fold_run_to_response` awaits the terminal event and returns one model |
| No `think`, `plan`, or `tool_start` ever reaches the caller | Yes at the top level, verified structurally by the key-set assertion and by reading the fold loop, which has no branch for any of the three. The nested half of that arm is vacuous, F-4.1-J-01 |
| Locked schema exactly, `CitationV1` read verbatim off `CitationPayload` | Yes, verified against the advertised schema and the class identity |
| Honest refusal, no fabricated citations, identical rule to every other surface | Partly. Relaying is verified; the one surface-specific wording (`_fallback_answer_text`) is untested and unreviewed, F-4.1-J-03 |
| No response ever carries a cost field, `operator_mode` hard-pinned false | Yes in code, and true structurally. The arm claiming to prove it does not, F-4.1-J-01 |
| A bad-token caller never reaches the core loop, no run, no budget | Yes, verified by code order and by three real spy-backed tests |
| `list_tools()` advertises exactly one tool, no internal tool separately reachable | Yes, verified at the registry and by the absence of any internal-tool import |

Two clauses depend on arms that do not test what they claim, and one depends on code no test executes. That is the FAIL.

### Ticket status

Judge is the only role permitted to write `done` or `rejected` here, per the task-tracker convention.

| Ticket | Status | Reason |
| --- | --- | --- |
| T-4.1-01 | rejected | The gate is green at 13 of 13 and its failing-first history is genuinely verifiable, both real accomplishments. It is nonetheless rejected on F-4.1-J-01: two of its nine declared arms end in an assertion that is true for every possible input, including the leak each was written to catch. F-4.1-J-02 and F-4.1-J-03 also land here, since both are coverage gaps in this ticket's artifact: the shipped production mount is never exercised, and four branches of the module under test are never executed. The coverage-exclusion statement in the file and in the test docstring is present and honest about what it excludes, which is why the gaps above are filed as defects rather than as undeclared blind spots |
| T-4.1-02 | done | `MCPServer` instantiation, the single `@server.tool` registration, and the fold loop all verified by direct inspection. The advertised input and output schemas match Section 13.2 clause for clause, independently dumped rather than read off the passing test. `CitationPayload` is reused verbatim with exactly one class definition repo-wide. The fold discards `think`, `plan`, `tool_start`, `tool_result` and `cost` by having no branch for them, and terminates on the registry's own terminal-event contract. The mount code is present and correct by reading, and its three non-obvious requirements are correctly implemented; that it is untested is filed against T-4.1-01, whose artifact the missing test would be |
| T-4.1-03 | done | Auth runs as the first statement of the tool body, before `create_run`, verified by line order and by three spy-backed rejection tests that assert zero runs created. `resolve_user_from_bearer_token` is genuinely shared with one definition and two callers, and `get_current_user`'s behavior is unchanged: same checks, same order, same detail string, same 401, with the whole authenticated-route suite green as independent confirmation. `operator_mode=False` is hard-set in this module's own code and `is_operator_user` is neither imported nor called here, so the stronger surface-level rule is what ships |
| T-4.1-04 | done | `mcp>=2.0` present in both `requirements.txt` and `pyproject.toml`, floor-pinned per this repo's library convention, with `pip show mcp` confirming `2.0.0` MIT from the Model Context Protocol project. Six DECISIONS.md rows added, all six checked against the code and all six accurate. `list_tools()` confirmed at exactly one tool with no internal tool importable, let alone advertised. F-4.1-J-04 (two undeclared direct imports of transitive packages) is filed against this ticket's dependency-declaration scope but is minor and does not block it |

### Not fixed by the judge, deliberately

None of the four findings were fixed in this round. The finder is not the closer, per `.claude/rules/self-eval-loop.md`. F-4.1-J-01 is the only blocking one and its fix is a one-line change in each of two tests; F-4.1-J-02 and F-4.1-J-03 each need a small new test rather than a source change; F-4.1-J-04 needs two lines in the dependency files. A fix round should also re-run the gate and confirm the corrected F-4.1-J-01 assertions still pass, since a corrected assertion that suddenly fails would mean a real leak exists.

### Ready for the adversary round?

Not yet. Run the fix round first. The specific reason is F-4.1-J-01: an adversary probing this surface for a cost or internal-event leak would be checking a property whose own gate arms cannot currently detect a violation, so a clean adversary result would carry less weight than it should. Once the two assertions are corrected and the uncovered branches have arms, the adversary round has real ground to stand on. The highest-value adversary targets this round did not cover, recorded so the next round does not have to re-derive them: a run that emits no `token` event at all (the guardrail-refusal and daily-cap-decline shapes behind `_fallback_answer_text`), an answer exceeding 8000 characters or a run exceeding 50 citations (both silently truncated at `server.py:264` and `server.py:230` with no disclosure to the caller, the same shape as the carried F-4.0-A-12), a run that never terminates (the fold loop has no wall-clock bound of its own and relies entirely on the core's per-step timeouts), and a hostile `Authorization` header shape the SDK's `Context.headers` view might normalize differently from FastAPI's `Header`.
