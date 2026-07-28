# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) version 1.1.0, and this project intends to adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once the first release is cut.

This project has not cut a release. There is no version tag and no release date. Requirements planning (Plan.md Phases 1 to 5) is complete, and build execution is underway at Plan.md Phase 6: build phases 1.0 and 1.1 are merged, so application code now exists (the FastAPI app, the typed event contract, the auth service, and the user-data schema). No agent loop, no tools, and no real query behavior yet; those begin at build phase 2.0. Every entry below therefore sits under Unreleased. This file is hand-maintained; no changelog-generation tooling is wired up yet, and none is planned until the first tag exists (see `.claude/rules/git-workflow.md`).

Entries are written from the real commit history (`git log`), not from memory or inference. Commit message format: this repo adopted the Conventional Commits specification (v1.0.0) for commit subject lines on 2026-07-26. Commit 1f2ffd0 and earlier predate that convention and use the prior sentence-case style with no type prefix; see `.claude/rules/git-workflow.md` for the full format.

## Table of contents

- [Unreleased](#unreleased)

## Unreleased

Scope note: entries start at commit f90b203 (2026-05-05, "Strip System 1+2 code, adapt baseline for System 3"). That commit removed System 1 (data pipelines) and System 2 (knowledge graph) from this repository and adopted the System 3 (search agent, API, UI) scope CLAUDE.md now describes. Commit history before f90b203 documents a different project scope that no longer lives in this repo; see the data-engineering repo symlinked at `reference/agentic-search-data-engineering` for that history's current home. The System 1/2 removal itself is recorded under Removed below.

### Added

- System 3 baseline scaffold: `src/` skeleton, and CLAUDE.md, AGENTS.md, README, `pyproject.toml`, and `requirements.txt` rewritten for the FastAPI, LangGraph, and React stack (f90b203).
- `requirements/` planning folder: Plan.md, Background_requirements.md, and the kickoff meeting notes (12a45f0).
- dev-standards skill, a six-lens production readiness review (2bc7de9).
- NCBI repos deep dive doc: 13 of roughly 200 surveyed NCBI GitHub repos analyzed for System 3 tool integration, code to reuse, and architecture patterns to adopt (27e967b).
- Tier 1 SDLC hardening: a jq-free JSON parser for hooks, `scan-secrets.sh`, `scan-write-secrets.sh`, `block-bash-delete.sh`, `scan-context-injection.sh`, and the goal-contracts rule (876d411).
- Tier 2 SDLC rules and skills: ai-security-standards, production-standards, production-examples, the eval-harness skill (pass@k and pass/fail/abstain scoring), and the verify skill (d26002e).
- Tier 3 SDLC rules: self-eval-loop, anti-rationalization, supply-chain-security, sandbox-diagnosis (f243831).
- Competency-question moat test criteria and the worktree isolation decision for concurrent bossman-mode builders (e636201).
- Phase 1 planning completed and synthesized: 13 Plan.md steps, 75 decisions logged (5196af7, 41d5119).
- Agent_teams_tmux_quickstart.md doc and a bossman-mode tmux preflight so parallel builders show in live panes instead of falling back to invisible background execution (6b7e5bf).
- Evaluation_playbook.md: the moat test, the locked v1 must-pass competency question set, an 8-point offline eval rubric, and the online feedback loop design (86560ae, 56f8f6f).
- phase-checkpoint skill, syncing planning docs at each phase boundary (86560ae).
- PRD locked at requirements/PRD.md, graded 7 of 7 against the evaluation playbook (57173b6).
- no-prose-walls rule (ca9c9b6).
- Claude_security_plugin_usage.md doc and a security scan milestone gate wired into release-workflow and the pull request template (87729d4).
- Build-team model tiering and evidence-based judging added to bossman-mode (1ff2dea).
- Adversary role and single-writer-per-state shared-ledger coordination added to bossman-mode and self-eval-loop (fc895dc).
- API_capability_sheet.md, live-verified against production NCBI and enrichment endpoints, resolving all three Phase 2 feasibility flags (06b877c).
- plan-then-fan-out rule: the strongest model plans and decomposes, cheaper models execute the fan-out (06b877c).
- Technical_specification.md locked: 25 sections, seven tools, six delivery surfaces (f75432d).
- Strategic_memo.md, completing Phase 4 of System 3 planning (babdab9).
- System_3_overview.html, combining the four Phase 4 planning docs into one navigable page (682e26c).
- task-tracker and learnings skills; tool-call-budgets and v1-scope-boundary rules; prompt-cache-discipline adopted; Tool_implementation_mechanics.md with 19 per-tool API traps (76c570d).
- tracker/BOARD.md and render_board.py: a real board generator that parses BOARD.md and refuses to write when the board is malformed, plus the sync-board.sh hook that regenerates the views on every edit to a tracker markdown file (76c570d, 0f2048d).
- Phase_6_execution_flow.html visual and Build_workflow_cadence.md, naming the model and effort for every stage of the build loop (2c2dd80, b4c5616).
- docs/README.md as an index and organizing layer for the docs folder (f30250b, 1f2ffd0).
- Build phase 1.0: the FastAPI app skeleton and health endpoint (a971d42), the Pydantic event contract (`Query`, `RequestContext`, the `Event` envelope, and all eleven Section 2.3 payload types) (f2b3614), and the `run()` stub wired to a query endpoint (cf630a9).
- Build phase 1.1, merged as PR #6 (4013477): the auth service and the PostgreSQL user-data schema.
  - Auth primitives: argon2id password hashing, HS256 access tokens with the verification algorithm pinned explicitly, and opaque refresh tokens stored only as SHA-256 hashes (465291e).
  - Five endpoints mounted at `/auth`: signup, login, refresh, logout, and me (ff797d2).
  - All six Section 15 user-data tables (`users`, `auth_sessions`, `sessions`, `interactions`, `cq_candidates`, `saved_queries`) as SQLAlchemy models, plus Alembic scaffolding and the `0001_user_data_schema` revision, both directions (fcd3db0).
  - Security hardening from the adversary pass: RFC 6819 refresh-token reuse detection, case-insensitive email uniqueness enforced by a functional unique index, a required `exp` claim, and a 90-day absolute session ceiling, in the `0002_auth_hardening` revision (8313d82).
  - Token lifetimes: 15-minute access, 30-day sliding refresh, 90-day absolute ceiling that does not renew on rotation.
  - Test suite grew from 191 to 314.

### Changed

- `.claude/` config and `reference/` symlinks brought under version control so the development harness is reproducible across machines (edc52c8).
- DECISIONS.md reset for System 3: 81 System 1/2 rows cleared, restarted with 7 foundational System 3 architecture decisions (2bc7de9).
- `/ship` skill reworked to delegate to the docs-sync and git-sync agents in sequence, and to explicitly authorize pushing to any branch when the user invokes it (edeff0a, 77fabd3).
- `.claude/rules/` reconciled and adapted for System 3: git-workflow branch names and gitignore rewritten, dependency-tracking relaxed to skills and hooks only, the clarify-before-drafting versus preserve-your-thinking conflict resolved in favor of an explicit user override (9f0e4b6).
- `.claude/skills/` and `.claude/agents/` cleaned up: repo-dive rescoped to System 3 (was targeting the data-engineering sibling repo), skill-adapt-verify's dead paths fixed, a differentiator added to dev-standards, bold and em dashes removed from first-principles, objective-review, and socratic-questioning (7ce14ff).
- Root docs synced for the SDLC hardening additions: the stale current-focus row corrected, eval-harness and verify registered in AGENTS.md's skills table (7de3238).
- System 3 plan extended with new research steps (orchestration, model routing, KV cache, model-bench), the evaluation playbook step, and a prototype-first build sequence (4a8097e).
- eval-harness skill rewritten against Evaluation_playbook.md, which it had never referenced; it was missing 13 of 17 demanded checks (76c570d).
- Root documents corrected: 19 stale statements fixed, the pull request template rewritten off the inherited BioLink and KGX gates it no longer needed (76c570d).
- bossman-mode and release-workflow branch-naming defect fixed: both were creating `feature/description` branches against the documented `phase/N.M-description` convention (76c570d).
- Docs reorganized into architecture, build, ncbi, and data-engineering folders; the HTML publishing dependency inverted so the repo file is the source and the artifact fragment is derived from it at publish time, instead of the reverse (f30250b, 1f2ffd0).
- Build board reflowed left to right (to do, in progress, blocked, in review, done) with the previously missing in-review column added (777e1ea).
- Background_requirements.md relocated into requirements/context, a clean rename with content unchanged (a9bdcd7).
- `.claude` and `.codex` tracking toggled: untracked on 2026-07-25 to keep the local agent OS out of the shipped repo, then re-tracked the next day for the duration of v1 so the Phase 5 harness rewrite could appear in a pull request and survive a fresh clone (4b0c731, 566831f).

### Fixed

- Residual schema-drift leftovers flagged by the Step 4.3 technical specification re-grade (4ba8ddc).
- CLAUDE.md and AGENTS.md auto-read skill references pointing at 5 deleted skills (qa-gate, architecture-patterns, documentation-standards, python-code-standards, testing-standards); fixed to reference only existing skills (2bc7de9).
- Dead paths in skill-adapt-verify, a dead citation in dev-standards, a dead reference in writing-style, and a stale self-eval-loop judge pointer (7ce14ff, 9f0e4b6).
- Remaining references to the nonexistent qa-gate skill removed from bossman-mode and git-workflow (9f0e4b6).
- Shell-allowlist-bypass example in production-examples corrected: the permission engine evaluates per shell segment, so the real residual risk is a destructive command smuggled inside a quoted subcommand argument, not a visibly chained command (9f0e4b6).
- `pytest` could not import `system_03_search_agent` from `src/` with no `PYTHONPATH` set; added `pythonpath = ["src"]` to `pyproject.toml` (d300b2d).
- `Event.payload` was an open `dict[str, Any]` with nothing binding it to its declared type, and `RequestContext.session_memory` accepted an unbounded arbitrary payload; both fixed with a model validator and a serialized-size cap, independently re-verified (b20b17c).
- Three ruff findings (import sort order, a deprecated `datetime.timezone.utc` pattern) in `test_events.py` (472df34).
- `agentic-search-ui`'s own `venv/` had been a wholesale copy of the sibling `agentic-search-data-engineering` repo's venv, with every generated script (`activate`, `pip`) hardcoded to the sibling's path; rebuilt clean, LEARNINGS.md 2026-07-27.

### Removed

- All System 1 and System 2 code stripped from this repository: ETL pipelines, the AGE loader, schema, mappings, scripts, and tests. System 1 and System 2 now live in the separate agentic-search-data-engineering repo, symlinked read-only at `reference/` (f90b203).
- Publish-fragment files removed from version control (`tracker/board.body.html`, `docs/Phase_6_execution_flow.body.html`); the artifact publisher now derives them at publish time instead of committing them (1f2ffd0).

### Security

- Security hooks wired into `.claude/settings.json`: `scan-secrets.sh` (rewritten to fail closed when `jq` is absent instead of passing every command through), `scan-write-secrets.sh`, `block-bash-delete.sh`, and `scan-context-injection.sh` (876d411).
- ai-security-standards.md and supply-chain-security.md rules added, covering prompt-injection defense for Layer 2 and Layer 3 retrieved data, least-privilege tools, and pre-install checks for npm, PyPI, and MCP server integrations (d26002e, f243831).
- Security hooks hardened: `block-bash-delete` extended to catch destructive commands smuggled inside quoted execution-wrapper arguments, `scan-write-secrets` broadened to source files, `block-sensitive-read.sh` added to block reads of `.ssh`, `.aws`, `.gnupg`, `.netrc`, and private-key files (2d3ad66).
- Security scan milestone gate wired into release-workflow as Step 3, between tests and ship, with a matching pull request template checkbox (87729d4).
- `setuptools` upgraded to 83.0.0, clearing three known CVEs (a path traversal in `PackageIndex`, an RCE in the download functions, a Unicode-normalization bypass in `MANIFEST.in` exclusions).
- Accepted `ecdsa` 0.19.2's known CVE (PYSEC-2026-1325, no upstream fix) as a risk for build phase 1.1 to resolve when it implements JWT signing, since nothing in phase 1.0 invokes it; see DECISIONS.md 2026-07-27.
- Deferred the full `claude-security` multi-agent scan for phase 1.0, since no auth, database, LLM, or external-API surface exists yet; relied on the judge's gate review, two independent adversarial-probe passes, and the always-on `security-guidance` layer instead; see DECISIONS.md 2026-07-27.
- Resolved the `ecdsa` CVE at the root in build phase 1.1 by replacing `python-jose[cryptography]` with `PyJWT` (465291e). `ecdsa` is a core requirement of `python-jose` rather than an extra, so it could not be excluded in place; `pip show ecdsa` now reports not found and `pip-audit` reports no known vulnerabilities. See DECISIONS.md 2026-07-28.
- Hardened the auth surface against an adversary pass that filed 18 findings, of which 9 were closed with independently re-verified fixes, 2 rejected, and 7 deferred to named later phases (8313d82). The two most serious were reachable only by unscripted testing after the scripted gate had passed: the migration test ran `alembic downgrade base` against the database named by `USER_DB_URL` and destroyed every row on each run while restoring the schema on teardown, and refresh rotation shipped correctly while delivering none of the "bounded to one use" property the technical specification states, since nothing acted on the replay the server detected.
- Deferred the full security scan a second time at build phase 1.1 and scheduled it once at the Plan.md Step 6.2 reconciliation, scoped to the entire repository rather than a commit range, where it is a hard prerequisite for starting Step 6.3. Build phases 1.0 and 1.1 remain entirely unscanned; the only run in `security/` predates all build-phase code. See DECISIONS.md 2026-07-28.
