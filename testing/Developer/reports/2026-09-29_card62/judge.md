# Card 62 judge report, 2026-09-29

Judge, one round, of branch `fix/card62-install-first-try` (commits 731ac19a, b09559a3, 47929be9, bc898f39, 4f749a7f, 30cd9106). Local probes only; no request to deployed develop or production.

## Findings

### F-62-J01: the copied install still fails with the same setuptools error on a stock Mac, because it runs `python3`
- Severity: should-fix
- Where: `frontend/src/components/screens/InfoScreens.tsx:199` (`INSTALL_EXAMPLE` starts `python3 -m venv s3-env`)
- Evidence: with launchd's default PATH, `python3` is macOS's own interpreter:
  `env -i HOME=$HOME PATH=/usr/bin:/bin:/usr/sbin:/sbin bash -c 'command -v python3; python3 --version'` printed `/usr/bin/python3` and `Python 3.9.6`.
  Running the page's copied install with it (`/usr/bin/python3 -m venv py39 && . py39/bin/activate && pip install <worktree>/clients/system3-cli`, the local path standing in for the git URL) printed `ERROR: No matching distribution found for setuptools==83.0.0`, byte for byte the error PR-8.10-04 reported. pip 21.2.4 in that venv never says "requires Python >=3.11".
- What a user would notice: on a Mac with no newer Python, the three copied lines fail exactly as before the card. The body text now says "Python 3.11 or newer", which is the fix PR-8.10-04 asked for, so a careful reader can recover; but the copied command does nothing to enforce or reveal it, and the error still names setuptools. Candidate: a first line such as `python3 --version` or `python3.11 -m venv`, or a sentence saying the setuptools error means the Python is too old. The owner may accept the text-only fix; recorded because the acceptance is "first try".
### F-62-J02: the new KGX copy tells outsiders to install the server's unpinned dependency closure
- Severity: should-fix
- Where: `frontend/src/components/screens/InfoScreens.tsx:239` (`KGX_EXAMPLE` first line `pip install "git+https://github.com/monideep2255/agentic-search-ui.git"`); `pyproject.toml:17-45` (every server dependency is a floor: `"litellm>=1.40"`, `"anthropic>=0.34"`, `"fastapi>=0.111"`, ...)
- Evidence: running that install (local worktree path standing in for the git URL) into a fresh Python 3.11 venv took 34 s, exit 0, and pip resolved about 100 packages to whatever was newest today, among them `litellm-1.103.0 anthropic-1.9.0 openai-2.54.0 boto3-1.43.104 huggingface-hub-1.33.0 mcp-2.2.0` (`kgx_install.log` in the judge's scratchpad). `clients/system3-cli/pyproject.toml:15-19` says the opposite policy for the `s3` install: "EVERY DEPENDENCY PINNED EXACTLY ... a floor on a transitive dependency would let `pip install` pull a release nobody reviewed", citing `supply-chain-security.md`.
- What a user would notice: nothing on the day. The risk is that the page now hands every outside reader a floor-pinned install of an LLM-provider stack (litellm had a live PyPI compromise window this year) to reach one exporter they cannot run without operator-granted graph credentials anyway. Before the card the page printed no such install. Candidate: say `s3-kgx-export` is operator-only and drop the copyable install, or point it at a pinned `requirements.txt` install. Owner's call; filed because the card introduced the line.
### F-62-J03: the KGX copy is a standalone bare `pip install`, which only works inside the venv the other copy made
- Severity: note
- Where: `frontend/src/components/screens/InfoScreens.tsx:239-241` (`KGX_EXAMPLE`), `:736` (card body "it comes with the server's own package, the first line of the KGX command")
- Evidence: outside a virtual environment on this Mac, bare `pip` does not exist: `env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin bash -c 'command -v pip || echo "no pip"'` printed `no pip`; with Homebrew first on PATH, `pip --version` printed `bash: pip: command not found`. The KGX copy button gives only the pip line and the export line, no venv lines. Inside the venv the page's install made, it works: `pip install <worktree>` then `s3-kgx-export --help` exit 0 (usage printed), and the page's own `s3-kgx-export NCBIGene:672 --hops 1 --output-dir ./kgx-out` with no credentials printed `s3-kgx-export: graph connection environment variables are not fully set: GRAPH_PG_HOST, GRAPH_PG_USER, GRAPH_PG_PASSWORD, GRAPH_PG_DBNAME must all be set, then retry` (names only, no values; good). `test_every_printed_command_comes_with_the_install_the_page_prints_for_it` models the three copies as one continuous shell ("installed so far"), so it cannot see this.
- What a user would notice: someone who copies only the KGX command, or pastes it in a new terminal, gets `pip: command not found` or `externally-managed-environment`, the PR-8.10-04 failure again. Also, that failed export run left two empty directories, `kgx-out/` and `logs/`, in the reader's current directory (pre-existing behaviour, not this card).
### F-62-J04: on a cut-off run, `s3` invents a trust caution the server never sent, "Single source", under a multi-citation answer
- Severity: should-fix (inside this card's own new code)
- Where: `src/system_03_search_agent/adapters/cli/render.py:1087` (`finish()` now calls `self._write_trust_line(None)`), `:877-879` (an `ask` tag with no line gets `_UNCONFIRMED_WITHOUT_TRUST_LINE`, `:271`)
- Evidence: judge's probe `probe_render.py` (scratchpad), stream guard, token, citation, answer-scope `trust_signal` with `outcome: "ask"`, then the stream ends with no `done` (dropped connection):
  ```
  BRCA1 is linked to breast cancer [1].
  [answer]
  Single source, not independently confirmed

  References:
  [1] ncbi_gene - https://www.ncbi.nlm.nih.gov/gene/672
  --stderr--
  error: the run ended before a final answer was received; any answer text above is incomplete and its citations may be partial.
  ```
  exit 1. The same line also prints when `done.trust_line` is whitespace only (probe C). The web shows no outcome at all when no `done` arrived (`frontend/src/hooks/useRunView.ts:1098`, `done && done.type === "done" ? ... : null`), so this is not parity with the web; it is a caution the CLI composes itself. "Single source" is a factual claim about the evidence; the server's own line for the same state is "Based on N sources, not yet confirmed" (`synthesis/trust.py:624`), and PR-8.10-01's case had 12 citations. The server does send `trust_line` on every `ask` answer it finishes, so the fallback fires mainly on the cut-off path the card wired it into.
- What a user would notice: after a dropped connection, a stdout reader (or an agent parsing stdout) sees `[answer]` plus "Single source, not independently confirmed" above a References block that may list many sources, while stderr says the run did not finish. Candidate: do not print the fallback from `finish()` when no `done` arrived, or word it without a source count.
- Related, noted not filed: a trust line is written with no leading newline guard, so a token arriving after the answer-scope trust signal glues to it (probe D printed ` More text after the tag.Based on 1 source, not yet confirmed`). `core/graph.py:12884-12913` emits the answer trust signal after the last token, so a well-formed stream does not hit it.
### F-62-J05: breaking the trust line's "printed at most once" leaves every test green, and the break prints "Single source" under a 12-source answer
- Severity: should-fix (test gap on this card's new control)
- Where: `src/system_03_search_agent/adapters/cli/render.py:880` (`self._printed_trust_line = True`), `:1087` (`finish()` calls `_write_trust_line(None)` after `done` already called it)
- Evidence: in a scratch copy of the branch (`git archive HEAD`), deleting line 880 and running `tests/system_03_search_agent/adapters/cli`, `adapters/mcp` and `test_integrations_page_claims.py`: `425 passed, 1 deselected` (the deselected test is the LICENSE copy check, which needs files the scratch copy lacks). With that mutation, an `ask` answer whose `done.trust_line` is "Based on 12 sources, not yet confirmed" printed:
  ```
  [answer]
  Based on 12 sources, not yet confirmed

  References:
  [1] ncbi_gene - https://www.ncbi.nlm.nih.gov/gene/672
  Single source, not independently confirmed
  ```
  Also green under mutation: deleting the `finish()` call at `:1087` entirely (425 passed), so the cut-off-run behaviour in F-62-J04 is pinned by nothing; and widening the refusal guard at `:870` to `self._tagged_outcome is None` (425 passed; the server sends no trust line on a refusal, `synthesis/trust.py:601`, so this one is defence in depth only).
- What a user would notice: nothing today. A later edit to this function could print two contradicting trust statements on every unconfirmed answer and CI would not notice. The existing test (`test_s3_as_printed.py`, `test_an_unconfirmed_answer_reads_answer_with_its_trust_line`) checks the line is present and before References, never that nothing follows.
### F-62-J06: two refusal wordings misname the case: two Authorization headers read "no bearer token", and `Bearer ` with nothing after it reads "invalid"
- Severity: note
- Where: `src/system_03_search_agent/adapters/mcp/server.py:846` (`_NO_TOKEN_MESSAGE if authorization is None`), with `_extract_bearer_header` returning None for duplicate headers (`:815-816`)
- Evidence: judge's own probe `probe_auth.py` calling `_authenticate_mcp_caller` with a Starlette `Headers` context (AUTH_SECRET set to a throwaway value):
  ```
  no auth header: MCPError: 'no bearer token on this request. The MCP server needs a Syst' ... len=294
  empty header: MCPError: 'malformed bearer token: the Authorization header must be the' ... len=360
  Bearer space: MCPError: 'invalid bearer token: it is not a current access token for a' ... len=424
  Token scheme: MCPError: 'malformed bearer token: ...' len=360
  two headers: MCPError: 'no bearer token on this request. ...' len=294
  guest token: MCPError: 'invalid bearer token: ... A guest token cannot be used here ...' len=424
  expired: MCPError: 'invalid bearer token: ...' len=424
  log lines: 11 token fragments in log: False
  ```
  Security checks held: every message is a fixed constant, none echoes the token or the exception text, nothing token-shaped reached the log, and a guest, an expired and a garbage token all get the identical invalid message, so the words do not reveal which check failed or whether an account exists. The "well-signed token for a user id with no row" case could not be run (SQLite cannot compile the `users` table: `CompileError`); by reading only, `auth/dependencies.py:108-110` raises the same `InvalidBearerTokenError`, so it gets the same words.
- What a user would notice: someone whose proxy adds a second Authorization header is told they sent none, and hunts for a missing header. Minor; the fix text ("send ... as Authorization: Bearer <token>") still points the right way.
### F-62-J07: the install and the agent config are POSIX-only, and the page does not say so
- Severity: note
- Where: `frontend/src/components/screens/InfoScreens.tsx:200` (`. s3-env/bin/activate`), `:225` (`"command": "/path/to/s3-env/bin/s3"`), `:736` (card body: "replace ... with the full path that command -v s3 prints")
- Evidence: `grep -n -i 'windows\|powershell\|macos\|linux' frontend/src/components/screens/InfoScreens.tsx` returns nothing. On Windows the venv's script is `s3-env\Scripts\s3.exe`, activation is `s3-env\Scripts\activate`, and neither `.` nor `command -v` exists in cmd or PowerShell. Not run (no Windows host); stated from the venv layout Python documents.
- What a user would notice: a Windows reader, "someone outside the project", fails on line 2 of the copied install. Candidate: one clause, "on macOS or Linux", or a Windows variant. Owner's call on whether Windows readers are in scope.

## Per-defect evidence

| Defect | Verdict | Evidence (judge's own probe unless marked) |
|--------|---------|------|
| 1. KGX command not in what the page installs | met, with J02 and J03 | Page's `s3` install into a 3.11 venv: `s3-kgx-export` gives `command not found: s3-kgx-export`, exit 127, as the card body now says. Then the KGX copy's first line (`pip install <worktree>` for the git URL): exit 0, `bin/` holds `s3` and `s3-kgx-export`, `s3-kgx-export --help` exit 0, the printed export line refuses with the four `GRAPH_PG_*` names and no values. `pip check`: "No broken requirements found." |
| 2. Python 3.11 and a virtualenv | met in the text, not in the command (J01) | 3.11 venv: install exit 0, `command -v s3` prints the venv path. Stock `/usr/bin/python3` 3.9.6: the copied lines still fail with "No matching distribution found for setuptools==83.0.0". |
| 3. Agent app cannot find bare `s3` | met | Under launchd's PATH (`/usr/bin:/bin:/usr/sbin:/sbin`) and an empty HOME, `bash -c 's3 mcp'` gives `bash: s3: command not found`; the full venv path starts and answers `s3: not logged in; run 's3 login' first` (it started; `S3_BASE_URL` pointed at a closed local port, no deployed app contacted). `s3 mcp --help` prints "Point the agent at s3 by the full path that command -v s3 prints, with the argument mcp, since an agent app may not read your shell's PATH". |
| 4. `[ask]` under a finished answer | met, with J04 and J05 | Installed `s3 login --base-url http://127.0.0.1:18765` then `s3 ask "Which diseases are associated with BRCA1?"` against a local stub API serving a 3-citation `ask` answer: printed `[answer]` then `Based on 3 sources, not yet confirmed` then References, exit 0; `--json` still reports `"trust_outcome": "ask"` and the `trust_line`. A question back still prints `[ask]` (author's test turned red when the asked-back guard was removed). |
| 5. Guest over MCP told malformed | met | `_authenticate_mcp_caller` with a real minted guest token: "invalid bearer token: ... A guest token cannot be used here ... The MCP server needs a System 3 account: sign in with POST /auth/login ...". No token or exception text in the message or the log (J06). `_is_token_refusal` still matches all three, so `s3 mcp` renewal holds (author's test, and mutations 9 and 10 below turn it red). |

## Break-it results

Run in a scratch copy made with `git archive HEAD`, never in the worktree. Python suite: `adapters/cli`, `adapters/mcp`, `test_integrations_page_claims.py` (425 tests, LICENSE-copy test deselected because the copy lacks the root files). Page text: `IntegrationsScreen.test.tsx` via vitest (16 tests).

Went RED, as they should:
- Tag reverts to `[ask]`; `done` stops printing the trust line; trust line unsanitized; asked-back guard removed; fallback caution removed.
- No-token and malformed messages swapped; "bearer token" dropped from the invalid or no-token message; account guidance dropped; old shared message restored; exception text appended to the message.
- KGX pip line dropped; KGX installs `system3-cli` instead; bare `"command": "s3"`; config path differs from the install's venv; Python version changed to 3.9; KGX flag `--hopz`; `s3 mcp --help` reverted.
- Vitest: venv lines dropped; activate line dropped; "not in that install" sentence dropped; "coming to MCP next" restored; "Python 3.11 or newer" removed; "command -v s3" instruction removed; KGX copy button text swapped.

Stayed GREEN (findings):
- Trust line "printed at most once" flag removed (J05).
- `finish()` no longer calls `_write_trust_line(None)` (J05, and J04's path).
- Refusal guard widened (J05, defence in depth only).
- `--hops` shortened to `--hop`: green, but correctly so, since argparse accepts an unambiguous prefix and the command still works.

Gates, run by the judge: `ruff check` on the eight changed Python files, "All checks passed!"; `isort --check-only` on them, clean. Author's suites in the scratch copy: 425 passed plus the 1 LICENSE artefact; vitest 16 passed.

## What was verified by probe, and what only by reading

Verified by the judge's own probes: every row of the per-defect table; J01, J02, J03, J04, J05, J06's message and log behaviour; all break-it results; lint.

Read only, not run:
- The git URL itself (`git+https://github.com/...`): the local worktree path stood in for it, so what GitHub's default branch serves today was not installed. The page's install will serve the branch's `s3 mcp --help` text only once this merges.
- A real desktop agent app driving `s3 mcp`: simulated by launchd's PATH, not a real app.
- The "valid signature, no such user" MCP case (SQLite cannot build the `users` table); `auth/dependencies.py:108-110` read instead.
- Windows (J07).
- Correction to J05: the refusal guard is at `render.py:871`, not `:870`.

## Card-fix warning

F-62-J04 and F-62-J05 sit inside a fix made by this card (`render.py:855-882` and the `finish()` call at `:1087`, commit 731ac19a). By the review loop's stop rule that is worth the lead's attention before another round.

Verdict: MERGE WITH NAMED ITEMS (F-62-J01, F-62-J02, F-62-J04, F-62-J05 to be fixed or accepted by the owner; J03, J06, J07 notes)
