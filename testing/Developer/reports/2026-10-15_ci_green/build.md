# CI green: build report, 2026-10-15

Base: cffdb8fd2d96968a62518d5eded1ecbefed34a15 on fix/ci-model-prices-and-strawberry.

## Table of contents

- [Ticket A: model prices](#ticket-a-model-prices)
- [Ticket B: strawberry-graphql 0.327.7](#ticket-b-strawberry-graphql-03277)
- [Gates](#gates)
- [Learnings](#learnings)

## Ticket A: model prices

Files: src/system_03_search_agent/harness/tiers.py, src/system_03_search_agent/harness/harness.py, tests/system_03_search_agent/harness/test_opus_writer.py, plus two test files outside the stated list (see below): test_tiers.py, test_decide.py.

Price per token, input and output, before and after:

| Model | litellm map | Fallback table | Before | After |
|---|---|---|---|---|
| anthropic/claude-opus-5.5 | (0, 0) | (4e-06, 2e-05) | (0, 0) | (4e-06, 2e-05) |
| deepseek/deepseek-v4-flash | no entry | (1.4e-07, 2.8e-07) | same | same |
| moonshotai/kimi-k2.6 | no entry | (6.46e-07, 2.72e-06) | same | same |
| z-ai/glm-5.2 | no entry | (7.182e-07, 2.2572e-06), restored | raises HarnessCallError | (7.182e-07, 2.2572e-06) |
| typesafe/jev-1.13 | no entry | none | raises | raises (Jev is charged by its own reported cost) |

Only Opus changes price among the priced models; glm-5.2 goes from raising to priced.

Mutations (test_opus_writer.py):

- Remove the glm entry: test_the_rollback_writer_glm_5_2_is_priced_when_litellm_has_no_entry goes red (2 failed, 31 passed).
- Drop the zero check: test_a_model_litellm_maps_at_zero_gets_the_tables_price goes red (1 failed, 32 passed).
- Restored: 33 passed.

Two edits outside the stated file list were needed, both forced by the change:

- test_tiers.py, test_no_model_id_shaped_string_outside_the_default_table: it allowed a model id in tiers.py only as a _DEFAULT_MODELS value, so the restored glm key failed it. It now also allows the keys of the fallback price table (priced by identity, in tiers.py only).
- test_decide.py, _free_guard: it mocked litellm at zero for the guard model (deepseek, in the table) and expected a free guard. With the zero rule the table price applies (5 tests failed at 0.0001028 against 0.0001). The helper now empties the table so the guard is free as its name says.

## Ticket B: strawberry-graphql 0.327.7

Files: requirements.txt (pin and its comment).

Supply-chain steps (.claude/rules/supply-chain-security.md, PyPI):

1. Compromise search ("strawberry-graphql pypi malware", "strawberry-graphql compromised", WebSearch): one malware record, MAL-2026-4771, for version 0.315.6 only (it added a cross-web dependency in place of python-multipart), withdrawn 2026-05-26. Nothing about 0.327.7. Other hits are old CVEs fixed long before 0.324.0.
2. PyPI JSON: 0.327.7 uploaded 2026-09-07T19:36:22Z (wheel) and 19:36:24Z (sdist); 0.324.0 uploaded 2026-08-10. Required dependencies are identical (cross-web>=0.6.0, graphql-core<3.4.0,>=3.2.0, packaging>=23, python-dateutil>=2.7, typing-extensions>=4.14.0). cross-web was already required by 0.324.0. Only change: the unused cli and debug extras went from "libcst" to "libcst>=1.9.0". No new or widened transitive dependency.
3. pip download --no-deps: strawberry_graphql-0.327.7-py3-none-any.whl, 307 files, no setup.py, no .pth, Generator uv 0.12.10. A wheel, so nothing runs at install.
4. Scratch venv, project requirements with the new pin, pip-audit -r requirements.txt: "No known vulnerabilities found". Installed: strawberry-graphql 0.327.7, cross-web 0.7.0, graphql-core 3.2.11.

GraphQL checks in the scratch venv with 0.327.7:

- Imported types, schema, context, security, router: all import.
- tests/system_03_search_agent/adapters/graphql: 255 passed, 2 warnings. test_security.py (the security settings) passes unchanged.
- Warnings: two DeprecationWarning lines, "Passing a class to strawberry.scalar() is deprecated" at types.py:635 (AskText) and :641 (AskSessionId). Both are identical on 0.324.0 in the main venv (same 255 passed, same 2 warnings), so none is new. No GraphQL code changed.

## Gates

Main venv, from the worktree:

- ruff check (no path): All checks passed!
- isort --check-only (gate 2's full command, all paths): exit 0.
- pytest tests/system_03_search_agent/harness -m "not integration" -q: 566 passed.
- Full unit suite as gate 4 (pytest -m "not integration" -q -rs): 7635 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 377.91s.
- Gate 6 in the scratch venv (pip-audit -r requirements.txt): No known vulnerabilities found.

## Learnings

- A scratch venv outside the main checkout does not pick up the main checkout's .env: litellm's import-time load_dotenv walks up from its own location. Six graphql tests failed there with "USER_DB_URL is not set" until the .env was sourced. Same tests passed 255 of 255 once it was, and failed identically on 0.324.0 under a wrong credential, so it was the environment, not the version.
- The bash hook blocks any rm, so the scratch venv could not be removed by the builder.
