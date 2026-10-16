# Card 114 adversary round, pull request 233

Adversary, dial position 2, 2026-10-15. Branch tree 266d35e6, develop tree cffdb8fd. Findings appended as established.

## Findings

### Live proof, hunt 1 (evidence, not a finding)

Own probe (`<scratchpad>/adv/run1.py`, `run2.py`), `core/run.py` `run_streaming`, `RequestContext(surface="web_ui", reads_placement=True)`, environment forced to GUARD_MODEL and PLAN_MODEL deepseek/deepseek-v4-flash, SYNTH_MODEL z-ai/glm-5.2, CLASSIFIER_PROVIDER jev, PER_QUERY_COST_CAP_USD 0.25, main venv (litellm 1.93.0, its map has no openrouter/z-ai/glm-5.x entry).

| Tree | Question | Depth | Elapsed | Reported cost | Summary written sentences |
|---|---|---|---|---|---|
| develop cffdb8fd | Query 66, Marfan features | plain_language | 10.8 s | $0.000378 | none. Only "I found 1 condition related to Marfan syndrome [1]." Log: "writer call failed after the listing was sent (trace ef869f1ed2ba4f79): unexpected; the listing is the answer" |
| branch 266d35e6 | Query 66 run 1 | plain_language | 6.4 s | $0.019507 | four: "Marfan syndrome is a condition that affects connective tissue throughout the body and is passed down through families [84]." and three more |
| branch | Query 66 run 2 | plain_language | 7.7 s | $0.019049 | none: features line and "I found 1 condition related to Marfan syndrome [1]." only, although glm-5.2 was called twice (stderr: "LiteLLM completion() model= z-ai/glm-5.2" twice) and no writer failure was logged. See A-114-01 |
| branch | "Which diseases are associated with BRCA1?" run 1 | researcher | 8.3 s | $0.020067 | one: "The encoded protein combines with other tumor suppressors, ... (BASC) [23]." |
| branch | same, run 2 | researcher | 9.8 s | $0.020183 | three, lead "BRCA1 is associated with four diseases: familial cancer of breast [1], ..." then the count line repeating the same four records. See A-114-02 |

Live spend this round: $0.0792 of the $0.40 budget. Writer works again on the branch in 3 of 4 runs; develop's failure reproduced exactly as described.

### A-114-01: With the writer restored, query 66 still gave a count-line-only summary in 1 of 2 runs
- Severity: minor (the branch is not the cause; it does not fully deliver "develop's writer works again")
- What: on the branch tree with develop's models, query 66 run 2 billed two glm-5.2 writer calls ($0.019049) and logged no writer failure, yet the summary held no written sentence: the person sees the same count line develop shows today. Run 1 wrote four sentences. Cause not established in this round (the run 1 probe did not capture sentence check logs); consistent with writer bench 3's record that glm-5.2 withdrew 9 of 18 summaries.
- Reproduction: `<scratchpad>/adv/run1.py "What phenotypic features are associated with Marfan syndrome?" plain_language` from the branch tree, second run. Summary tokens: `['claim', 'MedGen lists these clinical features: Aortic regurgitation [4], ... Hypertropia [13]. ']`, `['claim', 'I found 1 condition related to Marfan syndrome [1]. ']`, nothing more. stderr: `LiteLLM completion() model= z-ai/glm-5.2; provider = openrouter` twice.
- What a person would see: after the merge, some questions still get only the record count, now at about 50 times develop's cost per question ($0.019 against $0.0004), because the writer is paid for and its prose is dropped. A two-run sample cannot give the rate; the build report's claim that the writer works should not be read as "every answer has prose".
- NOT FIXED

### A-114-02: Researcher lead sentence repeats the four records the count line lists right under it
- Severity: minor, unsure (writer behaviour that develop could not show because its writer failed; not caused by this diff)
- What: BRCA1 at Researcher, run 2 on the branch: the summary opens "BRCA1 is associated with four diseases: familial cancer of breast [1], familial breast-ovarian cancer susceptibility 1 [2], pancreatic cancer susceptibility 4 [3], and Fanconi anemia complementation group S [4]." and the next claim is "Found 4 disease records for BRCA1: Familial cancer of breast [1], Familial breast-ovarian cancer susceptibility 1 [2], Pancreatic cancer susceptibility 4 [3] and Fanconi anemia complementation group S [4]." Decision `write.lead_sentence` chose `first` by jev.
- Reproduction: `<scratchpad>/adv/run2.py "Which diseases are associated with BRCA1?" researcher`, branch tree, second of two runs. Run 1 chose `neither` and did not repeat.
- What a person would see: the same four diseases twice in the first two sentences, which the test queries document forbids for Researcher ("Researcher never repeats a record in the prose that the list below already shows"). Restoring the writer brings this back into reach on develop.
- NOT FIXED

### A-114-03: The new zero rule covers only an exact double zero; a partial zero, a near zero or NaN from litellm still beats the table's price
- Severity: minor (pre-existing shapes, but they sit inside the line this fix rewrote, and the fix's own comment says "A zero there is a gap, not a free model")
- What: `_price_per_token` replaces litellm's figure with the table's only when both prices are exactly 0. When litellm returns input non-zero and output 0, input 0 and output non-zero, a denormal such as 1e-30, or NaN, the table entry is ignored and that figure is used, for every model the table names, Opus included.
- Reproduction: `<scratchpad>/adv/price_matrix.py` (monkeypatches `litellm.get_model_info`, calls `harness._price_per_token`), branch tree, main venv. Pasted rows:
  - `in_zero|anthropic/claude-opus-5.5 ['1e-06', '0.0']` (table says 4e-06, 2e-05)
  - `zero_out|z-ai/glm-5.2 ['0.0', '1e-06']`
  - `tiny|anthropic/claude-opus-5.5 ['1e-30', '0.0']`
  - `nan|z-ai/glm-5.2 ['nan', 'nan']`
  Develop gives the same values for these shapes, so this is not a regression; it is the gap the fix names and leaves half closed. NaN is the worst: `projected > cap` is False for NaN, so a NaN price would turn the per-question cap off for that model.
- What a person would see: if litellm's map (fetched at process start, it is not pinned; LITELLM_LOCAL_MODEL_COST_MAP is unset) ever carries an Opus or glm entry with the output price missing as 0, every Opus answer is metered near $0 and the per-question cap stops guarding the expensive writer. The cost line shown would be false.
- NOT FIXED

Correction to A-114-03, established after it was written: the pre-flight estimate does not go NaN, because `estimate_next_call_cost_usd` returns `max(static, bound)` and `max(0.025, nan)` is 0.025 (probe: a NaN-priced Opus against a $0.0000001 cap was REFUSED on both trees). The hole is after the first call: the metered cost is `prompt_tokens * nan + ...`, `track_cost` stores NaN, and every later check passes. Probe on the branch tree: `h.track_cost("n2","synth",float("nan")); h.track_cost("n2","synth",5.0)` then `check_per_query_cap` with cap 0.25 printed `running cost nan` and `after NaN plus 5.0 : admitted`. So a NaN price still disables the cap for the rest of that question, and the reported cost is NaN. Same on develop; still within the line this fix rewrote.

### Hunt 2 result: the cap, every model and tier (evidence)

`<scratchpad>/adv/cap_matrix.py`, both trees, main venv's real litellm map, PER_QUERY_COST_CAP_USD 0.25, one fresh question per row, prompt of 2000 or 17000 words. Rows that differ between develop and branch:

| Tier, model, prompt | develop estimate | branch estimate | Admitted |
|---|---|---|---|
| synth, glm-5.2, 17000 words | 0.025000 (static; the real call then raises unpriced) | 0.029378 | both |
| synth, Opus 5.5, 2000 words | 0.025000 | 0.093336 | both |
| synth, Opus 5.5, 17000 words | 0.025000 | 0.193336 | both |
| plan, Opus 5.5, 17000 words | 0.012500 | 0.193336 | both |
| `_two_drafts_fit_cap`, Opus 5.5, 17000 words each | True | False | n/a |
| deepseek-v4-flash and kimi-k2.6, every tier | identical | identical | both |

For develop's own models (deepseek guard and plan, glm-5.2 writer) no row changes from admitted to refused: the zero rule cannot make the cap refuse a question develop answered, because none of those three is mapped by litellm at all (it raises "This model isn't mapped yet"), so the zero branch is never reached for them; glm-5.2's bound at 0.0294 is far under 0.25. The only model the zero rule changes today is Opus 5.5 (litellm 1.93.0 returns 0 and 0 for openrouter/anthropic/claude-opus-5.5). See A-114-04.

### A-114-04: On any deployment whose writer is the Opus default, the branch now runs the two writer drafts one after the other and can refuse the second, where develop ran both at once
- Severity: minor, unsure (the branch's accounting is the correct one; develop's was false. Filed because it is a visible change of speed and answer for a person, and it is not stated in the build report)
- What: litellm 1.93.0 maps openrouter/anthropic/claude-opus-5.5 at 0 and 0, so develop prices Opus at zero: its cost line for an Opus question omits the writer entirely and the cap never binds it. The branch prices it at $4 and $20 per million. With PER_QUERY_COST_CAP_USD 0.25, `_two_drafts_fit_cap` turns False at every realistic writer prompt, and at a 23,334-token prompt the second draft is refused even after waiting.
- Reproduction: branch tree, SYNTH_MODEL anthropic/claude-opus-5.5, guard cost 0.0004 tracked, then the first draft metered at writer bench 3's real G-001 figure $0.087288:
  ```
  6000 words -> 10000 prompt tokens bound; one-draft bound 0.12 ; both at once: False ; second after first ($0.087288): admitted
  10460 words -> 17434 prompt tokens bound; one-draft bound 0.1497 ; both at once: False ; second after first ($0.087288): REFUSED? no: admitted
  14000 words -> 23334 prompt tokens bound; one-draft bound 0.1733 ; both at once: False ; second after first ($0.087288): REFUSED
  ```
  (pasted lines 1 and 3 verbatim; line 2 verbatim output was "both at once: False ; second after first ($0.087288): admitted"). Develop, same model: `two_drafts|anthropic/claude-opus-5.5 dev= True`, synth estimate 0.025000 at every prompt size.
- What a person would see: develop does not use Opus (SYNTH_MODEL is glm-5.2 there), so nobody on develop sees this today. Anyone running with SYNTH_MODEL unset (local runs, and production at the next release if production sets no SYNTH_MODEL) gets the second draft only after the first returns, adding a full writer call (writer bench 3: 10.7 s median) and pushing answers past the 20-second rule; on a long prompt the second draft never runs. The cost line becomes true where it was understated by the whole writer cost. Whether 0.25 is still the right cap for Opus is the owner's call; the build report's price table says "Only Opus changes price" but not what that does to drafts or speed.
- NOT FIXED

Note on A-114-04's reproduction block: its second line was mistyped in the edit. The verbatim output for 10460 words is `10460 words -> 17434 prompt tokens bound; one-draft bound 0.1497 ; both at once: False ; second after first ($0.087288): admitted`.

### Hunt 4 result: strawberry 0.327.7 against the GraphQL surface (evidence)

Own probes `<scratchpad>/adv/gql_attack.py` and `gql_depth.py`, the real `web_sse.app` with the real router, `RequestTimeoutMiddleware` and schema, Starlette TestClient. Run on the branch tree once under the main venv (strawberry 0.324.0, graphql-core 3.2.11) and once under `<scratchpad>/venv-ci` (strawberry 0.327.7, graphql-core 3.2.11), then the parsed responses diffed. Two passes: a stand-in registered principal (dependency override on `get_context`), and the real `get_context` with no credential.

| Attack | 0.324.0 | 0.327.7 |
|---|---|---|
| `__schema`, `__type`, aliased `__schema`, `__schema` inside a fragment | refused, "GraphQL introspection has been disabled ..." | identical |
| Misspelt field, argument, enum value, type | no "Did you mean" in any message | identical |
| 21 aliases / 20 aliases | "21 aliases found. Allowed: 20" / admitted | identical |
| 1001 tokens | "Syntax Error: Document contains more than 1000 tokens. Parsing aborted." | identical |
| Fragment cycle | "Cannot spread fragment 'A' within itself via 'B'." | identical |
| Inline fragments nested 11, 30, 63 / 70, 500 | admitted / refused by the 64-level middleware | identical |
| Two `ask` fields in one mutation | TOO_MANY_RUN_CREATING_FIELDS | identical |
| `subscription { __typename }` over POST | "Schema is not configured to execute subscription operation." | identical |
| `@defer`, `@stream` | "Unknown directive" | identical |
| WebSocket with `graphql-ws`, `graphql-transport-ws`, no subprotocol | closed, WebSocketDisconnect code 1000, never accepted | identical |
| JSON array (batch) of 1 or 2 operations | 400 "Batching is not enabled" | identical |
| GET with query, GET text/html (IDE), GET event-stream | 400 "queries are not allowed when using GET" / 404 / 400 | identical |
| text/plain, form-urlencoded, application/graphql, multipart upload, no content type | 400 "Unsupported content type" | identical |
| POST with Accept text/event-stream or multipart/mixed | ordinary application/json result | identical |
| Resolver raising RuntimeError, ValueError, KeyError carrying a secret-looking message | masked, "This request could not be completed due to an internal error." | identical |
| Unknown run | RUN_NOT_FOUND "no such run" | identical |
| CORS preflight from https://evil.example | 400, no allow-origin header | identical |
| Every attack with no credential | 401 "invalid or expired credentials" (WebSocket still closed) | identical, 0 diffs |

The one difference a client can observe is byte-level: 0.327.7's `encode_json` is `json.dumps(data, separators=(",", ":"))` where 0.324.0's is `json.dumps(data)`, so bodies are compact (`{"data":{"__typename":"Query"}}` against `{"data": {"__typename": "Query"}}`). Parsed JSON is identical in every case above. Not filed as a finding: a JSON client cannot tell, and nothing in this repository compares GraphQL bodies as raw text that I found. Pre-existing on both versions, not caused by the branch: an invalid `text` variable of 100,000 characters is echoed back whole inside the error message.

### A-114-05: The stated root cause is incomplete: litellm's price map is downloaded from litellm's main branch at every process start, so the price a model gets depends on that download, not on the installed litellm
- Severity: minor (not introduced by this branch, and the branch's fallback holds in both cases I tested; filed because the comment the branch writes into `tiers.py` and the build report state a cause that my probes contradict, and the next breakage will come from the same place)
- What: `harness/tiers.py` now says "litellm no longer has any openrouter/z-ai/glm-5.x entry". The installed litellm does have one. With LITELLM_LOCAL_MODEL_COST_MAP unset, litellm replaces its bundled map at import with `https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json` (litellm `__init__.py` line 396); today that file has 4186 entries and no glm-5.2. The bundled map of litellm 1.105.1 (the version the CI scratch venv resolves from `litellm>=1.40`) has 4459 entries and prices glm-5.2.
- Reproduction: `_price_per_token` under `<scratchpad>/venv-ci` (litellm 1.105.1), pasted:
  ```
  == a114dev
   litellm 1.105.1 LOCAL True entries 4459
     z-ai/glm-5.2 litellm: (4.1e-07, 3.99e-06) -> price: (4.1e-07, 3.99e-06)
     deepseek/deepseek-v4-flash litellm: (4.186e-08, 8.372e-08) -> price: (4.186e-08, 8.372e-08)
   litellm 1.105.1 LOCAL  entries 4186
     z-ai/glm-5.2 litellm: unmapped -> price: RAISES HarnessCallError
  == a114
   litellm 1.105.1 LOCAL True entries 4459
     z-ai/glm-5.2 litellm: (4.1e-07, 3.99e-06) -> price: (4.1e-07, 3.99e-06)
   litellm 1.105.1 LOCAL  entries 4186
     z-ai/glm-5.2 litellm: unmapped -> price: (7.182e-07, 2.2572e-06)
  ```
  So develop's writer failure is caused by the download, and develop would have answered with the bundled map. On the branch, glm-5.2's output price is $2.2572 per million when the download succeeds at boot and $3.99 when it fails and litellm falls back to its bundled copy; deepseek-v4-flash is $0.14 and $0.28 against $0.04186 and $0.08372. One billed call I made today (`<scratchpad>/adv/billprobe.py`, OpenRouter usage accounting) came back at about $0.62 and $2.42 per million for glm-5.2 (1664 prompt tokens, $0.00103168; 12 completion tokens, $0.00002904) and $0.091 per million input for deepseek (1211 tokens, $0.000110201); OpenRouter's public catalogue lists glm-5.2 today at $0.037 and $7.00, which matches neither.
- What a person would see: the cost line on an answer, and how close a question runs to its cap, change with whether a GitHub download succeeded when the server last started. Any upstream edit to that file can again remove a model's price and take the writer down, as it did on develop, for a model not in the local table (kimi-k2.6 and Opus are covered by the table; a new SYNTH_MODEL is not). The restored glm entry also skips the table's own provenance rule ("re-read the catalogue rather than hand-editing"): it was copied from production, not read from the catalogue.
- NOT FIXED

Supplement to A-114-03: a partial zero is not hypothetical. litellm 1.105.1's bundled map (LITELLM_LOCAL_MODEL_COST_MAP=True) returns `typesafe/jev-1.13 litellm: (4.2e-08, 0.0)`, input priced, output zero. Jev is charged by its own reported cost rather than through `_price_per_token`, so this one does not reach a person today; it shows the shape occurs in the real map.

Supplement to A-114-01 and A-114-02, two more query 66 runs on the branch with sentence check logs (`run2.py`), $0.018944 and $0.019956:

- Run 3 (12.5 s): written sentences present ("Marfan syndrome is a condition that affects many parts of the body at once [83]." and one more), but one draft's check failed: `WARNING ... sentence_check: sentence check: Jev made no verdict (trace 483fba068a964c5a, unexpected_error); approving nothing, no other model is asked` then `WARNING ... core.graph: sentence check approved nothing (trace 483fba068a964c5a): SentenceCheckUnreadable`. The underlying exception's type and text are not logged anywhere (`sentence_check.py` line 802 catches `Exception` and logs only the reason string), so why Jev failed cannot be read from the logs. When this hits both drafts the person gets the count-line-only answer of run 2. This code is not in the diff; it becomes reachable on develop again because the writer runs.
- Run 4 (8.3 s): the A-114-02 repetition also happens at plain_language. Lead: "Marfan syndrome is associated with aortic regurgitation [4], arachnodactyly [5], astigmatism [6], ectopia lentis [7], esotropia [8], exotropia [9], pes planus [10], glaucoma [11], congestive heart failure [12], and hypertropia [13]." Two claims later: "MedGen lists these clinical features: Aortic regurgitation [4], Arachnodactyly [5], ... and Hypertropia [13]." The same ten features, the same ten citations, twice in one summary. `write.lead_sentence` chose `first`.

Query 66 tally on the branch: 4 runs, written sentences in 3, count-line-only in 1, same list twice in 1. Live spend so far $0.1182.

### A-114-06: No test pins that a real, non-zero litellm price still beats the table; a mutant that always prefers the table survives the harness suite
- Severity: minor (test gap inside this phase's fix)
- What: the rewritten condition has two halves: a double zero for a table model goes to the table (pinned by `test_a_model_litellm_maps_at_zero_gets_the_tables_price` and, indirectly, by `test_decide`'s `_free_guard`), and anything else from litellm wins (the docstring's "Primary source"). The second half is unpinned for table models. Mutating the line to `if model_id not in _FALLBACK_PRICES_USD_PER_TOKEN:` (the table always wins for any model it names, litellm's price ignored) leaves the harness suite exactly at baseline.
- Reproduction: copies of the branch's `src` and `tests` in `<scratchpad>/adv/mut0` (unmutated) and `<scratchpad>/adv/mut3` (mutated), `pytest tests/system_03_search_agent/harness -m "not integration" -q`, main venv:
  - unmutated: `3 failed, 550 passed, 13 errors` (the 3 failures and 13 errors come from the copy lacking repository files outside `src` and `tests`; they are the same in every copy)
  - mutated: `3 failed, 550 passed, 13 errors`, the same three tests
  For contrast, the mutants `if not is_zero:` and `if not (is_zero or model_id in ...)` are both killed (`8 failed, 545 passed, 13 errors`, the 5 extra being `test_decide.py::test_an_unusable_jev_reply_is_charged_at_its_reported_cost[...]`), but only through the zero path.
- What a person would see: nothing today, because the downloaded map prices none of the four table models (A-114-05). The day litellm prices one of them for real (its bundled 1.105.1 map already prices glm-5.2 at $0.41 and $3.99 per million), a regression that freezes the table's stale figure would pass CI, and the cost line and the cap would use the hand-copied price over the maintained one.
- NOT FIXED

Correction to the running spend: the earlier supplement said $0.1182; the sum of the reported costs is $0.1193 (nine items: five develop and branch questions before, the two billing probe calls at $0.00106072 and $0.000112021, and the two extra query 66 runs). Final live spend for this round: $0.1193 of $0.40. Opus was never called as writer.

### Gate 6, own run

`pip-audit -r requirements.txt` in `<scratchpad>/venv-ci`: branch tree "No known vulnerabilities found"; develop tree "Found 2 known vulnerabilities in 1 package", strawberry-graphql 0.324.0, PYSEC-2026-4302 (fix 0.327.2) and PYSEC-2026-4303 (fix 0.326.1).

## Verdict

PASS, with six findings, none critical or major.

Two findings sit inside the fix this phase made (the rewritten zero condition in `_price_per_token`): A-114-03 (only an exact double zero falls back to the table; partial zero, near zero and NaN do not) and A-114-06 (the non-zero half of that condition is unpinned; a mutant survives). Both are minor. Per the review loop's rule this is named so the lead can decide whether it fires the stop condition.

| Finding | Severity | In this phase's fix | One line |
|---|---|---|---|
| A-114-01 | minor | no | Writer restored, but query 66 still gave a count-line-only summary in 1 of 4 branch runs; a Jev sentence check failure is logged without its cause |
| A-114-02 | minor, unsure | no | Lead sentence repeats the same records or features the next line lists (BRCA1 Researcher, Marfan plain language) |
| A-114-03 | minor | yes | Partial zero, near zero or NaN from litellm still beats the table; a NaN metered cost turns the cap off for the rest of the question |
| A-114-04 | minor, unsure | consequence | With Opus as writer, the drafts now run one after the other and a long prompt loses the second draft; develop priced Opus at zero |
| A-114-05 | minor | no (root cause statement is) | Prices come from litellm's map downloaded at boot; the bundled map prices glm-5.2 differently, and the comment's cause is incomplete |
| A-114-06 | minor | yes | No test pins that litellm's real non-zero price beats the table |

Verified with my own probes:

- Develop's writer fails ("writer call failed after the listing was sent ... unexpected") and the branch's writes sentences, live, with develop's models and cap (hunt 1).
- Price matrix for every table model and tier default under 14 litellm shapes on both trees: the branch never raises where develop did not, and differs only by pricing double zeros at the table price and pricing glm-5.2 where develop raised (hunt 3).
- Cap estimates for every model on every tier on both trees: no develop model moves from admitted to refused; only Opus changes (hunt 2).
- 49 GraphQL client attacks on 0.324.0 and 0.327.7, authenticated and not: identical parsed responses; only compact JSON bytes differ (hunt 4).
- pip-audit result for both pins.
- Mutation of the new condition, three mutants (two killed, one survived).

Only read, not probed: the strawberry supply-chain checks in the build report (compromise search, upload dates, wheel contents); the full unit suite count (7635 passed); ruff and isort results; production's table values.

## Learnings

- macOS has no `timeout` command; the first live run exited 127 and wrote nothing. Cost under five minutes.
- litellm prints "Provider List" banners to stdout before a probe's JSON, so the first parse of the branch runs failed; parse from the first brace. Under five minutes.
- The bash hook blocks file deletion, so the mutation copies in the scratchpad (`<scratchpad>/adv/mut0` to `mut3`) could not be deleted by this agent.

Correction to the verdict's list: the GraphQL attack count is 56 (47 in `gql_attack.py`, 9 in `gql_depth.py`), not 49.
