---
name: release-workflow
description: End-to-end release workflow for System 3 changes. Verifies locally, then ships. No BioLink gates, no KGX validation.
---

# Release workflow

What "release" means in this repo:

- A feature or fix has been written, tested, and is ready to land on `main`.
- The dev server starts and basic smoke tests pass.
- Docs and `DECISIONS.md` are in sync.

## Pre-flight

1. `git status` is clean except for the change you intend to ship. If there is unrelated drift, stash or commit it separately first.
2. The venv is active (`which python`).
3. API keys are configured in `.env`.

## Step 1: local verification

Run the affected code path end-to-end locally:

- For agent changes: run a test query through the full agent loop (guardrail -> plan -> act -> write)
- For API changes: hit the endpoint with curl or the test client
- For UI changes: verify the component renders and interacts correctly
- For tool changes: verify the tool returns expected results against the live graph or mock

The point is to prove the code path works, not just unit tests.

## Step 2: tests

Run `pytest -q`. All tests must pass. If tests are missing for the change, write them first.

## Step 3: ship

Invoke `.claude/skills/ship/SKILL.md`:

1. Run `docs-sync` if any architecture, schema, or agent behavior changed.
2. `git add` only the files you intend to ship (no `git add -A`).
3. `git commit` with a short, sentence-case message describing the why, not the what. Never add `Co-Authored-By` lines.
4. Push the feature branch: `git push -u origin feature/description`
5. Create a pull request with a description of what changed and why.

## Step 4: post-release sanity

After the commit:

1. `git log -1 --stat` and confirm only the intended files are in the commit.
2. If a `DECISIONS.md` row was added, mention it in the chat reply.

## What this skill does NOT do

- Does not deploy. Deployment is a separate step.
- Does not tag releases or bump versions.
- Does not run BioLink validation or KGX checks (those are System 1+2 concerns).
