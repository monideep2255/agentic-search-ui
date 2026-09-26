---
paths:
  - ".claude/hooks/**/*"
  - ".claude/settings.json"
  - "src/system_03_search_agent/**/*.py"
---

## Dependency tracking

Scope: hooks under `.claude/`, and every Python module under `src/system_03_search_agent/`. Skills, rules, and agents are exempt (see below).

A hook can point at another file, a routing table, or a config it reads. When that target moves or gets deleted, the reference breaks silently: the hook still fires, but the step it depends on is gone. Hooks are invisible wiring, nothing lists them in a table and nothing routes to them by name, so a broken hook dependency is genuinely undiscoverable without a declared field. This is the failure mode `depends_on`/`depended_by` exists to prevent.

### Mandatory: hooks

Hooks declare `depends_on`/`depended_by` in a header comment block, since a `.sh` file has no YAML frontmatter to hold it:

```bash
#!/usr/bin/env bash
# scope: project
# depends_on: [.claude/hooks/lib/_json.sh]
# depended_by: [.claude/settings.json]
```

What counts:

- `depends_on`: other files, routing tables, or rules this hook reads or invokes, config files it consumes
- `depended_by`: index files (`.claude/settings.json`, CLAUDE.md) that wire it up, other components that reference it

### Exempt: skills, rules, and agents

Skills, rules, and agents do not need `depends_on`/`depended_by`:

- Skills: every skill is enumerated in CLAUDE.md's skills table, one row per skill naming its purpose and invocation. That table is the dependency record; a separate frontmatter field would just duplicate it, the same reasoning that already applies to agents below.
- Rules: every rule in `.claude/rules/` is loaded automatically regardless of whether anything declares a link to it. A rule with no `paths:` frontmatter loads each session; a rule with `paths:` loads when a file matching one of its globs is read. The one rule kept in `docs/rules/` loads only when read, and `CLAUDE.md` names the situation that calls for it. There is no "undiscoverable" failure mode to guard against.
- Agents: agents are invoked by name from a small, fixed roster listed in CLAUDE.md's sub-agent table. That table is the dependency record; a separate frontmatter field would just duplicate it.

If a skill, rule, or agent cross-references another component in its prose (as this rule does), that is fine and encouraged, but it is not a tracked, enforced field.

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

- Creating a new hook: add both fields from the start
- Modifying a hook: check if dependencies changed
- When a NEW hook starts referencing an existing hook or file, update the existing one's `depended_by`
- When deleting a hook, grep for its name first and update everywhere that listed it

### Keep it honest

- Only direct dependencies (1 hop), not transitive
- Use relative paths from repo root
- Update when you notice drift, don't let it go stale
- This rule is enforced by convention, not by tooling, and only within its actual scope (hooks). If you skip it, future-you will have to grep through 50 files to figure out what broke
- Known open item: `.claude/hooks/session-start.sh` reads `CLAUDE.md` directly but declares no `depends_on` header. This is a real violation under this rule as written, not a hypothetical one. Add the header comment the next time that hook is touched; it is recorded here rather than fixed on the spot so this rule change stays a documentation-only edit.

### Why this rule narrowed from skills-and-hooks to hooks-only

This rule used to make `depends_on`/`depended_by` mandatory for skills too. An audit found only 4 of the (then) 13 skills carried the fields at all, and the skill that carried them most fully still had entries in its `depended_by` list that did not hold up against the files they pointed to. A field absent from most skills and unreliable where present was not tracking dependencies, it was recording intentions. Mandating it bought no real discoverability, since a field nobody keeps current is not more discoverable than no field at all, and CLAUDE.md's skills table already does the discovery job for skills, the same way it already does for agents. The mandate narrowed to hooks because hooks are the one category where that fallback does not exist: nothing else lists them. If this rule is ever widened back to include skills, re-run that audit first and confirm the field would actually be kept current, not just declared once at creation.
