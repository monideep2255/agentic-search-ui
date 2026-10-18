# Judge report, card 114, pull request 233

Judge round 1, dial position 2. Subject: `git diff cffdb8fd...266d35e6` (fa8507ec, 266d35e6). Worktree: <scratchpad>/j114, detached at 266d35e6.

## Findings

### J-114-01: Comments in the touched files that are now false

- Severity: minor
- What: five statements in files this pull request edits are false at 266d35e6:
  1. `src/system_03_search_agent/harness/tiers.py` lines 66 to 68: "Develop sets no `SYNTH_MODEL`, so this default reaches develop when the phase merges." Develop's API sets `SYNTH_MODEL` (LEARNINGS.md 2026-10-08 row "Develop's model settings"), and the comment this pull request added at lines 144 to 149 of the same file says so ("develop's current writer, which sets that model in its API environment"). The file now contradicts itself.
  2. `tiers.py` lines 135 to 142: Opus's price is "the same figures litellm 1.93.0's own map carries" and "It is here although litellm prices it today". litellm 1.93.0, installed in the project venv, maps Opus at zero (probe below), which is the very reason this pull request adds the zero rule.
  3. `tiers.py` lines 107 to 110: the table is "for models litellm's own static map does not yet carry". After fa8507ec it also overrides a model litellm maps at zero for both prices.
  4. `src/system_03_search_agent/harness/harness.py` lines 230 to 240 (an older duplicate comment block kept above the re-export): "this table exists only for the gap where a resolved tier's model id ... is not yet present in litellm's map". Same widening, not reflected.
  5. `tests/system_03_search_agent/harness/test_opus_writer.py` lines 29 to 31, module docstring: "The rollback arm and the cheaper models' arm read the installed map on purpose." The rollback arm (`test_the_rollback_writer_glm_5_2_is_priced_when_litellm_has_no_entry`) now calls `_litellm_map_lacks_everything` and no longer reads the installed map.
  Also pre-existing in a touched file, not introduced here: `harness.py` line 289 error text tells the operator to "add it to harness.harness._FALLBACK_PRICES_USD_PER_TOKEN"; the table lives in `tiers.py` and a value added under the harness name would not be seen by `test_tiers.py`'s scan intent.
  And `requirements.txt`'s new comment says the libcst floor "widened"; going from `libcst` to `libcst>=1.9.0` narrows it.
- Reproduction (project venv, litellm 1.93.0):
  ```
  anthropic/claude-opus-5.5 | litellm: (0, 0) | price: (4e-06, 2e-05)
  ```
  and `grep -n "Develop sets no" src/system_03_search_agent/harness/tiers.py` gives line 66, while line 147 to 148 reads "develop's current writer, which sets that model in its API environment".
- Why a person would care: the next person to switch develop's writer reads line 66 and believes a merge changes develop's writer, which LEARNINGS.md 2026-10-08 records already misled one builder. Nobody asking a question sees a difference today.
- NOT FIXED

### J-114-02: A one-sided zero from litellm still prices that side at zero for a model the table names

- Severity: minor (unsure whether any installed map ever does this; not worse than develop)
- What: the zero rule in `_price_per_token` (harness.py lines 274 to 280) fires only when BOTH prices are zero. When litellm maps a tabled model with one side at zero, litellm's half-zero pair wins over the table. For Opus, whose cost is dominated by output, an output price of zero would let the per-question cap count the writer's output as free. The card's own reasoning ("a zero there is a gap, not a free model") applies equally to one zero side.
- Reproduction (project venv, `litellm.get_model_info` replaced by a stub returning the pair shown):
  ```
  opus, litellm (0, 2e-5) partial -> (0.0, 2e-05)
  opus, litellm (4e-6, 0) partial -> (4e-06, 0.0)
  glm, litellm (0,0) -> (7.182e-07, 2.2572e-06)
  free id, litellm (0,0) -> (0.0, 0.0)
  ```
  The last line confirms a model the table does not name (a ":free" id) stays free and does not raise, which is right.
- Why a person would care: if a future litellm map (it is fetched from upstream at import unless `LITELLM_LOCAL_MODEL_COST_MAP` is set, and `requirements.txt` asks only `litellm>=1.40`) carried Opus with a zero output price, a question could run past the owner's 25-cent cap without the pre-flight check refusing it. Same behaviour as develop today, so not a regression. The narrowest fix: take the table's value per side when that side is zero and the table names the model.
- NOT FIXED

### J-114-03: The model-id scan widening is tiers.py-only, but allows a fallback key anywhere in tiers.py, and contradicts tiers.py's own pattern 11 comment

- Severity: minor
- What: the brief's premise that the widening allows a fallback key "in ANY source file" is not what the code does. `test_no_model_id_shaped_string_outside_the_default_table` skips a value only when `path == _TIERS_FILE and value in allowed_values` (test_tiers.py lines 238 to 241), so another file still goes red. What is weaker than needed: inside tiers.py, a fallback-table key is now allowed as any string constant, not only as a key of `_FALLBACK_PRICES_USD_PER_TOKEN` (for example a hardcoded `model == "z-ai/glm-5.2"` branch). That looseness already existed for `_DEFAULT_MODELS` values; the change extends it to glm-5.2, which is not a default.
  Two statements now disagree with the scan:
  - tiers.py lines 74 to 86 (Jev comment): the scan "scans this repository for exactly one allowed table of model-id-shaped literals and `_DEFAULT_MODELS` is it ... a second table, even one this file also owns, would be a second place a model id is allowed to appear, which is the thing pattern 11 forbids." This pull request makes the fallback table exactly that second allowed table. Phase 8.7 removed glm-5.2 from the table for this reason (the deleted comment said so).
  - The test's docstring ("find matches only among harness/tiers.py's _DEFAULT_MODELS values") and its failure message ("found outside harness/tiers.py's _DEFAULT_MODELS table") still name only `_DEFAULT_MODELS`.
- Reproduction (probes in <scratchpad>/j114, each reverted with `git checkout`):
  ```
  # appended `_ROLLBACK = "z-ai/glm-5.2"` to harness/harness.py
  FAILED tests/system_03_search_agent/harness/test_tiers.py::test_no_model_id_shaped_string_outside_the_default_table
  1 failed in 0.64s
  # appended `def _sneaky(model): return model == "z-ai/glm-5.2"` to harness/tiers.py
  1 passed in 0.45s
  ```
- Narrowest change that keeps the scan's intent: allow a fallback-table key only when its AST node is a key of the dict literal assigned to `_FALLBACK_PRICES_USD_PER_TOKEN` in tiers.py (collect those `ast.Dict.keys` nodes' line numbers and match on line plus value), and update the Jev comment, the docstring and the message to say there are now two allowed tables, the second for prices only. Whether pattern 11 allows the second table is a design call recorded nowhere in DECISIONS.md that I found; the lead should check.
- Why a person would care: no one asking a question sees this. It is a guard against a hardcoded model choice silently overriding the configured writer, and the guard's documentation now argues against the code.
- NOT FIXED

### J-114-04: Mutation results; one mutation of the zero rule survives (partial zero is unpinned)

- Severity: minor
- What: four of five mutations of ticket A go red. The one that survives changes the zero rule from "both prices zero" to "either price zero"; no test pins what happens on a one-sided zero (see J-114-02), so the suite is silent on that half of the rule.
- Reproduction (<scratchpad>/j114, `pytest -q` over test_opus_writer.py, test_decide.py, test_tiers.py; each mutation reverted with `git checkout`, `git status --short` empty afterwards):
  ```
  == baseline
  126 passed in 12.27s
  == M1 drop glm entry from _FALLBACK_PRICES_USD_PER_TOKEN
  FAILED ...test_opus_writer.py::test_the_rollback_writer_glm_5_2_is_priced_when_litellm_has_no_entry
  FAILED ...test_opus_writer.py::test_the_old_writer_is_never_priced_below_the_static_estimate
  2 failed, 124 passed in 12.28s
  == M2 drop zero check (`if True:`)
  FAILED ...test_opus_writer.py::test_a_model_litellm_maps_at_zero_gets_the_tables_price
  1 failed, 125 passed in 12.55s
  == M3 zero check ignores table membership (`if not is_zero:`)
  FAILED ...test_decide.py::test_an_unusable_jev_reply_is_charged_at_its_reported_cost[...] (5 ids)
  5 failed, 121 passed in 12.26s
  == M4 `and` -> `or` in is_zero
  126 passed in 11.85s
  == M5 drop the table emptying in test_decide._free_guard
  E       assert 0.0001028 == 0.0001 ± 1.0e-10
  5 failed, 66 passed in 11.93s
  ```
  M3 shows a free model the table does not name stays free (it would otherwise raise), pinned only indirectly, by test_decide.py's Jev tests.
- Why a person would care: only through J-114-02. No regression against develop.
- NOT FIXED

### J-114-05: The restored glm-5.2 price is not OpenRouter's price today; develop's writer output is counted at about a third of the catalogue rate

- Severity: major against the card's claim ("the per-question cost cap counts every model's real price"); minor for a person asking a question (the cap is not reached either way)
- What: the restored entry `"z-ai/glm-5.2": (0.0000007182, 0.0000022572)` was copied from production's table ("Values are the ones production carries"), not re-read from the catalogue that tiers.py names as the only allowed provenance ("When a price changes, re-read the catalogue rather than hand-editing"). OpenRouter's public catalogue, read today, prices glm-5.2 at 0.000000037 input and 0.000007 output per token. The table's output price is 3.1 times lower. Develop's writer is glm-5.2 (`SYNTH_MODEL`), so develop's writer cost is now metered and cap-checked at the table's price, not the real one. The other tabled prices also drift from today's catalogue (deepseek-v4-flash table 1.4e-07 and 2.8e-07 against catalogue 9.1e-08 and 1.82e-07, overcounted; kimi-k2.6 output 2.72e-06 against 3.41e-06, undercounted, not used on develop), but those are untouched by this pull request.
- Reproduction (`curl https://openrouter.ai/api/v1/models`, 2026-10-15 23:35 UTC, fields `pricing.prompt` and `pricing.completion`):
  ```
  anthropic/claude-opus-5.5 0.000004 0.00002
  z-ai/glm-5.2 0.000000037 0.000007
  deepseek/deepseek-v4-flash 0.000000091 0.000000182
  moonshotai/kimi-k2.6 0.00000065 0.00000341
  ```
  Writer call bound at 17,000 prompt tokens and the synth ceiling of 4,000 output tokens (`_TIER_MAX_TOKENS`):
  ```
  table glm bound 0.0212382
  catalogue glm bound 0.028629
  ```
- Why a person would care: today it does not change any answer: both figures are about a tenth of the 25-cent cap. It does mean the cost figures the operator reads for develop's writer undercount the output side, and the claim in the card's words is not true for develop's writer. Opus's table price matches the catalogue exactly.
- Unsure: OpenRouter's catalogue price for a multi-provider model can differ from what a given call is billed; I did not read a bill. The lead should re-read the catalogue rather than take my figures.
- NOT FIXED

### J-114-06: The root cause is the upstream price map losing every OpenRouter entry, not litellm dropping glm-5.2; deployed prices change if that fetch fails

- Severity: major (unsure; behaviour existed before this pull request, but the pull request's diagnosis and comments rest on it)
- What: litellm fetches its price map from GitHub at import unless `LITELLM_LOCAL_MODEL_COST_MAP` is set. Today that upstream file has 4,187 entries and none beginning `openrouter/`. The map bundled inside the installed litellm still prices every model this project uses. So which price a running process uses depends on whether that one fetch succeeded at start-up:
  - Fetch succeeds (normal): no OpenRouter entries, Opus resolves to (0, 0) and falls to the table, every other model falls to the table. This pull request's fix covers this case.
  - Fetch fails or is disabled: litellm's bundled map prices win, nonzero, and the table is never read. deepseek-v4-flash is then priced at 4.186e-08 and 8.372e-08, glm-5.2 at 4.1e-07 and 3.99e-06, and the cap and meter silently change.
  The new comments say "litellm no longer has any openrouter/z-ai/glm-5.x entry" (tiers.py line 145) and "litellm's map no longer carries it" (tiers.py line 64, test_opus_writer.py line 225). That is true of the fetched upstream file only. litellm 1.105.1's own bundled map carries `openrouter/z-ai/glm-5.2`.
- Reproduction (<scratchpad>/venv-ci, litellm 1.105.1, the version CI installs from `litellm>=1.40`; `_price_per_token` at 266d35e6):
  ```
  == LITELLM_LOCAL_MODEL_COST_MAP=True
  anthropic/claude-opus-5.5 | litellm: (4e-06, 2e-05) | price: (4e-06, 2e-05)
  deepseek/deepseek-v4-flash | litellm: (4.186e-08, 8.372e-08) | price: (4.186e-08, 8.372e-08)
  z-ai/glm-5.2 | litellm: (4.1e-07, 3.99e-06) | price: (4.1e-07, 3.99e-06)
  == LITELLM_LOCAL_MODEL_COST_MAP=False
  anthropic/claude-opus-5.5 | litellm: (0, 0) | price: (4e-06, 2e-05)
  deepseek/deepseek-v4-flash | litellm: no entry: ModelNotMappedError | price: (1.4e-07, 2.8e-07)
  z-ai/glm-5.2 | litellm: no entry: ModelNotMappedError | price: (7.182e-07, 2.2572e-06)
  ```
  ```
  bundled entries 4460 openrouter 486
  live entries 4186 openrouter 0
  openrouter/z-ai/glm-5.2 True False
  ```
  and `curl` of `https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json` gives `4187 0` (entries, OpenRouter entries).
- Why a person would care: whether a question's spend is counted at one price or another depends on GitHub being reachable when the server starts, and the comments now point the next maintainer at the wrong cause. If upstream restores its OpenRouter entries, glm-5.2 and Opus will be priced by litellm again and the table goes quiet, which is fine, but if upstream restores them at zero for both sides only tabled models are protected. One option for the lead (not a fix I am prescribing): set `LITELLM_LOCAL_MODEL_COST_MAP=True` so the installed version's map is used and pricing is reproducible, and decide whether the table or litellm should win.
- NOT FIXED

### J-114-07: pyproject.toml still pins strawberry-graphql==0.324.0, so CI installs 0.327.7, uninstalls it, and tests the vulnerable 0.324.0

- Severity: blocking
- What: 266d35e6 moves the pin in `requirements.txt` only. `pyproject.toml` line 52 still reads `"strawberry-graphql==0.324.0",` (its comment at line 45 too). CI's `.github/gates/setup_python.sh` line 8 runs `pip install -r requirements.txt && pip install -e ".[dev]"`; the second command resolves the project's own `==0.324.0` and replaces 0.327.7. Gate 6 (`pip-audit -r requirements.txt`) audits the file, not the environment, so it reports clean while every Python gate on pull request 233 ran on 0.324.0, the version with PYSEC-2026-4302 and PYSEC-2026-4303. The build report's "the GraphQL unit tests pass unchanged" on 0.327.7 was true only in the builder's scratch venv, never in CI. Anyone who installs the project the documented way (`pip install -e .`, a developer, the Factory agent) also gets 0.324.0.
- Reproduction:
  ```
  $ git grep -n "strawberry-graphql==" -- pyproject.toml requirements.txt
  pyproject.toml:52:    "strawberry-graphql==0.324.0",
  requirements.txt:82:strawberry-graphql==0.327.7
  ```
  Dry run of CI's second step in <scratchpad>/venv-ci (holds 0.327.7; unchanged afterwards):
  ```
  Collecting strawberry-graphql==0.324.0 (from agentic-search-ui==0.1.0)
  Would install agentic-search-ui-0.1.0 isort-9.0.0 mypy_extensions-1.1.0 ruff-0.16.0 strawberry-graphql-0.324.0
  after dry run: 0.327.7
  ```
  Pull request 233's own CI log, job "Python gates (1, 2, 3, 4, 6, 9)" (passed), `gh run view --job 116725715683 --log`:
  ```
      Found existing installation: strawberry-graphql 0.327.7
      Uninstalling strawberry-graphql-0.327.7:
        Successfully uninstalled strawberry-graphql-0.327.7
  Successfully installed ... strawberry-graphql-0.327.7   (first step)
  Successfully installed ... agentic-search-ui-0.1.0 ... strawberry-graphql-0.324.0   (second step)
  No known vulnerabilities found
  ```
- Why a person would care: the card says "CI's dependency check passes again"; it passes because it reads a file the test environment ignores. Whether develop's deployment runs the fixed version depends on how Railway's Nixpacks build installs (railway.json names only `"builder": "NIXPACKS"`): if it installs `requirements.txt` alone it gets 0.327.7, if it also installs the project it gets 0.324.0. I did not read a deploy log, so that half is unsure. Narrowest fix: move `pyproject.toml`'s pin (and its comment) to 0.327.7 in the same change; a guard that the two manifests agree on every exact pin would stop the next one.
- NOT FIXED

### J-114-08: Source comments still name the installed strawberry as 0.324.0

- Severity: minor
- What: four source comments state that an API was verified against the installed 0.324.0: `src/system_03_search_agent/adapters/graphql/security.py` line 12 ("directly against the INSTALLED `strawberry-graphql==0.324.0`"), `schema.py` line 428 ("verified present on strawberry.Schema in the installed 0.324.0"), `context.py` line 15, `tests/system_03_search_agent/adapters/graphql/test_context.py` line 257. The requirements.txt pin no longer says 0.324.0 (pyproject.toml still does, J-114-07).
- Reproduction: `git grep -n "0\.324\.0" -- '*.py'` at 266d35e6 lists exactly those four lines.
- Why a person would care: the next reviewer of a strawberry change reads that the security bounds were checked against a version the pin no longer names. No user effect. My own probe of the bounds on both versions found no behaviour difference (J-114-09).
- NOT FIXED

Addendum to J-114-07 and J-114-06 (read-only Railway CLI, develop environment, service search-agent-api, latest build log and variable names only, no values):

- The deploy build installs `requirements.txt` only: `[6/8] RUN  python -m venv --copies /opt/venv && . /opt/venv/bin/activate && pip install -r requirements.txt`. So develop's next deploy runs 0.327.7; the unsure half of J-114-07 resolves to "deploy fixed, CI and `pip install -e .` not". J-114-07 stays blocking because CI's green on this pull request is evidence about 0.324.0, not about the version being shipped.
- That build installed `litellm-1.104.2`. The API's variable names include `CLASSIFIER_PROVIDER`, `GUARD_MODEL`, `PLAN_MODEL`, `SYNTH_MODEL`, `PER_QUERY_COST_CAP_USD`; no `LITELLM_LOCAL_MODEL_COST_MAP`. So develop takes the fetched upstream map (J-114-06's first case), and this pull request's table is what prices develop's guard, plan and writer.

### J-114-09: Verified, not a defect: strawberry 0.327.7 behaves the same on this project's GraphQL bounds; pip-audit and PyPI metadata match the build report

- Severity: none (verification record)
- What and reproduction:
  - GraphQL unit tests, `pytest -q tests/system_03_search_agent/adapters/graphql -m "not integration"` with the main checkout's .env sourced: 0.327.7 (<scratchpad>/venv-ci) `255 passed, 2 warnings in 5.68s`; 0.324.0 (project venv) `255 passed, 2 warnings in 4.86s`.
  - My own probe executing documents against the real `schema` and reading the real `graphql_router` on each version, outputs diffed: the only differing line is the version line. Shared results: `ROUTER_SETTINGS {'graphql_ide': 'None', 'allow_queries_via_get': 'False', 'subscription_protocols': []}`, `router.protocols []`; introspection refused ("GraphQL introspection has been disabled ..."); 21 aliases refused ("21 aliases found. Allowed: 20"), 20 allowed; over 1,000 tokens refused ("Document contains more than 1000 tokens"); two `ask` fields refused with code `TOO_MANY_RUN_CREATING_FIELDS`; an internal error masked ("This request could not be completed due to an internal error.").
  - Depth bound mutation on 0.327.7 (`MAX_QUERY_DEPTH = 10` to `100`): `80 failed, 44 passed` in test_security.py, so the depth tests are live on the new version. Reverted.
  - `pip-audit -r requirements.txt` in venv-ci: at 266d35e6 `No known vulnerabilities found`; with cffdb8fd's requirements.txt `strawberry-graphql 0.324.0 PYSEC-2026-4302 0.327.2` and `PYSEC-2026-4303 0.326.1`.
  - PyPI JSON: required (non-extra) dependencies identical for 0.324.0 and 0.327.7 (`cross-web>=0.6.0, graphql-core<3.4.0,>=3.2.0, packaging>=23, python-dateutil>=2.7, typing-extensions>=4.14.0`); only difference `libcst` to `libcst>=1.9.0` on the cli and debug extras; 0.327.7 wheel uploaded `2026-09-07T19:36:22.775168Z`, not yanked, no listed vulnerabilities.
- Caveat: all of this is about 0.327.7 where it is actually installed; J-114-07 shows CI does not install it.

## Gates (judge's own run, <scratchpad>/j114 at 266d35e6, project venv)

- `ruff check` (no path): `All checks passed!`, exit 0.
- `isort --check-only --diff src tests services tracker alembic .claude .github`: exit 0, output `Skipped 2 files`.
- Gate 4 exactly (`PYTHONPATH=src`, main checkout .env sourced, `pytest -m "not integration" -q -rs --junitxml=unit-results.xml`): `7635 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 431.06s (0:07:11)`, exit 0. Same counts as build.md. No rerun was needed. Note: the project venv holds strawberry 0.324.0 and litellm 1.93.0, so this run, like CI's (J-114-07), is not a run on 0.327.7.
- Harness tests under litellm 1.105.1 (<scratchpad>/venv-ci), fetched map and bundled map: `566 passed in 24.47s` and `566 passed in 24.17s`. The price tests do not depend on whether litellm's upstream fetch succeeds.
- Gate 6 in venv-ci: `No known vulnerabilities found` (J-114-09).

## Checklist answers

1. Charges: develop (`GUARD_MODEL`, `PLAN_MODEL` deepseek-v4-flash; `SYNTH_MODEL` glm-5.2; no `LITELLM_LOCAL_MODEL_COST_MAP`) takes the fetched upstream map, which has no OpenRouter entries, so deepseek is priced by the table before and after (unchanged); glm-5.2 goes from raising to the table's price (J-114-05 on whether that price is real). Jev is charged from its own reported cost and never reaches `_price_per_token`. Only Opus changes among tabled models (zero to table). A ":free" or any untabled model litellm maps at zero stays free and does not raise (J-114-02 probe; M3 in J-114-04). A one-sided zero is not handled (J-114-02).
2. Stale statements: J-114-01, J-114-03, J-114-06, J-114-08.
3. The widening is tiers.py-only, not any file; narrower AST-keyed allowance described in J-114-03.
4. `_free_guard`: its tests check Jev's charge and the cap after an over-ceiling Jev charge; the guard being free is a fixture convenience so the total equals Jev's charge. Emptying the table hides nothing those tests are meant to check (M5 shows the only effect is the guard's 0.0000028 appearing in the total). It does model a world (deepseek mapped at zero and free) that can no longer occur, which is acceptable for a fixture.
5. J-114-09 (verified), with the caveat of J-114-07.
6. J-114-04 (ticket A) and J-114-09 (ticket B: the old pin goes red in pip-audit; the depth bound mutation goes red on 0.327.7).
7. Above.
8. For a person asking a question on develop after its next deploy: the writer is priced instead of raising, the deploy installs strawberry 0.327.7, and no GraphQL behaviour changed. Nothing is worse than develop for them. What is worse than claimed is the evidence: CI tested 0.324.0, and the glm-5.2 price is not today's catalogue price.

## Verified by my own probes versus only read

- Probed: every price row in J-114-02, J-114-05, J-114-06; the mutations in J-114-04; the scan scope in J-114-03; strawberry behaviour, pip-audit, PyPI metadata in J-114-09; CI's downgrade in J-114-07 (dry run and the pull request's own CI log); develop's install command, litellm version and variable names (Railway build log, names only); gates above.
- Read only: that the Jev path never calls `_price_per_token` (grep of jev_client.py and harness.py, no run); that production's table carries the same glm-5.2 values (`git show origin/production:...tiers.py`); the supply-chain compromise search in build.md (not repeated).

## Learnings

- litellm's default import fetches its price map from GitHub, and the upstream file currently has no `openrouter/` entries while the installed package's bundled map has 486. A price that "litellm no longer carries" may be missing only from the fetched file. Probe with and without `LITELLM_LOCAL_MODEL_COST_MAP=True` before concluding which.
- A dependency pinned in both `requirements.txt` and `pyproject.toml` must move in both; CI's `pip install -e ".[dev]"` after `-r requirements.txt` silently restores the `pyproject.toml` pin, and gate 6 audits only the file.

## Verdict

FIX FIRST: J-114-07 (move `pyproject.toml`'s strawberry pin to 0.327.7 so CI and `pip install -e .` run the fixed version). Recommended in the same fix round: J-114-05 (re-read glm-5.2's price from the catalogue), J-114-01 item 1 (tiers.py line 66 contradicts line 147). The rest are minor. No finding sits inside a fix made during an earlier round of this card; J-114-07 sits inside this card's own commit 266d35e6.
