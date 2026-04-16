---
name: skill-adapt-verify
description: Verify that a skill copied or adapted from personal-os-work has been properly adapted for this repo. Catches personal-os paths, NWS/Django/GQuery references, broken sub-agent pointers, writing-style violations, and missing frontmatter. Use after copying any .claude/skills/* or .claude/agents/* file from reference-repos/personal-os/ or from any other external repo.
---

# skill-adapt-verify

Automates the "did I fully adapt this copied skill" check. Runs a script that greps the target file for known bad patterns and verifies references resolve.

## When to use

- After copying a skill from `reference-repos/personal-os/.claude/skills/<name>/SKILL.md`
- After copying an agent from `reference-repos/personal-os/.claude/agents/<name>.md`
- After pulling a rule from another repo
- Before committing any `.claude/*` file that originated outside this repo

## When NOT to use

- For skills/agents written from scratch in this repo (no adaptation needed)
- For non-`.claude/` files (this checks adaptation drift, not general lint)

## How it works

The skill runs `scripts/verify_adaptation.py` against a target path. The script returns non-zero on failure and prints a categorized report. Categories checked:

1. Stale paths: references to `NIH/`, `Forge/`, `Learning/`, `Automations/`, `Brainstorming/`, `Computercraft/`, `personal-os-work/`, `GROWTH_SYSTEM.md`, `EXTENSIONS.md`
2. Wrong-repo content: `GQuery`, `NWS`, `django-gquery`, `USWDS`, `Confluence` branding
3. Broken pointers: referenced agents/skills that do not exist in `.claude/agents/` or `.claude/skills/`
4. Writing style: em dashes, bold markdown (`**text**`), emoji, title-case headings
5. Frontmatter: `name` and `description` fields present; `description` is non-trivial (>20 chars)
6. Tool references: mentions of `Confluence`, `Jira`, `Slack`, `Gmail`, `Tavily` tools that this repo does not use

## Invocation

```text
/skill-adapt-verify <path>
```

Examples:

```text
/skill-adapt-verify .claude/skills/eval-harness/SKILL.md
/skill-adapt-verify .claude/agents/docs-sync.md
```

Or run against all recently modified `.claude/` files:

```text
/skill-adapt-verify --recent
```

## Process for Claude

1. Receive the target path from the user (or find recent `.claude/` changes via `git diff --name-only`)
2. Run `python .claude/skills/skill-adapt-verify/scripts/verify_adaptation.py <target>`
3. If the script exits non-zero, read the report and fix each flagged line in place
4. Re-run the script until it passes
5. Report what was changed in a short summary

## Fix conventions

- Stale paths: remove the reference entirely, or replace with the equivalent in this repo (`system-01-data-pipelines/`, `system-02-knowledge-graph/`, `reference-repos/ncbi_ai_agents/`)
- Wrong-repo content: delete. Do not try to translate examples from other repos into ETL examples unless the original concept genuinely applies
- Broken pointers: remove the row from the table, or replace with an existing agent/skill
- Em dashes: replace with a comma, a period, or "in particular" / "specifically" per writing-style.md
- Bold markdown: convert to "word:" format
- Missing frontmatter: add it. Name must match the directory. Description must say what the skill does AND when to use it

## Three-state permissions

Allow: run the script, read files, edit the target to fix flagged issues.
Ask: before deleting a whole section of the target file (more than 10 lines).
Deny: never edit files outside `.claude/`. Never edit the script itself unless the user asks.
