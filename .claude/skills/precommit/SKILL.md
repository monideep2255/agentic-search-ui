---
name: precommit
description: "Run pre-commit verification checks for the agentic-search-ui stack: Python compile check, test suite, lint, git status, and an optional frontend check. It checks the code, not the running product: to run the app and prove a change on screen, use /verify. Invoke with /precommit."
scope: project
depends_on:
  - pyproject.toml
  - requirements.txt
depended_by:
  - CLAUDE.md
---

# Precommit skill

Named `verify` until 2026-09-26, when it was renamed so that `/verify` could mean running the product and proving a change on screen (card 42, DECISIONS.md "The verify loop of card 42 is approved as proposed"). This skill is unchanged apart from its name.

Run these checks in sequence before committing System 3 code, then format the output as a verification report. Stop at the first FAIL if it is a real blocker.

Five build phases are merged as of this write-up: 1.0 (FastAPI skeleton and the event contract), 1.1 (auth service and the PostgreSQL user-data schema), 2.0 (the real LangGraph loop and the three-tier harness), 1.2 (the React shell and SSE streaming, wired end to end), and 2.1 (`cypher_query` over Layer 1, the first live graph access). The Python test suite, the FastAPI entrypoint, ruff, and the frontend test suite all exist and are runnable now. Every check below runs for real and reports a real result. None of them degrade to a pass-with-note for an empty or Phase-1 repository state anymore.

## Prerequisites

- Python virtualenv (`venv/`) active: `which python` should point inside `venv/`
- Run from the repo root

## Checks to run

### 1. Python import/compile check

Compile every module under the search agent package:

```bash
python -m py_compile $(find src/system_03_search_agent -name "*.py")
```

Catches syntax errors before they hit git history. The FastAPI app entrypoint exists at `src/system_03_search_agent/adapters/web_sse/app.py` (shipped in build phase 1.2). Run the import smoke check against it:

```bash
python -c "import system_03_search_agent.adapters.web_sse.app"
```

Confirm the entrypoint path first with `find src/system_03_search_agent -name "main.py" -o -name "app.py"` in case a future phase relocates it. If the found path differs from `adapters/web_sse/app.py`, import that path instead and report the change. Only report "no application module yet" if the find command genuinely returns nothing, which is not the current state.

### 2. Test suite

```bash
pytest --tb=short
```

Short traceback for failures. Report the actual pass/fail count from the pytest output, taken from the run itself, never hardcoded into this skill.

`tests/` now holds hundreds of real tests across the five merged build phases. Zero collected tests (pytest exit code 5, "no tests collected") is a FAILURE, not a pass with a note. At this point in the project, zero collection means the test runner is broken, most likely a wrong working directory, a broken `PYTHONPATH`, a bad virtualenv activation, or a deleted or moved test tree, not that tests do not exist yet. Treat it as a real blocker: report it as FAIL, name the likely cause, and stop rather than continuing past it.

### 3. Lint

```bash
ruff check .
```

Confirmed from `pyproject.toml`: ruff is configured as a dev dependency (`[project.optional-dependencies].dev`), and `[tool.ruff]` sets `line-length = 100`. ruff is installed in `venv/` and runs (`ruff --version` reports a working install). Run the command and report the issue count normally: zero issues is PASS, any issue found is a real result to report, not a note.

If a future environment genuinely lacks ruff, "command not found" or a `ModuleNotFoundError` is the signal: report "lint configured in pyproject.toml but ruff is not installed, run `pip install -e '.[dev]'`" as a note in that case only, and do not invent a different lint command. That is not the current state of `venv/`.

### 3b. Import order

```bash
bash .github/gates/gate02_import_order.sh
```

This runs the CI gate's own script rather than a hand-written `isort` line, and that is the point of it. Section 24 gate 2 is `isort --check-only --diff` over `src tests services tracker alembic .claude .github`, and if this skill restated that command instead of invoking it, the two could drift and nothing would report it.

Added 2026-08-30 after build phase 5.0's pull request went red on exactly this gate while every local check was green (F-5.0-30 in `tracker/phase_5.0.md`). The gate existed only in CI, so it had never once run against that branch. This is build phase 4.15's lesson one layer out: 4.15 found that `ruff check` with no path is a different command from `ruff check src services`, and 5.0 found that a gate the local ritual omits entirely has never run at all. "Verified locally" names a set of commands, so the honest form of the claim is the list.

Two things not to do when it fails. Do not run bare `isort` and commit whatever comes out: isort is not idempotent on every input, and on the input that caused this, its first pass split a statement and its second merged it back with a `# noqa: F401` hoisted onto the `import (` line, where it suppresses the unused-import check for every name in the statement rather than one. That form passes both this gate and ruff, and taking it would trade a red gate for a quietly weakened one, which `goal-contracts` forbids outright. And do not add the file to an ignore list to make the check pass. Fix the imports, then confirm that gate 3 still passes too, since the two tools can disagree.

### 4. Git status

```bash
git status --short
git diff --stat
```

Show uncommitted changes so you know what you are about to commit.

### 5. Frontend check (conditional)

```bash
test -f frontend/package.json && (cd frontend && npm test && npm run test:e2e)
```

`frontend/package.json` exists (shipped in build phase 1.2, the React shell with SSE). Run this check for real. The `package.json` `scripts` block defines `test` (`vitest run`, 120 unit and component tests across 15 files) and `test:e2e` (`playwright test`, 3 end-to-end tests), not `lint`: there is currently no `lint` script and no eslint devDependency wired into `frontend/package.json`, so do not invoke `npm run lint`, it will fail with "missing script" rather than reporting a real lint result. Report that gap as a note (no frontend lint check configured yet) rather than fabricating a command. Report the `test` and `test:e2e` results the same way as the Python checks: pass/fail counts, not a skip, since the frontend is no longer unscaffolded.

Keep the `test -f frontend/package.json` guard for robustness, but do not treat it as expected to fail. If it ever does fail, that itself is a regression worth flagging (a deleted or moved frontend), not the normal Phase 1 state it used to guard against.

### 6. Documentation drift

```bash
python tracker/check_doc_drift.py --check
```

Checks the structure of every tracked markdown file, and two kinds of reference that git and the frozen build board can settle:

- A table of contents that does not match its body.
- Two sections describing the same build phase.
- A last-updated date older than the file's newest dated content.
- The integrity of the two append-only tables in DECISIONS.md and LEARNINGS.md: a blank line inside a table, which silently truncates it when rendered; a row missing the `<details>` wrapper its format requires; a row whose column count does not match the header.
- A phase-to-pull-request reference that names a pull request other than the one that merged the phase.
- A phase called "next" that `tracker/BOARD.md`, frozen at build phase 6.2, marks done.

Since 2026-09-25 it compares no count (build harness review item D1): it no longer computes counts from source to fail a document that states a stale value. The last-updated check, which D1 keeps among the structural checks, compares a file with itself and never with today's date. A fact `--check` could not compute is a failure line naming why, never an "ok".

`python3 tracker/check_doc_drift.py --counts` still computes the counts it used to compare (Python tests, frontend tests, Playwright tests, the premise gate, DECISIONS.md rows, LEARNINGS.md entries, open flags) and prints them, checking no document against them.

Exit 0 is clean. A nonzero exit names each drifted document as `path:line`. Fix the document, then rerun. Never pass this check by narrowing it, and never report it as skipped when the script exists.

The script never writes a file. Run `--self-test` if a result looks wrong: it exercises the classifier that separates a current assertion from a dated historical record, which is the part most likely to produce a false result. Its module docstring states what it does not check, and that statement is part of the check, not a footnote to it.

## Output format

Format results as a verification report:

```
VERIFICATION REPORT
====================
Python compile:  PASS / FAIL (details)
Tests:           X passed, Y failed / FAIL: no tests collected, investigate before proceeding
Lint:            X issues found (0 is PASS) / FAIL (details) / not installed (note, unexpected)
Git status:      clean / N files changed
Frontend:        PASS / FAIL (vitest: X passed Y failed, playwright: X passed Y failed)
Doc drift:       PASS (0 stale, 0 structural) / FAIL (N stale, M structural, list them)

Overall:         READY / NOT READY
```

## When to use

- Before committing System 3 code
- Before presenting work to the user
- After making changes to the agent loop, tools, API routes, or React components
- Say `/precommit` to invoke

## Important

This skill does not assume a virtualenv path beyond `venv/` at the repo root. Confirm your environment is active before invoking.

The repository is no longer near-empty: five build phases are merged, and the Python test suite, the FastAPI entrypoint, ruff, and the frontend test suite all exist and run for real. This skill hard-fails on real errors. Mark a check FAIL when it errors on code that actually exists: a real syntax error, a real failing test, zero collected tests, a real lint violation, or a real frontend test failure. There is no longer a pre-code-state exemption for any of the five checks; the only note-not-failure exception left in this skill is the frontend `lint` gap described in check 5, because no `lint` script is currently wired into `frontend/package.json`.

## Exit checklist

Done when all of these are true:

- [ ] All 7 checks ran: Python compile, test suite, lint, import order, git status, frontend, documentation drift
- [ ] Import order ran the gate's own script, `bash .github/gates/gate02_import_order.sh`, not a hand-written `isort` line that could drift from it
- [ ] A failing import-order check was fixed by correcting the imports, never by taking bare `isort` output that broadens a `# noqa`, and never by adding the file to an ignore list
- [ ] Each result captured with pass/fail and counts where relevant, taken from the actual command output, never hardcoded into this skill
- [ ] Zero collected Python tests reported as FAIL with a likely cause, never as a pass-with-note
- [ ] The frontend `lint` gap (no `lint` script in `frontend/package.json`) reported as a note, not fabricated as a command that will fail with "missing script"
- [ ] Verification report printed in the standard format
- [ ] Overall READY / NOT READY line included
- [ ] Any real blocker failure is surfaced, not swallowed
