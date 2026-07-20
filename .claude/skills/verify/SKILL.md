---
name: verify
description: "Run pre-commit verification checks for the agentic-search-ui stack: Python compile check, test suite, lint, git status, and an optional frontend check. Invoke with /verify."
scope: project
depends_on:
  - pyproject.toml
  - requirements.txt
depended_by:
  - CLAUDE.md
---

# Verify skill

Run these checks in sequence before committing System 3 code, then format the output as a verification report. Stop at the first FAIL if it is a real blocker.

Most of the stack (FastAPI app, agent code, React frontend) is still Phase 1 scaffolding as of this write-up. Several checks below currently degrade to a pass-with-note instead of failing, because there is no code yet for them to fail on. As Phase 2 through 6 land real code, the same checks become fully meaningful without editing this skill.

## Prerequisites

- Python virtualenv (`venv/`) active: `which python` should point inside `venv/`
- Run from the repo root

## Checks to run

### 1. Python import/compile check

Compile every module under the search agent package:

```bash
python -m py_compile $(find src/system_03_search_agent -name "*.py")
```

Catches syntax errors before they hit git history. If a FastAPI app entrypoint exists (for example `src/system_03_search_agent/api/main.py`), also run an import smoke check:

```bash
python -c "import system_03_search_agent.api.main"
```

Check whether an entrypoint exists first with `find src/system_03_search_agent -name "main.py" -o -name "app.py"`. As of Phase 1, none exists yet, only package `__init__.py` stubs. Skip the import smoke check and report "no application module yet" rather than erroring on a path that does not exist.

### 2. Test suite

```bash
pytest --tb=short
```

Short traceback for failures. Report pass/fail count. `tests/` currently holds only an `__init__.py` stub, so pytest exits with "no tests collected" (exit code 5). Treat that as a pass with a note, not a failure. Once real tests exist, report the actual pass/fail count.

### 3. Lint

```bash
ruff check .
```

Confirmed from `pyproject.toml`: ruff is configured as a dev dependency (`[project.optional-dependencies].dev`), and `[tool.ruff]` sets `line-length = 100`. It is not currently installed in `venv/`. Run the command anyway; if it fails with "command not found" or a `ModuleNotFoundError`, report "lint configured in pyproject.toml but ruff is not installed, run `pip install -e '.[dev]'`" as a note, not a failure. Do not invent a different lint command. Once ruff is installed and runs, report the issue count normally.

### 4. Git status

```bash
git status --short
git diff --stat
```

Show uncommitted changes so you know what you are about to commit.

### 5. Frontend check (conditional)

```bash
test -f frontend/package.json && (cd frontend && npm run lint && npm test)
```

Only run this if `frontend/package.json` exists. As of Phase 1, `frontend/` is empty with no `package.json`, so this step is skipped with the note "frontend not scaffolded yet." Once the React app exists (Phase 1 build order item "React shell"), run `npm run lint` and `npm test` under `frontend/` and report their results the same way as the Python checks.

## Output format

Format results as a verification report:

```
VERIFICATION REPORT
====================
Python compile:  PASS / FAIL (details)
Tests:           X passed, Y failed / no tests collected (pass, note)
Lint:            X issues found / not installed (pass, note)
Git status:      clean / N files changed
Frontend:        skipped (no frontend/package.json) / PASS / FAIL

Overall:         READY / NOT READY
```

## When to use

- Before committing System 3 code
- Before presenting work to the user
- After making changes to the agent loop, tools, API routes, or React components
- Say `/verify` to invoke

## Important

This skill does not assume a virtualenv path beyond `venv/` at the repo root. Confirm your environment is active before invoking.

It does not hard-fail on the current near-empty repo. An empty test suite, a missing app entrypoint, an unscaffolded frontend, and an uninstalled ruff are all expected states today, and are reported as pass-with-note, not FAIL. Only mark a check FAIL when it errors on code that actually exists: a real syntax error, a real failing test, a real lint violation, or a real frontend test failure.

## Exit checklist

Done when all of these are true:

- [ ] All 5 checks ran: Python compile, test suite, lint, git status, frontend (or explicitly skipped with a note)
- [ ] Each result captured with pass/fail and counts where relevant
- [ ] Pre-code-state conditions (empty tests, missing entrypoint, unscaffolded frontend, uninstalled ruff) reported as pass-with-note, never as a hard failure
- [ ] Verification report printed in the standard format
- [ ] Overall READY / NOT READY line included
- [ ] Any real blocker failure is surfaced, not swallowed
