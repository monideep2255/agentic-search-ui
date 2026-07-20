---
name: repo-dive
description: Deep dive an external repo (typically symlinked into reference/) and produce a first-principles analysis. Adapted from personal-os-work for the System 3 search-agent context. TRIGGER when user says "deep dive this repo", "what can we learn from X", or "analyze the reference at Y". DO NOT TRIGGER for normal code reading.
---

# repo-dive: external repo first-principles analysis

For this repo, "external" means anything in `reference/`. The reference symlinks are read-only context. The job of this skill is to extract the parts that apply to System 3 (search agent, API, UI) work and ignore the rest.

## When to use

- User shares a path under `reference/` and says "what can we learn from this"
- New reference repo is symlinked and needs an analysis pass
- Designing a new tool or agent node and looking for prior art in `reference/ncbi_ai_agents-ncbi-kg/`

## When not to use

- Looking up a single file or function (use Read or Grep)
- Already-analyzed reference that has a deep-dive doc
- Anything in `src/system_03_search_agent/`, `docs/` (that's our own code, not external)

## Process

### Step 1: orient

Read in this order:

1. The repo's own `README.md`
2. The repo's own `CLAUDE.md` (if present)
3. Top-level folder structure (one-level `ls`)
4. `pyproject.toml` or `package.json` (versions, dependencies)
5. The entry-point file (`__main__.py`, `cli.py`, `main.py`, `app.py`)

### Step 2: identify the relevant subset

For this repo, "relevant" means: search-agent patterns, tool integrations (Layer 1/2/3 data access), agent-loop and guardrail design, FastAPI, LangGraph, React, MCP patterns, API design, eval and citation patterns. De-prioritize:

- ETL parsers, KGX exporters, AGE bulk loaders, BioLink schema mapping, and other System 1/2 internals. That work lives in the separate `agentic-search-data-engineering` repo, not here.

### Step 3: produce the analysis

Write to `docs/reference_analysis/<repo-name>_deep_dive.md` (create the folder if needed). Structure:

```markdown
# <repo name>: relevance to this repo

## What it is
One paragraph. What the repo does, who built it, last updated.

## What we can use
A bulleted list of files, functions, or patterns that apply directly to System 3.
For each: file path with line numbers, what it does, how to adapt it.

## What to skip
A bulleted list of features that exist in the reference but do not apply here, with one-line reasons.

## Patterns worth copying
For each pattern: name it, describe it, link to the source file, describe how to apply it in this repo.

## Decisions to flag for DECISIONS.md
Anything where the reference made a decision we should explicitly accept or override.
```

### Step 4: do not vendor files

The reference symlinks are documentation. Never copy a file from `reference/` into `src/system_03_search_agent/`. Always rewrite from first principles, informed by the reference. This is a project-level rule (see `.claude/rules/file-protection.md`) and the user's stated preference.

## Style rules

- Sentence case headings
- No bold, no em dashes, no emoji
- Be honest about what doesn't apply (over half of any reference is usually irrelevant)
- File path references use `relative/path/file.py:42` format
- Mermaid diagrams only when they add information beyond a list

## Anti-patterns

- "Everything in this repo is relevant": almost never true
- Copying file contents into the analysis doc instead of linking
- Vague "consider adopting this": always specify the exact target file in our repo
- Sections that just restate the README

## Output

After writing the analysis, report:

1. Repo name and what it is (one sentence)
2. The analysis file path
3. Top 3 patterns worth copying (one line each)
4. Top 1 decision flagged for DECISIONS.md
