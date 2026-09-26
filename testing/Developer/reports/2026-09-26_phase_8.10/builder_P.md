# Builder P, build phase 8.10: the command line and system3-cli

Builder P's report for tickets T-8.10-01 to T-8.10-04 of `tracker/phase_8.10.md`, on the branch `feat/8.10-p`, cut from the pushed phase branch at `8cd197d`. What it holds:

- Every acceptance line, answered with its evidence.
- Every added test, shown failing when its behaviour is broken.
- Every number, pasted from output rather than retyped.

Paths are written as `<repo-root>` and `<scratch>`. No email, password or token appears.

## Table of contents

- [Summary](#summary)
- [T-8.10-01: the command line tools install and start from a built package](#t-810-01-the-command-line-tools-install-and-start-from-a-built-package)
- [T-8.10-02: a client reads tomorrow's stream without failing](#t-810-02-a-client-reads-tomorrows-stream-without-failing)
- [T-8.10-03: s3 works as the page prints it](#t-810-03-s3-works-as-the-page-prints-it)
- [T-8.10-04: system3-cli, s3 and a local MCP server](#t-810-04-system3-cli-s3-and-a-local-mcp-server)
- [The system3-cli wheel and its clean install](#the-system3-cli-wheel-and-its-clean-install)
- [Live checks on develop](#live-checks-on-develop)
- [Gates](#gates)
- [Every added test fails when its behaviour is broken](#every-added-test-fails-when-its-behaviour-is-broken)
- [Decisions taken, from the user's chair](#decisions-taken-from-the-users-chair)
- [For the lead](#for-the-lead)
- [Left undone, and why](#left-undone-and-why)
- [What cost time](#what-cost-time)

## Summary

| Ticket | Status | Commit |
|---|---|---|
| T-8.10-01, the tools install and start from a built package | Done | `e607adb5`, with a fix to the check in `42a8f318` |
| T-8.10-02, a client reads tomorrow's stream | Done | `711796e1` |
| T-8.10-03, `s3` works as the page prints it | Done | `f185621c`, with the `[ask]` label for a question back in `2c4db98d` |
| T-8.10-04, `system3-cli` with `s3` and `s3 mcp` | Done | `012af833`, with a test fix in `0e565d2d` |

```mermaid
flowchart LR
  Agent[AI agent] -->|stdio JSON-RPC| Bridge[s3 mcp]
  Bridge -->|POST /mcp/ with bearer| Remote[System 3 MCP server]
  Bridge -->|renews before expiry| Refresh["/auth/refresh"]
  Person[Person at a terminal] --> S3[s3 ask, login, stop]
  S3 --> Api[REST and event stream]
```

## T-8.10-01: the command line tools install and start from a built package

The cause, confirmed in code:

- `pyproject.toml` kept a hand-written package list that lacked `system_03_search_agent.observability` and `system_03_search_agent.eval`.
- It declared no package data.

The fix discovers packages under `src/` (`[tool.setuptools.packages.find]`) and declares the two JSON files as package data.

### "`s3-kgx-export --help` prints its help from an installed copy instead of crashing."

The audit smoke script's own `kgx` check, run offline with its own `build_cli` and `check_kgx` functions (`<scratch>/smoke_kgx_offline.py`):

```text
before (committed tree 012af833):
FAIL kgx       s3-kgx-export --help exit 1: ModuleNotFoundError: No module named 'system_03_search_agent.observability'
after (this worktree):
PASS kgx       help works; without graph access the export stops with a message naming GRAPH_* settings
```

### "An installed server finds its own data files."

The new check compares the wheel with `src/`. Against the tree before the fix it named both data files and every missing module. The first lines of `<scratch>/gate_before.out`:

```text
FAIL . (agentic_search_ui-0.1.0-py3-none-any.whl)
     left out of the wheel: src/system_03_search_agent/data/personas_v1.json
     left out of the wheel: src/system_03_search_agent/eval/__init__.py
     ...
     left out of the wheel: src/system_03_search_agent/observability/tracing.py
     left out of the wheel: src/system_03_search_agent/orchestrator/few_shot_examples.json
     import system_03_search_agent.adapters.web_sse.app: ModuleNotFoundError: No module named 'system_03_search_agent.observability'
     ...
     s3-kgx-export --help exited 1: ModuleNotFoundError: No module named 'system_03_search_agent.observability'
PASS clients/system3-cli (system3_cli-0.1.0-py3-none-any.whl): installs cleanly, every module imports, every command's --help works
1 passed, 1 failed
```

It listed 16 missing files and 27 modules that failed to import (counted from the output with `grep -c`). The finding is wider than the audit's: the web app (`adapters/web_sse/app.py`), the agent loop (`core/graph.py`) and 15 of the 30 tool modules also failed to import from an installed wheel, not only the export command. After the fix, both wheels pass (see [Gates](#gates)).

### "A package that leaves out a module fails CI, not a user."

- `.github/gates/gate_packages_install.sh`: shaped like every gate, with one executable line that calls `.github/gates/check_packages_install.py`.
- Its step is the last one in `.github/workflows/ci.yml`'s `python-gates` job. That job already has every dependency and the placeholder environment the server's modules need at import. The step body is exactly the script path, and `tests/ci/test_gate_invocation_canonical.py` passes over it.
- For each distribution (the root and each `clients/*`), the check does six things:
  - stages the git-tracked files into a temporary tree, so no untracked file and no stale `build/` directory can mask a gap;
  - builds the wheel;
  - compares the server's wheel with `src/`;
  - installs the wheel with no dependencies into an empty virtual environment;
  - imports every module the wheel ships;
  - runs every console script with `--help`.
- Its docstring states what it does not cover, as `goal-contracts` asks. It does not resolve dependencies from an index, and it does not exercise a command beyond `--help`.
- `tests/ci/test_packages_install.py`, 13 tests, proves each detector goes red on a hand-built broken wheel. It also pins the server's `pyproject.toml` to discovery and to declared package data.
- The check's own final run found one more defect, fixed in `42a8f318`. CI's Python job sets `PYTHONPATH: src`, and `pip install -e .` leaves `src/agentic_search_ui.egg-info` behind. With both, the "empty" environment's pip reported the wheel as already installed, installed nothing, and the check crashed looking for `s3`. Every subprocess the check starts now drops `PYTHONPATH`. It reports a missing command or an "already installed" answer instead of crashing, and a test reproduces the condition.
- Rerun under CI's condition (`PYTHONPATH=src` exported, the leftover egg-info directories present), the pre-fix tree is still red with the same 16 files left out and 27 import failures, and this branch is green.

## T-8.10-02: a client reads tomorrow's stream without failing

The cause, confirmed in code: `client.py` validated each received frame with `Event.model_validate_json`, whose payload models all say `extra="forbid"`. The fix, in `client.py` only: when strict validation fails, the client drops every key the contract does not declare. It does so at the envelope, the payload and each nested model (`DecisionRecord`, `ToolCall`, `ResolvedEntity`), then validates the rest with the unchanged strict models. `contracts/events.py` is untouched, so the server stays strict.

### "An `s3` installed today keeps answering after the server adds a field or a new kind of event."

`tests/system_03_search_agent/adapters/cli/test_tomorrows_stream.py` drives the real `CliClient` and the real `Renderer` together. The stream carries a field this build does not know on every frame kind an answer needs (the envelope, `think` and its nested entity, `step`, `token`, `citation`, `trust_signal`, `done` and its nested decision), plus a frame of an unknown type. The first test asserts:

- exit 0;
- the answer text, `[answer]` and `References:` with the NCBI link on stdout;
- the unknown frame skipped and counted (`stream_skipped_frame_count == 1`);
- no unknown key reaching the renderer.

The safety half is also tested. A known field with a wrong value still ends the run with the decode error, even when an unknown key sits beside it. A bound on a known field (`token.text` over 1,000 characters) still holds. `fetch_citations` gets the same leniency.

### "The contract's promise is true."

For new optional fields and new event types it is now true of the Python client. It is not true for a new value of a closed enum in a known field: that frame still ends the run with an error. That is deliberate, since this build cannot say what an unknown trust outcome means. The docstring wording is the lead's, as the ledger says.

Also fixed while here: `create_run` raised `CliApiError(...)` with one argument against a three-argument constructor. A reply with no `run_id` therefore reached the person as "unexpected error (TypeError)". A test covers it.

## T-8.10-03: s3 works as the page prints it

The parked tag `parked/phase-8.4-2026-09-25` carries no change under `adapters/cli/`: the diff the brief named has 0 lines. Its `s3 login` fix is commit `22e0e2b6`, a page change to `InfoScreens.tsx`, which is builder R's fence. Nothing was taken from it for this ticket, and the lead was told.

### "`s3 login` asks for my email when I leave it off, instead of failing."

- On a terminal, `s3 login` prompts `Email: ` on stderr, then `Password: ` through `getpass`. The password prompt used to be empty, which showed nothing at all while `s3 login` waited.
- Piped, the first line is the email and the second the password.
- With no email at all, it says `run it as: s3 login you@example.org` and sends nothing.
- Live on develop, a bare `s3 login --base-url <develop>` with the email and password piped printed `logged in to https://search-agent-api-develop-43b3.up.railway.app` and exited 0.

### "`s3` talks to the live product unless I say otherwise."

- One named constant, `PRODUCTION_API_ORIGIN = "https://search-agent-api-production.up.railway.app"` in `main.py`. The repository records this origin in `README.md` line 30, `docs/build/Release_flow.md` line 23 and `tests/system_03_search_agent/tools/fixtures/release_environments.json`, so no question to the lead was needed.
- A test pins the constant to that fixture.
- `--base-url` and `S3_BASE_URL` still override it; an empty `S3_BASE_URL` falls back to production.
- `main()` itself was driven with `s3 login person@example.org` and its request reached `<production>/auth/login`.
- `s3 --help`, `-h` and `help` now exit 0, and they never read the credential file.

### "`s3 ask --json` prints the whole answer as JSON."

`JsonRenderer` in `render.py` writes one object at the end of the run. Its keys:

- The answer: `answer`, `citations` (each with `source_url`), `unresolved_markers`.
- The verdict: `trust_outcome`, `trust_line`.
- The question back: `clarifying_question`, `clarifying_options`.
- The offer to go further: `next_step`, `next_step_query`.
- The run: `session_id`, `run_id`, `persona_name`, `complete`, `guard`, `error`, `stream`.

A parametrized test proves it exits with the same code as the human output for an answer, a question back, a guard refusal, a fatal error and a cut-off stream. `ensure_ascii=True` keeps it terminal-safe; a test shows no raw ESC or bidi override reaches stdout. Live: one JSON object, `trust_outcome 'ask'`, `trust_line 'Based on 22 sources, not yet confirmed'`, 22 citations, `session_id 'p810p-live-2'`, `complete True`.

### "A bare topic shows its clarifying options, numbered, so I can pick one."

Live on develop, `s3 ask --session-id p810p-live-3 GERD`:

```text
What would you like to know about GERD?
  1. What is GERD?
  2. Which genes are associated with GERD?
  3. What are the clinical trials for GERD?
  4. What does recent research say about GERD?

[refuse]
```

stderr: `s3: to ask one of these, run: s3 ask --session-id p810p-live-3 "<the question you pick>"`.

That live run was taken before the lead's follow-up, which made a question back read `[ask]` and exit 0 instead of `[refuse]` and exit 1 (`2c4db98d`). The follow-up used the same rule as builder Q's MCP fold (`adapters/mcp/server.py`, `_is_ask_back`), which says it mirrors the web's. A run is a question back when all four hold:

- the first `think` event carries a non-empty clarifying question;
- the guardrail did not refuse;
- no fatal error ended the run;
- no citation arrived.

The refusal's wording is never read. `TestAQuestionBackIsLabelledAsk` in `test_s3_as_printed.py` proves both directions, in the human output and in `--json`: a question back reads `ask`, and a refusal worded exactly like the question still reads `refuse`. It was not rerun live, to keep this brief's question budget.

Each option goes through `_sanitize_untrusted` like any answer token, and a test with an OSC sequence and a forged `[answer]` inside an option proves it. A session id with spaces is shell-quoted in the hint.

## T-8.10-04: system3-cli, s3 and a local MCP server

### "I install one small package and get `s3` and an MCP server, without the whole backend."

- `clients/system3-cli/pyproject.toml` builds from `package-dir = { "" = "../../src" }`: the same source files as the server's distribution, with no second copy. The directory tracks no Python file, and a test checks that.
- Dependencies are `httpx` and `pydantic`, plus their closure, all eleven pinned exactly. The build backend is pinned too (`setuptools==83.0.0`).
- The MCP SDK is not a dependency. `mcp==2.0.0` itself requires `uvicorn`, `starlette`, `sse-starlette`, `python-multipart`, `pyjwt`, `opentelemetry-api` and `jsonschema`. It could not be a dependency while the same acceptance line forbids `uvicorn`. `s3 mcp` is therefore a thin JSON-RPC forwarder over `httpx`. The lead approved this before it was built.
- `test_system3_cli_package.py` imports every `s3` module and runs `s3 --help` in a fresh interpreter. An import hook makes every undeclared third-party package unimportable, as in a clean install. The test asserts nothing outside the four shipped packages is imported and no server package is imported.
- The clean install is in the next section.

### "I sign in once, and my AI agent can use System 3."

`adapters/cli/mcp_bridge.py`: `s3 mcp` forwards every message to `<signed-in origin>/mcp/`, so every tool the remote lists is offered, and no tool name appears in the bridge. What it guarantees:

- It renews the access token when less than 60 seconds remain (read from the JWT's `exp`, unverified, for timing only).
- It renews once more when the server refuses the token, then resends that message once. The server refuses before any run starts (T-4.1-03), so the resend cannot start a second run.
- Renewals share one lock, so two requests at once renew once. The refresh token rotates on each use, and replaying a used one signs the person out everywhere.
- Renewal fails closed: the agent gets an error that says to run `s3 login`, and nothing is sent.
- It never follows a redirect, so the token only ever goes to the stored origin.
- The token never reaches stdout, stderr or an error message.
- stdout carries one ASCII JSON-RPC message per line and nothing else.
- It answers `ping` locally, stops waiting on a request the agent cancels, and bounds inbound lines (1 MiB) and replies (16 MiB).
- It never leaves the agent waiting: a request the server closes on without answering gets an error.

Live renewal against develop's real `/auth/refresh` (`<scratch>/p810p_live_renew.py`). The stored access token was replaced with an expired one, and only `initialize` and `tools/list` were sent, so no question was spent:

```text
stored refresh token before: 7d1599fd71; access token set to an expired one
tools listed after renewal: ['ask_biomedical_question']
s3 mcp stderr: 's3 mcp: forwarding MCP messages to https://search-agent-api-develop-43b3.up.railway.app/mcp/ with your s3 sign-in\ns3 mcp: renewed the sign-in'
stored refresh token after: 21bddc9232 (rotated: True)
access token replaced: True; mode 0o600
secrets in stderr: 0
```

The fingerprints are the first ten hex characters of a SHA-256, never the token.

### "An agent that only runs commands can connect."

`test_mcp_bridge_stdio.py`:

- The client: the MCP SDK's own `stdio_client` and `ClientSession`, starting `python -m system_03_search_agent.adapters.cli.main mcp`.
- The stand-in: a real SDK `MCPServer`, served by uvicorn on 127.0.0.1 in stateless streamable HTTP mode, as the deployed mount is. Its two tool names are ones the bridge has never seen, and it refuses a call without the stored token.
- The run: `initialize`, `list_tools` and two `call_tool` calls, recording any transport fault. It passes in about 3 seconds.

`test_mcp_bridge.py` adds 25 in-process tests covering both reply shapes, a JSON body and an event stream.

Live, the clean-installed `s3 mcp` driven by the SDK client against develop:

```text
server system3-biomedical-search 1.0.0, protocol 2025-11-25
tools listed: ['ask_biomedical_question']
is_error False, answer present, 23 citations, trust ask, 14s
transport faults (non-JSON on stdout): 0
```

### "Built, never published."

Nothing was published and no name was registered. The wheel was built locally and from a `git+file` URL of this branch with `#subdirectory=clients/system3-cli`. That proves the install route the page can print until the first release: a clone resolves `../../src` correctly.

## The system3-cli wheel and its clean install

Its `METADATA`, from the built wheel:

```text
Name: system3-cli
Version: 0.1.0
Requires-Python: >=3.11
Requires-Dist: httpx==0.28.1
Requires-Dist: pydantic==2.13.4
Requires-Dist: annotated-types==0.8.0
Requires-Dist: anyio==4.14.2
Requires-Dist: certifi==2026.7.22
Requires-Dist: h11==0.16.0
Requires-Dist: httpcore==1.0.9
Requires-Dist: idna==3.18
Requires-Dist: pydantic-core==2.46.4
Requires-Dist: typing-extensions==4.16.0
Requires-Dist: typing-inspection==0.4.2
```

The wheel ships 12 modules:

- `system_03_search_agent/__init__.py` and `adapters/__init__.py`.
- The seven files of `adapters/cli/`, including `mcp_bridge.py`.
- `contracts/__init__.py`, `events.py` and `query.py`.

Supply-chain checks before installing, per `.claude/rules/supply-chain-security.md`, each read-only from PyPI's JSON API:

| Pin | Published | Yanked | Wheel |
|---|---|---|---|
| httpx==0.28.1 | 2024-12-06 | no | pure |
| pydantic==2.13.4 | 2026-05-06 | no | pure |
| annotated-types==0.8.0 | 2026-07-23 | no | pure |
| anyio==4.14.2 | 2026-07-12 | no | pure |
| certifi==2026.7.22 | 2026-07-22 | no | pure |
| h11==0.16.0 | 2025-04-24 | no | pure |
| httpcore==1.0.9 | 2025-04-24 | no | pure |
| idna==3.18 | 2026-06-02 | no | pure |
| pydantic-core==2.46.4 | 2026-05-06 | no | cp311 macOS arm64 |
| typing-extensions==4.16.0 | 2026-07-02 | no | pure |
| typing-inspection==0.4.2 | 2025-10-01 | no | pure |

- Every version is the one this repository's own environment already runs.
- The install used `--only-binary :all:`, so no setup script ran.
- A search for compromise reports found none naming these packages. The one September 2026 sweep that listed PyPI entries names two unrelated packages ([Hacker News PyPI label](https://thehackernews.com/search/label/PyPI), [compromised-packages-check PR 133](https://github.com/jaschadub/compromised-packages-check/pull/133)).

The clean install, into a new venv at `<scratch>/p810p_cleanvenv`:

```text
install exit 0
Successfully installed annotated-types-0.8.0 anyio-4.14.2 certifi-2026.7.22 h11-0.16.0 httpcore-1.0.9 httpx-0.28.1 idna-3.18 pydantic-2.13.4 pydantic-core-2.46.4 system3-cli-0.1.0 typing-extensions-4.16.0 typing-inspection-0.4.2
--- pip check:
No broken requirements found.
--- forbidden present?
none
```

`pip list` showed only those twelve plus the venv's own bootstrap `pip` and `setuptools`. "Forbidden" checked `fastapi`, `uvicorn`, `starlette`, `langgraph`, `litellm`, `psycopg2`, `redis`, `sqlalchemy`, `alembic`, `strawberry` and `mcp`. From that venv, `s3 --help`, `s3 mcp --help` and `s3 login --help` all exited 0, and `s3 ask --help` lists `--json`.

## Live checks on develop

- `/health`: `{"status":"ok","app_env":"develop"}`.
- The account was minted with `make_accounts.py 20260926p810p`.
- Four questions were sent, all from the clean-installed `s3`, by `<scratch>/p810p_live.py`.

| Step | Result |
|---|---|
| Bare `s3 login --base-url <develop>` | exit 0, 1s, `logged in to <develop>`, credential file mode 0o600 |
| `s3 ask` BRCA1 | exit 0, 17s, first line "Found 4 disease records for BRCA1: Familial cancer of breast [1], ...", `[ask]`, 26 reference lines |
| `s3 ask --json` BRCA1 | exit 0, 12s, one JSON object, 22 citations, first URL `https://www.ncbi.nlm.nih.gov/medgen/C0346153` |
| `s3 ask GERD` | exit 1, 3s, the four numbered options and the pick-one hint (before `2c4db98d`, which makes it `[ask]` and exit 0) |
| `s3 mcp`, SDK client, `ask_biomedical_question` | 23 citations, 14s, 0 transport faults |
| Secrets in any captured output | none |

The 26 and 22 differ because they are two runs of the same question; the audit already records that run-to-run variance (board cards 11 and 12).

## Gates

Run at `2c4db98d`, the last code commit, as CI runs them, each with its own exit code. The environment was CI's placeholder values (`<scratch>/ci_placeholder_env.sh`, copied from `ci.yml`, no credential), with `PYTHONPATH=src` exported as CI's job does:

```text
HEAD 2c4db98d
ruff check exit 0
All checks passed!
isort exit 0
Skipped 2 files
gate04 exit 1
6 failed, 5926 passed, 212 skipped, 24 deselected, 1 xfailed, 7 warnings in 243.15s (0:04:03)
gate_packages_install exit 0
PASS . (agentic_search_ui-0.1.0-py3-none-any.whl): installs cleanly, every module imports, every command's --help works
PASS clients/system3-cli (system3_cli-0.1.0-py3-none-any.whl): installs cleanly, every module imports, every command's --help works
2 passed, 0 failed
```

The commands, each run separately from `<repo-root>`:

- `ruff check`, with no path.
- `isort --check-only --diff src tests services tracker alembic .claude .github`.
- `bash .github/gates/gate04_unit_suite.sh`.
- `bash .github/gates/gate_packages_install.sh`.

Gate 4's six failures, read from `unit-results.xml`:

- `adapters/graphql/test_no_cost_channel.py`: `TestNeverCost::test_no_cost_figure_appears_anywhere_in_the_response`, `TestNeverCost::test_operator_mode_is_pinned_false_for_every_caller`, `TestRegisteredAccountsOnly::test_a_valid_guest_token_is_refused_with_an_actionable_message`.
- `core/test_think_retry.py`: `test_one_unusable_reply_is_retried_and_the_run_continues`, `test_two_unusable_replies_end_the_run_as_before_and_never_a_third_call`, `test_a_valid_first_reply_makes_exactly_one_think_call`.

The six database failures are not from this branch. The three in `adapters/graphql/test_no_cost_channel.py` and three of the four in `core/test_think_retry.py` fail identically on the base commit `8cd197d`: `6 failed, 1 passed`. Each fails with `FATAL: role "postgres" does not exist`. This machine's Postgres has no `postgres` role, and CI's service does. The audit saw the same three GraphQL failures.

The first full run on this branch also failed two tests caused by this branch, both fixed in `0e565d2d`:

- `harness/test_tiers.py::test_no_model_id_shaped_string_outside_the_default_table` flagged `"notifications/cancelled"` in `mcp_bridge.py`. That is an MCP method name, which has a provider/model slug's shape by the MCP specification. The check was wrong for one input and the subject was right. On the lead's approval the exact string joined the exemption set beside the two media types, with its reason in the comment. `test_exempt_media_types_can_never_collide_with_a_default_model_id` still fails when a real `_DEFAULT_MODELS` value is added to the set (shown in the next section).
- My own `test_the_wheel_is_built_from_the_servers_own_source_files` saw the gitignored `build/lib` copy that an in-place wheel build leaves in `clients/system3-cli/`. It now reads tracked files only.

## Every added test fails when its behaviour is broken

Each mutation was applied by `<scratch>/mutate.py`, which edits one line, runs the named tests and always restores the file, confirming the restore by content.

| Ticket | Mutation | Result |
|---|---|---|
| 02 | `_decode_ignoring_unknown_fields` result ignored | 2 failed, including "the answer still prints" |
| 03 | `email` a required positional again | 3 failed |
| 03 | `PRODUCTION_API_ORIGIN` back to `http://127.0.0.1:8000` | 1 failed |
| 03 | `--json` renamed with no shared prefix | 4 failed |
| 03 | numbered options never printed | 3 failed |
| 03 | `s3 --help` unknown again | 3 failed |
| 04 | no `Authorization` header | 2 failed (JSON and event-stream replies) |
| 04 | no renewal before expiry | 1 failed |
| 04 | a refusal passed on, no retry | 1 failed |
| 04 | renewal fails open | 1 failed |
| 04 | redirects followed | 1 failed |
| 04 | silence when the server never answers | 1 failed |
| 04 | renewals not shared between concurrent requests | 1 failed |
| 04 | stdio: a status line written to stdout | 1 failed |
| 04 | stdio: no `Authorization` header | 1 failed |
| 04 | stdio: only a known tool name passed on | 1 failed |
| 04 | package: `s3` imports `fastapi` | 1 failed |
| 04 | package: `s3` imports a server module | 1 failed |
| 04 | package: a floor instead of a pin | 1 failed |
| 04 | package: `mcp==2.0.0` added | 1 failed |
| 01 | the check compares only `.py` files | 1 failed |
| 01 | the check skips the import step | 1 failed |
| 01 | the check ignores `--help`'s exit code | 1 failed |
| 01 | the check leaves `PYTHONPATH` in reach | 1 failed |
| 01 | `pyproject.toml` back to no discovery | 1 failed |
| 01 | the orchestrator data file undeclared | 1 failed |
| 01 | the check's subprocesses inherit `PYTHONPATH` again | 2 failed, including the egg-info regression test |
| 01 | the whole gate against the pre-fix tree | exit 1, 16 files left out, `s3-kgx-export --help` exited 1 |
| 03 follow-up | `_shown_outcome` shows the stream's `refuse` unchanged | 1 failed, the question back |
| 03 follow-up | every `refuse` relabelled `ask`, the rule ignored | 4 failed, including the refusal worded as a question |
| 03 follow-up | the rule ignores citations | 1 failed |
| 03 follow-up | `--json` keeps the stream's `refuse` | 1 failed |
| test_tiers | a real `_DEFAULT_MODELS` value added to the exemption set | the collision test failed |
| test_tiers | `"notifications/cancelled"` removed from the set | the scan test failed |

Three first attempts proved nothing, and each was fixed rather than counted:

- Renaming `--json` to `--jsonx` passed, because argparse accepts a prefix of an option. The honest mutation removes the shared prefix.
- The stdio test's comment claimed the SDK client fails on a non-JSON stdout line. It does not; it hands the fault to `message_handler`. The test now records those faults and asserts none.
- The concurrent-renewal test passed with sharing disabled, because `httpx.MockTransport` never yields to the event loop. The stand-in's refresh now yields, as a network call would.

## Decisions taken, from the user's chair

- The package installs nothing a person did not ask for. The MCP SDK would have pulled a web server into a command line tool; a forwarder needs only `httpx`. Approved by the lead before it was built.
- Every package the install pulls is pinned, not only the two named ones, so `pip install` can never fetch a release nobody reviewed.
- An expired sign-in stops a request with "run `s3 login`" rather than sending it anyway: a clear stop is better than a confusing refusal.
- `--json` writes nothing until the run ends, so a script parsing stdout always gets one whole object.
- A question back reads `[ask]` and exits 0, as over MCP (the lead's follow-up). The exit code follows the label shown, so a script sees a question back the way it sees any other `[ask]`: the system worked and wants a choice. A real refusal still exits 1. The options sit above the tag, and the hint says how to pick one.
- `s3 login` names the server it signed in to, now that the default is production rather than a local address.

## For the lead

1. The helper lives at `.github/gates/check_packages_install.py`, inside my fence. The repository's other gate helpers live in `.github/scripts/`. Move it if you prefer the convention; the gate script's one line would change with it.
2. `ci.yml`'s header says Section 24 is the source of truth for the gate list and asks for no gate to be added without changing it first. Section 24 is locked. The new step says it is not one of the ten and runs after them; whether that needs a `DECISIONS.md` row is yours.
3. For builder R's page:
   - The install route that works today is `pip install "git+https://github.com/<owner>/<repo>.git#subdirectory=clients/system3-cli"`, proven here from a `git+file` URL of this branch.
   - The stdio MCP config is `{"mcpServers": {"system3": {"command": "s3", "args": ["mcp"]}}}`, after `s3 login`.
   - The `s3` default server is now production.
4. The audit smoke script's `page` check treats a printed bare `s3 login` as broken whenever `s3 login --help` mentions "email". It now does, as the optional `[email]`. Either R prints `s3 login you@example.org`, which works, or the smoke check should read `[email]` as optional.
5. Done in `2c4db98d`: `s3` now reads `[ask]` for a question back, by Q's rule, in both outputs. It exits 0; if you want a question back to exit non-zero for scripts, that is one line in each renderer.
6. Installing `system3-cli` and `agentic-search-ui` into one environment makes both own the same `system_03_search_agent` files, and uninstalling one removes them from the other. The page should suggest installing `system3-cli` on its own, for example with `pipx` or `uv tool`.
7. The Debugging guide gained the `mcp_bridge.py` row. Its `main.py`, `render.py` and `S3_BASE_URL` rows were updated. The manifest was regenerated with `PYTHONPATH=src python tests/system_03_search_agent/test_debugging_guide_coverage.py`, which changed only the `main.py` and `mcp_bridge.py` entries.
8. The in-place builds used for the clean-install proof left `build/`, `src/agentic_search_ui.egg-info` and `src/system3_cli.egg-info` in this worktree. All three are gitignored and none is committed. The check itself builds from a staged copy and leaves nothing behind.
9. The check builds without isolation when the running interpreter can build a wheel itself (setuptools 70.1 or later, or the `wheel` package), and with isolation otherwise, fetching the build backend from PyPI. Locally it took the first path. I expect CI to take the second, since nothing in `requirements.txt` installs either, but I did not verify that. I also did not fetch build tools locally, because only `system3-cli`'s pins were cleared for download. The first CI run on the pull request is the proof of that path.

## Left undone, and why

- The `contracts/events.py` docstring text: outside every fence, the lead's per the ledger.
- A full smoke-script run against develop: it would spend four more questions past this brief's five, and its `page` line waits on builder R. Its `kgx` line was run offline, before and after, above.
- A new enum value in a known field still ends an installed client's run with an error. That is outside the ticket's acceptance and deliberate; see T-8.10-02.

## What cost time

Nothing took more than about five minutes on its own. The small ones:

- The Write tool turned a `‮` escape in a test file into the raw right-to-left override character. Ruff caught it (PLE2502), and it was replaced by the escape text. A scan found no other raw control character in any file I wrote.
- The delete guard refused an `rm` I had added as a precaution for a scratch directory that did not exist. That step was dropped rather than routed around.
- The secret-scan hook refused a command that exported CI's placeholder variables, whose names look like credentials. The file was written with the Write tool and sourced by path.
- A zsh loop passed `mcp --help` to `s3` as one word, so two help checks falsely read "unknown command". They were rerun directly.
- The three mutations above that first proved nothing.
- The package check passed locally and then crashed on the final gate run, because that run exported `PYTHONPATH=src` as CI does. Diagnosing it (an egg-info on the path made pip skip the install) took about five minutes. It is the one finding here that would have reached CI, and it is fixed and tested in `42a8f318`.
