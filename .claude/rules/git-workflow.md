---
description: "Git workflow: phase branches, MRs for review, clean commits, gitignored paths"
scope: portable
alwaysApply: true
---

## Git workflow

### Branch model

Work on phase branches, not directly on `main`. One branch per bossman phase.

Branch naming: `phase/N.M-short-description`

- `phase/1.0-fastapi-skeleton`
- `phase/1.1-auth-service`
- `phase/2.0-langgraph-agent-loop`
- `phase/2.1-cypher-tool`
- `phase/3.0-guardrail-node`

Non-phase work uses a type prefix and short description, e.g. `chore/short-description`, `fix/short-description`.

Create the branch at phase start: `git checkout -b phase/N.M-description`

### Merge requests

One MR per phase. Create the MR when the phase is complete and release-workflow passes.

MR flow:
1. Push the phase branch: `git push -u origin phase/N.M-description`
2. Create PR/MR with deliverables checklist from `requirements/Plan.md`
3. User reviews and approves
4. Merge into `main` (no squash, preserve commit history)
5. Delete the phase branch after merge

Do not start the next phase branch until the current MR is merged or the user says to proceed.

### Commit hygiene

Adopted 2026-07-26: this repo follows the Conventional Commits specification (v1.0.0) for the commit subject line. Commits at 1f2ffd0 (2026-07-26) and earlier predate this convention and use the previous sentence-case style with no type prefix. That seam in `git log` is expected, not an error; the pre-adoption commits are not being rewritten.

Header structure:

```text
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

- type: required, one of the eight below.
- scope: optional, a noun in parentheses right after the type, e.g. `fix(cypher-query): ...`. Use zero or one scope per commit. Stacking more than one scope signals the commit does more than one logical thing, which the next rule already forbids.
- `!`: optional, placed immediately before the colon, flags a breaking change (see below).
- description: required, sentence case, immediately after the colon and space. Same casing rule this repo already used.

Types:

- feat: a new capability lands, a tool implementation, an agent-loop step, an API route, a UI surface.
- fix: a bug in existing code or a wrong planning artifact gets corrected.
- docs: a change to `docs/`, `requirements/`, `README.md`, `CLAUDE.md`, `AGENTS.md`, or a rule under `.claude/rules/`.
- chore: repo maintenance with no behavior change, a dependency bump, a `.gitignore` edit, tracker housekeeping, a file rename.
- refactor: a code or doc restructuring with no behavior change and no bug fix.
- test: adding or changing tests only, no production code change.
- ci: a change to `.claude/hooks/`, `.claude/settings.json`, or a GitHub Actions workflow.
- security: a change whose primary purpose is closing a security gap, a supply-chain finding, a prompt-injection defense, a credential-scoping fix.

Scopes: optional on every commit. Use one when it disambiguates which part of the system a commit touches, skip it for repo-wide changes such as most `docs` and `chore` commits.

- Tools: `cypher-query`, `ncbi-efetch`, `ncbi-dbsnp`, `pubtator`, `litvar2`, `pathogen-detection`, `clinicaltrials`
- Agent loop steps: `guardrail`, `think`, `plan`, `act`, `write`
- Delivery surfaces: `web-ui`, `api`, `graphql`, `mcp`, `cli`, `kgx-export`
- Cross-cutting and infrastructure: `harness`, `cache`, `auth`, `docs`, `tracker`, `rules`, `hooks`

Breaking changes: either form below is sufficient on its own, and the two can be combined.

- Header form: a `!` immediately before the colon, e.g. `feat(api)!: drop the v1 query endpoint`.
- Footer form: a footer starting with `BREAKING CHANGE:` followed by a space and description (the alias `BREAKING-CHANGE:` is equivalent to it), placed one blank line after the body.

What changes: every commit subject gains a required `<type>[optional scope]:` prefix, followed by a space, before the description.

What stays unchanged, called out explicitly because a reader might expect it to move:

- Branch naming (`phase/N.M-short-description`, above) is untouched. The Conventional Commits spec says nothing about branch names.
- Sentence-case description text, no emoji, one logical change per commit: unchanged.
- NEVER add Co-Authored-By lines to commit messages. No co-author trailers of any kind. Unchanged: the spec never requires any footer to exist, including a co-author trailer.
- Never `git push --force`. Never amend a published commit. Never `git add -A` blindly. Stage specific files. All three unchanged.

### Gitignored paths

`node_modules/`, `__pycache__/`, `venv/`, `.env`, `.pytest_cache/`, `frontend/build/` or `frontend/dist/`
