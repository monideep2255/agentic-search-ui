---
name: repo-dive
description: Deep dive an external repo (typically symlinked into reference/) and produce a first-principles analysis. Adapted from personal-os-work for the data-engineering context. TRIGGER when user says "deep dive this repo", "what can we learn from X", or "analyze the reference at Y". DO NOT TRIGGER for normal code reading.
---

# repo-dive: external repo first-principles analysis

For this repo, "external" means anything in `reference/`. The reference symlinks are read-only context. The job of this skill is to extract the parts that apply to System 1 + System 2 work and ignore the rest.

## When to use

- User shares a path under `reference/` and says "what can we learn from this"
- New reference repo is symlinked and needs an analysis pass
- Designing a new module and looking for prior art in `reference/ncbi_ai_agents-ncbi-kg/`

## When not to use

- Looking up a single file or function (use Read or Grep)
- Already-analyzed reference that has a deep-dive doc
- Anything in `data-pipelines/`, `knowledge-graph/`, `docs/` (that's our own code, not external)

## Process

### Step 1: orient

Read in this order:

1. The repo's own `README.md`
2. The repo's own `CLAUDE.md` (if present)
3. Top-level folder structure (one-level `ls`)
4. `pyproject.toml` or `package.json` (versions, dependencies)
5. The entry-point file (`__main__.py`, `cli.py`, `pipeline.py`)

### Step 2: identify the relevant subset

For this repo, "relevant" means: ETL, BioLink, KGX, PostgreSQL/AGE, NCBI APIs, validation, schema definition. Skip:

- Frontend code, React, Tailwind, Mermaid renderers
- Search agent code, LangGraph, LangChain, FastAPI, MCP
- Deploy automation (Railway, Docker, GitHub Actions)
- Observability dashboards (PostHog, LangSmith, Grafana)

### Step 3: produce the analysis

Write to `docs/reference_analysis/<repo-name>_deep_dive.md` (create the folder if needed). Structure:

```markdown
# <repo name>: relevance to this repo

## What it is
One paragraph. What the repo does, who built it, last updated.

## What we can use
A bulleted list of files, functions, or patterns that apply directly to System 1 or System 2.
For each: file path with line numbers, what it does, how to adapt it.

## What to skip
A bulleted list of features that exist in the reference but do not apply here, with one-line reasons.

## Patterns worth copying
For each pattern: name it, describe it, link to the source file, describe how to apply it in this repo.

## Decisions to flag for DECISIONS.md
Anything where the reference made a decision we should explicitly accept or override.
```

### Step 4: do not vendor files

The reference symlinks are documentation. Never copy a file from `reference/` into `data-pipelines/` or `knowledge-graph/`. Always rewrite from first principles, informed by the reference. This is a project-level rule (see CLAUDE.md "Canonical reference pipeline" section and the user's stated preference).

## Style rules

- Sentence case headings
- No bold, no em dashes, no emoji
- Be honest about what doesn't apply (over half of any reference is usually irrelevant)
- File path references use `relative/path/file.py:42` format
- Mermaid diagrams only when they add information beyond a list

## Anti-patterns

- "Everything in this repo is relevant" — almost never true
- Copying file contents into the analysis doc instead of linking
- Vague "consider adopting this" — always specify the exact target file in our repo
- Sections that just restate the README

## Output

After writing the analysis, report:

1. Repo name and what it is (one sentence)
2. The analysis file path
3. Top 3 patterns worth copying (one line each)
4. Top 1 decision flagged for DECISIONS.md
