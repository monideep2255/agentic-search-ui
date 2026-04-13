---
name: best-practices
description: Session-start checklist, code change safety rules, and commit hygiene for the agentic-search-data-engineering repo (System 1 + System 2 only).
---

# Best practices

Adapted from the reference NCBI KG skill. Stripped Railway, frontend, and feature-branch deploy content. This repo works directly on `main`, no Railway, no separate deploy step.

## 1. Session start checklist

Before doing any work in a fresh session:

1. Read `CLAUDE.md` for current focus and System 1 + 2 scope reminder.
2. Run `git status` and `git log -5 --oneline` to see what changed since last session.
3. Skim `DECISIONS.md` for recent architecture decisions.
4. Confirm Python venv is active: `which python` should point inside `venv/`.
5. Confirm Postgres + AGE is running and `ncbi_kg` database exists.
6. Re-read the file or skill you are about to modify before editing.

If any check fails, fix the environment before writing new code. Do not paper over a broken environment with new code.

## 2. Scope discipline (the System 3 rule)

This repo is System 1 (data pipelines) + System 2 (knowledge graph) only.

Never add to this repo:

- FastAPI servers, LangGraph agents, or any LLM orchestration
- React, Next.js, or any web UI code
- Slack / Telegram / WhatsApp delivery channels
- MCP servers or query-time API call code

If a task drifts toward System 3, stop and ask the user.

## 3. Code change safety

Before editing any Python module under `system-01-data-pipelines/` or `system-02-knowledge-graph/`:

1. Read the full file, not just the function you intend to change.
2. Grep for callers: `Grep` the symbol you are about to rename or change signature on.
3. Check the module docstring for the `Depends on` / `Reads` / `Writes` block (see `.claude/rules/dependency-tracking.md`).
4. If the change touches schema, provenance, or BioLink predicates, log a row in `DECISIONS.md`.

### Idempotency

Pipeline steps must be safe to re-run. Never write a step that:

- Deletes its previous output without first checking what it is about to delete
- Mutates `data/ftp_cache/` (it is a read-only cache after download)
- Skips a step on the basis of a stale flag instead of a content hash

### Provenance

Every node and every edge gets `source` and `source_url`. Functions that produce nodes or edges must take provenance as a required parameter, not a default. If you can call the constructor without provenance, the signature is wrong. Fix the signature.

## 4. Commit hygiene

- Work on `main`. No PR process.
- Commit messages in sentence case, descriptive, no emoji.
- One logical change per commit. Pipeline + schema + tests for the same database go together; unrelated cleanup goes in a separate commit.
- **Never add `Co-Authored-By` lines.** Project rule.
- Never `git push --force`. Never amend a published commit.
- Never `git add -A` blindly. Stage specific files so you do not accidentally commit `.env`, `data/`, or `reference/`.

## 5. Common pitfalls

- Forgetting to activate the venv. Symptom: `ModuleNotFoundError` for `linkml` or `kgx`.
- Forgetting `CREATE EXTENSION age` after restoring a database. Symptom: `function ag_catalog.cypher does not exist`.
- Loading `dotenv` from a stdin heredoc. Symptom: `AssertionError` deep in dotenv. Fix: use `dotenv_values(".env")` (returns a dict).
- Treating `reference/` as part of the project. It is read-only Confluence-style documentation. Never edit, never vendor files out of it.
- Writing schemas inside the pipeline modules. Schemas live in `system-02-knowledge-graph/schema/`, pipelines import them.

## 6. Three-state permissions

Allow:
- Read any file in the repo.
- Run validators, parsers, dry-run pipeline steps.
- Append to `DECISIONS.md`.
- Write tests against existing code.

Ask:
- Modify `system-02-knowledge-graph/schema/` or BioLink predicate constants.
- Add a new pipeline directory under `system-01-data-pipelines/`.
- Add a new dependency to `requirements.txt`.
- Touch anything inside `data/` (other than reading metadata).

Deny:
- Edit anything inside `reference/`.
- Delete `data/ftp_cache/` or `data/kgx/` without explicit instruction.
- Push to a remote branch other than `main`.
- Add System 3 dependencies (FastAPI, LangGraph, React, MCP, Slack SDKs, etc.).
