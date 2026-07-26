---
name: best-practices
description: Session-start checklist, code change safety rules, and commit hygiene for agentic-search-ui (System 3: search agent + UI).
---

# Best practices

## 1. Session start checklist

Before doing any work in a fresh session:

1. Read `CLAUDE.md` for current focus and System 3 scope.
2. Run `git status` and `git log -5 --oneline` to see what changed since last session.
3. Skim `DECISIONS.md` for recent architecture decisions.
4. Confirm Python venv is active: `which python` should point inside `venv/`.
5. Confirm API keys are configured (`.env` has `ANTHROPIC_API_KEY` or equivalent).
6. Re-read the file or skill you are about to modify before editing.

If any check fails, fix the environment before writing new code.

## 2. Scope discipline

This repo is System 3 (search agent, API, UI) only.

The knowledge graph (System 1 + System 2) lives in a separate repo, symlinked at `reference/agentic-search-data-engineering`. System 3 connects to the live graph as a read-only client via psycopg2.

Never add to this repo:

- ETL pipeline code (FTP downloads, bulk parsers, KGX exporters)
- Schema validation or BioLink mapping code
- AGE loader or graph write operations
- Anything that modifies the knowledge graph

If a task drifts toward System 1 or System 2, stop and ask the user.

## 3. Code change safety

Before editing any module:

1. Read the full file, not just the function you intend to change.
2. Grep for callers: search the symbol you are about to rename or change signature on.
3. If the change touches agent prompts, tool definitions, or API routes, log a row in `DECISIONS.md`.

### Agent loop integrity

The agent loop has 5 steps: Guardrail, Think, Plan, Act, Write. Changes to one step must not break assumptions of others. Specifically:

- Tool signatures are typed JSON schemas. Changing a tool's parameters requires updating both the tool definition and the agent's system prompt.
- Guardrail changes affect what reaches the planner. Test with edge cases.
- Cost control levers (per-query cap, per-user cap) are safety-critical. Changes require explicit testing.

### Provenance

Every answer must trace back to specific records in NCBI databases. Functions that produce citations must include `source`, `source_id`, and `layer` (1, 2, or 3). If you can produce a citation without provenance fields, the function signature is wrong.

## 4. Commit hygiene

- Work on feature branches. One PR per feature/phase, merged into `main` after review.
- Commit messages in sentence case, descriptive, no emoji.
- One logical change per commit.
- Never add `Co-Authored-By` lines. Project rule.
- Never `git push --force`. Never amend a published commit.
- Never `git add -A` blindly. Stage specific files so you do not accidentally commit `.env` or `node_modules/`.

## 5. Common pitfalls

- Forgetting to activate the venv. Symptom: `ModuleNotFoundError` for `fastapi` or `langgraph`.
- Missing API keys in `.env`. Symptom: 401 errors from LLM providers at runtime.
- Treating `reference/agentic-search-data-engineering` as part of the project. It is read-only reference material. Never edit files in it.
- Hardcoding model names instead of using the multi-model harness config. Every model call goes through the tier routing.
- Streaming responses without proper error handling. SSE connections that fail mid-stream leave the UI in a broken state.

## 6. Three-state permissions

Allow:
- Read any file in the repo.
- Run tests, linters, type checkers.
- Append to `DECISIONS.md`.
- Start the dev server locally.

Ask:

- Add a new dependency to `requirements.txt` or `package.json`.
- Change agent system prompts or tool definitions.
- Modify cost control thresholds.
- Change auth configuration.

Deny:

- Edit anything inside `reference/`.
- Write to the knowledge graph (all connections are read-only).
- Push to a remote branch other than the current feature branch.
- Add System 1/2 dependencies (linkml, kgx, biopython bulk processing).
