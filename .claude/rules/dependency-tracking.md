## Dependency tracking

Scope: skills and hooks under `.claude/`, and every Python module under `src/system_03_search_agent/`. Rules and agents are exempt (see below).

A skill or hook can point at another file, a routing table, or a config it reads. When that target moves or gets deleted, the reference breaks silently: the skill still triggers, but the step it depends on is gone. Skills are also invoked by name from a large, growing set, so an undeclared dependency is hard to rediscover later. This is the failure mode `depends_on`/`depended_by` exists to prevent.

### Mandatory: skills and hooks

Skills and hooks with YAML frontmatter declare:

```yaml
---
name: my-skill
description: ...
---
```

What counts:

- `depends_on`: other skills/agents/rules this component reads or invokes, config files it consumes
- `depended_by`: index files (CLAUDE.md, README.md) that list it, other components that reference it

### Exempt: rules and agents

Rules and agents do not need `depends_on`/`depended_by` frontmatter:

- Rules: every rule in `.claude/rules/` is loaded automatically each session regardless of whether anything declares a link to it. There is no "undiscoverable" failure mode to guard against.
- Agents: agents are invoked by name from a small, fixed roster listed in CLAUDE.md's sub-agent table. That table is the dependency record; a separate frontmatter field would just duplicate it.

If a rule or agent cross-references another component in its prose (as this rule does), that is fine and encouraged, but it is not a tracked, enforced field.

### For Python modules

Use module docstrings to list cross-module dependencies that aren't obvious from imports:

```python
"""Cypher query tool for the search agent.

Depends on:
    - system_03_search_agent.agent.tools.cypher_query
    - system_03_search_agent.harness.cost_control
    - system_03_search_agent.config.settings (AGE_CONNECTION_STRING)

Reads:
    - Environment variable: AGE_DSN (read-only connection to Hetzner graph)

Writes:
    - logs/query_audit.jsonl
"""
```

### When to update

- Creating a new skill or hook: add both fields from the start
- Modifying a skill or hook: check if dependencies changed
- When a NEW skill or hook starts referencing an existing skill or hook, update the existing one's `depended_by`
- When deleting a skill or hook, grep for its name first and update everywhere that listed it

### Keep it honest

- Only direct dependencies (1 hop), not transitive
- Use relative paths from repo root
- Update when you notice drift, don't let it go stale
- This rule is enforced by convention, not by tooling, and only within its actual scope (skills and hooks). If you skip it, future-you will have to grep through 50 files to figure out what broke
