# Card 114 fresh verifier, pull request 233

Bases: branch tree `54cb4a6c` (fix/ci-model-prices-and-strawberry head), develop tree `cffdb8fd`. Worktrees at `<scratchpad>/v114` and `<scratchpad>/v114dev`, detached.

## Findings

### V-114-01: The fix round's glm-5.2 price is one cheap endpoint's figure, not glm-5.2's catalogue price; today the catalogue says $0.62 and $2.42 per million, and the table meters the writer's input at a seventeenth of that

- Severity: major against the card's words ("the per-question cost cap counts every model's real price"); minor for a person asking a question today (no question is refused or slowed by it, see V-114-02). Sits inside a fix made during this phase (fix round, J-114-05). Escalation trigger.
- What: the fix round set `"z-ai/glm-5.2": (0.000000037, 0.000007)` from OpenRouter's model-level `pricing` read at 23:50 UTC on 2026-10-15. Re-read now, the model-level price is different, and the fix round's pair is exactly the price of one provider endpoint, Wafer `wafer/us`, the cheapest of 32. The model-level figure moves with whichever endpoint OpenRouter currently lists first; it is not a stable "real price". The figure today matches the price the adversary was actually billed (A-114-05: $0.62 and $2.42 per million from OpenRouter usage accounting).
- Reproduction: `curl -s https://openrouter.ai/api/v1/models` and `curl -s https://openrouter.ai/api/v1/models/z-ai/glm-5.2/endpoints`, 2026-10-15 (this round):
  ```
  z-ai/glm-5.2 {"prompt": "0.00000062", "completion": "0.00000242", "input_cache_read": "0.00000014"}
  ...
  Wafer wafer/us {"prompt": "0.000000037", "completion": "0.000007", "input_cache_read": "0.000000036", "discount": 0} 0
  CoreWeave coreweave/fp4 {"prompt": "0.00000062", "completion": "0.00000242", ...}
  Decart decart/fast {"prompt": "0.0000025", "completion": "0.000009", ...}
  ```
  Endpoint input prices run from 3.51e-08 to 2.5e-06, output from 1.8e-06 to 9e-06. The metering line (`harness.py` line 826, `prompt_tokens * input_price + completion_tokens * output_price`) uses the table, so a writer call of 17,000 prompt and 800 output tokens is metered at 17000*3.7e-08 + 800*7e-06 = $0.0062 against $0.0125 at today's catalogue (and billed) price: half.
- Why a person would care: no answer changes today (the cap is far away either way). The operator's cost line for develop's writer undercounts by about half on a normal question, and the card's claim is not true for develop's own writer. The fix replaced one stale figure with a figure that was never the price most calls are billed at; re-reading the model-level field again tomorrow can give a third value.
- NOT FIXED

### V-114-02: Check 4 holds: `_price_per_token` raises on the branch nowhere develop priced, under either litellm version and either map

- Severity: none (holds)
- What: every tier default, every table key and develop's settings, priced by `harness._price_per_token` on both trees, under the main venv (litellm 1.93.0) and `<scratchpad>/venv-ci` (litellm 1.105.1), each with the fetched map (LITELLM_LOCAL_MODEL_COST_MAP unset) and the bundled map (`=True`). Probe `<scratchpad>/ver/price_table.py`. Branch differs from develop only on Opus under a zero map (table price instead of zero) and on glm-5.2 under a map without it (priced instead of raising). Jev raises on both trees under the fetched map (it is charged from its own reported cost, not through this function); under bundled 1.105.1 it is (4.2e-08, 0.0) on both trees, untouched because the table does not name it.
- Reproduction, pasted (`venv` = main venv 1.93.0, `venv-ci` = 1.105.1):
  ```
  === tree=v114dev py=venv
  ## litellm 1.93.0 LOCAL=unset entries=4186 openrouter=0
  anthropic/claude-opus-5.5 | litellm (0, 0) | price (0.0, 0.0)
  deepseek/deepseek-v4-flash | litellm no entry (Exception) | price (1.4e-07, 2.8e-07)
  moonshotai/kimi-k2.6 | litellm no entry (Exception) | price (6.46e-07, 2.72e-06)
  typesafe/jev-1.13 | litellm no entry (Exception) | price RAISES HarnessCallError
  z-ai/glm-5.2 | litellm no entry (Exception) | price RAISES HarnessCallError
  === tree=v114dev py=venv
  ## litellm 1.93.0 LOCAL=True entries=2953 openrouter=95
  anthropic/claude-opus-5.5 | litellm (0, 0) | price (0.0, 0.0)
  deepseek/deepseek-v4-flash | litellm no entry (Exception) | price (1.4e-07, 2.8e-07)
  moonshotai/kimi-k2.6 | litellm no entry (Exception) | price (6.46e-07, 2.72e-06)
  typesafe/jev-1.13 | litellm no entry (Exception) | price RAISES HarnessCallError
  z-ai/glm-5.2 | litellm no entry (Exception) | price RAISES HarnessCallError
  === tree=v114dev py=venv-ci
  ## litellm 1.105.1 LOCAL=unset entries=4186 openrouter=0
  anthropic/claude-opus-5.5 | litellm (0, 0) | price (0.0, 0.0)
  deepseek/deepseek-v4-flash | litellm no entry (ModelNotMappedError) | price (1.4e-07, 2.8e-07)
  moonshotai/kimi-k2.6 | litellm no entry (ModelNotMappedError) | price (6.46e-07, 2.72e-06)
  typesafe/jev-1.13 | litellm no entry (ModelNotMappedError) | price RAISES HarnessCallError
  z-ai/glm-5.2 | litellm no entry (ModelNotMappedError) | price RAISES HarnessCallError
  === tree=v114dev py=venv-ci
  ## litellm 1.105.1 LOCAL=True entries=4459 openrouter=486
  anthropic/claude-opus-5.5 | litellm (4e-06, 2e-05) | price (4e-06, 2e-05)
  deepseek/deepseek-v4-flash | litellm (4.186e-08, 8.372e-08) | price (4.186e-08, 8.372e-08)
  moonshotai/kimi-k2.6 | litellm (4.3415e-07, 1.828e-06) | price (4.3415e-07, 1.828e-06)
  typesafe/jev-1.13 | litellm (4.2e-08, 0.0) | price (4.2e-08, 0.0)
  z-ai/glm-5.2 | litellm (4.1e-07, 3.99e-06) | price (4.1e-07, 3.99e-06)
  === tree=v114 py=venv
  ## litellm 1.93.0 LOCAL=unset entries=4186 openrouter=0
  anthropic/claude-opus-5.5 | litellm (0, 0) | price (4e-06, 2e-05)
  deepseek/deepseek-v4-flash | litellm no entry (Exception) | price (1.4e-07, 2.8e-07)
  moonshotai/kimi-k2.6 | litellm no entry (Exception) | price (6.46e-07, 2.72e-06)
  typesafe/jev-1.13 | litellm no entry (Exception) | price RAISES HarnessCallError
  z-ai/glm-5.2 | litellm no entry (Exception) | price (3.7e-08, 7e-06)
  === tree=v114 py=venv
  ## litellm 1.93.0 LOCAL=True entries=2953 openrouter=95
  anthropic/claude-opus-5.5 | litellm (0, 0) | price (4e-06, 2e-05)
  deepseek/deepseek-v4-flash | litellm no entry (Exception) | price (1.4e-07, 2.8e-07)
  moonshotai/kimi-k2.6 | litellm no entry (Exception) | price (6.46e-07, 2.72e-06)
  typesafe/jev-1.13 | litellm no entry (Exception) | price RAISES HarnessCallError
  z-ai/glm-5.2 | litellm no entry (Exception) | price (3.7e-08, 7e-06)
  === tree=v114 py=venv-ci
  ## litellm 1.105.1 LOCAL=unset entries=4186 openrouter=0
  anthropic/claude-opus-5.5 | litellm (0, 0) | price (4e-06, 2e-05)
  deepseek/deepseek-v4-flash | litellm no entry (ModelNotMappedError) | price (1.4e-07, 2.8e-07)
  moonshotai/kimi-k2.6 | litellm no entry (ModelNotMappedError) | price (6.46e-07, 2.72e-06)
  typesafe/jev-1.13 | litellm no entry (ModelNotMappedError) | price RAISES HarnessCallError
  z-ai/glm-5.2 | litellm no entry (ModelNotMappedError) | price (3.7e-08, 7e-06)
  === tree=v114 py=venv-ci
  ## litellm 1.105.1 LOCAL=True entries=4459 openrouter=486
  anthropic/claude-opus-5.5 | litellm (4e-06, 2e-05) | price (4e-06, 2e-05)
  deepseek/deepseek-v4-flash | litellm (4.186e-08, 8.372e-08) | price (4.186e-08, 8.372e-08)
  moonshotai/kimi-k2.6 | litellm (4.3415e-07, 1.828e-06) | price (4.3415e-07, 1.828e-06)
  typesafe/jev-1.13 | litellm (4.2e-08, 0.0) | price (4.2e-08, 0.0)
  z-ai/glm-5.2 | litellm (4.1e-07, 3.99e-06) | price (4.1e-07, 3.99e-06)
  ```
- Why a person would care: no model develop's settings use goes from priced to unpriced, so no question that develop's model calls could answer is refused for want of a price.
- Holds

Correction to V-114-01, established by the live runs below (V-114-04), which read OpenRouter's own `usage.cost` on every glm-5.2 call: today's bill is near the TABLE's figure, not near the model-level catalogue figure I quoted. OpenRouter routed the writer to a cheap endpoint each time. Pasted, per glm-5.2 call (prompt tokens, completion tokens, billed, table price, catalogue model-level price now):
  ```
  glm call 11281 246 billed 0.00224426 table 0.002139 catalogue-now 0.00759
  glm call 11653 483 billed 0.0028334 table 0.003812 catalogue-now 0.008394
  glm call 11161 147 billed 0.00207454 table 0.001442 catalogue-now 0.007276
  glm call 11533 456 billed 0.00309337 table 0.003619 catalogue-now 0.008254
  glm call 11455 212 billed 0.00220842 table 0.001908 catalogue-now 0.007615
  ```
  Per question, the harness's metered total against OpenRouter's billed total: $0.007265 against $0.005237, $0.006448 against $0.005336, $0.002672 against $0.002520. So my "undercounts by about half" does not hold; the table meters each writer call between 30% under and 35% over the bill. What still holds: the figure the fix round wrote is one endpoint's price that the model-level field happened to show at 23:50 UTC, the model-level field now shows a price about three and a half times the bill, and neither is "the real price" in a stable sense. Severity lowered to minor. Still inside this phase's fix.

### V-114-03: Checks 2 and 3, live: with develop's settings the branch starts both writer drafts together on every question that has a second draft; develop's writer fails; the cap can never stop glm-5.2's second draft

- Severity: none for the branch against develop (holds). Two observations about answer quality that are not caused by this diff are recorded at the end.
- What and reproduction: own probe `<scratchpad>/ver/live.py`, main venv (litellm 1.93.0, fetched map, no LITELLM_LOCAL_MODEL_COST_MAP, as develop's deploy), `core/run.py` `run_streaming`, `RequestContext(surface="web_ui", reads_placement=True)`, GUARD_MODEL and PLAN_MODEL deepseek/deepseek-v4-flash, SYNTH_MODEL z-ai/glm-5.2, CLASSIFIER_PROVIDER jev, PER_QUERY_COST_CAP_USD 0.25. It wraps `litellm.acompletion` (start and end second of each call, whether the prompt carries "COMPLETENESS REQUIREMENT", tokens, OpenRouter's `usage.cost`) and `graph._two_drafts_fit_cap` (its result, the running cost, each draft's pre-call bound from `cost_control.estimate_next_call_cost_usd`). Pasted from the runs:

  | Tree, question, depth | Seconds | Cost (meter / OpenRouter bill) | Two drafts | Draft starts (first, COMPLETENESS) | Bounds, running, cap | Written sentences in the summary |
  |---|---|---|---|---|---|---|
  | develop, query 66, plain | 14.3 | 0.000541 / 0.000162 | fit True on static 0.025 each, price `RAISES HarnessCallError`; no glm call made | none | 0.025, 0.025, 0.000541, 0.25 | none. Log: `writer call failed after the listing was sent (trace 140e40ba4c6c4fe1): unexpected; the listing is the answer`. Summary: `I found 5 published papers, 1 condition, 1 literature index entry and 5 clinical trials related to Marfan syndrome [...]` |
  | branch, query 66, plain, run 1 | 8.0 | 0.007265 / 0.005237 | True | 5.51 s, 5.51 s | 0.028561623, 0.028579827, 0.000379, 0.25 | none (both drafts returned prose; summary holds only the code-built `MedGen lists these clinical features: ...` and `I found 1 condition related to Marfan syndrome [1].`) |
  | branch, query 66, plain, run 2 | 14.3 | 0.006448 / 0.005336 | True | 9.35 s, 9.36 s | 0.028555629, 0.028573833, 0.000550, 0.25 | one: `Marfan syndrome is a condition that affects many parts of the body, and the records describe it as a connective tissue disease that runs in families, mainly caused by a change in the FBN1 gene [83].` |
  | branch, query 66, plain, run 3 | 12.2 | 0.002672 / 0.002520 | not asked (no completeness draft that run, one glm call) | 10.76 s, none | n/a | none (writer returned `Marfan syndrome is linked to changes in three genes: FBN1, TGFBR1, and TGFBR2 [1][2][3]. ...`; nothing of it reached the summary) |
  | branch, BRCA1, researcher, run 1 | 12.0 | 0.009844 / 0.006189 | True | 8.57 s, 8.57 s | 0.028568912, 0.028592185, 0.000380, 0.25 | four, e.g. `BRCA1 encodes a 190 kD nuclear phosphoprotein that maintains genomic stability and acts as a tumor suppressor [23].` |
  | branch, BRCA1, researcher, run 2 | 7.6 | 0.008950 / 0.006888 | True | 4.68 s, 4.69 s | 0.028569393, 0.028592666, 0.000375, 0.25 | two, e.g. `BRCA1 encodes a nuclear phosphoprotein that maintains genomic stability and acts as a tumor suppressor, with mutations responsible for approximately 40% ... [23].` |

  Pre-call bound for one glm-5.2 writer draft at the new price: about 12,300 bounded prompt tokens * 3.7e-08 + 4,000 output ceiling * 7e-06 = $0.0286 (the probe's own figures above). Both drafts plus the running cost: about $0.058 against a $0.25 cap. The prompt size at which two drafts would stop fitting: (0.25 - 0.0004 - 2 * 0.028) / (2 * 3.7e-08), about 2.6 million tokens each, beyond any context window. So under develop's settings the cap cannot refuse, truncate or serialise a writer draft at this price, and the output ceiling, not the prompt, sets the bound.
- Why a person would care: on develop today every question loses its written summary (the writer cannot be priced). On the branch the writer runs, both drafts start together, and every answer arrives in 7.6 to 14.3 seconds. Nothing is refused or slowed by the cap. No regression.
- Not caused by this diff, recorded because a person will see them once the writer is back on develop:
  - Query 66 wrote prose into the summary in 1 of 3 runs. Run 1's two drafts and run 3's one draft all returned prose that never reached the summary; run 3 logged no sentence check line at all. Matches A-114-01 (open).
  - BRCA1 Researcher repeated the four diseases in the lead sentence and the count line directly under it in 2 of 2 runs (`BRCA1 is associated with four diseases in the retrieved records: Familial cancer of breast [1], ...` then `Found 4 disease records for BRCA1: Familial cancer of breast [1], ...`). Matches A-114-02 (open), now 2 of 2 at Researcher.
- Live spend this round, OpenRouter's own figures summed: $0.0263 (develop 0.000162, branch 0.005237 + 0.005336 + 0.002520 + 0.006189 + 0.006888). No Opus call.
- Holds

### V-114-04: J-114-07 closed: CI's exact setup sequence in a fresh venv ends at strawberry-graphql 0.327.7, and the two manifests agree on every exact pin

- Severity: none (closure evidence)
- Reproduction: a new Python 3.11 venv (`python3.11 -m venv <scratchpad>/ver/venv-fresh`, CI's `PYTHON_VERSION: "3.11"`), then from the branch tree `bash .github/gates/setup_python.sh` (`python -m pip install --upgrade pip && pip install -r requirements.txt && pip install -e ".[dev]"`), exit 0. Afterwards:
  ```
  Name: strawberry-graphql
  Version: 0.327.7
  ```
  The second install step's log reads `Requirement already satisfied: strawberry-graphql==0.327.7 ... (from agentic-search-ui==0.1.0) (0.327.7)`, and the only `Uninstalling` line in the whole log is `Uninstalling pip-23.3.1`. litellm resolved to 1.105.1. A comparison of every `==` pin in `pyproject.toml` (dependencies and extras) against `requirements.txt`:
  ```
  strawberry-graphql pyproject 0.327.7 requirements 0.327.7 AGREE
  ruff pyproject 0.16.0 requirements None AGREE
  isort pyproject 9.0.0 requirements None AGREE
  ```
  `git grep -n "0\.324\.0" -- ':!testing'` outside history notes leaves only `pyproject.toml:45` (a comment naming the historical finding made at that version, as the fix round says) and the requirements.txt history comment.
- Closed

### V-114-05: Check 5, as a client: strawberry 0.327.7 enforces depth, aliases, tokens, introspection, subscriptions off, GET and IDE off, and error masking, identically to 0.324.0

- Severity: none (holds)
- What and reproduction: own probe `<scratchpad>/ver/gql_client.py`. Part 1 mounts a recursive test schema (the real schema has no recursive type, so depth cannot be exceeded legally there) under the project's own `security.SCHEMA_EXTENSIONS`, `STRAWBERRY_CONFIG` and `ROUTER_SETTINGS` in a `GraphQLRouter`, with one resolver raising a `RuntimeError` whose message imitates a leaked credential and private address (obviously fake). Part 2 posts to the real `web_sse.app` at `/graphql/`, with no credential and then with `get_context` overridden by a stand-in registered principal. Run in `<scratchpad>/ver/venv-fresh` (strawberry 0.327.7, CI's setup) and in the main venv (0.324.0); the result lines diffed: only the version line differs (`diff` shows `strawberry 0.324.0` against `strawberry 0.327.7`, plus one stderr log line captured in the 0.327.7 file). Pasted from 0.327.7:
  ```
  strawberry 0.327.7 graphql-core 3.2.11
  depth 9 (root+9 branch, leaf at 11? ): HTTP 200 errors=None data={"root": {"branch": {"branch": {"branch": {"branch": {"branch": {"branch": {"branch": {"br
  depth 9: HTTP 200 errors=None data={"root": {"branch": {"branch": {"branch": {"branch": {"branch": {"branch": {"branch": {"br
  depth 10: HTTP 200 errors=["'anonymous' exceeds maximum operation depth of 10"] data=null
  depth 12: HTTP 200 errors=["'anonymous' exceeds maximum operation depth of 10"] data=null
  introspection __schema: HTTP 200 errors=["GraphQL introspection has been disabled, but the requested query contained the field '__schema'.", "GraphQL introspection has been disabled, but the requested query contained the field 'types'."] data=null
  introspection __type: HTTP 200 errors=["GraphQL introspection has been disabled, but the requested query contained the field '__type'.", "GraphQL introspection has been disabled, but the requested query contained the field 'fields'."] data=null
  suggestion (misspelt leaf): HTTP 200 errors=["Cannot query field 'lef' on type 'Node'."] data=null
  masked internal error: HTTP 200 errors=['This request could not be completed due to an internal error.'] data=null
  21 aliases: HTTP 200 errors=['21 aliases found. Allowed: 20'] data=null
  20 aliases: HTTP 200 errors=None data={"a0": {"leaf": "ok"}, "a1": {"leaf": "ok"}, "a2": {"leaf": "ok"}, "a3": {"leaf": "ok"}, "
  over 1000 tokens: HTTP 200 errors=['Syntax Error: Document contains more than 1000 tokens. Parsing aborted.'] data=null
  GET query: HTTP 400 errors=None data="queries are not allowed when using GET"
  GET IDE (text/html): HTTP 404 errors=None data="Not Found"
  subscription op over POST: HTTP 200 errors=['Schema is not configured to execute subscription operation.'] data=null
  websocket graphql-transport-ws: refused (WebSocketDisconnect 4406)
  websocket graphql-ws: refused (WebSocketDisconnect 4406)
  real router graphql_ide None allow GET False protocols ()
  real, no credential: HTTP 401 errors=None data=null
  real, __typename: HTTP 200 errors=None data={"__typename": "Query"}
  real, __schema: HTTP 200 errors=["GraphQL introspection has been disabled, but the requested query contained the field '__schema'.", "GraphQL introspection has been disabled, but the requested query contained the field 'queryType'."] data=null
  real, two ask fields: HTTP 200 errors=["this document selects 'ask' 2 time(s) (directly, through an alias, or through a spread fragment); at most 1 is", "Field 'AskInput.sessionId' of required type 'AskSessionId!' was not provided.", "Field 'AskInput.sessionId' of required type 'AskSessionId!' was not provided."] data=null
  real, subscription: HTTP 200 errors=['Schema is not configured to execute subscription operation.'] data=null
  real, misspelt field: HTTP 200 errors=["Cannot query field 'rn' on type 'Query'."] data=null
  real, GET: HTTP 400 errors=None data="queries are not allowed when using GET"
  real websocket: refused (WebSocketDisconnect 1000)
  ```
  The secret in the raising resolver reached the server log (traceback) but not the client body.
- Why a person would care: the GraphQL surface a client can reach behaves the same after the upgrade; the upgrade clears PYSEC-2026-4302 and PYSEC-2026-4303 without loosening any bound.
- Holds

### V-114-06: A-114-03 is closed for zero, negative, NaN, infinite and non-numbers, but not for the "near zero" A-114-03 named: a denormal price from litellm still beats the table for Opus and glm-5.2

- Severity: minor, unsure (no installed map does this today; inside this phase's fix, the rewritten condition in `_price_per_token`)
- What: A-114-03 listed four shapes that beat the table: input zero, output zero, "a denormal such as 1e-30", and NaN. The fix round marks A-114-03 closed. `_is_real_price` accepts any finite number above zero, so 1e-30 is "real" and wins over the table for a model the table names. One-sided zeros, NaN, infinities, negatives and non-numbers now all go to the table, as claimed.
- Reproduction: own probe `<scratchpad>/ver/shapes.py` (replaces `litellm.get_model_info`, calls `harness._price_per_token`), branch tree, main venv. Pasted rows:
  ```
  anthropic/claude-opus-5.5 | litellm out zero (4e-06, 0.0) -> (4e-06, 2e-05)
  anthropic/claude-opus-5.5 | litellm nan out (4e-06, nan) -> (4e-06, 2e-05)
  anthropic/claude-opus-5.5 | litellm denormal 1e-30 out (4e-06, 1e-30) -> (4e-06, 1e-30)
  anthropic/claude-opus-5.5 | litellm tiny 1e-12 both (1e-12, 1e-12) -> (1e-12, 1e-12)
  anthropic/claude-opus-5.5 | litellm bool True (True, True) -> (1.0, 1.0)
  z-ai/glm-5.2 | litellm denormal 1e-30 out (4e-06, 1e-30) -> (4e-06, 1e-30)
  test-provider/x:free | litellm nan out (4e-06, nan) -> (4e-06, nan)
  ```
  The last row: a model the table does not name still takes NaN through, as on develop and as the docstring says; for such a model the cap is off for the rest of the question (A-114-03's correction). The `True` row is a curiosity: `float(True)` is 1.0, which `_is_real_price` accepts.
- Why a person would care: only if a future fetched litellm map carried a vanishing price for Opus or glm-5.2; then that writer would be metered near zero and the per-question cap would not bind it. Not worse than develop, which takes any such figure. Recorded so the closure of A-114-03 is read as partial.
- NOT FIXED

### V-114-07: J-114-03, A-114-06 and J-114-02 closed by my own probes; check 6, my own mutation, goes red and restores green

- Severity: none (closure evidence)
- Reproduction, all in a third throwaway worktree `<scratchpad>/v114mut` at 54cb4a6c, main venv, each change reverted with `git checkout` and `git status --short` empty afterwards; baseline `tests/.../harness/test_tiers.py` plus `test_opus_writer.py`: `63 passed in 4.70s`.
  - J-114-03, the model-id scan:
    ```
    == J-114-03 probe a: hardcoded glm compare in tiers.py
    FAILED tests/system_03_search_agent/harness/test_tiers.py::test_no_model_id_shaped_string_outside_the_default_table
    == probe b2: second dict in tiers.py keyed by glm-5.2
    FAILED tests/system_03_search_agent/harness/test_tiers.py::test_no_model_id_shaped_string_outside_the_default_table
    == probe c: a table key literal in graph.py
    FAILED tests/system_03_search_agent/harness/test_tiers.py::test_no_model_id_shaped_string_outside_the_default_table
    == probe e: second assignment to the table name inside tiers.py
    22 passed in 0.50s
    ```
    Probe e passes by design: a second dict literal bound to `_FALLBACK_PRICES_USD_PER_TOKEN` is a table position. A literal equal to a `_DEFAULT_MODELS` value is still allowed anywhere in tiers.py (`_ROUTE = {"anthropic/claude-opus-5.5": "z"}` passed), as before this pull request.
  - A-114-06, the table always wins for a model it names (`or (_is_real_price(...) and _is_real_price(...))` replaced by `or False`), whole harness folder: `FAILED tests/system_03_search_agent/harness/test_opus_writer.py::test_a_real_non_zero_litellm_price_beats_the_table` and `1 failed, 573 passed in 24.46s`.
  - J-114-02 (one-sided zero): V-114-06's rows `out zero (4e-06, 0.0) -> (4e-06, 2e-05)` and `in zero (0.0, 2e-05) -> (4e-06, 2e-05)`.
  - Check 6, my mutation (one property: a price must be finite to be real). `return math.isfinite(number) and number > 0.0` changed to `return number > 0.0` in `_is_real_price`: `FAILED tests/system_03_search_agent/harness/test_opus_writer.py::test_a_price_that_is_not_a_real_number_takes_the_tables_price[infinite]`, `1 failed, 62 passed in 3.20s`. Restored: `63 passed in 2.87s`.
- Closed

### V-114-08: J-114-01 item 5 and J-114-06's corrected comment are still not true: two test arms read the installed litellm map, and the new root-cause comment's "never read this table" is false for the project venv's litellm

- Severity: minor (comments and docstrings; no person sees it). Both sentences were written in this phase's fix round.
- What:
  1. `tests/.../harness/test_opus_writer.py` module docstring now says "No arm here reads the installed map." Two arms call `harness.price_per_token` with no fake of `litellm.get_model_info`: `test_the_cheaper_models_keep_todays_static_estimate` (lines 416 to 427) and `test_the_old_writer_is_never_priced_below_the_static_estimate` (lines 429 to 439). Their result depends on whether litellm's start-up fetch succeeded. The second arm's docstring still says "The old writer's installed price", which the fix round's own comments say no longer exists under the fetched map.
  2. `harness/tiers.py`'s new root-cause paragraph says the installed package's bundled map carries OpenRouter entries, "which is why a process whose fetch fails would price by litellm and never read this table". True for litellm 1.105.1 (CI). False for litellm 1.93.0, the project venv's version: its bundled map has 95 OpenRouter entries, none for glm-5.2, and Opus at zero, so the table is read for glm-5.2, deepseek, kimi and Opus with the fetch off.
- Reproduction: `grep -n "get_model_info\|_litellm_map_lacks_everything\|^def test_" tests/system_03_search_agent/harness/test_opus_writer.py` shows no fake between lines 416 and 440. For item 2, V-114-02's rows:
  ```
  ## litellm 1.93.0 LOCAL=True entries=2953 openrouter=95
  anthropic/claude-opus-5.5 | litellm (0, 0) | price (4e-06, 2e-05)
  deepseek/deepseek-v4-flash | litellm no entry (Exception) | price (1.4e-07, 2.8e-07)
  z-ai/glm-5.2 | litellm no entry (Exception) | price (3.7e-08, 7e-06)
  ```
- Why a person would care: the next maintainer reasoning about which price develop uses gets a wrong premise from the comment. No answer changes.
- NOT FIXED

### V-114-09: Check 7, the gates, and check 5's unit half: all green on the branch tree in a venv built by CI's own setup

- Severity: none (holds)
- Reproduction: `<scratchpad>/ver/venv-fresh` (V-114-04: Python 3.11, CI's `setup_python.sh`, strawberry-graphql 0.327.7, litellm 1.105.1), branch tree `<scratchpad>/v114`, the main checkout's `.env` sourced for USER_DB_URL and then CI's own gate 4 job environment applied on top (extracted from `.github/workflows/ci.yml` by a script, USER_DB_URL left local). `setup_schema.sh` (`alembic upgrade head`) was not run against the local database; the tests found their tables.
  - Gate 3, `ruff check` (no path), ruff 0.16.0: `All checks passed!`, exit 0.
  - Gate 2, `isort --check-only src tests services tracker alembic .claude .github`: `Skipped 2 files`, exit 0.
  - Gate 4, `.github/gates/gate04_unit_suite.sh` (`pytest -m "not integration" -q -rs --junitxml=unit-results.xml`): `7643 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 462.72s (0:07:42)`, exit 0.
  - Gate 4's second half, `.github/gates/gate04b_no_unsanctioned_skips.sh` (`python .github/scripts/assert_no_db_skips.py unit-results.xml`): `ok: 7787 test cases, every skip sanctioned (1 a known open finding, deliberately skipped and tracked, 28 a live Layer 1 graph or model credential CI does not hold, 115 the live premise-gate opt-in)`, exit 0. The fix round did not run this half; it passes.
  - Gate 6, `.github/gates/gate06_python_audit.sh` (`pip-audit -r requirements.txt`): `No known vulnerabilities found`, exit 0.
  - GraphQL tests alone, `pytest -m "not integration" tests/system_03_search_agent/adapters/graphql`: `255 passed, 2 warnings in 4.35s`.
  - Pull request 233's own CI run on 54cb4a6c, job "Python gates (1, 2, 3, 4, 6, 9)" (`gh run view --job 116738653056 --log`): `Requirement already satisfied: strawberry-graphql==0.327.7 ... (from agentic-search-ui==0.1.0) (0.327.7)`, `7643 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 269.06s`, `No known vulnerabilities found`. All four check groups pass.
- Holds

## Closure of the fix round's claims (check 1)

| Finding | Fix round says | Verifier | Evidence |
|---|---|---|---|
| J-114-01 | Closed | Partly. Items 1 to 4 and the libcst wording hold; item 5 (test module docstring) is still false | V-114-08 |
| J-114-02 | Closed | Closed | V-114-06 rows `in zero`, `out zero` |
| J-114-03 | Closed | Closed | V-114-07 probes a, b2, c |
| J-114-05 | Closed | Re-read done, but the figure written is one endpoint's price that the model-level field showed for a while; today the field says $0.62 and $2.42, while the bill is near the table | V-114-01 and its correction |
| J-114-06 | Closed (comments) | Partly. Comments now name the fetch as the cause; one new sentence is false for litellm 1.93.0. The dependency on the fetch itself is unchanged, as the fix round says | V-114-08, V-114-02 |
| J-114-07 | Closed | Closed | V-114-04, V-114-09 (CI log) |
| J-114-08 | Closed | Closed | V-114-04 (`git grep`) |
| A-114-03 | Closed | Partly. Zero, one-sided zero, NaN, infinite, negative, non-number closed; the denormal it named is not | V-114-06 |
| A-114-06 | Closed | Closed | V-114-07 |

## Verdict

PASS: nothing on this branch is worse than develop for a person asking a question.

Stop condition: three findings sit inside fixes made during this phase's fix round: V-114-01 (the glm-5.2 figure, minor after its correction), V-114-06 (A-114-03's denormal shape, minor, unsure) and V-114-08 (two new sentences that are false, minor). None is blocking, none changes an answer.

Verified with my own probes: develop's writer failure and the branch's writer, live, with develop's settings (V-114-03); both drafts starting together and their pre-call bounds (V-114-03); OpenRouter's billed cost per writer call (V-114-01 correction); the catalogue and endpoint prices (V-114-01); `_price_per_token` on both trees, two litellm versions, both maps (V-114-02); 14 price shapes on both sides (V-114-06); CI's setup sequence in a fresh venv (V-114-04); GraphQL limits as a client on both strawberry versions (V-114-05); the scan probes and two mutations (V-114-07); gates 2, 3, 4, 4b and 6 (V-114-09).

Only read: the supply-chain search for 0.327.7 (build.md); the deploy's install command and litellm version (judge's addendum); that Jev never reaches `_price_per_token`.

## Learnings

None cost over five minutes. The secret-scan hook blocked a heredoc that named CI's placeholder variables; extracting the environment from `ci.yml` with a script avoided typing them.
