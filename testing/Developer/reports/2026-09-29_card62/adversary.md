# Card 62 adversary round, 2026-09-29

Branch `fix/card62-install-first-try`, worktree card62. One round. Targets: (1) a lying trust signal in `s3` or MCP, (2) a first-try failure from the Integrations page's printed commands, or an MCP refusal that points at the wrong next step. Local stubs only, no request to develop or production.

## Findings

### F-62-A01: a question back that is then stopped or errors prints "Single source, not independently confirmed" under `[ask]`, with zero sources
- Severity: blocking (inside this card's own new code, commit 731ac19a)
- Where: `src/system_03_search_agent/adapters/cli/render.py:855` (`self._tagged_outcome = outcome` stores the SHOWN outcome, so a question back is stored as `"ask"`), `:877-879` (an `ask` with no line gets `_UNCONFIRMED_WITHOUT_TRUST_LINE`), `:872` (`self._asked_back()` is re-evaluated at finish time, and `_is_ask_back` returns False once `_fatal_error_seen` is set, `:563`), `:1087` (`finish()` calls `_write_trust_line(None)`).
- Reproduction: adversary probe `scratchpad/adv62/p1.py`, driving the real `Renderer` with: guard passed; think with `clarifying_question: "Which part do you mean?"`, options `["A?","B?"]`; token "Which part do you mean?"; answer-scope `trust_signal` `outcome: "refuse"`, `grounded: false`; then a fatal `error` with `error_class: "cancelled"` (the shape of a stopped run). Output, exit 1:
  ```
  Which part do you mean?
    1. A?
    2. B?

  [ask]
  Single source, not independently confirmed
  --stderr--
  [think] n
  error [run]: this query was stopped before it finished.
  ```
  The same stream ending with no terminal event (dropped connection) prints `[ask]` with nothing under it, so it is the fatal-error path specifically. The server sent a refusal-shaped question back, zero citations and no trust line; "Single source" is a statement about evidence that does not exist. The web, for a fatal run, shows no outcome and "Not verified · the run did not finish" (`frontend/src/hooks/useRunView.ts:866-870`, `:1096-1097`).
- What a user would see: they typed a bare topic, pressed Ctrl-C or the server errored, and `s3` told them the (non-existent) answer rests on a single source. An agent parsing stdout reads a trust verdict under a question. Root cause is two-fold: `_tagged_outcome` conflates "question back shown as ask" with "server's ask outcome", and `_asked_back()` changes value after the tag was printed. J04 covers the no-`done` answer path; this is a distinct path (question back, fatal error) that J04's fix ("don't print the fallback when no done arrived") might or might not cover depending on how it is written.
- NOT FIXED
### F-62-A02: `s3` prints the web's trust line but drops the two things the web never drops beside it, "High-risk claim" and "Not fully grounded"
- Severity: should-fix (the card's own promise, "s3 shows the web's trust line", commit 731ac19a)
- Where: `src/system_03_search_agent/adapters/cli/render.py:810-819` (`_handle_trust_signal` reads only `payload.outcome` from the answer-scope signal; `risk_tier` and `grounded` are never read), `:862-882` (`_write_trust_line` prints `done.trust_line` alone). Web: `frontend/src/hooks/useRunView.ts:900-924`, whose own comment says "Two things are never dropped for it: an ungrounded verdict, and a high-risk tier, which stays visible in the risk colour"; rendered as one line of spans at `frontend/src/components/screens/AnswerScreen.tsx:2057-2090`.
- Reproduction: probe `scratchpad/adv62/p1.py`, real `Renderer`:
  - Stream: token with [1] [2], two citations, answer-scope `trust_signal` `{outcome: "answer", risk_tier: "high", grounded: true}`, `done` `{trust_outcome: "answer", trust_line: "Confirmed by 2 independent sources"}`. `s3` printed:
    ```
    [answer]
    Confirmed by 2 independent sources
    ```
    The web, for the same stream, pushes `{kind:"good", "Confirmed by 2 independent sources"}` then `{kind:"risk", "High-risk claim"}` (useRunView.ts:917-923), shown in red.
  - Stream: answer-scope `trust_signal` `{outcome:"answer", risk_tier:"low", grounded:false}`, `done.trust_line: "Based on 1 source"`. `s3` printed `[answer]` / `Based on 1 source`, exit 0. The web shows "Not fully grounded · Based on 1 source" (useRunView.ts:916).
  - Reachability, by reading: `answer_trust_line` returns "Confirmed by N" only when at least one claim is high risk (`synthesis/trust.py:615-622`), and `_aggregate_answer_scope_trust` makes the answer tier `high` whenever any claim is (`core/graph.py:10718-10720`). So EVERY "Confirmed by" answer, and every `ask` "Based on N sources, not yet confirmed" answer (the high-risk single-source row), shows "High-risk claim" on the web and nothing on `s3`. `grounded` is `all(...)` over claims (`graph.py:10726`), so one ungrounded claim under a trust line is reachable too.
  - The web half was read, not run (no vitest probe written, to leave the worktree untouched).
- What a user would see: on the web, "Confirmed by 2 independent sources · High-risk claim" with the risk span in red; on `s3`, "Confirmed by 2 independent sources" with a clean `[answer]` tag. The CLI now shows the positive half of the web's line and hides the caution half. Before the card `s3` printed no line, so it hid nothing it appeared to show.
- NOT FIXED
### F-62-A03: the copied install needs `git`, and the page never says so
- Severity: should-fix
- Where: `frontend/src/components/screens/InfoScreens.tsx:201` (`pip install "git+https://github.com/...#subdirectory=clients/system3-cli"`), `:239` (the KGX copy's `git+https://` line); card body `:736` names Python 3.11 and a virtual environment and nothing else as prerequisites. `grep -n -i '\bgit\b' InfoScreens.tsx`, excluding the URLs, returns nothing.
- Reproduction: a Python 3.14 venv (Homebrew `python3` on this Mac is 3.14.3, which the page's "3.11 or newer" admits), then the page's pip line with a local `git+file://` URL standing in for GitHub, under a PATH with no git:
  `env -i HOME=$SP PATH="$SP/py314/bin:/bin" $SP/py314/bin/pip install --no-cache-dir "git+file:///<worktree>#subdirectory=clients/system3-cli"`
  printed `ERROR: Cannot find command 'git' - do you have 'git' installed and in your PATH?` With git on PATH the same venv installs `s3` in 3 s (exit 0, `install314.log`), so git is the only missing piece.
- Who hits it: a minimal Linux (a `python:3.11-slim` container or a fresh Debian/Ubuntu server has no git), and a Mac without the Command Line Tools, where `/usr/bin/git` is a stub that opens an install dialog and fails the pip run (not reproduced here: this Mac has the tools; stated from how the stub behaves, and note the same stub also fronts `/usr/bin/python3`, so on such a Mac the FIRST line already pops that dialog).
- What a user would see: the third copied line fails with a git error on a page that listed its requirements as Python 3.11 and a virtual environment.
- NOT FIXED
### F-62-A04: "the full path that command -v s3 prints" prints nothing in any terminal other than the one that ran the install
- Severity: note
- Where: `frontend/src/components/screens/InfoScreens.tsx:736` (card body: "replace /path/to/s3-env/bin/s3 with the full path that command -v s3 prints"); `src/system_03_search_agent/adapters/cli/main.py:749-750` (`s3 mcp --help`, same instruction).
- Reproduction: after the page's install into `py314` (A03), a new shell in the same directory: `bash -c 'command -v s3; echo "rc=$?"'` printed `rc=1` and nothing else; `zsh -c ...` the same. Only with the venv activated (`bash -c '. py314/bin/activate; command -v s3'`) did it print `.../py314/bin/s3`.
- What a user would see: someone who installs, closes the terminal, and later sets up the agent gets an empty line and no path to paste. The page never says to re-enter the environment (`. s3-env/bin/activate`) first, nor gives the path directly (`$PWD/s3-env/bin/s3`, which the install's own directory determines). The `--help` half is fine in practice, since a person who can run `s3 mcp --help` has `s3` on PATH.
- NOT FIXED
### F-62-A05: when the answer-scope `trust_signal` and `done` disagree, `s3`'s tag and new trust line follow the signal, while the web, `--json` and the exit code follow `done`, so `s3` can print a clean `[answer]` over a run the server called `ask` or `refuse`
- Severity: note (not reachable from a well-formed stream today: `core/graph.py:12897-12955` sends one answer-scope signal whose outcome equals `done.trust_outcome`; reachable from an older or newer server, a proxy, or a future downgrade path)
- Where: `src/system_03_search_agent/adapters/cli/render.py:819` (the FIRST answer-scope signal prints the tag; `_handle_done` at `:926` cannot change it), `:855` (`_tagged_outcome` is set from that signal), `:877-879` (the new "Single source" fallback keys on `_tagged_outcome`, not on `done.trust_outcome`). Contrast `JsonRenderer._handle_done`, `render.py:~1222`, which overwrites with `done.trust_outcome`, and the web, `useRunView.ts:1096-1102`, which reads only `done`.
- Reproduction: probe `scratchpad/adv62/p2.py`, real `Renderer`:
  - signal `answer`, then `done {trust_outcome: "ask"}` with no `trust_line`: printed `[answer]`, no line under it, `References:`, exit 0. The web shows "Single source, not independently confirmed" in the warn tone (`OUTCOME_BY_TRUST.ask`); this is exactly the case the card's fallback was written for, and it does not fire.
  - signal `answer`, then `done {trust_outcome: "refuse"}`: printed `[answer]` over the answer, exit 1. The web shows "Refused".
  - signal `refuse`, then `done {trust_outcome: "answer", trust_line: "Based on 1 source"}`: printed `[refuse]` and suppressed the trust line (`:875`), exit 0. The web shows "Answered" and "Based on 1 source".
- What a user would see: only on a server whose two verdicts disagree, `s3`'s stdout contradicts its own exit code and the web. Filed because the card added a second output (the trust line) keyed on the first-signal source while its docstring cites the web, which keys on `done`; one source of truth for both tag and line would remove the class. The first-signal tag itself predates the card.
- NOT FIXED
### F-62-A06: `s3 mcp` reads any error whose text contains "bearer token" as a sign-in refusal, and the server echoes argument names into its errors, so an ordinary bad argument makes `s3 mcp` rotate the sign-in and tell the agent to run `s3 login`
- Severity: should-fix (the matcher predates the card; the card rewrote the contract it depends on, and its new docstring at `mcp_bridge.py:250-256` asserts "Matching the words rather than only the code keeps an ordinary invalid request from triggering a renewal", which this disproves)
- Where: `src/system_03_search_agent/adapters/cli/mcp_bridge.py:257-261` (`"bearer token" in text.lower()` on any JSON-RPC error message, any code), `:664` (applied to every reply), `:574-588` (renew once, resend, then the fixed "run s3 login" error); `src/system_03_search_agent/adapters/mcp/server.py:894-899` (`f"unknown argument(s): {', '.join(sorted(unknown))}"`, caller-supplied names echoed, code INVALID_PARAMS).
- Reproduction: probe `scratchpad/adv62/p3.py`. First the REAL server function: `server._reject_unknown_arguments(ctx)` with arguments `{"query": "BRCA1", "bearer token": "x"}` raised `MCPError` with message `'unknown argument(s): bearer token'`. Then the real `McpBridge` (the repository's own `StandIn` harness from `test_mcp_bridge.py`, local mock transport, no network) with a valid, unexpired token and a remote that answers that exact error:
  ```
  agent received: [{'jsonrpc': '2.0', 'id': 3, 'error': {'code': -32001, 'message': 'System 3 refused your sign-in even after renewing it. In a terminal, run: s3 login, then restart this MCP server.'}}]
  renewals: 1 mcp posts: 2
  stderr: s3 mcp: renewed the sign-in
  ```
- What a user would see: an agent that sends an argument with those words (a model inventing a `bearer token` parameter is not far-fetched when the tool is behind auth) gets told the person's sign-in failed; the person runs `s3 login` and restarts, which fixes nothing, and each attempt burns a refresh rotation. The real cause, "unknown argument", is swallowed. A tighter match, the INVALID_REQUEST code plus a message that STARTS with one of the three fixed prefixes, would close it.
- NOT FIXED
### F-62-A07: the KGX line installs a second package that owns the same files as `s3`; removing it deletes `s3` while pip still says `system3-cli` is installed
- Severity: should-fix (introduced by this card's KGX copy, commit 4f749a7f)
- Where: `frontend/src/components/screens/InfoScreens.tsx:239` (`KGX_EXAMPLE` line 1, the root package); root `pyproject.toml` ships all of `system_03_search_agent` and its own `s3` console script; `clients/system3-cli/pyproject.toml` `package-dir = {"" = "../../src"}` ships the same `system_03_search_agent.adapters.cli` files and the same `s3` script. As J03 records, the KGX line only works inside the venv the install copy made, so that is where a reader runs it.
- Reproduction (scratch venv `py314`, Homebrew Python 3.14.3; local worktree path standing in for the git URL; no deployed app contacted):
  1. The page's install: `pip install <worktree>/clients/system3-cli`: exit 0, `bin/s3` present.
  2. The KGX copy's first line in the same venv: `pip install <worktree>`: exit 0, no resolver warning, `pip check` "No broken requirements found." `pip show -f agentic-search-ui` lists `system_03_search_agent/adapters/cli/render.py`, which `system3-cli` also lists (24 shared `system_03_search_agent` paths).
  3. A reader who tried KGX, got the operator-credentials refusal, and removes it: `pip uninstall -y agentic-search-ui` printed `Successfully uninstalled agentic-search-ui-0.1.0`. Then `ls py314/bin | grep s3` printed nothing; `s3 --help` gave `command not found: s3`; `python -c "import system_03_search_agent.adapters.cli.main"` gave `ModuleNotFoundError: No module named 'system_03_search_agent'`; yet `pip check` still said "No broken requirements found." and `pip show system3-cli` still reported version 0.1.0.
- What a user would see: `s3` and the agent's configured `/path/to/s3-env/bin/s3` vanish after uninstalling the thing the page said is a separate install for a different command; reinstalling `system3-cli` looks like a no-op to pip ("already satisfied") unless they know `--force-reinstall`. The reverse order has the same shape. The page could say to use a separate environment for the KGX package.
- NOT FIXED
- A07 addendum, run after filing: re-running the page's OWN install line (as a `git+file://` URL of the worktree, the same URL form the page prints) after step 3 printed only "Requirement already satisfied" lines and `ls py314/bin | grep s3` printed nothing: `s3` stays gone. A local-directory install does rebuild and restore it, but that is not what the page prints. So the page's recovery path does not recover.
- A04 addendum: the same gap hits the page's second copy. `CLI_EXAMPLE` (`InfoScreens.tsx:208-209`, `s3 login ...` then `s3 ask ...`) pasted in any terminal other than the install's gives `command not found: s3` (the `bash -c`/`zsh -c` runs above are that terminal). The card body says the first two install lines "make and enter a virtual environment" but never that a later terminal must enter it again.
### F-62-A08: after a fatal error, `s3` still prints the server's positive trust line; the web replaces it with "Not verified · the run did not finish"
- Severity: note (card code, commit 731ac19a; reachable only if a `done` carrying a `trust_line` follows a fatal `error`. A fatal error followed by `done` IS a shape today's server sends, `_decline_for_daily_cap` per `adapters/mcp/server.py:~905`, but with no trust line, so today the line is None there)
- Where: `src/system_03_search_agent/adapters/cli/render.py:862-882` (`_write_trust_line` checks `_guard_rejected` and the outcome, never `_fatal_error_seen`). Web: `frontend/src/hooks/useRunView.ts:866-870` checks `fatalError` FIRST and never shows the summary line, and `:1096-1097` shows no outcome at all.
- Reproduction: probe `scratchpad/adv62/p4.py`: tokens, two citations, fatal `error` (`unexpected`), answer-scope `trust_signal` `answer`/`high`, `done {trust_outcome: "answer", trust_line: "Confirmed by 2 independent sources"}`. Printed, exit 1:
  ```
  Claim [1]. [2]
  [answer]
  Confirmed by 2 independent sources
  ...
  --stderr--
  error [run]: this query failed unexpectedly before finishing.
  ```
- What a user would see: the strongest verdict the product has, "Confirmed by 2 independent sources", on stdout over a run stderr says failed. The web and MCP (`_floor_trust_signal_for_fatal_error`) both floor on a fatal error; the new CLI line does not. One `or self._fatal_error_seen` in the guard would match them. This also covers the "error mid-answer" case of the brief.
- NOT FIXED

### F-62-A09: `done.trust_line` may carry newlines, and `s3` prints each as its own stdout line, so a trust line can forge a numbered reference row directly under the genuine `[answer]` tag
- Severity: note (hostile or broken server, proxy, or a `--base-url` pointed elsewhere: the threat model `render.py`'s own sanitizer comment adopts, `:282-300`)
- Where: `src/system_03_search_agent/contracts/events.py` `DonePayload.trust_line` (`max_length=200`, no single-line pattern); `render.py:376` (`_ESCAPE_EXEMPT_CHARS = {"\n"}`), `:881` (the line is written through `_sanitize_untrusted`, which keeps `\n`). Web: the line is one `<span>` (`AnswerScreen.tsx:2073-2090`), where a newline collapses to a space.
- Reproduction: probe `scratchpad/adv62/p2.py` case E6, `done.trust_line = "Based on 1 source\n[2] ncbi_gene - https://www.ncbi.nlm.nih.gov/gene/999"`. Printed:
  ```
  Claim [1].
  [answer]
  Based on 1 source
  [2] ncbi_gene - https://www.ncbi.nlm.nih.gov/gene/999

  References:
  [1] ncbi_gene - https://www.ncbi.nlm.nih.gov/gene/671
  ```
  `References:` inside the line IS escaped (`References\:`), and `[answer]` would be, but a `[n] source - url` row is not in the forgery vocabulary.
- What a user would see: a source row that the stream never sent as a citation, placed in the trust block, printed before the tag's own line could be told apart. Token text could already print such a row mid-answer; the trust line is new, trusted-looking real estate right under the tag. A "first line only" or "newline to space" on the trust line would match the web.
- NOT FIXED
- A02 correction, by reading: not EVERY `ask` answer is high risk. `core/graph.py` also floors `trust_outcome` at `ask` for an incomplete answer (`AnswerScreen.tsx:436-447` describes that floor), which can be low risk. The claim stands for every "Confirmed by N" answer and for the `(high, grounded, insufficient)` row of `synthesis/trust.py`'s decision table.

## Not filed, and why

- Signal before tokens (probe p2 E1) prints `[answer]` above the answer and glues the trust line to the last token (`Claim two [2].Based on 2 sources, not yet confirmed`). Same root as the judge's "noted, not filed" glue under J04; not reachable from `core/graph.py`'s order. Not refiled.
- A `think` clarifying question plus an answer-scope `ask` signal arriving before the first citation prints the question's options and `[ask]` over a cited answer (p2 E7). Not reachable: both `clarifying_question=` sites (`core/graph.py:3423`, `:4071`) end the run with no search.
- "Based on 99999 sources, not yet confirmed" under one reference prints verbatim (p4); the web does the same, so parity, not a card defect.
- Python 3.10 (python.org installer, `/usr/local/bin/python3` here) gives a clear `requires a different Python: 3.10.7 not in '>=3.11'`, unlike J01's 3.9 case. Python 3.14 (Homebrew's `python3`) installs `s3` fine. Verified, no defect.
- Re-running `python3 -m venv s3-env` with a newer Python over J01's failed 3.9 venv, then the pip line, works (`s3 --help` exit 0), though the venv's `python` stays 3.9.6. No user-visible defect for `s3`.
- Not run, so not filed: Debian or Ubuntu without `python3-venv` (the first copied line fails with "ensurepip is not available"), and fish or csh, where `. s3-env/bin/activate` is the wrong script. No Linux host or container here.
- MCP refusals: the no-token, malformed and invalid messages point at the right next step for a direct HTTP client, the login route and its 15-minute lifetime match `auth/router.py:580-605` and `auth/tokens.py:36`, signup exists (`auth/router.py:552`, web `GuestAllowance.tsx:252`), and the words do not vary by whether an account exists. For `s3 mcp` users the bridge swaps them for "run s3 login", which is right, except in A06's case.

## Verified by probe versus read

- Probed (real `Renderer`, real `McpBridge`, real `_reject_unknown_arguments`, real pip installs in scratch venvs, local paths for the git URL, no deployed app contacted): A01, A02's CLI half, A03, A04, A05, A06, A07 and its addendum, A08, A09.
- Read only: A02's web half (`useRunView.ts`, `AnswerScreen.tsx`), and A02's and A05's reachability claims about `core/graph.py`; the Mac-without-Command-Line-Tools half of A03.

## Card-fix warning

A01, A02, A08 and A09 sit inside this card's own new code (`render.py` `_write_trust_line` and its call from `finish()`, commit 731ac19a). A07 is created by this card's KGX copy (commit 4f749a7f). A01 is the second defect the review has found in the `finish()` fallback path after the judge's J04, so by the review loop's stop rule this goes to the product owner.

Count: 1 blocking, 5 should-fix (A02, A03, A06, A07, and A01's sibling path via J04 is the judge's, not counted), 4 notes (A04, A05, A08, A09). Totals: blocking 1 (A01), should-fix 4 (A02, A03, A06, A07), note 4 (A04, A05, A08, A09).

Correction to the count line above, which miscounted: ignore it. Verdict against the card's goal ("installs and connects on the first try"; "s3 shows the web's trust line"): FAIL, on A01 (a trust verdict with zero sources under a question back) and A02 (the web's caution half of the line is dropped).

Final count: blocking 1, should-fix 4, note 4.
